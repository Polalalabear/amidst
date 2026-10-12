"""Read-only, source-bound review evidence; local comments never grant authority.

The input reconstruction is an unchanged prior checkpoint. This index does not
perform retrieval, association, physical screening, ranking or media generation.
Exact annotation geometry is explicitly distinct from an actual opening.
"""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.blender_physical_source import PhysicalSourceInputs, _pinned_json

Json = dict[str, Any]
MAX_PRIMITIVES = 64
MAX_VERTICES = 8192
MAX_TRIANGLES = 4096
MAX_PREVIEW_TRIANGLES = 1024
MAX_SAMPLES = 400
MAX_MISSING = 256
_PORTALS = {
    "office": ("PORTAL_1F_OFFICE", "PORTAL_1F_AUDITORIUM_OFFICE"),
    "classroom101": ("PORTAL_1F_CLASS101",),
    "auditorium": ("PORTAL_1F_AUDITORIUM", "PORTAL_1F_AUDITORIUM_OFFICE"),
}
_WALKABLE = {
    "office": "WALK_1F_OFFICE",
    "classroom101": "WALK_1F_CLASS101",
    "auditorium": "WALK_1F_AUDITORIUM",
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STATES = {"PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION", "INFERRED_CROSS_CAMERA", "MISSING"}


def _finite(value: Any) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("PHYSICAL_REVIEW_NUMERIC_INPUT_DENIED")
    return float(value)


def _point(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("PHYSICAL_REVIEW_GEOMETRY_DENIED")
    return [_finite(component) for component in value]


def _safe(value: Any) -> bool:
    if isinstance(value, Mapping):
        if {
            "gt",
            "ground_truth",
            "trajectory",
            "private_path",
            "local_path",
            "session_id",
            "token",
            "input_frames",
        }.intersection(value):
            return False
        return all(isinstance(key, str) and _safe(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_safe(child) for child in value)
    if isinstance(value, str):
        return not any(marker in value for marker in ("/Users/", "/private/", "file://", "\\"))
    return (
        value is None
        or type(value) in (bool, int)
        or (type(value) is float and math.isfinite(value))
    )


def _documents(source: PhysicalSourceInputs) -> tuple[Json, Json]:
    """Reuse the pinned allowlist; no Blender, GT, observations or full source atlas."""
    portal = _pinned_json(source._repo, "portal_review")
    local = _pinned_json(source._repo, "local_scope_review")
    if any(document.get("source_sha256") != source.source_sha256 for document in (portal, local)):
        raise ValueError("PHYSICAL_REVIEW_SOURCE_BINDING_DENIED")
    return portal, local


class BlenderPhysicalReviewIndex:
    """Prepare immutable bounded context once; queries only slice display evidence."""

    def __init__(self, source: PhysicalSourceInputs, physical_result: Mapping[str, Any]) -> None:
        source.verify()
        if source.site_id not in _PORTALS or source._geometry is None:
            raise ValueError("PHYSICAL_REVIEW_SOURCE_UNAVAILABLE")
        if not _safe(physical_result):
            raise ValueError("PHYSICAL_REVIEW_UNSAFE_PRIOR_RESULT")
        self._source = source
        self._site = source.site_id
        self._result = copy.deepcopy(dict(physical_result))
        binding = self._result.get("source_binding", {})
        selection = self._result.get("selection", {})
        if (
            binding.get("source_sha256") != source.source_sha256
            or binding.get("site_id") != self._site
            or binding.get("normalized_units") != "METRES"
            or binding.get("time_unit") != "SECONDS"
            or self._result.get("physical_source_sha256") != source.physical_source_sha256
            or not _SHA.fullmatch(str(self._result.get("physical_sha256", "")))
            or source._geometry.source_sha256 != source.source_sha256
        ):
            raise ValueError("PHYSICAL_REVIEW_SOURCE_BINDING_DENIED")
        self._cameras = tuple(selection.get("camera_ids", ()))
        if (
            not 1 <= len(self._cameras) <= 4
            or len(set(self._cameras)) != len(self._cameras)
            or any(not isinstance(camera, str) or not camera for camera in self._cameras)
        ):
            raise ValueError("PHYSICAL_REVIEW_CAMERA_SCOPE_DENIED")
        self._time = [_finite(value) for value in self._result.get("source_time_range", ())]
        if (
            len(self._time) != 2
            or not 0 <= self._time[0] <= self._time[1]
            or self._time[1] - self._time[0] > 10
            or [_finite(value) for value in selection.get("time_range", ())] != self._time
        ):
            raise ValueError("PHYSICAL_REVIEW_CANONICAL_PRIOR_REQUIRED")
        if not isinstance(binding.get("clock_id"), str) or not binding["clock_id"]:
            raise ValueError("PHYSICAL_REVIEW_SOURCE_CLOCK_REQUIRED")
        self._binding = copy.deepcopy(binding)
        self._scope = content_hash(
            {
                "binding": binding,
                "physical_sha256": self._result["physical_sha256"],
                "physical_source": source.physical_source_sha256,
            }
        )
        self._geometry: list[Json] = []
        self._items: list[Json] = []
        self._preview_omitted = 0
        portal, local = _documents(source)
        self._build(portal, local)
        self._samples, self._missing = self._motion_evidence()
        self._catalog = {
            "schema_version": "workbench.blender-physical-review.v1",
            "status": "UNKNOWN",
            "review_status": "PENDING",
            "source_binding": copy.deepcopy(binding),
            "source_sha256": source.source_sha256,
            "physical_source_sha256": source.physical_source_sha256,
            "evidence_hashes": dict(source.evidence_hashes),
            "camera_coverage": copy.deepcopy(self._result.get("camera_coverage", [])),
            "prior_results": {
                "checkpoint": "2de9821",
                "status": "UNCHANGED_PRIOR_RESULTS",
                "physical_sha256": self._result["physical_sha256"],
                "ranking_recomputed": False,
                "media_rerendered": False,
                "candidate_refs": [
                    row["candidate_ref"] for row in self._result.get("candidates", [])
                ],
                "search": copy.deepcopy(self._result.get("search", {})),
            },
            "items": self._items,
            "geometry_primitives": self._geometry,
            "geometry_coverage": {
                "partial": True,
                "global_clearance_certified": False,
                "actual_apertures_approved": 0,
                "preview_truncated": self._preview_omitted > 0
                or any(row["truncated"] for row in self._geometry),
                "omitted_primitive_count": self._preview_omitted,
                "max_primitives": MAX_PRIMITIVES,
                "max_vertices": MAX_VERTICES,
                "max_triangles": MAX_TRIANGLES,
                "max_preview_triangles": MAX_PREVIEW_TRIANGLES,
            },
            "decision_scope": "LOCAL_ENGINEERING_REVIEW_ONLY",
            "source_authority_changed": False,
            "rerun_authorized": False,
            "agent_used": False,
            "gt_used": False,
            "source_modified": False,
            "source_copied": False,
            "opened_blender": False,
            "limitations": [
                "Annotation locations are not aperture geometry or camera/room ownership.",
                "Missing support does not prove disconnection or collision freedom.",
                "Source witnesses and partial context never gain collider authority.",
                "Local review comments do not change formal source authority or prior results.",
            ],
        }
        self.review_sha256 = content_hash(
            {"catalog": self._catalog, "samples": self._samples, "missing": self._missing}
        )

    def _ref(self, namespace: str, identity: Any) -> str:
        digest = opaque_ref(
            namespace.replace("-", ""), content_hash({"scope": self._scope, "identity": identity})
        ).split(":", 1)[1]
        return f"{namespace}:{digest}"

    def _primitive(
        self,
        label: str,
        kind: str,
        vertices: Sequence[Any],
        triangles: Sequence[Any],
        authority: str,
        **metadata: Any,
    ) -> str | None:
        points = [_point(value) for value in vertices]
        faces = [list(value) for value in triangles]
        if any(
            len(face) != 3
            or any(type(index) is not int or index < 0 or index >= len(points) for index in face)
            for face in faces
        ):
            raise ValueError("PHYSICAL_REVIEW_GEOMETRY_DENIED")
        if (
            len(self._geometry) >= MAX_PRIMITIVES
            or len(points) + sum(len(row["vertices"]) for row in self._geometry) > MAX_VERTICES
            or len(faces) + sum(len(row["triangles"]) for row in self._geometry) > MAX_TRIANGLES
        ):
            self._preview_omitted += 1
            return None
        value = {
            "label": label,
            "kind": kind,
            "units": "METRES",
            "vertices": points,
            "triangles": faces,
            "authority": authority,
            "display_only": True,
            "is_aperture": False,
            "is_collider": False,
            "ownership_confirmed": False,
            "source_geometry_sha256": self._source.geometry_model_sha256,
            "truncated": False,
            **metadata,
        }
        if not _safe(value):
            raise ValueError("PHYSICAL_REVIEW_GEOMETRY_DENIED")
        value["geometry_ref"] = self._ref("review-geometry", content_hash(value))
        self._geometry.append(value)
        return str(value["geometry_ref"])

    def _item(
        self,
        kind: str,
        identity: str,
        title: str,
        geometry_refs: list[str],
        gaps: list[tuple[str, str]],
        checks: list[tuple[str, str]],
        evidence: list[str],
    ) -> None:
        item_ref = self._ref("review-item", [kind, identity])
        self._items.append(
            {
                "item_ref": item_ref,
                "kind": kind,
                "title": title,
                "site_id": self._site,
                "status": "UNKNOWN",
                "review_status": "PENDING",
                "source_authority": "HUMAN_REVIEW",
                "ownership_confirmed": False,
                "selection_basis": "DECLARED_REVIEW_CONTEXT_NOT_CAMERA_OR_PATH_OWNERSHIP",
                "geometry_refs": geometry_refs,
                "evidence_refs": evidence,
                "pending_gaps": [
                    {"code": code, "description": description} for code, description in gaps
                ],
                "checklist": [
                    {
                        "check_ref": self._ref("review-check", [item_ref, code]),
                        "code": code,
                        "title": title_,
                        "default_decision": "UNKNOWN",
                        "required_evidence": evidence + geometry_refs,
                    }
                    for code, title_ in checks
                ],
                "focus": {
                    "camera_ids": list(self._cameras),
                    "time_range": list(self._time),
                    "geometry_refs": geometry_refs,
                },
            }
        )

    def _build(self, portal_document: Json, local_document: Json) -> None:
        source = self._source
        assert source._geometry is not None
        factor = source.contract.scale.metres_per_blender_unit
        surfaces = {row.surface_id: row for row in source._geometry.surfaces}
        for identity in _PORTALS[self._site]:
            row = surfaces.get(identity)
            refs = []
            if row is not None:
                ref = self._primitive(
                    identity,
                    "SOURCE_ANNOTATION",
                    [[component * factor for component in point] for point in row.vertices],
                    row.triangles,
                    "ANNOTATION_ONLY_NOT_APERTURE",
                    source_object_id=row.source_object_id,
                    source_face_indices=list(row.source_face_indices),
                    source_triangle_indices=[],
                    declared_floor_ids=list(row.floor_ids),
                )
                if ref is not None:
                    refs.append(ref)
            diagnostic = [
                row for row in portal_document.get("pairs", []) if row["portal_id"] == identity
            ]
            self._item(
                "PORTAL_APERTURE",
                identity,
                f"門洞核對：{identity}",
                refs,
                [
                    (
                        "ACTUAL_APERTURE_UNAPPROVED",
                        "只有登錄 annotation；實際門框邊界、寬高與通行法向未核准。",
                    ),
                    (
                        "ADJACENT_WALKABLE_UNDECLARED",
                        "來源未宣告相鄰 walkable 關係，不能從名稱認定房間／走廊。",
                    ),
                    (
                        "NO_SITE_APERTURE_DIAGNOSTIC"
                        if not diagnostic
                        else "APERTURE_DIAGNOSTIC_ONLY",
                        "此門無來源門孔診斷對。"
                        if not diagnostic
                        else "已有診斷對，但不是可通行門孔核准。",
                    ),
                ],
                [
                    ("OPENING_BOUNDARY", "核對原來源門框／門扇／牆面，列出可見來源面與仍缺的面。"),
                    ("OPENING_NORMAL", "確認實際通行法向及門兩侧落腳面；不可將 box 寬度當孔寬。"),
                    (
                        "OPENING_BODY_CLEARANCE",
                        f"核對最窄淨寬至少 {source.contract.portal_min_width_m:g} m、"
                        f"淨高至少 {source.contract.portal_min_height_m:g} m；未量測保持未知。",
                    ),
                    (
                        "OPENING_OWNERSHIP",
                        "確認這個門的空間關係與目前 site/camera 是否有來源依據；名稱本身不作證。",
                    ),
                ],
                ["evidence:geometry_archive", "evidence:portal_review", "evidence:body_policy"],
            )
        # A partial full-floor preview must not crowd out the declared site's support.
        site_ref = self._support_context(
            source.site_support_domains[self._site].support_surfaces, "此 site 登錄原支持面"
        )
        floor_ref = self._support_context(
            source.support_domains["1F"].support_surfaces,
            "1F 原支持三角面（保留原高度／缺洞）",
        )
        refs = [ref for ref in (site_ref, floor_ref) if ref is not None]
        self._item(
            "CORRIDOR_CONNECTIVITY",
            "1F",
            "走廊連通核對（來源部分支持域）",
            refs,
            [
                ("PORTAL_ADJACENCY_UNAPPROVED", "門與走廊的合法相鄰／穿越關係未確認。"),
                (
                    "PARTIAL_SUPPORT_NOT_COMPLETE_ROUTE",
                    "核准支持面保留孔洞與不連續；未覆蓋部分不可視為牆或無路。",
                ),
                ("MISSING_MOTION_NOT_ROUTE", "長缺口只有端點，示意線不代表中間動線。"),
            ],
            [
                ("CONNECTIVITY_SOURCE", "核對門兩側原支持面的實際接續／高度差，指出缺少的來源。"),
                ("CORRIDOR_BOUNDARIES", "確認走廊可通行範圍、孔洞／障礙；不可補看不見的連接。"),
                (
                    "ROUTE_AND_OWNERSHIP",
                    "對照影像時間、投影與缺口，確認關聯只是假設，site／房間歸屬仍須來源。",
                ),
            ],
            ["evidence:floor_support", "evidence:geometry_archive", "evidence:portal_review"],
        )
        body_refs = [site_ref] if site_ref is not None else []
        region = next(
            (
                row
                for row in local_document.get("regions", [])
                if row.get("walkable_id") == _WALKABLE[self._site]
            ),
            None,
        )
        witnesses = [] if region is None else region.get("review_witnesses", [])
        for ordinal, witness in enumerate(witnesses[:24]):
            points = witness.get("triangle_bu")
            face = [[0, 1, 2]] if points is not None else []
            if points is None and witness.get("location_bu") is not None:
                points = [witness["location_bu"]]
            if points is None:
                continue
            ref = self._primitive(
                f"人體來源見證 {ordinal + 1}：{witness['reason']}",
                "SOURCE_WITNESS",
                [[component * factor for component in point] for point in points],
                face,
                "SOURCE_CONTEXT_NOT_APPROVED_COLLIDER",
                source_object_id=witness.get("source_object_id"),
                source_face_indices=[]
                if "source_face_index" not in witness
                else [witness["source_face_index"]],
                source_triangle_indices=[],
                witness_reason=witness["reason"],
            )
            if ref is not None:
                body_refs.append(ref)
        self._item(
            "BODY_CLEARANCE",
            _WALKABLE[self._site],
            "人體淨空核對（名義直立圓柱）",
            body_refs,
            [
                (
                    "BODY_CEILING_CLEARANCE_UNAPPROVED",
                    "支持面核准不包含身體／天花／完整封閉體淨空。",
                ),
                (
                    "SOURCE_BODY_WITNESSES_PARTIAL"
                    if witnesses
                    else "SITE_BODY_REGION_NOT_EXPORTED",
                    "現有來源見證仍包含未分類接觸／退化／封閉體不確定。"
                    if witnesses
                    else "此 site 沒有完整來源人體域見證，不能沿用 Office 結論。",
                ),
                (
                    "PROJECTED_BODY_IS_HYPOTHESIS",
                    "地板投影及設定人體尺度是名義假設；不是人物真實身形／身份。",
                ),
            ],
            [
                (
                    "BODY_FOOT_CONTACT",
                    "核對原三角面接地高度與投影接點，不把 annotation plane 當接地面。",
                ),
                (
                    "BODY_SURROUNDING_SOURCE",
                    "核對牆／門扇／家具／天花來源面及缺失，判明未分類與退化來源。",
                ),
                (
                    "BODY_POLICY_CLEARANCE",
                    f"對照設定半徑 {source.contract.parameter('body_radius_m'):g} m、"
                    f"高 {source.contract.parameter('body_height_m'):g} m及淨空，"
                    "不把政策值當量測人體。",
                ),
            ],
            [
                "evidence:local_scope_review",
                "evidence:floor_support",
                "evidence:body_policy",
                "evidence:architectural_scale",
            ],
        )

    def _support_context(self, surfaces: Sequence[Any], title: str) -> str | None:
        factor = self._source.contract.scale.metres_per_blender_unit
        vertices: list[list[float]] = []
        triangles: list[list[int]] = []
        triangle_sources: list[Json] = []
        eligible = sorted(surfaces, key=lambda value: value.surface_id)
        total = sum(len(row.triangles) for row in eligible)
        for row in eligible:
            for ordinal, triangle in enumerate(row.triangles):
                if len(triangles) >= MAX_PREVIEW_TRIANGLES:
                    break
                index = len(vertices)
                vertices.extend(
                    [[component * factor for component in row.vertices[i]] for i in triangle]
                )
                triangles.append([index, index + 1, index + 2])
                triangle_sources.append(
                    {"source_surface_id": row.surface_id, "source_surface_triangle_index": ordinal}
                )
        return self._primitive(
            title,
            "SOURCE_TRIANGLES",
            vertices,
            triangles,
            "APPROVED_SUPPORT_ONLY_NOT_BODY_CLEARANCE",
            source_surface_ids=[row.surface_id for row in eligible],
            source_surface_metadata=[
                {
                    "source_surface_id": row.surface_id,
                    "source_object_id": row.source_object_id,
                    "source_face_indices": list(row.source_face_indices),
                }
                for row in eligible
            ],
            face_mapping="SUPPORT_SURFACE_REFERENCES_NOT_PER_TRIANGLE_SOURCE_FACE_ASSIGNMENT",
            triangle_sources=triangle_sources,
            source_triangle_count=total,
            truncated=total > len(triangles),
            omitted_triangle_count=total - len(triangles),
        )

    def _motion_evidence(self) -> tuple[list[Json], list[Json]]:
        samples: dict[str, Json] = {}
        missing: dict[str, Json] = {}
        candidates = list(self._result.get("candidates", []))
        baseline = self._result.get("baseline_candidate")
        if isinstance(baseline, dict) and all(
            row["candidate_ref"] != baseline["candidate_ref"] for row in candidates
        ):
            candidates.append(baseline)
        for candidate in candidates:
            for path in candidate.get("paths", []):
                for sample in path.get("samples", []):
                    if sample.get("state") not in _STATES:
                        raise ValueError("PHYSICAL_REVIEW_SAMPLE_STATE_DENIED")
                    row = {
                        key: copy.deepcopy(sample.get(key))
                        for key in (
                            "timestamp",
                            "world_position",
                            "state",
                            "camera_id",
                            "frame_ref",
                            "observation_ref",
                            "connect_from_previous",
                            "missing_reason",
                            "overlap_support",
                        )
                    }
                    row["timestamp"] = _finite(row["timestamp"])
                    row["source_camera_ids"] = list(path.get("camera_ids", []))
                    if row["world_position"] is not None:
                        row["world_position"] = _point(row["world_position"])
                    if row["camera_id"] not in self._cameras and row["camera_id"] is not None:
                        raise ValueError("PHYSICAL_REVIEW_CAMERA_SCOPE_DENIED")
                    key = content_hash(row)
                    if key not in samples:
                        samples[key] = {**row, "candidate_refs": []}
                    samples[key]["candidate_refs"].append(candidate["candidate_ref"])
                for gap in path.get("gaps", []):
                    row = {
                        key: copy.deepcopy(gap.get(key))
                        for key in ("time_range", "reason", "state", "gap_ref")
                    }
                    row["camera_ids"] = list(path.get("camera_ids", []))
                    row["candidate_ref"] = candidate["candidate_ref"]
                    missing[content_hash(row)] = row
        return sorted(
            samples.values(),
            key=lambda row: (row["timestamp"], str(row["camera_id"]), content_hash(row)),
        ), list(missing.values())

    def snapshot(self, camera_ids: Sequence[str], start: float, end: float) -> Json:
        self._source.verify()
        lo, hi = _finite(start), _finite(end)
        if (
            not isinstance(camera_ids, Sequence)
            or isinstance(camera_ids, (str, bytes))
            or not 1 <= len(camera_ids) <= 4
            or any(not isinstance(camera, str) for camera in camera_ids)
            or len(set(camera_ids)) != len(camera_ids)
            or not set(camera_ids).issubset(self._cameras)
        ):
            raise ValueError("PHYSICAL_REVIEW_CAMERA_SCOPE_DENIED")
        if not self._time[0] <= lo <= hi <= self._time[1] or hi - lo > 10:
            raise ValueError("PHYSICAL_REVIEW_TIME_SCOPE_DENIED")
        cameras = sorted(camera_ids)
        result = copy.deepcopy(self._catalog)
        result["review_sha256"] = self.review_sha256
        result["selection"] = {
            "camera_ids": cameras,
            "time_range": [lo, hi],
            "clock_id": self._binding["clock_id"],
            "canonical_ranking_scope": "FULL_SOURCE_UNCHANGED",
        }
        samples = [
            copy.deepcopy(row)
            for row in self._samples
            if lo <= row["timestamp"] <= hi
            and (
                row["camera_id"] in cameras
                or (row["camera_id"] is None and set(row["source_camera_ids"]).issubset(cameras))
            )
        ]
        for sample in samples:
            sample["overlap_support"] = [
                row for row in sample["overlap_support"] or [] if row.get("camera_id") in cameras
            ]
        gaps = [
            copy.deepcopy(row)
            for row in self._missing
            if set(row["camera_ids"]).intersection(cameras)
            and row["time_range"][0] <= hi
            and row["time_range"][1] >= lo
        ]
        for gap in gaps:
            gap["original_time_range"] = list(gap["time_range"])
            gap["time_range"] = [max(lo, gap["time_range"][0]), min(hi, gap["time_range"][1])]
        result["camera_coverage"] = [
            row for row in result["camera_coverage"] if row["camera_id"] in cameras
        ]
        for coverage in result["camera_coverage"]:
            coverage["count_scope"] = "UNCHANGED_FULL_SOURCE_PRIOR"
            coverage["display_time_range"] = [lo, hi]
            if coverage.get("projected_frame_count") == 0:
                gaps.append(
                    {
                        "camera_ids": [coverage["camera_id"]],
                        "time_range": [lo, hi],
                        "original_time_range": coverage["time_range"],
                        "state": "MISSING",
                        "reason": "PRIOR_CAMERA_HAS_NO_USABLE_PROJECTION",
                        "candidate_ref": None,
                    }
                )
        result["synchronized_evidence"] = {
            "samples": copy.deepcopy(samples[:MAX_SAMPLES]),
            "missing_intervals": gaps[:MAX_MISSING],
            "sample_count": len(samples),
            "missing_interval_count": len(gaps),
            "truncated": len(samples) > MAX_SAMPLES or len(gaps) > MAX_MISSING,
            "maximum_samples": MAX_SAMPLES,
            "maximum_missing_intervals": MAX_MISSING,
            "position_filled": False,
            "identity_confirmed": False,
            "behavior_confirmed": False,
        }
        for item in result["items"]:
            item["focus"]["camera_ids"] = cameras
            item["focus"]["time_range"] = [lo, hi]
        return result


def validate_review_decision(index: BlenderPhysicalReviewIndex, payload: Mapping[str, Any]) -> Json:
    """Strict local diff DTO; author/session/revision/CAS belong to the server store."""
    index._source.verify()
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {"review_sha256", "item_ref", "checks"}
        or not _safe(payload)
        or payload["review_sha256"] != index.review_sha256
    ):
        raise ValueError("PHYSICAL_REVIEW_DECISION_BINDING_DENIED")
    item = next((row for row in index._items if row["item_ref"] == payload["item_ref"]), None)
    if item is None:
        raise ValueError("PHYSICAL_REVIEW_ITEM_DENIED")
    checks = payload["checks"]
    if not isinstance(checks, list) or not 1 <= len(checks) <= len(item["checklist"]):
        raise ValueError("PHYSICAL_REVIEW_CHECKS_DENIED")
    allowed = {row["check_ref"] for row in item["checklist"]}
    evidence = set(item["evidence_refs"] + item["geometry_refs"])
    normalized: list[Json] = []
    seen: set[str] = set()
    for check in checks:
        if not isinstance(check, Mapping) or set(check) != {
            "check_ref",
            "decision",
            "evidence_refs",
            "comment",
        }:
            raise ValueError("PHYSICAL_REVIEW_CHECKS_DENIED")
        ref = check["check_ref"]
        if (
            not isinstance(ref, str)
            or ref not in allowed
            or ref in seen
            or not isinstance(check["decision"], str)
            or check["decision"] not in {"CONFIRMED_LOCAL", "CONTRADICTED_LOCAL", "UNKNOWN"}
        ):
            raise ValueError("PHYSICAL_REVIEW_CHECKS_DENIED")
        comment = check["comment"]
        refs = check["evidence_refs"]
        if (
            not isinstance(comment, str)
            or len(comment) > 2000
            or not isinstance(refs, list)
            or len(refs) > 16
            or any(not isinstance(value, str) or value not in evidence for value in refs)
            or len(set(refs)) != len(refs)
            or (check["decision"] != "UNKNOWN" and (not comment.strip() or not refs))
        ):
            raise ValueError("PHYSICAL_REVIEW_EVIDENCE_REQUIRED")
        seen.add(ref)
        normalized.append(
            {
                "check_ref": ref,
                "decision": check["decision"],
                "evidence_refs": sorted(refs),
                "comment": comment.strip(),
                "previous_decision": "UNKNOWN",
            }
        )
    normalized.sort(key=lambda row: row["check_ref"])
    result = {
        "schema_version": "workbench.blender-physical-review-decision.v1",
        "status": "LOCALLY_REVIEWED"
        if any(row["decision"] != "UNKNOWN" for row in normalized)
        else "UNKNOWN",
        "scope": "LOCAL_ENGINEERING_REVIEW_ONLY",
        "review_sha256": index.review_sha256,
        "item_ref": item["item_ref"],
        "source_binding": copy.deepcopy(index._binding),
        "checks": normalized,
        "remaining_check_refs": sorted(
            allowed - {row["check_ref"] for row in normalized if row["decision"] != "UNKNOWN"}
        ),
        "source_authority_changed": False,
        "formal_approval": False,
        "rerun_authorized": False,
        "prior_results_changed": False,
    }
    result["decision_sha256"] = content_hash(result)
    return result
