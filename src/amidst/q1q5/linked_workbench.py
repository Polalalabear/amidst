"""SYNTHETIC RGB bridge on the shared Workbench Application/session/QAPI."""

import secrets
import time
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from amidst.q1q5.api import QAPI, RecordingStore, from_environment
from amidst.q1q5.linked_runtime import RUN, SCENE, load_rgb, require
from amidst.q1q5.production_preflight import read_pinned, strict_json
from amidst.q1q5.store import canonical_hash
from amidst.workbench.product_bridge import BinaryResponse
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Session, Workbench

MEDIA = "/api/controlled_scene_media"


class LinkedWorkbench(Workbench):
    def session(self, payload):
        result = super().session(payload)
        # Only this explicitly synthetic adapter adds its registered Q scene.
        old = self.sessions[result["session_ref"]]
        self.sessions[result["session_ref"]] = Session(old.role, frozenset({SCENE}))
        return result


class SyntheticRGB:
    def __init__(self, path, pin, workbench, *, clock=time.monotonic):
        self.run = load_rgb(path, pin)
        self.workbench, self.clock, self.grants = workbench, clock, {}

    def authorize(self, token):
        session = self.workbench._session(token)
        require(SCENE in session.scene_ids, "SCENE_DENIED")

    def call(self, action, payload):
        require(
            action == "synced_frames"
            and set(payload)
            == {"schema_version", "session_ref", "scene_id", "run_id", "t_s", "camera_ids"}
            and payload["schema_version"] == "controlled-scene.synced-frames-request.v1"
            and payload["scene_id"] == SCENE
            and payload["run_id"] == RUN,
            "SYNTHETIC_RGB_SCOPE",
        )
        self.authorize(payload["session_ref"])
        cameras = payload["camera_ids"]
        require(
            isinstance(cameras, list)
            and cameras
            and len(set(cameras)) == len(cameras)
            and set(cameras) <= {"A", "B"},
            "RGB_CAMERA_SCOPE",
        )
        micros = Fraction(str(payload["t_s"])) * 1_000_000
        require(micros.denominator == 1 and micros >= 0, "RGB_TIME_GRID")
        stamp = int(micros)
        frame = stamp // 200_000
        pending, tiles = [], []
        for camera in cameras:
            tile = dict(camera_id=camera, frame_ref=None, media_url=None, status="OUT_OF_RANGE")
            if frame < 10:
                row = self.run.rgb_record(camera, frame)
                self.run.read_rgb(camera, frame)  # Verify EVERY requested PNG before grants.
                tile.update(
                    status="READY",
                    frame_ref=f"frame:{RUN}:{camera}:{frame}",
                    frame_index=frame,
                    timestamp_s=frame / 5,
                    file_sha256=row["file_sha256"],
                    served_sha256=row["file_sha256"],
                    media_token_ttl_s=60,
                )
                pending.append((tile, camera, frame, row["file_sha256"]))
            tiles.append(tile)
        now = self.clock()
        self.grants = {k: v for k, v in self.grants.items() if v["expires"] > now}
        require(len(self.grants) + len(pending) <= 4096, "MEDIA_GRANT_LIMIT")
        for tile, camera, frame, pin in pending:
            token = secrets.token_urlsafe(32)
            self.grants[token] = dict(
                session_ref=payload["session_ref"],
                camera=camera,
                frame=frame,
                pin=pin,
                expires=now + 60,
            )
            tile["media_url"] = MEDIA + "?token=" + token
        result = dict(
            schema_version="controlled-scene.synced-frames.v1",
            status="READY",
            data_origin="SYNTHETIC",
            rgb_source_kind="SYNTHETIC_GENERATED_RGB",
            identity_verdict="UNCONFIRMED",
            agent_used=False,
            resolved_scope=dict(scene_id=SCENE, run_id=RUN),
            clock_id="SYNTHETIC_CLOCK",
            t_us=stamp,
            frame_rule="LATEST_AT_OR_BEFORE_EXPECTED_GRID",
            tiles=tiles,
            provenance=dict(gt_read=False, producer="q1q5-linked-synthetic-rgb"),
        )
        result["output_sha256"] = canonical_hash(
            {**result, "tiles": [{**tile, "media_url": None} for tile in tiles]}
        )
        return result

    def media(self, token):
        require(token in self.grants, "MEDIA_TOKEN_INVALID")
        grant = self.grants[token]
        require(self.clock() < grant["expires"], "MEDIA_TOKEN_EXPIRED")
        self.authorize(grant["session_ref"])
        row = self.run.rgb_record(grant["camera"], grant["frame"])
        require(row["file_sha256"] == grant["pin"], "MEDIA_PIN_MISMATCH")
        return self.run.read_rgb(grant["camera"], grant["frame"])


