#!/usr/bin/env python3
"""CS-B D47 human-review server: read-only, loopback-only, whitelist-only.

Serves the review page, each run's ``acceptance/d47_screening.json`` and the
RGB files listed in the run's ``safe_bundle/rgb_index.json`` (after checking
``file_sha256``). It never writes files and never reads GT, masks or private
paths. This is an acceptance tool, not part of the workbench.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HOST = "127.0.0.1"
PAGE_DIR = Path(__file__).resolve().parents[1] / "tools" / "cs_b_review"
PAGE_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
SCREENING_REL = Path("acceptance") / "d47_screening.json"
RGB_INDEX_REL = Path("safe_bundle") / "rgb_index.json"


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_file(root: Path, rel: str | Path) -> Path:
    """Resolve ``rel`` under ``root``; refuse '..', absolute paths and symlinks."""
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts or not rel_path.parts:
        raise Refused(403, "path refused")
    current = root
    for part in rel_path.parts:
        current = current / part
        if current.is_symlink():
            raise Refused(403, "symlink refused")
    if not current.is_file():
        raise Refused(404, "not found")
    root_real = root.resolve()
    if root_real not in current.resolve().parents:
        raise Refused(403, "path outside run directory")
    return current


class Run:
    def __init__(self, run_dir: Path):
        self.dir = run_dir
        if run_dir.is_symlink() or not run_dir.is_dir():
            raise SystemExit(f"run dir refused (missing or symlink): {run_dir}")
        self.run_id = run_dir.name
        self.index_error: str | None = None
        self.rgb: dict[str, str] = {}  # rgb_ref -> expected sha256
        self.rgb_root: dict[str, Path] = {}
        self.index_sha256: str | None = None
        self._load_index()

    def _load_index(self) -> None:
        try:
            raw = safe_file(self.dir, RGB_INDEX_REL).read_bytes()
            self.index_sha256 = sha256_bytes(raw)
            doc = json.loads(raw)
            for fr in doc["frames"]:
                self.rgb[fr["rgb_ref"]] = fr["file_sha256"]
        except (Refused, OSError, ValueError, KeyError, TypeError) as exc:
            self.index_error = f"rgb_index.json unusable: {exc}"
            self.rgb = {}

    def screening_bytes(self) -> bytes:
        return safe_file(self.dir, SCREENING_REL).read_bytes()

    def rgb_bytes(self, rgb_ref: str) -> bytes:
        expected = self.rgb.get(rgb_ref)
        if expected is None:
            raise Refused(404, "not listed in rgb_index.json")
        path = None
        for base in (Path("safe_bundle"), Path(".")):  # rgb_ref is relative to safe_bundle
            try:
                path = safe_file(self.dir, base / rgb_ref)
                break
            except Refused as exc:
                if exc.status != 404:
                    raise
        if path is None:
            raise Refused(404, "listed file missing on disk")
        data = path.read_bytes()
        if sha256_bytes(data) != expected:
            raise Refused(409, f"SHA-256 mismatch for {rgb_ref}; file refused")
        return data


def make_handler(runs: dict[str, Run]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CSBReview/1"

        def log_message(self, fmt, *args):  # quieter
            sys.stderr.write("[cs-b-review] " + fmt % args + "\n")

        def _send(self, status: int, body: bytes, ctype: str, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status: int, message: str):
            self._send(status, json.dumps({"error": message}, ensure_ascii=False).encode(),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            try:
                self._route(unquote(urlsplit(self.path).path))
            except Refused as exc:
                self._error(exc.status, exc.message)
            except Exception as exc:  # never leak a traceback
                self._error(500, f"internal error: {type(exc).__name__}")

        do_HEAD = do_GET  # noqa: N815

        def _route(self, path: str):
            if path in PAGE_FILES:
                name, ctype = PAGE_FILES[path]
                self._send(200, (PAGE_DIR / name).read_bytes(), ctype)
                return
            parts = path.strip("/").split("/")
            if path == "/api/runs":
                body = [{"run_id": r.run_id, "index_error": r.index_error,
                         "rgb_index_sha256": r.index_sha256} for r in runs.values()]
                self._send(200, json.dumps(body).encode(), "application/json; charset=utf-8")
                return
            if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "screening":
                run = runs.get(parts[2])
                if run is None:
                    raise Refused(404, "unknown run")
                data = run.screening_bytes()
                self._send(200, data, "application/json; charset=utf-8",
                           {"X-Screening-SHA256": sha256_bytes(data)})
                return
            if len(parts) >= 3 and parts[0] == "rgb":
                run = runs.get(parts[1])
                if run is None:
                    raise Refused(404, "unknown run")
                self._send(200, run.rgb_bytes("/".join(parts[2:])), "image/png")
                return
            raise Refused(404, "not found")

        def _deny(self):
            self._error(405, "read-only server")

        do_POST = do_PUT = do_DELETE = do_PATCH = _deny  # noqa: N815

    return Handler


def build_server(run_dirs: list[Path], port: int) -> ThreadingHTTPServer:
    runs: dict[str, Run] = {}
    for d in run_dirs:
        run = Run(Path(d))
        runs[run.run_id] = run
    return ThreadingHTTPServer((HOST, port), make_handler(runs))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", action="append", required=True, type=Path)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    srv = build_server(args.run_dir, args.port)
    print(f"CS-B D47 review: http://{HOST}:{srv.server_address[1]}/  (read-only)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
