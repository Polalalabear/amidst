"""R-N CLI: the old two-corpus layout is unchanged (golden produced by the pre-change script) and the new --root layout reads
any recording (E6 formal 12). Synthetic frames/detections only; Projector is a stub, no catalog, no GT, no model."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
GOLDEN = Path(__file__).parent / "fixtures" / "e6_rn_golden.json"
CAMS = ["CAM_ENTRY", "CAM_W1"]
NORMALIZE_DROP = ("sources", "code_sha256", "protocol_sha256")     # file hashes: PNG encoder / this very script


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class StubProjector:
    def __init__(self, *_):
        pass

    def ground(self, cam, u, v, w, h):
        return [u / 50.0, v / 50.0]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def build_recording(root: Path, cid: str, cameras: Path, b1_runs: Path, n=30):
    """indexes/rgb pinned like the E3 recordings; red walker in CAM_W1 for ticks 0-14 and 25-29, blue walker always in CAM_ENTRY."""
    (root / "indexes" / cid).mkdir(parents=True)
    (root / "rgb" / cid).mkdir(parents=True)
    records, rgb_records = [], []
    for t in range(n):
        for cam in CAMS:
            rel = f"rgb/{cid}/{cam}/{t:06d}.png"
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (320, 180), (200, 30, 30) if cam == "CAM_W1" else (30, 30, 200)).save(p)
            red_here = cam == "CAM_W1" and (t < 15 or t >= 25)
            dets = []
            if red_here:
                dets.append({"class_label": "person", "score": 0.9, "bbox_xyxy_px": [100 + t, 40, 130 + t, 150]})
            if cam == "CAM_ENTRY":
                dets.append({"class_label": "person", "score": 0.4, "bbox_xyxy_px": [200, 40, 230, 150]})
            records.append({"frame_index": t, "camera_id": cam, "rgb_file_sha256": sha(p.read_bytes()), "detections": dets})
            rgb_records.append({"camera_id": cam, "frame_index": t, "relative_path": rel})
    rec_raw = ("\n".join(json.dumps(r) for r in records) + "\n").encode()
    (root / "indexes" / cid / "detection_index.records.jsonl").write_bytes(rec_raw)
    rgb_raw = json.dumps({"records": rgb_records}).encode()
    (root / "rgb" / cid / "rgb_index.json").write_bytes(rgb_raw)
    (root / "indexes" / cid / "detection_index.json").write_text(json.dumps({
        "records_ref": "detection_index.records.jsonl", "records_file_sha256": sha(rec_raw), "rgb_index_sha256": sha(rgb_raw)}))
    b1 = {"camera_catalog_sha256": sha(cameras.read_bytes()),
          "rows": [{"tick": t, "events": [{"type": "ACQUIRE"}] if t == 0 else [], "tracking": {"est_xy": [2.0, 2.0]}} for t in range(n)]}
    (b1_runs / cid).mkdir(parents=True, exist_ok=True)
    (b1_runs / cid / "B1.k1.json").write_text(json.dumps(b1))


def run_module(rn, argv):
    rn.Projector, rn.load_cameras = StubProjector, lambda p: None
    rn.main(argv)


def normalized(path: Path):
    doc = json.loads(path.read_text())
    for k in NORMALIZE_DROP:
        doc[k] = "<dropped>" if k != "sources" else sorted(doc[k])
    doc["seed"] = {k: v for k, v in doc["seed"].items() if k != "b1_sha256"}
    return doc


@pytest.fixture()
def cameras(tmp_path):
    p = tmp_path / "cameras.json"
    p.write_text('{"cameras": []}')
    return p


def old_layout(tmp_path, cameras, cid="E3-T1"):
    ev = tmp_path / "ev"
    build_recording(ev / "e3-652-20261122", cid, cameras, ev / "f4-658-20261122" / "runs-final-9")
    (ev / "e3-reappearances-20261122").mkdir()
    return ev


def test_old_layout_matches_golden_from_pre_change_script(tmp_path, cameras):
    rn = load(ROOT / "scripts/evaluation/e6_rule_neutral.py", "rn_new")
    ev = old_layout(tmp_path, cameras)
    run_module(rn, ["--evidence", str(ev), "--cameras", str(cameras), "--out", str(tmp_path / "out")])
    golden = json.loads(GOLDEN.read_text())
    got = {arm: normalized(tmp_path / "out/E3-T1" / f"{arm}.json") for arm in ("RN_U", "RN_N")}
    assert got == golden


def test_root_layout_equals_old_layout_bytes(tmp_path, cameras):
    rn = load(ROOT / "scripts/evaluation/e6_rule_neutral.py", "rn_new2")
    ev = old_layout(tmp_path, cameras)
    run_module(rn, ["--evidence", str(ev), "--cameras", str(cameras), "--out", str(tmp_path / "old")])
    run_module(rn, ["--root", str(ev / "e3-652-20261122"), "--b1-runs", str(ev / "f4-658-20261122/runs-final-9"),
                    "--cameras", str(cameras), "--out", str(tmp_path / "new")])
    for arm in ("RN_U", "RN_N"):
        assert (tmp_path / "old/E3-T1" / f"{arm}.json").read_bytes() == (tmp_path / "new/E3-T1" / f"{arm}.json").read_bytes()


def test_root_layout_reads_non_e3_case_ids_and_cases_filter(tmp_path, cameras):
    rn = load(ROOT / "scripts/evaluation/e6_rule_neutral.py", "rn_new3")
    root, b1 = tmp_path / "formal", tmp_path / "b1"
    for cid in ("E6-S01", "E6-S02", "E6-S03"):
        build_recording(root, cid, cameras, b1)
    run_module(rn, ["--root", str(root), "--b1-runs", str(b1), "--cameras", str(cameras), "--out", str(tmp_path / "all")])
    assert sorted(p.name for p in (tmp_path / "all").iterdir()) == ["E6-S01", "E6-S02", "E6-S03"]
    run_module(rn, ["--root", str(root), "--b1-runs", str(b1), "--cases", "E6-S02", "--cameras", str(cameras), "--out", str(tmp_path / "one")])
    assert [p.name for p in (tmp_path / "one").iterdir()] == ["E6-S02"]
    doc = json.loads((tmp_path / "one/E6-S02/RN_U.json").read_text())
    assert doc["case_id"] == "E6-S02" and doc["paid_calls"] == 0 and doc["identity"] == "UNCONFIRMED"
    assert doc["rows"] and doc["calls"][0]["kind"] == "FIRST"


def test_argument_rules_and_pins(tmp_path, cameras):
    rn = load(ROOT / "scripts/evaluation/e6_rule_neutral.py", "rn_new4")
    rn.Projector, rn.load_cameras = StubProjector, lambda p: None
    for argv in (["--cameras", str(cameras), "--out", str(tmp_path / "a")],                                   # neither layout
                 ["--evidence", "x", "--root", "y", "--b1-runs", "z", "--cameras", str(cameras), "--out", str(tmp_path / "b")],
                 ["--root", "y", "--cameras", str(cameras), "--out", str(tmp_path / "c")]):                   # --root without --b1-runs
        with pytest.raises(SystemExit):
            rn.main(argv)
    (tmp_path / "exists").mkdir()
    with pytest.raises(ValueError, match="OUTPUT_EXISTS"):
        rn.main(["--root", "y", "--b1-runs", "z", "--cameras", str(cameras), "--out", str(tmp_path / "exists")])
    root, b1 = tmp_path / "formal", tmp_path / "b1"
    build_recording(root, "E6-S01", cameras, b1)
    other = tmp_path / "other.json"
    other.write_text("{}")
    with pytest.raises(ValueError, match="CALIBRATION_PIN"):
        rn.main(["--root", str(root), "--b1-runs", str(b1), "--cameras", str(other), "--out", str(tmp_path / "pin")])
    with pytest.raises(ValueError, match="NO_CASES"):
        rn.main(["--root", str(tmp_path / "empty"), "--b1-runs", str(b1), "--cameras", str(cameras), "--out", str(tmp_path / "nc")])
