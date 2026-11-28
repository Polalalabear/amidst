"""#771: q_track_boxes serves source boxes only for observations a tracking response already named; GT never read."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_bootstrap_class_counts import recorded_demo  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
try:
    from serve_demo_integration import Demo
finally:
    sys.path.pop(0)

TOKEN, KEY = "tok", ("scene", "run")
FORBIDDEN = ("ground_truth", "gt_", "actor", "trajectory", "visibility", "depth", "event_script", "persons.sim", "color")


class FakeAPI:
    def __init__(self):
        rec = {"frame_ref": "f1", "timestamp_us": 100, "camera_id": "CAM_A",
               "detections": [{"observation_id": "o1", "class_label": "person", "bbox_xyxy_px": [1, 2, 3, 4], "score": .9,
                               "color": {"x": 1}},
                              {"observation_id": "o2", "class_label": "person", "bbox_xyxy_px": [5, 6, 7, 8], "score": .8}]}
        self.runs = {KEY: SimpleNamespace(bindings=SimpleNamespace(index=SimpleNamespace(records=[rec]), index_sha256="idx"))}

    def _summary(self, run, oid):   # the real reader (QAPI._summary) is reused; this stands in for its data only
        from amidst.q1q5.api import QAPI
        return QAPI._summary(None, run, oid)


def demo():
    d = Demo.__new__(Demo)
    d.api, d.sessions, d.shown_obs = FakeAPI(), {TOKEN: {"scene"}}, {}
    return d


def ask(d, ids, **extra):
    return d.call("q_track_boxes", {"session_ref": TOKEN, "scene_id": "scene", "run_id": "run", "observation_ids": ids, **extra})


def test_serves_named_observations_with_source_fields_only():
    d = demo()
    d.shown_obs[(TOKEN,) + KEY] = frozenset({"o1"})
    out = ask(d, ["o1"])
    assert out["observations"]["o1"] == {"observation_id": "o1", "camera_id": "CAM_A", "timestamp_us": 100, "frame_ref": "f1",
                                         "class_label": "person", "score": .9, "bbox_xyxy_px": [1, 2, 3, 4]}
    assert out["identity_verdict"] == "UNCONFIRMED" and out["provenance"]["gt_read"] is False
    keys = {k for o in out["observations"].values() for k in o}
    assert not any(t in k for k in keys for t in FORBIDDEN)


def test_rejects_observations_not_named_by_a_response():
    d = demo()
    d.shown_obs[(TOKEN,) + KEY] = frozenset({"o1"})
    with pytest.raises(Exception) as e:
        ask(d, ["o2"])
    assert "FORBIDDEN_DATA_SCOPE" in str(getattr(e.value, "code", e.value))
    with pytest.raises(Exception):
        ask(demo(), ["o1"])   # nothing named yet


def test_rejects_bad_payloads_and_foreign_sessions():
    d = demo()
    d.shown_obs[(TOKEN,) + KEY] = frozenset({"o1"})
    for bad in ([], ["o1", "o1"], [1], list(map(str, range(129)))):
        with pytest.raises(Exception):
            ask(d, bad)
    with pytest.raises(Exception):
        ask(d, ["o1"], extra_field=1)
    d.sessions = {}
    with pytest.raises(Exception):
        ask(d, ["o1"])


def test_remembers_sighting_observations_without_touching_the_response():
    d = demo()
    doc = {"sightings": [{"observation_ids": ["o1"]}, {"observation_ids": ["o2"]}]}
    before = repr(doc)
    d.remember_obs(TOKEN, KEY, doc)
    assert d.shown_obs[(TOKEN,) + KEY] == frozenset({"o1", "o2"})
    assert repr(doc) == before


@pytest.mark.parametrize("label", ["A4-1", "B4-1"])
def test_real_demo_boxes_match_index_and_track_hash_is_unchanged(recorded_demo, label):   # noqa: F811
    demo_ = recorded_demo
    run = next(r for r in demo_.api.runs.values() if r.title.startswith(label + " "))
    token = demo_.call("session", {"role": "demo"})["session_ref"]
    req = {"schema_version": "q-core.track-request.v1", "session_ref": token, "scene_id": run.catalog["scene_id"],
           "run_id": run.catalog["run_id"], "feature": {"class_label": "person", "color_label": None}, "region_ids": [],
           "time": None, "playback_now_us": run.bindings.clock.duration_us}
    first = demo_.call("q_core_track", dict(req))
    ids = [o for s in first["sightings"] for o in s["observation_ids"]][:20]
    assert ids
    boxes = demo_.call("q_track_boxes", {"session_ref": token, "scene_id": req["scene_id"], "run_id": req["run_id"], "observation_ids": ids})
    index = {d["observation_id"]: (r, d) for r in run.bindings.index.records for d in r["detections"] or []}
    for oid, b in boxes["observations"].items():
        r, d = index[oid]
        assert b["bbox_xyxy_px"] == d["bbox_xyxy_px"] and b["timestamp_us"] == r["timestamp_us"] and b["camera_id"] == r["camera_id"]
    again = demo_.call("q_core_track", dict(req))
    assert again["output_sha256"] == first["output_sha256"]
