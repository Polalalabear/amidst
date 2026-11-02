"""Build tiny SYNTHETIC-only CQ-21-T inputs. No real source or human approvals."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write(name, doc):
    data = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False).encode() + b"\n"
    (ROOT / name).write_bytes(data)
    return sha(data)


def seal_graph(doc, prefix):
    doc["content_sha256"] = sha(raw({k: v for k, v in doc.items() if k not in {"graph_id", "content_sha256", "stats"}}))
    doc["graph_id"] = prefix + ":" + doc["scene_revision"] + ":static:" + doc["content_sha256"][:16]


def seal_receipt(doc):
    # Independently enumerated #260 five-key preimage; metadata is never authority.
    tables = {
        "edge_decisions": ["edge_id", "traversability", "state", "run_ids", "allowed_purposes"],
        "transition_decisions": ["transition_id", "from_camera_id", "to_camera_id", "via_exit_zone_ids", "to_entry_zone_ids", "region_path", "edge_path", "run_ids", "decision", "allowed_purposes"],
        "region_purpose_decisions": ["region_id", "run_ids", "decision", "allowed_purposes", "exclusions"],
        "derived_legal_transitions_by_run": ["run_id", "transition_ids"],
    }
    payload = {"input_pins": doc["input_pins"], **{name: [{k: row[k] for k in fields} for row in doc[name]] for name, fields in tables.items()}}
    doc["decisions_sha256"] = sha(raw(payload))


def build():
    h = sha(b"SYNTHETIC_NOT_A_REAL_SCENE")
    cameras = ["SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"]
    transitions = []
    for dest, regions, edges in [("SYNTHETIC_B", ["SYNTHETIC_R0"], []), ("SYNTHETIC_C", ["SYNTHETIC_R0", "SYNTHETIC_R1"], ["SYNTHETIC_E01"])]:
        transitions.append({"transition_id": "T_SYNTHETIC_A__" + dest, "from_camera_id": cameras[0], "to_camera_id": dest,
            "via_exit_zone_ids": ["SYNTHETIC_A:EXIT"], "to_entry_zone_ids": [dest + ":ENTRY"],
            "region_path": regions, "edge_path": edges, "relation": "UNKNOWN", "region_hops": len(edges),
            "path_traversability": "TOPOLOGICAL_ONLY" if edges else "APPROVED_WALKABLE",
            "path_has_unknown_state": bool(edges), "ranking_area_m2": None, "ranking_area_refs": [],
            "nominal_path_length_m": None, "basis_refs": ["SYNTHETIC_ONLY"]})
    scope = {"schema_version": "q-demo.r004-tracking-scope.v3", "status": "PROPOSED", "G4_approved": False,
        "query_camera_ids": cameras, "tracking_camera_ids": cameras, "query_only_camera_ids": [],
        "directed_pairs": [], "north_floor_y_gt_12": "SYNTHETIC_ONLY", "overlap_pairs_deferred": "SYNTHETIC_ONLY"}
    for a in cameras:
        for b in cameras:
            if a == b:
                continue
            row = {"from_camera_id": a, "to_camera_id": b}
            t = next((t for t in transitions if t["from_camera_id"] == a and t["to_camera_id"] == b), None)
            row.update({"disposition": "TRANSITION", "transition_id": t["transition_id"]} if t else {"disposition": "EXCLUDED", "reason": "SYNTHETIC_NO_TRANSITION"})
            scope["directed_pairs"].append(row)
    scope_pin = write("tracking_scope.json", scope)
    inputs = [{"ref": "tracking-scope:SYNTHETIC:v3", "sha256": scope_pin}]
    region = {"schema_version": "q-demo.region-graph.v1", "scene_id": "SYNTHETIC", "scene_revision": "SYNTHETIC_R1",
        "scene_static_sha256": h, "approval_status": "DRAFT", "approval_ref": None,
        "regions": [{"region_id": rid, "kind": "ROOM", "floor_id": "SYNTHETIC_FLOOR", "walk_ids": [rid + ":WALK"], "polygon_ref": rid + ":POLYGON", "polygon_sha256": h} for rid in ["SYNTHETIC_R0", "SYNTHETIC_R1"]],
        "edges": [{"edge_id": "SYNTHETIC_E01", "regions": ["SYNTHETIC_R0", "SYNTHETIC_R1"], "via": {"kind": "ADJACENT", "ref": "SYNTHETIC_BOUNDARY"}, "direction": "BIDIRECTIONAL", "state": "UNKNOWN", "traversability": "TOPOLOGICAL_ONLY", "basis_refs": ["SYNTHETIC_ONLY"]}],
        "inputs": deepcopy(inputs)}
    seal_graph(region, "rgraph")
    camera = {"schema_version": "q-demo.camera-transition-graph.v1", "scene_id": "SYNTHETIC", "scene_revision": "SYNTHETIC_R1",
        "camera_catalog_sha256": h, "region_graph_sha256": region["content_sha256"], "approval_status": "DRAFT", "approval_ref": None,
        "cameras": [], "transitions": transitions, "inputs": deepcopy(inputs)}
    poly = [[0, 0], [100, 0], [100, 100], [0, 100]]
    for cid in cameras:
        camera["cameras"].append({"camera_id": cid, "calibration_sha256": h,
            "covered_regions": [{"region_id": "SYNTHETIC_R1" if cid == "SYNTHETIC_C" else "SYNTHETIC_R0", "basis": "STATIC_VISIBILITY_INDEX", "visibility_ref": "SYNTHETIC_ONLY", "visible_area_m2": None}],
            "entry_zones": [{"entry_zone_id": cid + ":ENTRY", "roi_polygon_px": poly}],
            "exit_zones": [{"exit_zone_id": cid + ":EXIT", "roi_polygon_px": poly, "leads_to_edge_ids": ["SYNTHETIC_E01"], "mapping_basis": "MANUAL_ON_STATIC_FRAME", "static_frame_ref": "SYNTHETIC_ONLY", "static_frame_sha256": h}]})
    seal_graph(camera, "cgraph")
    region_pin = write("region_graph.json", region)
    camera_pin = write("camera_graph.json", camera)
    run = "SYNTHETIC_RUN"
    purpose = ["SYNTHETIC_UNSELECTED_PURPOSE"]
    receipt = {"schema_version": "q-demo.g4-approval-receipt.v1", "status": "APPROVED", "date": "2000-01-01",
        "fixture_role": "SYNTHETIC_TEST_ONLY_NOT_HUMAN_APPROVAL",
        "approval_ref": "https://example.invalid/SYNTHETIC/checkpoint#comment-1",
        "human_decision_ref": "https://example.invalid/SYNTHETIC/D1#comment-2", "independent_review_ref": None,
        "input_pins": {"scene_id": "SYNTHETIC", "scene_revision": "SYNTHETIC_R1", "source_sha256": h,
            "catalog_sha256": h, "static_sha256": h, "region_graph_file_sha256": region_pin,
            "region_graph_content_sha256": region["content_sha256"], "camera_graph_file_sha256": camera_pin,
            "camera_graph_content_sha256": camera["content_sha256"], "tracking_scope_file_sha256": scope_pin,
            "run_camera_scopes": [{"run_id": run, "camera_ids": cameras, "allowed_purposes": purpose, "exclusions": []}]},
        "edge_decisions": [{"edge_id": "SYNTHETIC_E01", "traversability": "APPROVED_WALKABLE", "state": "OPEN", "run_ids": [run], "allowed_purposes": purpose, "recommendation": "SYNTHETIC_ONLY", "yyin_opinion": "MISSING"}],
        "transition_decisions": [{**{k: t[k] for k in ["transition_id", "from_camera_id", "to_camera_id", "via_exit_zone_ids", "to_entry_zone_ids", "region_path", "edge_path"]}, "run_ids": [run], "decision": "APPROVED", "allowed_purposes": purpose, "recommendation": "SYNTHETIC_ONLY", "yyin_opinion": "MISSING"} for t in transitions],
        "region_purpose_decisions": [{"region_id": rid, "run_ids": [run], "decision": "APPROVED", "allowed_purposes": purpose, "exclusions": [], "recommendation": "SYNTHETIC_ONLY", "yyin_opinion": "MISSING"} for rid in ["SYNTHETIC_R0", "SYNTHETIC_R1"]],
        "derived_legal_transitions_by_run": [{"run_id": run, "transition_ids": []}],
        "approved_purposes": [], "exclusions": [], "provenance": {"producer": "SYNTHETIC_FIXTURE", "gt_read": False}}
    seal_receipt(receipt)
    docs = {"approved": receipt}
    pending = deepcopy(receipt); pending["status"] = "PROPOSED"
    pending["approval_ref"] = pending["human_decision_ref"] = None
    for table in ["edge_decisions", "transition_decisions", "region_purpose_decisions"]:
        for row in pending[table]:
            row["allowed_purposes"] = []
            for key in ["decision", "traversability", "state"]:
                if key in row:
                    row[key] = "PENDING_USER"
    seal_receipt(pending); docs["pending"] = pending
    tampered = deepcopy(receipt); tampered["decisions_sha256"] = "0" * 64; docs["decisions_tampered"] = tampered
    wrong_bytes = deepcopy(receipt); wrong_bytes["provenance"]["bytes_only_change"] = "SYNTHETIC"; docs["registry_pin_mismatch"] = wrong_bytes
    draft = deepcopy(receipt); draft["schema_version"] = "q-demo.g4-approval-receipt-draft.v1"; draft["status"] = "PROPOSED"; docs["draft"] = draft
    missing = deepcopy(receipt); del missing["edge_decisions"][0]["state"]; docs["missing_field"] = missing
    files = {"tracking_scope.json": scope_pin, "region_graph.json": region_pin, "camera_graph.json": camera_pin}
    approved_pin = None
    for name, doc in docs.items():
        filename = "receipt_" + name + ".json"; pin = write(filename, doc); files[filename] = pin
        if name == "approved":
            approved_pin = pin
        registry = {"documents": {"receipt:SYNTHETIC:" + name: {"path": filename,
            "file_sha256": approved_pin if name == "registry_pin_mismatch" else pin,
            "schema_version": doc["schema_version"]}}}
        files["registry_" + name + ".json"] = write("registry_" + name + ".json", registry)
    options = {group: "UNSELECTED" for group in ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "C1", "C2", "C3"]}
    options["_test"] = {"fixture_role": "SYNTHETIC_TEST_CONFIGURATION_NOT_U8_ADOPTION", "selected_contract_cases": {}, "C2_provenance_paths": {
        "response_file_sha256": None, "response_decisions_sha256": None, "journal_file_sha256": None, "journal_decisions_sha256": None}}
    files["contract_options.UNSELECTED.json"] = write("contract_options.UNSELECTED.json", options)
    write("MANIFEST.json", {"fixture_role": "SYNTHETIC_ONLY", "files": files, "approved_decisions_sha256": receipt["decisions_sha256"],
                            "current_graph_authority": "DRAFT; receipt fixtures do not approve graph/scope", "contract_option": "UNSELECTED"})


if __name__ == "__main__":
    build()
