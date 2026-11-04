"""O3 non-person class-agnostic same-camera IoU linker tests (#422).

All inputs are hand-crafted SYNTHETIC observations; no real-run threshold approval is implied.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from amidst.q1q5.linker import (
    TRACKABLE_CLASSES_V1,
    TRACKABLE_OBJECT_CLASSES,
    LinkError,
    LinkParameters,
    LocalLinker,
    _hash,
    is_trackable_class,
    link_class_detections,
)

REPO = Path(__file__).resolve().parents[2]
CLASS_ALIAS_PATH = REPO / "configs/q1q5/class_alias_v1.json"
KEY = "c" * 16


def _parameter_doc(interval=200_000, gap=600_000):
    values = {
        "link_iou_min": 0.3,
        "link_center_dist_max_diag_ratio": 0.5,
        "link_max_gap_us": gap,
        "link_min_score": 0.4,
        "link_color_rule": "NOT_NONE",
        "link_ambiguity_margin": 0.05,
    }
    doc = {
        "schema_version": "q-demo.parameter-set.v1",
        "applies_to": {
            "scene_revision": "rSYN",
            "run_ids": ["SYN_RUN"],
            "detection_index_ids": ["idx:" + KEY],
            "index_interval_us": interval,
        },
        "parameters": [
            {
                "name": name,
                "value": value,
                "status": "APPROVED",
                "unit": "SYNTHETIC",
                "proposal_ref": "synthetic://o3-test",
            }
            for name, value in values.items()
        ],
        "approval": {
            "status": "APPROVED",
            "approved_by": "SYNTHETIC",
            "approval_ref": "synthetic://o3-test",
        },
    }
    doc["content_sha256"] = _hash(doc)
    doc["parameter_set_id"] = "pset:q-demo:" + doc["content_sha256"][:16]
    return doc


def _parameters(interval=200_000, gap=600_000):
    doc = _parameter_doc(interval=interval, gap=gap)
    return LinkParameters.from_document(
        doc,
        expected_sha256=doc["content_sha256"],
        scene_revision="rSYN",
        run_id="SYN_RUN",
        index_id="idx:" + KEY,
        index_interval_us=interval,
    )


def _obs(frame, ordinal=0, *, label="car", box=None, score=0.9, camera_id="CAM_SYN", color_verdict=None):
    item = {
        "observation_id": f"obs:{KEY}:{camera_id}:{frame}:{ordinal}",
        "class_label": label,
        "bbox_xyxy_px": list(box or [10, 10, 50, 50]),
        "score": score,
    }
    if color_verdict is not None:
        item["color"] = {"verdicts": {"red": color_verdict}}
    return item


def _record(frame, obs_list=None, *, state="INFERRED", camera_id="CAM_SYN", interval_us=200_000):
    return {
        "run_id": "SYN_RUN",
        "clock_id": "SYN_CLOCK",
        "camera_id": camera_id,
        "frame_index": frame,
        "timestamp_us": frame * interval_us,
        "frame_state": state,
        "detections": ([] if obs_list is None else list(obs_list)) if state == "INFERRED" else None,
    }


def test_trackable_classes_are_subset_of_coco80_and_helper_respects_flag():
    coco_doc = json.loads(CLASS_ALIAS_PATH.read_text(encoding="utf-8"))
    coco_classes = set(coco_doc["class_labels"])
    expected = {
        "person",
        "car",
        "bicycle",
        "motorcycle",
        "bus",
        "truck",
        "backpack",
        "handbag",
        "suitcase",
    }
    assert TRACKABLE_OBJECT_CLASSES == expected
    assert TRACKABLE_CLASSES_V1 == expected
    assert TRACKABLE_OBJECT_CLASSES <= coco_classes

    for cls_name in expected:
        assert is_trackable_class(cls_name) is True
        assert is_trackable_class(cls_name, allow_non_person=False) is (cls_name == "person")

    for unsupported in ("chair", "couch", "dining table", "tv", "laptop", "cup", "unicorn", "", None):
        assert is_trackable_class(unsupported) is False  # type: ignore[arg-type]


@pytest.mark.parametrize("target_class", ["car", "bicycle", "truck", "backpack"])
def test_non_person_classes_link_across_frames_with_iou_and_gap_tolerance(target_class):
    # Frame 0, 1, 2: continuous movement; Frame 3: 1-frame occlusion gap; Frame 4: re-observed within gap<=2;
    # Frame 5, 6, 7: 3-frame gap (> max_gap_frames=2); Frame 8, 9: new track segment.
    records = [
        _record(0, [_obs(0, 0, label=target_class, box=[10, 10, 50, 50])]),
        _record(1, [_obs(1, 0, label=target_class, box=[12, 10, 52, 50])]),
        _record(2, [_obs(2, 0, label=target_class, box=[14, 10, 54, 50])]),
        _record(3, []),  # 1-frame gap (within max_gap_frames=2)
        _record(4, [_obs(4, 0, label=target_class, box=[16, 10, 56, 50])]),
        _record(5, []),
        _record(6, []),
        _record(7, []),  # 3-frame gap (exceeds max_gap_frames=2)
        _record(8, [_obs(8, 0, label=target_class, box=[100, 100, 140, 140])]),
        _record(9, [_obs(9, 0, label=target_class, box=[102, 100, 142, 140])]),
    ]

    result = link_class_detections(
        records,
        target_class=target_class,
        iou_threshold=0.3,
        max_gap_frames=2,
        min_track_len=2,
    )
    assert result["status"] == "TRACKING"
    assert result["reasons"] == []
    assert result["target_class"] == target_class
    assert result["identity_verdict"] == "UNCONFIRMED"
    assert result["evidence_state"] == "OBSERVED"
    assert len(result["tracks"]) == 2
    assert len(result["sightings"]) == 2

    first_track, second_track = result["tracks"]
    assert first_track["class_label"] == target_class
    assert first_track["frame_indices"] == [0, 1, 2, 4]
    assert first_track["range_us"] == [0, 1_000_000]
    assert first_track["evidence_state"] == "OBSERVED"
    assert first_track["identity_verdict"] == "UNCONFIRMED"
    assert all(iou >= 0.3 for iou in first_track["ious"])

    assert second_track["class_label"] == target_class
    assert second_track["frame_indices"] == [8, 9]
    assert second_track["range_us"] == [1_600_000, 2_000_000]

    # Also verify LocalLinker step-by-step on the same sequence
    params = _parameters(interval=200_000, gap=600_000)  # max_gap_samples = 2
    linker = LocalLinker(
        records[0],
        records[0]["detections"][0]["observation_id"],
        parameters=params,
        stride_samples=1,
        index_grid_origin_frame=0,
        target_class=target_class,
    )
    s1 = linker.step(records[1])
    s2 = linker.step(records[2])
    s3 = linker.step(records[3])
    s4 = linker.step(records[4])
    assert [s1.state, s2.state, s3.state, s4.state] == ["PLAYING", "PLAYING", "TEMP_LOST", "PLAYING"]
    assert s4.link["decision"] == "LINKED"
    assert s4.link["gap_samples"] == 1
    assert s4.identity_verdict == "UNCONFIRMED"


def test_mixed_class_scene_never_merges_person_or_chair_into_car_track():
    # Identical 100% overlapping bounding boxes [20, 20, 60, 60] for car, person, and chair.
    # At frame 1, car is absent while person and chair remain at the exact same box!
    # At frame 2, car returns at the same box.
    f0_car = _obs(0, 0, label="car", box=[20, 20, 60, 60], score=0.95)
    f0_person = _obs(0, 1, label="person", box=[20, 20, 60, 60], score=0.99, color_verdict="STRONG")
    f0_chair = _obs(0, 2, label="chair", box=[20, 20, 60, 60], score=0.99)

    f1_person = _obs(1, 0, label="person", box=[20, 20, 60, 60], score=0.99, color_verdict="STRONG")
    f1_chair = _obs(1, 1, label="chair", box=[20, 20, 60, 60], score=0.99)

    f2_car = _obs(2, 0, label="car", box=[22, 20, 62, 60], score=0.92)
    f2_person = _obs(2, 1, label="person", box=[22, 20, 62, 60], score=0.99, color_verdict="STRONG")
    f2_chair = _obs(2, 2, label="chair", box=[22, 20, 62, 60], score=0.99)

    records = [
        _record(0, [f0_car, f0_person, f0_chair]),
        _record(1, [f1_person, f1_chair]),
        _record(2, [f2_car, f2_person, f2_chair]),
    ]

    car_res = link_class_detections(records, target_class="car", iou_threshold=0.3, max_gap_frames=2)
    assert car_res["status"] == "TRACKING"
    assert len(car_res["tracks"]) == 1
    assert car_res["tracks"][0]["observation_ids"] == [
        f0_car["observation_id"],
        f2_car["observation_id"],
    ]
    assert car_res["tracks"][0]["frame_indices"] == [0, 2]

    # LocalLinker for car must report TEMP_LOST on frame 1 (ignoring person & chair) and LINKED on frame 2
    tracker = LocalLinker(
        records[0],
        f0_car["observation_id"],
        parameters=_parameters(),
        stride_samples=1,
        index_grid_origin_frame=0,
        target_class="car",
    )
    step1 = tracker.step(records[1])
    assert step1.state == "TEMP_LOST"
    assert step1.link["decision"] == "NO_CANDIDATE"
    assert step1.link["next_observation_id"] is None

    step2 = tracker.step(records[2])
    assert step2.state == "PLAYING"
    assert step2.link["decision"] == "LINKED"
    assert step2.link["next_observation_id"] == f2_car["observation_id"]


@pytest.mark.parametrize("unsupported_class", ["chair", "dining table", "cup", "couch", "tv", "laptop"])
def test_non_trackable_coco_classes_return_unsupported_and_reject_in_strict_mode(unsupported_class):
    coco_doc = json.loads(CLASS_ALIAS_PATH.read_text(encoding="utf-8"))
    supported_vocab = set(coco_doc["class_labels"])
    records = [
        _record(0, [_obs(0, 0, label=unsupported_class, box=[10, 10, 40, 40])]),
        _record(1, [_obs(1, 0, label=unsupported_class, box=[10, 10, 40, 40])]),
    ]

    res = link_class_detections(
        records,
        target_class=unsupported_class,
        supported_classes=supported_vocab,
    )
    assert res["status"] == "UNSUPPORTED"
    assert res["reasons"] == ["CLASS_NOT_SUPPORTED_BY_LINKER"]
    assert res["tracks"] == []
    assert res["sightings"] == []
    assert res["multi_view"] == []
    assert res["single_view"] == []
    assert res["identity_verdict"] == "UNCONFIRMED"

    with pytest.raises(LinkError) as exc_info:
        link_class_detections(
            records,
            target_class=unsupported_class,
            supported_classes=supported_vocab,
            strict=True,
        )
    assert exc_info.value.code == "CLASS_NOT_SUPPORTED_BY_LINKER"

    with pytest.raises(LinkError) as seed_exc:
        LocalLinker(
            records[0],
            records[0]["detections"][0]["observation_id"],
            parameters=_parameters(),
            stride_samples=1,
            index_grid_origin_frame=0,
            target_class=unsupported_class,
        )
    assert seed_exc.value.code == "CLASS_NOT_SUPPORTED_BY_LINKER"


@pytest.mark.parametrize("non_person_class", ["car", "bicycle", "truck", "backpack", "chair"])
def test_non_person_with_color_label_is_rejected_with_unsupported_condition(non_person_class):
    records = [_record(0, [_obs(0, 0, label=non_person_class, color_verdict="STRONG")])]

    with pytest.raises(LinkError) as exc_info:
        link_class_detections(records, target_class=non_person_class, color_label="red")
    assert exc_info.value.code == "UNSUPPORTED_CONDITION"

    with pytest.raises(LinkError) as seed_exc:
        LocalLinker(
            records[0],
            records[0]["detections"][0]["observation_id"],
            parameters=_parameters(),
            stride_samples=1,
            index_grid_origin_frame=0,
            target_class=non_person_class,
            color_label="red",
        )
    assert seed_exc.value.code == "UNSUPPORTED_CONDITION"


def test_min_track_len_and_as_of_us_future_cutoff():
    records = [
        _record(0, [_obs(0, 0, label="car", box=[10, 10, 50, 50])]),  # single-frame noise at [10,10,50,50]
        _record(2, [_obs(2, 0, label="car", box=[100, 100, 150, 150])]),
        _record(3, [_obs(3, 0, label="car", box=[102, 100, 152, 150])]),
        _record(4, [_obs(4, 0, label="car", box=[104, 100, 154, 150])]),  # timestamp_us = 800_000
    ]
    # Cut off at as_of_us = 800_000 (so frame 4 is in the future and must not be used),
    # and require min_track_len = 2 (so frame 0 noise is filtered out).
    res = link_class_detections(
        records,
        target_class="car",
        min_track_len=2,
        as_of_us=800_000,
    )
    assert len(res["tracks"]) == 1
    assert res["tracks"][0]["frame_indices"] == [2, 3]
    assert res["tracks"][0]["range_us"] == [400_000, 800_000]
    assert res["status"] == "TRACKING"


def test_person_tracking_regression_zero_change_to_existing_semantics():
    params = _parameters()
    p0 = _obs(0, 0, label="person", box=[0, 0, 10, 10], color_verdict="STRONG")
    p1 = _obs(1, 0, label="person", box=[1, 1, 11, 11], color_verdict="STRONG")
    c1 = _obs(1, 1, label="car", box=[0, 0, 10, 10], score=0.99)
    r0 = _record(0, [p0])
    r1 = _record(1, [c1, p1])

    # Default target_class="person"
    tracker = LocalLinker(
        deepcopy(r0),
        p0["observation_id"],
        parameters=params,
        stride_samples=1,
        index_grid_origin_frame=0,
        color_label="red",
    )
    expected_segment_id = "local:" + hashlib.sha256(
        json.dumps(["SYN_RUN", "SYN_CLOCK", "CAM_SYN", p0["observation_id"], params.content_sha256],
                   separators=(",", ":")).encode()
    ).hexdigest()[:16]
    assert tracker.segment_id == expected_segment_id

    step = tracker.step(deepcopy(r1))
    assert step.state == "PLAYING"
    assert step.link["decision"] == "LINKED"
    assert step.link["next_observation_id"] == p1["observation_id"]
    assert step.local_segment_id == expected_segment_id

    # Batch link_class_detections default target_class="person" with color_label="red"
    batch = link_class_detections([r0, r1], color_label="red")
    assert batch["status"] == "TRACKING"
    assert batch["target_class"] == "person"
    assert len(batch["tracks"]) == 1
    assert batch["tracks"][0]["observation_ids"] == [p0["observation_id"], p1["observation_id"]]


def test_cross_run_or_cross_clock_is_strictly_rejected():
    # 1. Mixed clocks within same camera in batch must raise LinkError with CROSS_RUN_OR_CLOCK
    r_clock_a = _record(0, [_obs(0, 0, label="car")])
    r_clock_a["clock_id"] = "CLOCK_ALPHA"
    r_clock_b = _record(1, [_obs(1, 0, label="car")])
    r_clock_b["clock_id"] = "CLOCK_BETA"

    with pytest.raises(LinkError) as exc_info:
        link_class_detections([r_clock_a, r_clock_b], target_class="car")
    assert exc_info.value.code == "CROSS_RUN_OR_CLOCK"

    # 2. Mixed runs within batch must raise LinkError with CROSS_RUN_OR_CLOCK
    r_run_a = _record(0, [_obs(0, 0, label="car")])
    r_run_a["run_id"] = "RUN_A"
    r_run_b = _record(1, [_obs(1, 0, label="car")])
    r_run_b["run_id"] = "RUN_B"

    with pytest.raises(LinkError) as exc_run:
        link_class_detections([r_run_a, r_run_b], target_class="car")
    assert exc_run.value.code == "CROSS_RUN_OR_CLOCK"

    # 3. Parameters run_id mismatch
    params = _parameters()
    r_foreign_run = _record(0, [_obs(0, 0, label="car")])
    r_foreign_run["run_id"] = "FOREIGN_RUN"
    with pytest.raises(LinkError) as exc_param:
        link_class_detections([r_foreign_run], target_class="car", parameters=params)
    assert exc_param.value.code == "CROSS_RUN_OR_CLOCK"

    # 4. LocalLinker rejects cross run/clock step
    r0 = _record(0, [_obs(0, 0, label="car")])
    tracker = LocalLinker(
        deepcopy(r0),
        r0["detections"][0]["observation_id"],
        parameters=params,
        stride_samples=1,
        index_grid_origin_frame=0,
        target_class="car",
    )
    r_foreign_clock = _record(1, [_obs(1, 0, label="car")])
    r_foreign_clock["clock_id"] = "FOREIGN_CLOCK"
    with pytest.raises(LinkError) as exc_step:
        tracker.step(r_foreign_clock)
    assert exc_step.value.code == "CROSS_RUN_OR_CLOCK"


def test_unscored_and_low_score_observations_strictly_filtered_and_never_default_to_one():
    # Observations with missing score or score < min_score (default 0.40)
    obs_no_score = _obs(0, 0, label="car")
    del obs_no_score["score"]

    obs_low_score = _obs(0, 1, label="car", score=0.35)
    obs_valid_score = _obs(0, 2, label="car", score=0.88, box=[10, 10, 50, 50])

    r0 = _record(0, [obs_no_score, obs_low_score, obs_valid_score])
    r1 = _record(1, [_obs(1, 0, label="car", score=0.85, box=[12, 10, 52, 50])])

    # In standard mode: unscored & low-score are filtered out; only valid score links
    res = link_class_detections([r0, r1], target_class="car", min_score=0.4)
    assert res["status"] == "TRACKING"
    assert len(res["tracks"]) == 1
    track = res["tracks"][0]
    assert track["observation_ids"] == [obs_valid_score["observation_id"], r1["detections"][0]["observation_id"]]

    # In strict mode: missing score on an inferred detection raises LinkError
    r_strict = _record(0, [obs_no_score])
    with pytest.raises(LinkError) as exc_strict:
        link_class_detections([r_strict], target_class="car", strict=True)
    assert exc_strict.value.code == "INVALID_SCORE"

    # LocalLinker _eligible rejects unscored and low-score
    params = _parameters()
    tracker = LocalLinker(
        _record(0, [obs_valid_score]),
        obs_valid_score["observation_id"],
        parameters=params,
        stride_samples=1,
        index_grid_origin_frame=0,
        target_class="car",
    )
    assert tracker._eligible(obs_no_score) is False
    assert tracker._eligible(obs_low_score) is False
    assert tracker._eligible(obs_valid_score) is True


def test_gap_and_lost_slices_aligned_to_grid_and_no_status_loss():
    # 1. Target present in frames 0..1, absent in frames 2..4 (records horizon extends to frame 4 -> 1_000_000 us).
    # Without as_of_us, effective_as_of extends to end of records (1_000_000 us), producing LOST and status="LOST".
    records = [
        _record(0, [_obs(0, 0, label="car", box=[10, 10, 50, 50])]),
        _record(1, [_obs(1, 0, label="car", box=[12, 10, 52, 50])]),
        _record(2, []),
        _record(3, []),
        _record(4, []),  # ts_us = 800_000, end_us = 1_000_000
    ]
    res_lost = link_class_detections(records, target_class="car")
    assert res_lost["status"] == "LOST"
    assert len(res_lost["single_view"]) == 2
    seg_on, seg_lost = res_lost["single_view"]
    assert seg_on == {
        "kind": "ON_CAMERA",
        "camera_id": "CAM_SYN",
        "range_us": [0, 400_000],
        "evidence_state": "OBSERVED",
    }
    assert seg_lost == {
        "kind": "LOST",
        "camera_id": None,
        "range_us": [400_000, 1_000_000],
        "evidence_state": "UNKNOWN",
    }

    # 2. Multi-camera gap slice alignment
    # Camera 1 active in frames 0..1 [0, 400_000];
    # Gap in frame 2;
    # Camera 2 active in frames 3..4 [600_000, 1_000_000].
    cam1_r0 = _record(0, [_obs(0, 0, label="car", camera_id="CAM_1", box=[10, 10, 50, 50])], camera_id="CAM_1")
    cam1_r1 = _record(1, [_obs(1, 0, label="car", camera_id="CAM_1", box=[12, 10, 52, 50])], camera_id="CAM_1")
    cam2_r3 = _record(3, [_obs(3, 0, label="car", camera_id="CAM_2", box=[20, 20, 60, 60])], camera_id="CAM_2")
    cam2_r4 = _record(4, [_obs(4, 0, label="car", camera_id="CAM_2", box=[22, 20, 62, 60])], camera_id="CAM_2")

    res_gap = link_class_detections([cam1_r0, cam1_r1, cam2_r3, cam2_r4], target_class="car")
    assert res_gap["status"] == "TRACKING"
    assert len(res_gap["single_view"]) == 3
    s0, s1, s2 = res_gap["single_view"]
    assert s0 == {"kind": "ON_CAMERA", "camera_id": "CAM_1", "range_us": [0, 400_000], "evidence_state": "OBSERVED"}
    assert s1 == {"kind": "GAP", "camera_id": None, "range_us": [400_000, 600_000], "evidence_state": "UNKNOWN"}
    assert s2 == {"kind": "ON_CAMERA", "camera_id": "CAM_2", "range_us": [600_000, 1_000_000], "evidence_state": "OBSERVED"}

    # Grid alignment check: timestamp not matching interval_us grid raises PARAMETER_GRID_MISMATCH
    off_grid_record = _record(1, [_obs(1, 0, label="car")])
    off_grid_record["timestamp_us"] = 250_000  # not multiple of 200_000
    with pytest.raises(LinkError) as exc_grid:
        link_class_detections([off_grid_record], target_class="car", interval_us=200_000)
    assert exc_grid.value.code == "PARAMETER_GRID_MISMATCH"


def test_link_class_detections_with_link_parameters_object():
    params = _parameters(interval=200_000, gap=600_000)
    r0 = _record(0, [_obs(0, 0, label="car", box=[10, 10, 50, 50])])
    r1 = _record(1, [_obs(1, 0, label="car", box=[12, 10, 52, 50])])

    res = link_class_detections([r0, r1], target_class="car", parameters=params)
    assert res["status"] == "TRACKING"
    assert len(res["tracks"]) == 1
    assert res["tracks"][0]["class_label"] == "car"
