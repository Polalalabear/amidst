"""Focused unit tests for E7 Colab notebook, D385 answer-table compliance, decider GT isolation, and acceleration comparison."""
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
    assert len(cells) >= 9

    # Cell 1 (index 1): centralized configuration + real HF IDs (no PIN_* placeholders) + PINNED_DEPS comment
    cfg_src = "".join(cells[1]["source"])
    for token in (
        "PACK_ROOT",
        "DATASET_SCOPE",
        "MODEL_CONFIGS",
        "CPU_SAMPLE_CAP",
        "PINNED_DEPS",
        "GIT_REPO_URL",
        "PINNED_GIT_COMMIT",
        "SMOKE_MODE",
    ):
        assert token in cfg_src, f"Missing config token {token} in Cell 1"
    assert "PIN_REVISION_BEFORE_RUN" not in cfg_src
    assert "PIN_AUDITED_COMMIT_BEFORE_RUN" not in cfg_src
    assert "pyproject.toml" in cfg_src, "PINNED_DEPS compatibility comment missing"

    all_code = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    drive_idx = next(i for i, s in enumerate(all_code) if "drive.mount" in s and "git" in s)
    hw_idx = next(i for i, s in enumerate(all_code) if "collect_hardware_provenance" in s)
    mf_idx = next(i for i, s in enumerate(all_code) if "verify_manifest_sha256" in s)
    dec_idx = next(i for i, s in enumerate(all_code) if "run_acceleration_comparison" in s)
    score_idx = next(i for i, s in enumerate(all_code) if "score_e7_comparison" in s)

    assert drive_idx < hw_idx < mf_idx < dec_idx < score_idx, "Run All cell order violated"

    # Cell 6 wires real HF backend builders + smoke mode
    dec_src = all_code[dec_idx]
    for fn_name in (
        "build_qwen_vl_inference_fn",
        "build_laya_text_inference_fn",
        "build_diffusion_vlm_inference_fn",
        "build_smoke_inference_fn",
    ):
        assert fn_name in dec_src, f"Cell 6 missing backend builder {fn_name}"

    # ONLY the scoring cell may reference answer_table.json
    for idx, src in enumerate(all_code):
        if idx != score_idx:
            assert "answer_table.json" not in src, f"Non-scoring code cell {idx} references answer_table.json"
    assert "answer_table.json" in all_code[score_idx]


def test_notebook_cell7_hard_fails_on_missing_answer_table(tmp_path: Path):
    """P2-3: Cell 7 MUST raise FileNotFoundError on missing answer_table.json (no silent {} fallback)."""
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cell7 = next(c for c in nb["cells"] if c.get("id") == "e7-cell-7-scoring")
    src = "".join(cell7["source"])
    assert "FileNotFoundError" in src
    assert "else {}" not in src

    # Execute Cell 7 with an empty PACK_ROOT and assert FileNotFoundError is raised immediately
    env = {
        "PACK_ROOT": tmp_path,
        "RAW_COMPARISONS": [],
        "HARDWARE_PROVENANCE": {},
        "MANIFEST_VERIFICATION": {},
        "DATASET_SCOPE": "e3_16_segments",
    }
    with pytest.raises(FileNotFoundError, match="MISSING_ANSWER_TABLE"):
        exec(compile(src, "e7-cell-7-scoring", "exec"), env)


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
        E7.build_qwen_vl_inference_fn,
        E7.build_laya_text_inference_fn,
        E7.build_diffusion_vlm_inference_fn,
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


def test_laya_and_diffusion_custom_code_audit_gate():
    reqs = _make_synthetic_requests()
    un_audited = E7.LayaTextDecider(
        custom_code_audited=False,
        inference_fn=lambda req, acc: json.dumps({"answer": "NOT_VISIBLE", "next_camera_ranking": ["CAM_EXT_CAR"]}),
    )
    with pytest.raises(E7.CustomCodeAuditError):
        un_audited.decide(reqs[0], accelerated=True)

    with pytest.raises(E7.CustomCodeAuditError):
        E7.build_laya_text_inference_fn(custom_code_audited=False)

    with pytest.raises(E7.CustomCodeAuditError):
        E7.build_diffusion_vlm_inference_fn(custom_code_audited=False)

    audited = E7.LayaTextDecider(
        custom_code_audited=True,
        audited_commit="deadbeef1234567890",
        inference_fn=lambda req, acc: json.dumps({"answer": "NOT_VISIBLE", "next_camera_ranking": ["CAM_EXT_CAR"]}),
    )
    out = audited.decide(reqs[0], accelerated=True)
    assert out["fallback_reason"] is None
    assert out["parsed"]["answer"] == "NOT_VISIBLE"
    assert out["retries_attempted"] == 0


