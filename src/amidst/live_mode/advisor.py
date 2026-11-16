"""Image adjudication for live mode (docs/design/LIVE_MODE_LLM_DECISION_V1.md, sections 0A.4 and 0D).

When the rule tracker faces more than one red person, or has lost the target while red people are in view, one
camera frame with numbered boxes and a reference crop (the target at first lock) go to a vision model, which answers
with a number or 0. The answer refers to people by track id (people.py), so it still means something when it comes
back seconds later.

What leaves the backend: two JPEGs made from camera pixels and the number of candidates. No coordinates, no actor
ids, no scripted positions; the backend has none of those. A chosen candidate is an appearance hypothesis; identity
stays unconfirmed.

A question needs at least two candidates in one camera (see LiveDecider). A lone candidate is left to the rule.

Modes (server flag --advisor):
  off     rule tracker only; nothing in this module runs
  review  the rule keeps deciding; an answer that arrives while its person is still tracked takes over
  lead    as review, and while a question is open the output is held (state ADJUDICATING) instead of following the rule

Every paid call goes through ApiGuard. Guard denials, timeouts, invalid replies and late answers fall back to the rule
and are reported as decision_source RULE_FALLBACK with a fallback_reason.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

URL = "https://api.openai.com/v1/chat/completions"
# D237 (issue #93): config id -> (API model id, USD per million input tokens, output tokens). Live default: sol6.1.
MODELS = {"sol6.1": ("gpt-6.1-sol", 2.0, 10.0), "terra6.1": ("gpt-6.1-terra", 1.0, 5.0), "astra6": ("gpt-6-astra", 10.0, 50.0)}
SYSTEM = ("A camera system tracks one person (the target). It sees camera pixels only. Identity is never confirmed: "
          "you only judge which candidate best matches the target's appearance. Answer 0 when no candidate matches. Reply in JSON.")
MAX_OUT = 400
EST_PROMPT_TOKENS = 1100   # measured about 807 for two images plus text (LIVE_MODE_ADJUDICATION_20261116.md)
GUARD_REASON = {"API_DISABLED": "MODE_NOT_AUTHORIZED", "TOTAL_BUDGET": "CALL_BUDGET_EXHAUSTED", "DAILY_COST_CAP": "CALL_BUDGET_EXHAUSTED",
                "DAILY_CALL_CAP": "CALL_BUDGET_EXHAUSTED"}


def crop_jpeg(img, bbox, pad: float = 0.15) -> bytes:
    """Reference crop: the box plus a margin, enlarged so a small person is still legible."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    box = (max(0, int(x0 - w * pad)), max(0, int(y0 - h * pad)), min(img.width, int(x1 + w * pad)), min(img.height, int(y1 + h * pad)))
    c = img.crop(box)
    s = max(1.0, min(4.0, 300 / max(1, c.height)))
    if s > 1.0:
        c = c.resize((int(c.width * s), int(c.height * s)))
    buf = io.BytesIO(); c.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def frame_jpeg(img, boxes: list) -> bytes:
    """The camera frame with yellow boxes numbered 1..k in the given order."""
    from PIL import ImageDraw, ImageFont
    im = img.copy(); d = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default(size=max(14, im.height // 24))
    except TypeError:  # older Pillow: fixed small font
        font = ImageFont.load_default()
    t = max(2, im.width // 320)
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        d.rectangle([x0, y0, x1, y1], outline=(255, 230, 0), width=t)
        s = max(16, im.height // 20); lx, ly = max(0, x0), max(s, y0)
        d.rectangle([lx, ly - s, lx + s, ly], fill=(0, 0, 0))
        d.text((lx + s * 0.28, ly - s * 0.92), str(i + 1), fill=(255, 230, 0), font=font)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


class OpenAIAdjudicator:
    """provider(ref_jpeg, frame_jpeg, k, timeout_s) -> {choice, reason, prompt_tokens, completion_tokens, api_model}."""

    def __init__(self, model: str = "sol6.1"):
        self.config_id = model
        self.api_model = MODELS[model][0]

    def __call__(self, ref: bytes, frame: bytes, k: int, timeout_s: float) -> dict:
        url = lambda b: "data:image/jpeg;base64," + base64.b64encode(b).decode()  # noqa: E731
        body = {"model": self.api_model, "max_completion_tokens": MAX_OUT,
                "response_format": {"type": "json_schema", "json_schema": {"name": "adjudication", "strict": True, "schema": {
                    "type": "object", "additionalProperties": False, "required": ["choice", "reason"],
                    "properties": {"choice": {"type": "integer", "enum": list(range(0, k + 1))},
                                   "reason": {"type": "string", "description": "Traditional Chinese, at most 40 characters"}}}}},
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": [
                    {"type": "text", "text": "Image 1: the target when the system first locked on. Image 2: a camera frame now, candidates are "
                     f"numbered in yellow boxes. Which numbered person (1-{k}) is the target? 0 if none."},
                    {"type": "image_url", "image_url": {"url": url(ref), "detail": "high"}},
                    {"type": "image_url", "image_url": {"url": url(frame), "detail": "high"}}]}]}
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
        usage = data.get("usage") or {}
        ans = json.loads(data["choices"][0]["message"]["content"])
        return {"choice": ans.get("choice"), "reason": ans.get("reason"), "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"), "api_model": data.get("model")}


