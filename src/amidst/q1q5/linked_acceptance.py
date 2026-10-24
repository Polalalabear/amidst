"""One bounded engineering recipe. No downloads, assets overwrite, GT or formal unlock."""

import hashlib
import http.client
import importlib.metadata
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from amidst.q1q5.baseline_runner import save, verify_composition
from amidst.q1q5.linked_runtime import materialize_rgb, query_inputs, require
from amidst.q1q5.llm_provider import LocalHTTPTransport
from amidst.q1q5.ollama_runtime import validate_config
from amidst.q1q5.production_preflight import read_pinned, strict_json
from amidst.q1q5.runtime_telemetry import ProcessSampler, rss_bytes


def pin(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(ref):
    require(set(ref) == {"path", "file_sha256"}, "PINNED_INPUT_REF")
    return strict_json(read_pinned(Path(ref["path"]), ref["file_sha256"]))


def environment(expected, *, version=importlib.metadata.version):
    require(expected["schema_version"] == "q-demo.linked-environment.v1", "ENVIRONMENT_VERSION")
    actual = dict(
        python=platform.python_version(),
        machine=platform.machine(),
        packages={name: version(name) for name in expected["packages"]},
    )
    require(
        all(actual[k] == expected[k] for k in ["python", "machine", "packages"]),
        "ENVIRONMENT_MISMATCH_NO_INSTALL_PERFORMED",
    )
    return actual


def service_snapshot(base_url, *, fetch=None):
    # Reuse the original loopback-only policy; then read just three bounded metadata endpoints.
    url = urlsplit(LocalHTTPTransport(base_url).base_url)

    def request(path):
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=2)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            raw = response.read(1_048_577)
            require(response.status == 200 and len(raw) <= 1_048_576, "SERVICE_METADATA_REQUIRED")
            return strict_json(raw)
        finally:
            connection.close()

    fetch = fetch or request
    return {
        name: fetch(path)
        for name, path in [("version", "/api/version"), ("tags", "/api/tags"), ("ps", "/api/ps")]
    }


def verify_service(observed, expected, runtime):
    require(
        observed["version"].get("version") == expected["ollama_version"]
        and runtime["model"] == expected["model"]
        and runtime["model_digest"] == expected["model_digest"],
        "SERVICE_VERSION_OR_MODEL",
    )
    matches = [m for m in observed["tags"].get("models", []) if m.get("name") == runtime["model"]]
    require(
        len(matches) == 1 and matches[0].get("digest") == runtime["model_digest"],
        "OBSERVED_MODEL_DIGEST_MISMATCH",
    )


def owned_service_pid(pid, base_url):
    require(type(pid) is int and pid > 0, "EXPLICIT_SERVICE_PID")
    port = urlsplit(LocalHTTPTransport(base_url).base_url).port
    command = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True)
    listeners = subprocess.check_output(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], text=True
    )
    require(
        "ollama" in command and "serve" in command and {int(p) for p in listeners.split()} == {pid},
        "SERVICE_PID_LISTENER_MISMATCH",
    )
    return pid


class ScopedReader:
    """Sample only an explicit listener and its verified Ollama runner children."""

    def __init__(self, service_pid):
        self.service_pid, self.runners = service_pid, []

    def __call__(self, pid):
        value = rss_bytes(pid)
        if pid == self.service_pid:
            children = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True)
            for text in children.stdout.split():
                if not text.isdigit():
                    continue
                child = int(text)
                result = subprocess.run(
                    ["ps", "-p", str(child), "-o", "command="], capture_output=True, text=True
                )
                if (
                    result.returncode == 0
                    and "ollama" in result.stdout
                    and "runner" in result.stdout
                ):
                    self.runners.append(dict(pid=child, rss_bytes=rss_bytes(child)))
        return value

    def report(self):
        pids = sorted({r["pid"] for r in self.runners})
        return dict(
            samples=self.runners,
            per_pid_sampled_rss_peak_bytes={
                str(p): max(
                    (
                        r["rss_bytes"]
                        for r in self.runners
                        if r["pid"] == p and r["rss_bytes"] is not None
                    ),
                    default=None,
                )
                for p in pids
            },
            peaks_must_not_be_summed=True,
            physical_vram_peak_bytes=None,
            missing_reason=None if pids else "NO_VERIFIED_RUNNER_OBSERVED",
        )


def child(command, *, root, logs, service_pid=None, timeout_s=300):
    """Only descendants of this newly started session may be terminated on timeout."""
    with (
        (logs.with_suffix(".stdout")).open("xb") as out,
        (logs.with_suffix(".stderr")).open("xb") as err,
    ):
        process = subprocess.Popen(
            command, cwd=root, stdout=out, stderr=err, start_new_session=True
        )
        pids = dict(orchestrator=os.getpid(), worker=process.pid)
        if service_pid:
            pids["ollama_service"] = service_pid
        reader = ScopedReader(service_pid)
        timed_out = False
        with ProcessSampler(pids, reader=reader) as sampler:
            try:
                returncode = process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                if process.poll() is None and os.getpgid(process.pid) == process.pid:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
                returncode = process.returncode
        save(
            logs.with_suffix(".resources.json"),
            dict(
                processes=sampler.report(),
                runners=reader.report(),
                child_returncode=returncode,
                command=command,
            ),
        )
    require(not timed_out, "OWNED_WORKER_TIMEOUT_SHARED_MODEL_UNTOUCHED")
    require(returncode == 0, "CHILD_FAILED_SEE_PRESERVED_LOGS")


