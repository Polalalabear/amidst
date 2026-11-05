"""Artificial projection arithmetic only; no dataset, controller or media reads."""
import copy
import hashlib
import json

import pytest

from amidst.evaluation.case2_tracking_eval import EvaluationError, FORMAT, METRICS, score


def encode(doc):
    return json.dumps(doc, sort_keys=True, allow_nan=False).encode()


def projection(role):
    common = dict(format=FORMAT, role=role, data_origin="SYNTHETIC", evaluation_eligible=False,
                  authoring_ref="synthetic-independent-" + role, source_id="synthetic-source",
                  run_id="synthetic-run", clock_id="synthetic-source-clock",
                  sample_set_sha256=hashlib.sha256(b"independent-sample-plan").hexdigest())
    landing = dict(frame_id="synthetic-floor", unit="m", coordinate_authority_ref="synthetic-calibration",
                   position=[3.0, 4.0], source_time_us=3_000_000)
    row = dict(sample_id="sample-a", status="OBSERVED", action="SWITCH", camera_id="synthetic-b",
               lost_onset_us=2_000_000, landing=landing)
    if role == "reference":
        row.update(decision_window_us=[1_000_000, 2_000_000], entry_window_us=[1_200_000, 2_000_000])
    else:
        row.update(decision_time_us=1_200_000, entry_time_us=1_400_000)
    return dict(common, samples=[row])


def evaluate(p=None, r=None):
    # Two authored fixtures: no reference is copied from prediction.
    pb = encode(projection("prediction") if p is None else p)
    rb = encode(projection("reference") if r is None else r)
    return score(pb, rb, expected_prediction_sha256=hashlib.sha256(pb).hexdigest(),
                 expected_reference_sha256=hashlib.sha256(rb).hexdigest())


def test_perfect_has_known_zero_errors_but_is_proposed_and_not_real():
    result = evaluate()
    assert result["summary"]["switch_consistency"]["rate_pct"] == 100
    row = result["samples"][0]
    assert row["switch_latency_ms"]["value"] == 200
    assert row["lost_onset_error_ms"]["value"] == 0
    assert row["landing_error_m"]["value"] == 0
    assert result["eq14_status"] == "UNRESOLVED"
    assert result["definition_status"] == "PROPOSED"
    assert result["real_data_status"] == result["production_adapter"] == "NOT_RUN"
    assert result["evaluation_eligible"] is result["independence_verified"] is False
    assert result == evaluate()


def test_known_errors_are_measured_not_unknown():
    p = projection("prediction")
    p["samples"][0].update(camera_id="synthetic-wrong", lost_onset_us=2_350_000)
    p["samples"][0]["landing"]["position"] = [0, 0]
    result = evaluate(p)
    assert result["summary"]["switch_consistency"]["rate_pct"] == 0
    row = result["samples"][0]
    assert row["switch_latency_ms"]["value"] == "UNKNOWN"
    assert row["lost_onset_error_ms"]["value"] == 350
    assert row["landing_error_m"]["value"] == 5


@pytest.mark.parametrize("action", ["KEEP", "LOST", "ABSTAIN"])
def test_action_disagreement_remains_known_without_a_switch_camera(action):
    p = projection("prediction")
    p["samples"][0].update(action=action)
    p["samples"][0].pop("camera_id")
    assert evaluate(p)["samples"][0]["switch_consistency"]["value"] is False


@pytest.mark.parametrize("role", ["prediction", "reference"])
@pytest.mark.parametrize("status", ["MISSING", "UNKNOWN"])
def test_explicit_missing_or_unknown_is_never_zero(role, status):
    p, r = projection("prediction"), projection("reference")
    (p if role == "prediction" else r)["samples"][0]["status"] = status
    row = evaluate(p, r)["samples"][0]
    assert all(row[key]["value"] == "UNKNOWN" for key in METRICS)


