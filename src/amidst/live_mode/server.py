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

from .advisor import MODELS as ADVISOR_MODELS, Advisor, LiveDecider, OpenAIAdjudicator
from .color import judge
from .detector import LiveDetector
from .people import PeopleTracker
from .tracker import Projector, Tracker

REPO = Path(__file__).resolve().parents[3]
FRONT = REPO / "frontend" / "live-mode"
GEOMETRY = REPO / "docs" / "evaluation" / "R004_SCENE_GEOMETRY_2D_V1.json"
SCENARIO = REPO / "docs" / "evaluation" / "R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"


N6_FILES = {"/data/character.glb": "character.glb", "/data/scene.glb": "scene.glb",
            "/data/cameras.three.json": "cameras.three.json"}


def assets_dir(arg: str | None) -> Path | None:
    """N6 LOCAL assets (#539): --assets, else $AMIDST_LIVE_ASSETS, else $AMIDST_ARTIFACTS/data/live-assets-20261115."""
    if arg or os.environ.get("AMIDST_LIVE_ASSETS"):
        return Path(arg or os.environ["AMIDST_LIVE_ASSETS"])
    art = os.environ.get("AMIDST_ARTIFACTS")
    return Path(art) / "data" / "live-assets-20261115" if art else None


class State:
    def __init__(self, args):
        self.lock = threading.Lock()
        self.geometry = json.loads(GEOMETRY.read_text())
        self.projector = Projector(self.geometry["cameras"])
        self.tracker = Tracker(self.projector)
        self.det = LiveDetector(Path(args.models), device=args.device, threads=args.threads)
        self.args = args
        self.assets = assets_dir(args.assets)
        self.n6 = bool(self.assets and all((self.assets / f).is_file() for f in N6_FILES.values()))
        self.guard = None
        if args.advisor != "off" and args.advisor_provider == "openai":   # paid: server-side opt-in only (AMIDST_API_* env)
            import dataclasses
            from amidst.q1q5.api_budget import ApiGuard, GuardConfig
            cfg = GuardConfig.from_env()
            if cfg.prices is None:   # D237 prices, keyed by API model id
                cfg = dataclasses.replace(cfg, prices={m[0]: {"input_usd_per_mtok": m[1], "output_usd_per_mtok": m[2]} for m in ADVISOR_MODELS.values()})
            self.guard = ApiGuard(cfg)
        self.decider = self._new_decider()

    def _new_decider(self):
        """None when the advisor is off, so the rule-only path is exactly what it was before."""
        a = self.args
        if a.advisor == "off":
            return None
        if a.advisor_provider == "openai":
            provider = OpenAIAdjudicator(a.advisor_model)
            model_id = provider.api_model
        else:   # no network, no cost: answers 1 after a delay; only for exercising the flow
            def provider(ref, frame, k, timeout_s):
                time.sleep(a.advisor_fake_delay_s)
                return {"choice": 1, "reason": "假模型：固定回答 1", "prompt_tokens": 0, "completion_tokens": 0, "api_model": "fake"}
            model_id = "fake"
        return LiveDecider(a.advisor, Advisor(provider, self.guard, model_id, timeout_s=a.advisor_timeout_s), PeopleTracker(),
                           lost_min_candidates=a.advisor_lost_min_candidates)

    def reset(self):
        self.tracker = Tracker(self.projector)
        self.decider = self._new_decider()

    def infer(self, header: dict, jpegs: dict, track: bool) -> dict:
        t0 = time.perf_counter()
        cams = list(jpegs)
        imgs = [Image.open(io.BytesIO(jpegs[c])).convert("RGB") for c in cams]
        t1 = time.perf_counter()
        # Larger frames (e.g. 960x540, kept for adjudication crops) are shrunk for detection so the detector and the
        # colour judgement see the same size as before; boxes are then scaled back to the received frame.
        dw, dh = self.args.det_width, self.args.det_height
        det_imgs = [im if im.width <= dw else im.resize((dw, dh), Image.Resampling.BILINEAR) for im in imgs]
        with self.lock:  # one inference at a time on the device
            dets, timing = self.det.detect(det_imgs)
            t2 = time.perf_counter()
            out = {}
            for cam, im, dim, lst in zip(cams, imgs, det_imgs, dets):
                arr = np.asarray(dim)
                if track:  # live path shows/uses only detections above the display threshold
                    lst = [d for d in lst if d["score"] >= self.args.min_score]
                for d in lst:
                    d.update(judge(arr, d["bbox"]))
                    if dim is not im:
                        k = im.width / dim.width
                        d["bbox"] = [v * k for v in d["bbox"]]
                out[cam] = lst
            t3 = time.perf_counter()
            tracking = None
            if track:
                tracking = self.tracker.update(header["tick"], out, imgs[0].size)
                if self.decider is not None:
                    tracking = self.decider.step(header["tick"], float(header.get("t_capture_ms") or 0) / 1000.0, self.tracker, tracking, out,
                                                 dict(zip(cams, imgs)))
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
            if p in N6_FILES and state.n6:
                return self._file(state.assets / N6_FILES[p])
            if p == "/config":
                return self._send(200, json.dumps({"device": state.args.device, "threads": state.args.threads,
                                                   "glb": state.n6, "n6": state.n6,
                                                   "advisor": state.args.advisor, "advisor_model": state.args.advisor_model if state.args.advisor != "off" else None,
                                                   "advisor_provider": state.args.advisor_provider if state.args.advisor != "off" else None}).encode())
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n)
            p = self.path.split("?")[0]
            if p == "/reset":
                with state.lock:
                    state.reset()
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
    ap.add_argument("--assets", default=None, help="N6 asset dir (character.glb, scene.glb, cameras.three.json)")
    ap.add_argument("--models", default=str(REPO / "local/data/demo-owned-v1/models/rtdetr"))
    ap.add_argument("--det-width", type=int, default=320, help="frames wider than this are shrunk to det-width x det-height for detection")
    ap.add_argument("--det-height", type=int, default=180)
    ap.add_argument("--advisor", default="off", choices=["off", "review", "lead"], help="image adjudication (advisor.py); off = rule tracker only")
    ap.add_argument("--advisor-model", default="sol6.1", choices=sorted(ADVISOR_MODELS))
    ap.add_argument("--advisor-provider", default="openai", choices=["openai", "fake"], help="fake = no network, no cost, always answers 1")
    ap.add_argument("--advisor-timeout-s", type=float, default=5.0)
    ap.add_argument("--advisor-fake-delay-s", type=float, default=2.5)
    ap.add_argument("--advisor-lost-min-candidates", type=int, default=2, choices=[1, 2],
                    help="candidates needed to ask while the target is lost; 1 restores the first version, which often picked a lone wrong person")
    args = ap.parse_args()
    if args.port == 8785:
        raise SystemExit("8785 is the pinned demo port; refusing")
    state = State(args)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    print(f"live-mode server on http://127.0.0.1:{args.port} device={args.device} n6={state.n6}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
