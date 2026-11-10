#!/usr/bin/env python3
"""Bounded real safe-RGB WSGI check, without listeners, image decoding or inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from amidst.workbench import controlled_scene_data, controlled_scene_rgb_data
from amidst.workbench.controlled_scene_rgb_api import ControlledRGBAPI
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Workbench


def http(app, url, payload=None):
    parts = urlsplit(url)
    raw = json.dumps(payload).encode() if payload is not None else b""
    env = {"HTTP_HOST": "127.0.0.1:12345", "SERVER_PORT": "12345",
           "REQUEST_METHOD": "POST" if payload is not None else "GET",
           "PATH_INFO": parts.path, "QUERY_STRING": parts.query, "wsgi.input": BytesIO(raw),
           "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw))}
    result = {}

    def start(status, headers):
        result.update(status=int(status.split()[0]), headers=dict(headers))

    body = b"".join(app(env, start))
    if result["status"] != 200:
        raise RuntimeError(f"CHECK_HTTP_{result['status']}")
    return body, result["headers"]


def check(repo: Path) -> dict:
    runs = controlled_scene_rgb_data.registrations(repo)
    counts = Counter()
    hashes = {}
    reader = controlled_scene_data.read_regular

    def safe_read(root, relative, **kwargs):
        if (root not in {r.run_root for r in runs}
                or not (relative in {"safe_bundle/manifest.json", "safe_bundle/scene_static.json",
                                     "safe_bundle/cameras.json", "safe_bundle/runtime_profile.json",
                                     "safe_bundle/rgb_index.json"} or relative.startswith("rgb/"))):
            raise RuntimeError("READ_SCOPE_VIOLATION")
        raw = reader(root, relative, **kwargs)
        key = root.name + "/" + relative
        counts[key] += 1
        digest = hashlib.sha256(raw).hexdigest()
        if key in hashes and hashes[key] != digest:
            raise RuntimeError("INPUT_CHANGED_DURING_CHECK")
        hashes[key] = digest
        return raw

    controlled_scene_data.read_regular = controlled_scene_rgb_data.read_regular = safe_read
    try:
        with tempfile.TemporaryDirectory(prefix="controlled-rgb-2a-") as state:
            api = ControlledRGBAPI(runs)
            wb = Workbench({}, ReviewStore(Path(state) / "review.db", {}), controlled_scene=api)
            app = Application(wb, repo)
            token = wb.session({"role": "research"})["session_ref"]
            bootstrap = json.loads(http(app, "/api/bootstrap?surface=workbench-v2")[0])
            results = []
            for run in bootstrap["scenes"][0]["runs"]:
                rows = []
                for t in (0, 5, run["sampling"]["last_timestamp_s"]):
                    result = json.loads(http(app, "/api/synced_frames", {
                        "schema_version": "controlled-scene.synced-frames-request.v1",
                        "session_ref": token, "scene_id": runs[0].scene_id, "run_id": run["run_id"],
                        "t_s": t, "camera_ids": run["camera_ids"]})[0])
                    for tile in result["tiles"]:
                        body, headers = http(app, tile["media_url"])
                        if (tile["status"] != "READY" or headers["Content-Type"] != "image/png"
                                or hashlib.sha256(body).hexdigest() != tile["served_sha256"]):
                            raise RuntimeError("RGB_MEDIA_CHECK_FAILED")
                        rows.append({k: tile[k] for k in ("camera_id", "frame_index", "timestamp_s",
                                                         "file_sha256", "served_sha256")})
                results.append({"run_id": run["run_id"], "manifest_sha256": run["manifest_sha256"],
                                "runtime_readiness": run["runtime_readiness"],
                                "input_adapter_receipts": run["input_adapter_receipts"],
                                "rgb_checks": rows})
            return {"schema_version": "controlled-rgb-playback-check.v1", "status": "PASS",
                    "data_origin": bootstrap["data_origin"], "gt_read": False,
                    "private_read": False, "listener_started": False, "inference_run": False,
                    "runs": results, "read_counts": dict(sorted(counts.items())),
                    "input_file_sha256": dict(sorted(hashes.items()))}
    finally:
        controlled_scene_data.read_regular = controlled_scene_rgb_data.read_regular = reader


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.repo.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Receipts are versioned by their caller; never overwrite an earlier result.
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "runs": len(result["runs"]),
                      "rgb_checks": sum(len(r["rgb_checks"]) for r in result["runs"]),
                      "receipt": str(args.output),
                      "file_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
