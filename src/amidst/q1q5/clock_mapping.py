"""Declared demo clocks, exact microseconds and bounded query coverage (#86 §3).

This module accepts in-memory declarations only: no file access, media, inference,
system clock or model calls. ``TimeResolution.status`` describes time coverage,
not whether the caller's detection index, graph or parameters are ready.

Time literals support offset ISO datetimes, 24-hour HH:MM[:SS[.ffffff]], and
Chinese 點/時 expressions (including 半), with explicit 上午/下午. An end time
may inherit an explicitly stated 上午/下午 from the start, as in §3.2. Other
natural language belongs to Q3; unsupported/ambiguous input fails closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, tzinfo
from types import MappingProxyType
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_SECOND_US = 1_000_000
_DAY_US = 86_400 * _SECOND_US
_ISO = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})"
)
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?")
_NUM = r"[0-9零〇一二兩三四五六七八九十]+"
_ZH_TIME = re.compile(rf"({_NUM})[點点時时](?:(半)|({_NUM})分?)?(?:({_NUM})秒)?")
_STR_FIELDS = (
    "run_id", "clock_id", "timezone", "wall_origin", "mapping_version",
    "declaration_source", "declared_by", "declared_at",
)
_FIELDS = frozenset((*_STR_FIELDS, "schema_version", "mapping_kind", "t0_us",
                     "rate", "source_duration_us", "content_sha256"))


class ClockMappingError(ValueError):
    """A fail-closed domain error; HTTP adapters decide its wire representation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _invalid(message: str) -> ClockMappingError:
    return ClockMappingError("TIME_EXPRESSION_INVALID", message)


def _epoch_us(value: datetime) -> int:
    delta = _in_zone(value, UTC) - _EPOCH
    return delta.days * _DAY_US + delta.seconds * _SECOND_US + delta.microseconds


def _in_zone(value: datetime, zone: tzinfo) -> datetime:
    try:
        return value.astimezone(zone)
    except (OverflowError, ValueError) as exc:
        raise _invalid("Time is outside the supported calendar") from exc


def _iso(value: object) -> datetime:
    # datetime.fromisoformat alone silently truncates precision beyond µs.
    if not isinstance(value, str) or not _ISO.fullmatch(value):
        raise _invalid("Expected an ISO datetime with an explicit offset and at most six decimals")
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError("missing offset")
        return result
    except ValueError as exc:
        raise _invalid("Invalid offset datetime") from exc


def _wall(us: int, zone: ZoneInfo) -> str:
    try:
        return (_EPOCH + timedelta(microseconds=us)).astimezone(zone).isoformat()
    except (OverflowError, ValueError) as exc:
        raise _invalid("Time is outside the supported calendar") from exc


