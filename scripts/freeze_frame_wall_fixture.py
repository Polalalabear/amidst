"""Capture actual loopback POSTs for K5 frontend integration, without GT."""

import argparse
import copy
import hashlib
import json
import tempfile
import threading
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
from wsgiref.simple_server import WSGIRequestHandler, make_server

from office_demo_backend import load_scene

from amidst.blind_hypothesis import verify_output_sha256
from amidst.engineering.registry import content_hash
from amidst.workbench.blind_hypothesis_integration import bind_hypotheses
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Session, Workbench

REPO = Path(__file__).resolve().parents[1]


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


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
    fixture = json.loads(fixture_path.read_bytes())
    scene = load_scene(args.bundle, fixture, perception_version="rgb-mask-contact-v2")
    scene = scene.with_display_identity(fixture["scene_id"], "Office person", "D18 person run")
    bind_hypotheses(scene, fixture_path, REPO, "configs/office_person_hypothesis_binding_v1.json")
    original = content_hash(scene.index.observations)
    captures, measured = [], {}
    with tempfile.TemporaryDirectory(prefix="amidst-k5-http-") as directory:
        keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
        reviews = ReviewStore(
            Path(directory) / "review.db", {scene.scene_id: {k: scene.snapshot()[k] for k in keys}}
        )
        workbench = Workbench({scene.scene_id: scene}, reviews)
        # This fixed token only exists in this short-lived isolated capture process.
        token = "session:k5-http-fixture-person-v1"
        workbench.sessions[token] = Session("research", frozenset({scene.scene_id}))
        app = Application(workbench, REPO)
        with make_server("127.0.0.1", 0, app, handler_class=Quiet) as server:
            url = "http://127.0.0.1:" + str(server.server_port)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opener = build_opener(ProxyHandler({}))

            def post(name, action, request):
                wire = json.dumps(request, allow_nan=False).encode()
                req = Request(
                    url + "/api/" + action,
                    data=wire,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": url,
                    },
                )
                with opener.open(req, timeout=30) as response:
                    assert response.status == 200
                    result = json.loads(response.read())
                result = copy.deepcopy(result)
                if action == "frame_retrieval":
                    measured[name] = result["stats"].pop("latency_ms")
                    body = {k: v for k, v in result.items() if k != "output_sha256"}
                    assert content_hash(body) == result["output_sha256"]
                captures.append(
                    {
                        "name": name,
                        "method": "POST",
                        "path": "/api/" + action,
                        "http_status": 200,
                        "request": request,
                        "response": result,
                        "request_sha256": content_hash(request),
                        "response_sha256": content_hash(result),
                        "volatile_response_fields_omitted": ["stats.latency_ms"]
                        if action == "frame_retrieval"
                        else [],
                    }
                )
                return result

            try:
                scope = {"session_ref": token, "scene_id": scene.scene_id}
                none = post(
                    "C4B_NONE",
                    "target_reconstruction",
                    scope
                    | {
                        "camera_ids": fixture["camera_ids"],
                        "start": 0.0,
                        "end": 9.8,
                        "top_k": 3,
                        "observation_ref": fixture["observation_ref"],
                        "negative_evidence_mode": "NONE",
                    },
                )
                hypothesis = none["blind_hypotheses"]
                assert hypothesis["status"] == "READY" and verify_output_sha256(hypothesis)
                assert not hypothesis["negative_evidence_applied"]
                query = scope | {
                    "query_kind": "TIME_RANGE",
                    "time_range_s": [4.8, 8.0],
                    "max_frames": 64,
                }
                post("TIME_RANGE", "frame_retrieval", query)
                for use in ["PATHS", "REACHABLE_REGIONS"]:
                    post(
                        "HYPOTHESIS_" + use,
                        "frame_retrieval",
                        query
                        | {
                            "query_kind": "HYPOTHESIS",
                            "hypothesis": {
                                "response_sha256": hypothesis["output_sha256"],
                                "hypothesis_refs": [],
                                "use": use,
                            },
                        },
                    )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive()
    assert original == content_hash(scene.index.observations)
    binding = scene._blind_hypothesis.binding
    index_path = REPO / binding["visibility_index"]
    index = json.loads(index_path.read_bytes())
    payload = {
        "schema_version": "office-demo.k5-http-frame-wall-fixture.v1",
        "base_commit": "4019a44f1dc22130e7b6013179ac86c899ca1200",
        "transport": "ACTUAL_LOOPBACK_HTTP_POST_DYNAMIC_PORT_SERVER_CLOSED_AFTER_CAPTURE",
        "session_scope": "CAPTURE_PROCESS_ONLY_NOT_A_LIVE_SERVICE_TOKEN",
        "gt_read": False,
        "renderer_visibility_read": False,
        "run_id": scene.run_id,
        "source_sha256": scene.source_hash,
        "safe_inputs_sha256": sha(args.bundle / "safe_inputs.json"),
        "original_observations_sha256": original,
        "cases": captures,
        "visibility_index_context": {
            "source_path": binding["visibility_index"],
            "sha256": sha(index_path),
            "purpose": "INDEX_CONTEXT_SEPARATE_FROM_UNMODIFIED_API_RESPONSES",
            "entries": [
                {
                    k: e[k]
                    for k in (
                        "camera_id",
                        "visibility_ref",
                        "method",
                        "visibility_rule",
                        "polygons",
                        "suggestion_polygons",
                        "area_m2",
                        "suggestion_area_m2",
                    )
                }
                for e in index["entries"]
            ],
        },
        "api_absent_fields": {
            "response.visibility_entries[*].suggestion_polygons": (
                "NOT_EXPOSED_BY_CURRENT_RESOLVED_API_ENTRY; supplied separately as index context"
            ),
        },
        "producer_files_sha256": {
            p: sha(REPO / p)
            for p in [
                "scripts/freeze_frame_wall_fixture.py",
                "scripts/office_demo_backend.py",
                "src/amidst/workbench/service.py",
                "src/amidst/workbench/frame_retrieval.py",
                "src/amidst/workbench/blind_hypothesis_integration.py",
                "src/amidst/workbench/contact_scene.py",
                "configs/office_person_hypothesis_binding_v1.json",
            ]
        },
    }
    payload["output_sha256"] = content_hash(payload)
    with args.output.open("x") as stream:
        json.dump(payload, stream, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "sha256": sha(args.output),
                "cases": [
                    {
                        "name": c["name"],
                        "status": c["response"].get("status"),
                        "frames": c["response"].get("stats", {}).get("frames_suggested"),
                        "candidates": len(c["response"].get("negative_evidence_candidates", [])),
                    }
                    for c in captures
                ],
                "local_only_measured_latency_ms": measured,
            }
        )
    )


if __name__ == "__main__":
    main()
