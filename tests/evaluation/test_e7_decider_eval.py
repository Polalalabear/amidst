"""Focused unit tests for E7 Colab notebook, decider GT isolation, and acceleration comparison."""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from amidst.evaluation import e7_decider_eval as E7
from amidst.evaluation import e7_scoring_bridge as E7S

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "e7_colab_decider_eval.ipynb"
E7_MODULE_PATH = REPO_ROOT / "src" / "amidst" / "evaluation" / "e7_decider_eval.py"


def _make_synthetic_requests() -> list[E7.DeciderRequest]:
    reqs = []
    for i in range(6):
        group = "e3_16_segments" if i < 4 else "e6_12_segments"
        case_id = f"E3-A{i + 1}" if i < 4 else f"E6-S{i - 3}"
        reqs.append(
            E7.DeciderRequest(
                request_id=f"{case_id}|t{i * 10}",
                case_id=case_id,
                dataset_group=group,
                tick=i * 10,
                variable_text=f"DETECTIONS tick={i * 10}",
                candidates=(
                    {
                        "detection_id": "D1",
                        "camera_id": "CAM_EXT_CAR",
                        "box": [20.0, 60.0, 50.0, 130.0],
                        "score": 0.88,
                    },
                ),
                camera_ids=("CAM_EXT_CAR", "CAM_ENTRY"),
            )
        )
    return reqs


def test_notebook_json_validity_and_cell_structure():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    cells = nb["cells"]
    assert len(cells) >= 8

    # Cell 1 (index 1): centralized configuration
    cfg_src = "".join(cells[1]["source"])
    for token in ("PACK_ROOT", "DATASET_SCOPE", "MODEL_CONFIGS", "CPU_SAMPLE_CAP", "PINNED_DEPS"):
        assert token in cfg_src, f"Missing config token {token} in Cell 1"

    # Hardware provenance cell, MANIFEST SHA-256 verification cell, decider cell, scoring cell
    all_code = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    hw_idx = next(i for i, s in enumerate(all_code) if "collect_hardware_provenance" in s)
    mf_idx = next(i for i, s in enumerate(all_code) if "verify_manifest_sha256" in s)
    dec_idx = next(i for i, s in enumerate(all_code) if "run_acceleration_comparison" in s)
    score_idx = next(i for i, s in enumerate(all_code) if "score_e7_comparison" in s)

    assert hw_idx < mf_idx < dec_idx < score_idx, "Run All cell order violated"

    # ONLY the scoring cell may reference answer_table.json
    for idx, src in enumerate(all_code):
        if idx != score_idx:
            assert "answer_table.json" not in src, f"Non-scoring code cell {idx} references answer_table.json"
    assert "answer_table.json" in all_code[score_idx]


def test_decider_gt_isolation_ast_and_signature():
    source = E7_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # AST proof: no import of e3_scoring or e7_scoring_bridge
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "e3_scoring" not in alias.name
                assert "e7_scoring_bridge" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "e3_scoring" not in mod
            assert "e7_scoring_bridge" not in mod
            for alias in node.names:
                assert "e3_scoring" not in alias.name
                assert "e7_scoring_bridge" not in alias.name

    # Signature proof: no decider or runner accepts answer_table / gt / expected
    forbidden_params = {"answer_table", "gt", "gt_path", "gt_boxes", "gt_visible", "expected"}
    for fn in (
        E7.BaseDeciderAdapter.decide,
        E7.LayaTextDecider.__init__,
        E7.QwenVLDecider.__init__,
        E7.DiffusionVLMDecider.__init__,
        E7.run_acceleration_comparison,
    ):
        params = set(inspect.signature(fn).parameters.keys())
        assert not (params & forbidden_params), f"{fn} exposes forbidden GT param: {params & forbidden_params}"


def test_manifest_verification_stops_on_mismatch(tmp_path: Path):
    f1 = tmp_path / "requests.jsonl"
    f1.write_text('{"request_id":"r1"}\n', encoding="utf-8")
    good_sha = hashlib.sha256(f1.read_bytes()).hexdigest()
    manifest = tmp_path / "MANIFEST.sha256"
    manifest.write_text(f"{good_sha}  requests.jsonl\n", encoding="utf-8")

    res = E7.verify_manifest_sha256(tmp_path)
    assert res["status"] == "OK"
    assert res["files_verified"] == 1

    # Corrupt file -> immediate stop
    f1.write_text('{"request_id":"tampered"}\n', encoding="utf-8")
    with pytest.raises(E7.ManifestVerificationError, match="MANIFEST_SHA_MISMATCH"):
        E7.verify_manifest_sha256(tmp_path)