class Advisor:
    """One question at a time. ``ask`` returns at once; ``poll`` hands back each finished question exactly once."""

    def __init__(self, provider: Callable, guard=None, model_id: str = "gpt-6.1-sol", timeout_s: float = 5.0, min_interval_s: float = 1.0,
                 clock: Callable[[], float] = time.monotonic, run_async: bool = True):
        self.provider, self.guard, self.model_id = provider, guard, model_id
        self.timeout_s, self.min_interval_s, self.clock, self.run_async = timeout_s, min_interval_s, clock, run_async
        self.reference: bytes | None = None
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._done: dict | None = None
        self._seq = 0
        self._last_end = -1e9
        self.calls = 0

    def set_reference(self, jpeg: bytes) -> None:
        self.reference = jpeg

    def busy(self) -> bool:
        return self._pending is not None

    def pending_ms(self) -> float | None:
        return None if self._pending is None else (self.clock() - self._pending["t0"]) * 1000

    def ask(self, kind: str, cam: str, pids: list[int], frame: bytes) -> bool:
        if self.reference is None or self._pending is not None or self.clock() - self._last_end < self.min_interval_s:
            return False
        self._seq += 1
        self._pending = {"seq": self._seq, "t0": self.clock(), "kind": kind, "cam": cam, "pids": list(pids)}
        self.calls += 1
        args = (self._seq, self.reference, frame, len(pids))
        if self.run_async:
            threading.Thread(target=self._work, args=args, daemon=True).start()
        else:
            self._work(*args)
        return True

    def _work(self, seq: int, ref: bytes, frame: bytes, k: int) -> None:
        out: dict = {"seq": seq}
        try:
            box: dict = {}

            def fn():
                box["r"] = self.provider(ref, frame, k, self.timeout_s)
                return box["r"], box["r"].get("prompt_tokens"), box["r"].get("completion_tokens")
            if self.guard is not None:
                g = self.guard.run("live_adjudication", self.model_id, EST_PROMPT_TOKENS, MAX_OUT, fn)
                if not g.allowed:
                    out.update(source="RULE_FALLBACK", fallback_reason=GUARD_REASON.get(g.reason, "PROVIDER_UNAVAILABLE"), guard_reason=g.reason)
            else:
                fn()
            if "source" not in out:
                r = box["r"]; c = r.get("choice")
                if isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= k:
                    out.update(source="AGENT", fallback_reason=None, choice=c, reason=(r.get("reason") or "")[:40], model=r.get("api_model") or self.model_id)
                else:
                    out.update(source="RULE_FALLBACK", fallback_reason="INVALID_RESPONSE")
        except (TimeoutError, urllib.error.URLError) as exc:
            timed = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
            out.update(source="RULE_FALLBACK", fallback_reason="PROVIDER_TIMEOUT" if timed else "PROVIDER_UNAVAILABLE")
        except Exception:  # noqa: BLE001 - a broken provider must never break tracking
            out.update(source="RULE_FALLBACK", fallback_reason="PROVIDER_UNAVAILABLE")
        with self._lock:
            self._done = out

    def poll(self) -> dict | None:
        p = self._pending
        if p is None:
            return None
        with self._lock:
            done = self._done if self._done and self._done["seq"] == p["seq"] else None
            if done:
                self._done = None
        elapsed = self.clock() - p["t0"]
        if done is None:
            if elapsed <= self.timeout_s:
                return None
            done = {"source": "RULE_FALLBACK", "fallback_reason": "TIME_BUDGET"}  # the late reply, if any, is dropped by its seq
        self._pending = None
        self._last_end = self.clock()
        return {"kind": p["kind"], "cam": p["cam"], "pids": p["pids"], "latency_ms": round(elapsed * 1000), "choice": done.get("choice"),
                "reason": done.get("reason"), "model": done.get("model"), "source": done["source"], "fallback_reason": done.get("fallback_reason")}