def test_d385_answer_table_rejects_forbidden_gt_fields():
    """P1-1: Answer tables containing gt_visible, gt_boxes, actors, etc. MUST be hard-rejected."""
    dec_rec = {
        "request_id": "E3-A1|t0",
        "parsed": {"answer": "SELECT", "camera_id": "CAM_EXT_CAR", "detection_id": "D1"},
    }
    for bad_key, bad_val in (
        ("gt_visible", ["CAM_EXT_CAR"]),
        ("gt_boxes", {"CAM_EXT_CAR": [18.0, 58.0, 52.0, 132.0]}),
        ("actors", []),
        ("depth", {}),
        ("visibility", {}),
        ("trajectories", []),
        ("world_xy", [1.0, 2.0]),
        ("gt_body_box", [1.0, 2.0, 3.0, 4.0]),
    ):
        entry = {
            "expected_answer": "SELECT",
            "expected_camera_ids": ["CAM_EXT_CAR"],
            "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
            bad_key: bad_val,
        }
        with pytest.raises(ValueError, match="D385_FORBIDDEN_GT_FIELD"):
            E7S.score_single_decision(dec_rec, entry)

        with pytest.raises(ValueError, match="D385_FORBIDDEN_GT_FIELD"):
            E7S.validate_colab_answer_table({"E3-A1|t0": entry})

    # Top-level forbidden key also rejected
    with pytest.raises(ValueError, match="D385_FORBIDDEN_GT_FIELD"):
        E7S.validate_colab_answer_table({"gt_boxes": {}})


def test_d385_label_only_scoring_and_own_box_needs_mac_scoring():
    """P1-1: Label-only answer tables score SELECT, NOT_VISIBLE, UNCERTAIN, STILL_HERE_OCCLUDED and mark OWN_BOX."""
    # SELECT hit & miss
    entry_select = {
        "request_id": "R1",
        "expected_answer": "SELECT",
        "expected_camera_ids": ["CAM_EXT_CAR"],
        "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
    }
    assert E7S.score_single_decision(
        {"request_id": "R1", "parsed": {"answer": "SELECT", "camera_id": "CAM_EXT_CAR", "detection_id": "D1"}},
        entry_select,
    )["outcome"] == "CORRECT"
    assert E7S.score_single_decision(
        {"request_id": "R1", "parsed": {"answer": "SELECT", "camera_id": "CAM_EXT_CAR", "detection_id": "D2"}},
        entry_select,
    )["outcome"] == "WRONG_PERSON"

    # OWN_BOX -> NEEDS_MAC_SCORING (not inflated as correct)
    own_res = E7S.score_single_decision(
        {"request_id": "R1", "parsed": {"answer": "OWN_BOX", "camera_id": "CAM_EXT_CAR", "box_xyxy": [10, 10, 40, 80]}},
        entry_select,
    )
    assert own_res["outcome"] == "NEEDS_MAC_SCORING"
    assert own_res["correct"] is False

    # NOT_VISIBLE
    entry_nv = {
        "request_id": "R2",
        "expected_answer": "NOT_VISIBLE",
        "expected_camera_ids": [],
        "expected_detection_ids": {},
    }
    assert E7S.score_single_decision({"request_id": "R2", "parsed": {"answer": "NOT_VISIBLE"}}, entry_nv) == {
        "outcome": "BLIND_OK",
        "correct": True,
    }
    assert E7S.score_single_decision(
        {"request_id": "R2", "parsed": {"answer": "SELECT", "camera_id": "CAM_EXT_CAR", "detection_id": "D1"}},
        entry_nv,
    ) == {"outcome": "FALSE_LOCK", "correct": False}

    # UNCERTAIN
    entry_unc = {
        "request_id": "R3",
        "expected_answer": "UNCERTAIN",
        "expected_camera_ids": [],
        "expected_detection_ids": {},
    }
    assert E7S.score_single_decision({"request_id": "R3", "parsed": {"answer": "UNCERTAIN"}}, entry_unc) == {
        "outcome": "CORRECT",
        "correct": True,
    }

    # STILL_HERE_OCCLUDED
    entry_occ = {
        "request_id": "R4",
        "expected_answer": "STILL_HERE_OCCLUDED",
        "expected_camera_ids": ["CAM_ENTRY"],
        "expected_detection_ids": {},
    }
    assert E7S.score_single_decision(
        {"request_id": "R4", "parsed": {"answer": "STILL_HERE_OCCLUDED", "camera_id": "CAM_ENTRY"}},
        entry_occ,
    ) == {"outcome": "CORRECT", "correct": True}
    assert E7S.score_single_decision(
        {"request_id": "R4", "parsed": {"answer": "STILL_HERE_OCCLUDED", "camera_id": "CAM_EXT_CAR"}},
        entry_occ,
    ) == {"outcome": "WRONG_CAMERA", "correct": False}


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
        if req.tick == 30 and accelerated:
            return json.dumps(
                {
                    "answer": "OWN_BOX",
                    "camera_id": "CAM_EXT_CAR",
                    "box_xyxy": [20.0, 60.0, 50.0, 130.0],
                    "next_camera_ranking": ["CAM_EXT_CAR"],
                }
            )
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

    # 3. Scoring bridge ONLY reads D385 label-only answer table (no gt_visible / gt_boxes!)
    answer_table = {
        r.request_id: {
            "request_id": r.request_id,
            "case_id": r.case_id,
            "tick": r.tick,
            "expected_answer": "SELECT",
            "expected_camera_ids": ["CAM_EXT_CAR"],
            "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
        }
        for r in reqs
    }
    scored = E7S.score_e7_comparison(res_e3, answer_table)
    assert scored["accelerated"]["n_decision_points"] == 4
    # tick 0: SELECT (correct), tick 10: FALLBACK, tick 20: SELECT (correct), tick 30: OWN_BOX (NEEDS_MAC_SCORING, not inflated)
    assert scored["accelerated"]["needs_mac_scoring_count"] == 1
    assert scored["accelerated"]["decision_point_accuracy"] == 0.5  # 2/4
    assert scored["unaccelerated"]["decision_point_accuracy"] == round(2 / 3, 4)


