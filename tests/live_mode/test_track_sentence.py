"""The live sentence interface delegates to Q3 and exposes only a parse receipt."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amidst.live_mode.candidates import TrackRequestError
from amidst.live_mode.track_sentence import TrackSentenceParser
from amidst.q1q5.api_budget import ApiGuard, GuardConfig, GuardedNlClient
from amidst.q1q5.nl_query_parse import ClientResult, NlClientError


@pytest.mark.parametrize(("sentence", "color"), [
    ("追蹤紅衣的人", "red"),
    ("追蹤藍衣的人", "blue"),
    ("請追蹤 red person", "red"),
])
def test_recognizes_q3_colors(sentence, color):
    assert TrackSentenceParser().parse(None, sentence, "off") == (
        color, {"parser": "RULES", "ignored": [], "unrecognized_count": 0},
    )


def test_chip_overrides_both_colors_and_reports_ignored_fields_without_text():
    color, receipt = TrackSentenceParser().parse(
        "blue", "查找 在秘密倉庫 的 紅衣或藍衣 0:01 到 0:20", "off"
    )
    assert color == "blue"
    assert receipt["note"] == "CHIP_OVERRIDES_SENTENCE"
    assert receipt["ignored"] == ["action", "location", "time"]
    assert receipt["unrecognized_count"] > 0
    assert set(receipt) == {"parser", "note", "ignored", "unrecognized_count"}


@pytest.mark.parametrize(("sentence", "error"), [
    ("紅衣 或 藍衣", "FEATURE_AMBIGUOUS"),
    ("黑衣", "FEATURE_REQUIRED"),
    (None, "FEATURE_REQUIRED"),
])
def test_no_color_or_ambiguous_color_requires_a_chip(sentence, error):
    with pytest.raises(TrackRequestError) as exc:
        TrackSentenceParser().parse(None, sentence, "off")
    assert exc.value.status == 400 and exc.value.response == {"error": error}


@pytest.mark.parametrize(("effective", "cfg"), [
    ("off", GuardConfig(enabled=True, max_usd_total=1)),
    ("lead", GuardConfig()),
    ("review", GuardConfig(enabled=True, max_usd_total=0)),
    ("review", None),
])
def test_rules_do_not_construct_clients_when_switch_or_budget_is_off(effective, cfg):
    factory = Mock()
    guard = SimpleNamespace(config=cfg) if cfg is not None else None
    parser = TrackSentenceParser(guard=guard, client_factory=factory)
    assert parser.parse(None, "找紅衣", effective)[1]["parser"] == "RULES"
    factory.assert_not_called()


@pytest.mark.parametrize("expected", ["API", "LOCAL", "RULES"])
def test_only_separately_guarded_api_uses_q3_fallback_chain(tmp_path, expected):
    guard = ApiGuard(GuardConfig(
        enabled=True, max_usd_total=1,
        prices={"fake": {"input_usd_per_mtok": 0, "output_usd_per_mtok": 0}},
    ), usage_dir=tmp_path)
    fake_result = ClientResult({
        "action": "追蹤", "location": [], "target": ["person", "blue"],
        "time": None, "unrecognized": [],
    }, 10, 4, 0.0)
    fake_api = SimpleNamespace(
        model="fake", parse=Mock(return_value=fake_result,
                                 side_effect=None if expected == "API" else NlClientError("UNAVAILABLE")),
    )
    local = SimpleNamespace(
        parse=Mock(return_value=fake_result,
                   side_effect=None if expected == "LOCAL" else NlClientError("UNAVAILABLE"))
    )
    factory = Mock(return_value={"API": GuardedNlClient(fake_api, guard), "LOCAL": local})
    parser = TrackSentenceParser(guard=guard, client_factory=factory)
    color, receipt = parser.parse(None, "追蹤紅衣", "review")
    assert (color, receipt["parser"]) == ("red" if expected == "RULES" else "blue", expected)
    factory.assert_called_once_with(guard=guard)
    fake_api.parse.assert_called_once()
    assert local.parse.call_count == (expected != "API")