def _integer(value: object, name: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        bound = f" >= {minimum}" if minimum is not None else ""
        raise ClockMappingError("DataIntegrityError", f"{name} must be an integer{bound}")
    return value


def _content_hash(document: Mapping[str, object]) -> str:
    body = {key: value for key, value in document.items() if key != "content_sha256"}
    return hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ClockMapping:
    """Validated, immutable q-demo.clock-mapping.v1 declaration, including its hash.

    A content hash proves self-consistency, not approval. The store should pass
    ``expected_sha256``/scope to ``from_document`` when it has trusted pins.
    """

    document: Mapping[str, object]
    _origin_us: int = field(init=False, repr=False)
    _zone: ZoneInfo = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.document, Mapping):
            raise ClockMappingError("CLOCK_MAPPING_MISSING", "No clock mapping declaration")
        doc = dict(self.document)
        if _FIELDS - doc.keys() or any(doc.get(key) in (None, "") for key in _STR_FIELDS):
            raise ClockMappingError("CLOCK_MAPPING_MISSING", "Incomplete clock mapping declaration")
        if doc.keys() - _FIELDS:
            raise ClockMappingError("DataIntegrityError", "Unexpected clock mapping fields")
        if any(not isinstance(doc[key], str) or not doc[key].strip() for key in _STR_FIELDS):
            raise ClockMappingError("DataIntegrityError", "Declaration strings must be nonempty")
        if (doc["schema_version"] != "q-demo.clock-mapping.v1"
                or doc["mapping_kind"] != "DECLARED_DEMO_CLOCK"):
            raise ClockMappingError("DataIntegrityError", "Unsupported clock mapping kind/version")
        if _integer(doc["rate"], "rate") != 1:
            raise ClockMappingError("DataIntegrityError", "Only rate=1 is supported")
        _integer(doc["t0_us"], "t0_us", 0)
        duration = _integer(doc["source_duration_us"], "source_duration_us", 1)
        if cast(int, doc["t0_us"]) >= duration:
            raise ClockMappingError("DataIntegrityError", "t0_us must be inside the source run")
        try:
            zone = ZoneInfo(cast(str, doc["timezone"]))
            origin = _iso(doc["wall_origin"])
            _iso(doc["declared_at"])
            actual = origin.astimezone(zone)
            if (actual.utcoffset() != origin.utcoffset()
                    or actual.replace(tzinfo=None) != origin.replace(tzinfo=None)):
                raise ValueError("Origin offset/local time does not match the IANA timezone")
            origin_us = _epoch_us(origin)
            # Validate both boundaries before exposing a usable mapping.
            _wall(origin_us - cast(int, doc["t0_us"]), zone)
            _wall(origin_us + duration - cast(int, doc["t0_us"]), zone)
        except (ValueError, OverflowError, ZoneInfoNotFoundError) as exc:
            raise ClockMappingError("DataIntegrityError", "Invalid clock timezone/origin") from exc
        digest = doc["content_sha256"]
        if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or digest != _content_hash(doc)):
            raise ClockMappingError("DataIntegrityError", "Clock mapping content hash mismatch")
        object.__setattr__(self, "document", MappingProxyType(doc))
        object.__setattr__(self, "_origin_us", origin_us)
        object.__setattr__(self, "_zone", zone)

    @classmethod
    def from_document(
        cls, document: Mapping[str, object] | None, *, expected_run_id: str | None = None,
        expected_clock_id: str | None = None, expected_sha256: str | None = None,
    ) -> ClockMapping:
        if document is None:
            raise ClockMappingError("CLOCK_MAPPING_MISSING", "No clock mapping declaration")
        result = cls(document)
        for field_name, expected in (("run_id", expected_run_id), ("clock_id", expected_clock_id),
                                     ("content_sha256", expected_sha256)):
            if expected is not None and result.document[field_name] != expected:
                raise ClockMappingError("DataIntegrityError", f"Clock {field_name} pin mismatch")
        return result

    @property
    def run_id(self) -> str:
        return cast(str, self.document["run_id"])

    @property
    def clock_id(self) -> str:
        return cast(str, self.document["clock_id"])

    @property
    def content_sha256(self) -> str:
        return cast(str, self.document["content_sha256"])

    @property
    def duration_us(self) -> int:
        return cast(int, self.document["source_duration_us"])

    def source_to_wall(self, source_us: int) -> str:
        """Map an integer boundary, including duration; this does not select a frame."""
        _integer(source_us, "source_us")
        return _wall(self._origin_us + source_us - cast(int, self.document["t0_us"]), self._zone)

    def wall_to_source(self, wall_time: str) -> int:
        """Convert without clipping; callers resolve a query against [0, duration)."""
        return _epoch_us(_iso(wall_time)) - self._origin_us + cast(int, self.document["t0_us"])


def _local_time(naive: datetime, zone: ZoneInfo) -> datetime:
    # A local time may not exist (spring jump), or denote two instants (fall fold).
    candidates = {}
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold)
        if _in_zone(_in_zone(candidate, UTC), zone).replace(tzinfo=None) == naive:
            candidates[_epoch_us(candidate)] = candidate
    if len(candidates) != 1:
        raise _invalid("Nonexistent or ambiguous local time; provide an explicit offset")
    return next(iter(candidates.values()))


def _number(text: str) -> int:
    if text.isascii() and text.isdecimal():
        return int(text)
    digits = {c: i for i, c in enumerate("零一二三四五六七八九")}
    digits.update({"〇": 0, "兩": 2})
    if text in digits:
        return digits[text]
    if re.fullmatch(r"[一二兩三四五]?十[一二三四五六七八九]?", text):
        tens, units = text.split("十")
        return digits.get(tens, 1) * 10 + digits.get(units, 0)
    raise _invalid("Unsupported number in time literal")


