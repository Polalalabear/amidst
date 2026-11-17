"""Live mode spike server (D210). Serves the static front end and runs inference.

    PYTHONPATH=src:<runtime-deps> python -m amidst.live_mode.server --port 8791 --device mps

Never bind 8785 (demo pin). The server receives only camera JPEGs, a tick number and a capture
clock; it has no access to the operator's person id or coordinates.
"""
from __future__ import annotations

import argparse
import hashlib
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
from .llm_switch import MODES as LLM_MODES, allowed_origins, cors_headers, host_ok, resolve as resolve_llm
from .people import PeopleTracker
from .tracker import Projector, Tracker, load_cameras, catalog_path
from .scheduler import CameraScheduler, load_graph, DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, DEFAULT_EXPAND_EVERY

REPO = Path(__file__).resolve().parents[3]
FRONT = REPO / "frontend" / "live-mode"
GEOMETRY = REPO / "docs" / "evaluation" / "R004_SCENE_GEOMETRY_2D_V1.json"
SCENARIO = REPO / "docs" / "evaluation" / "R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"


N6_FILES = {"/data/character.glb": "character.glb", "/data/scene.glb": "scene.glb",
            "/data/cameras.three.json": "cameras.three.json"}


def inside(path: Path, root: Path) -> bool:
    """True when path, after resolving '..' and symlinks, is still under root (blocks --path-as-is traversal)."""
    return path.resolve().is_relative_to(root.resolve())


def assets_dir(arg: str | None) -> Path | None:
    """N6 LOCAL assets (#539): --assets, else $AMIDST_LIVE_ASSETS, else $AMIDST_ARTIFACTS/data/live-assets-20261115."""
    if arg or os.environ.get("AMIDST_LIVE_ASSETS"):
        return Path(arg or os.environ["AMIDST_LIVE_ASSETS"])
    art = os.environ.get("AMIDST_ARTIFACTS")
    return Path(art) / "data" / "live-assets-20261115" if art else None