class LinkedApplication(Application):
    def _dispatch(self, environ):
        if environ.get("PATH_INFO") == MEDIA:
            try:
                host = environ.get("HTTP_HOST", "")
                url = urlsplit("http://" + host)
                require(
                    url.hostname in {"127.0.0.1", "localhost", "::1"}
                    and not url.username
                    and not url.password
                    and url.path == ""
                    and not url.query
                    and not url.fragment
                    and (url.port or 80) == int(environ["SERVER_PORT"]),
                    "HOST_DENIED",
                )
                require(
                    environ["REQUEST_METHOD"] == "GET"
                    and environ.get("HTTP_ORIGIN") in {None, "http://" + host}
                    and environ.get("HTTP_SEC_FETCH_SITE") != "cross-site",
                    "ORIGIN_DENIED",
                )
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                require(set(query) == {"token"} and len(query["token"]) == 1, "MEDIA_QUERY")
                return BinaryResponse(
                    200, "image/png", (), self.q_api.rgb_api.media(query["token"][0])
                )
            except (ValueError, KeyError):
                return BinaryResponse(
                    403, "application/json", (), b'{"error_code":"RGB_ACCESS_REJECTED"}'
                )
        return super()._dispatch(environ)


def application(repo, rgb, rgb_pin, private_root, *, recordings=None, recordings_pin=None):
    """Environment pins are loaded by the original registry/runtime loader."""
    private_root = Path(private_root)
    require(
        not private_root.exists() and private_root.parent.is_dir(), "NEW_WORKBENCH_PRIVATE_ROOT"
    )
    private_root.mkdir(mode=0o700)
    wb = LinkedWorkbench({}, ReviewStore(private_root / "review.sqlite3", {}))
    bridge = SyntheticRGB(rgb, rgb_pin, wb)
    api = from_environment(bridge, Path(repo))
    require(
        len(api.runs) == 1
        and all(
            r.source_kind == "SYNTHETIC"
            and r.catalog["scene_id"] == SCENE
            and r.catalog["run_id"] == RUN
            and r.bindings.index.manifest["rgb_index_sha256"] == rgb_pin
            for r in api.runs.values()
        ),
        "SYNTHETIC_WORKBENCH_ONLY",
    )
    require(bool(recordings) == bool(recordings_pin), "RECORDING_CATALOG_PIN_REQUIRED")
    if recordings:
        catalog = strict_json(read_pinned(Path(recordings), recordings_pin))
        require(
            set(catalog) == {"schema_version", "recording_root", "recordings"}
            and catalog["schema_version"] == "q-demo.linked-recordings.v1",
            "RECORDING_CATALOG",
        )
        store = RecordingStore(
            Path(catalog["recording_root"]), repo_root=Path(repo), max_bytes=16_777_216
        )
        api = QAPI(
            list(api.runs.values()),
            max_responses=128,
            max_media_refs=4096,
            recording_store=store,
            recordings=catalog["recordings"],
            rgb_api=bridge,
        )
    (private_root / "recordings").mkdir(mode=0o700)
    api.recording_store = RecordingStore(
        private_root / "recordings", repo_root=Path(repo), max_bytes=16_777_216
    )
    return LinkedApplication(wb, Path(repo), q_api=api)
