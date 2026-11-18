"""Local N6 launcher: fail before model loading on missing catalog/assets; advisor always off."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys

from amidst.paths import data_dir

REPO = Path(__file__).resolve().parents[1]


def command(args):
    if not 1024 <= args.port <= 65535 or args.port == 8785:
        raise ValueError("LIVE_PORT_INVALID: use a separate port in 1024..65535; 8785 is pinned")
    if not args.cameras.is_file():
        raise ValueError(
            f"CAMERA_CATALOG_MISSING: {args.cameras}; set --cameras to safe_static/cameras.json"
        )
    catalog = json.loads(args.cameras.read_text())
    if catalog.get("schema_version") != "controlled-scene.cameras.v1" or not catalog.get("cameras"):
        raise ValueError(
            "CAMERA_CATALOG_INVALID: expected nonempty safe_static controlled-scene.cameras.v1"
        )
    from amidst.live_mode.tracker import load_cameras

    load_cameras(str(args.cameras))
    for name in ["character.glb", "scene.glb", "cameras.three.json"]:
        if not (args.assets / name).is_file():
            raise ValueError(
                f"LIVE_ASSET_MISSING: {args.assets / name}; set --assets to the N6 directory"
            )
    for name in ["rtdetr_r18vd_dec3_6x_coco_from_paddle.pth", "source/rtdetr_pytorch/src"]:
        if not (args.models / name).exists():
            raise ValueError(f"LIVE_MODEL_MISSING: {args.models / name}; set --models")
    if not (REPO / "frontend/live-mode/node_modules/three/package.json").is_file():
        raise ValueError("LIVE_NODE_DEPENDENCY_MISSING: run npm ci in frontend/live-mode")
    missing = [
        m for m in ["torch", "torchvision", "numpy", "PIL"] if importlib.util.find_spec(m) is None
    ]
    if missing:
        raise ValueError(
            f"LIVE_RUNTIME_MISSING: {missing}; use the existing RT-DETR runtime via PYTHONPATH"
        )
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError as exc:
            raise ValueError(
                f"LIVE_PORT_IN_USE: {args.port}; choose --port, do not stop unknown processes"
            ) from exc
    return [
        sys.executable,
        "-B",
        "-m",
        "amidst.live_mode.server",
        "--port",
        str(args.port),
        "--device",
        args.device,
        "--models",
        str(args.models),
        "--assets",
        str(args.assets),
        "--cameras",
        str(args.cameras),
        "--advisor",
        "off",
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    data = data_dir()
    ap.add_argument("--port", type=int, default=int(os.environ.get("AMIDST_LIVE_PORT", "8791")))
    ap.add_argument(
        "--device", choices=["cpu", "mps"], default="mps" if sys.platform == "darwin" else "cpu"
    )
    ap.add_argument(
        "--cameras",
        type=Path,
        default=Path(
            os.environ.get(
                "AMIDST_LIVE_CAMERAS", data / "r004-build-v2-20261021/safe_static/cameras.json"
            )
        ),
    )
    ap.add_argument(
        "--assets",
        type=Path,
        default=Path(os.environ.get("AMIDST_LIVE_ASSETS", data / "live-assets-20261115")),
    )
    ap.add_argument(
        "--models",
        type=Path,
        default=Path(os.environ.get("AMIDST_LIVE_MODELS", data / "demo-owned-v1/models/rtdetr")),
    )
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    try:
        cmd = command(args)
    except (ValueError, OSError) as exc:
        ap.exit(1, str(exc) + "\n")
    print(
        json.dumps(
            {
                "status": "PREFLIGHT_PASS",
                "advisor": "off",
                "models_executed": False,
                "operator": f"http://127.0.0.1:{args.port}/?role=operator&model=glb",
                "system": f"http://127.0.0.1:{args.port}/?role=system",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if not args.check_only:
        os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