class State:
    def __init__(self, args):
        self.lock = threading.Lock()
        self.projector = Projector(load_cameras(args.cameras))   # safe_static camera catalog, calibration only
        self.registered_cameras = list(self.projector.cams)
        graph, self.graph_meta = load_graph(args.camera_graph, args.graph_sha256,
            hashlib.sha256(catalog_path(args.cameras).read_bytes()).hexdigest(), self.registered_cameras)
        self.scheduler = CameraScheduler(graph, expand_every=args.expand_every, mode=args.schedule,
                                        graph_sha256=self.graph_meta['graph_sha256'])
        self.args = args
        self.tracker = self._new_tracker()
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
        self.llm_switch = {"requested": args.advisor, "effective": args.advisor, "available": True, "reason": None, "reason_code": None, "reason_text": None}

    def set_llm_mode(self, requested: str, model: str | None = None) -> dict:
        """Workbench switch (llm_switch.py). Off or an unusable provider leaves the decider None: the rule-only path."""
        res = resolve_llm(requested, self.args.advisor_provider)
        with self.lock:
            if model in ADVISOR_MODELS:
                self.args.advisor_model = model
            self.args.advisor = res["effective"]
            if res["effective"] != "off" and self.args.advisor_provider == "openai" and self.guard is None:
                import dataclasses
                from amidst.q1q5.api_budget import ApiGuard, GuardConfig
                cfg = GuardConfig.from_env()
                if cfg.prices is None:
                    cfg = dataclasses.replace(cfg, prices={m[0]: {"input_usd_per_mtok": m[1], "output_usd_per_mtok": m[2]} for m in ADVISOR_MODELS.values()})
                self.guard = ApiGuard(cfg)
            self.decider = self._new_decider()
            self.llm_switch = res
        return res

    def _new_tracker(self):
        a = self.args
        return Tracker(self.projector, gate_m=a.gate_m, gate_growth_m_s=a.gate_growth, max_gate_m=a.max_gate)

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
                           gate_m=a.gate_m, lost_min_candidates=a.advisor_lost_min_candidates, apply=a.advisor_apply)

    def reset(self):
        self.tracker = self._new_tracker()
        self.decider = self._new_decider()

    def infer(self, header: dict, jpegs: dict, track: bool) -> dict:
        t0 = time.perf_counter()
        with self.lock:  # one inference at a time on the device
            available = header.get('available_cameras', list(jpegs))
            registered = getattr(self,'registered_cameras',list(jpegs))
            if not isinstance(available,list) or any(not isinstance(c,str) for c in available):
                raise ValueError('AVAILABLE_CAMERA_IDS_REQUIRED')
            available = [c for c in dict.fromkeys(available) if c in registered]
            scheduler = getattr(self,'scheduler',None) if track else None
            plan = scheduler.plan(self.tracker.active,self.tracker.lost,available) if scheduler else None
            wanted = set(plan['camera_ids']) if plan else set(jpegs)
            cams = [c for c in jpegs if c in wanted and (not track or c in registered)]
            if not cams and track:
                cams = [c for c in jpegs if c in registered]
                if plan: plan['reason']='REQUEST_PLAN_MISS'
            if not cams:
                raise ValueError('NO_CAMERA_FRAMES')
            imgs = [Image.open(io.BytesIO(jpegs[c])).convert("RGB") for c in cams]
            t1 = time.perf_counter()
            dw, dh = self.args.det_width, self.args.det_height
            det_imgs = [im if im.width <= dw else im.resize((dw, dh), Image.Resampling.BILINEAR) for im in imgs]
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
                t_s = float(header.get("t_capture_ms") or 0) / 1000.0
                tracking = self.tracker.update(header["tick"], out, imgs[0].size, t_s)
                if self.decider is not None:
                    tracking = self.decider.step(header["tick"], t_s, self.tracker, tracking, out,
                                                 dict(zip(cams, imgs)))
            t4 = time.perf_counter()
            schedule = None
            if scheduler:
                following = scheduler.plan(self.tracker.active,self.tracker.lost,available)
                schedule = dict(plan,camera_ids=cams,next_camera_ids=following['camera_ids'])
        timing.update({"decode": (t1 - t0) * 1e3, "detect_total": (t2 - t1) * 1e3,
                       "color": (t3 - t2) * 1e3, "track": (t4 - t3) * 1e3,
                       "server_total": (t4 - t0) * 1e3})
        return {"tick": header["tick"], "dets": out, "tracking": tracking, "timing_ms": timing,
                "schedule": schedule}