def test_laya_custom_code_audit_gate():
    reqs = _make_synthetic_requests()
    un_audited = E7.LayaTextDecider(
        custom_code_audited=False,
        inference_fn=lambda req, acc: json.dumps({"answer": "NOT_VISIBLE", "next_camera_ranking": ["CAM_EXT_CAR"]}),
    )
    with pytest.raises(E7.CustomCodeAuditError):
        un_audited.decide(reqs[0], accelerated=True)

    audited = E7.LayaTextDecider(
        custom_code_audited=True,
        audited_commit="deadbeef1234567890",
        inference_fn=lambda req, acc: json.dumps({"answer": "NOT_VISIBLE", "next_camera_ranking": ["CAM_EXT_CAR"]}),
    )
    out = audited.decide(reqs[0], accelerated=True)
    assert out["fallback_reason"] is None
    assert out["parsed"]["answer"] == "NOT_VISIBLE"
    assert out["retries_attempted"] == 0


def test_acceleration_comparison_scopes_and_no_retry_inflation():
    reqs = _make_synthetic_requests()
    calls = {"n": 0}

    def _stub_fn(req: E7.DeciderRequest, accelerated: bool) -> str:
        calls["n"] += 1
        # Simulate one format error on tick=10 (accelerated) and one disagreement on tick=20
        if req.tick == 10 and accelerated:
            return "NOT VALID JSON {{"
        if req.tick == 20 and not accelerated:
            return json.dumps({"answer": "NOT_VISIBLE", "next_camera_ranking": ["CAM_ENTRY"]})
        return json.dumps(
            {
                "answer": "SELECT",
                "camera_id": "CAM_EXT_CAR",
                "detection_id": "D1",
                "next_camera_ranking": ["CAM_EXT_CAR"],
            }
        )

    decider = E7.QwenVLDecider(inference_fn=_stub_fn)

    # 1. E3 16-segment scope (4 synthetic items) with CPU sample cap = 3
    res_e3 = E7.run_acceleration_comparison(
        decider,
        reqs,
        dataset_scope="e3_16_segments",
        input_mode="image_text",
        unaccelerated_sample_cap=3,
    )
    assert res_e3["dataset_scope"] == "e3_16_segments"
    assert res_e3["accelerated"]["sample_size"] == 4
    assert res_e3["unaccelerated"]["sample_size"] == 3
    assert res_e3["accelerated"]["format_fallback_count"] == 1
    assert res_e3["accelerated"]["format_fallback_rate"] == 0.25
    assert res_e3["accelerated"]["retries_total"] == 0
    assert res_e3["unaccelerated"]["retries_total"] == 0
    # 4 accelerated + 3 unaccelerated = 7 exact calls (zero retry inflation)
    assert calls["n"] == 7
    assert res_e3["compared_decision_points"] == 3
    assert len(res_e3["differences"]) == 2  # tick 10 (fallback vs SELECT) and tick 20 (SELECT vs NOT_VISIBLE)
    assert res_e3["decision_agreement_vs_unaccelerated"] == round(1 / 3, 4)

    # 2. E6 12-segment additional group scope (2 synthetic items)
    res_e6 = E7.run_acceleration_comparison(
        decider,
        reqs,
        dataset_scope="e6_12_segments",
        input_mode="text_only",
        unaccelerated_sample_cap=20,
    )
    assert res_e6["dataset_scope"] == "e6_12_segments"
    assert res_e6["accelerated"]["sample_size"] == 2
    assert res_e6["unaccelerated"]["sample_size"] == 2
    assert res_e6["decision_agreement_vs_unaccelerated"] == 1.0

    # 3. Scoring bridge ONLY reads answer table
    answer_table = {
        r.request_id: {
            "gt_visible": ["CAM_EXT_CAR"],
            "gt_boxes": {"CAM_EXT_CAR": [18.0, 58.0, 52.0, 132.0]},
            "candidate_boxes": {"CAM_EXT_CAR|D1": [20.0, 60.0, 50.0, 130.0]},
        }
        for r in reqs
    }
    scored = E7S.score_e7_comparison(res_e3, answer_table)
    assert scored["accelerated"]["n_decision_points"] == 4
    assert scored["accelerated"]["decision_point_accuracy"] == 0.75  # 3/4 correct (1 format fallback)
    assert scored["unaccelerated"]["decision_point_accuracy"] == round(2 / 3, 4)
