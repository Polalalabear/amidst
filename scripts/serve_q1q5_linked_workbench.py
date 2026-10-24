"""Serve only the owned SYNTHETIC chain on a dynamic loopback port; Ctrl-C stops this server."""

import argparse
import os
import secrets
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from amidst.q1q5.baseline_runner import save
from amidst.q1q5.linked_workbench import application
from amidst.workbench.service import QuietHandler


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["rgb", "registry", "runtime"]:
        p.add_argument("--" + name, type=Path, required=True)
        p.add_argument("--" + name + "-sha256", required=True)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--recordings", type=Path)
    p.add_argument("--recordings-sha256")
    a = p.parse_args(argv)
    os.environ["AMIDST_Q1Q5_REGISTRY"] = str(a.registry)
    os.environ["AMIDST_Q1Q5_REGISTRY_SHA256"] = a.registry_sha256
    os.environ["AMIDST_Q1Q5_OLLAMA_RUNTIME"] = str(a.runtime)
    os.environ["AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256"] = a.runtime_sha256
    app = application(
        Path(__file__).resolve().parents[1],
        a.rgb,
        a.rgb_sha256,
        a.private_root,
        recordings=a.recordings,
        recordings_pin=a.recordings_sha256,
    )
    with make_server(
        "127.0.0.1", 0, app, server_class=Server, handler_class=QuietHandler
    ) as server:
        url = f"http://127.0.0.1:{server.server_port}/workbench-v2/?mode=review"
        save(
            a.receipt,
            dict(
                pid=os.getpid(),
                url=url,
                owner_nonce=secrets.token_hex(16),
                source_kind="SYNTHETIC",
                registry_file_sha256=a.registry_sha256,
                rgb_file_sha256=a.rgb_sha256,
                gt_read=False,
            ),
        )
        print(url, flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