def test_p1a_write_colab_answer_table_rejects_before_creating_file_and_pre_upload_gate(tmp_path: Path):
    """P1-A: write_colab_answer_table validates BEFORE creating the file; verify_colab_pack_pre_upload gates packs."""
    bad_path = tmp_path / "bad.json"
    bad_table = {
        "E3-A1|t0": {
            "expected_answer": "SELECT",
            "expected_camera_ids": ["CAM_EXT_CAR"],
            "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
            "gt_visible": ["CAM_EXT_CAR"],
        }
    }
    with pytest.raises(ValueError, match="D385_FORBIDDEN_GT_FIELD"):
        E7S.write_colab_answer_table(bad_path, bad_table)
    assert not bad_path.exists(), "Failed validation MUST NOT create output file"

    # Build valid upload pack and verify pre-upload gate + MANIFEST
    pack_root = tmp_path / "pack"
    good_table = {
        "E3-A1|t0": {
            "request_id": "E3-A1|t0",
            "case_id": "E3-A1",
            "tick": 0,
            "expected_answer": "SELECT",
            "expected_camera_ids": ["CAM_EXT_CAR"],
            "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
        }
    }
    ans_path = pack_root / "scoring_only" / "answer_table.json"
    digest = E7S.write_colab_answer_table(ans_path, good_table)
    assert ans_path.is_file()
    assert digest == hashlib.sha256(ans_path.read_bytes()).hexdigest()

    req_path = pack_root / "requests" / "e3_16_segments.jsonl"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text('{"request_id":"E3-A1|t0","case_id":"E3-A1","tick":0}\n', encoding="utf-8")
    req_sha = hashlib.sha256(req_path.read_bytes()).hexdigest()
    (pack_root / "MANIFEST.sha256").write_text(
        f"{digest}  scoring_only/answer_table.json\n{req_sha}  requests/e3_16_segments.jsonl\n",
        encoding="utf-8",
    )

    gate = E7S.verify_colab_pack_pre_upload(pack_root)
    assert gate["status"] == "OK"
    assert gate["answer_table_entries"] == 1
    assert gate["manifest_verification"]["status"] == "OK"

    # Forbidden GT file inside pack must be rejected
    (pack_root / "a-log.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="D385_FORBIDDEN_PACK_FILE"):
        E7S.verify_colab_pack_pre_upload(pack_root)


def test_p1b_d392_gt_regime_rejected_and_strict_value_type_validation():
    """P1-B / D392: gt_regime forbidden, numeric boxes in legal keys rejected, unknown non-forbidden keys rejected."""
    # 1. gt_regime is now FORBIDDEN (D392)
    with pytest.raises(ValueError, match="D385_FORBIDDEN_GT_FIELD"):
        E7S.validate_colab_answer_table(
            {
                "E3-A1|t0": {
                    "expected_answer": "SELECT",
                    "expected_camera_ids": ["CAM_EXT_CAR"],
                    "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
                    "gt_regime": "VISIBLE",
                }
            }
        )

    # 2. Legal key expected_detection_ids smuggling numeric bounding box -> D385_INVALID_ANSWER_VALUE
    with pytest.raises(ValueError, match="D385_INVALID_ANSWER_VALUE"):
        E7S.validate_colab_answer_table(
            {
                "E3-A1|t0": {
                    "expected_answer": "SELECT",
                    "expected_camera_ids": ["CAM_EXT_CAR"],
                    "expected_detection_ids": {"CAM_X": [[18.0, 58.0, 52.0, 132.0]]},
                }
            }
        )

    # 3. Non-forbidden unknown key (box_xyxy) -> D385_DISALLOWED_ANSWER_FIELD
    with pytest.raises(ValueError, match="D385_DISALLOWED_ANSWER_FIELD"):
        E7S.validate_colab_answer_table(
            {
                "E3-A1|t0": {
                    "expected_answer": "SELECT",
                    "expected_camera_ids": ["CAM_EXT_CAR"],
                    "expected_detection_ids": {"CAM_EXT_CAR": ["D1"]},
                    "box_xyxy": [1, 2, 3, 4],
                }
            }
        )

    # 4. Invalid expected_answer enum, non-str expected_camera_ids, bool tick -> D385_INVALID_ANSWER_VALUE
    with pytest.raises(ValueError, match="D385_INVALID_ANSWER_VALUE"):
        E7S.validate_colab_answer_entry({"expected_answer": "OWN_BOX"}, key="R1")
    with pytest.raises(ValueError, match="D385_INVALID_ANSWER_VALUE"):
        E7S.validate_colab_answer_entry({"expected_answer": "SELECT", "expected_camera_ids": [123]}, key="R2")
    with pytest.raises(ValueError, match="D385_INVALID_ANSWER_VALUE"):
        E7S.validate_colab_answer_entry({"expected_answer": "SELECT", "tick": True}, key="R3")


def test_p2_1_notebook_cell6_skips_unaudited_models_without_crashing():
    """P2-1: Cell 6 records unaudited custom-code models as SKIPPED_UNAUDITED and completes Qwen runs."""
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cell1 = next(c for c in nb["cells"] if c.get("id") == "e7-cell-1-config")
    cell6 = next(c for c in nb["cells"] if c.get("id") == "e7-cell-6-run-deciders")

    env: dict = {}
    exec(compile("".join(cell1["source"]), "e7-cell-1-config", "exec"), env)
    env["SMOKE_MODE"] = True
    env["REQUESTS"] = _make_synthetic_requests()
    exec(compile("".join(cell6["source"]), "e7-cell-6-run-deciders", "exec"), env)

    # Qwen (2 modes: image_text + text_only) ran cleanly; laya and diffusion_vlm were skipped as SKIPPED_UNAUDITED
    assert len(env["RAW_COMPARISONS"]) == 2
    assert all(r["party_id"] == "qwen_vl" for r in env["RAW_COMPARISONS"])
    skipped = env["SKIPPED_MODELS"]
    assert len(skipped) == 2
    assert {s["party_id"] for s in skipped} == {"laya_text", "diffusion_vlm"}
    assert all(s["status"] == "SKIPPED_UNAUDITED" for s in skipped)


def test_p2_3_and_p2_4_warmup_excluded_from_latency_and_hardware_provenance_dtype():
    """P2-3: warmup() runs before timed decide() loop and stores load_ms separately. P2-4: bf16/dtype provenance."""
    import time

    reqs = _make_synthetic_requests()[:2]
    events: list[str] = []

    def _fast_infer(req: E7.DeciderRequest, accelerated: bool) -> str:
        events.append(f"infer:{req.request_id}:{accelerated}")
        return json.dumps({"answer": "NOT_VISIBLE", "next_camera_ranking": ["CAM_EXT_CAR"]})

    def _slow_warmup(accelerated: bool) -> float:
        events.append(f"warmup:{accelerated}")
        time.sleep(0.03)
        return 30.0

    _fast_infer.warmup = _slow_warmup  # type: ignore[attr-defined]
    decider = E7.QwenVLDecider(inference_fn=_fast_infer)
    res = E7.run_acceleration_comparison(decider, reqs, dataset_scope="e3_16_segments", input_mode="text_only")

    # Warmup occurred BEFORE the first infer call for both accelerated and unaccelerated passes
    assert events[0] == "warmup:True"
    assert events[1].startswith("infer:")
    assert "warmup:False" in events
    assert events.index("warmup:False") < next(i for i, e in enumerate(events) if e.endswith(":False") and e.startswith("infer:"))

    # load_ms recorded separately (>= 20 ms) while per-request latency_p95_ms stays tiny (< 20 ms)
    assert res["accelerated"]["load_ms"] >= 20.0
    assert res["unaccelerated"]["load_ms"] >= 20.0
    assert res["accelerated"]["latency_p95_ms"] < 20.0
    assert res["unaccelerated"]["latency_p95_ms"] < 20.0

    # P2-4: Hardware provenance records cuda_bf16_supported (bool) and actual_accelerated_dtype
    hw = E7.collect_hardware_provenance(REPO_ROOT)
    assert isinstance(hw["cuda_bf16_supported"], bool)
    assert hw["actual_accelerated_dtype"] in {"bf16", "fp16", "fp32"}
