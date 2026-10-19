"""Independent receipt/grid/hash/selection verification; no detector rerun or GT."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "data/pilot/controlled_scene_v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seed_path = REPO / "configs/controlled_scene_cs_b_sampling_v1.json"
    seed = json.loads(seed_path.read_bytes())["seed"]
    reports = []
    for event, count, cameras in (
        ("a", 50, ["CAM_W1", "CAM_W2", "CAM_R102_CTRL"]),
        ("b1", 100, ["CAM_W1", "CAM_W2", "CAM_N1", "CAM_R102_CTRL"]),
    ):
        run_id = f"ctrl-lcorr-s1-{event}-5fps-v1-r001"
        run = ROOT / "runs" / run_id
        path = run / "acceptance/d47_screening.json"
        result = json.loads(path.read_bytes())
        assert result["schema_version"] == "d47_screening_v1"
        assert result["run_id"] == run_id
        assert result["rgb_index_sha256"] == sha(run / "safe_bundle/rgb_index.json")
        assert result["sampling"]["seed_sha256"] == sha(seed_path)
        assert result["detector"]["config_sha256"] == sha(REPO / result["detector"]["config_ref"])
        assert result["acceptance_only"] and result["not_for_runtime_or_safe_bundle"]
        assert not result["formal_acceptance"] and not result["gt_read"]
        rows = result["frames"]
        assert len(rows) == count * len(cameras)
        keys = {(r["camera_id"], r["frame_index"]) for r in rows}
        assert keys == {(c, k) for c in cameras for k in range(count)}
        index = json.loads((run / "safe_bundle/rgb_index.json").read_bytes())
        original = {(r["camera_id"], r["frame_index"]): r for r in index["frames"]}
        required = {"camera_id", "frame_index", "timestamp_s", "rgb_ref", "file_sha256",
                    "detections", "projection", "flags", "review_reasons", "review_required"}
        for r in rows:
            assert required <= r.keys()
            source = original[(r["camera_id"], r["frame_index"])]
            assert all(r[k] == v for k, v in source.items())
            assert sha(run / r["rgb_ref"]) == r["file_sha256"]
            assert r["timestamp_s"] == r["frame_index"] / 5
            assert set(r["review_reasons"]) <= {"FLAGGED", "D27_TARGET", "BLIND_BOUNDARY", "SWITCH_BOUNDARY", "RANDOM_SAMPLE"}
            assert r["review_required"] == bool(r["review_reasons"])
            assert ("FLAGGED" in r["review_reasons"]) == bool(r["flags"])
            assert isinstance(r["projection"]["expected_present"], bool)
            assert "expected_bbox_xyxy_px" in r["projection"]
            for d in r["detections"]:
                assert {"bbox_xyxy_px", "score", "labels"} <= d.keys()
                x0, y0, x1, y1 = d["bbox_xyxy_px"]
                assert 0 <= x0 < x1 <= 960 and 0 <= y0 < y1 <= 540
                assert 0 < d["score"] <= 1 and isinstance(d["labels"], list)
        camera_reports = {}
        for camera in cameras:
            batch = [r for r in rows if r["camera_id"] == camera]
            eligible = [r for r in batch if not set(r["review_reasons"]) - {"RANDOM_SAMPLE"}]
            def order(row):
                value = [seed, run_id, camera, row["frame_index"]]
                key = hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
                return key, row["frame_index"]
            selected = sorted(eligible, key=order)[:math.ceil(len(eligible) * .10)]
            actual = {r["frame_index"] for r in batch if "RANDOM_SAMPLE" in r["review_reasons"]}
            assert actual == {r["frame_index"] for r in selected}
            camera_reports[camera] = {
                "frames": len(batch), "review_required": sum(r["review_required"] for r in batch),
                "reasons": dict(Counter(v for r in batch for v in r["review_reasons"])),
                "sampling_eligible": len(eligible), "random_selected": sorted(actual),
                "no_detection_indices": [r["frame_index"] for r in batch if not r["detections"]],
                "missing_expected_indices": [r["frame_index"] for r in batch if "EXPECTED_PERSON_MISSING" in r["flags"]],
            }
        flags = dict(Counter(v for r in rows for v in r["flags"]))
        reasons = dict(Counter(v for r in rows for v in r["review_reasons"]))
        assert flags == result["summary"]["flags"]
        assert reasons == result["summary"]["review_reasons"]
        assert sum(r["review_required"] for r in rows) == result["summary"]["review_required"]
        assert sum("D27_TARGET" in r["review_reasons"] for r in rows) == (22 if event == "a" else 0)
        assert sum("BLIND_BOUNDARY" in r["review_reasons"] for r in rows) == (16 if event == "b1" else 0)
        reports.append({"run_id": run_id, "path": str(path), "sha256": sha(path),
                        "bytes": path.stat().st_size, "verified_frames": len(rows),
                        "summary": result["summary"], "cameras": camera_reports})
    print(json.dumps({"verified_total": sum(r["verified_frames"] for r in reports),
                      "reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
