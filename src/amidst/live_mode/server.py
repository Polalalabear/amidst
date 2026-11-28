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
import math
import mimetypes
import os
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl

import numpy as np
from PIL import Image

from .advisor import MODELS as ADVISOR_MODELS, Advisor, LiveDecider, OpenAIAdjudicator
from .candidates import COLORS, SAME_PERSON_M, TrackRequestError, TrackSelection, finite_point
from .color import judge
from .detector import DEFAULT_CAMERA_MIN_SCORES, DEFAULT_MIN_SCORE, LiveDetector
from .llm_switch import MODES as LLM_MODES, allowed_origins, cors_headers, host_ok, resolve as resolve_llm
from .people import PeopleTracker
from .relock import RelockConfig
from .tracker import Projector, Tracker, load_cameras, catalog_path
from .scheduler import CameraScheduler, load_graph, DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, DEFAULT_EXPAND_EVERY
from .track_sentence import TrackSentenceParser

REPO = Path(__file__).resolve().parents[3]
FRONT = REPO / "frontend" / "live-mode"
SHARED_TOKENS = REPO / "frontend" / "workbench-v2" / "tokens.css"
GEOMETRY = REPO / "docs" / "evaluation" / "R004_SCENE_GEOMETRY_2D_V1.json"
SCENARIO = REPO / "docs" / "evaluation" / "R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"


N6_FILES = {"/data/character.glb": "character.glb", "/data/scene.glb": "scene.glb",
            "/data/cameras.three.json": "cameras.three.json"}
TRACK_POST_FIELDS = {
    "/track/start": {"color", "sentence", "reselect", "session_id"},
    "/track/pick": {"cand_id", "session_id"},
    "/track/stop": {"session_id"},
}
TRACK_GET_FIELDS = {"/track/state": set(), "/track/candidates": {"color"}}


def allow_fields(keys, allowed):
    extra = sorted(set(keys) - allowed)
    if extra:
        raise TrackRequestError(400, "FIELD_NOT_ALLOWED", fields=extra)


def inside(path: Path, root: Path) -> bool:
    """True when path, after resolving '..' and symlinks, is still under root (blocks --path-as-is traversal)."""
    return path.resolve().is_relative_to(root.resolve())


def assets_dir(arg: str | None) -> Path | None:
    """N6 LOCAL assets (#539): --assets, else $AMIDST_LIVE_ASSETS, else $AMIDST_ARTIFACTS/data/live-assets-20261115."""
    if arg or os.environ.get("AMIDST_LIVE_ASSETS"):
        return Path(arg or os.environ["AMIDST_LIVE_ASSETS"])
    art = os.environ.get("AMIDST_ARTIFACTS")
    return Path(art) / "data" / "live-assets-20261115" if art else None


COLOR_WEAK_DEFAULT = 0.2   # #619: live red/blue label share; offline CFG["weak"] (D131) stays 0.3


