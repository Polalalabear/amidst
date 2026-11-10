"""Read-only checks of existing presentation bundles; never materializes datasets.

Run through the existing uv environment; see the companion engineering audit.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounds(vertices):
    return [[f(v[a] for v in vertices) for a in range(3)] for f in (min, max)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--url", help="Optional local API; creates an ephemeral research session")
    parser.add_argument("--inventory", type=Path, help="Output from audit_auditorium_source.py")
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo / "src"))
    from amidst.workbench.blender_scene import _GEOMETRY, _PINS, _SCALE, _SUPPORT, _source_meshes

    documents = {}
    for relative in (_GEOMETRY, _SUPPORT, _SCALE):
        path = args.evidence / relative
        assert sha(path) == _PINS[relative], relative
        raw = path.read_bytes()
        documents[relative] = json.loads(gzip.decompress(raw) if relative.endswith(".gz") else raw)
    source = args.canonical / "blender/school_v3.blend"
    assert sha(source) == documents[_GEOMETRY]["source_sha256"]
    assert (
        sha(args.repo / "scripts/export_policy_source_evidence.py")
        == documents[_GEOMETRY]["exporter_code_sha256"]
    )
    config = json.loads(
        (args.repo / "configs/physical_policy_source_selection_school_v3.json").read_bytes()
    )
    assert (
        hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == documents[_GEOMETRY]["config_content_sha256"]
    )
    print("source", sha(source), "archive", _PINS[_GEOMETRY])
    bundles = []
    for site, expected, count in (
        ("office", "1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163", 1662),
        ("auditorium", "9555df8e0947a0eb951c2d21d63687ac81033748178d397e45e5221a4f7f321c", 318),
    ):
        path = (
            args.evidence
            / "data/engineering/local_run/blender_camera_v1"
            / site
            / "safe_inputs.json"
        )
        assert sha(path) == expected
        data = json.loads(path.read_bytes())
        bundles.append(data)
        presentation = data["presentation"]
        regenerated = _source_meshes(documents[_GEOMETRY], documents[_SUPPORT], site)
        assert regenerated == presentation, site + " crop differs"
        assert sum(len(m["triangles"]) for m in presentation["meshes"]) == count
        print(
            site,
            "safe_sha",
            expected,
            "triangles",
            count,
            "crop",
            presentation["bounds_metres"],
            "vertex_bounds",
            bounds([v for m in presentation["meshes"] for v in m["vertices"]]),
        )
        print(
            "cameras",
            [
                (c["camera_id"], [c["calibration"]["camera_to_world"][a][3] for a in range(3)])
                for c in data["cameras"]
            ],
        )
    for field in (
        "source_sha256",
        "scale_sha256",
        "model_revision",
        "metres_per_bu",
        "units",
        "native_units",
    ):
        assert bundles[0]["source_binding"][field] == bundles[1]["source_binding"][field], field
    assert {c["camera_id"]: c["calibration"] for c in bundles[0]["cameras"]} == {
        c["camera_id"]: c["calibration"] for c in bundles[1]["cameras"]
    }
    assert bundles[0]["source_binding"]["run_id"] != bundles[1]["source_binding"]["run_id"]
    lo, hi = bundles[1]["presentation"]["bounds_metres"]
    intersecting = []
    for mesh in documents[_GEOMETRY]["meshes"]:
        box = bounds(mesh["vertices"])
        if all(box[1][a] * 0.0247 >= lo[a] and box[0][a] * 0.0247 <= hi[a] for a in range(3)):
            intersecting.append([mesh["source_object_id"], len(mesh["triangles"])])
    print("archive_roi_aabb_superset", intersecting)
    assert {row[0] for row in intersecting} == {"group_0", "group_0.002", "group_0.263"}
    if args.inventory:
        inventory = json.loads(args.inventory.read_bytes())
        assert inventory["source_sha256"] == sha(source) and inventory["source_unchanged"] is True
        assert inventory["scene"] == bundles[0]["presentation"]["evaluated_scene"]
        furniture = [o for o in inventory["objects"] if "evaluated_triangles" in o]
        assert len(furniture) == 94
        assert not set(documents[_GEOMETRY]["excluded_annotation_object_ids"]).intersection(
            o["name"] for o in furniture
        )
        assert not any(o["phase1_annotation_only"] for o in furniture)
        archive_names = {m["source_object_id"] for m in documents[_GEOMETRY]["meshes"]}
        assert not archive_names.intersection(o["name"] for o in furniture)
        for obj in furniture:
            box = obj["evaluated_bounds_m"]
            assert not any(
                all(
                    box[1][a] / 0.0247 >= reg["bounds_bu"]["minimum"][a]
                    and box[0][a] / 0.0247 <= reg["bounds_bu"]["maximum"][a]
                    for a in range(3)
                )
                for reg in documents[_GEOMETRY]["regions"]
            ), obj["name"]
        counts = {
            c: sum(o["evaluated_triangles"] for o in furniture if c in o["collections"])
            for c in ("Theatre Chair", "N1 Hamburg")
        }
        assert counts == {"Theatre Chair": 528784, "N1 Hamburg": 82814}
        unique = {
            obj["evaluated_local_geometry_sha256"]: obj["evaluated_triangles"] for obj in furniture
        }
        assert len(unique) == 19 and sum(unique.values()) == 117103
        for obj in furniture:
            assert not any(obj[k] for k in ("hide_render", "hide_viewport", "hide_get"))
            assert obj["visible_get"] is True
            assert not any(c["hide_render"] or c["hide_viewport"] for c in obj["collection_flags"])
            assert (
                max(
                    abs(x - y)
                    for a, b in zip(obj["bounds_m"], obj["evaluated_bounds_m"], strict=True)
                    for x, y in zip(a, b, strict=True)
                )
                <= 1e-5
            )
        for camera in bundles[0]["cameras"]:
            obj = next(o for o in inventory["objects"] if o["name"] == camera["camera_id"])
            assert (
                max(
                    abs(
                        obj["matrix_world"][a][3] * 0.0247
                        - camera["calibration"]["camera_to_world"][a][3]
                    )
                    for a in range(3)
                )
                < 1e-9
            )
        print("furniture_triangles", counts, "archive_included", 0, "region_intersections", 0)
        print(
            "unique_evaluated_local_meshes",
            len({o["evaluated_local_geometry_sha256"] for o in furniture}),
        )
        print("inventory_sha", sha(args.inventory))
        for family in ("Accoudoir", "Assise", "Dossier", "Fond Dossier", "Pied"):
            parts = [
                o for o in furniture if o["name"] == family or o["name"].startswith(family + ".")
            ]
            assert len(parts) == 16
            assert len({o["evaluated_local_geometry_sha256"] for o in parts}) == (
                2 if family == "Accoudoir" else 1
            )
            print(
                "chair_family",
                family,
                "parts",
                len(parts),
                "unique_geometry",
                len({o["evaluated_local_geometry_sha256"] for o in parts}),
            )
    if args.url:
        assert args.url.startswith("http://127.0.0.1:"), "local URL required"
        opener = build_opener(ProxyHandler({}))

        def fetch(route, payload=None):
            request = Request(
                args.url.rstrip("/") + "/" + route,
                None if payload is None else json.dumps(payload).encode(),
                {} if payload is None else {"Content-Type": "application/json"},
            )
            with opener.open(request, timeout=15) as response:
                return response.read()

        meta = json.loads(fetch("__office_launcher"))
        print("runtime_start_commit", meta["commit"], "pid", meta["pid"])
        for name in ("app.mjs", "scene.mjs", "physical-review.mjs"):
            raw = fetch(name)
            assert raw == (args.repo / "frontend/workbench" / name).read_bytes(), name
            print("served", name, hashlib.sha256(raw).hexdigest())
        session = json.loads(fetch("api/session", {"role": "research"}))
        snapshot = json.loads(
            fetch(
                "api/scene", {"session_ref": session["session_ref"], "scene_id": "blender-office"}
            )
        )["snapshot"]
        assert snapshot["presentation"] == bundles[0]["presentation"]
        print("API_EQUALS_OFFICE_SAFE_PRESENTATION", True)
    print(
        "PASS: existing crop reproduction and common display coordinates; completeness NOT asserted"
    )


if __name__ == "__main__":
    main()
