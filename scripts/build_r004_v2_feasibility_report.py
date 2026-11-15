"""Assemble #516 design evidence; never manufactures measured RGB or gate verdicts."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--service-root", type=Path, required=True)
    p.add_argument("--scenario", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--mesh-report", type=Path, required=True)
    p.add_argument("--color-report", type=Path, required=True)
    p.add_argument("--estimate", type=Path, required=True)
    p.add_argument("--clearance", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cost-proof", type=Path)
    a = p.parse_args()
    a.repo = a.repo.resolve()
    a.scenario = a.scenario.resolve()
    read = lambda p: json.loads(p.read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    git_sha = subprocess.check_output(
        ["git", "-C", str(a.repo), "rev-parse", "HEAD"], text=True
    ).strip()
    doc, mesh, color, estimate = map(read, [a.scenario, a.mesh_report, a.color_report, a.estimate])
    clearance = read(a.clearance)
    cost = read(a.cost_proof) if a.cost_proof else None
    assert clearance["verdict"] == "PASS"
    assert all(r["checks"]["walls"]["status"] == "PASS" for r in clearance["runs"])
    assert sha(a.scenario) == mesh["scenario_sha256"] == color["scenario_sha256"]
    geometry_file = a.repo / "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json"
    geo = read(geometry_file)
    source = a.service_root / geo["provenance"]["source_blend"]["path"]
    export_file = a.service_root / "local/evidence/codex-516-feasibility-20261110/scene_export.json"
    export = read(export_file)
    assert sha(export_file) == geo["provenance"]["codex_feasibility"]["scene_export_sha256"]
    assert sha(source) == mesh["source_sha256_before"] == mesh["source_sha256_after"]
    objs = {x["name"]: x for x in export["objects"]}
    walls, furniture = [], []
    for s in geo["clearance_segments"]:
        item = {k: s[k] for k in ["segment_id", "a", "b"]}
        item["height_range_m"] = objs[s["collider"]]["bounds_world_m"][2]
        (walls if s["collider"].startswith("WALL_") else furniture).append(item)
    geometry, spawn = {}, {}
    for run in doc["runs"]:
        rid = run["run_id"]
        doors = []
        for d in run["doors"]:
            actual = geo["door_openings"][d["door_id"]]
            doors.append(
                {
                    "door_id": d["door_id"],
                    **{k: actual[k] for k in ["center_xy", "normal_xy", "width_m"]},
                    "geometry_status": "MEASURED",
                    "source_sha256": sha(source),
                }
            )
        geometry[rid] = {
            "floor_z_m": 0,
            "floor_context": "indoor 0m; exterior -0.06m, floor regions in source geometry",
            "walls": walls,
            "furniture": furniture,
            "doors": doors,
        }
        spawn[rid] = []
        for r in mesh["endpoints"]:
            if r["run_id"] != rid:
                continue
            spawn[rid].append(
                {
                    "actor_id": r["actor_id"],
                    "kind": r["kind"],
                    "xy": r["xy"],
                    "timestamp_us": r["time_us"],
                    "method": "static_projection",
                    "outside_all_render_cameras": r["status"] == "PASS",
                    "cameras_checked": [c["camera_id"] for c in r["cameras"]],
                    "mesh_evidence_status": r["status"],
                    "camera_results": r["cameras"],
                }
            )
    epochs = {r["run_id"]: r["ambiguous_episodes"] for r in estimate}
    by_cam = []
    for run in doc["runs"]:
        for cam in run["render_camera_ids"]:
            rows = [
                r
                for r in color["rows"]
                if r["run_id"] == run["run_id"] and r["camera_id"] == cam and r["actor_id"] == "B"
            ]
            assert len(rows) == 1
            worst = min(rows[0]["variants"], key=lambda r: r["red_margin"])
            by_cam.append(
                {
                    "run_id": run["run_id"],
                    "camera_id": cam,
                    "b_hue_measured": worst["hsv"][0],
                    "measurement_kind": "NO_RENDER_PROXY_NOT_RGB",
                    "in_band": worst["expected_band"],
                    "crop_ratio": 0.5,
                    "min_margin_proxy": worst["red_margin"],
                    "hue_proxy_range": color["b_hue_proxy_range"],
                }
            )

    def pin(relative_path, path, storage="GIT"):
        return {
            "relative_path": relative_path,
            "sha256": sha(path),
            "git_sha": git_sha,
            "git_sha_role": "audit_code_baseline; not an asset Git object",
            "storage": storage,
        }

    inputs = [
        pin(str(a.scenario.relative_to(a.repo)), a.scenario),
        pin(
            "scripts/design/check_actor_clearance.py",
            a.repo / "scripts/design/check_actor_clearance.py",
        ),
        pin(str(source.relative_to(a.service_root)), source, "LOCAL"),
        pin(
            str((a.evidence / "hsv_config.json").relative_to(a.service_root)),
            a.evidence / "hsv_config.json",
            "LOCAL",
        ),
        pin("docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json", geometry_file),
    ]
    report = {
        "schema": "amidst.r004-v2-feasibility.v1",
        "inputs": inputs,
        "scenario_revision": doc.get("revision"),
        "geometry": geometry,
        "clearance": {
            "verdict": "PASS",
            "walls_status": "PASS",
            "checker_git_sha": git_sha,
            "command": "uv run python scripts/design/check_actor_clearance.py "
            + str(a.scenario.relative_to(a.repo)),
        },
        "spawn_points": spawn,
        "color": {
            "red_band_hue": [0.95, 0.05],
            "hsv_config_sha256": color["hsv_config_sha256"],
            "t_hue": color["shader_hsv"]["T"][0],
            "a_hue": color["shader_hsv"]["A"][0],
            "c_hue": color["shader_hsv"]["C"][0],
            "a_in_band": True,
            "c_in_band": False,
            "b_by_camera": by_cam,
            "measurement_kind": "shader and illuminant proxy; no new RGB; b_hue_measured is legacy schema field for the proxy value",
            "limitations": color["boundary"],
        },
        "ambiguity": {
            "unit": "episode",
            "color_variant": "in_band",
            "episodes": epochs,
            "total_episodes": sum(map(len, epochs.values())),
            "method": "unchanged estimate_plan_decision_points.py; assumed coverage, perfect detection; planning estimate",
        },
        "render_cost": {
            "runs": {
                "A4-1-v2-4actor": {"render_seconds_estimate": 3000, "disk_gib_estimate": 2.2},
                "B4-1-v2-4actor": {"render_seconds_estimate": 1000, "disk_gib_estimate": 1.3},
            },
            "free_gib_before": cost['free_bytes'] / 1024**3 if cost else shutil.disk_usage(a.evidence).free / 1024**3,
            "total_disk_gib_estimate": 3.5,
            "includes_frames": True,
            "estimate_basis": "2630 new PNG + 1050 reused; safe PNG sanitization needs separate pixels/chunks files, plus 18 movies and indexes; 3.5GiB conservative total, not a measured bound",
        },
        "actor_cloning": {
            "feasible": all(x["independent_meshes"] for x in mesh["clone_checks"]),
            "materials": {
                "A": "original T red shader; gray trousers",
                "B": "H=.012 S=.75 V=.65; navy trousers",
                "C": "H=.62 S=.75 V=.65; beige trousers",
            },
            "shared_animation": True,
            "animation_scope": "approved #527 low-flex walking and corrected arms; same gait kernel, independent authored roots",
        },
        "boundary": {
            "rendered": False,
            "blend_saved": False,
            "gt_read": False,
            "wrote_local_dir": True,
            "local_dir": str(a.evidence.relative_to(a.service_root)),
        },
    }
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