class State:
    def __init__(self, args, *, track_sentence_guard=None):
        self.lock = threading.Lock()
        self.projector = Projector(load_cameras(args.cameras))   # safe_static camera catalog, calibration only
        self.registered_cameras = list(self.projector.cams)
        graph, self.graph_meta = load_graph(args.camera_graph, args.graph_sha256,
            hashlib.sha256(catalog_path(args.cameras).read_bytes()).hexdigest(), self.registered_cameras)
        self.scheduler = CameraScheduler(
            graph, expand_every=args.expand_every, mode=args.schedule,
            graph_sha256=self.graph_meta["graph_sha256"],
            cover_single_uncovered_camera=getattr(args, "relock", "off") == "fallback",
        )
        self.args = args
        self.det = LiveDetector(Path(args.models), device=args.device, threads=args.threads,
                                resize_mode=args.det_resize_mode)
        self.assets = assets_dir(args.assets)
        self.n6 = bool(self.assets and all((self.assets / f).is_file() for f in N6_FILES.values()))
        requested = args.advisor
        switch = resolve_llm(requested, args.advisor_provider)
        args.advisor = switch["effective"]
        self.guard = None
        if args.advisor != "off" and args.advisor_provider == "openai":   # paid: server-side opt-in only (AMIDST_API_* env)
            import dataclasses
            from amidst.q1q5.api_budget import ApiGuard, GuardConfig
            cfg = GuardConfig.from_env()
            if cfg.prices is None:   # D237 prices, keyed by API model id
                cfg = dataclasses.replace(cfg, prices={m[0]: {"input_usd_per_mtok": m[1], "output_usd_per_mtok": m[2]} for m in ADVISOR_MODELS.values()})
            self.guard = ApiGuard(cfg)
        # LIVE A/B §4.2 reserves a separately approved budget for Q3 sentences.
        self.sentence_parser = TrackSentenceParser(guard=track_sentence_guard)
        self.reset()
        self.llm_switch = self._scene_context_gate(switch)

    def set_llm_mode(self, requested: str, model: str | None = None) -> dict:
        """Workbench switch (llm_switch.py). Off or an unusable provider leaves the decider None: the rule-only path."""
        res = resolve_llm(requested, self.args.advisor_provider,
                          guard_cfg=self.guard.config if self.guard is not None else None)
        with self.lock:
            if isinstance(model, str) and model in ADVISOR_MODELS:
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
            self.llm_switch = res = self._scene_context_gate(res)
        return res

    def _scene_context_gate(self, res: dict) -> dict:
        """#666 M3: Agent mode needs the scene context (D340). If it could not be built, Agent mode does not start: the rule-only path
        runs and /config llm_switch (shown by the HUD switch) says SCENE_CONTEXT_UNAVAILABLE:<exception type>."""
        err = getattr(self, "scene_context_error", None)
        if self.args.advisor != "agent" or not err:
            return res
        self.args.advisor, self.decider = "off", None
        return {**res, "effective": "off", "available": False, "reason": err, "reason_code": err,
                "reason_text": f"場景上下文建不起來（{err}），Agent 模式沒有啟動，只用規則"}

    def _new_tracker(self, color="red"):
        a = self.args
        # #589 R2: "off" (default) is the unchanged rule tracker. "fallback" enables the R1 state machine with every
        # measured threshold UNKNOWN, i.e. LIVE_MODE_RELOCK_V1 4.5 (t_short = inf, R(u) = max_gate, tau_app UNKNOWN -> NEEDS_CONFIRM).
        relock = RelockConfig() if getattr(a, "relock", "off") == "fallback" else None
        return Tracker(self.projector, gate_m=a.gate_m, gate_growth_m_s=a.gate_growth,
                       max_gate_m=a.max_gate, target_color=color, relock=relock)

    def _new_decider(self):
        """None when the advisor is off, so the rule-only path is exactly what it was before."""
        a = self.args
        if a.advisor == "off":
            return None
        # F3 (#657): agent_service uses its own candidate policy. LiveDecider filters by the session target_color.
        if a.advisor == "agent":
            context = self._live_scene_context()
            return None if context is None else self._new_service_decider(context)   # None: see _scene_context_gate (#666 M3)
        if a.advisor_provider == "openai":
            provider = OpenAIAdjudicator(a.advisor_model)
            model_id = provider.api_model
        else:   # no network, no cost: answers 1 after a delay; only for exercising the flow
            def provider(ref, frame, k, timeout_s):
                time.sleep(a.advisor_fake_delay_s)
                return {"choice": 1, "reason": "假模型：固定回答 1", "prompt_tokens": 0, "completion_tokens": 0, "api_model": "fake"}
            model_id = "fake"
        return LiveDecider(a.advisor, Advisor(provider, self.guard, model_id, timeout_s=a.advisor_timeout_s), PeopleTracker(),
                           gate_m=a.gate_m, lost_min_candidates=a.advisor_lost_min_candidates, apply=a.advisor_apply,
                           target_color=getattr(getattr(self, "selection", None), "color", None) or "red")

    def _new_service_decider(self, scene_context):
        from .service_decider import ServiceLiveDecider, guarded_responses_transport
        a = self.args
        if a.advisor_provider == "openai":
            api_model = ADVISOR_MODELS[a.advisor_model][0]
            transport = guarded_responses_transport(self.guard, api_model, a.advisor_timeout_s)
        else:   # no network, no cost: always "not visible, look at the first camera"; only for exercising the flow
            api_model = "fake"

            def transport(body):
                time.sleep(a.advisor_fake_delay_s)
                return {"text": json.dumps({"answer": "NOT_VISIBLE", "next_camera_hint": None, "reason_codes": ["FAKE"], "reason": "假模型"}),
                        "usage": {}, "latency_s": a.advisor_fake_delay_s}
        return ServiceLiveDecider(transport, PeopleTracker(), scene_context, model=api_model,
                                  timeout_s=max(a.advisor_timeout_s, 8.0), gate_m=a.gate_m)

    def _live_scene_context(self):
        """r004 graphs + this server's camera catalog (calibration). The F2 wall gate validated no LIVE camera, so no wall clipping:
        every camera is listed SCENE_CONTEXT_INCOMPLETE for walls. A failure is not swallowed silently (#666 M3): it is logged, kept in
        ``scene_context_error`` (SCENE_CONTEXT_UNAVAILABLE:<exception type>) and returns None, so Agent mode does not start."""
        self.scene_context_error = None
        try:
            from amidst.q1q5 import scene_context as sx
            from amidst.q1q5.scene_graphs import R004_PINS, load_scene_graphs
            repo = Path(__file__).resolve().parents[3]
            raw = catalog_path(self.args.cameras).read_bytes()
            catalog = json.loads(raw)
            g = load_scene_graphs("r004")
            sha = {**R004_PINS, "camera_catalog.json": hashlib.sha256(raw).hexdigest()}
            static = sx.static_geometry((repo / "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json").read_bytes(),
                                        (repo / "docs/evaluation/F2_WALL_GATE_20261122.json").read_bytes(), "live")
            return sx.build(g.region, g.camera, catalog, sorted(self.registered_cameras), sha, g.tracking_scope, static=static)
        except Exception as exc:  # noqa: BLE001 -- any build failure: reported, never a silent downgrade to "no spatial information"
            self.scene_context_error = f"SCENE_CONTEXT_UNAVAILABLE:{type(exc).__name__}"
            print(f"[live] {self.scene_context_error}: {exc}; Agent mode not started", flush=True)
            return None

    def reset(self):
        if getattr(self, "scheduler", None):
            self.scheduler.reset()
        self.selection = TrackSelection()
        self._clear_target()
        return {"ok": True, "session_id": self.selection.session_id}

    def _clear_target(self):
        if getattr(self, "scheduler", None):
            self.scheduler.set_target_color(self.selection.color or "red")
        self.tracker = self._new_tracker(self.selection.color or "red")
        self.decider = self._new_decider()
        self.pending_acquire = []

    def _seed_target(self, candidate, capture_s, by):
        self.selection.locked()
        return self.tracker.seed(candidate, capture_s, by)

    def _auto_target(self):
        candidates = self.selection.snapshot(self.selection.color)["candidates"]
        if len(candidates) == 1:
            return self._seed_target(candidates[0], self.selection.latest.capture_s, "AUTO_SINGLE")
        if candidates:
            self.selection.mode = "NEEDS_PICK"
        return None

    def track_start(self, req):
        session_id = req.get("session_id")
        chip, sentence, reselect = req.get("color"), req.get("sentence"), req.get("reselect", False)
        if "color" in req and chip not in COLORS:
            raise TrackRequestError(400, "COLOR_UNSUPPORTED")
        if "sentence" in req and (not isinstance(sentence, str) or not sentence.strip() or len(sentence) > 80):
            raise TrackRequestError(400, "INVALID_SENTENCE")
        if type(reselect) is not bool:
            raise TrackRequestError(400, "INVALID_RESELECT")
        with self.lock:
            self.selection.require_session(session_id)
            epoch, effective = self.selection.epoch, self.llm_switch["effective"]

        color, receipt = self.sentence_parser.parse(chip, sentence, effective)

        with self.lock:
            self.selection.require_session(session_id)
            if self.selection.epoch != epoch:
                raise TrackRequestError(409, "TRACK_MODE_CONFLICT")
            self.selection.start(color, reselect)
            if not reselect:
                self._clear_target()
                tracked = self._auto_target()
                if tracked:
                    self.pending_acquire = tracked["events"]
            result = {"mode": self.selection.mode, **self.selection.snapshot(color)}
            if receipt is not None:
                result["parse"] = receipt
            return result

    def track_pick(self, req):
        with self.lock:
            self.selection.require_session(req.get("session_id"))
            cand_id = req.get("cand_id")
            if not isinstance(cand_id, str) or not 1 <= len(cand_id) <= 64:
                raise TrackRequestError(404, "CANDIDATE_UNKNOWN")
            picked, capture_s = self.selection.pick(cand_id)
            self._clear_target()
            tracked = self._seed_target(picked, capture_s, "USER_PICK")
            self.pending_acquire = tracked["events"]
            return {"mode": self.selection.mode, "color": self.selection.color, "picked": picked}

    def track_stop(self, req):
        with self.lock:
            self.selection.require_session(req.get("session_id"))
            self.selection.stop()
            self._clear_target()
            return {"mode": self.selection.mode}

    def track_candidates(self, color):
        if color is not None and color not in (*COLORS, "any"):
            raise TrackRequestError(400, "COLOR_UNSUPPORTED")
        with self.lock:
            return self.selection.snapshot(color or self.selection.color or "any")

    def track_state(self):
        with self.lock:
            return self.selection.state()

    def _infer_tracking(self, tick, t_s, out, frames, img_size):
        self.tracker.project_detections(out, img_size)
        self.selection.observe(tick, t_s, out)
        if self.selection.mode == "ACQUIRING":
            tracking = self._auto_target()
        elif self.selection.tracking_active:
            tracking = self.tracker.update(tick, out, img_size, t_s, projected=True)
        else:
            tracking = None

        if tracking is None:
            state = "SEARCHING" if self.selection.mode == "ACQUIRING" else self.selection.mode
            tracking = {"state": state, "active_cam": None, "seen_cams": [], "est_xy": None,
                        "events": [], "lost_ticks": 0}
        else:
            tracking["events"] = self.pending_acquire + tracking["events"]
            self.pending_acquire = []
            if self.selection.reselecting:
                tracking["state"] = "TRACKING"
            elif self.decider is not None and (self.selection.color == "red" or getattr(self.decider, "any_color", False)):
                # Each decider declares whether it supports the selected session colour.
                tracking["target"] = {"color": self.selection.color, "mode": self.selection.mode}
                tracking = self.decider.step(tick, t_s, self.tracker, tracking, out, frames)
        tracking["target"] = {"color": self.selection.color, "mode": self.selection.mode}
        return tracking

    def _effective_gate(self, t_s):
        """Read-only mirror of Tracker.update's gate, before the tick can change t_seen."""
        tracker = self.tracker
        gate = getattr(tracker, "gate", getattr(self.args, "gate_m", None))
        if gate is None:
            return None
        growth = getattr(tracker, "growth", 0.0)
        seen = getattr(tracker, "t_seen", None)
        if growth and seen is not None:
            return min(tracker.max_gate, gate + growth * max(0.0, t_s - seen))
        return gate

    def _diagnose_detections(self, out, tracking, scheduled, last_est, gate):
        """Response metadata only. Never feeds back into tracking, scheduling or selection.

        Unscheduled cameras have no fresh detections and remain omitted from /infer. If an
        observation outside the supplied schedule is inspected here, mark it explicitly.
        Candidate IDs are existing signed selection-group handles, never identity confirmations.
        """
        color = self.selection.color
        for cam, dets in out.items():
            for det in dets:
                det.pop("cand_id", None)
                point = det.get("est_xy")
                det["reject_reason"] = (
                    "CAM_NOT_SCHEDULED" if cam not in scheduled else
                    "COLOR_MISMATCH" if color in ("red", "blue") and det.get("color") != color else
                    "OUT_OF_GATE" if last_est is not None and point is not None and gate is not None
                    and math.dist(point, last_est) > gate else None
                )
        if not tracking or not (tracking.get("lost_ticks") or tracking.get("state") == "LOST"):
            return
        # Match every member of a connected selection group to its signed representative.
        # This mirrors group_candidates' same-colour <1.5m connected components; it never
        # creates IDs, changes epochs or relaxes the explicit reselect/pick endpoint guards.
        pool = [(cam, d) for cam, ds in out.items() for d in ds
                if d.get("color") in ("red", "blue") and finite_point(d.get("est_xy"), 2)]
        for candidate in self.selection.snapshot(color or "any")["candidates"]:
            members = [d for cam, d in pool if cam == candidate["cam"] and list(d["bbox"]) == candidate["bbox"]]
            while members:
                current = members.pop()
                current["cand_id"] = candidate["cand_id"]
                for _, other in pool:
                    if "cand_id" not in other and other.get("color") == current.get("color") and math.dist(other["est_xy"], current["est_xy"]) < SAME_PERSON_M:
                        members.append(other)
                        # Mark on enqueue so cycles do not duplicate work.
                        other["cand_id"] = candidate["cand_id"]

    def infer(self, header: dict, jpegs: dict, track: bool) -> dict:
        t0 = time.perf_counter()
        with self.lock:  # one inference at a time on the device
            tick = header["tick"]
            if track:
                if type(tick) is not int or not 0 <= tick < 2**53:
                    raise TrackRequestError(400, "INVALID_TICK")
                latest = self.selection.latest
                if latest is not None and tick <= latest.tick:
                    raise TrackRequestError(409, "NON_MONOTONIC_TICK", next_tick=latest.tick + 1)
            available = header.get('available_cameras', list(jpegs))
            registered = getattr(self,'registered_cameras',list(jpegs))
            if not isinstance(available,list) or any(not isinstance(c,str) for c in available):
                raise ValueError('AVAILABLE_CAMERA_IDS_REQUIRED')
            available = [c for c in dict.fromkeys(available) if c in registered]
            scheduler = getattr(self,'scheduler',None) if track else None
            t_s = float(header.get('t_capture_ms') or 0) / 1000.0
            # No capture clock in the header: the session-colour candidate memory is skipped (t_mem None), never stamped with a made-up 0 (#559 P2-1).
            t_mem = t_s if header.get('t_capture_ms') is not None else None
            plan = scheduler.plan(self.tracker.active,self.tracker.lost,available,t_s=t_mem) if scheduler else None
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
            camera_min_scores, min_score = self.args.camera_min_scores, self.args.min_score
            for cam, im, dim, lst in zip(cams, imgs, det_imgs, dets):
                arr = np.asarray(dim)
                threshold = camera_min_scores.get(cam, min_score)
                observations = []
                for d in lst:
                    bbox, score = d["bbox"], d["score"]
                    if not finite_point(bbox, 4) or not finite_point([score], 1) or (track and score < threshold):
                        continue
                    colors = judge(arr, bbox, getattr(self.args, "color_weak", None))
                    if dim is not im:
                        k = im.width / dim.width
                        bbox = [v * k for v in bbox]
                    observations.append({"bbox": bbox, "score": score, **colors})
                out[cam] = observations
            t3 = time.perf_counter()
            tracking = None
            if track:
                gate = self._effective_gate(t_s)
                last_est = list(self.tracker.est) if getattr(self.tracker, "est", None) is not None else None
                tracking = self._infer_tracking(tick, t_s, out, dict(zip(cams, imgs)), imgs[0].size)
                tracking["gate_m_effective"] = gate
                self._diagnose_detections(out, tracking, set(cams), last_est, gate)
            else:
                self._diagnose_detections(out, None, set(cams), None, None)
            t4 = time.perf_counter()
            schedule = None
            if scheduler:
                if t_mem is not None:
                    scheduler.observe(out, t_mem)
                following = scheduler.plan(self.tracker.active,self.tracker.lost,available,t_s=t_mem)
                schedule = dict(plan,camera_ids=cams,next_camera_ids=following['camera_ids'])
        timing.update({"decode": (t1 - t0) * 1e3, "detect_total": (t2 - t1) * 1e3,
                       "color": (t3 - t2) * 1e3, "track": (t4 - t3) * 1e3,
                       "server_total": (t4 - t0) * 1e3})
        return {"tick": tick, "dets": out, "tracking": tracking, "timing_ms": timing,
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

        def _track_api(self, p, body=None):
            host = self.headers.get("Host")
            origin = self.headers.get("Origin")
            try:
                if not host_ok(host, self.server.server_port) or (origin and origin != f"http://{host}"):
                    raise TrackRequestError(403, "ORIGIN_NOT_ALLOWED")
                if body is None:
                    pairs = parse_qsl(self.path.partition("?")[2], keep_blank_values=True)
                    params = dict(pairs)
                    allow_fields(params, TRACK_GET_FIELDS[p])
                    if len(params) != len(pairs):
                        raise TrackRequestError(400, "DUPLICATE_QUERY_FIELD")
                    result = state.track_state() if p == "/track/state" else state.track_candidates(params.get("color"))
                else:
                    try:
                        req = json.loads(body)
                    except (ValueError, RecursionError) as exc:
                        raise TrackRequestError(400, "INVALID_JSON_OBJECT") from exc
                    if not isinstance(req, dict):
                        raise TrackRequestError(400, "INVALID_JSON_OBJECT")
                    allow_fields(req, TRACK_POST_FIELDS[p])
                    allow_fields(dict(parse_qsl(self.path.partition("?")[2], keep_blank_values=True)), set())
                    handler = {"/track/start": state.track_start, "/track/pick": state.track_pick,
                               "/track/stop": state.track_stop}[p]
                    result = handler(req)
            except TrackRequestError as exc:
                return self._send(exc.status, json.dumps(exc.response).encode())
            return self._send(200, json.dumps(result, allow_nan=False).encode())

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
            if p in TRACK_GET_FIELDS:
                return self._track_api(p)
            if p in ("/", "/index.html"):
                return self._file(FRONT / "index.html")
            if p in ("/shared/tokens.css", "/src/tokens.css"):
                # One explicit shared asset; never expose the workbench directory.
                return self._file(SHARED_TOKENS, root=SHARED_TOKENS.parent)
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
                                                   "det_resize_mode": state.args.det_resize_mode,
                                                   "min_score": state.args.min_score,
                                                   "gate_m": getattr(state.args, "gate_m", None),
                                                   "max_gate_m": getattr(state.args, "max_gate", None),
                                                   "gate_growth_m_s": getattr(state.args, "gate_growth", 0.0),
                                                   "camera_min_scores": state.args.camera_min_scores,
                                                   "det_size": [state.args.det_width, state.args.det_height],
                                                   "schedule_mode":state.args.schedule,
                                                   "schedule_policy":{"expand_every":state.args.expand_every,
                                                                      "recent_candidate_s":getattr(state.scheduler,"recent_candidate_s",0) if hasattr(state,"scheduler") else 0,
                                                                      "recent_red_s":getattr(state.scheduler,"recent_candidate_s",0) if hasattr(state,"scheduler") else 0,
                                                                      **state.graph_meta},
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
            if p in TRACK_POST_FIELDS:
                return self._track_api(p, body)
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
                model = req.get("advisor_model") if isinstance(req, dict) else None
                if model is not None and (not isinstance(model, str) or model not in ADVISOR_MODELS):   # unhashable / non-string / unknown: reject, never ignore
                    return self._send(400, b'{"error":"bad advisor_model"}')
                return self._send(200, json.dumps(state.set_llm_mode(mode, model)).encode())
            if p == "/reset":
                with state.lock:
                    result = state.reset()
                return self._send(200, json.dumps(result).encode())
            if p in ("/infer", "/detect"):
                hl = struct.unpack("<I", body[:4])[0]
                header = json.loads(body[4:4 + hl])
                off, jpegs = 4 + hl, {}
                for f in header["frames"]:
                    jpegs[f["cam"]] = body[off:off + f["bytes"]]
                    off += f["bytes"]
                try:
                    res = state.infer(header, jpegs, track=(p == "/infer"))
                except TrackRequestError as exc:
                    return self._send(exc.status, json.dumps(exc.response).encode())
                return self._send(200, json.dumps(res).encode())
            self._send(404, b"not found", "text/plain")

    return H


def camera_min_score(value: str):
    try:
        camera, score = value.split('=', 1)
        score = float(score)
        if not camera or not 0.05 <= score <= 1:
            raise ValueError
        return camera, score
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected CAMERA=SCORE with 0.05 <= SCORE <= 1') from exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    ap.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                    help="live person threshold; calibrated with letterbox on frozen N6 RGB (#552)")
    ap.add_argument("--camera-min-score", action="append", type=camera_min_score,
                    default=list(DEFAULT_CAMERA_MIN_SCORES.items()),
                    help="repeatable CAMERA=SCORE override; CAM_ENTRY=0.05 by default; last value wins")
    ap.add_argument("--det-resize-mode", choices=["letterbox", "stretch"], default="letterbox",
                    help="preserve source aspect ratio (default); stretch reproduces the spike")
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
    ap.add_argument("--relock", choices=["off", "fallback"], default="off",
                    help="#589 R2 long-distance reacquisition. off = current rule tracker (default, unchanged). fallback = LIVE_MODE_RELOCK_V1 "
                         "state machine with the 4.5 UNKNOWN fallbacks: candidates inside the gate still re-lock, farther or ambiguous ones "
                         "enter NEEDS_CONFIRM instead of being picked silently")
    ap.add_argument("--color-weak", type=float, default=COLOR_WEAK_DEFAULT, help="minimum clothing-colour share of the box crop for a red/blue label (#619)")
    ap.add_argument("--det-width", type=int, default=320, help="frames wider than this are shrunk to det-width x det-height for detection")
    ap.add_argument("--det-height", type=int, default=180)
    ap.add_argument("--workbench-ports", type=lambda v: [int(x) for x in v.split(",")], default=[8785],
                    help="ports of the workbench page(s) allowed to read and set /config from the browser (loopback origins only; default 8785)")
    ap.add_argument("--advisor", default="off", choices=["off", "review", "lead", "agent"],
                    help="image adjudication (advisor.py); agent = agent_service decider (service_decider.py, F3 #657); off = rule tracker only")
    ap.add_argument("--advisor-model", default="terra6.1", choices=sorted(ADVISOR_MODELS))
    ap.add_argument("--advisor-provider", default="openai", choices=["openai", "fake"], help="fake = no network, no cost, always answers 1")
    ap.add_argument("--advisor-timeout-s", type=float, default=5.0)
    ap.add_argument("--advisor-fake-delay-s", type=float, default=2.5)
    ap.add_argument("--advisor-apply", default="reseed", choices=["reseed", "lock"],
                    help="reseed: move the rule tracker onto the chosen person once; lock: keep following the chosen track id "
                         "(worse than the rule alone on the A4 route in replay)")
    ap.add_argument("--advisor-lost-min-candidates", type=int, default=2, choices=[1, 2],
                    help="candidates needed to ask while the target is lost; 1 restores the first version, which often picked a lone wrong person")
    args = ap.parse_args()
    args.camera_min_scores = dict(args.camera_min_score)
    if args.port == 8785:
        raise SystemExit("8785 is the pinned demo port; refusing")
    state = State(args)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    print(f"live-mode server on http://127.0.0.1:{args.port} device={args.device} n6={state.n6}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