def _literal(
    text: str, day: date, zone: ZoneInfo, inherited_period: str | None = None,
) -> tuple[datetime, str | None]:
    if not isinstance(text, str) or not text.strip():
        raise _invalid("Both time boundaries are required")
    text = text.strip()
    if _ISO.fullmatch(text):
        return _iso(text), None
    text = re.sub(r"\s+", "", text)
    period = next((p for p in ("上午", "下午") if text.startswith(p)), None)
    if period:
        text = text[len(period):]
    if match := _TIME.fullmatch(text):
        hour, minute = int(match[1]), int(match[2])
        second = int(match[3] or 0)
        microsecond = int((match[4] or "").ljust(6, "0") or 0)
    elif match := _ZH_TIME.fullmatch(text):
        hour = _number(match[1])
        if 1 <= hour <= 12 and not (period or inherited_period):
            raise _invalid("Chinese twelve-hour literals require 上午/下午")
        minute = 30 if match[2] else _number(match[3]) if match[3] else 0
        second, microsecond = _number(match[4]) if match[4] else 0, 0
    else:
        raise _invalid("Unsupported time literal")
    if period and not 1 <= hour <= 12:
        raise _invalid("上午/下午 requires an hour from 1 to 12")
    used_period = period or (inherited_period if 1 <= hour <= 12 else None)
    if used_period:
        hour = hour % 12 + (12 if used_period == "下午" else 0)
    try:
        local = datetime(day.year, day.month, day.day, hour, minute, second, microsecond)
    except ValueError as exc:
        raise _invalid("Invalid clock time") from exc
    return _local_time(local, zone), period


def _ordered_wall_range(start: str, end: str) -> tuple[datetime, datetime]:
    first, last = _iso(start), _iso(end)
    if first.date() != last.date() or _epoch_us(last) <= _epoch_us(first):
        raise _invalid("A range must increase within one declared date; no midnight rollover")
    return first, last


def parse_wall_range(
    mapping: ClockMapping | None, start_literal: str, end_literal: str,
    *, date_literal: str | None = None,
) -> tuple[str, str]:
    """Resolve literal defaults from the selected run, never from today's date.

    Date literals, when supplied, are YYYY-MM-DD. Explicit offset datetimes may
    resolve a DST fold. Mixed full datetimes/time-only boundaries use that full
    datetime's date, unless an explicit date was supplied (which must agree).
    """
    if mapping is None:
        raise ClockMappingError("CLOCK_MAPPING_MISSING", "Select a declared clock mapping")
    try:
        day = date.fromisoformat(date_literal) if date_literal is not None else None
    except (ValueError, TypeError) as exc:
        raise _invalid("Date must be YYYY-MM-DD") from exc
    if date_literal is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_literal):
        raise _invalid("Date must be YYYY-MM-DD")
    explicit_days = []
    for value in (start_literal, end_literal):
        if isinstance(value, str) and _ISO.fullmatch(value.strip()):
            explicit_days.append(_in_zone(_iso(value.strip()), mapping._zone).date())
    if explicit_days:
        if len(set(explicit_days)) != 1 or (day is not None and day != explicit_days[0]):
            raise _invalid("Conflicting dates or midnight rollover")
        day = explicit_days[0]
    if day is None:
        day = _iso(mapping.document["wall_origin"]).astimezone(mapping._zone).date()
    first, period = _literal(start_literal, day, mapping._zone)
    last, _ = _literal(end_literal, day, mapping._zone, period)
    first = _in_zone(first, mapping._zone)
    last = _in_zone(last, mapping._zone)
    _ordered_wall_range(first.isoformat(), last.isoformat())
    return first.isoformat(), last.isoformat()


@dataclass(frozen=True, slots=True)
class RunTimeRange:
    run_id: str
    range_us: tuple[int, int]


