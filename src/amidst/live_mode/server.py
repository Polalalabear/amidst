"""Live mode spike server (D210). Serves the static front end and runs inference.

    PYTHONPATH=src:<runtime-deps> python -m amidst.live_mode.server --port 8791 --device mps

Never bind 8785 (demo pin). The server receives only camera JPEGs, a tick number and a capture
clock; it has no access to the operator's person id or coordinates.
"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image

from .color import judge
from .detector import LiveDetector
from .tracker import Projector, Tracker

REPO = Path(__file__).resolve().parents[3]
FRONT = REPO / "frontend" / "live-mode"
GEOMETRY = REPO / "docs" / "evaluation" / "R004_SCENE_GEOMETRY_2D_V1.json"
SCENARIO = REPO / "docs" / "evaluation" / "R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"


class State:
    def __init__(self, args):
        self.lock = threading.Lock()
        self.geometry = json.loads(GEOMETRY.read_text())
        self.projector = Projector(self.geometry["cameras"])
        self.tracker = Tracker(self.projector)
        self.det = LiveDetector(Path(args.models), device=args.device, threads=args.threads)
        self.args = args
        self.glb = os.environ.get("AMIDST_LIVE_CHARACTER_GLB")

    def infer(self, header: dict, jpegs: dict, track: bool) -> dict:
        t0 = time.perf_counter()
        cams = list(jpegs)
        imgs = [Image.open(io.BytesIO(jpegs[c])).convert("RGB") for c in cams]
        t1 = time.perf_counter()
        with self.lock:  # one inference at a time on the device
            dets, timing = self.det.detect(imgs)
            t2 = time.perf_counter()
            out = {}
            for cam, im, lst in zip(cams, imgs, dets):
                arr = np.asarray(im)
                if track:  # live path shows/uses only detections above the display threshold
                    lst = [d for d in lst if d["score"] >= self.args.min_score]
                for d in lst:
                    d.update(judge(arr, d["bbox"]))
                out[cam] = lst
            t3 = time.perf_counter()
            tracking = None
            if track:
                tracking = self.tracker.update(header["tick"], out, imgs[0].size)
            t4 = time.perf_counter()
        timing.update({"decode": (t1 - t0) * 1e3, "detect_total": (t2 - t1) * 1e3,
                       "color": (t3 - t2) * 1e3, "track": (t4 - t3) * 1e3,
                       "server_total": (t4 - t0) * 1e3})
        return {"tick": header["tick"], "dets": out, "tracking": tracking, "timing_ms": timing}


def make_handler(state: State):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: Path):
            if not path.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix == ".mjs":
                ctype = "text/javascript"
            self._send(200, path.read_bytes(), ctype)

        def do_GET(self):
            p = self.path.split("?")[0]
            if p in ("/", "/index.html"):
                return self._file(FRONT / "index.html")
            if p.startswith("/src/"):
                return self._file(FRONT / p[1:])
            if p.startswith("/vendor/three/"):
                return self._file(FRONT / "node_modules" / "three" / p[len("/vendor/three/"):])
            if p == "/data/geometry.json":
                return self._file(GEOMETRY)
            if p == "/data/scenario.json":
                return self._file(SCENARIO)
            if p == "/data/character.glb" and state.glb:
                return self._file(Path(state.glb))
            if p == "/config":
                return self._send(200, json.dumps({"device": state.args.device, "threads": state.args.threads,
                                                   "glb": bool(state.glb)}).encode())
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n)
            p = self.path.split("?")[0]
            if p == "/reset":
                with state.lock:
                    state.tracker = Tracker(state.projector)
                return self._send(200, b"{}")
            if p in ("/infer", "/detect"):
                hl = struct.unpack("<I", body[:4])[0]
                header = json.loads(body[4:4 + hl])
                off, jpegs = 4 + hl, {}
                for f in header["frames"]:
                    jpegs[f["cam"]] = body[off:off + f["bytes"]]
                    off += f["bytes"]
                res = state.infer(header, jpegs, track=(p == "/infer"))
                return self._send(200, json.dumps(res).encode())
            self._send(404, b"not found", "text/plain")

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    ap.add_argument("--min-score", type=float, default=0.35)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--models", default=str(REPO / "local/data/demo-owned-v1/models/rtdetr"))
    args = ap.parse_args()
    if args.port == 8785:
        raise SystemExit("8785 is the pinned demo port; refusing")
    state = State(args)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    print(f"live-mode server on http://127.0.0.1:{args.port} device={args.device}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
