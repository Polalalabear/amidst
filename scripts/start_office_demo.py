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
EXPECTED = Path('/Users/polalabear/Developer/amidst-claude')
BRANCH = 'claude/office-demo-visualization'
REPAIR_BRANCH = 'fix/auditorium-display-geometry'
TASK_B = '3cc3f6885246ebdffc1af3315347341cc81707b2'
TASK1 = '3181cff84ac2c712f66da0e24a3387dee672df03'
EVIDENCE = Path(os.environ.get('OFFICE_EVIDENCE_REPO',
    '/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization')).resolve()
BUNDLE = Path(os.environ.get('OFFICE_BUNDLE', str(
    EVIDENCE / 'data/engineering/local_run/blender_camera_v1/office'))).resolve()
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
    if REPO.resolve() != EXPECTED or command('git', '-C', str(REPO),
            'rev-parse', '--show-toplevel') != str(EXPECTED):
        raise RuntimeError('拒絕啟動：不是指定的 Claude checkout。')
    branch = command('git', '-C', str(REPO), 'branch', '--show-current')
    if branch not in {BRANCH, REPAIR_BRANCH}:
        raise RuntimeError('拒絕啟動：Git branch 與 Claude frontend branch 不符。')
    command('git', '-C', str(REPO), 'merge-base', '--is-ancestor', TASK1, 'HEAD')
    if branch == REPAIR_BRANCH:
        command('git', '-C', str(REPO), 'merge-base', '--is-ancestor', TASK_B, 'HEAD')
    for flags in [[], ['--cached']]:
        command('git', '-C', str(REPO), 'diff', *flags, '--quiet')
    commit = command('git', '-C', str(REPO), 'log', '-1', '--format=%H',
                     '--', 'frontend/workbench')
    free = shutil.disk_usage(REPO).free
    if free < 256 * 1024 * 1024:
        raise RuntimeError('可用空間不足 256 MiB；未建立環境或複製資產。')
    import pydantic  # noqa: F401
    import PIL  # noqa: F401
    paths = [REPO / 'scripts/office_demo_backend.py',
        REPO / 'configs/office_demo_fixture_v1.json',
        BUNDLE / 'manifest.json', BUNDLE / 'safe_inputs.json',
        REPO / 'configs/office_demo_display_v1.json',
        REPO / 'data/engineering/office_display_v1.json.gz',
        REPO / 'scripts/materialize_office_display.py',
        *(VENDOR / name for name in VENDOR_FILES.values())]
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f'缺少既有依賴或路徑為 symlink：{path}；未下載或複製。')
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    for key in ['source_path', 'dataset_path', 'asset_root']:
        if not Path(manifest[key]).exists():
            raise RuntimeError(f'Office 原始依賴缺失：{key}={manifest[key]}')
    safe = json.loads((BUNDLE / 'safe_inputs.json').read_text())
    fixture = json.loads((REPO / 'configs/office_demo_fixture_v1.json').read_text())
    if digest(BUNDLE / 'safe_inputs.json') != fixture['safe_inputs_sha256']:
        raise RuntimeError('Office safe-input hash 與 fixture 不符。')
    frames = safe['frames']
    if len(frames) != 100 or set(f['camera_id'] for f in frames) != set(fixture['camera_ids']):
        raise RuntimeError('Office frame/camera fixture 不符。')
    for frame in frames:
        path = Path(frame['local_path'])
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(Path(manifest['asset_root']))
                or path.stat().st_size != frame['byte_count']):
            raise RuntimeError(f'Office source frame 缺失或不符：{path}')
    tracked = command('git', '-C', str(REPO), 'ls-files', 'frontend/workbench',
        'frontend/product/timeline.mjs', 'src/amidst/workbench',
        'scripts/office_demo_backend.py', 'configs/office_demo_fixture_v1.json').splitlines()
    fingerprint = hashlib.sha256()
    for path in sorted({REPO / p for p in tracked} | set(paths) | {Path(__file__)}):
        fingerprint.update(str(path).encode()); fingerprint.update(digest(path).encode())
    return {'repo': str(REPO), 'commit': commit, 'fingerprint': fingerprint.hexdigest(),
        'app_sha256': digest(REPO / 'frontend/workbench/app.mjs'),
        'style_sha256': digest(REPO / 'frontend/workbench/style.css'),
        'bundle': str(BUNDLE), 'evidence_repo': str(EVIDENCE),
        'free_mib': free // (1024 * 1024)}


def process_identity(pid):
    try:
        return command('/bin/ps', '-ww', '-p', str(pid), '-o', 'lstart=,args=')
    except subprocess.CalledProcessError:
        return ''


def owned(record):
    identity = process_identity(record['pid'])
    return bool(identity and identity == record['process_identity']
                and str(Path(__file__)) in identity and '--_serve' in identity)


def listener(pid):
    out = command('/usr/sbin/lsof', '-nP', '-a', '-p', str(pid),
                  '-iTCP', '-sTCP:LISTEN', '-Fn')
    ports = [line.split(':')[-1] for line in out.splitlines()
             if line.startswith('n127.0.0.1:')]
    if len(ports) != 1 or not ports[0].isdigit():
        raise RuntimeError('無法核對唯一 localhost listener。')
    return f'http://127.0.0.1:{ports[0]}/'


def readiness(record, config):
    if not owned(record) or listener(record['pid']) != record['url']:
        raise RuntimeError('PID／啟動身分／listener 不符；拒絕重用。')
    for key in ['repo', 'commit', 'fingerprint', 'app_sha256', 'style_sha256']:
        if record[key] != config[key]:
            raise RuntimeError('現有 launcher 來源已改變；先以 --stop 停止所屬程序再啟動。')
    url = record['url']
    remote = json_fetch(url + '__office_launcher')
    if remote != record:
        raise RuntimeError('服務端 launcher metadata 不符。')
    for name, key in [('app.mjs', 'app_sha256'), ('style.css', 'style_sha256')]:
        if hashlib.sha256(fetch(url + name)).hexdigest() != config[key]:
            raise RuntimeError('實際 HTTP frontend 與指定 checkout 不符。')
    served_app = fetch(url + 'app.mjs')
    if any(marker not in served_app for marker in [b'cameraTilesHTML', b'sourcePlaybackStep']):
        raise RuntimeError('HTTP frontend 缺少新版 Office camera viewer／playback。')
    fetch(url)
    for route, name in VENDOR_FILES.items():
        if hashlib.sha256(fetch(url + route.lstrip('/'))).hexdigest() != digest(VENDOR / name):
            raise RuntimeError('Three.js HTTP 依賴不符。')
    bootstrap = json_fetch(url + 'api/bootstrap')
    if {s['scene_id'] for s in bootstrap['scenes']} != {'blender-office'}:
        raise RuntimeError('Office catalog 不符。')
    session = json_fetch(url + 'api/session', {'role': 'research'})
    scope = {'session_ref': session['session_ref'], 'scene_id': 'blender-office'}
    fixture = json.loads((REPO / 'configs/office_demo_fixture_v1.json').read_text())
    for timestamp in [0.0, 0.2, 0.4]:
        timeline = json_fetch(url + 'api/timeline', scope | {
            'camera_ids': fixture['camera_ids'], 'timestamp': timestamp})
        frames = timeline['frames']
        if len(frames) != 2 or any(f['timestamp'] != timestamp for f in frames):
            raise RuntimeError('Office timeline 未回應雙鏡頭 0.2 秒採樣影格。')
        for frame in frames:
            data = fetch(url + 'api/media?' + urlencode(scope | {'ref': frame['frame_ref']}))
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise RuntimeError('Office source frame 未回傳 PNG。')
    return url


def serve():
    from office_demo_backend import application, load_scene
    from amidst.workbench.service import Application, QuietHandler
    from wsgiref.simple_server import make_server

    config = preflight()
    fixture = json.loads((REPO / 'configs/office_demo_fixture_v1.json').read_text())
    scene = load_scene(BUNDLE, fixture)
    # Reuse existing Office factories. Only the three vendor routes use shared dependencies.
    with tempfile.TemporaryDirectory(prefix='state-', dir=RUNTIME) as state:
        app = application(scene, Path(state) / 'review.sqlite3', REPO, EVIDENCE)
        vendor_app = Application(app.workbench, EVIDENCE)
        record = {}
        def dispatch(environ, start_response):
            if environ.get('PATH_INFO') == '/__office_launcher':
                host = urlsplit('//' + environ.get('HTTP_HOST', ''))
                if (environ.get('REQUEST_METHOD') != 'GET' or host.hostname != '127.0.0.1'
                        or host.port != server.server_port or host.username or host.password
                        or host.path or host.query or host.fragment):
                    start_response('403 Forbidden', [('Content-Length', '0')]); return [b'']
                body = json.dumps(record, sort_keys=True).encode()
                start_response('200 OK', [('Content-Type', 'application/json'),
                    ('Content-Length', str(len(body))), ('Cache-Control', 'no-store')])
                return [body]
            target = vendor_app if environ.get('PATH_INFO') in VENDOR_FILES else app
            return target(environ, start_response)
        with make_server('127.0.0.1', 0, dispatch, handler_class=QuietHandler) as server:
            record.update(config | {'pid': os.getpid(),
                'process_identity': process_identity(os.getpid()),
                'url': f'http://127.0.0.1:{server.server_port}/', 'nonce': secrets.token_hex(16)})
            pending = RUNTIME / 'runtime.json.tmp'
            pending.write_text(json.dumps(record, indent=2) + '\n')
            pending.replace(RUNTIME / 'runtime.json')
            def exit_owned(signum, frame):
                raise SystemExit(0)
            signal.signal(signal.SIGTERM, exit_owned)
            server.serve_forever()


def service_status():
    for name in ['postgres', 'ollama']:
        result = subprocess.run(['/usr/bin/pgrep', '-x', name], capture_output=True,
                                text=True, timeout=5)
        pids = ','.join(result.stdout.split()) or 'none'
        print(f'{name}: ' + ('已存在' if result.returncode == 0 else '未運行') +
              f'（PID {pids}；Lite 不需要、未啟動、未連線）')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['lite', 'backend', 'agent'], default='lite')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--_serve', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.mode != 'lite':
        parser.error('僅支援 Lite；既有 Office deterministic API 已內建。Backend/Agent 未接入安全生命週期。')
    os.umask(0o077)
    if RUNTIME.is_symlink():
        raise RuntimeError('拒絕使用 symlink runtime directory。')
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    if RUNTIME.stat().st_uid != os.getuid() or RUNTIME.stat().st_mode & 0o077:
        raise RuntimeError('Runtime directory 必須由目前使用者擁有且權限為 700。')
    if args._serve:
        serve(); return
    lock_path = RUNTIME / 'launcher.lock'
    if lock_path.is_symlink():
        raise RuntimeError('拒絕使用 symlink lock。')
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('另一個 launcher 正在啟動；稍後以 --status 查詢。') from None
        path = RUNTIME / 'runtime.json'
        if path.is_symlink():
            raise RuntimeError('拒絕使用 symlink runtime record。')
        record = json.loads(path.read_text()) if path.exists() else None
        if args.stop:
            if record is None or not owned(record):
                print('沒有可確認由本 launcher 啟動的存活程序；未送出任何信號。'); return
            os.kill(record['pid'], signal.SIGTERM)
            for _ in range(30):
                if not owned(record):
                    path.unlink(missing_ok=True)
                    print(f"已停止 launcher-owned Workbench PID {record['pid']}；PG/Ollama 未變更。")
                    return
                time.sleep(0.1)
            raise RuntimeError('程序尚未退出；未強制終止。')
        config = preflight()
        if record and owned(record):
            url = readiness(record, config)
            print('重用已驗證的 launcher-owned Workbench。')
        else:
            if args.status:
                raise RuntimeError('沒有可確認的 launcher-owned Workbench。')
            # Lost metadata must not cause an unverified duplicate server.
            ps = command('/bin/ps', '-ww', '-U', str(os.getuid()), '-o', 'pid=,args=')
            for line in ps.splitlines():
                if str(Path(__file__)) in line and '--_serve' in line:
                    raise RuntimeError('發現未能映射 runtime record 的 Office 程序；未建立第二個。')
            log_path = RUNTIME / 'startup.log'
            if log_path.is_symlink():
                raise RuntimeError('拒絕使用 symlink log。')
            if path.exists():
                path.unlink()
            env = os.environ | {'PYTHONPATH': str(REPO / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
            with log_path.open('w') as log:
                child = subprocess.Popen([sys.executable, str(Path(__file__)), '--_serve'],
                    cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 35
            try:
                while True:
                    if child.poll() is not None:
                        raise RuntimeError('Office 啟動失敗：' + log_path.read_text()[-4000:])
                    if path.is_file():
                        record = json.loads(path.read_text())
                        if record['pid'] != child.pid:
                            raise RuntimeError('Runtime PID 不是本次啟動的 child。')
                        url = readiness(record, config); break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Office 啟動逾時；未宣告 ready。')
                    time.sleep(0.2)
            except BaseException:
                if child.poll() is None:
                    child.terminate(); child.wait(timeout=5)
                raise
        print(f"\nOFFICE_DEMO_URL={url}\nFRONTEND_COMMIT={config['commit']}\n"
              f"FRONTEND_REPO={REPO}\nWORKBENCH_READY=YES (PID {record['pid']})\n"
              f"OFFICE_MEDIA=AVAILABLE; API_STATUS=PASS; free={config['free_mib']} MiB")
        service_status()
        print(f'停止此 launcher 的工作台："{REPO / "start-office-demo.command"}" --stop')
        print(f'Runtime／小型 startup log：{RUNTIME}\n視覺驗收仍待使用者確認。')
        if not args.no_open and not args.status:
            subprocess.run(['/usr/bin/open', url], check=False, timeout=10)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'OFFICE_DEMO_ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