def make_handler(state: State):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in getattr(self, "_cors", {}).items():   # only /config, only for an allow-listed workbench origin
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _config_cors(self):
            self._cors = cors_headers(self.headers.get("Origin"), allowed_origins(getattr(state.args, "workbench_ports", (8785,))))

        def do_OPTIONS(self):
            if self.path.split("?")[0] != "/config":
                return self._send(404, b"not found", "text/plain")
            self._config_cors()
            self._send(204 if self._cors else 403, b"")

        def _file(self, path: Path, root: Path | None = None):
            if root is not None and not inside(path, root):
                return self._send(404, b"not found", "text/plain")
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
                return self._file(FRONT / p[1:], root=FRONT)
            if p.startswith("/vendor/three/"):
                three = FRONT / "node_modules" / "three"
                return self._file(three / p[len("/vendor/three/"):], root=three)
            if p == "/data/geometry.json":
                return self._file(GEOMETRY)
            if p == "/data/scenario.json":
                return self._file(SCENARIO)
            if p in N6_FILES and state.n6:
                return self._file(state.assets / N6_FILES[p])
            if p == "/config":
                self._config_cors()
                return self._send(200, json.dumps({"device": state.args.device, "threads": state.args.threads,
                                                   "schedule_mode":state.args.schedule,
                                                   "schedule_policy":{"expand_every":state.args.expand_every,**state.graph_meta},
                                                   "glb": state.n6, "n6": state.n6,
                                                   "advisor": state.args.advisor, "advisor_model": state.args.advisor_model if state.args.advisor != "off" else None,
                                                   "advisor_provider": state.args.advisor_provider if state.args.advisor != "off" else None,
                                                   "llm_switch": {**state.llm_switch, "provider": state.args.advisor_provider, "model": state.args.advisor_model,
                                                                  "models": sorted(ADVISOR_MODELS)}}).encode())
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n)
            p = self.path.split("?")[0]
            if p == "/config":   # workbench LLM switch: {"advisor": "off|review|lead", "advisor_model": optional}; nothing else is accepted
                if not host_ok(self.headers.get("Host"), self.server.server_port):   # DNS rebinding: the Host must be loopback plus this port
                    return self._send(403, b'{"error":"host not allowed"}')
                self._config_cors()
                origin = self.headers.get("Origin")
                if origin and not self._cors and origin != f"http://{self.headers.get('Host')}":   # a page from any other origin may not change the switch
                    return self._send(403, b'{"error":"origin not allowed"}')
                try:
                    req = json.loads(body or b"{}")
                    mode = req["advisor"]
                except (ValueError, KeyError, TypeError):
                    return self._send(400, b'{"error":"advisor required"}')
                if not isinstance(mode, str) or mode not in LLM_MODES:
                    return self._send(400, b'{"error":"bad advisor"}')
                return self._send(200, json.dumps(state.set_llm_mode(mode, req.get("advisor_model"))).encode())
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
    ap.add_argument('--schedule',choices=['adaptive','all'],default='adaptive')
    ap.add_argument('--expand-every',type=int,default=DEFAULT_EXPAND_EVERY,help='lost rounds per expansion; full search after twice this')
    ap.add_argument('--camera-graph',type=Path,default=DEFAULT_GRAPH)
    ap.add_argument('--graph-sha256',default=DEFAULT_GRAPH_SHA256)
    ap.add_argument("--cameras", default=None, help="camera catalog (controlled-scene.cameras.v1); default local/data/r004-build-v2-20261021/safe_static/cameras.json")
    ap.add_argument("--assets", default=None, help="N6 asset dir (character.glb, scene.glb, cameras.three.json)")
    ap.add_argument("--models", default=str(REPO / "local/data/demo-owned-v1/models/rtdetr"))
    ap.add_argument("--gate-m", type=float, default=4.0,
                    help="how far from the last estimate a red detection may be and still be the target. The spike used 3; 4 lost the "
                         "target much less often in replay and in fresh runs (docs/evaluation/LIVE_MODE_TRACKER_20261116.md)")
    ap.add_argument("--gate-growth", type=float, default=0.0, help="metres per second the gate widens while the target is unseen (0 = fixed)")
    ap.add_argument("--max-gate", type=float, default=8.0)
    ap.add_argument("--det-width", type=int, default=320, help="frames wider than this are shrunk to det-width x det-height for detection")
    ap.add_argument("--det-height", type=int, default=180)
    ap.add_argument("--workbench-ports", type=lambda v: [int(x) for x in v.split(",")], default=[8785],
                    help="ports of the workbench page(s) allowed to read and set /config from the browser (loopback origins only; default 8785)")
    ap.add_argument("--advisor", default="off", choices=["off", "review", "lead"], help="image adjudication (advisor.py); off = rule tracker only")
    ap.add_argument("--advisor-model", default="sol6.1", choices=sorted(ADVISOR_MODELS))
    ap.add_argument("--advisor-provider", default="openai", choices=["openai", "fake"], help="fake = no network, no cost, always answers 1")
    ap.add_argument("--advisor-timeout-s", type=float, default=5.0)
    ap.add_argument("--advisor-fake-delay-s", type=float, default=2.5)
    ap.add_argument("--advisor-apply", default="reseed", choices=["reseed", "lock"],
                    help="reseed: move the rule tracker onto the chosen person once; lock: keep following the chosen track id "
                         "(worse than the rule alone on the A4 route in replay)")
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
