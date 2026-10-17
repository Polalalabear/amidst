"""Lite Office launcher: reuse verified local assets, never start PG/Ollama."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

REPO = Path(__file__).resolve().parents[1]
APPLICATION_BASE = '78b99e623f72f0e9f8df24ec54ce57815c1a9cf5'
# Resolve the shared immutable asset checkout from Git, also in nested worktrees.
_common = subprocess.check_output(
    ["git", "rev-parse", "--git-common-dir"], cwd=REPO, text=True
).strip()
ASSETS = Path(
    os.environ.get("OFFICE_ASSETS_REPO", str((REPO / _common).resolve().parent))
).resolve()
EVIDENCE = Path(
    os.environ.get("OFFICE_EVIDENCE_REPO", str(ASSETS / ".local-worktrees/phase1-finalization"))
).resolve()
PRESETS = Path(
    os.environ.get("OFFICE_PRESETS", str(REPO / "configs/office_demo_presets_person_v1.json"))
).resolve()
BUNDLE = Path(os.environ["OFFICE_BUNDLE"]).resolve() if os.environ.get("OFFICE_BUNDLE") else None
UI_REPO = REPO
VENDOR = EVIDENCE / 'frontend/workbench/node_modules/three'
VENDOR_FILES = {'/vendor/three.module.js': 'build/three.module.js',
    '/vendor/three.core.js': 'build/three.core.js',
    '/vendor/OrbitControls.js': 'examples/jsm/controls/OrbitControls.js'}
RUNTIME = Path('/private/tmp') / ('amidst-office-demo-' + str(os.getuid()) + '-' +
    hashlib.sha256(str(REPO).encode()).hexdigest()[:12])
HTTP = build_opener(ProxyHandler({}))


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=10).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url, value=None):
    request = Request(url, None if value is None else json.dumps(value).encode(),
                      {} if value is None else {'Content-Type': 'application/json'})
    with HTTP.open(request, timeout=5) as response:
        return response.read()


def json_fetch(url, value=None):
    return json.loads(fetch(url, value))


def preflight():
    if command("git", "-C", str(REPO), "rev-parse", "--show-toplevel") != str(REPO):
        raise RuntimeError("拒絕啟動：launcher 不在 repository root。")
    branch = command("git", "-C", str(REPO), "branch", "--show-current")
    head = command("git", "-C", str(REPO), "rev-parse", "HEAD")
    print(f"Git branch={branch or 'DETACHED'} HEAD={head[:12]}", flush=True)
    command("git", "-C", str(REPO), "merge-base", "--is-ancestor", APPLICATION_BASE, "HEAD")
    status = command("git", "-C", str(REPO), "status", "--porcelain=v1")
    print("Working tree: " + (status or "CLEAN"), flush=True)
    if any(not line.startswith("??") for line in status.splitlines()):
        raise RuntimeError("tracked modifications detected；請先檢閱並提交，未啟動服務。")
    if status:
        print("WARNING: untracked files 保留，不納入 launcher 來源驗證。", flush=True)
    print(f"Python={sys.executable} environment={sys.prefix}", flush=True)
    commit = command("git", "-C", str(REPO), "log", "-1", "--format=%H", "--", "frontend/workbench")
    free = shutil.disk_usage(REPO).free
    if free < 256 * 1024 * 1024:
        raise RuntimeError("可用空間不足 256 MiB；未建立環境或複製資產。")
    if free < 12 * 1024**3:
        print(f"WARNING: low disk capacity {free // 1024**2} MiB；不複製資產。", flush=True)
    import PIL  # noqa: F401
    import pydantic  # noqa: F401
    from office_demo_backend import contact_config_path, preset_specs, validate_bundle_files

    from amidst.workbench.scene_errors import integrity_error

    default_scene, specs = preset_specs(PRESETS, EVIDENCE, ASSETS, BUNDLE)
    paths = [
        REPO / "scripts/office_demo_backend.py",
        PRESETS,
        REPO / "configs/office_contact_v2.json",
        REPO / "configs/hybrid_contact_v1_1.json",
        REPO / "configs/office_demo_display_v1.json",
        REPO / "data/engineering/office_display_v1.json.gz",
        REPO / "scripts/materialize_office_display.py",
        *(
            UI_REPO / "frontend/workbench" / name
            for name in ("app.mjs", "scene.mjs", "cross-camera.mjs", "style.css")
        ),
        *(VENDOR / name for name in VENDOR_FILES.values()),
        *sorted((REPO / "src/amidst/blind_hypothesis").glob("*.py")),
    ]
    optional_paths = []
    nondefault_paths = set()
    for spec in specs:
        bundle = spec["bundle_path"]
        optional_paths.extend([spec["fixture_path"], bundle / "manifest.json",
                               bundle / "safe_inputs.json"])
        if spec["scene_id"] != default_scene:
            nondefault_paths.update([spec["fixture_path"], bundle / "manifest.json",
                                     bundle / "safe_inputs.json"])
        try:
            if spec.get("load_error"):
                raise ValueError(spec["load_error"])
            fixture = spec["config"]
            if "contact_config" in fixture:
                config_path = REPO / fixture["contact_config"]
                optional_paths.append(config_path)
                if spec["scene_id"] != default_scene:
                    nondefault_paths.add(config_path)
                contact_config_path(fixture)
            if spec.get("hypothesis_binding"):
                from amidst.workbench.blind_hypothesis_integration import _pinned
                binding_path = REPO / spec["hypothesis_binding"]
                optional_paths.append(binding_path)
                if spec["scene_id"] != default_scene:
                    nondefault_paths.add(binding_path)
                binding = json.loads(binding_path.read_bytes())
                dependency_files = [
                    (binding[key], binding[key + "_sha256"]) for key in ("map", "config", "visibility_index", "restricted_policy") if key in binding]
                dependency_files.append((str(spec["fixture_path"].relative_to(REPO)),
                                         binding["fixture_sha256"]))
                for relative, expected in dependency_files:
                    path = REPO / relative
                    optional_paths.append(path)
                    if spec["scene_id"] != default_scene:
                        nondefault_paths.add(path)
                    try:
                        _pinned(REPO, relative, expected)
                    except FileNotFoundError:
                        print(f"HYPOTHESIS_DEPENDENCY_UNAVAILABLE={spec['scene_id']}", flush=True)
                optional_paths.extend(REPO / f for f in (
                    "src/amidst/geometry/source_floor_map.py",
                    "src/amidst/geometry/restricted_policy.py",
                    "src/amidst/geometry/visibility_policy.py"))
            validate_bundle_files(bundle, fixture)
        except (OSError, ValueError, KeyError, TypeError) as error:
            if spec["scene_id"] == default_scene or integrity_error(error):
                raise
            print(f"PRESET_UNAVAILABLE={spec['scene_id']}", flush=True)
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"缺少既有依賴或路徑為 symlink：{path}；未下載或複製。")
    tracked = command(
        "git",
        "-C",
        str(REPO),
        "ls-files",
        "frontend/workbench",
        "frontend/product/timeline.mjs",
        "src/amidst/workbench",
        "src/amidst/engineering",
        "scripts/office_demo_backend.py",
        "configs/office_demo_presets_v1.json",
        "configs/office_demo_fixture_v1.json",
    ).splitlines()
    fingerprint = hashlib.sha256()
    fingerprint_paths = {REPO / p for p in tracked} | set(paths) | set(optional_paths)
    for path in sorted(fingerprint_paths | {Path(__file__)}):
        fingerprint.update(str(path).encode())
        if path.is_symlink():
            raise RuntimeError("PRESET_SYMLINK_REJECTED")
        try:
            fingerprint.update(digest(path).encode() if path.is_file() else b"MISSING")
        except OSError as error:
            required = {REPO / p for p in tracked} | set(paths) | {Path(__file__)}
            if path not in nondefault_paths or path in required:
                raise
            fingerprint.update(("UNREADABLE:" + type(error).__name__).encode())
    return {
        "repo": str(REPO),
        "commit": commit,
        "head": head,
        "branch": branch,
        "fingerprint": fingerprint.hexdigest(),
        "app_sha256": digest(UI_REPO / "frontend/workbench/app.mjs"),
        "scene_sha256": digest(UI_REPO / "frontend/workbench/scene.mjs"),
        "cross_camera_sha256": digest(UI_REPO / "frontend/workbench/cross-camera.mjs"),
        "style_sha256": digest(UI_REPO / "frontend/workbench/style.css"),
        "default_scene_id": default_scene,
        "scene_ids": [s["scene_id"] for s in specs],
        "presets": str(PRESETS),
        "ui_repo": str(UI_REPO),
        "evidence_repo": str(EVIDENCE),
        "free_mib": free // (1024 * 1024),
    }


def process_identity(pid):
    try:
        return command('/bin/ps', '-ww', '-p', str(pid), '-o', 'lstart=,args=')
    except subprocess.CalledProcessError:
        return ''


def owned(record):
    pid = record.get('pid')
    if type(pid) is not int or pid <= 1:
        return False
    identity = process_identity(pid)
    if not (identity and identity == record.get('process_identity')
            and str(Path(__file__)) in identity and '--_serve' in identity):
        return False
    try:
        cwd = command('/usr/sbin/lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn')
        return 'n' + str(REPO) in cwd.splitlines()
    except subprocess.SubprocessError:
        return False


def listener(pid):
    out = command('/usr/sbin/lsof', '-nP', '-a', '-p', str(pid),
                  '-iTCP', '-sTCP:LISTEN', '-Fn')
    ports = [line.split(':')[-1] for line in out.splitlines()
             if line.startswith('n127.0.0.1:')]
    if len(ports) != 1 or not ports[0].isdigit():
        raise RuntimeError('無法核對唯一 localhost listener。')
    return f'http://127.0.0.1:{ports[0]}/'


def readiness(record, config):
    if not owned(record) or listener(record["pid"]) != record["url"]:
        raise RuntimeError("PID／啟動身分／listener 不符；拒絕重用。")
    for key in [
        "repo",
        "commit",
        "fingerprint",
        "app_sha256",
        "style_sha256",
        "scene_sha256",
        "cross_camera_sha256",
    ]:
        if record[key] != config[key]:
            raise RuntimeError("現有 launcher 來源已改變；先以 --stop 停止所屬程序再啟動。")
    url = record["url"]
    remote = json_fetch(url + "__office_launcher")
    if remote != record:
        raise RuntimeError("服務端 launcher metadata 不符。")
    for name, key in [
        ("app.mjs", "app_sha256"),
        ("style.css", "style_sha256"),
        ("scene.mjs", "scene_sha256"),
        ("cross-camera.mjs", "cross_camera_sha256"),
    ]:
        if hashlib.sha256(fetch(url + name)).hexdigest() != config[key]:
            raise RuntimeError("實際 HTTP frontend 與指定 checkout 不符。")
    print("HTTP frontend resources: MATCH (app/style/scene/cross-camera)", flush=True)
    served_app = fetch(url + "app.mjs")
    if any(marker not in served_app for marker in [b"cameraTilesHTML", b"sourcePlaybackStep"]):
        raise RuntimeError("HTTP frontend 缺少新版 Office camera viewer／playback。")
    fetch(url)
    for route, name in VENDOR_FILES.items():
        if hashlib.sha256(fetch(url + route.lstrip("/"))).hexdigest() != digest(VENDOR / name):
            raise RuntimeError("Three.js HTTP 依賴不符。")
    bootstrap = json_fetch(url + "api/bootstrap")
    scene_ids = [s["scene_id"] for s in bootstrap["scenes"]]
    if (
        len(scene_ids) != len(config["scene_ids"])
        or set(scene_ids) != set(config["scene_ids"])
        or scene_ids[0] != config["default_scene_id"]
    ):
        raise RuntimeError("場景 catalog 與預設清單不符。")
    from office_demo_backend import preset_specs

    _, specs = preset_specs(PRESETS, EVIDENCE, ASSETS, BUNDLE)
    session = json_fetch(url + "api/session", {"role": "research"})
    by_id = {entry["scene_id"]: entry for entry in bootstrap["scenes"]}
    degraded = []
    for spec in specs:
        entry = by_id[spec["scene_id"]]
        if entry.get("status") == "UNAVAILABLE":
            if (spec["scene_id"] == config["default_scene_id"] or not entry.get("reason")
                    or entry.get("available") is not False):
                raise RuntimeError("DEFAULT_PRESET_UNAVAILABLE_OR_REASON_MISSING")
            degraded.append({"scene_id": spec["scene_id"], "reason": entry["reason"]})
            if spec["scene_id"] == "blender-office-person":
                print("PERSON_DEMO_READINESS=UNAVAILABLE reason=" + entry["reason"], flush=True)
            continue
        scope = {"session_ref": session["session_ref"], "scene_id": spec["scene_id"]}
        fixture = spec["config"]
        detail = json_fetch(url + "api/scene", scope)["snapshot"]
        quality_status = detail.get("contact_quality_status")
        if quality_status:
            degraded.append({"scene_id": spec["scene_id"], "contact_quality": quality_status})
        for key in ("source_sha256", "dataset_sha256", "run_id", "clock_id"):
            if key in fixture and detail["source_binding"][key] != fixture[key]:
                raise RuntimeError("場景來源或時鐘與 fixture 不符。")
        for timestamp in [0.0, 0.2, 0.4]:
            timeline = json_fetch(
                url + "api/timeline",
                scope | {"camera_ids": fixture["camera_ids"], "timestamp": timestamp},
            )
            frames = timeline["frames"]
            if len(frames) != 2 or any(f["timestamp"] != timestamp for f in frames):
                raise RuntimeError("場景 timeline 未回應雙鏡頭 0.2 秒採樣影格。")
            for frame in frames:
                data = fetch(url + "api/media?" + urlencode(scope | {"ref": frame["frame_ref"]}))
                if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("場景 source frame 未回傳 PNG。")
        if spec["scene_id"] == "blender-office-person":
            problems = person_demo_readiness(url, scope, fixture)
            if problems:
                degraded.append({"scene_id": spec["scene_id"], "demo_checks": problems})
    print("SCENES=" + json.dumps(scene_ids), flush=True)
    print("PRESET_READINESS=" + ("DEGRADED" if degraded else "READY"), flush=True)
    if degraded:
        print("PRESET_DETAILS=" + json.dumps(degraded), flush=True)
    return url


def person_demo_readiness(url, scope, fixture):
    """Check the inferred layer separately from the intentionally UNKNOWN target."""
    interval = fixture["blind_interval"]
    problems = []
    requests = {
        "target_reconstruction": scope | {
            "camera_ids": fixture["camera_ids"],
            "start": interval["start_s"], "end": interval["end_s"],
            "top_k": fixture["top_k"], "observation_ref": fixture["observation_ref"],
        },
        "frame_retrieval": scope | {
            "query_kind": "TIME_RANGE", "camera_ids": fixture["camera_ids"],
            "time_range_s": interval["interior_time_range_s"], "max_frames": 64,
        },
    }
    for action, payload in requests.items():
        try:
            result = json_fetch(url + "api/" + action, payload)
            checked = result.get("blind_hypotheses", {}) if action == "target_reconstruction" else result
            if checked.get("status") != "READY":
                raise ValueError(checked.get("reason") or result.get("reason") or "RESPONSE_NOT_READY")
            if action == "target_reconstruction" and (
                    checked.get("interval", {}).get("start_s") != interval["start_s"]
                    or checked.get("interval", {}).get("end_s") != interval["end_s"]
                    or not checked.get("hypotheses")):
                raise ValueError("D18_ENDPOINT_SCOPE_MISMATCH")
            if action == "frame_retrieval" and (
                    result.get("truncated") is not False
                    or len(result.get("frame_evaluations", {})) != 34):
                raise ValueError("BLIND_INTERVAL_FRAMES_INCOMPLETE")
            print(f"PERSON_DEMO_API={action} READY", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as error:
            from amidst.workbench.scene_errors import public_reason

            problems.append({"api": action, "error_type": type(error).__name__,
                             "reason": public_reason(error, "PERSON_DEMO_API_FAILED")})
    print("PERSON_DEMO_READINESS=" + ("DEGRADED" if problems else "READY"), flush=True)
    if problems:
        print("PERSON_DEMO_DETAILS=" + json.dumps(problems), flush=True)
    return problems


def serve():
    from wsgiref.simple_server import make_server

    from office_demo_backend import application, load_presets

    from amidst.workbench.service import Application, QuietHandler

    config = preflight()
    scene = load_presets(PRESETS, EVIDENCE, ASSETS, BUNDLE)
    # Reuse existing Office factories. Only the three vendor routes use shared dependencies.
    with tempfile.TemporaryDirectory(prefix="state-", dir=RUNTIME) as state:
        app = application(scene, Path(state) / "review.sqlite3", UI_REPO, EVIDENCE)
        vendor_app = Application(app.workbench, EVIDENCE)
        record = {}

        def dispatch(environ, start_response):
            if environ.get("PATH_INFO") == "/__office_launcher":
                host = urlsplit("//" + environ.get("HTTP_HOST", ""))
                if (
                    environ.get("REQUEST_METHOD") != "GET"
                    or host.hostname != "127.0.0.1"
                    or host.port != server.server_port
                    or host.username
                    or host.password
                    or host.path
                    or host.query
                    or host.fragment
                ):
                    start_response("403 Forbidden", [("Content-Length", "0")])
                    return [b""]
                body = json.dumps(record, sort_keys=True).encode()
                start_response(
                    "200 OK",
                    [
                        ("Content-Type", "application/json"),
                        ("Content-Length", str(len(body))),
                        ("Cache-Control", "no-store"),
                    ],
                )
                return [body]
            target = vendor_app if environ.get("PATH_INFO") in VENDOR_FILES else app
            return target(environ, start_response)

        with make_server(
            "127.0.0.1",
            int(os.environ.get("OFFICE_PORT", "0")),
            dispatch,
            handler_class=QuietHandler,
        ) as server:
            record.update(
                config
                | {
                    "pid": os.getpid(),
                    "process_identity": process_identity(os.getpid()),
                    "executable": sys.executable,
                    "cwd": str(REPO),
                    "management": "EXPLICIT_STOP_OR_RESTART",
                    "url": f"http://127.0.0.1:{server.server_port}/",
                    "nonce": secrets.token_hex(16),
                }
            )
            pending = RUNTIME / "runtime.json.tmp"
            pending.write_text(json.dumps(record, indent=2) + "\n")
            pending.replace(RUNTIME / "runtime.json")

            def exit_owned(signum, frame):
                raise SystemExit(0)

            signal.signal(signal.SIGTERM, exit_owned)
            try:
                server.serve_forever()
            finally:
                path = RUNTIME / "runtime.json"
                if path.is_file() and json.loads(path.read_text()).get("nonce") == record["nonce"]:
                    path.unlink()


def service_status():
    for name in ['postgres', 'ollama']:
        result = subprocess.run(['/usr/bin/pgrep', '-x', name], capture_output=True,
                                text=True, timeout=5)
        pids = ','.join(result.stdout.split()) or 'none'
        print(f'{name}: ' + ('已存在' if result.returncode == 0 else '未運行') +
              f'（PID {pids}；Lite 不需要、未啟動、未連線）')


def inventory(record=None):
    """No automatic idle inference: listener traffic and CPU cannot prove non-use."""
    rows = command('/bin/ps', '-ww', '-U', str(os.getuid()), '-o', 'pid=,comm=')
    found = False
    for row in rows.splitlines():
        pid_text, executable = row.strip().split(None, 1)
        if 'python' not in executable.lower():
            continue
        pid = int(pid_text)
        if pid == os.getpid():
            continue  # The foreground controller is not a previous service.
        identity = process_identity(pid)
        if not any(name in identity for name in (
                'start_office_demo.py', 'office_demo_backend.py', 'amidst.workbench',
                'start_local_demo.py')):
            continue
        found = True
        current = record and pid == record.get('pid') and owned(record)
        category = 'CURRENT_ACTIVE' if current else 'OWNERSHIP_UNKNOWN'
        print(f'Previous Demo PID={pid} executable={executable} {category}; preserved', flush=True)
        print(f'  identity={identity}', flush=True)
        for flags in [('-d', 'cwd'), ('-iTCP', '-sTCP:LISTEN')]:
            result = subprocess.run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid),
                                     *flags, '-Fn'], capture_output=True, text=True, timeout=5)
            print('  ' + result.stdout.strip().replace('\n', ' '), flush=True)
    if not found:
        print('Previous Demo: none detected', flush=True)
    print('OLD_IDLE_VERIFIED=none; no independent idle/session-release evidence. '
          'OWNERSHIP_UNKNOWN/IN_USE_BY_OTHER_SESSION are preserved.', flush=True)


def stop_managed(record, path):
    if record is None or not owned(record):
        print('沒有可確認由本 launcher 啟動的存活程序；未送出任何信號。')
        return
    # Explicit stop/restart is authorization for this service only, not an idle claim.
    pid = record['pid']
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not owned(record):
            if path.exists() and json.loads(path.read_text()).get('nonce') == record.get('nonce'):
                path.unlink()
            print(f'已停止 managed Demo PID {pid} (SIGTERM)；其他服務保留。', flush=True)
            return
        time.sleep(0.1)
    raise RuntimeError('SIGTERM 後 5 秒程序尚未退出；未強制終止。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['start', 'status', 'stop', 'restart'],
                        default='start')
    parser.add_argument('--mode', choices=['lite', 'backend', 'agent'], default='lite')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--_serve', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.mode != 'lite':
        parser.error('僅支援 Lite；Backend/Agent 未接入安全生命週期。')
    if args.status and args.stop:
        parser.error('--status 與 --stop 不可同時使用')
    action = 'stop' if args.stop else 'status' if args.status else args.action
    port = int(os.environ.get('OFFICE_PORT', '0'))
    if not 0 <= port <= 65535:
        parser.error('OFFICE_PORT 必須為 0..65535；0 由系統選取')
    os.umask(0o077)
    if RUNTIME.is_symlink():
        raise RuntimeError('拒絕使用 symlink runtime directory。')
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    if RUNTIME.stat().st_uid != os.getuid() or RUNTIME.stat().st_mode & 0o077:
        raise RuntimeError('Runtime directory 必須由目前使用者擁有且權限為 700。')
    if args._serve:
        serve()
        return
    lock_path = RUNTIME / 'launcher.lock'
    if lock_path.is_symlink():
        raise RuntimeError('拒絕使用 symlink lock。')
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('另一個 launcher 正在啟動；稍後以 status 查詢。') from None
        path = RUNTIME / 'runtime.json'
        if path.is_symlink():
            raise RuntimeError('拒絕使用 symlink runtime record。')
        record = json.loads(path.read_text()) if path.exists() else None
        inventory(record)
        if action == 'stop':
            stop_managed(record, path)
            return
        # Validate before restart so failed preflight preserves a healthy old service.
        print('Stage: preflight', flush=True)
        config = preflight()
        if action == 'restart':
            stop_managed(record, path)
            record = None
        if record and owned(record):
            print('Stage: verify current service', flush=True)
            url = readiness(record, config)
            print('重用已驗證的 managed Demo。', flush=True)
        else:
            if action == 'status':
                raise RuntimeError('沒有可確認的 managed Demo。')
            rows = command('/bin/ps', '-ww', '-U', str(os.getuid()), '-o', 'pid=,args=')
            for line in rows.splitlines():
                if str(Path(__file__)) in line and '--_serve' in line:
                    raise RuntimeError('發現無法映射 runtime record 的 Office 程序；'
                                       '保留並拒絕重複啟動。')
            log_path = RUNTIME / 'startup.log'
            if log_path.is_symlink():
                raise RuntimeError('拒絕使用 symlink log。')
            if path.exists():
                path.unlink()
            env = os.environ | {'PYTHONPATH': str(REPO / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
            print(f'Stage: initialize (requested port={port}; log={log_path})', flush=True)
            with log_path.open('w') as log:
                child = subprocess.Popen([sys.executable, str(Path(__file__)), '--_serve'],
                    cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 35
            try:
                while True:
                    if child.poll() is not None:
                        raise RuntimeError('Stage initialize failed: '
                                           + log_path.read_text()[-4000:])
                    if path.is_file():
                        record = json.loads(path.read_text())
                        if record['pid'] != child.pid:
                            raise RuntimeError('Runtime PID 不是本次啟動的 child。')
                        print(f'Stage: HTTP health PID={child.pid} '
                              f'port={urlsplit(record["url"]).port}',
                              flush=True)
                        url = readiness(record, config)
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Stage initialize timeout (35s)；未宣告 READY。')
                    time.sleep(0.2)
            except BaseException:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f'WARNING: child PID={child.pid} SIGTERM timeout；保留管理資訊。',
                              file=sys.stderr)
                if child.poll() is not None and path.exists():
                    if json.loads(path.read_text()).get('pid') == child.pid:
                        path.unlink()
                raise
        print(f"\nOFFICE_DEMO_URL={url}\nHEAD={config['head']}\n"
              f"FRONTEND_COMMIT={config['commit']}\nFRONTEND_REPO={REPO}\n"
              f"WORKBENCH_READY=YES PID={record['pid']} PORT={urlsplit(url).port}\n"
              f"HTTP_HEALTH=PASS FRONTEND_MATCH=PASS free={config['free_mib']} MiB", flush=True)
        service_status()
        launcher = REPO / 'start-office-demo.command'
        print(f'狀態: "{launcher}" status\n停止: "{launcher}" stop\n'
              f'重啟: "{launcher}" restart\n'
              f'日誌: tail -n 60 "{RUNTIME / "startup.log"}"\n'
              f'版本: git -C "{REPO}" log -1 --oneline\n'
              'Terminal 關閉後服務維持受 runtime record 管理；請用 stop 停止。\n'
              'WARNING: HTTP READY 不代表完整 8 分鐘 Demo 或空間精度驗收通過。', flush=True)
        if not args.no_open and action != 'status':
            subprocess.run(['/usr/bin/open', url], check=False, timeout=10)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError, RuntimeError,
            subprocess.SubprocessError) as error:
        print(f'OFFICE_DEMO_ERROR: {error}', file=sys.stderr)
        raise SystemExit(1) from None
