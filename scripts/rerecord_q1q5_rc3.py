"""Re-record the 8+8+160 engineering cases only after B1/#257 is merged.

This operator tool never repairs old responses, modifies the kit, merges a PR,
renders RGB, or rebuilds a detector index. All generated recordings stay LOCAL.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from copy import deepcopy
from pathlib import Path
from urllib.request import urlopen

REPOSITORY = "Polalalabear/amidst"
KIT_COMMIT = "4e3edfcf3fb984f590ce5d2af2e6b44a9cd7500c"
B1 = "b761a336c75879870a1e5e748fa032461f4d35d2"
D85 = "3a87bc5216c186d7f32c77be7fbc3d29118b907a"
CONTRACT_MERGE = "83da40f075e7981b02b4b2150ccf0cf9128e4008"
CONTRACT = "docs/contracts/Q1_Q2_FIRST_DEMO_V1.md"
CONTRACT_SHA = "b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04"
PROTOCOL_SHA = "db6e11d5483470b27bac3c88794d8dc5f79177ab948c7d416e87b89906bcf634"
PACKS = {
    "dynamic": ("q1q5-dynamic-baseline-v1_20261025", 8),
    "linked": ("q1q5-linked-baseline-v1_20261024", 8),
    "runner": ("q1q5-baseline-runner-v1_20261024", 160),
}
MODES = ("scripted", "timeout", "invalid", "unavailable")
EXPORT_PATHS = (
    "src/amidst/__init__.py", "src/amidst/q1q5", "tests/q1q5",
    "configs/q1q5/prompts", "configs/q1q5/baseline_v1_protocol.json",
    "scripts/run_q1q5_baseline.py", CONTRACT,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_digest(path):
    require(path.resolve() == path and path.is_file(), "MANIFEST_REGULAR_FILE_REQUIRED")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def read(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path and path.is_file(),
            "REGULAR_CANONICAL_FILE_REQUIRED: " + str(path))
    require(path.stat().st_size <= 32 * 1024**2, "METADATA_TOO_LARGE")
    return path.read_bytes()


def load(path):
    return json.loads(read(path))


def save(path, value):
    raw = value if isinstance(value, bytes) else (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def pin(path):
    raw = read(path)
    return {"sha256": digest(raw), "bytes": len(raw), "mtime_ns": path.stat().st_mtime_ns}


def inventory(paths):
    return {str(path): pin(path) for path in sorted(set(paths))}


def verify_inventory(pins):
    for name, expected in pins.items():
        require(pin(Path(name)) == expected, "OLD_INPUT_OR_RECORDING_CHANGED: " + name)


def recorded_paths(root):
    return sorted(path for path in root.glob("worker-*/sample-0/*/recorded") if path.is_dir())


def make_plan(artifacts):
    require(artifacts.is_absolute() and artifacts.resolve() == artifacts, "ARTIFACT_ROOT")
    packs, inputs = {}, []
    for name, (folder, expected) in PACKS.items():
        root = artifacts / folder
        runs = [root / ("run-" + mode) for mode in MODES] if name == "runner" else [
            root / "run/baseline"]
        selected = [path for run in runs for path in recorded_paths(run)]
        require(len(selected) == expected, "OLD_SELECTION_COUNT: " + name)
        protocol = runs[0] / "protocol.json"
        require(digest(read(protocol)) == PROTOCOL_SHA, "ORIGINAL_PROTOCOL_PIN")
        cases = root / ("CASES.synthetic.jsonl" if name == "runner" else "run/query/cases.jsonl")
        entry = {"root": str(root), "protocol": str(protocol), "cases": str(cases),
                 "expected": expected, "selected": [str(p.relative_to(root)) for p in selected]}
        inputs += [protocol, cases, root / "DELIVERY_MANIFEST.json"]
        if name != "runner":
            registry, runtime = root / "run/prepared/registry.json", root / "run/query/runtime.json"
            doc = load(registry)
            require(doc.get("recording_root") is None, "OLD_RECORDING_ROOT_MUST_BE_NULL")
            data_root = Path(doc["data_root"])
            require(data_root == registry.parent, "REGISTRY_ROOT")
            inputs += [registry, runtime]
            for item in doc["documents"].values():
                p = data_root / item["path"]
                require(p.resolve().is_relative_to(data_root), "REGISTRY_PATH_ESCAPE")
                require(digest(read(p)) == item["file_sha256"], "REGISTRY_DOCUMENT_PIN")
                inputs.append(p)
            entry.update(registry=str(registry), runtime=str(runtime))
        # Freeze original domain context as well as the old immutable outputs.
        # None of these old responses are passed to inference or copied as new output.
        for path in selected:
            inputs += [p for p in path.iterdir() if p.is_file()]
        packs[name] = entry
    return {"schema_version": "q-demo.rc5-rerecord-plan.v2", "formal_acceptance": False,
            "expected_recordings": 176, "kit_commit": KIT_COMMIT, "contract_file_sha256": CONTRACT_SHA,
            "packs": packs, "immutable_files": inventory(inputs),
            "execution_gate": "CLAUDE_REVIEW_AND_MERGE_OF_D85_PR231_REQUIRED",
            "selection": "ALL_FIRST_CALL_BOTH_STAGES; original warm_repeats=2 retained",
            "accuracy": None}


def command(args, *, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True).stdout


def product_gate(repo, product_commit):
    require(re.fullmatch(r"[0-9a-f]{40}", product_commit) is not None, "FULL_PRODUCT_SHA")
    live = json.loads(command([
        "gh", "pr", "view", "257", "--repo", REPOSITORY, "--json",
        "state,baseRefName,mergeCommit,mergedAt,headRefOid,url",
    ]))
    require(live["state"] == "MERGED" and live["mergedAt"]
            and live["baseRefName"] == "codex/q1q5-staging"
            and live["mergeCommit"]["oid"] == product_commit, "B1_PR257_NOT_MERGED_AT_REQUESTED_SHA")
    for ancestor in (D85, CONTRACT_MERGE, B1):
        command(["git", "merge-base", "--is-ancestor", ancestor, product_commit], cwd=repo)
    require(digest(command(["git", "show", product_commit + ":" + CONTRACT], cwd=repo))
            == CONTRACT_SHA, "PRODUCT_CONTRACT_PIN")
    kit = json.loads(command(["gh", "pr", "view", "127", "--repo", REPOSITORY,
                              "--json", "headRefOid,url"]))
    require(kit["headRefOid"] == KIT_COMMIT, "KIT_HEAD_CHANGED_REVIEW_REQUIRED")
    live["independent_kit"] = kit
    return live


def export_product(repo, commit, root):
    root.mkdir(mode=0o700)
    listing = command(["git", "ls-tree", "-r", "-z", commit, "--", *EXPORT_PATHS], cwd=repo)
    files = {}
    for row in listing.split(b"\0"):
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        name = name.decode()
        require(mode in {"100644", "100755"} and kind == "blob", "SOURCE_NOT_REGULAR")
        require(Path(name).suffix in {".py", ".json", ".txt", ".md"}, "SOURCE_EXTENSION")
        raw = command(["git", "cat-file", "blob", oid], cwd=repo)
        require(len(raw) <= 4 * 1024**2, "SOURCE_TOO_LARGE")
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        save(target, raw)
        files[name] = {"sha256": digest(raw), "commit": commit}
    for name in ("scripts/run_q1q5_baseline.py", "tests/q1q5/test_baseline_runner.py",
                 "src/amidst/q1q5/api.py"):
        require(name in files, "PRODUCT_SOURCE_INCOMPLETE: " + name)
    return {"scope": "ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT", "files": files,
            "source_product_commit": commit,
            "note": "Legacy runner envelope; every source blob is from this one merged product commit."}


def migrate_runtime(old, source):
    value = deepcopy(old)
    for name, file in (("q3_template", "q3_parse_v2.txt"), ("q5_template", "q5_agent_v2.txt")):
        raw = read(source / "configs/q1q5/prompts" / file)
        value[name]["text"], value[name]["sha256"] = raw.decode(), digest(raw)
    value["content_sha256"] = digest(canonical({k: v for k, v in value.items()
                                               if k != "content_sha256"}))
    return value


def migrate_registry(old_path, source, destination, *, scope_builder=None):
    """New engineering metadata only; original index/records bytes stay pinned."""
    if scope_builder is None:
        import sys

        sys.path.insert(0, str(source / "src"))
        from amidst.q1q5.engineering_scope import bind_engineering_scope

        scope_builder = bind_engineering_scope
    old = load(old_path)
    value = deepcopy(old)
    require(value["schema_version"] == "q-demo.api-registry.v1" and len(value["runs"]) == 1,
            "SINGLE_ENGINEERING_REGISTRY_REQUIRED")
    item = value["runs"][0]
    require(item["source_kind"] == "SYNTHETIC", "SYNTHETIC_REGISTRY_REQUIRED")
    original_root = Path(value["data_root"])
    require(original_root.is_absolute() and original_root.resolve() == original_root, "REGISTRY_ROOT")
    docs = {}
    for ref, metadata in value["documents"].items():
        rel = Path(metadata["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "SAFE_METADATA_PATH")
        raw = read(original_root / rel)
        require(digest(raw) == metadata["file_sha256"], "ORIGINAL_METADATA_PIN")
        docs[ref] = raw
    rref, cref = item["region_ref"], item["camera_ref"]
    region, camera, scope, scope_raw = scope_builder(json.loads(docs[rref]), json.loads(docs[cref]))
    docs[rref], docs[cref] = canonical(region), canonical(camera)
    scope_ref = "tracking_scope_rc4"
    require(scope_ref not in value["documents"], "NEW_SCOPE_REF_REQUIRED")
    docs[scope_ref] = scope_raw
    value["documents"][scope_ref] = dict(path="tracking_scope.json", file_sha256=digest(scope_raw),
                                         schema_version=scope["schema_version"])
    item["tracking_scope_ref"] = scope_ref
    destination.mkdir(mode=0o700)
    value["data_root"] = str(destination)
    # These sources have no input recordings. Never migrate private recording assets.
    require(not value["recordings"] and value["recording_root"] is None, "EMPTY_INPUT_RECORDINGS_REQUIRED")
    changed = {}
    for ref, raw in docs.items():
        metadata = value["documents"][ref]
        old_pin = metadata["file_sha256"] if ref != scope_ref else None
        metadata["file_sha256"] = digest(raw)
        if ref in (rref, cref):
            metadata["content_sha256"] = json.loads(raw)["content_sha256"]
        target = destination / metadata["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        save(target, raw)
        if old_pin != digest(raw):
            changed[ref] = dict(old_file_sha256=old_pin, new_file_sha256=digest(raw))
    value["content_sha256"] = digest(canonical({k: v for k, v in value.items() if k != "content_sha256"}))
    target = destination / "registry.json"
    save(target, value)
    return target, dict(old_registry_sha256=digest(read(old_path)), new_registry_sha256=digest(read(target)),
                        changed_documents=changed, tracking_scope_sha256=digest(scope_raw),
                        original_index_and_records_bytes_preserved=True)


def disk_receipt(root):
    df = command(["df", "-k", str(root)]).decode()
    free = shutil.disk_usage(root).free
    require(free >= 8 * 1024**3, "DISK_SPACE_BELOW_8_GIB")
    return {"df_k": df, "free_bytes": free}


def model_receipt(runtime):
    require(runtime["base_url"] == "http://127.0.0.1:11437", "PINNED_LOCAL_ENDPOINT_REQUIRED")
    with urlopen(runtime["base_url"] + "/api/tags", timeout=5) as response:
        tags = json.load(response)
    require(any(row.get("name") == runtime["model"] and row.get("digest") == runtime["model_digest"]
                for row in tags["models"]), "LOCAL_MODEL_DIGEST_MISMATCH")
    return {"base_url": runtime["base_url"], "model": runtime["model"],
            "model_digest": runtime["model_digest"], "tags": tags,
            "background_load_controlled": False}


def validate_recording(root):
    response = load(root / "case.response.json")
    reasons = response.get("reasons")
    require(isinstance(reasons, list) and all(isinstance(r, str) and r for r in reasons)
            and len(set(reasons)) == len(reasons), "FRESH_REASONS_REQUIRED")
    links = response.get("links_ref")
    count = 0
    if links:
        require(Path(links).name == links, "LINK_JOURNAL_NAME")
        for line in read(root / links).splitlines():
            row = json.loads(line)
            require(row.get("schema_version") == "q-demo.link-record.v2"
                    and "matching_audit" in row, "FRESH_LINK_V2_REQUIRED")
            count += 1
    scope = response.get("resolved_scope")
    require(isinstance(scope, dict) and "tracking_scope_sha256" in scope, "FRESH_SCOPE_KEY_REQUIRED")
    if response["schema_version"] in {"q-demo.q1-response.v1", "q-demo.q3-response.v1"}:
        require(scope["tracking_scope_sha256"] is None, "FRESH_QUERY_SCOPE_MUST_BE_NULL")
    if response["schema_version"] == "q-demo.q2-response.v1":
        scope_pin = scope["tracking_scope_sha256"]
        require(isinstance(scope_pin, str) and re.fullmatch(r"[0-9a-f]{64}", scope_pin)
                and digest(read(root / "tracking_scope.json")) == scope_pin, "FRESH_SCOPE_PIN_REQUIRED")
        decisions = response.get("decisions_ref")
        if decisions:
            require(Path(decisions).name == decisions, "DECISION_JOURNAL_NAME")
            for line in read(root / decisions).splitlines():
                require(json.loads(line).get("input_pins", {}).get("tracking_scope_sha256") == scope_pin,
                        "FRESH_DECISION_SCOPE_PIN_REQUIRED")
    return {"response_schema": response["schema_version"], "reasons": reasons,
            "link_v2_rows": count}


def collect(plan_pack, run_roots, destination):
    selected = [p for root in run_roots for p in recorded_paths(root)]
    require(len(selected) == plan_pack["expected"], "FRESH_SELECTION_COUNT")
    rows = []
    for i, (old, fresh) in enumerate(zip(plan_pack["selected"], selected, strict=True)):
        check = validate_recording(fresh)
        target = destination / "recordings" / str(i)
        target.mkdir(parents=True)
        files = {}
        for path in sorted(fresh.iterdir()):
            require(path.suffix in {".json", ".jsonl"}, "DOMAIN_METADATA_ONLY")
            raw = read(path)
            save(target / path.name, raw)
            files[path.name] = digest(raw)
        context = {}
        for name in ("parameter_set.json", "clock_mapping.json", "region_graph.json",
                     "camera_graph.json", "detection_index.json", "detection_index.records.jsonl", "tracking_scope.json"):
            old_path = Path(plan_pack["root"]) / old / name
            if not old_path.is_file() and (fresh / name).is_file():
                context[name] = {"old_sha256": None, "fresh_sha256": digest(read(fresh / name)),
                                 "same_bytes": False, "change": "ADDED_BY_NEW_PRODUCT"}
            if old_path.is_file() and (fresh / name).is_file():
                old_sha, new_sha = digest(read(old_path)), digest(read(fresh / name))
                context[name] = {"old_sha256": old_sha, "fresh_sha256": new_sha,
                                 "same_bytes": old_sha == new_sha}
        rows.append({"id": i, "old_recorded": old, "fresh_recorded": str(fresh),
                     "files": files, "mechanical_checks": check, "context_comparison": context,
                     "controlled_context_changed": any(not v["same_bytes"] for v in context.values())})
    return rows


def execute(args):
    require(digest(read(args.plan)) == args.plan_sha256, "PLAN_PIN")
    plan = load(args.plan)
    require(plan["kit_commit"] == KIT_COMMIT and plan["expected_recordings"] == 176
            and plan["contract_file_sha256"] == CONTRACT_SHA, "PLAN_VERSION")
    live = product_gate(args.repo, args.product_commit)
    verify_inventory(plan["immutable_files"])
    require(args.allow_local_model_calls, "EXPLICIT_LOCAL_MODEL_PERMISSION_REQUIRED")
    require(args.output.is_absolute() and args.output.resolve() == args.output
            and not args.output.exists() and args.output.parent.is_dir()
            and not args.output.is_relative_to(args.repo.resolve()), "NEW_LOCAL_OUTPUT_REQUIRED")
    before = disk_receipt(args.output.parent)
    args.output.mkdir(mode=0o700)
    save(args.output / "PLAN.json", read(args.plan))
    save(args.output / "GATE.json", live)
    save(args.output / "df-before.json", before)
    commands = []
    try:
        source = args.output / "source"
        composition = export_product(args.repo, args.product_commit, source)
        composition_path = args.output / "COMPOSITION.json"
        save(composition_path, composition)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH=str(source / "src") + os.pathsep + str(source / "tests/q1q5"))
        for name, pack in plan["packs"].items():
            destination = args.output / name
            destination.mkdir()
            roots = []
            runtime_path = destination / "runtime.json"
            if name != "runner":
                old = load(Path(pack["runtime"]))
                save(destination / "MODEL_READY.json", model_receipt(old))
                save(runtime_path, migrate_runtime(old, source))
                registry_path, migration = migrate_registry(Path(pack["registry"]), source,
                                                              destination / "prepared")
                save(destination / "SCOPE_MIGRATION.json", migration)
                save(destination / "RUNTIME_MIGRATION.json", {
                    "old_file_sha256": digest(read(Path(pack["runtime"]))),
                    "new_file_sha256": digest(read(runtime_path)),
                    "changed_fields": [k for k in old if old[k] != load(runtime_path)[k]],
                    "model_parameters_budgets_unchanged": True,
                })
            for mode in MODES if name == "runner" else (None,):
                disk_receipt(args.output)
                target = destination / ("run-" + mode if mode else "run")
                protocol, cases = Path(pack["protocol"]), Path(pack["cases"])
                argv = [str(args.python), str(source / "scripts/run_q1q5_baseline.py"),
                        "--synthetic", "--protocol", str(protocol), "--protocol-sha256", PROTOCOL_SHA,
                        "--cases", str(cases), "--cases-sha256", digest(read(cases)),
                        "--composition", str(composition_path), "--composition-sha256",
                        digest(read(composition_path)), "--worker-timeout-ms", "60000",
                        "--lost-after-us", "600000", "--output", str(target)]
                if mode:
                    argv += ["--fixture", mode]
                else:
                    registry = registry_path
                    argv += ["--registry", str(registry), "--registry-sha256", digest(read(registry)),
                             "--runtime", str(runtime_path), "--runtime-sha256",
                             digest(read(runtime_path)), "--allow-local-model-calls"]
                started = time.time()
                result = subprocess.run(argv, env=env, capture_output=True)
                commands.append({"argv": argv, "started_unix": started,
                                 "elapsed_s": time.time() - started, "returncode": result.returncode})
                save(destination / ("stdout-" + str(mode) + ".txt"), result.stdout)
                save(destination / ("stderr-" + str(mode) + ".txt"), result.stderr)
                require(result.returncode == 0, "NEW_PRODUCT_RUN_FAILED: " + str(target))
                require(load(target / "REPORT.json")["status"] == "COMPLETE", "RUN_INCOMPLETE")
                roots.append(target)
            rows = collect(pack, roots, destination)
            save(destination / "HANDOFF.json", {
                "product_commit": args.product_commit, "kit_commit": KIT_COMMIT,
                "contract_file_sha256": CONTRACT_SHA, "recordings": rows,
                "selection": plan["selection"], "formal_acceptance": False,
                "independent_rc5_status": "PENDING_CLAUDE", "accuracy": None,
                "context_note": "Missing context remains INCOMPLETE; no fabricated supplemental inputs.",
            })
            disk_receipt(args.output)
            with zipfile.ZipFile(destination / "claude-recordings.zip", "x", zipfile.ZIP_DEFLATED) as z:
                for file in sorted((destination / "recordings").rglob("*")):
                    if file.is_file():
                        z.write(file, str(file.relative_to(destination)))
                z.write(destination / "HANDOFF.json", "HANDOFF.json")
        save(args.output / "STATUS.json", {"fresh_recordings": 176, "independent_rc5": "PENDING_CLAUDE",
                                           "AC7": "NOT_ACCEPTED", "formal_acceptance": False})
    finally:
        save(args.output / "COMMANDS.json", commands)
        verify_inventory(plan["immutable_files"])
        save(args.output / "df-after.json", disk_receipt(args.output))
        save(args.output / "MANIFEST.json", {
            str(p.relative_to(args.output)): file_digest(p) for p in sorted(args.output.rglob("*"))
            if p.is_file()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--artifacts", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    run = sub.add_parser("run")
    for name in ("plan", "repo", "output", "python"):
        run.add_argument("--" + name, required=True, type=Path)
    run.add_argument("--plan-sha256", required=True)
    run.add_argument("--product-commit", required=True)
    run.add_argument("--allow-local-model-calls", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "plan":
        save(args.output, make_plan(args.artifacts))
    else:
        execute(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
