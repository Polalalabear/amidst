"""ID, reference and approval rules (contract §3.2–§3.4; design §5)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .context import Context, is_hex64, nonempty_str
from .contract import DISPLAY_ONLY_FORBIDS, ID_PATTERN, PREFIX_BY_CLASS
from .report import Collector, rule


def _records(ctx: Context) -> list[tuple[str, str, dict[str, Any], str]]:
    """(collection, id, record, field path) for every ID-bearing record."""
    out: list[tuple[str, str, dict[str, Any], str]] = []
    for collection, key, items in (
        ("objects", "id", ctx.objects),
        ("walkable", "id", ctx.walkable),
        ("portals", "id", ctx.portals),
        ("floors", "floor_id", ctx.floors),
        ("cameras", "camera_id", ctx.cameras),
    ):
        for index, item in enumerate(items):
            value = item.get(key)
            if isinstance(value, str):
                out.append((collection, value, item, f"$.{collection}[{index}].{key}"))
    return out


@rule("ID-001", "ID 格式 ^[A-Z][A-Z0-9_]{2,63}$", "契約 §3.2")
def id_format(ctx: Context, out: Collector) -> None:
    for collection, id_, _, path in _records(ctx):
        if not ID_PATTERN.match(id_):
            out.err(
                "ID_FORMAT",
                "scene_static" if collection != "cameras" else "cameras",
                path,
                "ID 不符合 ^[A-Z][A-Z0-9_]{2,63}$",
                id_,
            )
    for collection, key, items in (
        ("objects", "id", ctx.objects),
        ("walkable", "id", ctx.walkable),
        ("portals", "id", ctx.portals),
        ("floors", "floor_id", ctx.floors),
        ("cameras", "camera_id", ctx.cameras),
    ):
        for index, item in enumerate(items):
            if not isinstance(item.get(key), str):
                out.err(
                    "ID_MISSING",
                    "scene_static",
                    f"$.{collection}[{index}].{key}",
                    f"{collection}[{index}] 缺少字串 {key}",
                )


@rule(
    "ID-002",
    "類別前綴正確（WALK_／OBSTACLE_／WALL_／PORTAL_／CORR_／ROOM_／AREA_／CAM_／FLOOR_）",
    "契約 §3.2；設計稿 §1.2",
)
def id_prefix(ctx: Context, out: Collector) -> None:
    for index, obj in enumerate(ctx.objects):
        id_, cls = obj.get("id"), obj.get("class")
        prefix = PREFIX_BY_CLASS.get(cls) if isinstance(cls, str) else None
        if isinstance(id_, str) and prefix and not id_.startswith(prefix):
            out.err(
                "ID_PREFIX",
                "scene_static",
                f"$.objects[{index}].id",
                f"class {cls} 的 ID 必須以 {prefix} 開頭",
                id_,
            )
    for index, walk in enumerate(ctx.walkable):
        if isinstance(walk.get("id"), str) and not walk["id"].startswith("WALK_"):
            out.err(
                "ID_PREFIX",
                "scene_static",
                f"$.walkable[{index}].id",
                "walkable ID 必須以 WALK_ 開頭",
                walk["id"],
            )
    for index, portal in enumerate(ctx.portals):
        if isinstance(portal.get("id"), str) and not portal["id"].startswith("PORTAL_"):
            out.err(
                "ID_PREFIX",
                "scene_static",
                f"$.portals[{index}].id",
                "portal ID 必須以 PORTAL_ 開頭",
                portal["id"],
            )
    for index, cam in enumerate(ctx.cameras):
        if isinstance(cam.get("camera_id"), str) and not cam["camera_id"].startswith("CAM_"):
            out.err(
                "ID_PREFIX",
                "cameras",
                f"$.cameras[{index}].camera_id",
                "camera ID 必須以 CAM_ 開頭",
                cam["camera_id"],
            )
    for index, floor in enumerate(ctx.floors):
        if isinstance(floor.get("floor_id"), str) and not floor["floor_id"].startswith("FLOOR_"):
            out.err(
                "ID_PREFIX",
                "scene_static",
                f"$.floors[{index}].floor_id",
                "floor ID 必須以 FLOOR_ 開頭",
                floor["floor_id"],
            )


@rule(
    "ID-003",
    "ID 唯一（同一集合不可重複；objects 與 walkable／portals 只允許同 class 的對應紀錄）",
    "契約 §3.2「重複 ID 讓整份匯出無效」",
)
def id_unique(ctx: Context, out: Collector) -> None:
    per_collection: dict[str, Counter[str]] = {}
    for collection, id_, _, _path in _records(ctx):
        per_collection.setdefault(collection, Counter())[id_] += 1
    for collection, counter in per_collection.items():
        for id_, count in counter.items():
            if count > 1:
                out.err(
                    "ID_DUPLICATE",
                    "scene_static",
                    f"$.{collection}",
                    f"{collection} 內 ID 重複 {count} 次",
                    id_,
                )
    object_class = {o.get("id"): o.get("class") for o in ctx.objects}
    homes: dict[str, set[str]] = {}
    for collection, counter in per_collection.items():
        for id_ in counter:
            homes.setdefault(id_, set()).add(collection)
    allowed = {
        frozenset({"objects", "walkable"}): "WALKABLE",
        frozenset({"objects", "portals"}): "PORTAL",
    }
    for id_, where in homes.items():
        if len(where) > 1 and allowed.get(frozenset(where)) != object_class.get(id_):
            out.err(
                "ID_DUPLICATE_ACROSS",
                "scene_static",
                "$",
                f"ID 同時出現在 {', '.join(sorted(where))}",
                id_,
            )


@rule(
    "ID-004",
    "沒有懸空參照，且參照的類型相符",
    "契約 §3.2「跨檔案的 ID 引用必須存在，類型也必須相符」；§3.4、§3.6、§3.7",
)
def id_references(ctx: Context, out: Collector) -> None:
    floor_ids = {f.get("floor_id") for f in ctx.floors}
    surfaces = {f.get("floor_id"): set(f.get("support_surface_ids") or []) for f in ctx.floors}
    walk_ids = {w.get("id") for w in ctx.walkable}
    portal_ids = {p.get("id") for p in ctx.portals}
    camera_ids = {c.get("camera_id") for c in ctx.cameras}
    for index, walk in enumerate(ctx.walkable):
        base, id_ = f"$.walkable[{index}]", walk.get("id")
        if walk.get("floor_id") not in floor_ids:
            out.err(
                "DANGLING_REF", "scene_static", f"{base}.floor_id", "floor_id 不在 floors[]", id_
            )
        elif walk.get("support_surface_id") not in surfaces.get(walk["floor_id"], set()):
            out.err(
                "DANGLING_REF",
                "scene_static",
                f"{base}.support_surface_id",
                "support_surface_id 不在該樓層的 support_surface_ids",
                id_,
            )
        for ci, conn in enumerate(walk.get("connections") or []):
            if not isinstance(conn, dict):
                continue
            if conn.get("to_walk_id") not in walk_ids:
                out.err(
                    "DANGLING_REF",
                    "scene_static",
                    f"{base}.connections[{ci}].to_walk_id",
                    "to_walk_id 不是 walkable[] 的 ID",
                    id_,
                )
            via = conn.get("via_portal_id")
            if via is not None and via not in portal_ids:
                out.err(
                    "DANGLING_REF",
                    "scene_static",
                    f"{base}.connections[{ci}].via_portal_id",
                    "via_portal_id 不是 portals[] 的 ID",
                    id_,
                )
    for index, portal in enumerate(ctx.portals):
        base, id_ = f"$.portals[{index}]", portal.get("id")
        if portal.get("floor_id") not in floor_ids:
            out.err(
                "DANGLING_REF", "scene_static", f"{base}.floor_id", "floor_id 不在 floors[]", id_
            )
        for side in portal.get("connects") or []:
            if side not in walk_ids:
                out.err(
                    "DANGLING_REF",
                    "scene_static",
                    f"{base}.connects",
                    "connects 含不存在的 walkable ID",
                    id_,
                )
    for index, obj in enumerate(ctx.objects):
        if (
            obj.get("class") in ("WALL", "OBSTACLE")
            and nonempty_str(obj.get("floor_id"))
            and obj["floor_id"] not in floor_ids
        ):
            out.err(
                "DANGLING_REF",
                "scene_static",
                f"$.objects[{index}].floor_id",
                "floor_id 不在 floors[]",
                obj.get("id"),
            )
        if obj.get("class") == "WALKABLE" and obj.get("id") not in walk_ids:
            out.err(
                "DANGLING_REF",
                "scene_static",
                f"$.objects[{index}].id",
                "class WALKABLE 的物件在 walkable[] 沒有對應紀錄",
                obj.get("id"),
            )
        if obj.get("class") == "PORTAL" and obj.get("id") not in portal_ids:
            out.err(
                "DANGLING_REF",
                "scene_static",
                f"$.objects[{index}].id",
                "class PORTAL 的物件在 portals[] 沒有對應紀錄",
                obj.get("id"),
            )
    object_class = {o.get("id"): o.get("class") for o in ctx.objects}
    for walk_id in walk_ids:
        if object_class.get(walk_id) != "WALKABLE":
            out.err(
                "DANGLING_REF",
                "scene_static",
                "$.walkable",
                "walkable[] 的 ID 在 objects[] 沒有 class WALKABLE 的核准紀錄",
                walk_id,
            )
    for portal_id in portal_ids:
        if object_class.get(portal_id) != "PORTAL":
            out.err(
                "DANGLING_REF",
                "scene_static",
                "$.portals",
                "portals[] 的 ID 在 objects[] 沒有 class PORTAL 的核准紀錄",
                portal_id,
            )
    for index, cam in enumerate(ctx.cameras):
        if cam.get("floor_id") not in floor_ids:
            out.err(
                "DANGLING_REF",
                "cameras",
                f"$.cameras[{index}].floor_id",
                "floor_id 不在 floors[]",
                cam.get("camera_id"),
            )
    for index, binding in enumerate(ctx.run_bindings):
        if binding.get("camera_id") not in camera_ids:
            out.err(
                "DANGLING_REF",
                "cameras",
                f"$.run_bindings[{index}].camera_id",
                "camera_id 不在 cameras[]",
                binding.get("camera_id"),
            )


@rule(
    "ID-005",
    "ID 集合與設計稿預期物件表一致（缺少、類別不符、多出的 ID）",
    "設計稿 §5 預期物件表；§1.2；附錄 A",
    "design",
)
def id_design_set(ctx: Context, out: Collector) -> None:
    design = ctx.design
    if design is None:
        from .report import Skip

        raise Skip("沒有 design_reference")
    expected = {o["id"]: o for o in design["expected_objects"]}
    actual = {o.get("id"): o for o in ctx.objects}
    for id_, spec in expected.items():
        obj = actual.get(id_)
        if obj is None:
            out.err(
                "EXPECTED_ID_MISSING",
                "scene_static",
                "$.objects",
                "設計稿預期的物件不在 objects[]",
                id_,
            )
        elif obj.get("class") != spec["class"]:
            out.err(
                "EXPECTED_CLASS_MISMATCH",
                "scene_static",
                "$.objects",
                f"class 應為 {spec['class']}，實際 {obj.get('class')}",
                id_,
            )
    if not ctx.params.allow_extra_ids:
        for id_ in actual:
            if id_ not in expected:
                out.err(
                    "UNEXPECTED_ID",
                    "scene_static",
                    "$.objects",
                    "設計稿預期物件表沒有這個 ID（不靠模糊名稱生成新 authority）",
                    id_ if isinstance(id_, str) else None,
                )
    exp_floors = {f["floor_id"] for f in design["floors"]}
    if {f.get("floor_id") for f in ctx.floors} != exp_floors:
        out.err(
            "FLOOR_SET_MISMATCH",
            "scene_static",
            "$.floors",
            f"floors[] 應只有 {sorted(exp_floors)}",
        )
    exp_cams = {c["camera_id"] for c in design["cameras"]["items"]}
    if {c.get("camera_id") for c in ctx.cameras} != exp_cams:
        out.err("CAMERA_SET_MISMATCH", "cameras", "$.cameras", f"cameras[] 應為 {sorted(exp_cams)}")


@rule(
    "APR-001",
    "核准欄位一致：APPROVED 需有 scope／approval ref 與 hash；walkable.approval 不得預先寫成已驗證",
    "契約 §3.3、§3.4；設計稿 §5",
)
def approval_consistency(ctx: Context, out: Collector) -> None:
    for index, obj in enumerate(ctx.objects):
        if obj.get("approval_status") == "APPROVED":
            for key in ("scope_ref", "approval_ref"):
                if not nonempty_str(obj.get(key)):
                    out.err(
                        "APPROVAL_INCOMPLETE",
                        "scene_static",
                        f"$.objects[{index}].{key}",
                        f"approval_status 為 APPROVED 時 {key} 不可為空",
                        obj.get("id"),
                    )
            if not is_hex64(obj.get("approval_sha256")):
                out.err(
                    "APPROVAL_INCOMPLETE",
                    "scene_static",
                    f"$.objects[{index}].approval_sha256",
                    "approval_status 為 APPROVED 時 approval_sha256 必須是 sha256",
                    obj.get("id"),
                )
    for index, walk in enumerate(ctx.walkable):
        approval = walk.get("approval")
        if not isinstance(approval, dict):
            continue
        status, base = approval.get("status"), f"$.walkable[{index}].approval"
        verified = approval.get("verified_by")
        if status == "NOT_EVALUATED":
            if verified not in ([], None) or approval.get("verification_sha256") is not None:
                out.err(
                    "APPROVAL_PREFILLED",
                    "scene_static",
                    base,
                    "NOT_EVALUATED 時 verified_by 必須為空、verification_sha256 必須為 null（"
                    "不得預先寫成 C7／K7 已驗證）",
                    walk.get("id"),
                )
        elif status == "APPROVED":
            if not (
                isinstance(verified, list) and verified and all(nonempty_str(v) for v in verified)
            ):
                out.err(
                    "APPROVAL_INCOMPLETE",
                    "scene_static",
                    f"{base}.verified_by",
                    "APPROVED 需列出 verifier 名稱與版本",
                    walk.get("id"),
                )
            if not is_hex64(approval.get("verification_sha256")):
                out.err(
                    "APPROVAL_INCOMPLETE",
                    "scene_static",
                    f"{base}.verification_sha256",
                    "APPROVED 需有報告 hash",
                    walk.get("id"),
                )


@rule(
    "APR-002", "display_only 為 true 時不得含 WALKABILITY／OCCLUSION／COLLISION 用途", "契約 §3.3"
)
def display_only_purposes(ctx: Context, out: Collector) -> None:
    for index, obj in enumerate(ctx.objects):
        purposes = obj.get("allowed_purposes")
        if obj.get("display_only") is True and isinstance(purposes, list):
            bad = sorted(set(purposes) & set(DISPLAY_ONLY_FORBIDS))
            if bad:
                out.err(
                    "DISPLAY_ONLY_PURPOSE",
                    "scene_static",
                    f"$.objects[{index}].allowed_purposes",
                    f"display_only 物件不得含 {', '.join(bad)}",
                    obj.get("id"),
                )
    for obj in ctx.solids:
        if obj.get("role") == "DISPLAY" and isinstance(obj.get("allowed_purposes"), list):
            bad = sorted(set(obj["allowed_purposes"]) & set(DISPLAY_ONLY_FORBIDS))
            if bad:
                out.err(
                    "DISPLAY_ROLE_PURPOSE",
                    "scene_static",
                    "$.objects",
                    f"role DISPLAY 不進任何物理判斷，不得含 {', '.join(bad)}",
                    obj.get("id"),
                )


@rule(
    "APR-003",
    "各類別的用途候選與 display_only 符合設計稿預期物件表",
    "設計稿 §5 allowed_purposes 候選",
    "design",
)
def class_purpose_policy(ctx: Context, out: Collector) -> None:
    template = ctx.template or {}
    policy = (template.get("purpose_policy") or {}).get("by_class")
    if ctx.design is None or not isinstance(policy, dict):
        from .report import Skip

        raise Skip("沒有 purpose_policy")
    for index, obj in enumerate(ctx.objects):
        spec = policy.get(obj.get("class"))
        purposes = obj.get("allowed_purposes")
        if spec is None or not isinstance(purposes, list):
            continue
        extra = sorted(set(purposes) - set(spec["allowed"]))
        if extra:
            out.err(
                "PURPOSE_NOT_CANDIDATE",
                "scene_static",
                f"$.objects[{index}].allowed_purposes",
                f"class {obj.get('class')} 的用途候選只有 {spec['allowed']}；多出 {extra}",
                obj.get("id"),
            )
        if "display_only" in obj and obj["display_only"] is not spec["display_only"]:
            out.err(
                "DISPLAY_ONLY_MISMATCH",
                "scene_static",
                f"$.objects[{index}].display_only",
                f"class {obj.get('class')} 的 display_only 應為 {spec['display_only']}",
                obj.get("id"),
            )