def recipe(repo, config, composition, composition_pin, output, *, permit, service_pid=None):
    require(permit is True, "EXPLICIT_LOCAL_MODEL_PERMISSION")
    require(
        set(config)
        == {
            "schema_version",
            "assets",
            "model_config",
            "runtime",
            "protocol",
            "environment",
            "selected_observation_id",
        }
        and config["schema_version"] == "q-demo.linked-recipe.v1",
        "RECIPE_FIELDS",
    )
    repo, output = Path(repo), Path(output)
    require(
        output.is_absolute()
        and output.resolve() == output
        and not output.exists()
        and output.parent.is_dir()
        and not output.is_relative_to(repo),
        "NEW_EXTERNAL_OUTPUT",
    )
    verified = verify_composition(composition, composition_pin, repo)
    expected = read(config["environment"])
    runtime = read(config["runtime"])
    validate_config(runtime)
    from amidst.q1q5.baseline_runner import load_plan

    load_plan(config["protocol"]["path"], config["protocol"]["file_sha256"], engineering=True)
    read(config["assets"])
    actual = environment(expected)
    before = service_snapshot(runtime["base_url"])
    verify_service(before, expected, runtime)
    if service_pid:
        owned_service_pid(service_pid, runtime["base_url"])
    output.mkdir(mode=0o700)
    save(
        output / "df-before.json",
        {"df_k": subprocess.check_output(["df", "-k", str(output)], text=True)},
    )
    try:
        from shutil import disk_usage

        require(disk_usage(output).free >= 8 * 1024**3, "DISK_SPACE_BELOW_8_GIB")
        model = read(config["model_config"])
        require(
            pin(model["weights"]) == expected["rtdetr_weights_sha256"], "WEIGHTS_ENVIRONMENT_PIN"
        )
        save(
            output / "ENVIRONMENT.json",
            dict(
                actual=actual,
                service_before=before,
                background_load_controlled=False,
                pyproject_sha256=pin(repo / "pyproject.toml"),
                uv_lock_sha256=pin(repo / "uv.lock"),
            ),
        )
        save(output / "RECIPE.json", config)
        materialize_rgb(config["assets"]["path"], config["assets"]["file_sha256"], output / "rgb")
        rgb = output / "rgb/rgb.json"
        command = [
            sys.executable,
            str(repo / "scripts/run_q1q5_linked_baseline.py"),
            "index",
            "--input",
            str(rgb),
            "--input-sha256",
            pin(rgb),
            "--model-config",
            config["model_config"]["path"],
            "--model-config-sha256",
            config["model_config"]["file_sha256"],
            "--allow-local-model-calls",
            "--output",
            str(output / "prepared"),
        ]
        child(
            command, root=repo, logs=output / "index-worker", service_pid=service_pid, timeout_s=120
        )
        prepared = output / "prepared"
        registry = prepared / "registry.json"
        query_inputs(
            prepared, pin(registry), config["selected_observation_id"], runtime, output / "query"
        )
        command = [sys.executable, str(repo / "scripts/run_q1q5_baseline.py")]
        for name, path, file_pin in [
            ("protocol", config["protocol"]["path"], config["protocol"]["file_sha256"]),
            ("cases", output / "query/cases.jsonl", pin(output / "query/cases.jsonl")),
            ("composition", composition, composition_pin),
            ("registry", registry, pin(registry)),
            ("runtime", output / "query/runtime.json", pin(output / "query/runtime.json")),
        ]:
            command += ["--" + name, str(path), "--" + name + "-sha256", file_pin]
        command += [
            "--synthetic",
            "--allow-local-model-calls",
            "--worker-timeout-ms",
            "60000",
            "--lost-after-us",
            "600000",
            "--output",
            str(output / "baseline"),
        ]
        child(command, root=repo, logs=output / "baseline-worker", service_pid=service_pid)
        report = strict_json((output / "baseline/REPORT.json").read_bytes())
        samples = [s for w in report["workers"] for s in w["report"]["samples"]]
        summary = dict(
            schema_version="q-demo.linked-acceptance.v1",
            status=report["status"],
            source_kind="SYNTHETIC",
            formal_run=False,
            counts_for_formal_acceptance=False,
            composition=verified,
            samples=len(samples),
            stage_replays=sum(len(s["stage_replays"]) for s in samples),
            model_calls={
                role: sum(s[role]["provider_calls"] or 0 for s in samples) for role in ["q3", "q5"]
            },
            timeout_calls={
                role: sum(s[role]["timeout_calls"] or 0 for s in samples) for role in ["q3", "q5"]
            },
            llm_used={role: sum(bool(s[role]["used"]) for s in samples) for role in ["q3", "q5"]},
            accuracy=None,
            display_fps=None,
            physical_vram_peak_bytes=None,
            browser_acceptance="SEPARATE_ENGINEERING_CHECK_REQUIRED",
            service_after=service_snapshot(runtime["base_url"]),
        )
        save(output / "ACCEPTANCE.json", summary)
        return summary
    finally:
        save(
            output / "df-after.json",
            {"df_k": subprocess.check_output(["df", "-k", str(output)], text=True)},
        )
        save(
            output / "MANIFEST.json",
            {
                str(p.relative_to(output)): pin(p)
                for p in sorted(output.rglob("*"))
                if p.is_file() and not p.is_symlink()
            },
        )


def server_command(repo, output):
    output = Path(output)
    command = [sys.executable, str(Path(repo) / "scripts/serve_q1q5_linked_workbench.py")]
    for name, path in [
        ("rgb", output / "rgb/rgb.json"),
        ("registry", output / "prepared/registry.json"),
        ("runtime", output / "query/runtime.json"),
    ]:
        command += ["--" + name, str(path), "--" + name + "-sha256", pin(path)]
    return command + [
        "--private-root",
        str(output / "workbench-private"),
        "--receipt",
        str(output / "SERVER.json"),
    ]
