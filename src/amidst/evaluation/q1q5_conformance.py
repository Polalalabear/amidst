# ruff: noqa: E501  (check summaries and contract-gap prose are deliberately single-line strings)
"""Contract-conformance checks for the Q1–Q5 first demo (``docs/contracts/Q1_Q2_FIRST_DEMO_V1.md``).

This module checks only the *contract layer*: schemas, closed lists, shared response fields and
invariants between documents. It deliberately knows nothing about the demo storyline (who appears
on which camera, or when); recognition quality and story correctness are human-review questions.
Thresholds (contract §11) are read from a parameter set and are never hard-coded: a check that needs
an unset parameter reports ``SKIPPED_PARAM_UNSET``, which is not a pass.

Standard library only (plus the ``amidst.contracts.q_demo`` schemas).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from amidst.contracts.q_demo import is_provisional, validate
from amidst.evaluation.response_versions import time_range_source

KIT_VERSION = "0.2.1+response-v2"
CONTRACT = {
    "path": "docs/contracts/Q1_Q2_FIRST_DEMO_V1.md",
    "status": "DRAFT",
    "pr": "Polalalabear/amidst#86",
    "branch": "claude/q1q2-contract-v1",
    "commit": "3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2",
    "file_sha256": "924c4365ab3b3169eb9192296a26eede9d558d885410e7e80197d00a77978078",
}

PASS = "PASS"
FAIL = "FAIL"
SKIPPED_PARAM_UNSET = "SKIPPED_PARAM_UNSET"
SKIPPED_NO_CONTEXT = "SKIPPED_NO_CONTEXT"

# ----------------------------------------------------------------------------- kinds

KIND_BY_SCHEMA = {
    "q-demo.clock-mapping.v1": "clock_mapping",
    "q-demo.detection-index.v1": "detection_index",
    "q-demo.region-graph.v1": "region_graph",
    "q-demo.camera-transition-graph.v1": "camera_graph",
    "q-demo.q1-request.v1": "q1_request",
    "q-demo.q1-response.v1": "q1_response",
    "q-demo.q1-response.v2": "q1_response",
    "q-demo.q3-parse-request.v1": "q3_request",
    "q-demo.q3-llm-output.v1": "q3_llm_output",
    "q-demo.q3-parse-response.v1": "q3_response",
    "q-demo.q3-parse-response.v2": "q3_response",
    "q-demo.explanation.v1": "explanation",
    "q-demo.q2-request.v1": "q2_request",
    "q-demo.q2-response.v1": "q2_response",
    "q-demo.q2-response.v2": "q2_response",
    "q-demo.agent-decision.v1": "agent_decision",
    "q-demo.decision-record.v1": "decision_record",
    "q-demo.candidate-snapshot.v1": "candidate_snapshot",
    "q-demo.candidate-evidence.v1": "candidate_evidence",
    "q-demo.parameter-set.v1": "parameter_set",
    "q1q5-conformance.supported-classes.v1": "supported_classes",
}
SCHEMA_BY_KIND = {
    **{kind: schema for schema, kind in KIND_BY_SCHEMA.items()
       if not (schema.endswith(".v2") and kind in ("q1_response", "q2_response", "q3_response"))},
    "detection_records": "q-demo.detection-record",
    "link_records": "q-demo.link-record",
}
LIST_KINDS = ("detection_records", "link_records")  # files holding one record per line / array item
RESPONSE_KINDS = ("q1_response", "q3_response", "q2_response")
GRAPH_KINDS = ("region_graph", "camera_graph")
CONTENT_HASHED_KINDS = (
    "detection_index",
    "region_graph",
    "camera_graph",
    "clock_mapping",
    "decision_record",
    "parameter_set",
)

STATUS_LISTS = {
    "q1_response": [
        "READY",
        "NO_MATCH",
        "PARTIAL",
        "UNSUPPORTED_CLASS",
        "UNSUPPORTED_CONDITION",
        "OUT_OF_RANGE",
        "UNKNOWN",
    ],
    "q3_response": [
        "PARSED",
        "NEEDS_CLARIFICATION",
        "UNSUPPORTED_CLASS",
        "UNSUPPORTED_CONDITION",
        "PARSE_FAILED",
        "TIME_EXPRESSION_INVALID",
    ],
    "q2_response": ["COMPLETE", "PARTIAL", "NO_SEED", "ENDED_BY_LIMIT", "UNKNOWN"],
}
FALLBACK_REASONS = {
    "ROUND_LIMIT",
    "TIME_BUDGET",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_TIMEOUT",
    "INVALID_RESPONSE",
    "ILLEGAL_CANDIDATE",
    "EXPLANATION_INVALID",
    "MODE_NOT_AUTHORIZED",
}
AGENT_ONLY_REASONS = {"ROUND_LIMIT", "TIME_BUDGET", "ILLEGAL_CANDIDATE"}
Q3_PROVIDER_REASONS = {"PROVIDER_UNAVAILABLE", "PROVIDER_TIMEOUT", "INVALID_RESPONSE"}
PRESENCE_ORDER = ["MATCH_STRONG", "MATCH_WEAK"]  # only these can satisfy a switch guard
TIMING_KEYS = {"latency_ms", "elapsed_ms", "duration_ms", "wall_time_ms", "generated_at"}
ERROR_CODES = {
    "FORBIDDEN_INFERENCE_INPUT": 422,
    "FORBIDDEN_DATA_SCOPE": 403,
    "DataIntegrityError": None,
    "PARAMETER_GRID_MISMATCH": None,  # §8.2: how it is returned (status / reason / HTTP code) is U25
}

FORBIDDEN_KEYS = {
    "ground_truth",
    "gt",
    "gt_trajectory",
    "gt_actor_id",
    "gt_path",
    "actor_id",
    "actor_ids",
    "blender_object",
    "blender_object_name",
    "object_name",
    "persons_sim",
    "event_script",
    "author_route",
    "route_script",
    "depth",
    "depth_map",
    "mask",
    "mask_ref",
    "visibility_map",
    "private_path",
    "local_path",
    "renderer_path",
    "private_evaluation",
}
GRAPH_FORBIDDEN_KEYS = {
    "actual_next_camera",
    "actual_next_region",
    "arrival_time_us",
    "arrival_us",
    "observed_transition",
    "person_id",
    "track_id",
}
FORBIDDEN_TOKEN_RE = re.compile(
    r"persons\.sim|private_evaluation|ground_truth|production_manifest|event_[\w-]+\.validation\.json",
    re.IGNORECASE,
)
GRAPH_INPUT_FORBIDDEN_RE = re.compile(
    r"persons\.sim|\.validation\.json|ground_truth|detidx:|detection[_-]index|(?<![a-z])event_"
    r"|(?<![a-z])(mask|depth)(?![a-z])",
    re.IGNORECASE,
)
ABS_PATH_RE = re.compile(
    r"(^|[\s\"'=(])(/(Users|home|private|var|tmp|etc|opt|mnt|Volumes|root)/|[A-Za-z]:[\\/]|\\\\|file://|~/)"
    r"|^/[A-Za-z0-9_.-]+/|\.\./"
)
IDENTITY_RE = re.compile(
    r"(?<![不非沒无])(同一個人|同一人|same person|is the same (person|individual))", re.IGNORECASE
)

UNKNOWN_CONTRACT_ITEMS: list[dict[str, str]] = []  # filled at the bottom of the file


# ----------------------------------------------------------------------------- documents


@dataclass
class Doc:
    path: str  # relative, never absolute
    kind: str
    data: Any
    file_sha256: str
    stem: str = ""
    role: str = ""

    @property
    def sort_key(self) -> tuple[str, str]:
        return (self.path, self.kind)


class ParamUnset(Exception):
    def __init__(self, names: Iterable[str]) -> None:
        self.names = sorted(set(names))
        super().__init__(", ".join(self.names))


class NoContext(Exception):
    """A document the check needs (a request, a graph, a snapshot…) was not supplied."""


class NotApplicable(Exception):
    """The check does not apply to this particular document; it is left out of the report."""


class Findings:
    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []
        self.notes: list[str] = []

    def add(self, path: str, message: str) -> None:
        self.items.append({"path": path, "message": message})

    def note(self, message: str) -> None:
        if message not in self.notes:
            self.notes.append(message)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
    )


def canonical_sha256(value: Any, exclude: tuple[str, ...] = ()) -> str:
    """Contract §2.1: canonical JSON (sorted keys, compact, no NaN) without the named top-level keys."""

    body = (
        {k: v for k, v in value.items() if k not in exclude} if isinstance(value, dict) else value
    )
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def index_key(manifest: dict[str, Any]) -> str:
    """Contract §2.2 (U21): the detection-index key behind ``index_id`` and every ``observation_id``.

    Canonical hash of the manifest without ``index_id``, ``content_sha256``, ``records_ref``,
    ``records_file_sha256`` (and ``stats``): everything is fixed before the per-frame records are
    written, so the observation ids inside the records can embed it without a cycle.
    """

    return canonical_sha256(
        manifest, ("index_id", "content_sha256", "records_ref", "records_file_sha256", "stats")
    )


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    """Contract §2.2 (U22): ``candidate_snapshot_sha256`` over the snapshot without itself, stats and
    each candidate's ``candidate_ref`` (candidates are identified by ``rank``)."""

    body = {k: v for k, v in snapshot.items() if k not in ("candidate_snapshot_sha256", "stats")}
    body["candidates"] = [
        {k: v for k, v in c.items() if k != "candidate_ref"} for c in snapshot.get("candidates", [])
    ]
    return canonical_sha256(body)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} is not allowed")


def _loads(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_constant)


def classify(path: Path, data: Any) -> str:
    if isinstance(data, dict):
        version = data.get("schema_version")
        if version in KIND_BY_SCHEMA:
            return KIND_BY_SCHEMA[version]
        if path.name.startswith("parameter_set"):
            return "parameter_set"
        if "error_code" in data and version is None:
            return "error_response"
        if version is None and "frame_ref" in data:
            return "detection_records"
        if version is None and "prev_observation_id" in data and "elapsed_us" in data:
            return "link_records"
    if isinstance(data, list) and data:
        if all(isinstance(x, dict) and "frame_ref" in x for x in data):
            return "detection_records"
        if all(isinstance(x, dict) and "prev_observation_id" in x for x in data):
            return "link_records"
    return "unclassified"


def _stem_role(name: str) -> tuple[str, str]:
    base = re.sub(r"\.jsonl?$", "", name)
    stem, dot, role = base.rpartition(".")
    return (stem, role) if dot else (base, "")


def load_directory(root: Path) -> list[Doc]:
    """Load every ``*.json`` / ``*.jsonl`` under ``root`` (no symlinks, no escaping the directory)."""

    root = root.resolve()
    docs: list[Doc] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.name.startswith(".") or path.suffix not in (".json", ".jsonl"):
            continue
        rel = path.relative_to(root).as_posix()
        stem, role = _stem_role(path.name)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            docs.append(
                Doc(
                    rel,
                    "unclassified",
                    {"error": "symlink or path escape rejected"},
                    "",
                    stem,
                    role,
                )
            )
            continue
        digest = file_sha256(path)
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".jsonl":
                records = [_loads(line) for line in text.splitlines() if line.strip()]
            else:
                records = _loads(text)
        except (ValueError, UnicodeDecodeError) as exc:
            docs.append(
                Doc(rel, "unclassified", {"error": f"unreadable JSON: {exc}"}, digest, stem, role)
            )
            continue
        if path.suffix == ".jsonl" or isinstance(records, list):
            items = records if isinstance(records, list) else [records]
            if items and all(
                isinstance(x, dict) and x.get("schema_version") == "q-demo.decision-record.v1"
                for x in items
            ):
                for index, item in enumerate(items):
                    docs.append(
                        Doc(f"{rel}#{index + 1}", "decision_record", item, digest, stem, role)
                    )
                continue
            kind = classify(path, items)
            docs.append(Doc(rel, kind, items, digest, stem, role))
            continue
        docs.append(Doc(rel, classify(path, records), records, digest, stem, role))
    return docs


# ----------------------------------------------------------------------------- context


