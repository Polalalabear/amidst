"""Open the hydrated local demo, reusing its PostgreSQL, Ollama and workbench."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import SplitResult, urljoin, urlsplit
from urllib.request import ProxyHandler, build_opener

REPO = Path(__file__).resolve().parents[1]
CANONICAL = Path(os.environ.get("DEMO_CANONICAL_ROOT", str(REPO.parent.parent))).resolve()
STATE = Path(os.environ.get(
    "DEMO_STATE", "/private/tmp/amidst-physical-review-workbench-20261013-qa.sqlite3"
)).absolute()
ABC = REPO / "data/engineering/local_run/phase2_abc"
RUNTIME = REPO / "data/engineering/local_run/demo_launcher"
PG_BIN = Path("/opt/homebrew/opt/postgresql@18/bin")
PG_CLUSTER = ABC / "postgres/cluster"
PG_SOCKET = Path("/private/tmp/amidst-pg-abc")
OLLAMA = Path("/opt/homebrew/bin/ollama")
HTTP = build_opener(ProxyHandler({}))


def command(*args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)


def fetch(url: str) -> dict:
    with HTTP.open(url, timeout=3) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("服務未回傳 JSON 物件。")
    return value


def ollama_endpoint(provider: dict) -> SplitResult:
    endpoint = urlsplit(provider.get("endpoint", ""))
    if (endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or endpoint.path not in {"", "/"} or endpoint.port is None or endpoint.port < 1):
        raise RuntimeError("Agent provider 必須指定本機 Ollama 的 HTTP 入口與埠號。")
    return endpoint


def listening_pids(port: int) -> list[int]:
    result = command("/usr/sbin/lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN")
    return sorted({int(line) for line in result.stdout.splitlines() if line.isdecimal()})


def processes() -> dict[int, list[str]]:
    result = command("/bin/ps", "-ww", "-U", str(os.getuid()), "-o", "pid=,args=")
    if result.returncode:
        raise RuntimeError("無法核對本機程序；請在一般 Terminal 執行。")
    found = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) == 2 and fields[0].isdecimal():
            try:
                found[int(fields[0])] = shlex.split(fields[1])
            except ValueError:
                continue
    return found


def workbench_pids() -> list[int]:
    found = []
    expected = {"--repo": REPO, "--state": STATE, "--canonical-root": CANONICAL}
    for pid, args in processes().items():
        if len(args) < 3 or not Path(args[0]).name.startswith("python"):
            continue
        if args[1:3] != ["-m", "amidst.workbench"]:
            continue
        try:
            same_state = Path(args[args.index("--state") + 1]).resolve() == STATE.resolve()
        except (ValueError, IndexError):
            continue
        if not same_state:
            continue
        try:
            matches = all(Path(args[args.index(flag) + 1]).resolve() == path.resolve()
                          for flag, path in expected.items())
        except (ValueError, IndexError):
            matches = False
        if not matches:
            raise RuntimeError("同一份 state 已由其他工作台設定使用，未啟動第二個程序。")
        found.append(pid)
    if len(found) > 1:
        raise RuntimeError("同一份 state 已有多個工作台程序，請先核對，未再啟動。")
    return found


def workbench_url(pid: int) -> str:
    result = command("/usr/sbin/lsof", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN",
                     "-nP", "-Fn")
    ports = [line.removeprefix("n127.0.0.1:") for line in result.stdout.splitlines()
             if line.startswith("n127.0.0.1:")]
    if len(ports) != 1 or not ports[0].isdecimal():
        raise RuntimeError("工作台尚未建立本機 listener。")
    url = f"http://127.0.0.1:{ports[0]}/"
    bootstrap = fetch(urljoin(url, "api/bootstrap"))
    if not isinstance(bootstrap.get("scenes"), list) or not bootstrap["scenes"]:
        raise RuntimeError("工作台尚未載入場景。")
    return url


def preflight() -> dict:
    required = [REPO / ".venv/bin/python", CANONICAL / "blender/school_v3.blend",
                PG_BIN / "pg_ctl", PG_CLUSTER / "PG_VERSION", ABC / "postgres/settings.json",
                ABC / "agent_provider.json", OLLAMA]
    required.extend(STATE.with_name(STATE.stem + suffix + STATE.suffix)
                    for suffix in ("", "-local-agent", "-accuracy-v2", "-operator-study"))
    missing = [str(path) for path in required if not path.is_file()]
    if not (ABC / "ollama_models/manifests").is_dir():
        missing.append(str(ABC / "ollama_models/manifests"))
    if missing:
        raise RuntimeError("缺少原有依賴，未建立替代資料：\n" + "\n".join(missing))
    for path in (PG_CLUSTER, ABC / "postgres/settings.json", PG_SOCKET, STATE, RUNTIME):
        if path.is_symlink():
            raise RuntimeError(f"此路徑不可為符號連結：{path}")
    provider = json.loads((ABC / "agent_provider.json").read_text())
    ollama_endpoint(provider)
    if not provider.get("model") or len(provider.get("model_digest", "").removeprefix(
            "sha256:")) != 64:
        raise RuntimeError("Agent provider 缺少原模型名稱或 digest。")
    postgres_settings()
    return provider


def spawn(name: str, args: list[str], env: dict[str, str]) -> subprocess.Popen:
    with (RUNTIME / f"{name}.log").open("a") as log:
        return subprocess.Popen(args, cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def wait_ready(probe, *, child: subprocess.Popen | None = None, timeout: int = 120):
    deadline = time.monotonic() + timeout
    while True:
        if child is not None and child.poll() is not None:
            raise RuntimeError(f"服務啟動後已退出，請查看 {RUNTIME} 的 log。")
        try:
            return probe()
        except (OSError, URLError, ValueError, RuntimeError):
            if time.monotonic() >= deadline:
                raise RuntimeError(f"等候服務逾時，請查看 {RUNTIME} 的 log。") from None
            time.sleep(0.5)


def postgres_settings() -> dict:
    from psycopg.conninfo import conninfo_to_dict

    settings = json.loads((ABC / "postgres/settings.json").read_text())
    values = conninfo_to_dict(settings["dsn"])
    if (values.get("host") != str(PG_SOCKET) or str(values.get("port")) != "55432"
            or values.get("dbname") != "amidst_abc" or values.get("user") != "amidst_local"
            or settings.get("schema_name") != "amidst_local"):
        raise RuntimeError("PostgreSQL 設定與原有 cluster／資料庫不同。")
    return settings


def postgres(*, start: bool) -> int:
    settings = postgres_settings()
    status = command(str(PG_BIN / "pg_ctl"), "-D", str(PG_CLUSTER), "status")
    if status.returncode:
        if not start:
            raise RuntimeError("PostgreSQL 尚未啟動。")
        if listening_pids(55432):
            raise RuntimeError("55432 已被其他程序占用，未啟動 PostgreSQL。")
        PG_SOCKET.mkdir(mode=0o700, exist_ok=True)
        result = command(str(PG_BIN / "pg_ctl"), "-D", str(PG_CLUSTER),
                         "-l", str(RUNTIME / "postgres.log"), "-o",
                         f"-h 127.0.0.1 -p 55432 -k {PG_SOCKET} -c max_connections=32",
                         "-w", "start", timeout=60)
        if result.returncode:
            raise RuntimeError(f"PostgreSQL 啟動失敗：{RUNTIME / 'postgres.log'}")
    import psycopg
    try:
        with psycopg.connect(settings["dsn"], connect_timeout=3, autocommit=True,
                             options="-c default_transaction_read_only=on") as connection:
            row = connection.execute(
                "SELECT current_database(), current_user, current_setting('data_directory'), "
                "to_regnamespace('amidst_local') IS NOT NULL"
            ).fetchone()
        if (row is None or row[:2] != ("amidst_abc", "amidst_local")
                or Path(row[2]).resolve() != PG_CLUSTER.resolve() or not row[3]):
            raise RuntimeError("PostgreSQL 原有資料庫／schema 核對失敗。")
    except psycopg.Error:
        raise RuntimeError("PostgreSQL 原資料庫無法連線；未建立新資料庫。") from None
    return int((PG_CLUSTER / "postmaster.pid").read_text().splitlines()[0])


def ollama(provider: dict, *, start: bool) -> int:
    endpoint = ollama_endpoint(provider)
    pids = listening_pids(endpoint.port)
    child = None
    if pids:
        args = processes().get(pids[0], [])
        if (len(pids) != 1 or len(args) < 2 or Path(args[0]).name != "ollama"
                or args[1] != "serve"):
            raise RuntimeError(f"Ollama 設定埠 {endpoint.port} 已被其他程序占用，未啟動。")
    else:
        if not start:
            raise RuntimeError("Ollama 尚未啟動。")
        env = os.environ | {"OLLAMA_HOST": endpoint.netloc,
                            "OLLAMA_MODELS": str(ABC / "ollama_models"), "OLLAMA_NO_CLOUD": "1",
                            "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1"}
        child = spawn("ollama", [str(OLLAMA), "serve"], env)
    tags_url = urljoin(endpoint.geturl().rstrip("/") + "/", "api/tags")
    tags = wait_ready(lambda: fetch(tags_url), child=child,
                      timeout=30 if start else 0)
    expected_digest = provider["model_digest"].removeprefix("sha256:")
    if not any(model.get("name") == provider["model"]
               and model.get("digest", "").removeprefix("sha256:") == expected_digest
               for model in tags.get("models", [])):
        raise RuntimeError("Ollama 未列出原有指定模型／digest；未下載或執行推論。")
    return child.pid if child else pids[0]


def launch(*, start: bool, open_browser: bool, provider: dict) -> None:
    print("[1/3] 核對並啟動 PostgreSQL…", flush=True)
    pg_pid = postgres(start=start)
    print(f"      PostgreSQL 正常（PID {pg_pid}）", flush=True)
    print("[2/3] 核對並啟動 Ollama…", flush=True)
    ollama_pid = ollama(provider, start=start)
    print(f"      Ollama 正常（PID {ollama_pid}，{provider['model']}）", flush=True)
    print("[3/3] 核對並啟動工作台…", flush=True)
    existing = workbench_pids()
    child = None
    if existing:
        wb_pid = existing[0]
    elif start:
        env = os.environ | {"PYTHONPATH": str(REPO / "src"),
                            "MPLCONFIGDIR": "/private/tmp/amidst-abc-mpl"}
        child = spawn("workbench", [str(REPO / ".venv/bin/python"), "-m", "amidst.workbench",
                                   "--port", "0", "--repo", str(REPO), "--state", str(STATE),
                                   "--canonical-root", str(CANONICAL)], env)
        wb_pid = child.pid
    else:
        raise RuntimeError("工作台尚未啟動。")
    url = wait_ready(lambda: workbench_url(wb_pid), child=child, timeout=120 if start else 0)
    if start:
        record = {"repo": str(REPO), "state": str(STATE), "url": url,
                  "pids": {"postgres": pg_pid, "ollama": ollama_pid, "workbench": wb_pid}}
        pending = RUNTIME / "runtime.json.tmp"
        pending.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        pending.replace(RUNTIME / "runtime.json")
    print(f"\n工作台：{url}\n日誌：{RUNTIME}\n可關閉 Terminal，服務會繼續運行。", flush=True)
    if open_browser and command("/usr/bin/open", url).returncode:
        print("瀏覽器未自動開啟，請手動開啟上方網址。", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-open", action="store_true", help="啟動服務，不開啟瀏覽器")
    parser.add_argument("--status", action="store_true", help="只核對服務，不啟動")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        provider = preflight()
        if args.status:
            launch(start=False, open_browser=False, provider=provider)
        else:
            RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
            with (RUNTIME / "launcher.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                launch(start=True, open_browser=not args.no_open, provider=provider)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            subprocess.TimeoutExpired) as error:
        print(f"\n啟動未完成：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
