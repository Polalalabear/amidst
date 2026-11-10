"""SYNTHETIC clock declarations only; no media, models, labels or real run data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from itertools import permutations

import pytest

from amidst.q1q5.clock_mapping import (
    ClockMapping,
    ClockMappingError,
    parse_wall_range,
    resolve_source_range,
    resolve_wall_range,
)


def declaration(**changes):
    doc = {
        "schema_version": "q-demo.clock-mapping.v1",
        "run_id": "SYNTHETIC_A", "clock_id": "SYNTHETIC_CLOCK_A",
        "mapping_kind": "DECLARED_DEMO_CLOCK", "timezone": "Asia/Taipei",
        "wall_origin": "2026-11-01T13:00:00+08:00", "t0_us": 0,
        "mapping_version": "SYNTHETIC-clock-v1", "declaration_source": "SYNTHETIC:config",
        "rate": 1, "source_duration_us": 60_000_000,
        "declared_by": "SYNTHETIC", "declared_at": "2026-10-20T00:00:00Z",
    }
    doc.update(changes)
    doc.pop("content_sha256", None)
    doc["content_sha256"] = hashlib.sha256(json.dumps(
        doc, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True,
    ).encode()).hexdigest()
    return doc


def clock(**changes):
    return ClockMapping.from_document(declaration(**changes))


def assert_code(code, call, *args, **kwargs):
    with pytest.raises(ClockMappingError) as raised:
        call(*args, **kwargs)
    assert raised.value.code == code


def test_declared_clock_is_immutable_and_preserves_scope_and_provenance():
    doc = declaration(declaration_source="SYNTHETIC:宣告")
    mapping = ClockMapping.from_document(
        doc, expected_run_id=doc["run_id"], expected_clock_id=doc["clock_id"],
        expected_sha256=doc["content_sha256"],
    )
    assert mapping.run_id == "SYNTHETIC_A"
    assert mapping.clock_id == "SYNTHETIC_CLOCK_A"
    assert mapping.content_sha256 == doc["content_sha256"]
    assert mapping.document == doc
    doc["wall_origin"] = "2040-01-01T00:00:00Z"
    assert mapping.source_to_wall(0) == "2026-11-01T13:00:00+08:00"
    with pytest.raises(TypeError):
        mapping.document["t0_us"] = 99


@pytest.mark.parametrize("origin", [
    "1960-01-01T00:00:00.123456+00:00", "2500-01-01T00:00:00.123456+00:00",
])
def test_microsecond_round_trip_uses_no_float_even_far_from_epoch(origin):
    mapping = clock(timezone="UTC", wall_origin=origin, t0_us=123456)
    for value in (0, 1, 123455, 123456, 123457, 59_999_999, 60_000_000):
        assert mapping.wall_to_source(mapping.source_to_wall(value)) == value
    assert mapping.wall_to_source(origin) == 123456


def test_equivalent_offset_wall_times_have_the_same_source_time():
    mapping = clock(t0_us=500000)
    assert mapping.wall_to_source("2026-11-01T05:00:00.000001Z") == 500001
    assert mapping.wall_to_source("2026-11-01T14:00:00.000001+09:00") == 500001


@pytest.mark.parametrize("missing", [None, "timezone", "wall_origin", "declaration_source"])
def test_incomplete_mapping_never_uses_system_defaults(missing):
    doc = declaration()
    if missing is None:
        doc = None
    else:
        doc.pop(missing)
    assert_code("CLOCK_MAPPING_MISSING", ClockMapping.from_document, doc)


@pytest.mark.parametrize("change", [
    {"timezone": "Not/A_Zone"}, {"timezone": "../UTC"},
    {"wall_origin": "2026-11-01T13:00:00"},
    {"wall_origin": "2026-11-01T13:00:00+09:00"},
    {"wall_origin": "2026-11-01T13:00:00.1234567+08:00"},
    {"rate": 2}, {"rate": True}, {"rate": 1.0},
    {"t0_us": -1}, {"t0_us": 0.0}, {"t0_us": False},
    {"t0_us": 60_000_000}, {"t0_us": 60_000_001},
    {"source_duration_us": 0}, {"source_duration_us": -1},
    {"source_duration_us": True}, {"source_duration_us": 60.0},
    {"mapping_kind": "OBSERVED_CLOCK"}, {"schema_version": "wrong"},
    {"declared_at": "2026-10-20"}, {"run_id": "   "},
    {"unexpected": "SYNTHETIC"},
])
def test_invalid_mapping_fails_closed(change):
    assert_code("DataIntegrityError", ClockMapping.from_document, declaration(**change))


def test_corrupted_mapping_and_external_pin_mismatches_are_integrity_errors():
    doc = declaration()
    doc["source_duration_us"] += 1
    assert_code("DataIntegrityError", ClockMapping.from_document, doc)
    for kwargs in ({"expected_run_id": "OTHER"}, {"expected_clock_id": "OTHER"},
                   {"expected_sha256": "0" * 64}):
        assert_code("DataIntegrityError", ClockMapping.from_document, declaration(), **kwargs)


@pytest.mark.parametrize("start,end,want_start,want_end", [
    ("下午 1 點", "1:30", "13:00:00", "13:30:00"),
    ("下午一點", "一點半", "13:00:00", "13:30:00"),
    ("下午1:00", "13:30", "13:00:00", "13:30:00"),
    ("13:00", "13:30", "13:00:00", "13:30:00"),
    ("十三時五分", "十三時六分", "13:05:00", "13:06:00"),
    ("上午十二點", "上午一點", "00:00:00", "01:00:00"),
    ("下午十二點", "下午一點", "12:00:00", "13:00:00"),
    ("13:00:00.000001", "13:00:00.000002", "13:00:00.000001", "13:00:00.000002"),
])
def test_literal_date_and_timezone_come_from_selected_run(start, end, want_start, want_end):
    first, last = parse_wall_range(clock(), start, end)
    assert first == f"2026-11-01T{want_start}+08:00"
    assert last == f"2026-11-01T{want_end}+08:00"


def test_explicit_date_and_full_iso_boundaries_are_preserved_in_normalized_request():
    mapping = clock()
    first, last = parse_wall_range(mapping, "13:00", "13:01", date_literal="2027-02-03")
    assert first == "2027-02-03T13:00:00+08:00"
    assert last == "2027-02-03T13:01:00+08:00"
    full = parse_wall_range(
        mapping, "2027-02-03 05:00:00Z", "2027-02-03T05:01:00Z",
    )
    assert full == (first, last)
    result = resolve_wall_range([mapping], first, last)
    assert result.to_scope()["requested_time"] == {"kind": "WALL", "wall_range": [first, last]}


@pytest.mark.parametrize("start,end,date_literal", [
    ("13:00", "", None), ("", "13:00", None), ("13:00", "13:00", None),
    ("13:00", "12:59", None), ("23:00", "01:00", None),
    ("25:00", "26:00", None), ("13:60", "14:00", None),
    ("13:00:60", "14:00", None), ("13:00:00.1234567", "14:00", None),
    ("下午十三點", "下午十四點", None), ("剛剛", "現在", None),
    ("一點", "一點半", None),
    ("13:00", "13:30", "今天"), ("13:00", "13:30", "2026-02-30"),
    ("2026-11-01T23:00:00+08:00", "2026-11-02T01:00:00+08:00", None),
    ("2026-11-02T13:00:00+08:00", "13:30", "2026-11-01"),
    ("9999-12-31T23:59:58Z", "9999-12-31T23:59:59Z", None),
    ("0001-01-01T00:00:00+14:00", "0001-01-01T00:01:00+14:00", None),
])
def test_invalid_or_ambiguous_wall_input_is_not_guessed(start, end, date_literal):
    assert_code("TIME_EXPRESSION_INVALID", parse_wall_range,
                clock(), start, end, date_literal=date_literal)


def test_missing_selected_mapping_has_a_distinct_error_code():
    assert_code("CLOCK_MAPPING_MISSING", parse_wall_range, None, "13:00", "13:30")
    assert_code("CLOCK_MAPPING_MISSING", resolve_wall_range, [],
                "2026-11-01T13:00:00+08:00", "2026-11-01T13:30:00+08:00")


def test_dst_nonexistent_origin_is_rejected_and_explicit_fold_origins_are_distinct():
    assert_code("DataIntegrityError", clock, timezone="America/New_York",
                wall_origin="2026-03-08T02:30:00-05:00")
    first = clock(timezone="America/New_York", wall_origin="2026-11-01T01:30:00-04:00")
    second = clock(timezone="America/New_York", wall_origin="2026-11-01T01:30:00-05:00")
    assert first.content_sha256 != second.content_sha256
    assert first.wall_to_source(second.source_to_wall(0)) == 3_600_000_000


@pytest.mark.parametrize("day,start,end", [
    ("2026-03-08", "02:10", "03:10"),
    ("2026-11-01", "01:10", "02:10"),
])
def test_dst_gap_and_ambiguous_time_only_literals_require_explicit_offsets(day, start, end):
    mapping = clock(timezone="America/New_York", wall_origin="2026-01-01T12:00:00-05:00")
    assert_code("TIME_EXPRESSION_INVALID", parse_wall_range, mapping, start, end,
                date_literal=day)


def test_explicit_dst_fold_range_uses_instant_order_not_naive_wall_order():
    mapping = clock(timezone="America/New_York", wall_origin="2026-11-01T00:00:00-04:00",
                    source_duration_us=14_400_000_000)
    start, end = parse_wall_range(
        mapping, "2026-11-01T01:10:00-04:00", "2026-11-01T01:05:00-05:00",
    )
    result = resolve_wall_range([mapping], start, end)
    assert result.ranges[0].range_us == (4_200_000_000, 7_500_000_000)


def test_full_partial_and_no_coverage_are_half_open_and_do_not_claim_no_match():
    mapping = clock()
    full = resolve_source_range(mapping, 0, 60_000_000)
    assert full.status == "READY" and full.coverage_complete and full.reason is None
    assert full.ranges[0].range_us == (0, 60_000_000)
    partial = resolve_wall_range([mapping], *parse_wall_range(mapping, "下午1點", "1:30"))
    assert partial.status == "PARTIAL" and partial.reason == "TIME_SCOPE_PARTIAL"
    assert partial.ranges[0].range_us == (0, 60_000_000)
    assert partial.uncovered_wall_ranges == ((
        "2026-11-01T13:01:00+08:00", "2026-11-01T13:30:00+08:00",
    ),)
    outside = resolve_source_range(mapping, 60_000_000, 60_000_001)
    assert outside.status == "OUT_OF_RANGE" and not outside.coverage_complete
    assert not outside.ranges  # duration itself is not an observable sample
    assert outside.to_scope()["time_coverage"]["uncovered_wall_ranges"] == [[
        "2026-11-01T13:01:00+08:00", "2026-11-01T13:01:00.000001+08:00",
    ]]


def test_query_before_and_after_run_reports_both_uncovered_edges():
    result = resolve_wall_range(
        [clock()], "2026-11-01T12:59:59.999999+08:00", "2026-11-01T13:01:00.000001+08:00",
    )
    assert result.ranges[0].range_us == (0, 60_000_000)
    assert result.uncovered_wall_ranges == (
        ("2026-11-01T12:59:59.999999+08:00", "2026-11-01T13:00:00+08:00"),
        ("2026-11-01T13:01:00+08:00", "2026-11-01T13:01:00.000001+08:00"),
    )


def test_multi_run_coverage_unions_ranges_but_keeps_run_clocks_and_pins_separate():
    runs = [
        clock(source_duration_us=10_000_000),
        clock(run_id="SYNTHETIC_B", clock_id="CLOCK_B", timezone="UTC",
              wall_origin="2026-11-01T05:00:05Z", source_duration_us=10_000_000),
        clock(run_id="SYNTHETIC_C", clock_id="CLOCK_C",
              wall_origin="2026-11-01T13:00:20+08:00", source_duration_us=10_000_000),
    ]
    outcomes = [resolve_wall_range(
        order, "2026-11-01T13:00:00+08:00", "2026-11-01T13:00:30+08:00",
    ) for order in permutations(runs)]
    assert all(result == outcomes[0] for result in outcomes)
    result = outcomes[0]
    assert [item.run_id for item in result.ranges] == [run.run_id for run in runs]
    assert [item.range_us for item in result.ranges] == [(0, 10_000_000)] * 3
    assert result.uncovered_wall_ranges == ((
        "2026-11-01T13:00:15+08:00", "2026-11-01T13:00:20+08:00",
    ),)
    assert result.clock_refs == tuple(
        (run.run_id, run.clock_id, run.content_sha256) for run in runs
    )


def test_touching_run_boundaries_have_no_spurious_gap():
    a = clock(source_duration_us=10_000_000)
    b = clock(run_id="SYNTHETIC_B", clock_id="CLOCK_B",
              wall_origin="2026-11-01T13:00:10+08:00", source_duration_us=10_000_000)
    result = resolve_wall_range([a, b], "2026-11-01T13:00:00+08:00",
                                "2026-11-01T13:00:20+08:00")
    assert result.coverage_complete and result.status == "READY"


def test_duplicate_run_mapping_is_an_integrity_error_not_merged():
    a = clock()
    assert_code("DataIntegrityError", resolve_wall_range, [a, a],
                "2026-11-01T13:00:00+08:00", "2026-11-01T13:01:00+08:00")


@pytest.mark.parametrize("start,end", [(0, 0), (10, 9), (-1, 10), (False, 10), (0, 1.0)])
def test_source_ranges_require_integer_increasing_nonnegative_boundaries(start, end):
    assert_code("TIME_EXPRESSION_INVALID", resolve_source_range, clock(), start, end)


def test_source_query_can_span_midnight_without_inventing_wall_literal_rollover():
    mapping = clock(wall_origin="2026-11-01T23:59:50+08:00")
    result = resolve_source_range(mapping, 0, 20_000_000)
    assert result.coverage_complete
    assert result.ranges[0].range_us == (0, 20_000_000)
    assert_code("TIME_EXPRESSION_INVALID", resolve_wall_range, [mapping],
                "2026-11-01T23:59:50+08:00", "2026-11-02T00:00:10+08:00")


def test_serialization_does_not_expose_mutable_internal_request_or_clip_requested_range():
    result = resolve_source_range(clock(), 0, 120_000_000)
    scope = result.to_scope()
    assert scope["requested_time"]["range_us"] == [0, 120_000_000]
    assert scope["resolved_source_ranges_us"][0]["range_us"] == [0, 60_000_000]
    scope["requested_time"]["range_us"][0] = 100
    assert result.to_scope()["requested_time"]["range_us"] == [0, 120_000_000]


def test_declared_offset_uses_historical_zone_rules_not_current_date():
    winter = clock(timezone="Europe/Berlin", wall_origin="2026-01-01T12:00:00+01:00")
    summer = clock(timezone="Europe/Berlin", wall_origin="2026-07-01T12:00:00+02:00")
    assert datetime.fromisoformat(winter.source_to_wall(0)).utcoffset().total_seconds() == 3600
    assert datetime.fromisoformat(summer.source_to_wall(0)).utcoffset().total_seconds() == 7200
