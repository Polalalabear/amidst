"""#766: E7 Colab runtime helpers (versions, zip pack, checkpoints, packaging, notebook wiring)."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from amidst.evaluation import e7_colab_runtime as R

REPO = Path(__file__).resolve().parents[2]
NB = REPO / "notebooks" / "e7_colab_decider_eval.ipynb"


def test_parse_pins_exact_only():
    assert R.parse_pins(["torch==2.7.1", "huggingface_hub==0.33.4"]) == {"torch": "2.7.1", "huggingface_hub": "0.33.4"}
    with pytest.raises(ValueError):
        R.parse_pins(["torch>=2.6"])


def test_version_check_ok_and_local_tag_ignored():
    pins = {"torch": "2.7.1"}
    assert R.check_runtime_versions(pins, disk_versions={"torch": "2.7.1+cu126"}, loaded_versions={"torch": None}) == []


def test_version_check_restart_message_when_loaded_differs():
    probs = R.check_runtime_versions({"torch": "2.7.1"}, disk_versions={"torch": "2.7.1"}, loaded_versions={"torch": "2.9.0"})
    assert len(probs) == 1 and "重啟" in probs[0] and "2.9.0" in probs[0]


def test_version_check_disk_mismatch_and_missing():
    probs = R.check_runtime_versions({"a": "1", "b": "2"}, disk_versions={"a": "9", "b": None}, loaded_versions={})
    assert len(probs) == 2


def test_check_min_versions_unchanged_runtime(monkeypatch):
    monkeypatch.setattr(R.metadata, "version", lambda n: {"numpy": "2.3.0"}[n])
    assert R.check_min_versions({"numpy": "2.0.0"}) == {"numpy": "2.3.0"}
    with pytest.raises(RuntimeError):
        R.check_min_versions({"numpy": "2.5.0"})


def test_check_min_versions_memory_vs_disk_mismatch_needs_restart(monkeypatch):
    import types

    monkeypatch.setattr(R.metadata, "version", lambda n: "2.3.0")
    monkeypatch.setitem(R.sys.modules, "numpy", types.SimpleNamespace(__version__="2.1.3"))
    with pytest.raises(RuntimeError, match="重啟"):
        R.check_min_versions({"numpy": "2.0.0"})


def _mk_pack(root: Path) -> None:
    (root / "requests").mkdir(parents=True)
    (root / "requests" / "r.jsonl").write_text("{}\n")
    (root / "PACK_INFO.json").write_text("{}")
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}" for p in sorted(root.rglob("*")) if p.is_file()]
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")


def test_zip_roundtrip_with_sidecar_and_manifest(tmp_path):
    from amidst.evaluation.e7_decider_eval import verify_manifest_sha256

    pack = tmp_path / "pack"
    _mk_pack(pack)
    z = R.make_pack_zip(pack, tmp_path / "drive" / "e7-colab-pack.zip")
    assert (tmp_path / "drive" / "e7-colab-pack.zip.sha256").read_text().split()[0] == z["zip_sha256"]
    got = R.extract_pack_zip(tmp_path / "drive" / "e7-colab-pack.zip", tmp_path / "content" / "e7")
    assert verify_manifest_sha256(got["pack_root"])["status"] == "OK"


def test_zip_sha_mismatch_and_traversal(tmp_path):
    pack = tmp_path / "pack"
    _mk_pack(pack)
    z = R.make_pack_zip(pack, tmp_path / "p.zip")
    with pytest.raises(RuntimeError, match="PACK_ZIP_SHA_MISMATCH"):
        R.extract_pack_zip(Path(z["zip"]), tmp_path / "o", expected_sha256="0" * 64)
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../evil.txt", "x")
    with pytest.raises(RuntimeError, match="PATH_TRAVERSAL"):
        R.extract_pack_zip(bad, tmp_path / "o2")


def test_zip_nested_top_folder(tmp_path):
    pack = tmp_path / "e7-colab-pack-20261127"
    _mk_pack(pack)
    z = tmp_path / "n.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in pack.rglob("*"):
            if p.is_file():
                zf.write(p, f"{pack.name}/{p.relative_to(pack).as_posix()}")
    assert R.extract_pack_zip(z, tmp_path / "o")["pack_root"].name == pack.name


def test_checkpoint_resume_skips_only_matching_fingerprint(tmp_path):
    fp = R.run_fingerprint(git_commit="a" * 40, dataset_scope="s", n_requests=3, smoke_mode=False, cpu_sample_cap=20, pinned_deps=["x==1"])
    assert R.load_group_checkpoint(tmp_path, "qwen_vl", "image_text", fp) is None
    R.save_group_checkpoint(tmp_path, "qwen_vl", "image_text", {"k": 1}, fp)
    assert R.load_group_checkpoint(tmp_path, "qwen_vl", "image_text", fp) == {"k": 1}
    assert R.load_group_checkpoint(tmp_path, "qwen_vl", "text_only", fp) is None
    other = dict(fp, n_requests=4)
    assert R.load_group_checkpoint(tmp_path, "qwen_vl", "image_text", other) is None
    R.checkpoint_path(tmp_path, "qwen_vl", "image_text").write_text("{broken")
    assert R.load_group_checkpoint(tmp_path, "qwen_vl", "image_text", fp) is None


def test_package_run_contains_notes_checkpoints_manifest(tmp_path):
    fp = {"f": 1}
    R.save_group_checkpoint(tmp_path, "p", "m", {"r": 1}, fp)
    (tmp_path / "e7_analysis_x.json").write_text("{}")
    notes = R.build_run_notes(notebook_version="v", git_commit="c", python_version="3.13", pinned_deps=["a==1"], versions={},
                              pack_zip_sha256=None, manifest_verification={}, smoke_mode=True, completed_groups=["p/m"],
                              resumed_groups=[], skipped_models=[], hf_provenance={}, deviations=["none"])
    assert notes["pack_zip_sha256"] == "UNKNOWN"
    res = R.package_run(tmp_path, "e7-run-x", notes, [tmp_path / "e7_analysis_x.json"])
    with zipfile.ZipFile(res["zip"]) as zf:
        names = set(zf.namelist())
    assert {"e7-run-x/RUN_NOTES.json", "e7-run-x/MANIFEST.sha256", "e7-run-x/checkpoints/p__m.json", "e7-run-x/e7_analysis_x.json"} <= names


def _nb_cells():
    nb = json.loads(NB.read_text(encoding="utf-8"))
    return {c["id"]: "".join(c["source"]) for c in nb["cells"]}


def test_notebook_pins_are_cp313_pair_and_not_downgrading_numpy_pillow():
    src = _nb_cells()["e7-cell-1-config"]
    ns: dict = {}
    start = src.index("PINNED_DEPS = [")
    exec(src[start:src.index("]", start) + 1], ns)  # noqa: S102 - literal list from our own notebook
    pins = R.parse_pins(ns["PINNED_DEPS"])
    assert pins["torch"] == "2.7.1" and pins["torchvision"] == "0.22.1"
    assert "numpy" not in pins and "Pillow" not in pins and "matplotlib" not in pins
    assert "66285546d2b821cf421d4f5eb2576359d3770cd3" in src


def test_notebook_wiring_resume_zip_package_and_gt_isolation():
    c = _nb_cells()
    full = "\n".join(c.values())
    assert "assert_runtime_consistent" in c["e7-cell-2-deps"]
    assert "extract_pack_zip" in full
    run = c["e7-cell-6-run-deciders"]
    assert "load_group_checkpoint" in run and "save_group_checkpoint" in run
    assert "package_run" in full
    assert "answer_table" not in run and "scoring_only" not in run  # GT isolation: decider cell never touches it


def test_notebook_cell6_resumes_second_run_without_loading_models(tmp_path):
    from tests.evaluation.test_e7_decider_eval import _make_synthetic_requests  # type: ignore

    nb = json.loads(NB.read_text(encoding="utf-8"))
    cells = {c["id"]: "".join(c["source"]) for c in nb["cells"]}

    def run():
        env: dict = {}
        exec(compile(cells["e7-cell-1-config"], "c1", "exec"), env)
        env.update(SMOKE_MODE=True, REQUESTS=_make_synthetic_requests(), OUTPUT_DIR=tmp_path, HARDWARE_PROVENANCE={"git_commit": "x"})
        exec(compile(cells["e7-cell-6-run-deciders"], "c6", "exec"), env)
        return env

    first = run()
    assert len(first["RAW_COMPARISONS"]) == 4 and first["RESUMED_GROUPS"] == []
    assert len(list((tmp_path / "checkpoints").glob("*.json"))) == 4
    second = run()
    assert len(second["RESUMED_GROUPS"]) == 4 and len(second["RAW_COMPARISONS"]) == 4
    assert second["RAW_COMPARISONS"] == first["RAW_COMPARISONS"]
    # a group that did not finish (checkpoint removed) is re-run, the others are skipped
    next((tmp_path / "checkpoints").glob("laya_typed__*.json")).unlink()
    third = run()
    assert len(third["RESUMED_GROUPS"]) == 3 and len(third["RAW_COMPARISONS"]) == 4