def _param_is_set(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() in {"", "待約定", "TBD", "UNKNOWN", "PROPOSED"}:
        return False
    return True


def _param_values(params: Any) -> dict[str, Any]:
    """``parameters[]`` of ``q-demo.parameter-set.v1`` (contract §11) as ``{name: value}``."""

    items = params.get("parameters") if isinstance(params, dict) else None
    if not isinstance(items, list):
        return {}
    return {
        item["name"]: item.get("value")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


class Ctx:
    def __init__(self, docs: list[Doc], params: dict[str, Any] | None = None) -> None:
        self.docs = docs
        self.params = params
        self.param_doc = next((d for d in docs if d.kind == "parameter_set"), None)
        if params is None and self.param_doc is not None:
            self.params = self.param_doc.data
        self._by_kind: dict[str, list[Doc]] = {}
        for doc in docs:
            self._by_kind.setdefault(doc.kind, []).append(doc)

    # -- lookup
    def of_kind(self, *kinds: str) -> list[Doc]:
        return [d for kind in kinds for d in self._by_kind.get(kind, [])]

    def sibling(self, doc: Doc, *kinds: str) -> Doc | None:
        for other in self.of_kind(*kinds):
            if (
                other is not doc
                and other.stem == doc.stem
                and Path(other.path).parent == Path(doc.path).parent
            ):
                return other
        return None

    def by_hash(self, kind: str, sha: str | None, field_name: str = "content_sha256") -> Doc | None:
        for other in self.of_kind(kind):
            if isinstance(other.data, dict) and sha and other.data.get(field_name) == sha:
                return other
        return None

    # -- parameters
    def param(self, name: str) -> Any:
        value = _param_values(self.params).get(name)
        if not _param_is_set(value):
            raise ParamUnset([name])
        return value

    def numeric(self, *names: str) -> dict[str, float]:
        missing, out = [], {}
        for name in names:
            try:
                value = self.param(name)
            except ParamUnset:
                missing.append(name)
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                missing.append(name)
            else:
                out[name] = value
        if missing:
            raise ParamUnset(missing)
        return out


# ----------------------------------------------------------------------------- registry


@dataclass(frozen=True)
class Check:
    id: str
    section: str
    kinds: tuple[str, ...]
    summary: str
    fn: Callable[[Doc, Ctx, Findings], None]
    heuristic: bool = False


CHECKS: list[Check] = []


def check(
    id: str, section: str, kinds: tuple[str, ...] | str, summary: str, heuristic: bool = False
):
    kinds_t = ("*",) if kinds == "*" else (kinds,) if isinstance(kinds, str) else tuple(kinds)

    def wrap(fn: Callable[[Doc, Ctx, Findings], None]):
        CHECKS.append(Check(id, section, kinds_t, summary, fn, heuristic))
        return fn

    return wrap


# ----------------------------------------------------------------------------- helpers


def walk(value: Any, path: str = "$") -> Iterator[tuple[str, str, Any]]:
    """Yield ``(path, 'key'|'value', item)`` for every dict key and string value."""

    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", "key", key
            yield from walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, "value", value


def strings(value: Any) -> set[str]:
    return {item for _, kind, item in walk(value) if kind == "value"}


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def epoch_us(text: str) -> int:
    """ISO 8601 with UTC offset -> integer microseconds since the Unix epoch."""

    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("timestamp has no UTC offset")
    return (moment - _EPOCH) // timedelta(microseconds=1)


def valid_range(r: Any) -> bool:
    return (
        isinstance(r, list)
        and len(r) == 2
        and all(isinstance(x, int) and not isinstance(x, bool) for x in r)
        and r[0] < r[1]
    )


def ranges_sorted_disjoint(ranges: list[Any]) -> str | None:
    last_end = None
    for index, r in enumerate(ranges):
        if not valid_range(r):
            return f"range {index} is not a half-open [start, end) with start < end"
        if last_end is not None and r[0] < last_end:
            return f"range {index} overlaps or is out of order"
        last_end = r[1]
    return None


def subtract_intervals(base: tuple[int, int], cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out, cursor = [], base[0]
    for start, end in sorted(cuts):
        if end <= cursor:
            continue
        if start >= base[1]:
            break
        if start > cursor:
            out.append((cursor, min(start, base[1])))
        cursor = max(cursor, end)
    if cursor < base[1]:
        out.append((cursor, base[1]))
    return out


def ok_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# ----------------------------------------------------------------------------- generic checks


@check(
    "DOCUMENT_LOADABLE",
    "§2.1",
    "*",
    "File parses as JSON (no NaN/Infinity), has a known schema_version, no symlink or path escape",
)
def _document_loadable(doc: Doc, ctx: Ctx, out: Findings) -> None:
    if doc.kind == "unclassified":
        detail = doc.data.get("error") if isinstance(doc.data, dict) else None
        out.add(
            "$",
            detail or "document has no recognised schema_version (see contract §2.2 for naming)",
        )


@check(
    "SCHEMA_VALID",
    "§2–§8 (per kind)",
    "*",
    "Document validates against its JSON Schema (closed lists, required keys, no extra keys)",
)
def _schema_valid(doc: Doc, ctx: Ctx, out: Findings) -> None:
    if doc.kind in ("unclassified", "error_response"):
        raise NotApplicable("no schema for this kind")
    key = doc.data["schema_version"] if doc.kind in RESPONSE_KINDS else SCHEMA_BY_KIND[doc.kind]
    if is_provisional(key):
        out.note("schema is PROVISIONAL (contract does not define it); see UNKNOWN_CONTRACT items")
    items = doc.data if doc.kind in LIST_KINDS else [doc.data]
    for index, item in enumerate(items[:2000]):
        prefix = f"$[{index}]" if doc.kind in LIST_KINDS else "$"
        for error in validate(item, key):
            out.add(prefix + error.path[1:], error.message)


@check(
    "NO_FORBIDDEN_CONTENT",
    "§2.3, §9, v1.1 §7",
    "*",
    "No local absolute path, GT / private / event-script field or token anywhere in the document",
)
def _no_forbidden_content(doc: Doc, ctx: Ctx, out: Findings) -> None:
    if doc.kind == "unclassified":
        raise NotApplicable("unreadable document")
    for path, kind, item in walk(doc.data):
        if kind == "key" and item.lower() in FORBIDDEN_KEYS:
            out.add(path, f"forbidden field name {item!r}")
        elif kind == "value":
            if ABS_PATH_RE.search(item):
                out.add(path, "looks like a local absolute path or path traversal")
            if FORBIDDEN_TOKEN_RE.search(item):
                out.add(
                    path,
                    "mentions a forbidden source (GT / private evaluation / persons.sim / event validation)",
                )
            if (
                doc.kind in GRAPH_KINDS
                and path.startswith("$.inputs")
                and GRAPH_INPUT_FORBIDDEN_RE.search(item)
            ):
                out.add(path, "graph input references a forbidden source (§5.1)")
    if doc.kind in GRAPH_KINDS:
        for path, kind, item in walk(doc.data):
            if kind == "key" and item in GRAPH_FORBIDDEN_KEYS:
                out.add(
                    path,
                    f"graph must not store a person's actual route or arrival ({item!r}, §5.1)",
                )


@check(
    "CONTENT_HASH_RECOMPUTE",
    "§2.1, §2.3, §3.1, §4.2, §5.2–§5.3, §8.7",
    CONTENT_HASHED_KINDS,
    "content_sha256 equals the canonical hash of the document without itself, stats and its self-derived id (index_id / graph_id / parameter_set_id), §2.2 preimage",
)
def _content_hash(doc: Doc, ctx: Ctx, out: Findings) -> None:
    data = doc.data
    if not isinstance(data, dict):
        return
    # §2.2: an id that embeds <hash16> cannot be inside the body that produces the hash. The preimage
    # is the document without content_sha256, without its own id field and without stats. For the
    # detection index this is the manifest *with* records_file_sha256 (the index_id segment uses the
    # separate index key instead, see _index_key).
    excluded = ("content_sha256", "stats") + {
        "detection_index": ("index_id",),
        "region_graph": ("graph_id",),
        "camera_graph": ("graph_id",),
        "parameter_set": ("parameter_set_id",),
    }.get(doc.kind, ())
    try:
        actual = canonical_sha256(data, excluded)
    except ValueError as exc:
        out.add("$", f"cannot canonicalise: {exc}")
        return
    if data.get("content_sha256") != actual:
        out.add("$.content_sha256", f"declared {data.get('content_sha256')!r}, recomputed {actual}")


@check(
    "OUTPUT_HASH_RECOMPUTE",
    "§2.1, §2.3, §7.5",
    RESPONSE_KINDS,
    "output_sha256 recomputes without output_sha256 and stats; hashed body has no timing fields or explanation text",
)
def _output_hash(doc: Doc, ctx: Ctx, out: Findings) -> None:
    data = doc.data
    try:
        actual = canonical_sha256(data, ("output_sha256", "stats"))
    except ValueError as exc:
        out.add("$", f"cannot canonicalise: {exc}")
        return
    if data.get("output_sha256") != actual:
        out.add("$.output_sha256", f"declared {data.get('output_sha256')!r}, recomputed {actual}")
    body = {k: v for k, v in data.items() if k not in ("output_sha256", "stats")}
    for path, kind, item in walk(body):
        if kind == "key" and item in TIMING_KEYS:
            out.add(
                path, f"timing field {item!r} must live under stats (it would change output_sha256)"
            )
    for name in ("explanation", "explanation_text"):
        if name in data:
            out.add(f"$.{name}", "explanation text must not be part of the hashed response (§7.5)")


@check(
    "ID_DERIVED_FROM_HASH",
    "§2.2",
    ("detection_index", "region_graph", "camera_graph"),
    "graph_id uses the first 16 hex chars of content_sha256; index_id (and the observation_id segment) uses the first 16 of the index key (manifest without index_id, content_sha256, records_ref, records_file_sha256), §2.2",
)
def _id_derived(doc: Doc, ctx: Ctx, out: Findings) -> None:
    data = doc.data
    id_field = "index_id" if doc.kind == "detection_index" else "graph_id"
    parts = str(data.get(id_field, "")).split(":")
    if len(parts) != 4:
        out.add(f"$.{id_field}", "expected <kind>:<scene_revision>:<run_id or static>:<hash16>")
        return
    if parts[1] != data.get("scene_revision"):
        out.add(f"$.{id_field}", "scene_revision segment differs from scene_revision")
    if doc.kind == "detection_index" and parts[2] != data.get("run_id"):
        out.add(f"$.{id_field}", "run_id segment differs from run_id")
    if doc.kind != "detection_index" and parts[2] != "static":
        out.add(f"$.{id_field}", "graph ids use 'static' as the run segment")
    if doc.kind == "detection_index":
        if parts[3] != index_key(data)[:16]:
            out.add(
                f"$.{id_field}",
                "hash segment is not the first 16 chars of the index key (manifest without index_id, content_sha256, records_ref, records_file_sha256, stats; §2.2)",
            )
    elif parts[3] != str(data.get("content_sha256", ""))[:16]:
        out.add(f"$.{id_field}", "hash segment is not content_sha256[:16]")


@check(
    "PARAMSET_INTEGRITY",
    "§2.2, §11",
    "parameter_set",
    "parameter_set_id is pset:q-demo:<first 16 chars of content_sha256> (content_sha256 itself is checked by CONTENT_HASH_RECOMPUTE)",
)
def _paramset(doc: Doc, ctx: Ctx, out: Findings) -> None:
    data = doc.data
    expected = f"pset:q-demo:{str(data.get('content_sha256', ''))[:16]}"
    if data.get("parameter_set_id") != expected:
        out.add("$.parameter_set_id", f"expected {expected} (hash16 of content_sha256, §2.2)")


@check(
    "ERROR_RESPONSE_RULES",
    "§2.3, v1.1 §7",
    "error_response",
    "Error responses use a known error code with the matching HTTP status (shape is provisional)",
)
def _error_response(doc: Doc, ctx: Ctx, out: Findings) -> None:
    code = doc.data.get("error_code")
    if code not in ERROR_CODES:
        out.add("$.error_code", f"{code!r} is not one of {sorted(ERROR_CODES)}")
    expected = ERROR_CODES.get(code)
    status = doc.data.get("http_status")
    if status is not None and expected is not None and status != expected:
        out.add("$.http_status", f"{code} must be HTTP {expected}, got {status}")
    out.note("error-response shape is PROVISIONAL (contract names codes only)")


# ----------------------------------------------------------------------------- shared response fields


@check(
    "COMMON_GT_READ_FALSE",
    "§2.3, §9",
    (*RESPONSE_KINDS, "detection_index"),
    "provenance.gt_read is exactly false",
)
def _gt_read(doc: Doc, ctx: Ctx, out: Findings) -> None:
    prov = doc.data.get("provenance")
    if not isinstance(prov, dict) or prov.get("gt_read") is not False:
        out.add(
            "$.provenance.gt_read",
            f"must be the boolean false, got {None if not isinstance(prov, dict) else prov.get('gt_read')!r}",
        )


@check(
    "COMMON_IDENTITY_UNCONFIRMED",
    "§2.3, §7.5, §8.7",
    RESPONSE_KINDS,
    "identity_verdict is UNCONFIRMED and no text claims 'the same person'",
    heuristic=True,
)
def _identity(doc: Doc, ctx: Ctx, out: Findings) -> None:
    if doc.data.get("identity_verdict") != "UNCONFIRMED":
        out.add(
            "$.identity_verdict", f"must be 'UNCONFIRMED', got {doc.data.get('identity_verdict')!r}"
        )
    for path, kind, item in walk(doc.data):
        if kind == "value" and IDENTITY_RE.search(item):
            out.add(
                path,
                "text asserts an identity ('same person'); candidates are only condition-matching",
            )


@check(
    "COMMON_AGENT_FIELDS",
    "§2.3, §7.3, §8.6",
    RESPONSE_KINDS,
    "agent_used / agent_attempted / llm_parse_used / decision_source / fallback_used / fallback_reason are mutually consistent",
)
def _agent_fields(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    used, attempted = d.get("agent_used"), d.get("agent_attempted")
    source, fb_used, fb_reason = (
        d.get("decision_source"),
        d.get("fallback_used"),
        d.get("fallback_reason"),
    )
    if used is True and attempted is not True:
        out.add("$.agent_attempted", "agent_used is true but agent_attempted is not")
    if fb_used is True and fb_reason is None:
        out.add("$.fallback_reason", "fallback_used is true but fallback_reason is null")
    if fb_used is False and fb_reason is not None:
        out.add("$.fallback_reason", "fallback_reason is set but fallback_used is false")
    if fb_reason is not None and fb_reason not in FALLBACK_REASONS:
        out.add("$.fallback_reason", f"{fb_reason!r} not in closed list")
    if source == "AGENT" and not (used is True and attempted is True):
        out.add("$.decision_source", "AGENT requires agent_used and agent_attempted true")
    if source == "RULE_FALLBACK" and not (fb_used is True and attempted is True):
        out.add(
            "$.decision_source", "RULE_FALLBACK requires fallback_used and agent_attempted true"
        )
    if source == "RULE_ONLY" and used is True and fb_used is not True:
        out.add(
            "$.decision_source",
            "RULE_ONLY cannot coexist with agent_used true unless a fallback is recorded",
        )
    if fb_reason in AGENT_ONLY_REASONS and attempted is not True:
        out.add("$.fallback_reason", f"{fb_reason} implies the Agent was attempted")
    if doc.kind in ("q1_response", "q3_response"):
        if used is not False:
            out.add("$.agent_used", "Q1 and Q3 responses fix agent_used to false (§2.3)")
        if attempted is not False:
            out.add("$.agent_attempted", "Q1 and Q3 never call the switching Agent")
        if source is not None:
            out.add("$.decision_source", "no switching decision exists in Q1/Q3, must be null")
    if doc.kind == "q3_response":
        if fb_reason in (AGENT_ONLY_REASONS | {"MODE_NOT_AUTHORIZED"}):
            out.add("$.fallback_reason", "Agent-only reason on a Q3 parse response")
        if d.get("parsed_by") == "RULE" and d.get("llm_parse_used") is not False:
            out.add("$.llm_parse_used", "parsed_by RULE requires llm_parse_used false")
        if d.get("parsed_by") == "LLM" and d.get("llm_parse_used") is not True:
            out.add("$.llm_parse_used", "parsed_by LLM requires llm_parse_used true")


@check(
    "COMMON_STATUS_REASON",
    "§2.3, §3.3, §5.1, §6.3, §7.4, §8.7",
    RESPONSE_KINDS,
    "status is in the endpoint's closed list; READY has no reason; PARTIAL has one",
)
def _status_reason(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    if d.get("status") not in STATUS_LISTS[doc.kind]:
        out.add("$.status", f"{d.get('status')!r} not in {STATUS_LISTS[doc.kind]}")
    if d.get("status") == "READY" and d.get("reason") is not None:
        out.add("$.reason", "READY must have reason null")
    if d.get("status") == "PARTIAL" and not d.get("reason"):
        out.add("$.reason", "PARTIAL must state its main reason")


@check(
    "TIME_COVERAGE_INTERNAL",
    "§3.3, §4.4, §6.3, §8.7",
    ("q1_response", "q2_response"),
    "Partial wall-clock coverage is never READY/COMPLETE/NO_MATCH; uncovered ranges listed; OUT_OF_RANGE queries nothing",
)
def _time_coverage(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    scope = d.get("resolved_scope") or {}
    cov = scope.get("time_coverage")
    status = d.get("status")
    if cov is None:
        raise NotApplicable("resolved_scope.time_coverage is null (no time-based query)")
    complete, uncovered = cov.get("coverage_complete"), cov.get("uncovered_wall_ranges") or []
    if complete is True and uncovered:
        out.add(
            "$.resolved_scope.time_coverage",
            "coverage_complete true but uncovered_wall_ranges is not empty",
        )
    if complete is False and not uncovered:
        out.add(
            "$.resolved_scope.time_coverage",
            "coverage_complete false but no uncovered_wall_ranges listed",
        )
    try:
        spans = [(epoch_us(a), epoch_us(b)) for a, b in uncovered]
    except (ValueError, TypeError) as exc:
        out.add(
            "$.resolved_scope.time_coverage.uncovered_wall_ranges", f"unparsable wall range: {exc}"
        )
        spans = []
    if any(a >= b for a, b in spans) or any(
        spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1)
    ):
        out.add(
            "$.resolved_scope.time_coverage.uncovered_wall_ranges",
            "ranges must be half-open, ordered and non-overlapping",
        )
    if complete is False and status in ("READY", "COMPLETE", "NO_MATCH"):
        out.add(
            "$.status",
            f"time coverage is incomplete, status must not be {status} (use PARTIAL or OUT_OF_RANGE)",
        )
    if status == "OUT_OF_RANGE" and scope.get("resolved_source_ranges_us"):
        out.add(
            "$.resolved_scope.resolved_source_ranges_us",
            "OUT_OF_RANGE must not resolve any source range",
        )
    ranges = scope.get("resolved_source_ranges_us") or []
    for index, item in enumerate(ranges):
        if not valid_range(item.get("range_us")):
            out.add(f"$.resolved_scope.resolved_source_ranges_us[{index}]", "not a half-open range")


@check(
    "TIME_COVERAGE_RECOMPUTE",
    "§3.1, §3.3",
    ("q1_response", "q2_response"),
    "Resolved source ranges, coverage_complete and uncovered_wall_ranges equal the values computed from the clock_mapping (wall requests only)",
)
def _time_recompute(doc: Doc, ctx: Ctx, out: Findings) -> None:
    scope = doc.data.get("resolved_scope") or {}
    requested = scope.get("requested_time")
    if not requested or requested.get("kind") != "WALL":
        raise NotApplicable("not a wall-clock request")
    mappings = [
        m
        for m in ctx.of_kind("clock_mapping")
        if m.data.get("run_id") in (scope.get("run_ids") or [])
    ]
    if not mappings:
        raise NoContext("no clock_mapping document for the response's run_ids")
    try:
        req = (epoch_us(requested["wall_range"][0]), epoch_us(requested["wall_range"][1]))
        expected_ranges, covers = [], []
        for m in sorted(mappings, key=lambda x: x.data["run_id"]):
            md = m.data
            origin, dur, t0 = epoch_us(md["wall_origin"]), md["source_duration_us"], md["t0_us"]
            cover = (origin - t0, origin - t0 + dur)
            a, b = max(req[0], cover[0]), min(req[1], cover[1])
            if a < b:
                covers.append((a, b))
                expected_ranges.append(
                    {"run_id": md["run_id"], "range_us": [a - origin + t0, b - origin + t0]}
                )
        uncovered = subtract_intervals(req, covers)
        got_uncovered = [
            (epoch_us(a), epoch_us(b))
            for a, b in (scope["time_coverage"] or {}).get("uncovered_wall_ranges", [])
        ]
    except (KeyError, ValueError, TypeError) as exc:
        out.add("$.resolved_scope", f"cannot recompute coverage: {exc}")
        return
    got_ranges = sorted(
        scope.get("resolved_source_ranges_us") or [], key=lambda x: x.get("run_id", "")
    )
    if got_ranges != expected_ranges:
        out.add(
            "$.resolved_scope.resolved_source_ranges_us",
            f"expected {expected_ranges}, got {got_ranges}",
        )
    cov = scope.get("time_coverage") or {}
    if cov.get("coverage_complete") is not (not uncovered):
        out.add("$.resolved_scope.time_coverage.coverage_complete", f"expected {not uncovered}")
    if got_uncovered != uncovered:
        out.add(
            "$.resolved_scope.time_coverage.uncovered_wall_ranges",
            f"expected {uncovered} (epoch µs), got {got_uncovered}",
        )
    status = doc.data.get("status")
    if not covers and status in ("READY", "NO_MATCH", "PARTIAL", "COMPLETE"):
        out.add("$.status", "no overlap with any run: status must be OUT_OF_RANGE")


@check(
    "SCOPE_HASH_LINKS",
    "§2.3, §4.2, §5, §11",
    RESPONSE_KINDS,
    "resolved_scope hashes / ids point at the supplied index, graphs, clock mapping and parameter set",
)
def _scope_links(doc: Doc, ctx: Ctx, out: Findings) -> None:
    scope = doc.data.get("resolved_scope") or {}
    checked = 0

    def link(
        field_name: str, kind: str, target_field: str, nested: Callable[[Doc], Any] | None = None
    ) -> None:
        nonlocal checked
        value = scope.get(field_name)
        candidates = ctx.of_kind(kind)
        if value is None or not candidates:
            return
        checked += 1
        values = [nested(c) if nested else c.data.get(target_field) for c in candidates]
        if value not in values:
            out.add(
                f"$.resolved_scope.{field_name}",
                f"{value!r} matches none of the supplied {kind} documents",
            )

    link("detection_index_sha256", "detection_index", "content_sha256")
    link("detection_index_id", "detection_index", "index_id")
    link(
        "class_map_sha256",
        "detection_index",
        "",
        lambda c: c.data["detector"]["class_map"]["content_sha256"],
    )
    link("color_method_version", "detection_index", "", lambda c: c.data["color_method"]["version"])
    link("region_graph_sha256", "region_graph", "content_sha256")
    link("camera_graph_sha256", "camera_graph", "content_sha256")
    link("clock_mapping_sha256", "clock_mapping", "content_sha256")
    if scope.get("parameter_set_id") is not None and ctx.param_doc is not None:
        checked += 1
        if scope["parameter_set_id"] != ctx.param_doc.data.get("parameter_set_id"):
            out.add("$.resolved_scope.parameter_set_id", "differs from the supplied parameter set")
        if scope.get("parameter_set_sha256") not in (
            None,
            ctx.param_doc.data.get("content_sha256"),
        ):
            out.add(
                "$.resolved_scope.parameter_set_sha256", "differs from the supplied parameter set"
            )
    if checked == 0:
        raise NoContext("no referenced document supplied")


@check(
    "GRAPH_APPROVAL_GATES_STATUS",
    "§5.1",
    ("q1_response", "q2_response"),
    "A response built on a DRAFT graph is not READY/COMPLETE and says GRAPH_NOT_APPROVED",
)
def _graph_gate(doc: Doc, ctx: Ctx, out: Findings) -> None:
    scope = doc.data.get("resolved_scope") or {}
    graphs = []
    for field_name, kind in (
        ("region_graph_sha256", "region_graph"),
        ("camera_graph_sha256", "camera_graph"),
    ):
        g = ctx.by_hash(kind, scope.get(field_name))
        if g is not None:
            graphs.append(g)
    if not graphs:
        raise NoContext("referenced graph not supplied")
    if any(g.data.get("approval_status") != "APPROVED" for g in graphs):
        if doc.data.get("status") in ("READY", "COMPLETE", "NO_MATCH"):
            out.add("$.status", "graph is DRAFT; status must not be READY/COMPLETE/NO_MATCH")
        if doc.data.get("reason") != "GRAPH_NOT_APPROVED" and doc.data.get("status") == "PARTIAL":
            out.add("$.reason", "PARTIAL on a DRAFT graph must carry reason GRAPH_NOT_APPROVED")


# ----------------------------------------------------------------------------- Q1


def _floor(ctx: Ctx) -> float:
    try:
        return ctx.numeric("index_score_floor")["index_score_floor"]
    except ParamUnset:
        for manifest in ctx.of_kind("detection_index"):
            value = manifest.data.get("detector", {}).get("index_score_floor")
            if ok_number(value):
                return value
        raise


@check(
    "Q1_MIN_SCORE_FLOOR",
    "§6.1, §4.2",
    ("q1_request", "q1_response"),
    "query_min_score is never below index_score_floor; a request below it is answered with FORBIDDEN_INFERENCE_INPUT",
)
def _q1_floor(doc: Doc, ctx: Ctx, out: Findings) -> None:
    floor = _floor(ctx)
    if doc.kind == "q1_response":
        score = (doc.data.get("normalized_condition") or {}).get("query_min_score")
        if ok_number(score) and score < floor:
            out.add(
                "$.normalized_condition.query_min_score",
                f"{score} is below index_score_floor {floor}",
            )
        return
    score = doc.data.get("condition", {}).get("query_min_score")
    if not (ok_number(score) and score < floor):
        return
    reply = ctx.sibling(doc, "q1_response", "error_response")
    if reply is None:
        raise NoContext("request is below the floor but no paired response/error file was supplied")
    if (
        reply.kind != "error_response"
        or reply.data.get("error_code") != "FORBIDDEN_INFERENCE_INPUT"
    ):
        out.add(
            reply.path,
            "a request below index_score_floor must be rejected with FORBIDDEN_INFERENCE_INPUT",
        )


@check(
    "Q1_UNSUPPORTED_HANDLING",
    "§6.1, §6.3",
    "q1_response",
    "UNSUPPORTED_* statuses return no results; a colour condition on a non-person class is UNSUPPORTED_*",
)
def _q1_unsupported(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    status, cond = d.get("status"), d.get("normalized_condition") or {}
    if status in ("UNSUPPORTED_CLASS", "UNSUPPORTED_CONDITION") and d.get("results"):
        out.add("$.results", f"{status} must not return results (nothing is queried)")
    if status == "UNSUPPORTED_CLASS" and not d.get("supported_classes_ref"):
        out.add("$.supported_classes_ref", "UNSUPPORTED_CLASS must attach supported_classes_ref")
    if (
        cond.get("color") is not None
        and cond.get("class_label") != "person"
        and status not in ("UNSUPPORTED_CONDITION", "UNSUPPORTED_CLASS")
    ):
        out.add(
            "$.status",
            "colour condition on a non-person class must be UNSUPPORTED_CONDITION (or UNSUPPORTED_CLASS)",
        )


@check(
    "Q1_SUPPORTED_SET_CONSISTENCY",
    "§6.1, §6.2",
    ("q1_response", "q1_request"),
    "Class / colour support decision agrees with the supplied class map, alias table and colour vocabulary",
)
def _q1_supported(doc: Doc, ctx: Ctx, out: Findings) -> None:
    sup_docs = ctx.of_kind("supported_classes")
    if not sup_docs:
        raise NoContext("no supported-classes context file supplied")
    sup = sup_docs[0].data
    labels, aliases, colors = (
        set(sup["class_labels"]),
        set(sup["aliases"]),
        set(sup.get("color_labels", [])),
    )
    if doc.kind == "q1_request":
        reply = ctx.sibling(doc, "q1_response", "error_response")
        if reply is None:
            raise NoContext("no paired response")
        if reply.kind == "error_response":
            return
        cond = doc.data["condition"]
        status = reply.data.get("status")
        known = cond["class_label"] in labels | aliases
        if not known and status != "UNSUPPORTED_CLASS":
            out.add(
                reply.path + "#status",
                f"class {cond['class_label']!r} is not in class_map or alias table: expected UNSUPPORTED_CLASS, got {status}",
            )
        if known and status == "UNSUPPORTED_CLASS":
            out.add(
                reply.path + "#status",
                f"class {cond['class_label']!r} is supported but the response says UNSUPPORTED_CLASS",
            )
        color = cond.get("color")
        if known and color is not None:
            bad = cond["class_label"] != "person" or (colors and color.get("label") not in colors)
            if bad and status != "UNSUPPORTED_CONDITION":
                out.add(
                    reply.path + "#status",
                    "unsupported colour condition must be UNSUPPORTED_CONDITION",
                )
            if not bad and status == "UNSUPPORTED_CONDITION":
                out.add(
                    reply.path + "#status",
                    "colour condition on person with a known colour is supported",
                )
        return
    label = (doc.data.get("normalized_condition") or {}).get("class_label")
    if (
        doc.data.get("status") not in ("UNSUPPORTED_CLASS", "UNSUPPORTED_CONDITION")
        and label not in labels
    ):
        out.add(
            "$.normalized_condition.class_label",
            f"{label!r} is not a class_map label (aliases must be normalised away)",
        )


@check(
    "Q1_STATUS_VS_COVERAGE",
    "§3.3, §4.4, §6.3",
    "q1_response",
    "READY needs a full inference pass and a result; NO_MATCH never hides un-inferred, missing or uncovered time; PARTIAL when anything is missing",
)
def _q1_status_coverage(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    status = d.get("status")
    results, no_match, not_eval = (
        d.get("results") or [],
        d.get("no_match_cameras") or [],
        d.get("not_evaluated_cameras") or [],
    )
    gaps = [
        r["camera_id"]
        for r in results
        if (r["coverage"]["not_inferred_frames"] or r["coverage"]["missing_frames"])
    ]
    gaps += [
        r["camera_id"]
        for r in no_match
        if (r["coverage"]["not_inferred_frames"] or r["coverage"]["missing_frames"])
    ]
    gaps += [r["camera_id"] for r in not_eval]
    if status == "READY":
        if not results:
            out.add("$.results", "READY requires at least one result")
        if gaps:
            out.add("$.status", f"READY but cameras are not fully inferred: {sorted(set(gaps))}")
    if status == "NO_MATCH":
        if results:
            out.add("$.results", "NO_MATCH must have no results")
        if gaps:
            out.add(
                "$.status",
                f"NO_MATCH over un-inferred or missing frames {sorted(set(gaps))}: must be PARTIAL",
            )
        if not no_match:
            out.add("$.no_match_cameras", "NO_MATCH must list the evaluated cameras")
    for index, r in enumerate(results):
        for s_index, seg in enumerate(r["matched_segments"]):
            if seg["matched_frames"] > seg["evaluated_frames"]:
                out.add(
                    f"$.results[{index}].matched_segments[{s_index}]",
                    "matched_frames exceeds evaluated_frames",
                )


@check(
    "Q1_RESULT_ORDER",
    "§6.3",
    "q1_response",
    "Results ordered by first match time then camera_id, ranks consecutive, segments ordered and half-open, counts consistent",
)
def _q1_order(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    results = d.get("results") or []
    if d.get("ranking_basis") != ["first_match_us_asc", "camera_id"]:
        out.add(
            "$.ranking_basis",
            f"expected ['first_match_us_asc', 'camera_id'], got {d.get('ranking_basis')!r}",
        )
    keys = []
    for index, r in enumerate(results):
        problem = ranges_sorted_disjoint([s["range_us"] for s in r["matched_segments"]])
        if problem:
            out.add(f"$.results[{index}].matched_segments", problem)
            continue
        keys.append((r["matched_segments"][0]["range_us"][0], r["camera_id"]))
    if keys != sorted(keys):
        out.add(
            "$.results",
            "not ordered by (first matched time, camera_id); detection count must not influence order",
        )
    ranks = [r["rank"] for r in results]
    if ranks and ranks != list(range(ranks[0], ranks[0] + len(ranks))):
        out.add("$.results[*].rank", f"ranks must be consecutive, got {ranks}")
    if d.get("returned_count") != len(results):
        out.add(
            "$.returned_count", f"{d.get('returned_count')} != number of results {len(results)}"
        )
    if d.get("next_cursor") is None and d.get("results_total") != d.get("returned_count"):
        out.add("$.results_total", "no next_cursor, so results_total must equal returned_count")
    if (d.get("results_total") or 0) < (d.get("returned_count") or 0):
        out.add("$.results_total", "smaller than returned_count")


@check(
    "Q1_NONE_CATEGORIES_DISJOINT",
    "§6.3",
    "q1_response",
    "A camera appears in only one of results / no_match_cameras / not_evaluated_cameras",
)
def _q1_disjoint(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    seen = Counter(
        r["camera_id"]
        for key in ("results", "no_match_cameras", "not_evaluated_cameras")
        for r in d.get(key) or []
    )
    for camera, count in seen.items():
        if count > 1:
            out.add(
                "$",
                f"camera {camera} appears in more than one of results / no_match_cameras / not_evaluated_cameras (§6.3: three kinds of 'none' must stay separate)",
            )


# ----------------------------------------------------------------------------- Q3


@check(
    "Q3_LLM_OUTPUT_STRICT",
    "§7.1",
    "q3_llm_output",
    "LLM output has no extra field and a consistent clarification flag",
)
def _q3_llm_strict(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    if d.get("needs_clarification") is True and not d.get("clarification_question"):
        out.add("$.clarification_question", "needs_clarification true requires a question")
    if d.get("needs_clarification") is False and d.get("clarification_question"):
        out.add("$.clarification_question", "question given although needs_clarification is false")
    tl = d.get("time_literal") or {}
    for part in ("start", "end", "date"):
        v = tl.get(part)
        if isinstance(v, str) and re.fullmatch(r"\d{9,}", v.strip()):
            out.add(
                f"$.time_literal.{part}",
                "looks like a converted microsecond value; the LLM must only quote literal text",
            )


@check(
    "Q3_LLM_TERMS_LITERAL",
    "§7.1",
    "q3_llm_output",
    "class/colour/time/camera/region terms are fragments of the user's original text",
)
def _q3_terms_literal(doc: Doc, ctx: Ctx, out: Findings) -> None:
    req = ctx.sibling(doc, "q3_request")
    if req is None:
        raise NoContext("no paired q3 request")
    text, d = req.data["text"], doc.data
    pieces = [("class_term", d.get("class_term")), ("color_term", d.get("color_term"))]
    tl = d.get("time_literal") or {}
    pieces += [(f"time_literal.{k}", tl.get(k)) for k in ("start", "end", "date")]
    pieces += [(f"camera_terms[{i}]", t) for i, t in enumerate(d.get("camera_terms") or [])]
    pieces += [(f"region_terms[{i}]", t) for i, t in enumerate(d.get("region_terms") or [])]
    for name, piece in pieces:
        if piece is not None and piece not in text:
            out.add(
                f"$.{name}",
                f"{piece!r} is not a fragment of the request text (the LLM must not rephrase)",
            )


@check(
    "Q3_RESPONSE_RULES",
    "§7.2–§7.4",
    "q3_response",
    "structured_query only when PARSED; clarification and failure statuses never execute; LLM call recorded when LLM was used",
)
def _q3_response(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    status, query = d.get("status"), d.get("structured_query")
    if status == "PARSED" and query is None:
        out.add("$.structured_query", "PARSED requires a structured_query")
    if (
        status in ("PARSE_FAILED", "NEEDS_CLARIFICATION", "TIME_EXPRESSION_INVALID")
        and query is not None
    ):
        out.add("$.structured_query", f"{status} must not carry an executable query (no guessing)")
    if status == "NEEDS_CLARIFICATION" and not d.get("clarification"):
        out.add("$.clarification", "NEEDS_CLARIFICATION requires a question and options")
    if status != "NEEDS_CLARIFICATION" and d.get("clarification") is not None:
        out.add("$.clarification", "clarification only belongs to NEEDS_CLARIFICATION")
    call = d.get("llm_call")
    if d.get("llm_parse_used") is True and (not call or (call.get("attempts") or 0) < 1):
        out.add("$.llm_call", "llm_parse_used true requires a recorded LLM call with attempts >= 1")
    if status == "PARSED" and d.get("parsed_by") is None:
        out.add("$.parsed_by", "PARSED requires parsed_by")
    if (
        d.get("parsed_by") == "RULE"
        and d.get("fallback_used") is True
        and d.get("fallback_reason") not in Q3_PROVIDER_REASONS
    ):
        out.add(
            "$.fallback_reason", f"rule parse fallback must be one of {sorted(Q3_PROVIDER_REASONS)}"
        )


@check(
    "Q3_STRUCTURED_QUERY_SCHEMA",
    "§7.2 step 4",
    "q3_response",
    "The assembled structured_query validates against the Q1 or Q2 request schema",
)
def _q3_query_schema(doc: Doc, ctx: Ctx, out: Findings) -> None:
    query = doc.data.get("structured_query")
    if query is None:
        raise NotApplicable("no structured_query")
    key = query.get("schema_version") if isinstance(query, dict) else None
    if key not in ("q-demo.q1-request.v1", "q-demo.q2-request.v1"):
        out.add("$.structured_query.schema_version", f"must be a Q1 or Q2 request, got {key!r}")
        return
    for error in validate(query, key):
        out.add("$.structured_query" + error.path[1:], error.message)
    if (query.get("origin") if key.endswith("q1-request.v1") else "Q3_PARSED") != "Q3_PARSED":
        out.add(
            "$.structured_query.origin", "a query assembled from Q3 must carry origin Q3_PARSED"
        )


@check(
    "Q3_FALLBACK_CONSISTENCY",
    "§7.3",
    "q3_response",
    "A rule parse after an LLM attempt (LLM_WITH_RULE_FALLBACK) records fallback_used with a provider reason",
)
def _q3_fallback(doc: Doc, ctx: Ctx, out: Findings) -> None:
    req = ctx.sibling(doc, "q3_request")
    if req is None:
        raise NoContext("no paired q3 request")
    d = doc.data
    if req.data.get("parser_mode") == "LLM_WITH_RULE_FALLBACK" and d.get("parsed_by") == "RULE":
        if (
            d.get("fallback_used") is not True
            or d.get("fallback_reason") not in Q3_PROVIDER_REASONS
        ):
            out.add(
                "$.fallback_reason",
                "LLM_WITH_RULE_FALLBACK answered by the rule parser must record PROVIDER_UNAVAILABLE / PROVIDER_TIMEOUT / INVALID_RESPONSE",
            )


@check(
    "Q3_ATTEMPTS_WITHIN_PARAM",
    "§7.2, §11",
    "q3_response",
    "llm_call.attempts <= q3_max_llm_attempts",
)
def _q3_attempts(doc: Doc, ctx: Ctx, out: Findings) -> None:
    limit = ctx.numeric("q3_max_llm_attempts")["q3_max_llm_attempts"]
    call = doc.data.get("llm_call")
    if call and call.get("attempts", 0) > limit:
        out.add("$.llm_call.attempts", f"{call['attempts']} exceeds q3_max_llm_attempts {limit}")


@check(
    "EXPLANATION_CITED_REFS",
    "§7.5",
    "explanation",
    "Every cited ref appears in the explained response; text claims no identity; at least one ref is cited (explanation wrapper is provisional)",
    heuristic=True,
)
def _explanation(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    target = next(
        (
            r
            for r in ctx.of_kind(*RESPONSE_KINDS)
            if r.data.get("output_sha256") == d.get("explains_output_sha256")
        ),
        None,
    )
    if target is None:
        raise NoContext("the explained response (explains_output_sha256) was not supplied")
    available = strings(target.data)
    refs = d.get("cited_refs") or []
    if not refs:
        out.add("$.cited_refs", "an explanation must cite at least one ref")
    for index, ref in enumerate(refs):
        if ref not in available:
            out.add(
                f"$.cited_refs[{index}]",
                f"{ref!r} does not occur in the explained response (explanation must be discarded)",
            )
    if IDENTITY_RE.search(d.get("text", "")):
        out.add("$.text", "explanation asserts an identity")
    out.note("explanation wrapper shape is PROVISIONAL")


# ----------------------------------------------------------------------------- candidates (§5.4)


RANKING_BASIS_KEYS = {"relation_tier", "overlap_area_m2", "camera_id"}  # Q-03: no secondary keys


def _tier(candidate: dict[str, Any]) -> int | None:
    """Contract §5.4 ``relation_tier`` decision order: the first matching rule is the answer.

    1. coverage / visible range / exit data missing (relation UNKNOWN in the kit schema) -> 4
    2. the path has an edge with ``state: UNKNOWN``               -> 3 (an OVERLAP is not lifted back to 1)
    3. ``relation: OVERLAP``                                      -> 1
    4. ``BLIND_GAP`` whose path is all OPEN and APPROVED_WALKABLE -> 2
    Any other combination has no tier in the contract (``None``).
    """

    if candidate["relation"] == "UNKNOWN":
        return 4
    if candidate["path_has_unknown_state"]:
        return 3
    if candidate["relation"] == "OVERLAP":
        return 1
    if (
        candidate["relation"] == "BLIND_GAP"
        and candidate["path_traversability"] == "APPROVED_WALKABLE"
    ):
        return 2
    return None


@check(
    "CANDIDATE_ORDER_D28",
    "§5.4, v1.1 §6.1",
    "candidate_snapshot",
    "Candidates sorted by relation_tier (§5.4 decision order 4,3,1,2), overlap_area_m2 desc (null last), camera_id; ranks consecutive; one entry per camera; ranking_basis has exactly the three D28 keys and no detection/colour keys",
)
def _cand_order(doc: Doc, ctx: Ctx, out: Findings) -> None:
    cands = doc.data["candidates"]
    keys = []
    for index, c in enumerate(cands):
        basis = c["ranking_basis"]
        tier = basis["relation_tier"]
        expected_tier = _tier(c)
        if expected_tier is None:
            out.note(
                "a transition whose path is neither all-OPEN APPROVED_WALKABLE nor UNKNOWN has no tier in the contract (U08); tier not checked"
            )
        elif tier != expected_tier:
            out.add(
                f"$.candidates[{index}].ranking_basis.relation_tier",
                f"tier {tier} inconsistent with the §5.4 decision order (expected {expected_tier})",
            )
        extra_keys = sorted(set(basis) - RANKING_BASIS_KEYS)
        if extra_keys:
            out.add(
                f"$.candidates[{index}].ranking_basis",
                f"ranking_basis lists exactly relation_tier, overlap_area_m2, camera_id (Q-03: no secondary keys); extra {extra_keys}",
            )
        if basis["camera_id"] != c["camera_id"]:
            out.add(f"$.candidates[{index}].ranking_basis.camera_id", "differs from camera_id")
        for key in basis:
            if re.search(r"detect|count|colou?r|score|match|presence|evidence", key, re.IGNORECASE):
                out.add(
                    f"$.candidates[{index}].ranking_basis.{key}",
                    "detection count / colour / evidence must not enter the ranking (D28)",
                )
        area = basis["overlap_area_m2"]
        keys.append((tier, area is None, -(area or 0), c["camera_id"]))
    if keys != sorted(keys):
        out.add(
            "$.candidates",
            "not in D28 order (relation_tier, overlap_area_m2 desc with null last, camera_id)",
        )
    ranks = [c["rank"] for c in cands]
    if ranks != list(range(1, len(cands) + 1)):
        out.add("$.candidates[*].rank", f"ranks must be 1..n in order, got {ranks}")
    for camera, count in Counter(c["camera_id"] for c in cands).items():
        if count > 1:
            out.add(
                "$.candidates",
                f"camera {camera} listed {count} times; keep the best transition and list others in alternative_transition_ids",
            )


@check(
    "CANDIDATE_TOPOLOGICAL_EXCLUDED",
    "§5.2–§5.4",
    "candidate_snapshot",
    "TOPOLOGICAL_ONLY paths never appear as candidates; excluded ones carry TOPOLOGICAL_ONLY_EDGE; agrees with the camera graph when supplied",
)
def _cand_topo(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    for index, c in enumerate(d["candidates"]):
        if c["path_traversability"] == "TOPOLOGICAL_ONLY":
            out.add(
                f"$.candidates[{index}]", "TOPOLOGICAL_ONLY transition must not be a candidate (K7)"
            )
    graphs = ctx.of_kind("camera_graph")
    transitions = {t["transition_id"]: t for g in graphs for t in g.data["transitions"]}
    if not transitions:
        out.note(
            "camera graph not supplied: only the snapshot's own path_traversability was checked"
        )
    for index, c in enumerate(d["candidates"]):
        t = transitions.get(c["transition_id"])
        if transitions and t is None:
            out.add(
                f"$.candidates[{index}].transition_id",
                "unknown transition (not in the camera graph)",
            )
        elif t is not None:
            if t["path_traversability"] == "TOPOLOGICAL_ONLY":
                out.add(
                    f"$.candidates[{index}].transition_id",
                    "graph says this transition is TOPOLOGICAL_ONLY",
                )
            if t["to_camera_id"] != c["camera_id"]:
                out.add(
                    f"$.candidates[{index}].camera_id", "differs from the transition's to_camera_id"
                )
    for index, e in enumerate(d["excluded_transitions"]):
        t = transitions.get(e["transition_id"])
        if (
            t is not None
            and e["reason"] == "TOPOLOGICAL_ONLY_EDGE"
            and t["path_traversability"] != "TOPOLOGICAL_ONLY"
        ):
            out.add(
                f"$.excluded_transitions[{index}]",
                "excluded as TOPOLOGICAL_ONLY_EDGE but the graph transition is not",
            )
        if (
            t is not None
            and t["path_traversability"] == "TOPOLOGICAL_ONLY"
            and e["reason"] != "TOPOLOGICAL_ONLY_EDGE"
        ):
            out.add(
                f"$.excluded_transitions[{index}].reason",
                "TOPOLOGICAL_ONLY transitions must be excluded with TOPOLOGICAL_ONLY_EDGE",
            )
    listed = {c["transition_id"] for c in d["candidates"]}
    for index, e in enumerate(d["excluded_transitions"]):
        if e["transition_id"] in listed:
            out.add(
                f"$.excluded_transitions[{index}]", "transition is both a candidate and excluded"
            )


@check(
    "CANDIDATE_SNAPSHOT_HASH",
    "§2.2, §5.4",
    "candidate_snapshot",
    "candidate_snapshot_sha256 equals the canonical hash of the snapshot without itself, stats and every candidate_ref (candidates identified by rank)",
)
def _cand_hash(doc: Doc, ctx: Ctx, out: Findings) -> None:
    actual = snapshot_hash(doc.data)
    if doc.data["candidate_snapshot_sha256"] != actual:
        out.add(
            "$.candidate_snapshot_sha256",
            f"declared {doc.data['candidate_snapshot_sha256']!r}, recomputed {actual} (preimage excludes candidate_ref, §2.2)",
        )


@check(
    "CANDIDATE_RANKING_AREA",
    "§5.3, §5.4",
    "candidate_snapshot",
    "ranking_basis.overlap_area_m2 equals the camera graph transition's ranking_area_m2 (null stays null)",
)
def _cand_area(doc: Doc, ctx: Ctx, out: Findings) -> None:
    transitions = {
        t["transition_id"]: t for g in ctx.of_kind("camera_graph") for t in g.data["transitions"]
    }
    if not transitions:
        raise NoContext("camera graph not supplied")
    for index, c in enumerate(doc.data["candidates"]):
        t = transitions.get(c["transition_id"])
        if t is None:
            continue  # unknown transitions are reported by CANDIDATE_TOPOLOGICAL_EXCLUDED
        if c["ranking_basis"]["overlap_area_m2"] != t["ranking_area_m2"]:
            out.add(
                f"$.candidates[{index}].ranking_basis.overlap_area_m2",
                f"{c['ranking_basis']['overlap_area_m2']!r} differs from the transition's ranking_area_m2 {t['ranking_area_m2']!r} (the area is read from the graph, never from events)",
            )


@check(
    "CANDIDATE_REFS_AND_LIMITS",
    "§5.4, §8.4, §11",
    "candidate_snapshot",
    "candidate_ref embeds the snapshot hash prefix and rank; candidate count <= top_k",
)
def _cand_refs(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    prefix = d["candidate_snapshot_sha256"][:16]
    for index, c in enumerate(d["candidates"]):
        m = re.fullmatch(r"cand:([0-9a-f]{16}):(\d+)", c["candidate_ref"])
        if not m or m.group(1) != prefix:
            out.add(f"$.candidates[{index}].candidate_ref", f"expected cand:{prefix}:<n>")
        elif int(m.group(2)) != c["rank"]:
            out.add(f"$.candidates[{index}].candidate_ref", "numeric suffix differs from rank")
    top_k = ctx.numeric("top_k")["top_k"]
    if len(d["candidates"]) > top_k:
        out.add("$.candidates", f"{len(d['candidates'])} candidates exceed top_k {top_k}")


# ----------------------------------------------------------------------------- decision records (§8)


def _snapshot_for(ctx: Ctx, record: dict[str, Any]) -> Doc | None:
    return ctx.by_hash(
        "candidate_snapshot", record.get("candidate_snapshot_sha256"), "candidate_snapshot_sha256"
    )


@check(
    "DECISION_FIELD_CONSISTENCY",
    "§8.4, §8.6, §8.7",
    "decision_record",
    "accepted/rejection_code, decided_by, switch_mode, fallback_reason, executed action and state_after agree",
)
def _decision_fields(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    mode, by, fb = d["switch_mode"], d["decided_by"], d["fallback_reason"]
    if d["accepted"] and d["rejection_code"] is not None:
        out.add("$.rejection_code", "accepted submissions have no rejection_code")
    if not d["accepted"] and d["rejection_code"] is None:
        out.add("$.rejection_code", "a rejected submission needs a rejection_code")
    if not d["accepted"] and d["state_after"] != d["state_before"]:
        out.add("$.state_after", "a rejected submission must not change the state")
    if mode == "RULE_ONLY":
        if by not in ("RULE_ONLY", "USER"):
            out.add("$.decided_by", "RULE_ONLY sessions are decided by RULE_ONLY or USER")
        if d["llm_calls"]:
            out.add("$.llm_calls", "RULE_ONLY must not call an LLM")
    if by == "RULE_FALLBACK" and (mode != "AGENT_SEQUENTIAL" or fb is None):
        out.add("$.decided_by", "RULE_FALLBACK needs AGENT_SEQUENTIAL mode and a fallback_reason")
    if by == "AGENT" and fb is not None:
        out.add("$.fallback_reason", "an Agent decision has no fallback_reason")
    if by == "AGENT" and not d["llm_calls"]:
        out.add("$.llm_calls", "an Agent decision must record its LLM call(s) (§7.6)")
    if by in ("AGENT", "USER") and d["accepted"] and d["submitted"] is not None:
        if d["executed_action"] != d["submitted"]["action"]:
            out.add("$.executed_action", "differs from the accepted submission")
        if d["submitted"].get("candidate_ref") != d["executed_candidate_ref"]:
            out.add("$.executed_candidate_ref", "differs from the accepted submission")
    if d["accepted"] and d["executed_action"] == "SWITCH" and d["state_after"] != "PLAYING":
        out.add("$.state_after", "an accepted SWITCH ends in PLAYING (via SWITCHING)")
    if (
        d["accepted"]
        and d["executed_action"] == "RETURN_TO_ORIGIN"
        and d["state_after"] != "RETURNED_TO_ORIGIN"
    ):
        out.add("$.state_after", "RETURN_TO_ORIGIN ends in RETURNED_TO_ORIGIN")
    if d["executed_action"] == "SWITCH" and not d["executed_candidate_ref"]:
        out.add("$.executed_candidate_ref", "SWITCH needs a candidate_ref")


@check(
    "DECISION_CANDIDATE_LEGALITY",
    "§5.4, §8.4",
    "decision_record",
    "The candidate switched to is in the legal snapshot (never a TOPOLOGICAL_ONLY / excluded / invented one) and its camera is a candidate camera",
)
def _decision_legality(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    refs = {c["candidate_ref"] for c in d["candidates_considered"]}
    executed = d["executed_candidate_ref"]
    if (
        d["accepted"]
        and d["executed_action"] in ("SWITCH", "NEXT_CANDIDATE")
        and executed not in refs
    ):
        out.add(
            "$.executed_candidate_ref", "executed candidate was not among candidates_considered"
        )
    snap = _snapshot_for(ctx, d)
    if snap is None:
        if d["candidate_snapshot_sha256"] is not None:
            out.note("candidate snapshot not supplied: membership in the snapshot was not verified")
        return
    legal = {c["candidate_ref"]: c for c in snap.data["candidates"]}
    for index, c in enumerate(d["candidates_considered"]):
        if c["candidate_ref"] not in legal:
            out.add(
                f"$.candidates_considered[{index}].candidate_ref",
                "not a candidate of the snapshot (invented or excluded)",
            )
        elif legal[c["candidate_ref"]]["rank"] != c["rank"]:
            out.add(f"$.candidates_considered[{index}].rank", "differs from the snapshot rank")
    if d["accepted"] and executed is not None and executed not in legal:
        out.add("$.executed_candidate_ref", "accepted a candidate outside the legal snapshot")
    if (
        d["accepted"]
        and executed in legal
        and legal[executed]["path_traversability"] == "TOPOLOGICAL_ONLY"
    ):
        out.add("$.executed_candidate_ref", "switched along a TOPOLOGICAL_ONLY path")


@check(
    "DECISION_SEQUENTIAL_ORDER",
    "§8.4, §8.6",
    "decision_record",
    "Candidates are taken in rank order without skipping; evidence is fetched before a switch/next; a switch is the last step and follows NEXT_CANDIDATEs",
)
def _decision_order(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    considered = d["candidates_considered"]
    ranks = [c["rank"] for c in considered]
    if ranks and ranks != list(range(ranks[0], ranks[0] + len(ranks))):
        out.add(
            "$.candidates_considered",
            f"ranks must advance by one without skipping (ILLEGAL_ORDER), got {ranks}",
        )
    for index, c in enumerate(considered):
        acted = c["action"] in ("SWITCH", "NEXT_CANDIDATE")
        if acted and not c["evidence_sha256"]:
            out.add(
                f"$.candidates_considered[{index}]",
                "acted on a candidate without fetching its evidence (EVIDENCE_NOT_FETCHED)",
            )
        if c["action"] == "SWITCH" and index != len(considered) - 1:
            out.add(
                f"$.candidates_considered[{index}]", "SWITCH must be the last candidate considered"
            )
        if c["action"] == "RETURN_TO_ORIGIN" and index != len(considered) - 1:
            out.add(f"$.candidates_considered[{index}]", "RETURN_TO_ORIGIN ends the search")
    if d["accepted"] and d["executed_action"] == "SWITCH":
        last = considered[-1] if considered else None
        if (
            last is None
            or last["candidate_ref"] != d["executed_candidate_ref"]
            or last["action"] != "SWITCH"
        ):
            out.add(
                "$.candidates_considered",
                "accepted SWITCH must correspond to the last considered candidate",
            )
    for index, c in enumerate(considered):
        if c["decided_by"] in ("RULE_ONLY", "RULE_FALLBACK") and c["action"] == "NEXT_CANDIDATE":
            expected = {
                "PERSON_NO_COLOR_MATCH": "CONDITION_MISMATCH",
                "MATCH_WEAK": "BELOW_SWITCH_GUARD",
                "PERSON_COLOR_UNKNOWN": "BELOW_SWITCH_GUARD",
                "NOT_EVALUATED": "INSUFFICIENT_COVERAGE",
                "PARTIAL_EVIDENCE": "INSUFFICIENT_COVERAGE",
            }.get(c["target_presence"])
            if expected and c["exclusion_reason"] != expected:
                out.add(
                    f"$.candidates_considered[{index}].exclusion_reason",
                    f"rule fallback records {expected} for {c['target_presence']}, got {c['exclusion_reason']!r}",
                )


@check(
    "DECISION_SWITCH_GUARD",
    "§8.4, §8.6, §11",
    "decision_record",
    "An accepted SWITCH only targets a candidate whose target_presence reaches switch_min_presence; a rule decision does not skip a guard-reaching candidate that has an entry observation, and records NO_ALIGNABLE_OBSERVATION when it has none",
)
def _decision_guard(doc: Doc, ctx: Ctx, out: Findings) -> None:
    minimum = ctx.param("switch_min_presence")
    if minimum not in PRESENCE_ORDER:
        raise ParamUnset(["switch_min_presence"])
    allowed = set(PRESENCE_ORDER[: PRESENCE_ORDER.index(minimum) + 1])
    d = doc.data
    for index, c in enumerate(d["candidates_considered"]):
        if c["action"] == "SWITCH" and d["accepted"] and c["target_presence"] not in allowed:
            out.add(
                f"$.candidates_considered[{index}].target_presence",
                f"{c['target_presence']} is below switch_min_presence {minimum}; the switch must be rejected (INSUFFICIENT_EVIDENCE)",
            )
        evidence = _evidence_by_hash(ctx, c["evidence_sha256"])
        if (
            evidence is not None
            and c["decided_by"] in ("RULE_ONLY", "RULE_FALLBACK")
            and c["action"] == "NEXT_CANDIDATE"
            and evidence.data["target_presence"] in allowed
        ):
            if evidence.data["entry_observation_id"] is not None:
                out.add(
                    f"$.candidates_considered[{index}].action",
                    "the rule must SWITCH to the first candidate that reaches switch_min_presence and has an entry_observation_id (§8.6 fallback step 2)",
                )
            elif c["exclusion_reason"] != "NO_ALIGNABLE_OBSERVATION":
                out.add(
                    f"$.candidates_considered[{index}].exclusion_reason",
                    "a guard-reaching candidate without entry_observation_id is recorded as NO_ALIGNABLE_OBSERVATION (§8.6 fallback step 3)",
                )


@check(
    "DECISION_REJECTION_CORRECTNESS",
    "§8.4",
    "decision_record",
    "A submission that violates the controller rules (unknown ref, stale snapshot, no evidence, no citation) was not accepted",
)
def _decision_rejection(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    sub = d["submitted"]
    if sub is None:
        raise NotApplicable("record has no submission")
    expected: list[str] = []
    snap = _snapshot_for(ctx, d)
    ref = sub.get("candidate_ref")
    if sub["action"] in ("SWITCH", "NEXT_CANDIDATE"):
        if snap is not None and ref not in {c["candidate_ref"] for c in snap.data["candidates"]}:
            expected.append("UNKNOWN_REF")
        entry = next((c for c in d["candidates_considered"] if c["candidate_ref"] == ref), None)
        if entry is None or not entry["evidence_sha256"]:
            expected.append("EVIDENCE_NOT_FETCHED")
    request = next(
        (a for a in ctx.of_kind("agent_decision") if a.data.get("decision_id") == d["decision_id"]),
        None,
    )
    if request is not None:
        if request.data["candidate_snapshot_sha256"] != d["candidate_snapshot_sha256"]:
            expected.append("STALE_SNAPSHOT")
        if request.data["action"] == "SWITCH" and not request.data["cited_observation_ids"]:
            expected.append("UNCITED_OR_FOREIGN_REF")
    elif snap is None:
        raise NoContext("neither the agent-decision request nor the snapshot was supplied")
    if expected and d["accepted"]:
        out.add(
            "$.accepted",
            f"controller should have rejected this submission ({', '.join(sorted(set(expected)))})",
        )


@check(
    "DECISION_BUDGET_LIMITS",
    "§8.6, §11",
    "decision_record",
    "rounds_used / budget_used_ms respect agent_max_rounds / agent_total_budget_ms unless the matching fallback is recorded",
)
def _decision_budget(doc: Doc, ctx: Ctx, out: Findings) -> None:
    p = ctx.numeric("agent_max_rounds", "agent_total_budget_ms")
    d = doc.data
    if d["switch_mode"] == "RULE_ONLY":
        return
    if d["rounds_used"] > p["agent_max_rounds"] and d["fallback_reason"] != "ROUND_LIMIT":
        out.add(
            "$.rounds_used",
            f"{d['rounds_used']} > agent_max_rounds {p['agent_max_rounds']} without ROUND_LIMIT fallback",
        )
    if d["fallback_reason"] == "ROUND_LIMIT" and d["rounds_used"] < p["agent_max_rounds"]:
        out.add("$.fallback_reason", "ROUND_LIMIT recorded before the limit was reached")
    if d["budget_used_ms"] > p["agent_total_budget_ms"] and d["fallback_reason"] != "TIME_BUDGET":
        out.add(
            "$.budget_used_ms",
            f"{d['budget_used_ms']} > agent_total_budget_ms {p['agent_total_budget_ms']} without TIME_BUDGET fallback",
        )
    if d["fallback_reason"] == "TIME_BUDGET" and d["budget_used_ms"] < p["agent_total_budget_ms"]:
        out.add("$.fallback_reason", "TIME_BUDGET recorded before the budget was reached")


_TRANSITIONS = {
    None: {"PLAYING"},
    "PLAYING": {"TEMP_LOST", "ENDED"},
    "TEMP_LOST": {"PLAYING", "SEARCHING", "ENDED"},
    "SEARCHING": {"SEARCHING", "PLAYING", "RETURNED_TO_ORIGIN", "ENDED"},
    "SWITCHING": {"PLAYING", "ENDED"},
    "RETURNED_TO_ORIGIN": {"PLAYING", "SEARCHING", "ENDED"},
    "ENDED": set(),
}


@check(
    "SESSION_STATE_MACHINE",
    "§8.6",
    "decision_record",
    "Each record is a legal §8.6 transition; step_index strictly increases and source time never goes backwards within a session",
)
def _state_machine(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    allowed = set(_TRANSITIONS.get(d["state_before"], set()))
    if d["decided_by"] == "USER":
        allowed.add("PLAYING")  # manual re-pick (Q-18) is a USER decision
    if d["state_after"] not in allowed and d["state_after"] != "ENDED":
        out.add(
            "$.state_after",
            f"{d['state_before']} -> {d['state_after']} is not in the §8.6 transition table",
        )
    siblings = sorted(
        (r for r in ctx.of_kind("decision_record") if r.data["session_id"] == d["session_id"]),
        key=lambda r: (r.data["step_index"], r.path),
    )
    if sum(1 for r in siblings if r.data["step_index"] == d["step_index"]) > 1:
        out.add("$.step_index", "duplicate step_index in session (decisions are append-only)")
    position = next((i for i, r in enumerate(siblings) if r is doc), None)
    if position:
        prev = siblings[position - 1].data
        if d["source_time_us"] < prev["source_time_us"]:
            out.add("$.source_time_us", "source time moved backwards (§8.6)")


@check(
    "Q2_RESPONSE_VS_DECISIONS",
    "§2.3, §8.6, §8.7",
    "q2_response",
    "agent_used / agent_attempted / fallback_used / first fallback_reason / decision_source equal what the session's decision records imply",
)
def _q2_vs_decisions(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    records = sorted(
        (r.data for r in ctx.of_kind("decision_record") if r.data["session_id"] == d["session_id"]),
        key=lambda r: r["step_index"],
    )
    if not records:
        raise NoContext("no decision records for this session_id")
    used = any(r["decided_by"] == "AGENT" and r["accepted"] for r in records)
    attempted = any(r["llm_calls"] for r in records)
    reasons = [r["fallback_reason"] for r in records if r["fallback_reason"]]
    if d["agent_used"] is not used:
        out.add("$.agent_used", f"records imply {used}")
    if d["agent_attempted"] is not (attempted or used):
        out.add("$.agent_attempted", f"records imply {attempted or used}")
    if d["fallback_used"] is not bool(reasons):
        out.add("$.fallback_used", f"records imply {bool(reasons)}")
    if (d["fallback_reason"] or None) != (reasons[0] if reasons else None):
        out.add(
            "$.fallback_reason",
            f"first recorded fallback reason is {reasons[0] if reasons else None!r}",
        )
    switches = [
        r
        for r in records
        if r["accepted"] and r["executed_action"] in ("SWITCH", "RETURN_TO_ORIGIN")
    ]
    expected_source = switches[-1]["decided_by"] if switches else None
    if d["decision_source"] != expected_source:
        out.add("$.decision_source", f"last switching decision came from {expected_source!r}")
    req = ctx.sibling(doc, "q2_request")
    if (
        req is not None
        and req.data["switch_mode"] == "AGENT_SEQUENTIAL"
        and all(r["switch_mode"] == "RULE_ONLY" for r in records)
    ):
        if d["fallback_reason"] != "MODE_NOT_AUTHORIZED":
            out.add(
                "$.fallback_reason",
                "AGENT_SEQUENTIAL requested but the session ran RULE_ONLY: MODE_NOT_AUTHORIZED expected",
            )


@check(
    "Q2_SWITCH_CAMERA_LEGAL",
    "§5.4, §8.6",
    "q2_response",
    "Every SWITCH segment cites an accepted SWITCH decision whose snapshot candidate is exactly that camera, and starts at the evidence's entry_timestamp_us with the decision's entry_observation_id",
)
def _q2_switch_camera(doc: Doc, ctx: Ctx, out: Findings) -> None:
    records = {
        r.data["decision_id"]: r
        for r in ctx.of_kind("decision_record")
        if r.data["session_id"] == doc.data["session_id"]
    }
    if not records:
        raise NoContext("no decision records for this session_id")
    for index, seg in enumerate(doc.data["timeline"]):
        if seg["kind"] != "ON_CAMERA" or seg["entered_by"] != "SWITCH":
            continue
        rec = records.get(seg.get("decision_id"))
        path = f"$.timeline[{index}]"
        if rec is None:
            out.add(path, "SWITCH segment has no decision_id of a recorded decision")
            continue
        r = rec.data
        if not (r["accepted"] and r["executed_action"] == "SWITCH"):
            out.add(path, "decision was not an accepted SWITCH")
        if seg["decided_by"] != r["decided_by"]:
            out.add(f"{path}.decided_by", f"decision record says {r['decided_by']}")
        snap = _snapshot_for(ctx, r)
        if snap is None:
            out.note("candidate snapshot not supplied: camera legality not verified")
            continue
        cand = next(
            (
                c
                for c in snap.data["candidates"]
                if c["candidate_ref"] == r["executed_candidate_ref"]
            ),
            None,
        )
        if cand is None or cand["camera_id"] != seg["camera_id"]:
            out.add(
                f"{path}.camera_id",
                "camera is not the camera of the legal candidate that was accepted",
            )
        entry = next(
            (
                c
                for c in r["candidates_considered"]
                if c["candidate_ref"] == r["executed_candidate_ref"]
            ),
            None,
        )
        evidence = _evidence_by_hash(ctx, entry["evidence_sha256"]) if entry else None
        if evidence is not None and seg["range_us"][0] != evidence.data["entry_timestamp_us"]:
            out.add(
                f"{path}.range_us",
                f"a SWITCH segment starts at the evidence's entry_timestamp_us {evidence.data['entry_timestamp_us']}; the GAP before it extends until then (§8.3)",
            )
        if r["entry_observation_id"] is not None and r["entry_observation_id"] not in seg.get(
            "observation_ids", []
        ):
            out.add(
                f"{path}.observation_ids",
                "the entry_observation_id of the decision must be among the segment's observations (§8.6)",
            )


# ----------------------------------------------------------------------------- Q2 response


@check(
    "Q2_TIMELINE_STRUCTURE",
    "§8.7",
    "q2_response",
    "Timeline ordered, contiguous, half-open; GAP segments never carry a position; observation-driven ON_CAMERA segments; status matches the timeline",
)
def _q2_timeline(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    timeline = d["timeline"]
    if d["status"] == "NO_SEED" and timeline:
        out.add("$.timeline", "NO_SEED must have an empty timeline")
    if d["status"] in ("COMPLETE", "ENDED_BY_LIMIT") and not timeline:
        out.add("$.timeline", f"{d['status']} requires a timeline")
    previous = None
    for index, seg in enumerate(timeline):
        path = f"$.timeline[{index}]"
        if not valid_range(seg["range_us"]):
            out.add(f"{path}.range_us", "not a half-open range")
            continue
        if previous is not None and seg["range_us"][0] != previous:
            out.add(
                f"{path}.range_us",
                f"segments must be ordered, non-overlapping and contiguous (previous ended at {previous})",
            )
        previous = seg["range_us"][1]
        if seg["kind"] == "GAP":
            for key, _ in (
                (k, v)
                for k, v in seg.items()
                if re.search(r"position|xyz|trajectory|interpolat|world", k, re.IGNORECASE)
            ):
                if key != "position" or seg[key] is not None:
                    out.add(
                        f"{path}.{key}",
                        "no position may be drawn inside a blind gap (position must be null)",
                    )
        elif seg["entered_by"] == "SWITCH" and not seg.get("decision_id"):
            out.add(f"{path}.decision_id", "a SWITCH entry must cite its decision")
    ids = [s["segment_id"] for s in timeline]
    if len(ids) != len(set(ids)):
        out.add("$.timeline", "duplicate segment_id")
    ranges = (d["resolved_scope"] or {}).get("resolved_source_ranges_us") or []
    if (
        d["status"] == "COMPLETE"
        and timeline
        and len(ranges) == 1
        and valid_range(timeline[0]["range_us"])
        and valid_range(timeline[-1]["range_us"])
    ):
        want = ranges[0]["range_us"]
        if timeline[0]["range_us"][0] != want[0] or timeline[-1]["range_us"][1] != want[1]:
            out.add("$.timeline", f"COMPLETE timeline must cover the whole resolved range {want}")


# ----------------------------------------------------------------------------- agent decision requests


@check(
    "AGENT_DECISION_FORMAT",
    "§8.4",
    "agent_decision",
    "Submission has a well-formed candidate_ref bound to its snapshot, citations for SWITCH, and a rationale for NEXT_CANDIDATE",
)
def _agent_decision(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    ref = d["candidate_ref"]
    if d["action"] in ("SWITCH", "NEXT_CANDIDATE") and ref is None:
        out.add("$.candidate_ref", f"{d['action']} needs a candidate_ref")
    if ref is not None and not re.fullmatch(r"cand:[0-9a-f]{16}:\d+", ref):
        out.add("$.candidate_ref", "expected cand:<snapshot_hash16>:<n>")
    if d["action"] == "NEXT_CANDIDATE" and not d["rationale"].strip():
        out.add("$.rationale", "declining a legal candidate must record its reason (§8.4)")
    out.note(
        "a submission may be deliberately illegal; legality is verified on the decision record (DECISION_REJECTION_CORRECTNESS)"
    )


# ----------------------------------------------------------------------------- graphs (§5)


@check(
    "GRAPH_STRUCTURE",
    "§5.1–§5.3",
    GRAPH_KINDS,
    "Graph ids unique, references resolve inside the graph, closed lists respected, approval fields coherent",
)
def _graph_structure(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    if d["approval_status"] == "APPROVED" and not d["approval_ref"]:
        out.add(
            "$.approval_ref",
            "APPROVED graph needs an approval_ref (r003 approvals do not carry over)",
        )
    if d["approval_status"] == "DRAFT" and d["approval_ref"]:
        out.add("$.approval_ref", "DRAFT graph must not cite an approval")
    if doc.kind == "region_graph":
        regions = [r["region_id"] for r in d["regions"]]
        if len(regions) != len(set(regions)):
            out.add("$.regions", "duplicate region_id")
        edge_ids = [e["edge_id"] for e in d["edges"]]
        if len(edge_ids) != len(set(edge_ids)):
            out.add("$.edges", "duplicate edge_id")
        for i, e in enumerate(d["edges"]):
            if any(r not in regions for r in e["regions"]):
                out.add(f"$.edges[{i}].regions", "references a region that is not defined")
            if e["via"]["kind"] == "STAIR":
                out.add(f"$.edges[{i}].via.kind", "STAIR is not used in v1 (stairs: [])")
            if e["direction"] == "ONE_WAY" and (
                e.get("from") not in e["regions"]
                or e.get("to") not in e["regions"]
                or e.get("from") == e.get("to")
            ):
                out.add(f"$.edges[{i}]", "ONE_WAY needs from/to naming the two regions")
            if e["direction"] == "BIDIRECTIONAL" and ("from" in e or "to" in e):
                out.add(f"$.edges[{i}]", "BIDIRECTIONAL must not carry from/to")
        return
    cameras = [c["camera_id"] for c in d["cameras"]]
    if len(cameras) != len(set(cameras)):
        out.add("$.cameras", "duplicate camera_id")
    exit_ids = {z["exit_zone_id"]: c["camera_id"] for c in d["cameras"] for z in c["exit_zones"]}
    entry_ids = {z["entry_zone_id"]: c["camera_id"] for c in d["cameras"] for z in c["entry_zones"]}
    for ci, c in enumerate(d["cameras"]):
        for zi, z in enumerate(c["exit_zones"]):
            if z["mapping_basis"] == "MANUAL_ON_STATIC_FRAME" and not (
                z.get("static_frame_ref") and z.get("static_frame_sha256")
            ):
                out.add(
                    f"$.cameras[{ci}].exit_zones[{zi}]",
                    "manual ROI needs static_frame_ref and static_frame_sha256 (person-free frame)",
                )
    ids = [t["transition_id"] for t in d["transitions"]]
    if len(ids) != len(set(ids)):
        out.add("$.transitions", "duplicate transition_id")
    for i, t in enumerate(d["transitions"]):
        p = f"$.transitions[{i}]"
        if t["from_camera_id"] not in cameras or t["to_camera_id"] not in cameras:
            out.add(p, "transition references an undefined camera")
        if t["from_camera_id"] == t["to_camera_id"]:
            out.add(p, "transition must connect two different cameras")
        for z in t["via_exit_zone_ids"]:
            if exit_ids.get(z) != t["from_camera_id"]:
                out.add(
                    f"{p}.via_exit_zone_ids", f"{z} is not an exit zone of {t['from_camera_id']}"
                )
        for z in t["to_entry_zone_ids"]:
            if entry_ids.get(z) != t["to_camera_id"]:
                out.add(
                    f"{p}.to_entry_zone_ids", f"{z} is not an entry zone of {t['to_camera_id']}"
                )
        if t["ranking_area_m2"] is not None and not t["ranking_area_refs"]:
            out.add(
                f"{p}.ranking_area_refs",
                "a ranking_area_m2 value must come with its geometry / calibration / visibility refs (§5.3)",
            )
        if t["region_hops"] != len(t["region_path"]) - 1:
            out.add(f"{p}.region_hops", "must equal len(region_path) - 1")
        if len(t["edge_path"]) != len(t["region_path"]) - 1:
            out.add(f"{p}.edge_path", "one edge per hop is required")
        if (
            t["path_traversability"] == "TOPOLOGICAL_ONLY"
            and t["nominal_path_length_m"] is not None
        ):
            out.add(
                f"{p}.nominal_path_length_m", "no nominal length without approved walkable geometry"
            )


@check(
    "GRAPH_CROSS_REFERENCES",
    "§5.2, §5.3",
    "camera_graph",
    "Camera graph agrees with its region graph: hash link, paths follow edges, traversability is the weakest edge, unknown state propagates",
)
def _graph_cross(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    rg = ctx.by_hash("region_graph", d["region_graph_sha256"])
    if rg is None:
        if ctx.of_kind("region_graph"):
            out.add("$.region_graph_sha256", "matches none of the supplied region graphs")
            return
        raise NoContext("region graph not supplied")
    regions = {r["region_id"] for r in rg.data["regions"]}
    edges = {e["edge_id"]: e for e in rg.data["edges"]}
    for ci, c in enumerate(d["cameras"]):
        for ri, r in enumerate(c["covered_regions"]):
            if r["region_id"] not in regions:
                out.add(f"$.cameras[{ci}].covered_regions[{ri}]", "undefined region")
        for zi, z in enumerate(c["exit_zones"]):
            for e in z["leads_to_edge_ids"]:
                if e not in edges:
                    out.add(
                        f"$.cameras[{ci}].exit_zones[{zi}].leads_to_edge_ids",
                        f"{e} is not an edge of the region graph",
                    )
    for i, t in enumerate(d["transitions"]):
        p = f"$.transitions[{i}]"
        if any(r not in regions for r in t["region_path"]):
            out.add(f"{p}.region_path", "undefined region")
        path_edges = []
        for hop, eid in enumerate(t["edge_path"]):
            e = edges.get(eid)
            if e is None:
                out.add(f"{p}.edge_path", f"{eid} is not an edge of the region graph")
                continue
            path_edges.append(e)
            if hop + 1 < len(t["region_path"]) and set(e["regions"]) != {
                t["region_path"][hop],
                t["region_path"][hop + 1],
            }:
                out.add(
                    f"{p}.edge_path[{hop}]",
                    "edge does not connect the consecutive regions of region_path",
                )
            if e["state"] == "CLOSED":
                out.add(f"{p}.edge_path[{hop}]", "CLOSED edges never enter a transition")
        resolved = len(path_edges) == len(t["edge_path"])
        weakest = (
            "TOPOLOGICAL_ONLY"
            if any(e["traversability"] == "TOPOLOGICAL_ONLY" for e in path_edges)
            else "APPROVED_WALKABLE"
            if resolved and all(e["traversability"] == "APPROVED_WALKABLE" for e in path_edges)
            else None
        )
        if weakest and t["path_traversability"] != weakest:
            out.add(f"{p}.path_traversability", f"weakest edge implies {weakest}")
        if weakest is None and t["path_traversability"] == "APPROVED_WALKABLE":
            out.add(
                f"{p}.path_traversability",
                "APPROVED_WALKABLE requires every edge to be APPROVED_WALKABLE",
            )
        if path_edges and t["path_has_unknown_state"] is not any(
            e["state"] == "UNKNOWN" for e in path_edges
        ):
            out.add(
                f"{p}.path_has_unknown_state", "must be true exactly when an edge has state UNKNOWN"
            )


# ----------------------------------------------------------------------------- clock mapping (§3.1)


@check(
    "CLOCK_MAPPING_RULES",
    "§3.1",
    "clock_mapping",
    "wall_origin's UTC offset matches the declared IANA timezone on that date; declared (not observed) clock",
)
def _clock_mapping(doc: Doc, ctx: Ctx, out: Findings) -> None:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    d = doc.data
    try:
        origin = datetime.fromisoformat(d["wall_origin"])
        zone = ZoneInfo(d["timezone"])
    except ZoneInfoNotFoundError:
        out.add("$.timezone", f"{d['timezone']!r} is not an IANA timezone known to this system")
        return
    except (KeyError, ValueError) as exc:
        out.add("$.wall_origin", f"unparsable: {exc}")
        return
    # Judge the explicit offset by the instant it names (§3.1), not by a local-time
    # lookup: that would discard the offset's fold and reject the second occurrence
    # of a DST fall-back hour, and would accept offsets in a spring-forward gap.
    actual = origin.utcoffset()
    expected = origin.astimezone(zone).utcoffset() if actual is not None else None
    if actual is None or actual != expected:
        out.add(
            "$.wall_origin",
            f"offset {actual} does not match {d['timezone']} at that instant ({expected}); fail closed",
        )
    if d["t0_us"] >= d["source_duration_us"]:
        out.add("$.t0_us", "t0_us must lie inside the run's source range")


# ----------------------------------------------------------------------------- detection index (§4)


@check(
    "INDEX_MANIFEST_RULES",
    "§4.2, §4.4",
    "detection_index",
    "Per-camera sampled / inferred ranges are half-open, ordered, inferred within sampled, not_inferred disjoint from inferred; index_interval_us = stride_samples x source_frame_interval_us; detector class_map / nms / load rules; one content_sha256 per index_id",
)
def _index_manifest(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    det = d["detector"]
    class_map = det["class_map"]
    if class_map["source_file_sha256"] == class_map["content_sha256"]:
        out.add(
            "$.detector.class_map.content_sha256",
            "the canonical class-map hash must not be replaced by the source-file hash (§4.2)",
        )
    if det["load"]["num_classes"] != class_map["num_classes"]:
        out.add(
            "$.detector.load.num_classes",
            f"load.num_classes {det['load']['num_classes']} differs from class_map.num_classes {class_map['num_classes']} (§4.2)",
        )
    if det["nms"]["applied"] is False and det["nms"]["iou"] is not None:
        out.add("$.detector.nms.iou", "nms.applied is false, so iou must be null (§4.2)")
    for other in ctx.of_kind("detection_index"):
        if (
            other is not doc
            and isinstance(other.data, dict)
            and other.data.get("index_id") == d["index_id"]
            and other.data.get("content_sha256") != d["content_sha256"]
        ):
            out.add(
                "$.content_sha256",
                f"{other.path} has the same index_id but a different content_sha256: DataIntegrityError, never overwrite (§2.2)",
            )
    cameras = [c["camera_id"] for c in d["sampling"]["per_camera"]]
    if len(cameras) != len(set(cameras)):
        out.add("$.sampling.per_camera", "duplicate camera_id")
    labels = d["color_method"]["color_vocabulary"]["labels"]
    if len(labels) != len(set(labels)):
        out.add("$.color_method.color_vocabulary.labels", "duplicate colour label")
    for i, cam in enumerate(d["sampling"]["per_camera"]):
        p = f"$.sampling.per_camera[{i}]"
        if cam["index_interval_us"] != cam["stride_samples"] * cam["source_frame_interval_us"]:
            out.add(
                f"{p}.index_interval_us",
                f"{cam['index_interval_us']} != stride_samples {cam['stride_samples']} x source_frame_interval_us {cam['source_frame_interval_us']} (§4.4)",
            )
        for key in ("sampled_ranges_us", "inferred_ranges_us"):
            problem = ranges_sorted_disjoint(cam[key])
            if problem:
                out.add(f"{p}.{key}", problem)
        sampled, inferred = cam["sampled_ranges_us"], cam["inferred_ranges_us"]
        for r in inferred:
            if not any(s[0] <= r[0] and r[1] <= s[1] for s in sampled if valid_range(s)):
                out.add(f"{p}.inferred_ranges_us", f"{r} is not inside any sampled range")
        for n in cam["not_inferred"]:
            if any(
                n["range_us"][0] < r[1] and r[0] < n["range_us"][1]
                for r in inferred
                if valid_range(r)
            ):
                out.add(f"{p}.not_inferred", f"{n['range_us']} overlaps inferred time")
            if not n["reason"]:
                out.add(f"{p}.not_inferred", "reason required")


@check(
    "INDEX_RECORDS_FILE_HASH",
    "§4.2",
    "detection_index",
    "records_file_sha256 equals the SHA-256 of the supplied records file",
)
def _index_records_hash(doc: Doc, ctx: Ctx, out: Findings) -> None:
    name = Path(doc.data["records_ref"]).name
    records = [r for r in ctx.of_kind("detection_records") if Path(r.path).name == name]
    if not records:
        raise NoContext(f"records file {name!r} not supplied")
    if records[0].file_sha256 != doc.data["records_file_sha256"]:
        out.add(
            "$.records_file_sha256",
            f"declared {doc.data['records_file_sha256']}, file is {records[0].file_sha256}",
        )


def _manifest(ctx: Ctx, records: Doc) -> Doc | None:
    for m in ctx.of_kind("detection_index"):
        if Path(m.data["records_ref"]).name == Path(records.path).name:
            return m
    found = ctx.of_kind("detection_index")
    return found[0] if len(found) == 1 else None


@check(
    "RECORDS_FRAME_STATE",
    "§4.3, §6.3",
    "detection_records",
    "frame_state is closed; only INFERRED has a detections array (empty = no detection); NOT_INFERRED has a reason; records sorted and unique",
)
def _records_state(doc: Doc, ctx: Ctx, out: Findings) -> None:
    keys = []
    for i, r in enumerate(doc.data):
        p = f"$[{i}]"
        state, dets = r["frame_state"], r["detections"]
        if state == "INFERRED" and not isinstance(dets, list):
            out.add(f"{p}.detections", "INFERRED frames carry an array (empty means no detection)")
        if state != "INFERRED" and dets is not None:
            out.add(
                f"{p}.detections",
                f"{state} must have detections null (never read it as 'no detection')",
            )
        if state == "NOT_INFERRED" and not r["state_reason"]:
            out.add(f"{p}.state_reason", "NOT_INFERRED needs a state_reason")
        m = re.fullmatch(r"frame:([^:]+):([^:]+):(\d+)", r["frame_ref"])
        if m and (m.group(2) != r["camera_id"] or int(m.group(3)) != r["frame_index"]):
            out.add(f"{p}.frame_ref", "does not match camera_id / frame_index")
        if state == "MISSING" and r["rgb_file_sha256"] is not None:
            out.add(f"{p}.rgb_file_sha256", "a MISSING frame has no file hash")
        keys.append((r["camera_id"], r["frame_index"]))
    if keys != sorted(keys):
        out.add("$", "records must be sorted by (camera_id, frame_index)")
    if len(keys) != len(set(keys)):
        out.add("$", "duplicate (camera_id, frame_index)")
    if len(doc.data) > 2000:
        out.note("only the first 2000 records were validated")


@check(
    "RECORDS_OBSERVATION_IDS",
    "§2.2, §4.3",
    "detection_records",
    "observation_id follows obs:<hash16>:<camera>:<frame>:<ordinal> where <hash16> is the hash segment of the manifest's index_id; ordinals 0..n-1 by score desc then bbox; boxes valid",
)
def _records_ids(doc: Doc, ctx: Ctx, out: Findings) -> None:
    segments: set[str] = set()
    for i, r in enumerate(doc.data[:2000]):
        dets = r["detections"] or []
        order = [(-x["score"], tuple(x["bbox_xyxy_px"])) for x in dets]
        if order != sorted(order):
            out.add(f"$[{i}].detections", "must be ordered by score desc, then bbox ascending")
        for j, x in enumerate(dets):
            m = re.fullmatch(r"obs:([0-9a-f]{16}):([^:]+):(\d+):(\d+)", x["observation_id"])
            if (
                not m
                or m.group(2) != r["camera_id"]
                or int(m.group(3)) != r["frame_index"]
                or int(m.group(4)) != j
            ):
                out.add(
                    f"$[{i}].detections[{j}].observation_id",
                    "must be obs:<hash16>:<camera>:<frame>:<ordinal> with ordinal = position",
                )
            else:
                segments.add(m.group(1))
            b = x["bbox_xyxy_px"]
            if not (b[0] < b[2] and b[1] < b[3]):
                out.add(
                    f"$[{i}].detections[{j}].bbox_xyxy_px",
                    "x_min < x_max and y_min < y_max required",
                )
    if len(segments) > 1:
        out.add("$", f"observation ids mix several index hash segments: {sorted(segments)}")
    manifest = _manifest(ctx, doc)
    if manifest is None:
        out.note("manifest not supplied: the hash segment was not compared with the index key")
    else:
        expected = str(manifest.data["index_id"]).rsplit(":", 1)[-1]
        for segment in sorted(segments - {expected}):
            out.add(
                "$",
                f"observation id segment {segment} is not the hash segment {expected} of the manifest's index_id (§2.2)",
            )


@check(
    "RECORDS_INDEX_GRID",
    "§4.4",
    "detection_records",
    "Frames on the index grid (index_grid_origin_frame + n x stride_samples) are never NOT_SAMPLED; frames off the grid are NOT_SAMPLED",
)
def _records_grid(doc: Doc, ctx: Ctx, out: Findings) -> None:
    manifest = _manifest(ctx, doc)
    if manifest is None:
        raise NoContext("manifest not supplied")
    cams = {c["camera_id"]: c for c in manifest.data["sampling"]["per_camera"]}
    for i, r in enumerate(doc.data[:2000]):
        cam = cams.get(r["camera_id"])
        if cam is None:
            continue  # RECORDS_MATCH_MANIFEST reports undeclared cameras
        rel = r["frame_index"] - cam["index_grid_origin_frame"]
        on_grid = rel >= 0 and rel % cam["stride_samples"] == 0
        if on_grid and r["frame_state"] == "NOT_SAMPLED":
            out.add(
                f"$[{i}].frame_state",
                f"frame {r['frame_index']} is on the index grid but NOT_SAMPLED: DataIntegrityError (§4.4)",
            )
        if not on_grid and r["frame_state"] != "NOT_SAMPLED":
            out.add(
                f"$[{i}].frame_state",
                f"frame {r['frame_index']} is off the index grid, so it can only be NOT_SAMPLED, got {r['frame_state']}",
            )


@check(
    "RECORDS_COLOR_RULES",
    "§4.3",
    "detection_records",
    "Colour only on applies_to_classes; verdicts cover the whole vocabulary; UNKNOWN verdicts carry unknown_reason; score range",
)
def _records_color(doc: Doc, ctx: Ctx, out: Findings) -> None:
    manifest = _manifest(ctx, doc)
    classes = manifest.data["color_method"]["applies_to_classes"] if manifest else None
    vocab = set(manifest.data["color_method"]["color_vocabulary"]["labels"]) if manifest else None
    if manifest is None:
        out.note("manifest not supplied: applies_to_classes and vocabulary not verified")
    for i, r in enumerate(doc.data[:2000]):
        for j, x in enumerate(r["detections"] or []):
            p, c = f"$[{i}].detections[{j}]", x["color"]
            if classes is not None and x["class_label"] not in classes and c is not None:
                out.add(
                    f"{p}.color",
                    f"colour computed for class {x['class_label']!r}, which is not in applies_to_classes",
                )
            if classes is not None and x["class_label"] in classes and c is None:
                out.add(f"{p}.color", "applies_to_classes detection without a colour summary")
            if c is None:
                continue
            if vocab is not None and set(c["verdicts"]) != vocab:
                out.add(f"{p}.color.verdicts", f"must have exactly the vocabulary {sorted(vocab)}")
            if "UNKNOWN" in c["verdicts"].values() and not c["unknown_reason"]:
                out.add(f"{p}.color.unknown_reason", "UNKNOWN verdict needs an unknown_reason")


@check(
    "RECORDS_MATCH_MANIFEST",
    "§4.3, §4.4",
    "detection_records",
    "INFERRED frames lie inside inferred_ranges_us of their camera; every camera is declared in the manifest",
)
def _records_manifest(doc: Doc, ctx: Ctx, out: Findings) -> None:
    manifest = _manifest(ctx, doc)
    if manifest is None:
        raise NoContext("manifest not supplied")
    cams = {c["camera_id"]: c for c in manifest.data["sampling"]["per_camera"]}
    for i, r in enumerate(doc.data[:2000]):
        cam = cams.get(r["camera_id"])
        if cam is None:
            out.add(f"$[{i}].camera_id", "camera not declared in the manifest")
            continue
        stamp = r["timestamp_us"]
        inside = any(a <= stamp < b for a, b in cam["inferred_ranges_us"])
        if r["frame_state"] == "INFERRED" and not inside:
            out.add(f"$[{i}].frame_state", "INFERRED frame outside the camera's inferred_ranges_us")
        if r["frame_state"] == "NOT_INFERRED" and inside:
            out.add(f"$[{i}].frame_state", "NOT_INFERRED frame inside inferred_ranges_us")


@check(
    "RECORDS_SCORE_FLOOR",
    "§4.2, §11",
    "detection_records",
    "No stored detection scores below index_score_floor",
)
def _records_floor(doc: Doc, ctx: Ctx, out: Findings) -> None:
    floor = _floor(ctx)
    for i, r in enumerate(doc.data[:2000]):
        for j, x in enumerate(r["detections"] or []):
            if x["score"] < floor:
                out.add(
                    f"$[{i}].detections[{j}].score", f"{x['score']} < index_score_floor {floor}"
                )


@check(
    "PROBE_FORBIDDEN_FIELD_REJECTED",
    "§6.1, §9, v1.1 §7",
    "*",
    "(base-url mode) A request carrying a forbidden extra field is rejected with HTTP 422 FORBIDDEN_INFERENCE_INPUT",
)
def _probe(doc: Doc, ctx: Ctx, out: Findings) -> None:
    if doc.role != "probe":
        raise NotApplicable("not a probe response")
    data = doc.data if isinstance(doc.data, dict) else {}
    if doc.kind != "error_response" or data.get("error_code") != "FORBIDDEN_INFERENCE_INPUT":
        out.add(
            "$",
            "a request with a forbidden extra field was not rejected with FORBIDDEN_INFERENCE_INPUT",
        )
    elif data.get("http_status") not in (None, 422):
        out.add("$.http_status", f"expected 422, got {data.get('http_status')}")


# ----------------------------------------------------------------------------- evidence, entry, links (§8.2, §8.3)

OBS_RE = re.compile(r"obs:([0-9a-f]{16}):([^:]+):(\d+):(\d+)")


def _evidence_by_hash(ctx: Ctx, sha: str | None) -> Doc | None:
    return ctx.by_hash("candidate_evidence", sha, "evidence_sha256") if sha else None


def _observation_times(ctx: Ctx) -> dict[str, int]:
    return {
        x["observation_id"]: r["timestamp_us"]
        for doc in ctx.of_kind("detection_records")
        for r in doc.data
        for x in r["detections"] or []
    }


@check(
    "EVIDENCE_PRESENCE_RULES",
    "§8.3",
    "candidate_evidence",
    "frames / coverage_complete / target_presence follow the §8.3 judging order (NOT_EVALUATED first, empty window never covered, NONE+UNKNOWN is not a colour mismatch, partial coverage never negative); entry observation not before decision_time_us",
)
def _evidence(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    frames, presence = d["frames"], d["target_presence"]
    evaluated = frames["evaluated"]
    expected_cells = (
        evaluated + frames["not_inferred"] + frames["missing"]
    )  # N; not_sampled is not counted
    verdicts = [o["color_verdict"] for o in d["best_observations"]]
    complete = expected_cells > 0 and evaluated == expected_cells
    if d["coverage_complete"] is not complete:
        out.add(
            "$.coverage_complete",
            f"must be {complete}: N = evaluated + not_inferred + missing = {expected_cells}, evaluated = {evaluated}; an empty window (N == 0) is never complete",
        )
    if (presence == "NOT_EVALUATED") != (evaluated == 0):
        out.add(
            "$.target_presence",
            "NOT_EVALUATED exactly when evaluated == 0 (it is judged first, including empty windows and all-NOT_INFERRED / MISSING windows)",
        )
    if evaluated == 0 and d["best_observations"]:
        out.add("$.best_observations", "nothing was evaluated, so there are no person boxes")
    if presence in ("NO_PERSON_DETECTED", "PERSON_NO_COLOR_MATCH") and not complete:
        out.add(
            "$.target_presence",
            f"{presence} is only valid with complete coverage; with 0 < evaluated < N it is PARTIAL_EVIDENCE",
        )
    if presence == "PARTIAL_EVIDENCE":
        if not 0 < evaluated < expected_cells:
            out.add("$.target_presence", "PARTIAL_EVIDENCE requires 0 < evaluated < N")
        if d["partial_basis"] not in ("PERSON_NO_COLOR_MATCH", "NO_PERSON_DETECTED"):
            out.add("$.partial_basis", "PARTIAL_EVIDENCE needs a partial_basis")
        if any(v != "NONE" for v in verdicts):
            out.add(
                "$.best_observations",
                "PARTIAL_EVIDENCE covers only all-NONE person boxes or no boxes; STRONG / WEAK / UNKNOWN give another value",
            )
    elif d["partial_basis"] is not None:
        out.add(
            "$.partial_basis", "partial_basis is null unless target_presence is PARTIAL_EVIDENCE"
        )
    if presence == "NO_PERSON_DETECTED" and d["best_observations"]:
        out.add("$.best_observations", "NO_PERSON_DETECTED has no person box")
    if presence == "MATCH_STRONG" and "STRONG" not in verdicts:
        out.add("$.best_observations", "MATCH_STRONG needs a STRONG person box")
    if presence == "MATCH_WEAK" and ("STRONG" in verdicts or "WEAK" not in verdicts):
        out.add("$.best_observations", "MATCH_WEAK: no STRONG, at least one WEAK")
    if presence == "PERSON_COLOR_UNKNOWN" and ("STRONG" in verdicts or "WEAK" in verdicts):
        out.add("$.best_observations", "PERSON_COLOR_UNKNOWN: no STRONG or WEAK person box")
    if presence == "PERSON_NO_COLOR_MATCH" and any(v != "NONE" for v in verdicts):
        out.add(
            "$.target_presence",
            "PERSON_NO_COLOR_MATCH needs all person boxes NONE; NONE mixed with UNKNOWN is PERSON_COLOR_UNKNOWN (§8.3)",
        )
    entry_id, entry_ts = d["entry_observation_id"], d["entry_timestamp_us"]
    if (entry_id is None) != (entry_ts is None):
        out.add(
            "$.entry_timestamp_us",
            "entry_observation_id and entry_timestamp_us are both null or both set",
        )
    if entry_ts is not None:
        if entry_ts < d["decision_time_us"]:
            out.add(
                "$.entry_timestamp_us",
                "an entry observation before decision_time_us would make playback time go backwards (§8.3)",
            )
        window = d["window_us"]
        if valid_range(window) and not window[0] <= entry_ts < window[1]:
            out.add("$.entry_timestamp_us", "the entry observation must lie inside window_us")
        if presence not in PRESENCE_ORDER:
            out.add(
                "$.entry_observation_id",
                f"{presence} can never reach switch_min_presence, so there is no entry observation",
            )
    for snap in ctx.of_kind("candidate_snapshot"):
        cand = next(
            (c for c in snap.data["candidates"] if c["candidate_ref"] == d["candidate_ref"]), None
        )
        if cand is not None and (
            cand["camera_id"] != d["camera_id"] or cand["window_us"] != d["window_us"]
        ):
            out.add("$.window_us", "camera_id / window_us differ from the snapshot candidate")
    out.note(
        "evidence_sha256 is only used as a link value: the contract does not state its preimage (U26)"
    )


@check(
    "DECISION_EVIDENCE_AND_ENTRY",
    "§8.3, §8.6, §8.7",
    "decision_record",
    "decision_time_us <= source_time_us; an accepted SWITCH has an entry_observation_id that matches the candidate's evidence; considered candidates match their evidence summary",
)
def _decision_entry(doc: Doc, ctx: Ctx, out: Findings) -> None:
    d = doc.data
    decision_time = d["decision_time_us"]
    if decision_time is not None and d["source_time_us"] < decision_time:
        out.add(
            "$.source_time_us", "source time is before decision_time_us (it never goes backwards)"
        )
    if d["accepted"] and d["executed_action"] == "SWITCH":
        if d["entry_observation_id"] is None:
            out.add(
                "$.entry_observation_id",
                "an accepted SWITCH enters at the evidence's entry_observation_id; with null it is INSUFFICIENT_EVIDENCE (§8.4)",
            )
        if decision_time is None:
            out.add(
                "$.decision_time_us",
                "a SWITCH happens inside a SEARCHING, so decision_time_us is set",
            )
    for index, c in enumerate(d["candidates_considered"]):
        evidence = _evidence_by_hash(ctx, c["evidence_sha256"])
        if evidence is None:
            continue
        e = evidence.data
        path = f"$.candidates_considered[{index}]"
        if e["candidate_ref"] != c["candidate_ref"]:
            out.add(f"{path}.candidate_ref", "differs from the evidence summary it cites")
        if e["target_presence"] != c["target_presence"]:
            out.add(f"{path}.target_presence", "differs from the evidence summary it cites")
        if decision_time is not None and e["decision_time_us"] != decision_time:
            out.add(f"{path}.evidence_sha256", "the evidence was taken at another decision_time_us")
        if (
            d["accepted"]
            and c["action"] == "SWITCH"
            and c["candidate_ref"] == d["executed_candidate_ref"]
            and e["entry_observation_id"] != d["entry_observation_id"]
        ):
            out.add(
                "$.entry_observation_id",
                f"the SWITCH must enter at the evidence's entry_observation_id {e['entry_observation_id']!r}",
            )


def _index_cameras(ctx: Ctx) -> dict[str, dict[str, Any]]:
    return {
        c["camera_id"]: c
        for m in ctx.of_kind("detection_index")
        for c in m.data["sampling"]["per_camera"]
    }


@check(
    "LINK_RECORD_GAP_RULES",
    "§8.2",
    "link_records",
    "elapsed_us is a positive multiple of the camera's index_interval_us; gap_samples = elapsed_us / index_interval_us (the current mismatching cell counts) and one less for LINKED",
)
def _link_records(doc: Doc, ctx: Ctx, out: Findings) -> None:
    cams = _index_cameras(ctx)
    if not cams:
        raise NoContext("detection index manifest not supplied")
    for i, r in enumerate(doc.data):
        m = OBS_RE.fullmatch(r["prev_observation_id"])
        cam = cams.get(m.group(2)) if m else None
        if cam is None:
            out.add(
                f"$[{i}].prev_observation_id", "camera of the observation is not in the manifest"
            )
            continue
        interval = cam["index_interval_us"]
        if r["elapsed_us"] % interval:
            out.add(
                f"$[{i}].elapsed_us",
                f"{r['elapsed_us']} is not a multiple of index_interval_us {interval}",
            )
            continue
        cells = r["elapsed_us"] // interval
        expected = cells - 1 if r["decision"] == "LINKED" else cells
        if r["gap_samples"] != expected:
            out.add(
                f"$[{i}].gap_samples",
                f"expected {expected}: gap_samples counts unlinked index cells after the last linked observation up to and including the current mismatching cell; a LINKED cell is not counted (elapsed {r['elapsed_us']} / interval {interval} = {cells})",
            )


@check(
    "SEARCHING_TRIGGER_TIME",
    "§8.2, §8.3, §8.6, §11",
    "decision_record",
    "decision_time_us is the time of the first unlinked index cell with gap_samples > link_max_gap_samples (elapsed_us >= link_max_gap_us, N derived as link_max_gap_us / index_interval_us - 1)",
)
def _searching_trigger(doc: Doc, ctx: Ctx, out: Findings) -> None:
    decision_time = doc.data["decision_time_us"]
    if decision_time is None:
        raise NotApplicable("no SEARCHING started in this record")
    gap_us = ctx.numeric("link_max_gap_us")["link_max_gap_us"]
    links = ctx.sibling(doc, "link_records")
    if links is None:
        raise NoContext("no link records for this session (<stem>.links.jsonl)")
    cams, times = _index_cameras(ctx), _observation_times(ctx)
    best: dict[
        str, tuple[int, int]
    ] = {}  # prev observation -> (gap_samples, time) of the first trigger
    for r in links.data:
        m = OBS_RE.fullmatch(r["prev_observation_id"])
        cam = cams.get(m.group(2)) if m else None
        if cam is None or r["prev_observation_id"] not in times:
            raise NoContext("prev_observation_id is not in the supplied manifest / records")
        interval = cam["index_interval_us"]
        if gap_us % interval:
            raise NoContext(
                "link_max_gap_us is not a multiple of index_interval_us: PARAMETER_GRID_MISMATCH (see Q2_FAIL_CLOSED_ON_GRID_MISMATCH)"
            )
        max_samples = gap_us // interval - 1
        if r["decision"] != "LINKED" and r["gap_samples"] > max_samples:
            key = r["prev_observation_id"]
            if key not in best or r["gap_samples"] < best[key][0]:
                best[key] = (r["gap_samples"], times[key] + r["elapsed_us"])
    triggers = sorted({time for _, time in best.values()})
    if decision_time not in triggers:
        out.add(
            "$.decision_time_us",
            f"{decision_time} is not the time of a first cell beyond link_max_gap_us {gap_us}; the link records give {triggers}",
        )


@check(
    "Q2_FAIL_CLOSED_ON_GRID_MISMATCH",
    "§8.2, §11",
    "q2_request",
    "If the parameter set and the index grid do not match (index_interval_us, link_max_gap_us a positive multiple of it, listed link_max_gap_samples = derived), the paired reply is PARAMETER_GRID_MISMATCH; otherwise it is not",
)
def _grid_fail_closed(doc: Doc, ctx: Ctx, out: Findings) -> None:
    pset = ctx.param_doc
    if pset is None or doc.data.get("parameter_set_id") != pset.data.get("parameter_set_id"):
        raise NoContext("the request's parameter set was not supplied")
    gap_us = ctx.numeric("link_max_gap_us")["link_max_gap_us"]
    reply = ctx.sibling(doc, "q2_response", "error_response")
    if reply is None:
        raise NoContext("no paired response")
    cameras = None
    if reply.kind == "q2_response":
        cameras = set((reply.data.get("resolved_scope") or {}).get("camera_ids") or []) or None
    problems = grid_problems(
        pset.data,
        gap_us,
        [m for m in ctx.of_kind("detection_index") if m.data["run_id"] in doc.data["run_ids"]],
        cameras,
    )
    closed = (
        reply.kind == "error_response" and reply.data.get("error_code") == "PARAMETER_GRID_MISMATCH"
    )
    if problems and not closed:
        for problem in problems:
            out.add(
                reply.path,
                f"{problem}: the service must fail closed with PARAMETER_GRID_MISMATCH, never round or pick the nearest cell count (§8.2)",
            )
    if not problems and closed:
        out.add(reply.path, "PARAMETER_GRID_MISMATCH although the grid and the parameter set match")
    out.note(
        "how PARAMETER_GRID_MISMATCH is returned (error code, status, reason) is not defined (U25)"
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def grid_problems(
    pset: dict[str, Any], gap_us: Any, manifests: list[Doc], cameras: set[str] | None
) -> list[str]:
    """Contract §8.2 grid check: the conditions under which the service must answer PARAMETER_GRID_MISMATCH."""

    problems: list[str] = []
    interval = (pset.get("applies_to") or {}).get("index_interval_us")
    if not _positive_int(interval):
        problems.append("applies_to.index_interval_us is not a positive integer")
    for m in manifests:
        for cam in m.data["sampling"]["per_camera"]:
            if cameras is not None and cam["camera_id"] not in cameras:
                continue
            if not _positive_int(cam["index_interval_us"]):
                problems.append(f"{cam['camera_id']}: index_interval_us is not a positive integer")
            elif _positive_int(interval) and cam["index_interval_us"] != interval:
                problems.append(
                    f"{cam['camera_id']}: index_interval_us {cam['index_interval_us']} differs from applies_to.index_interval_us {interval}"
                )
    if _positive_int(interval):
        if not _positive_int(gap_us) or gap_us % interval:
            problems.append(
                f"link_max_gap_us {gap_us} is not a positive integer multiple of index_interval_us {interval}"
            )
        else:
            listed = _param_values(pset).get("link_max_gap_samples")
            if _param_is_set(listed) and listed != gap_us // interval - 1:
                problems.append(
                    f"listed link_max_gap_samples {listed} differs from link_max_gap_us / index_interval_us - 1 = {gap_us // interval - 1}"
                )
    return problems


@check(
    "PARAMS_APPROVAL_GATES_STATUS",
    "§11",
    ("q1_response", "q2_response"),
    "A response built on a parameter set whose approval.status is not APPROVED is not READY/COMPLETE and says PARAMETERS_NOT_APPROVED",
)
def _params_gate(doc: Doc, ctx: Ctx, out: Findings) -> None:
    pset = ctx.param_doc
    scope = doc.data.get("resolved_scope") or {}
    if pset is None or scope.get("parameter_set_id") != pset.data.get("parameter_set_id"):
        raise NoContext("the response's parameter set was not supplied")
    if (pset.data.get("approval") or {}).get("status") == "APPROVED":
        return
    status = doc.data.get("status")
    if status in ("READY", "COMPLETE"):
        out.add("$.status", f"parameter set is not APPROVED; status must not be {status}")
    if status == "PARTIAL" and doc.data.get("reason") != "PARAMETERS_NOT_APPROVED":
        out.add(
            "$.reason", "PARTIAL on an unapproved parameter set must carry PARAMETERS_NOT_APPROVED"
        )


# ----------------------------------------------------------------------------- contract gaps

UNKNOWN_CONTRACT_ITEMS.extend(
    [
        {
            "id": "U01",
            "section": "§4.3",
            "issue": "Per-frame records have no schema_version; the records file name, location and format (JSONL vs array) are not defined.",
            "suggestion": "Add schema_version `q-demo.detection-record.v1` and state the file format.",
            "affects": "SCHEMA_VALID, RECORDS_*",
        },
        {
            "id": "U02",
            "section": "§4.2",
            "issue": "The manifest's class_map has only version and hash; the label list that Q1 support depends on is stored nowhere, and class_alias.json has no schema.",
            "suggestion": "Define class_map.labels (or a class_map file schema) and a q-demo.class-alias.v1 schema.",
            "affects": "Q1_SUPPORTED_SET_CONSISTENCY (kit uses its own supported-classes input)",
        },
        {
            "id": "U03",
            "section": "§2.3, §3.2, §6.3",
            "issue": "CLOCK_MAPPING_MISSING and TIME_EXPRESSION_INVALID are named as returns, but Q1/Q2 `status` lists do not contain them, and error responses (FORBIDDEN_INFERENCE_INPUT 422 etc.) have no body schema.",
            "suggestion": "Say whether these are statuses or error codes and define the error-response body.",
            "affects": "COMMON_STATUS_REASON, ERROR_RESPONSE_RULES",
        },
        {
            "id": "U04",
            "section": "§1–§8",
            "issue": "No HTTP endpoints or paths are defined for Q1, Q3 parse, Q2 or the Agent tools.",
            "suggestion": "Add an endpoint table (method, path, request and response schema_version).",
            "affects": "--base-url mode needs an --endpoint-map supplied by Codex",
        },
        {
            "id": "U05",
            "section": "§5.4, §8.4",
            "issue": "transition_candidates output has no schema: wrapper fields, ranking_basis shape, the name of the truncated-count field, the shape of window_truncated_us (§8.6) and the schema_version are not defined. (The hash rule is now defined: §2.2, candidate_snapshot_sha256.)",
            "suggestion": "Define q-demo.candidate-snapshot.v1 (wrapper, truncated count, window_truncated_us as a list of half-open ranges).",
            "affects": "CANDIDATE_* (kit uses a PROVISIONAL schema)",
        },
        {
            "id": "U06",
            "section": "§5.4 step 4",
            "issue": "Relationship between candidate_set_complete, truncated and a top_k cut is not stated (v1.1 §6.1 defines truncated as budget-only).",
            "suggestion": "State whether a top_k cut sets truncated or candidate_set_complete=false.",
            "affects": "CANDIDATE_REFS_AND_LIMITS (only count <= top_k is checked)",
        },
        {
            "id": "U08",
            "section": "§5.2",
            "issue": "traversability lists two values but §1 says unapproved passability is UNKNOWN; relation lists OVERLAP/BLIND_GAP but tier 4 (coverage / visible range / exit data missing) has no field to mark it; a BLIND_GAP whose path is neither all-OPEN APPROVED_WALKABLE nor has an UNKNOWN edge has no tier in §5.4; BIDIRECTIONAL/ADJACENT boundary-ref field names are not given.",
            "suggestion": "Add UNKNOWN to both closed lists (kit accepts it, and reads relation UNKNOWN as tier 4), define the tier of the remaining combination and name the ADJACENT boundary ref field.",
            "affects": "GRAPH_STRUCTURE",
        },
        {
            "id": "U09",
            "section": "§7.1, §7.3",
            "issue": "`parsed_by` values other than LLM, the `parser_mode` enum, the clarification/options shape, and where the rule parser's version and hash live in provenance are not defined.",
            "suggestion": "Define parsed_by (LLM|RULE), parser_mode enum and provenance.rule_parser {version, sha256}.",
            "affects": "Q3_RESPONSE_RULES, Q3_FALLBACK_CONSISTENCY",
        },
        {
            "id": "U10",
            "section": "§7.5",
            "issue": "The LLM explanation has no output schema, endpoint or schema_version; how its `content_sha256` is computed is not stated.",
            "suggestion": "Define q-demo.explanation.v1 {explains_output_sha256, text, cited_refs, fallback_reason, content_sha256}.",
            "affects": "EXPLANATION_CITED_REFS (PROVISIONAL schema)",
        },
        {
            "id": "U11",
            "section": "§8.2",
            "issue": "Link records are now fully listed (prev_observation_id, next_observation_id, iou, elapsed_us, gap_samples, decision, §8.2) but have no schema_version, file name or location, no session binding, and the contract does not say what next_observation_id / iou hold for a non-LINKED decision.",
            "suggestion": "Define q-demo.link-record.v1, the file (kit convention: <stem>.links.jsonl next to the decisions file) and the values of next_observation_id / iou when nothing is linked.",
            "affects": "LINK_RECORD_GAP_RULES, SEARCHING_TRIGGER_TIME (kit uses a PROVISIONAL schema and the link file convention)",
        },
        {
            "id": "U12",
            "section": "§8.7",
            "issue": "`budget_used_ms` sits inside the hashed body of decision-record, but §8.7 requires RULE_ONLY replays to have identical content_sha256; a measured value would break that.",
            "suggestion": "Move budget_used_ms under stats, or fix it to 0 for RULE_ONLY.",
            "affects": "CONTENT_HASH_RECOMPUTE (kit hashes it as written)",
        },
        {
            "id": "U13",
            "section": "§2.3, §8.7",
            "issue": "decisions_sha256 (Q2 response) has no definition (file hash or content hash, ordering); decision-record `rounds_used` does not say whether it is per decision or per SEARCHING episode; 'last switching decision' for decision_source does not say whether RETURN_TO_ORIGIN counts. (agent_used is defined since 1d1e061: an accepted AGENT step.)",
            "suggestion": "State each rule; the kit treats SWITCH and RETURN_TO_ORIGIN as switching decisions and does not recompute decisions_sha256.",
            "affects": "Q2_RESPONSE_VS_DECISIONS, DECISION_BUDGET_LIMITS",
        },
        {
            "id": "U14",
            "section": "§8.6, §2.3",
            "issue": "With MODE_NOT_AUTHORIZED the response is RULE_ONLY but fallback_used is true; it is not stated whether decision_source is RULE_ONLY or RULE_FALLBACK. (The ILLEGAL_CANDIDATE counter is per SEARCHING since 1d1e061.)",
            "suggestion": "State decision_source for MODE_NOT_AUTHORIZED.",
            "affects": "COMMON_AGENT_FIELDS, Q2_RESPONSE_VS_DECISIONS (kit accepts RULE_ONLY with fallback_used)",
        },
        {
            "id": "U15",
            "section": "§8.5, §8.7",
            "issue": "APPEARANCE seeds with several candidates need a user choice, but no response status or payload exists for 'awaiting seed selection'; NO_SEED does not say whether it may be returned when time coverage is partial.",
            "suggestion": "Add a status (e.g. SEED_SELECTION_REQUIRED) and say whether NO_SEED needs coverage_complete.",
            "affects": "Q2_TIMELINE_STRUCTURE (NO_SEED is not forced to coverage_complete)",
        },
        {
            "id": "U16",
            "section": "§6.3",
            "issue": "segment_merge_gap_us: whether the gap is measured between sample times or range ends, and strict vs inclusive, is not defined.",
            "suggestion": "Define the gap operator.",
            "affects": "no segment-merge check exists",
        },
        {
            "id": "U17",
            "section": "§2.2, §6.3",
            "issue": "query_id / query_sha256 / decision_id derivation from 'the normalised request' has no normalisation rule, so they cannot be recomputed.",
            "suggestion": "Specify the normalised-request canonical form.",
            "affects": "no query_id check exists",
        },
        {
            "id": "U18",
            "section": "§11",
            "issue": "parameter-set.v1 is defined (§11) but several §11 parameters have no machine name (crop ratio, HSV bands, exit rule, ...), the unit vocabulary is open, and the values of approval.status other than PROPOSED / APPROVED are not listed.",
            "suggestion": "Name every parameter and list the approval.status values.",
            "affects": "kit reads parameters[] by name; approval.status is kept a free string",
        },
        {
            "id": "U19",
            "section": "§4.3",
            "issue": "unknown_reason is one field per detection but verdicts are per colour; whether all verdicts must be UNKNOWN when it is set is not stated.",
            "suggestion": "State the relation.",
            "affects": "RECORDS_COLOR_RULES (only 'UNKNOWN => reason set' is enforced)",
        },
        {
            "id": "U23",
            "section": "§8.6, §8.7",
            "issue": "step_index counts steps, but only decisions are in the decisions file (link / TEMP_LOST steps are not), so records are not state-contiguous and step_index is not guaranteed consecutive.",
            "suggestion": "State whether the decisions file includes every step; the kit checks only that step_index increases and time never goes backwards.",
            "affects": "SESSION_STATE_MACHINE",
        },
        {
            "id": "U25",
            "section": "§8.2, §11",
            "issue": "PARAMETER_GRID_MISMATCH is 'returned' but the form is not defined: error code (HTTP status?), response status or reason. The same holds for PARAMETERS_NOT_APPROVED (reason, §11).",
            "suggestion": "State how PARAMETER_GRID_MISMATCH is returned, with its HTTP status.",
            "affects": "Q2_FAIL_CLOSED_ON_GRID_MISMATCH (kit expects an error_response with error_code PARAMETER_GRID_MISMATCH for a Q2 request)",
        },
        {
            "id": "U26",
            "section": "§8.3, §2.2",
            "issue": "The evidence summary has no schema_version or endpoint, and the preimage of evidence_sha256 is not stated (only that documents citing ids hash them as strings). The summary also does not say how a colour-less query is recorded (color_verdict) and whether the window_us shown is the clipped one.",
            "suggestion": "Define q-demo.candidate-evidence.v1 and the evidence_sha256 preimage.",
            "affects": "EVIDENCE_PRESENCE_RULES, DECISION_EVIDENCE_AND_ENTRY (PROVISIONAL schema; evidence_sha256 only used as a link value)",
        },
        {
            "id": "U27",
            "section": "§8.6, §11",
            "issue": "session_max_research_rounds, session_max_agent_rounds and fallback_budget_ms cannot be verified from the recorded artifacts: the decisions file does not state the number of SEARCHING episodes, `rounds_used` is of unknown scope (U13) and no field records the fallback's wall-clock use.",
            "suggestion": "Record episode counters and fallback wall-clock use in the decision record (or its stats).",
            "affects": "no session-limit check exists",
        },
        {
            "id": "U28",
            "section": "§4.2, §4.4",
            "issue": "The manifest has a top-level sampling.stride_samples and a stride_samples per camera (§4.4); their relation is not stated.",
            "suggestion": "State whether they must be equal or the top-level value is only a default.",
            "affects": "INDEX_MANIFEST_RULES (checks only index_interval_us = per-camera stride x source interval)",
        },
        {
            "id": "U20",
            "section": "§3.1",
            "issue": "Multi-run queries carry a single `clock_mapping_sha256` in resolved_scope although each run has its own mapping (§3.1 says each run uses its own mapping and no person may be chained across runs).",
            "suggestion": "Make it a map run_id -> sha256 or a hash over the set.",
            "affects": "SCOPE_HASH_LINKS, TIME_COVERAGE_RECOMPUTE (match by run_id)",
        },
    ]
)


UNKNOWN_CONTRACT_ITEMS.sort(key=lambda item: item["id"])

# Items of the v0.1.0 list that the contract now answers (3873ff2); the kit computes them as written.
RESOLVED_CONTRACT_ITEMS: list[dict[str, str]] = [
    {
        "id": "U07",
        "was": "numeric suffix of candidate_ref",
        "resolved_by": "§2.2: cand:<snapshot_hash16>:<rank>",
        "checked_by": "CANDIDATE_REFS_AND_LIMITS",
    },
    {
        "id": "U21",
        "was": "observation_id hash segment vs records_file_sha256 cycle",
        "resolved_by": "§2.2 detection index: index_id / observation_id use the index key (manifest without index_id, content_sha256, records_ref, records_file_sha256); content_sha256 keeps records_file_sha256",
        "checked_by": "ID_DERIVED_FROM_HASH, RECORDS_OBSERVATION_IDS, CONTENT_HASH_RECOMPUTE, INDEX_MANIFEST_RULES",
    },
    {
        "id": "U22",
        "was": "candidate_ref vs candidate_snapshot_sha256 cycle",
        "resolved_by": "§2.2 candidate snapshot: preimage without candidate_snapshot_sha256 and every candidate_ref",
        "checked_by": "CANDIDATE_SNAPSHOT_HASH, CANDIDATE_REFS_AND_LIMITS",
    },
    {
        "id": "U24",
        "was": "index_id / graph_id inside content_sha256",
        "resolved_by": "§2.2 general documents: preimage without content_sha256 and the document's own id field (graph_id, parameter_set_id)",
        "checked_by": "CONTENT_HASH_RECOMPUTE, ID_DERIVED_FROM_HASH, PARAMSET_INTEGRITY",
    },
]


# ----------------------------------------------------------------------------- runner


def run_checks(
    docs: list[Doc], params: dict[str, Any] | None = None, only: set[str] | None = None
) -> list[dict[str, Any]]:
    ctx = Ctx(docs, params)
    results: list[dict[str, Any]] = []
    for chk in CHECKS:
        if only and chk.id not in only:
            continue
        for doc in sorted(docs, key=lambda d: d.sort_key):
            if "*" not in chk.kinds and doc.kind not in chk.kinds:
                continue
            findings = Findings()
            status, message = PASS, ""
            try:
                chk.fn(doc, ctx, findings)
                if findings.items:
                    status = FAIL
                    message = f"{len(findings.items)} violation(s)"
            except NotApplicable:
                continue
            except ParamUnset as exc:
                status, message = (
                    SKIPPED_PARAM_UNSET,
                    "parameter(s) not set in the parameter set: " + ", ".join(exc.names),
                )
            except NoContext as exc:
                status, message = SKIPPED_NO_CONTEXT, str(exc)
            except (KeyError, TypeError, AttributeError, IndexError, ValueError) as exc:
                status, message = (
                    FAIL,
                    f"document structure unusable by this check ({type(exc).__name__}: {exc}); fix SCHEMA_VALID errors first",
                )
                findings.add("$", message)
            results.append(
                {
                    "check_id": chk.id,
                    "section": chk.section,
                    "document": doc.path,
                    "status": status,
                    "message": message,
                    "findings": findings.items[:50]
                    + (
                        [{"path": "$", "message": f"... {len(findings.items) - 50} more"}]
                        if len(findings.items) > 50
                        else []
                    ),
                    "notes": findings.notes,
                }
            )
    return results


def summarise(results: list[dict[str, Any]], n_docs: int) -> dict[str, Any]:
    by_status = Counter(r["status"] for r in results)
    by_check: dict[str, dict[str, int]] = {}
    for r in results:
        by_check.setdefault(r["check_id"], Counter())[r["status"]] += 1
    if n_docs == 0 or not results:
        overall = "ERROR"
    elif by_status[FAIL]:
        overall = "FAIL"
    elif by_status[SKIPPED_PARAM_UNSET]:
        overall = "INCOMPLETE"
    else:
        overall = "PASS"
    return {
        "overall": overall,
        "by_status": dict(sorted(by_status.items())),
        "by_check": {k: dict(sorted(v.items())) for k, v in sorted(by_check.items())},
        "failed_checks": sorted({r["check_id"] for r in results if r["status"] == FAIL}),
        "skipped_param_unset_checks": sorted(
            {r["check_id"] for r in results if r["status"] == SKIPPED_PARAM_UNSET}
        ),
    }


def build_report(
    docs: list[Doc],
    mode: str,
    params: dict[str, Any] | None = None,
    params_file: tuple[str, str] | None = None,
    only: set[str] | None = None,
    extra_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ctx = Ctx(docs, params)
    results = run_checks(docs, params, only) + (extra_findings or [])
    pset = ctx.params or {}
    report = {
        "report_schema": "q1q5-conformance.report.v1",
        "kit_version": KIT_VERSION,
        "contract": CONTRACT,
        "mode": mode,
        "inputs": [
            {"path": d.path, "kind": d.kind, "file_sha256": d.file_sha256,
             **_response_time_origin(d)}
            for d in sorted(docs, key=lambda d: d.sort_key)
        ],
        "parameter_set": {
            "supplied": bool(ctx.params),
            "parameter_set_id": pset.get("parameter_set_id"),
            "content_sha256": pset.get("content_sha256"),
            "file": (
                {"name": params_file[0], "file_sha256": params_file[1]} if params_file else None
            ),
        },
        "checks": results,
        "summary": summarise(results, len(docs)),
        "unknown_contract_items": UNKNOWN_CONTRACT_ITEMS,
        "resolved_contract_items": RESOLVED_CONTRACT_ITEMS,
    }
    report["output_sha256"] = canonical_sha256(report, ("output_sha256",))
    return report


def _response_time_origin(doc: Doc) -> dict[str, Any]:
    if doc.kind not in RESPONSE_KINDS:
        return {}
    try:
        source = time_range_source(doc.data)
    except (ValueError, TypeError):
        return {"time_range_source": "INVALID", "scoring_exclusion_reason": "INVALID_TIME_SOURCE"}
    return {"time_range_source": source,
            "scoring_exclusion_reason": "DEFAULT_SELECTED_RUN" if source == "DEFAULT_SELECTED_RUN" else None}


def exit_code(report: dict[str, Any], allow_incomplete: bool = False) -> int:
    overall = report["summary"]["overall"]
    return 0 if overall == "PASS" or (overall == "INCOMPLETE" and allow_incomplete) else 1


def list_checks() -> list[dict[str, Any]]:
    return [
        {
            "check_id": c.id,
            "section": c.section,
            "kinds": list(c.kinds),
            "summary": c.summary,
            "heuristic": c.heuristic,
        }
        for c in CHECKS
    ]


# ----------------------------------------------------------------------------- base-url mode

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
REQUEST_KINDS = ("q1_request", "q3_request", "q2_request")


def fetch_backend(
    base_url: str,
    docs: list[Doc],
    endpoint_map: dict[str, str],
    probe: bool = False,
    timeout_s: float = 30.0,
) -> tuple[list[Doc], list[dict[str, Any]]]:
    """POST each request document to a loopback backend; return response documents and gap entries.

    The contract defines no endpoints (U04), so ``endpoint_map`` (schema_version -> path) is required.
    Only loopback hosts are allowed: nothing here may reach an external service.
    """

    from urllib import error, parse, request

    parsed = parse.urlparse(base_url)
    if parsed.scheme != "http" or (parsed.hostname or "") not in LOOPBACK_HOSTS:
        raise ValueError(
            "--base-url must be http://127.0.0.1:<port> (or localhost); external hosts are refused"
        )
    responses: list[Doc] = []
    gaps: list[dict[str, Any]] = []

    def post(path: str, payload: Any) -> tuple[int, bytes]:
        body = canonical_json(payload).encode("utf-8")
        req = request.Request(
            base_url.rstrip("/") + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - loopback only, checked above
                return resp.status, resp.read()
        except error.HTTPError as exc:
            return exc.code, exc.read()

    for doc in sorted((d for d in docs if d.kind in REQUEST_KINDS), key=lambda d: d.sort_key):
        version = doc.data["schema_version"]
        path = endpoint_map.get(version)
        if path is None:
            gaps.append(
                {
                    "check_id": "ENDPOINT_MAPPED",
                    "section": "UNKNOWN (U04)",
                    "document": doc.path,
                    "status": SKIPPED_NO_CONTEXT,
                    "message": f"no endpoint for {version} in --endpoint-map; the contract defines none",
                    "findings": [],
                    "notes": [],
                }
            )
            continue
        variants = [("response", doc.data)] + (
            [("probe", {**doc.data, "actor_id": "kit-probe"})] if probe else []
        )
        for role, payload in variants:
            code, raw = post(path, payload)
            stem = doc.stem + (".probe" if role == "probe" else "")
            try:
                data = _loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                responses.append(
                    Doc(
                        f"{doc.stem}.{role}.json",
                        "unclassified",
                        {"error": f"non-JSON response (HTTP {code}): {exc}"},
                        hashlib.sha256(raw).hexdigest(),
                        stem,
                        role,
                    )
                )
                continue
            kind = classify(Path("x.json"), data)
            if isinstance(data, dict) and kind == "error_response" and "http_status" not in data:
                data = {**data, "http_status": code}
            responses.append(
                Doc(
                    f"{doc.stem}.{role}.json",
                    kind,
                    data,
                    hashlib.sha256(raw).hexdigest(),
                    stem,
                    "probe" if role == "probe" else "response",
                )
            )
    return responses, gaps