@pytest.mark.parametrize("field", ["source_id", "run_id", "clock_id", "sample_set_sha256"])
def test_binding_mismatch_excludes_all_metrics(field):
    r = projection("reference")
    r[field] = "0" * 64 if field.endswith("sha256") else "different"
    result = evaluate(r=r)
    assert result["binding_mismatches"] == [field]
    assert all(result["samples"][0][key]["value"] == "UNKNOWN" for key in METRICS)
    assert result["summary"]["switch_consistency"]["rate_pct"] == "UNKNOWN"


@pytest.mark.parametrize("role", ["prediction", "reference"])
def test_unmatched_sample_is_explicit_unknown(role):
    p, r = projection("prediction"), projection("reference")
    (p if role == "prediction" else r)["samples"] = []
    result = evaluate(p, r)
    assert len(result["samples"]) == 1
    assert all(result["samples"][0][key]["value"] == "UNKNOWN" for key in METRICS)


def test_empty_denominator_is_unknown():
    p, r = projection("prediction"), projection("reference")
    p["samples"], r["samples"] = [], []
    summary = evaluate(p, r)["summary"]
    assert summary["switch_consistency"] == dict(n_valid=0, n_unknown=0, n_agreed=0,
                                                 n_disagreed=0, rate_pct="UNKNOWN")
    assert all(summary[key]["median"] == "UNKNOWN" for key in METRICS[1:])


@pytest.mark.parametrize("field,value", [("frame_id", "other"), ("unit", "cm"),
                                       ("coordinate_authority_ref", "other"),
                                       ("source_time_us", 3_000_001), ("position", None)])
def test_landing_requires_coordinate_and_time_authority(field, value):
    p = projection("prediction")
    p["samples"][0]["landing"][field] = value
    row = evaluate(p)["samples"][0]
    assert row["landing_error_m"]["value"] == "UNKNOWN"
    assert row["switch_consistency"]["value"] is True


@pytest.mark.parametrize("field", ["lost_onset_us", "landing", "camera_id", "decision_time_us"])
def test_missing_metric_fields_are_not_defaulted(field):
    p = projection("prediction")
    p["samples"][0].pop(field)
    row = evaluate(p)["samples"][0]
    metric = {"lost_onset_us": "lost_onset_error_ms", "landing": "landing_error_m"}.get(field, "switch_consistency")
    assert row[metric]["value"] == "UNKNOWN"


@pytest.mark.parametrize("time_us", [999_999, 2_000_000])
def test_switch_window_is_half_open(time_us):
    p = projection("prediction")
    p["samples"][0]["decision_time_us"] = time_us
    assert evaluate(p)["samples"][0]["switch_consistency"]["value"] is False


def test_untrusted_hash_rejected_before_scoring():
    pb, rb = encode(projection("prediction")), encode(projection("reference"))
    with pytest.raises(EvaluationError, match="pin mismatch"):
        score(pb, rb, expected_prediction_sha256="0" * 64,
              expected_reference_sha256=hashlib.sha256(rb).hexdigest())


@pytest.mark.parametrize("mutation", ["eligible", "origin", "same-author", "duplicate-sample", "extra-field"])
def test_projection_contract_cannot_promote_or_smuggle_inputs(mutation):
    p, r = projection("prediction"), projection("reference")
    if mutation == "eligible":
        p["evaluation_eligible"] = True
    elif mutation == "origin":
        p["data_origin"] = "REAL_DATA"
    elif mutation == "same-author":
        r["authoring_ref"] = p["authoring_ref"]
    elif mutation == "duplicate-sample":
        r["samples"].append(copy.deepcopy(r["samples"][0]))
    else:
        r["unexpected_asset_ref"] = "not-read"
    with pytest.raises(EvaluationError):
        evaluate(p, r)


def test_independent_human_declaration_remains_unverified_and_real_not_run():
    r = projection("reference")
    r["data_origin"] = "INDEPENDENT_HUMAN"
    result = evaluate(r=r)
    assert result["reference_origin"] == "INDEPENDENT_HUMAN"
    assert result["independence_verified"] is False
    assert result["real_data_status"] == "NOT_RUN"