@dataclass(frozen=True, slots=True)
class TimeResolution:
    """Internal shared result; endpoint adapters add their own readiness gates.

    Per-run clock refs remain separate. This does not invent the unresolved
    multi-run wire representation for clock_mapping_sha256 (#127 U20).
    """

    status: str
    reason: str | None
    requested_time: Mapping[str, object]
    ranges: tuple[RunTimeRange, ...]
    uncovered_wall_ranges: tuple[tuple[str, str], ...]
    clock_refs: tuple[tuple[str, str, str], ...]

    @property
    def coverage_complete(self) -> bool:
        return not self.uncovered_wall_ranges

    def to_scope(self) -> dict[str, object]:
        requested = dict(self.requested_time)
        for key in ("wall_range", "range_us"):
            if key in requested:
                requested[key] = list(cast(tuple, requested[key]))
        return {
            "requested_time": requested,
            "resolved_source_ranges_us": [
                {"run_id": item.run_id, "range_us": list(item.range_us)} for item in self.ranges
            ],
            "time_coverage": {
                "coverage_complete": self.coverage_complete,
                "uncovered_wall_ranges": [list(pair) for pair in self.uncovered_wall_ranges],
            },
        }


def resolve_wall_range(
    mappings: Sequence[ClockMapping], start_wall: str, end_wall: str,
) -> TimeResolution:
    """Intersect with each run independently; union coverage without joining identities."""
    _ordered_wall_range(start_wall, end_wall)
    return _resolve_wall_instants(mappings, start_wall, end_wall)


def _resolve_wall_instants(
    mappings: Sequence[ClockMapping], start_wall: str, end_wall: str,
) -> TimeResolution:
    if not mappings:
        raise ClockMappingError("CLOCK_MAPPING_MISSING", "No selected run clock mappings")
    if any(not isinstance(mapping, ClockMapping) for mapping in mappings):
        raise ClockMappingError("CLOCK_MAPPING_MISSING", "A selected run has no clock mapping")
    first, last = _iso(start_wall), _iso(end_wall)
    if len({m.run_id for m in mappings}) != len(mappings):
        raise ClockMappingError("DataIntegrityError", "Each run must have exactly one mapping")
    start_us, end_us = _epoch_us(first), _epoch_us(last)
    ranges, covered, refs = [], [], []
    for mapping in sorted(mappings, key=lambda m: m.run_id):
        run_start = mapping._origin_us - cast(int, mapping.document["t0_us"])
        left, right = max(start_us, run_start), min(end_us, run_start + mapping.duration_us)
        refs.append((mapping.run_id, mapping.clock_id, mapping.content_sha256))
        if left < right:
            ranges.append(RunTimeRange(mapping.run_id, (left - run_start, right - run_start)))
            covered.append((left, right))
    cursor, uncovered = start_us, []
    for left, right in sorted(covered):
        if cursor < left:
            uncovered.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end_us:
        uncovered.append((cursor, end_us))
    status = "OUT_OF_RANGE" if not ranges else "PARTIAL" if uncovered else "READY"
    display_zone = min(mappings, key=lambda mapping: mapping.run_id)._zone
    return TimeResolution(
        status, "TIME_SCOPE_PARTIAL" if status == "PARTIAL" else None,
        MappingProxyType({"kind": "WALL", "wall_range": (start_wall, end_wall)}),
        tuple(ranges), tuple((_wall(a, display_zone), _wall(b, display_zone))
                             for a, b in uncovered), tuple(refs),
    )


def resolve_source_range(mapping: ClockMapping, start_us: int, end_us: int) -> TimeResolution:
    """Resolve a source-clock query with the same half-open clipping semantics."""
    if type(start_us) is not int or type(end_us) is not int or not 0 <= start_us < end_us:
        raise _invalid("Source range requires increasing nonnegative integer microseconds")
    # §3.2 rejects midnight rollover in wall input; an explicit SOURCE interval
    # can legitimately span midnight in the declared display clock.
    result = _resolve_wall_instants(
        [mapping], mapping.source_to_wall(start_us), mapping.source_to_wall(end_us),
    )
    return TimeResolution(
        result.status, result.reason,
        MappingProxyType({"kind": "SOURCE", "run_id": mapping.run_id,
                          "range_us": (start_us, end_us)}),
        result.ranges, result.uncovered_wall_ranges, result.clock_refs,
    )