class LiveDecider:
    """Glue between the rule tracker, the people tracker and the advisor. One ``step`` per inference tick."""

    def __init__(self, mode: str, advisor: Advisor, people, gate_m: float = 3.0, lock_keep_s: float = 1.5, lost_ticks_before_ask: int = 2,
                 max_candidates: int = 4, recheck_s: float = 4.0, fallback_show_s: float = 3.0, lost_min_candidates: int = 2):
        assert mode in ("review", "lead")
        self.mode, self.advisor, self.people = mode, advisor, people
        self.gate, self.keep, self.lost_n, self.max_c, self.recheck, self.show = gate_m, lock_keep_s, lost_ticks_before_ask, max_candidates, recheck_s, fallback_show_s
        # With a single candidate the model tends to say "yes": in the first live runs all 10 wrong answers were
        # one-candidate questions where the target was absent, while 16 of 16 two-candidate questions were right
        # (docs/evaluation/LIVE_MODE_ADVISOR_20261116.md). So a question needs at least two candidates by default.
        self.lost_min = lost_min_candidates
        self.locked: int | None = None
        self.lock_xy = None
        self.lock_seen = -1e9
        self.prev_est = None
        self.last: dict | None = None
        self.last_t = -1e9
        self.hold: dict | None = None

    @staticmethod
    def _tallest(person: dict):
        return max(person["dets"], key=lambda cd: cd[1]["bbox"][3] - cd[1]["bbox"][1])

    def step(self, tick: int, t_s: float, tracker, tracking: dict, dets: dict, frames: dict) -> dict:
        out = dict(tracking); events = list(tracking.get("events") or [])
        cands = [(cam, d, d["est_xy"]) for cam, lst in dets.items() for d in lst if d.get("color") == "red" and d.get("est_xy")]
        people = self.people.update(t_s, cands)
        by_pid = {p["pid"]: p for p in people}
        # reference crop at first lock
        if any(e["type"] == "ACQUIRE" for e in events) and out.get("est_xy") and people:
            p = min(people, key=lambda q: math.dist(q["xy"], out["est_xy"]))
            cam, det = next(((c, d) for c, d in p["dets"] if c == out.get("active_cam")), self._tallest(p))
            if cam in frames:
                self.advisor.set_reference(crop_jpeg(frames[cam], det["bbox"]))
            self.locked = None
        # a finished question
        res = self.advisor.poll()
        if res is not None:
            applied = False
            if res["source"] == "AGENT":
                if res["choice"] == 0:
                    self.locked, applied = None, True   # none of them: stop following whoever the rule or an earlier answer picked
                else:
                    pid = res["pids"][res["choice"] - 1]
                    seen = self.people.last_seen(pid)
                    if seen is not None and t_s - seen <= self.keep:
                        self.locked, self.lock_seen, self.lock_xy, applied = pid, seen, list(self.people.tracks[pid]["xy"]), True
                    else:   # the chosen person is no longer tracked: the answer came too late to use
                        res["source"], res["fallback_reason"] = "RULE_FALLBACK", "TIME_BUDGET"
            self.last = {"kind": res["kind"], "cam": res["cam"], "choice": res["choice"], "reason": res["reason"], "latency_ms": res["latency_ms"],
                         "applied": applied, "model": res["model"], "source": res["source"], "fallback_reason": res["fallback_reason"]}
            self.last_t = t_s
            events.append({"tick": tick, "type": "ADJUDICATED", "cam": res["cam"], "detail": {"choice": res["choice"], "applied": applied,
                                                                                               "source": res["source"], "latency_ms": res["latency_ms"]}})
        # follow the person an answer picked
        if self.locked is not None:
            me = by_pid.get(self.locked)
            if me is not None:
                cam = self._tallest(me)[0]; prev = tracker.active
                tracker.est, tracker.state, tracker.lost, tracker.active = list(me["xy"]), "TRACKING", 0, cam
                tracker.last_seen[cam] = tick
                out.update(state="TRACKING", est_xy=list(me["xy"]), active_cam=cam, seen_cams=sorted({c for c, _ in me["dets"]}), lost_ticks=0)
                if prev is not None and cam != prev:
                    events.append({"tick": tick, "type": "SWITCH", "cam": cam, "detail": {"from": prev, "by": "AGENT"}})
                self.lock_seen, self.lock_xy = t_s, list(me["xy"])
            elif t_s - self.lock_seen > self.keep:
                self.locked = None
            else:   # not detected this tick: wait at the last position instead of jumping to whoever is near
                tracker.est = list(self.lock_xy)
                out.update(est_xy=list(self.lock_xy), lost_ticks=max(1, out.get("lost_ticks") or 0), seen_cams=[])
        # is a question needed?
        matched = out.get("state") == "TRACKING" and (out.get("lost_ticks") or 0) == 0
        can_ask = self.advisor.reference is not None and not self.advisor.busy() and self.prev_est is not None \
            and (self.locked is None or t_s - self.last_t >= self.recheck)
        if can_ask:
            near = [p for p in people if math.dist(p["xy"], self.prev_est) <= self.gate]
            kind, pool, need = None, [], 1
            if matched and len(near) >= 2:
                kind, pool, need = "SILENT_PICK", near, 2
            elif not matched and out.get("state") != "SEARCHING" and (out.get("lost_ticks") or 0) >= self.lost_n and people:
                kind, pool, need = "LOST_WITH_CANDIDATES", people, self.lost_min
            if kind:
                per_cam: dict = {}
                for p in pool:
                    for cam, det in p["dets"]:
                        per_cam.setdefault(cam, []).append((p, det))
                cam = max((c for c in per_cam if c in frames), key=lambda c: len(per_cam[c]), default=None)
                if cam is not None and len(per_cam[cam]) >= need:
                    cs = sorted(per_cam[cam], key=lambda pd: pd[1]["bbox"][0] + pd[1]["bbox"][2])[: self.max_c]   # left to right
                    if self.advisor.ask(kind, cam, [p["pid"] for p, _ in cs], frame_jpeg(frames[cam], [d["bbox"] for _, d in cs])):
                        self.hold = {"cam": tracking.get("active_cam"), "est": self.prev_est}
                        events.append({"tick": tick, "type": "ADJUDICATE_ASK", "cam": cam, "detail": {"kind": kind, "candidates": len(cs)}})
        if not self.advisor.busy():
            self.hold = None
        elif self.mode == "lead" and self.hold is not None:   # the view waits for the answer
            out.update(state="ADJUDICATING", active_cam=self.hold["cam"], est_xy=self.hold["est"])
        fb = self.last is not None and self.last["source"] == "RULE_FALLBACK" and t_s - self.last_t <= self.show
        out["decision_source"] = "AGENT" if self.locked is not None else "RULE_FALLBACK" if fb else "RULE_ONLY"
        out["fallback_reason"] = self.last["fallback_reason"] if fb and self.locked is None else None
        pm = self.advisor.pending_ms()
        out["advisor"] = {"state": "ASKING" if self.advisor.busy() else "IDLE", "pending_ms": None if pm is None else round(pm), "last": self.last}
        out["events"] = events
        if out.get("est_xy") and out.get("state") != "ADJUDICATING":
            self.prev_est = out["est_xy"]
        return out
