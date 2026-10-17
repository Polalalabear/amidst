import json
import sys
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

repo = Path.cwd()
fixture_path = repo / "configs/office_demo_office_person_fixture_v1.json"
f = json.loads(fixture_path.read_bytes())
s = load_scene(
    repo / "data/engineering/office_person_20261016_v1/office",
    f,
    perception_version="rgb-mask-contact-v2",
).with_display_identity(f["scene_id"], "Office person", "D18 person run")
bind_hypotheses(s, fixture_path, repo, "configs/office_person_hypothesis_binding_v1.json")


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


out = {}
with tempfile.TemporaryDirectory(prefix="k8a-http-") as tmp:
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    wb = Workbench(
        {s.scene_id: s},
        ReviewStore(Path(tmp) / "r.db", {s.scene_id: {k: s.snapshot()[k] for k in keys}}),
    )
    token = "session:k8a-real-http-compat-v1"
    wb.sessions[token] = Session("research", frozenset({s.scene_id}))
    app = Application(wb, repo)
    with make_server("127.0.0.1", 0, app, handler_class=Quiet) as server:
        url = "http://127.0.0.1:" + str(server.server_port)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        opener = build_opener(ProxyHandler({}))

        def post(name, action, request):
            with opener.open(
                Request(
                    url + "/api/" + action,
                    data=json.dumps(request).encode(),
                    headers={"Content-Type": "application/json", "Origin": url},
                    method="POST",
                ),
                timeout=30,
            ) as response:
                assert response.status == 200
                r = json.loads(response.read())
            if action == "frame_retrieval":
                r["stats"].pop("latency_ms")
            if action == "target_reconstruction":
                assert verify_output_sha256(r["blind_hypotheses"])
            out[name] = {"request": request, "response": r}
            return r

        try:
            request = {
                "session_ref": token,
                "scene_id": s.scene_id,
                "camera_ids": f["camera_ids"],
                "start": 0.0,
                "end": 9.8,
                "top_k": 3,
                "observation_ref": f["observation_ref"],
            }
            for mode in ["NONE", "BASELINE", "BASELINE_AND_FEEDBACK"]:
                post(mode, "target_reconstruction", request | {"negative_evidence_mode": mode})
            baseline = out["BASELINE_AND_FEEDBACK"]["response"]["blind_hypotheses"]
            retrieval = post(
                "RETRIEVAL",
                "frame_retrieval",
                {
                    "session_ref": token,
                    "scene_id": s.scene_id,
                    "query_kind": "TIME_RANGE",
                    "time_range_s": [4.8, 8.0],
                    "max_frames": 64,
                },
            )
            post(
                "FEEDBACK",
                "target_reconstruction",
                request
                | {
                    "negative_evidence_mode": "BASELINE_AND_FEEDBACK",
                    "previous_response_sha256": baseline["output_sha256"],
                    "negative_evidence_refs": [
                        e["negative_evidence_ref"]
                        for e in retrieval["negative_evidence_candidates"]
                    ],
                },
            )
        finally:
            server.shutdown()
            thread.join()
            assert not thread.is_alive()
assert all(
    out[k]["response"]["blind_hypotheses"]["status"] == "READY"
    for k in ["NONE", "BASELINE", "BASELINE_AND_FEEDBACK", "FEEDBACK"]
)
for k in ["NONE", "BASELINE", "BASELINE_AND_FEEDBACK", "FEEDBACK"]:
    assert (
        sum(r["area_m2"] for r in out[k]["response"]["blind_hypotheses"]["reachable_regions"])
        == 281.125
    )
assert len(out["BASELINE"]["response"]["review_evidence"]["applied_frame_keys"]) == 34
assert out["FEEDBACK"]["response"]["pruning_convergence"]["chain_verified"]
assert all(
    r["reason"] == "ALREADY_APPLIED_FRAME"
    for r in out["FEEDBACK"]["response"]["review_evidence"]["feedback_conversion"]["frame_outcomes"]
)


def check(x):
    if isinstance(x, dict):
        assert "data_origin" not in x
        for v in x.values():
            check(v)
    elif isinstance(x, list):
        for v in x:
            check(v)


check(out)
with Path(sys.argv[1]).open("x") as stream:
    json.dump(out, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
print({k: content_hash(v["response"]) for k, v in out.items()})
