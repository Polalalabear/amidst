"""Explicit SYNTHETIC parameters; no real-run threshold approval is implied."""
from copy import deepcopy
import pytest

from amidst.q1q5.linker import LinkError, LinkParameters, LocalLinker, _hash

KEY = "a" * 16


def document(interval=200000, gap=600000):
    values = {"link_iou_min": 0.3, "link_center_dist_max_diag_ratio": 0.5,
              "link_max_gap_us": gap, "link_min_score": 0.4,
              "link_color_rule": "NOT_NONE", "link_ambiguity_margin": 0.05}
    doc = {"schema_version": "q-demo.parameter-set.v1", "applies_to": {
        "scene_revision": "rSYN", "run_ids": ["SYN_RUN"],
        "detection_index_ids": ["idx:" + KEY], "index_interval_us": interval},
        "parameters": [{"name": name, "value": value, "status": "APPROVED",
                        "unit": "SYNTHETIC", "proposal_ref": "synthetic://test"}
                       for name, value in values.items()],
        "approval": {"status": "APPROVED", "approved_by": "SYNTHETIC",
                     "approval_ref": "synthetic://test"}}
    return seal(doc)


def seal(doc):
    doc["content_sha256"] = _hash(doc)
    doc["parameter_set_id"] = "pset:q-demo:" + doc["content_sha256"][:16]
    return doc


def parameters(doc=None, interval=200000):
    doc = doc or document(interval)
    return LinkParameters.from_document(doc, expected_sha256=doc["content_sha256"],
        scene_revision="rSYN", run_id="SYN_RUN", index_id="idx:" + KEY,
        index_interval_us=interval)


def observation(frame, ordinal=0, box=None, score=0.9, verdict="STRONG", label="person"):
    return {"observation_id": f"obs:{KEY}:CAM_SYN:{frame}:{ordinal}",
            "class_label": label, "bbox_xyxy_px": box or [0, 0, 10, 10],
            "score": score, "color": {"verdicts": {"red": verdict}}}


def record(frame, state="INFERRED", obs=None, timestamp=None):
    return {"run_id": "SYN_RUN", "clock_id": "SYN_CLOCK", "camera_id": "CAM_SYN",
            "frame_index": frame, "timestamp_us": frame * 200000 if timestamp is None else timestamp,
            "frame_state": state, "detections": ([] if obs is None else obs) if state == "INFERRED" else None}


def linker(params=None, **kwargs):
    return LocalLinker(record(0, obs=[observation(0)]), observation(0)["observation_id"],
                       parameters=params or parameters(), stride_samples=1,
                       index_grid_origin_frame=0, **kwargs)


def test_gap_boundary_and_no_resurrection():
    tracker = linker()
    one = tracker.step(record(1))
    two = tracker.step(record(2, "MISSING"))
    three = tracker.step(record(3, "NOT_INFERRED"))
    assert [one.state, two.state, three.state] == ["TEMP_LOST", "TEMP_LOST", "SEARCHING"]
    assert [one.link["gap_samples"], two.link["gap_samples"], three.link["gap_samples"]] == [1, 2, 3]
    assert three.decision_time_us == 600000 and three.first_missing_us == 200000
    assert three.link["decision"] == "FRAME_NOT_INFERRED"
    assert two.link["decision"] == "FRAME_MISSING"
    assert one.link["iou"] is None and one.link["next_observation_id"] is None
    with pytest.raises(LinkError, match="Segment ended"):
        tracker.step(record(4, obs=[observation(4)]))
    fresh = LocalLinker(record(4, obs=[observation(4)]), observation(4)["observation_id"],
                       parameters=parameters(), stride_samples=1, index_grid_origin_frame=0)
    assert fresh.segment_id != tracker.segment_id


def test_linked_exactly_at_gap_limit_stays_in_segment():
    tracker = linker()
    tracker.step(record(1))
    tracker.step(record(2))
    result = tracker.step(record(3, obs=[observation(3)]))
    assert result.state == "PLAYING" and result.link["gap_samples"] == 2
    assert result.link["elapsed_us"] == 600000 and result.first_missing_us is None
    assert result.local_segment_id == tracker.segment_id


def test_zero_gap_tolerance_records_both_states_same_cell():
    tracker = linker(parameters(document(gap=200000)))
    result = tracker.step(record(1))
    assert result.transitions == ("TEMP_LOST", "SEARCHING")
    assert result.decision_time_us == 200000


def test_ambiguity_keeps_every_eligible_candidate_and_never_attaches():
    tracker = linker()
    candidates = [observation(1, i, score=0.9 - i / 10) for i in range(3)]
    result = tracker.step(record(1, obs=candidates[::-1]))
    assert result.link["decision"] == "AMBIGUOUS_LINK"
    assert result.link["next_observation_id"] is None
    assert result.ambiguous_observation_ids == tuple(o["observation_id"] for o in candidates)
    assert result.state == "TEMP_LOST"


def test_tie_break_score_and_id_when_explicit_margin_is_zero():
    doc = document()
    next(p for p in doc["parameters"] if p["name"] == "link_ambiguity_margin")["value"] = 0
    tracker = linker(parameters(seal(doc)))
    result = tracker.step(record(1, obs=[observation(1, 2), observation(1, 1),
                                       observation(1, 0, score=0.8)]))
    assert result.link["next_observation_id"] == observation(1, 1)["observation_id"]


