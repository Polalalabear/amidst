"""SYNTHETIC baseline API runner; one explicit worker per case/profile.

Real registry/runtime metadata is supported only with explicit local-model
permission. Formal datasets remain blocked pending independent freeze.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from amidst.q1q5.baseline_telemetry import measure_call

from amidst.q1q5.baseline_runner import (
    execute_sample,
    load_cases,
    load_plan,
    save,
    verify_composition,
)
from amidst.q1q5.production_preflight import metadata_ref, read_pinned, sha, strict_json


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "cases", "composition"):
        p.add_argument("--" + name, required=True, type=Path)
        p.add_argument("--" + name + "-sha256", required=True)
    p.add_argument("--synthetic", required=True, action="store_true")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--worker-timeout-ms", required=True, type=int)
    p.add_argument("--lost-after-us", required=True, type=int)
    p.add_argument("--fixture", choices=["scripted", "timeout", "invalid", "unavailable"])
    p.add_argument("--registry", type=Path)
    p.add_argument("--registry-sha256")
    p.add_argument("--runtime", type=Path)
    p.add_argument("--runtime-sha256")
    p.add_argument("--allow-local-model-calls", action="store_true")
    p.add_argument("--worker-case", help=argparse.SUPPRESS)
    p.add_argument("--worker-profile", help=argparse.SUPPRESS)
    return p


def disk(root, tag):
    save(
        root / ("df-" + tag + ".json"),
        {"df_k": subprocess.check_output(["df", "-k", str(root)], text=True)},
    )
    available = shutil.disk_usage(root).free
    if available < 8 * 1024**3:
        raise RuntimeError("DISK_SPACE_BELOW_8_GIB")
    return available


def configure(args, output):
    if args.fixture:
        # Explicit engineering-only fixtures; no fallback to them on registry errors.
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "tests/q1q5"))
        from test_baseline_runner import fixture_api

        return fixture_api(args.fixture, args.worker_case)
    from amidst.q1q5.api import from_environment

    os.environ["AMIDST_Q1Q5_REGISTRY"] = str(args.registry)
    os.environ["AMIDST_Q1Q5_REGISTRY_SHA256"] = args.registry_sha256
    for key in ("AMIDST_Q1Q5_OLLAMA_RUNTIME", "AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256"):
        os.environ.pop(key, None)
    if args.runtime:
        os.environ["AMIDST_Q1Q5_OLLAMA_RUNTIME"] = str(args.runtime)
        os.environ["AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256"] = args.runtime_sha256
    api = from_environment(None, Path(__file__).resolve().parents[1])
    token = "BASELINE_LOCAL_OPERATOR_ONLY"
    scenes = {run.catalog["scene_id"] for run in api.runs.values()}

    def authorize(session, scene, *, audit=False):
        if session != token or scene not in scenes:
            raise ValueError("denied")

    return api, authorize, token


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    if (
        not args.output.is_absolute()
        or args.output.resolve() != args.output
        or not args.output.parent.is_dir()
        or args.output.exists()
        or args.output.is_relative_to(repo)
    ):
        p.error("new canonical output outside repo with existing parent required")
    if not 1 <= args.worker_timeout_ms <= 300_000 or args.lost_after_us <= 0:
        p.error("explicit bounded worker timeout and positive engineering LOST interval required")
    if bool(args.fixture) == bool(args.registry):
        p.error("exactly one explicit fixture or pinned registry required")
    if args.registry and not args.registry_sha256:
        p.error("registry file pin required")
    if args.runtime and (
        not args.runtime_sha256 or not args.allow_local_model_calls or args.fixture
    ):
        p.error(
            "runtime file pin and explicit local-model permission required; "
            "no mixed fixture/runtime"
        )
    plan = load_plan(args.protocol, args.protocol_sha256, engineering=args.synthetic)
    cases = load_cases(args.cases, args.cases_sha256)
    composition = verify_composition(args.composition, args.composition_sha256, repo)
    profiles = plan["profiles"]
    args.output.mkdir(mode=0o700)
    try:
        before = disk(args.output, "before")
        if args.worker_case:
            case = next(row for row in cases if row["case_id"] == args.worker_case)
            profile = next(row for row in profiles if row["id"] == args.worker_profile)
            (api, authorize, token), setup = measure_call(lambda: configure(args, args.output))
            rows = []

            def request_loader(query):
                return strict_json(
                    read_pinned(
                        metadata_ref(args.cases.parent, query["request_ref"]),
                        query["request_file_sha256"],
                    )
                )

            for iteration in range(1 + plan["execution"]["warm_repeats"]):
                rows.append(
                    execute_sample(
                        api,
                        authorize,
                        case,
                        profile,
                        plan,
                        request_loader=request_loader,
                        session_ref=token,
                        output=args.output / ("sample-" + str(iteration)),
                        iteration=iteration,
                        protocol_sha256=args.protocol_sha256,
                        lost_after_us=args.lost_after_us,
                    )
                )
            report = {
                "status": "COMPLETE"
                if all(row["execution_status"] == "COMPLETE" for row in rows)
                else "ERROR",
                "source_kind": "SYNTHETIC",
                "provider_kind": "SCRIPTED_" + args.fixture.upper()
                if args.fixture
                else "EXPLICIT_LOCAL_RUNTIME",
                "case_id": case["case_id"],
                "profile_id": profile["id"],
                "setup": setup,
                "samples": rows,
                "formal_run": False,
                "accuracy": None,
                "composition": composition,
                "environment": {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "hardware_receipt": None,
                    "background_load_controlled": False,
                },
            }
            save(args.output / "telemetry.json", report)
            return 0 if report["status"] == "COMPLETE" else 1
        save(args.output / "protocol.json", read_pinned(args.protocol, args.protocol_sha256))
        save(
            args.output / "cases.jsonl",
            read_pinned(args.cases, args.cases_sha256, maximum=16_777_216),
        )
        workers = []
        for index, (case, profile) in enumerate(
            (case, profile) for case in cases for profile in profiles
        ):
            target = args.output / ("worker-" + str(index))
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                *(argv if argv is not None else sys.argv[1:]),
            ]
            # Replace only the output option; paths/case IDs are arguments, never shell text.
            command[command.index("--output") + 1] = str(target)
            command += ["--worker-case", case["case_id"], "--worker-profile", profile["id"]]
            entry = {"case_id": case["case_id"], "profile_id": profile["id"], "output": target.name}
            try:
                result = subprocess.run(
                    command, capture_output=True, timeout=args.worker_timeout_ms / 1000
                )
                save(args.output / ("worker-" + str(index) + ".stderr.txt"), result.stderr)
                entry["returncode"] = result.returncode
                if result.returncode == 0 and (target / "telemetry.json").is_file():
                    entry["report"] = strict_json((target / "telemetry.json").read_bytes())
                    entry["status"] = entry["report"]["status"]
                else:
                    entry["status"] = "ERROR"
                    if (target / "telemetry.json").is_file():
                        entry["report"] = strict_json((target / "telemetry.json").read_bytes())
            except subprocess.TimeoutExpired:
                entry.update(status="ERROR", reason="WORKER_TIMEOUT", returncode=None)
                workers.append(entry)
                # A cancelled local HTTP client does not prove the model server stopped.
                break
            workers.append(entry)
        expected = len(cases) * len(profiles)
        report = {
            "schema_version": "q-demo.baseline-run.v1",
            "status": "COMPLETE"
            if len(workers) == expected and all(row["status"] == "COMPLETE" for row in workers)
            else "ERROR",
            "formal_run": False,
            "counts_for_acceptance": False,
            "expected_workers": expected,
            "actual_workers": len(workers),
            "workers": workers,
            "protocol_file_sha256": args.protocol_sha256,
            "case_catalog_file_sha256": args.cases_sha256,
            "free_disk_before_bytes": before,
            "accuracy": None,
            "composition": composition,
            "command": sys.argv[1:] if argv is None else argv,
        }
        save(args.output / "REPORT.json", report)
        return 0 if report["status"] == "COMPLETE" else 1
    finally:
        try:
            disk(args.output, "after")
        finally:
            manifest = {
                str(path.relative_to(args.output)): sha(path.read_bytes())
                for path in sorted(args.output.rglob("*"))
                if path.is_file()
            }
            save(args.output / "MANIFEST.json", manifest)


if __name__ == "__main__":
    raise SystemExit(main())
