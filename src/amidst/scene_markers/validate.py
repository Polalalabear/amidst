"""Controlled-scene marker validator: run every rule over the safe-side static files.

The validator reads only the five allowlisted safe files (plus the repository's marker template
for the design reference).  It never opens private data, GT, masks or images; a private
reference found inside a safe file is reported by ``SPLIT-*`` and not followed.  The report is
deterministic (no clock, no local paths) and carries ``output_sha256``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amidst.engineering.registry import content_hash

from . import (  # noqa: F401  (register rules)
    rules_cameras,
    rules_geometry,
    rules_ids,
    rules_run,
    rules_schema,
    rules_split,
)
from .context import Context, as_dict
from .contract import CONTRACT_REF, DESIGN_REF
from .loader import load_safe_bundle
from .params import PARAMS_VERSION, VERIFIER_VERSION, ValidationParams
from .report import RULES, Collector, Issue, RuleOutcome, RuleSpec, Skip
from .rgb_index_adapter import resolve_rgb_index

REPORT_SCHEMA_VERSION = "controlled-scene.marker-validation.v1"
DEFAULT_TEMPLATE = (
    Path(__file__).resolve().parents[3] / "configs" / "controlled_scene_v1_marker_template.json"
)


def load_template(path: Path | None = None) -> dict[str, Any]:
    template = json.loads((path or DEFAULT_TEMPLATE).read_text(encoding="utf-8"))
    if (
        not isinstance(template, dict)
        or template.get("schema_version") != "controlled-scene.marker-template.v1"
    ):
        raise ValueError("not a controlled-scene marker template (schema_version mismatch)")
    return template


def _safe_hash(value: Any) -> str | None:
    try:
        return content_hash(value)
    except (TypeError, ValueError):
        return None


def _unknown_scopes(ctx: Context) -> list[dict[str, Any]]:
    """Scopes whose use is not approved yet.  The validator never turns UNKNOWN into permitted."""
    scopes: list[dict[str, Any]] = []
    for obj in ctx.objects:
        if obj.get("approval_status") != "APPROVED":
            scopes.append(
                {
                    "scope": "object_purposes",
                    "id": obj.get("id"),
                    "reason": f"approval_status={obj.get('approval_status')}",
                }
            )
        if obj.get("source_method") == "UNKNOWN":
            scopes.append(
                {"scope": "source_method", "id": obj.get("id"), "reason": "source_method=UNKNOWN"}
            )
        if obj.get("collision_scope") == "UNKNOWN":
            scopes.append(
                {
                    "scope": "collision_scope",
                    "id": obj.get("id"),
                    "reason": "collision_scope=UNKNOWN",
                }
            )
    for walk in ctx.walkable:
        approval = as_dict(walk.get("approval"))
        if approval.get("status") != "APPROVED":
            scopes.append(
                {
                    "scope": "walkable_verification",
                    "id": walk.get("id"),
                    "reason": f"approval.status={approval.get('status')}（C7／K7 尚未驗證）",
                }
            )
        if walk.get("status") == "UNKNOWN":
            scopes.append(
                {"scope": "walkable_status", "id": walk.get("id"), "reason": "status=UNKNOWN"}
            )
    return scopes


def _checked_purposes(ctx: Context) -> list[str]:
    found: set[str] = set()
    for record in ctx.objects + ctx.portals:
        purposes = record.get("allowed_purposes")
        if isinstance(purposes, list):
            found.update(p for p in purposes if isinstance(p, str))
    return sorted(found)


_GROUP_ORDER = ("IO", "SPLIT", "SCH", "HSH", "ID", "APR", "FLR", "WLK", "OBS", "PRT", "CAM", "RUN")


def _rule_order(spec: RuleSpec) -> tuple[int, str]:
    return _GROUP_ORDER.index(spec.rule_id.split("-")[0]), spec.rule_id


def run_rules(ctx: Context) -> list[RuleOutcome]:
    outcomes: list[RuleOutcome] = []
    for spec in sorted(RULES, key=_rule_order):
        collector = Collector(spec.rule_id)
        try:
            spec.func(ctx, collector)
        except Skip as skip:
            outcomes.append(RuleOutcome(spec, "SKIPPED", [], str(skip)))
            continue
        except Exception as exc:  # fail closed: a crashing rule is a failed rule
            collector.issues.append(
                Issue(
                    spec.rule_id,
                    "RULE_CRASHED",
                    "ERROR",
                    "validator",
                    "$",
                    None,
                    f"規則執行時例外 {type(exc).__name__}；輸入結構無法核對",
                )
            )
        failed = any(i.severity == "ERROR" for i in collector.issues)
        outcomes.append(RuleOutcome(spec, "FAIL" if failed else "PASS", collector.issues))
    return outcomes


def build_report(ctx: Context, outcomes: list[RuleOutcome]) -> dict[str, Any]:
    issues = [i.as_dict() for o in outcomes for i in o.issues]
    errors = sum(i["severity"] == "ERROR" for i in issues)
    report: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "status": "FAIL" if errors else "PASS",
        "verifier_version": VERIFIER_VERSION,
        "checked_schema_version": (ctx.static or {}).get("schema_version"),
        "contract_ref": CONTRACT_REF,
        "design_ref": DESIGN_REF if ctx.design is not None else None,
        "design_layer": "ENABLED" if ctx.design is not None else "DISABLED",
        "template_content_sha256": _safe_hash(ctx.template) if ctx.design is not None else None,
        "input_file_sha256": dict(sorted(ctx.file_sha256.items())),
        "input_content_sha256": {role: _safe_hash(doc) for role, doc in sorted(ctx.docs.items())},
        "checked_purposes": _checked_purposes(ctx),
        "parameters_version": PARAMS_VERSION,
        "parameters": ctx.params.as_dict(),
        "adapters": ctx.rgb_adapters,
        "rules": [o.as_dict() for o in outcomes],
        "issues": issues,
        "unknown_scopes": _unknown_scopes(ctx),
        "summary": {
            "rules_total": len(outcomes),
            "rules_passed": sum(o.result == "PASS" for o in outcomes),
            "rules_failed": sum(o.result == "FAIL" for o in outcomes),
            "rules_skipped": sum(o.result == "SKIPPED" for o in outcomes),
            "errors": errors,
            "warnings": sum(i["severity"] == "WARN" for i in issues),
            "infos": sum(i["severity"] == "INFO" for i in issues),
        },
        "skipped_reasons": {
            o.spec.rule_id: o.skip_reason for o in outcomes if o.result == "SKIPPED"
        },
    }
    report["output_sha256"] = _safe_hash(report)
    return report


def validate_documents(
    *,
    static: Any,
    manifest: Any,
    rgb_index: Any,
    runtime_profile: Any,
    cameras: Any = None,
    template: dict[str, Any] | None = None,
    params: ValidationParams | None = None,
    design: bool = True,
    file_sha256: dict[str, str] | None = None,
    load_issues: list[tuple[str, str, str, str]] | None = None,
) -> dict[str, Any]:
    """Validate already-parsed safe documents (used by tests and by ``validate_safe_bundle``)."""
    ctx = Context(
        params=params or ValidationParams(),
        template=(template if template is not None else load_template()) if design else template,
        static=static if isinstance(static, dict) else None,
        cameras_doc=cameras if isinstance(cameras, dict) else None,
        manifest=manifest if isinstance(manifest, dict) else None,
        rgb_index_raw=rgb_index if isinstance(rgb_index, dict) else None,
        runtime_profile=runtime_profile if isinstance(runtime_profile, dict) else None,
        file_sha256=dict(file_sha256 or {}),
        load_issues=list(load_issues or []),
        design_enabled=design,
    )
    resolution = resolve_rgb_index(ctx.rgb_index_raw, ctx.file_sha256.get("rgb_index"))
    ctx.rgb_index = resolution.document
    if resolution.adapter is not None:
        ctx.rgb_adapters.append(resolution.adapter)
    if resolution.error_code is not None and resolution.error_message is not None:
        ctx.rgb_index_error = (resolution.error_code, resolution.error_message)
    for role, value in (
        ("scene_static", static),
        ("manifest", manifest),
        ("rgb_index", rgb_index),
        ("runtime_profile", runtime_profile),
    ):
        if value is not None and not isinstance(value, dict):
            ctx.load_issues.append(("JSON_NOT_OBJECT", role, "$", f"{role} 頂層必須是 JSON 物件"))
    return build_report(ctx, run_rules(ctx))


def validate_safe_bundle(
    bundle_dir: Path,
    *,
    template_path: Path | None = None,
    params: ValidationParams | None = None,
    design: bool = True,
) -> dict[str, Any]:
    """Validate ``<bundle_dir>/{scene_static,manifest,cameras,rgb_index,runtime_profile}.json``."""
    docs, hashes, issues = load_safe_bundle(bundle_dir)
    return validate_documents(
        static=docs.get("scene_static"),
        manifest=docs.get("manifest"),
        rgb_index=docs.get("rgb_index"),
        runtime_profile=docs.get("runtime_profile"),
        cameras=docs.get("cameras"),
        template=load_template(template_path) if design else None,
        params=params,
        design=design,
        file_sha256=hashes,
        load_issues=issues,
    )
