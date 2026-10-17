"""Freeze a bounded C4b API response without serving HTTP, GT or rendering."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from office_demo_backend import load_scene

from amidst.blind_hypothesis import verify_output_sha256
from amidst.engineering.registry import content_hash
from amidst.workbench.blind_hypothesis_integration import bind_hypotheses
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Session, Workbench

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.bundle.resolve()):
        raise ValueError("OUTPUT_EXISTS_OR_INSIDE_INPUT")
    fixture_path = REPO / "configs/office_demo_office_person_fixture_v1.json"
    fixture = json.loads(fixture_path.read_text())
    scene = load_scene(args.bundle, fixture, perception_version="rgb-mask-contact-v2")
    scene = scene.with_display_identity(fixture["scene_id"], "Office person", "D18 person run")
    bind_hypotheses(scene, fixture_path, REPO, "configs/office_person_hypothesis_binding_v1.json")
    original = content_hash(scene.index.observations)
    with tempfile.TemporaryDirectory(prefix="amidst-c4b-review-") as directory:
        keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
        reviews = ReviewStore(
            Path(directory) / "reviews.db", {scene.scene_id: {k: scene.snapshot()[k] for k in keys}}
        )
        workbench = Workbench({scene.scene_id: scene}, reviews)
        # A fixed offline session makes the K5 request fingerprint reproducible.
        # No HTTP service exists and this token authorizes no running service.
        token = "session:c4b-offline-reproducible-person-v1"
        workbench.sessions[token] = Session("research", frozenset({scene.scene_id}))
        request = {
            "session_ref": token,
            "scene_id": scene.scene_id,
            "camera_ids": fixture["camera_ids"],
            "start": 0.0,
            "end": 9.8,
            "top_k": 3,
            "observation_ref": fixture["observation_ref"],
        }
        initial = workbench.call("target_reconstruction", request)
        previous = initial["blind_hypotheses"]["output_sha256"]
        rerun = workbench.call(
            "target_reconstruction", request | {"previous_response_sha256": previous}
        )
    if original != content_hash(scene.index.observations) or not all(
        verify_output_sha256(r["blind_hypotheses"]) for r in (initial, rerun)
    ):
        raise RuntimeError("ORIGINAL_OR_RESPONSE_HASH_MISMATCH")
    dependencies = json.loads(
        (REPO / "docs/engineering/C4B_DEPENDENCIES_20261017.json").read_text()
    )
    producer_files = [
        "scripts/freeze_person_blind_hypotheses.py",
        "scripts/office_demo_backend.py",
        "src/amidst/workbench/blind_hypothesis_integration.py",
        "src/amidst/workbench/service.py",
        "src/amidst/workbench/contact_scene.py",
        "src/amidst/engineering/hybrid_contact.py",
        "configs/office_demo_office_person_fixture_v1.json",
        "configs/office_person_hypothesis_binding_v1.json",
        "configs/office_person_blind_hypothesis_v1.json",
        "configs/office_person_contact_v2.json",
        "configs/hybrid_contact_v1.json",
    ]
    if any(sha(REPO / f) != expected for f, expected in dependencies["files_sha256"].items()):
        raise RuntimeError("IMPORTED_DEPENDENCY_CHANGED")
    payload = {
        "schema_version": "office-demo.c4b-frozen-response.v1",
        "gt_read": False,
        "run_id": scene.run_id,
        "source_sha256": scene.source_hash,
        "safe_inputs_sha256": sha(args.bundle / "safe_inputs.json"),
        "original_observations_sha256": original,
        "original_observation_count": len(scene.index.observations),
        "original_missing_null_count": sum(
            r["state"] == "MISSING" and r["world_position"] is None
            for r in scene.index.observations
        ),
        "dependencies": dependencies,
        "producer_files_sha256": {f: sha(REPO / f) for f in producer_files},
        "initial": initial,
        "no_new_evidence_rerun": rerun,
        "real_negative_evidence": "UNAVAILABLE_C5_NOT_REGISTERED",
        "physical_authority": "UNKNOWN",
        "identity_verdict": "UNCONFIRMED",
    }
    payload["output_sha256"] = content_hash(payload)
    with args.output.open("x") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    b = initial["blind_hypotheses"]
    print(
        json.dumps(
            {
                "artifact_sha256": sha(args.output),
                "status": b["status"],
                "reason": b["reason"],
                "hypotheses": len(b["hypotheses"]),
                "reachable_regions": len(b["reachable_regions"]),
                "k5_no_new_evidence_rerun": rerun["blind_hypotheses"]["status"],
            }
        )
    )


if __name__ == "__main__":
    main()