def test_geometry_score_class_and_color_filters_do_not_create_boxes():
    tracker = linker(color_label="red")
    result = tracker.step(record(1, obs=[observation(1, 0, label="car"),
        observation(1, 1, score=0.1), observation(1, 2, box=[20, 20, 30, 30]),
        observation(1, 3, verdict="NONE")]))
    assert result.link["decision"] == "NO_CANDIDATE"
    assert result.identity_verdict == "UNCONFIRMED"
    assert result.source_grid == {"stride_samples": 1, "index_grid_origin_frame": 0,
                                  "index_interval_us": 200000}


def test_unsampled_cells_do_not_count_as_gaps():
    params = parameters(document(interval=400000, gap=800000), interval=400000)
    tracker = LocalLinker(record(0, obs=[observation(0)]), observation(0)["observation_id"],
                         parameters=params, stride_samples=2, index_grid_origin_frame=0)
    assert tracker.step(record(1, "NOT_SAMPLED")) is None
    assert tracker.step(record(2)).link["gap_samples"] == 1
    assert tracker.step(record(3, "NOT_SAMPLED")) is None
    assert tracker.step(record(4)).state == "SEARCHING"


@pytest.mark.parametrize("interval,gap", [(400000, 600000), (1000000, 600000),
                                           (200000, 0), (True, 600000)])
def test_invalid_grid_not_rounded(interval, gap):
    with pytest.raises(LinkError) as error:
        parameters(document(interval, gap), interval)
    assert error.value.code == "PARAMETER_GRID_MISMATCH"


@pytest.mark.parametrize("change", ["hash", "approval", "scope", "missing", "duplicate", "derived"])
def test_parameter_pins_approval_and_missing_values_fail_closed(change):
    doc = document()
    if change == "hash":
        doc["content_sha256"] = "0" * 64
    elif change == "approval":
        doc["approval"]["status"] = "PROPOSED"
    elif change == "scope":
        doc["applies_to"]["run_ids"] = ["OTHER"]
    elif change == "missing":
        doc["parameters"] = doc["parameters"][:-1]
    elif change == "duplicate":
        doc["parameters"].append(deepcopy(doc["parameters"][0]))
    else:
        doc["parameters"].append({"name": "link_max_gap_samples", "value": 3,
            "status": "APPROVED", "proposal_ref": "synthetic://test", "unit": "cells"})
    if change != "hash":
        seal(doc)
    with pytest.raises(LinkError):
        parameters(doc)


@pytest.mark.parametrize("change", ["camera", "clock", "run", "skipped", "timestamp", "ref", "duplicate", "nan"])
def test_bad_input_does_not_change_state(change):
    tracker = linker()
    row = record(1, obs=[observation(1)])
    if change in {"camera", "clock", "run"}:
        row[change + "_id"] = "OTHER"
    elif change == "skipped":
        row = record(2)
    elif change == "timestamp":
        row["timestamp_us"] += 1
    elif change == "ref":
        row["detections"][0]["observation_id"] = observation(1)["observation_id"].replace(KEY, "b" * 16)
    elif change == "duplicate":
        row["detections"].append(deepcopy(row["detections"][0]))
    else:
        row["detections"][0]["score"] = float("nan")
    with pytest.raises(LinkError):
        tracker.step(row)
    assert tracker.step(record(1, obs=[observation(1)])).state == "PLAYING"


def test_seed_and_input_mutation_cannot_change_future_linking():
    row = record(0, obs=[observation(0)])
    tracker = LocalLinker(row, observation(0)["observation_id"], parameters=parameters(),
                         stride_samples=1, index_grid_origin_frame=0)
    row["detections"][0]["bbox_xyxy_px"] = [100, 100, 110, 110]
    assert tracker.step(record(1, obs=[observation(1)])).link["decision"] == "LINKED"


def test_unicode_parameter_hash_matches_canonical_contract_encoding():
    import hashlib
    import json
    doc = document()
    doc["approval"]["approved_by"] = "合成測試"
    seal(doc)
    preimage = {k: v for k, v in doc.items() if k not in {"parameter_set_id", "content_sha256", "stats"}}
    expected = hashlib.sha256(json.dumps(preimage, ensure_ascii=True, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert doc["content_sha256"] == expected
    assert parameters(doc).content_sha256 == expected


def test_seed_cannot_change_pinned_run():
    row = record(0, obs=[observation(0)])
    row["run_id"] = "OTHER"
    with pytest.raises(LinkError, match="run scope"):
        LocalLinker(row, observation(0)["observation_id"], parameters=parameters(),
                    stride_samples=1, index_grid_origin_frame=0)


def test_finite_out_of_image_detector_bbox_is_preserved_for_linking():
    seed=record(0,obs=[observation(0,box=[-2,-3,10,10])])
    tracker=LocalLinker(seed,observation(0)['observation_id'],parameters=parameters(),stride_samples=1,index_grid_origin_frame=0)
    row=record(1,obs=[observation(1,box=[-1,-2,11,11])]);before=deepcopy(row)
    step=tracker.step(row)
    assert step.link['decision']=='LINKED' and tracker.last['bbox_xyxy_px']==[-1,-2,11,11] and row==before
    assert 0<step.link['iou']<1


def test_allowing_negative_bbox_does_not_allow_negative_score():
    with pytest.raises(LinkError):LocalLinker(record(0,obs=[observation(0,box=[-2,-3,10,10],score=-.1)]),observation(0)['observation_id'],parameters=parameters(),stride_samples=1,index_grid_origin_frame=0)
