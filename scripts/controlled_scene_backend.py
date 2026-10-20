"""Explicit SYNTHETIC-only server. No Blender, GT, real-run loader or launcher changes."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from wsgiref.simple_server import make_server

from amidst.workbench.controlled_scene_api import ControlledSceneAPI
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, QuietHandler, Workbench


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--vendor-root", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="amidst-controlled-fixture-") as state:
        workbench = Workbench({}, ReviewStore(Path(state) / "review.sqlite3", {}),
                              controlled_scene=ControlledSceneAPI(fixture_mode=True))
        app = Application(workbench, repo, vendor_root=args.vendor_root)
        with make_server("127.0.0.1", args.port, app, handler_class=QuietHandler) as server:
            print(f"SYNTHETIC_FIXTURE_URL=http://127.0.0.1:{server.server_port}/workbench-v2/",
                  flush=True)
            print("FRONTEND_ASSETS_MAY_BE_UNMATERIALIZED; REAL_RUN_SUPPORT=NOT_IMPLEMENTED",
                  flush=True)
            server.serve_forever()


if __name__ == "__main__":
    main()
