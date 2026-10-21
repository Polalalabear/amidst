"""Explicit offline producer; all output stays outside the repository.

Indexer config is an operator-only receipt (not a query API). Its parameter_set
must approve index_score_floor, stride_samples, index_grid_origin_frame and an
HSVConfig value named hsv_config. Missing values never receive smoke defaults.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from amidst.q1q5.detection_index import (
    OfficialRTDetrR18, build_detection_index, content_hash, write_index,
)
from amidst.q1q5.hsv_color import HSVConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "config", "config-sha256", "run-id", "weights", "model-source", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--permit-real-rgb", action="store_true")
    args = parser.parse_args(argv)
    if not args.permit_real_rgb:
        parser.error("Real RGB inference requires explicit operator authorization")
    raw = Path(args.config).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.config_sha256:
        parser.error("Indexer config hash mismatch")
    config = json.loads(raw)
    parameters = config["parameter_set"]
    if (parameters["approval"]["status"] != "APPROVED"
            or parameters["content_sha256"] != content_hash(parameters, ("content_sha256", "parameter_set_id"))):
        parser.error("PARAMETERS_NOT_APPROVED")
    values = {p["name"]: p["value"] for p in parameters["parameters"] if p["status"] == "APPROVED"}
    needed = {"index_score_floor", "stride_samples", "index_grid_origin_frame", "hsv_config"}
    if not needed.issubset(values):
        parser.error("PARAMETERS_NOT_APPROVED: missing " + ", ".join(sorted(needed - values.keys())))
    repo, output = Path(args.repo).resolve(), Path(args.output).absolute()
    allowed = (Path.home() / "amidst-artifacts").resolve()
    if output.resolve() != output or not output.is_relative_to(allowed) or output.is_relative_to(repo):
        parser.error("Output must be canonical and under ~/amidst-artifacts, outside repo")
    subprocess.run(["df", "-h", str(repo)], check=True)
    subprocess.run(["df", "-k", str(repo)], check=True)
    from amidst.workbench.controlled_scene_rgb_data import load_rgb_playback, registrations
    registrations_by_id = {r.run_id: r for r in registrations(repo)}
    if args.run_id not in registrations_by_id:
        parser.error("Run not in server-owned A/B1 playback registration")
    run = load_rgb_playback(registrations_by_id[args.run_id])
    model = OfficialRTDetrR18(Path(args.model_source), Path(args.weights),
                            source_hashes=config["source_hashes"], seed=config["seed"],
                            threads=config["threads"])
    artifact = build_detection_index(
        run, model, scene_revision="r003", stride_samples=values["stride_samples"],
        index_grid_origin_frame=values["index_grid_origin_frame"],
        index_score_floor=values["index_score_floor"], color_config=HSVConfig(**values["hsv_config"]),
    )
    write_index(artifact, output)
    print(json.dumps({"index_id": artifact.manifest["index_id"],
                      "content_sha256": artifact.manifest["content_sha256"],
                      "records_file_sha256": artifact.manifest["records_file_sha256"],
                      "stats": artifact.stats}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
