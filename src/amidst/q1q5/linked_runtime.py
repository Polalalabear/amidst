"""One SYNTHETIC pixel/index/registry chain; no fabricated detector observations."""

import hashlib
import io
import json
import os
import shutil
import stat
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from amidst.q1q5.baseline_runner import save
from amidst.q1q5.detection_index import OfficialRTDetrR18, build_detection_index, write_index
from amidst.q1q5.hsv_color import HSVConfig
from amidst.q1q5.ollama_runtime import validate_config
from amidst.q1q5.production_preflight import metadata_ref, read_pinned, strict_json
from amidst.q1q5.q3_parse import ParseSettings
from amidst.q1q5.runtime_telemetry import ProcessSampler, StageMetrics
from amidst.q1q5.store import canonical_hash

SCENE = "SYNTHETIC_SCENE"
RUN = "SYNTHETIC_RUN"
TOKEN = "LINKED_LOCAL_OPERATOR"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def binary(path, pin):
    path = Path(path)
    require(
        path.is_absolute() and path.resolve() == path and path.is_file(), "CANONICAL_RGB_REQUIRED"
    )
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(
            stat.S_ISREG(info.st_mode) and info.st_size <= 16_777_216,
            "RGB_TOO_LARGE_OR_NOT_REGULAR",
        )
        raw = handle.read(16_777_217)
    require(len(raw) == info.st_size, "RGB_CHANGED")
    require(hashlib.sha256(raw).hexdigest() == pin, "RGB_PIN_MISMATCH")
    return raw


def materialize_rgb(assets, assets_pin, output):
    """Producer stage only. Generated source captions never enter this safe manifest."""
    from PIL import Image

    assets, output = Path(assets), Path(output)
    doc = strict_json(read_pinned(assets, assets_pin))
    require(
        doc["schema_version"] == "q-demo.synthetic-rgb-assets.v1"
        and doc["formal_dataset"] is False
        and {r["camera_id"] for r in doc["sources"]} == {"A", "B"},
        "SYNTHETIC_ASSETS_REQUIRED",
    )
    require(
        not output.exists() and output.resolve() == output and output.parent.is_dir(),
        "NEW_RGB_OUTPUT_REQUIRED",
    )
    playback = doc.get("engineering_playback")
    require(
        playback is None
        or playback
        == dict(
            duration_s=6,
            fps=5,
            camera_a_visible_until_s=2,
            camera_b_visible_from_s=3,
            method="STATIC_RGB_HOLD_NO_MOTION",
        ),
        "PLAYBACK_CONFIG",
    )
    duration_s = 6 if playback else 2
    count = duration_s * 5
    output.mkdir(mode=0o700)
    (output / "media").mkdir()
    transforms = []
    for row in doc["sources"]:
        raw = binary(metadata_ref(assets.parent, row["ref"]), row["file_sha256"])
        with Image.open(io.BytesIO(raw)) as image:
            require(
                list(image.size) == row["image_size_px"] and image.format == "PNG",
                "SOURCE_RGB_METADATA",
            )
            normalized = image.convert("RGB").resize((960, 540), Image.Resampling.BILINEAR)
            stream = io.BytesIO()
            normalized.save(stream, format="PNG")
            target = output / "media" / ("camera-" + row["camera_id"] + ".png")
            save(target, stream.getvalue())
        transforms.append(
            dict(
                camera_id=row["camera_id"],
                source_file_sha256=row["file_sha256"],
                result_file_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                source_size_px=row["image_size_px"],
                result_size_px=[960, 540],
                method="PIL_BILINEAR_STRETCH_RGB",
            )
        )
    stream = io.BytesIO()
    Image.new("RGB", (960, 540), (128, 128, 128)).save(stream, format="PNG")
    save(output / "media/neutral.png", stream.getvalue())
    records = []
    for camera in ["A", "B"]:
        for frame in range(count):
            # Materialize visible RGB only. No schedule/actor/route enters the indexer.
            selected = (camera == "A" and frame < (10 if playback else 2)) or (
                camera == "B" and frame >= (15 if playback else 5)
            )
            ref = "media/" + ("camera-" + camera + ".png" if selected else "neutral.png")
            records.append(
                dict(
                    camera_id=camera,
                    frame_index=frame,
                    timestamp_s=frame / 5,
                    rgb_ref=ref,
                    file_sha256=hashlib.sha256((output / ref).read_bytes()).hexdigest(),
                )
            )
    safe = dict(
        schema_version="q-demo.synthetic-rgb-run.v1",
        source_kind="SYNTHETIC",
        scene_id=SCENE,
        run_id=RUN,
        clock_id="SYNTHETIC_CLOCK",
        sampling=dict(
            fps=5, duration_s=duration_s, sample_count_per_camera=count, image_size_px=[960, 540]
        ),
        records=records,
        identity_verdict="UNCONFIRMED",
        gt_read=False,
    )
    save(output / "rgb.json", safe)
    save(
        output / "TRANSFORMS.json",
        dict(source_assets_file_sha256=assets_pin, transforms=transforms, formal=False),
    )
    return safe


def load_rgb(path, pin):
    path = Path(path)
    doc = strict_json(read_pinned(path, pin))
    if doc.get("schema_version") == "q-demo.dynamic-rgb-run.v1":
        from amidst.q1q5.dynamic_rgb import load_dynamic_rgb

        return load_dynamic_rgb(path, pin, doc, binary=binary, require=require)
    require(
        doc["schema_version"] == "q-demo.synthetic-rgb-run.v1"
        and doc["source_kind"] == "SYNTHETIC"
        and doc["gt_read"] is False,
        "SAFE_SYNTHETIC_RGB_REQUIRED",
    )
    sampling = doc["sampling"]
    require(
        sampling
        in [
            dict(fps=5, duration_s=d, sample_count_per_camera=d * 5, image_size_px=[960, 540])
            for d in [2, 6]
        ],
        "RGB_SAMPLING",
    )
    count = sampling["sample_count_per_camera"]
    rows = {(r["camera_id"], r["frame_index"]): r for r in doc["records"]}
    require(
        len(rows) == len(doc["records"]) == 2 * count
        and set(rows) == {(c, i) for c in ["A", "B"] for i in range(count)},
        "RGB_GRID",
    )
    for (_camera, frame), row in rows.items():
        require(row["timestamp_s"] == frame / 5, "RGB_CLOCK")
        metadata_ref(path.parent, row["rgb_ref"])
    manifest = {k: doc[k] for k in ["scene_id", "run_id", "clock_id", "sampling"]}
    manifest["allowlist"] = [dict(role="rgb_index", file_sha256=pin)]
    return SimpleNamespace(
        manifest=manifest,
        files={"rgb_index": {"missing": []}},
        camera_ids={"A", "B"},
        rgb_record=lambda camera, i: rows.get((camera, i)),
        read_rgb=lambda camera, i: binary(
            metadata_ref(path.parent, rows[(camera, i)]["rgb_ref"]),
            rows[(camera, i)]["file_sha256"],
        ),
    )


def sealed(doc, prefix=None):
    doc["content_sha256"] = canonical_hash(
        doc, exclude=("content_sha256", "graph_id", "parameter_set_id")
    )
    if prefix:
        doc["graph_id"] = prefix + ":rSYN:static:" + doc["content_sha256"][:16]
    return doc


def static_context(index, class_labels, *, static_pin=None):
    """Independent static engineering topology, not a renderer/person route."""
    scene_id, run_id = index["scene_id"], index["run_id"]
    clock_id = index["clock_id"]
    interval = index["sampling"]["per_camera"][0]["source_frame_interval_us"]
    h = static_pin or "a" * 64
    region = dict(
        schema_version="q-demo.region-graph.v1",
        scene_id=scene_id,
        scene_revision="rSYN",
        scene_static_sha256=h,
        approval_status="APPROVED",
        approval_ref="SYNTHETIC_ENGINEERING_ONLY",
        regions=[
            dict(
                region_id="R" + str(i),
                kind="ROOM",
                floor_id="F",
                walk_ids=["W" + str(i)],
                polygon_ref="poly:" + str(i),
                polygon_sha256=h,
            )
            for i in [1, 2]
        ],
        edges=[
            dict(
                edge_id="E12",
                regions=["R1", "R2"],
                via=dict(kind="ADJACENT", ref="boundary:12"),
                direction="BIDIRECTIONAL",
                state="OPEN",
                traversability="APPROVED_WALKABLE",
                basis_refs=["basis:SYNTHETIC"],
            )
        ],
        inputs=[dict(ref="static:SYNTHETIC", sha256=h)],
    )
    sealed(region, "rgraph")
    cameras = [
        dict(
            camera_id=c,
            calibration_sha256=h,
            covered_regions=[
                dict(
                    region_id="R" + str(i),
                    basis="STATIC_VISIBILITY_INDEX",
                    visibility_ref="vis:" + c,
                    visible_area_m2=None,
                )
            ],
            exit_zones=[
                dict(
                    exit_zone_id=c + ":exit",
                    roi_polygon_px=[[0, 0], [960, 0], [960, 540], [0, 540]],
                    leads_to_edge_ids=["E12"],
                    mapping_basis="MANUAL_ON_STATIC_FRAME",
                    static_frame_ref="static:" + c,
                    static_frame_sha256=h,
                )
            ],
            entry_zones=[],
        )
        for c, i in [("A", 1), ("B", 2)]
    ]
    camera = dict(
        schema_version="q-demo.camera-transition-graph.v1",
        scene_id=scene_id,
        scene_revision="rSYN",
        region_graph_sha256=region["content_sha256"],
        camera_catalog_sha256=h,
        approval_status="APPROVED",
        approval_ref="SYNTHETIC_ENGINEERING_ONLY",
        cameras=cameras,
        transitions=[
            dict(
                transition_id="T_A_B",
                from_camera_id="A",
                to_camera_id="B",
                via_exit_zone_ids=["A:exit"],
                to_entry_zone_ids=[],
                region_path=["R1", "R2"],
                edge_path=["E12"],
                relation="BLIND_GAP",
                region_hops=1,
                path_traversability="APPROVED_WALKABLE",
                path_has_unknown_state=False,
                ranking_area_m2=None,
                ranking_area_refs=[],
                nominal_path_length_m=None,
                basis_refs=["basis:SYNTHETIC"],
            )
        ],
        inputs=[dict(ref="static:SYNTHETIC", sha256=h)],
    )
    sealed(camera, "cgraph")
    from amidst.q1q5.engineering_scope import bind_engineering_scope

    region, camera, scope, _ = bind_engineering_scope(region, camera)
    clock = dict(
        schema_version="q-demo.clock-mapping.v1",
        run_id=run_id,
        clock_id=clock_id,
        timezone="Asia/Taipei",
        wall_origin="2026-11-01T13:00:00+08:00",
        mapping_kind="DECLARED_DEMO_CLOCK",
        t0_us=0,
        rate=1,
        source_duration_us=max(
            span[1] for row in index["sampling"]["per_camera"] for span in row["sampled_ranges_us"]
        ),
        mapping_version="SYNTHETIC",
        declaration_source="SYNTHETIC",
        declared_by="SYNTHETIC",
        declared_at="2026-10-24T00:00:00+08:00",
    )
    sealed(clock)
    values = dict(
        link_iou_min=0.3,
        link_center_dist_max_diag_ratio=0.5,
        link_max_gap_us=600000,
        link_min_score=0.4,
        link_color_rule="NOT_NONE",
        link_ambiguity_margin=0.05,
        query_min_score=0.5,
        top_k=3,
        search_window_us=1200000,
        research_interval_us=400000,
        session_max_research_rounds=8,
        session_max_agent_rounds=12,
        switch_min_presence="MATCH_STRONG",
        evidence_max_observations=3,
        fallback_budget_ms=1000,
        agent_max_rounds=3,
        agent_max_illegal_submissions=2,
        agent_call_timeout_ms=2000,
        agent_total_budget_ms=5000,
        exit_rule=dict(method="BBOX_BOTTOM_MIDPOINT", boundary_inclusive=True),
        q3_max_llm_attempts=2,
        q3_llm_timeout_ms=2000,
        segment_merge_gap_us=0,
    )
    ps = dict(
        schema_version="q-demo.parameter-set.v1",
        applies_to=dict(
            scene_revision="rSYN",
            run_ids=[run_id],
            detection_index_ids=[index["index_id"]],
            index_interval_us=interval,
        ),
        parameters=[
            dict(
                name=k,
                value=v,
                status="APPROVED",
                unit="SYNTHETIC",
                proposed_by="SYNTHETIC",
                proposal_ref="synthetic://engineering",
            )
            for k, v in values.items()
        ],
        approval=dict(
            status="APPROVED", approved_by="SYNTHETIC", approval_ref="synthetic://engineering"
        ),
    )
    sealed(ps)
    ps["parameter_set_id"] = "pset:q-demo:" + ps["content_sha256"][:16]
    aliases = dict(
        schema_version="q-demo.supported-classes.v1",
        version="SYNTHETIC",
        class_labels=list(class_labels),
        class_map_sha256=index["detector"]["class_map"]["content_sha256"],
        aliases={"人": "person", "車": "car"},
        color_vocabulary=dict(version="SYNTHETIC", labels=["red", "blue"]),
    )
    sealed(aliases["color_vocabulary"])
    sealed(aliases)
    catalog = dict(
        schema_version="q-demo.parse-catalog.v1",
        scene_id=scene_id,
        scene_revision="rSYN",
        run_id=run_id,
        class_labels=list(class_labels),
        color_labels=["red", "blue"],
        camera_ids=["A", "B"],
        region_ids=["R1", "R2"],
        class_aliases={"人": "person", "車": "car"},
        color_aliases={"紅": "red", "藍": "blue"},
        camera_aliases={"A": "A", "B": "B"},
        region_aliases={"R1": "R1", "R2": "R2"},
        class_map_sha256=aliases["class_map_sha256"],
    )
    sealed(catalog)
    return dict(
        region=region, camera=camera, tracking_scope=scope, clock=clock, parameter=ps, aliases=aliases, catalog=catalog
    )


def build_inputs(rgb_path, rgb_pin, model_config, output, *, predictor_factory=None):
    output = Path(output)
    require(
        output.is_absolute()
        and output.resolve() == output
        and not output.exists()
        and output.parent.is_dir(),
        "NEW_INDEX_OUTPUT_REQUIRED",
    )
    require(shutil.disk_usage(output.parent).free >= 8 * 1024**3, "DISK_SPACE_BELOW_8_GIB")
    output.mkdir(mode=0o700)
    metrics = StageMetrics()
    with ProcessSampler() as sampler:
        run = load_rgb(rgb_path, rgb_pin)
        factory = predictor_factory or OfficialRTDetrR18
        model = metrics(
            "model_load",
            lambda: factory(
                Path(model_config["source_root"]),
                Path(model_config["weights"]),
                source_hashes=model_config["source_hashes"],
                seed=7,
                threads=2,
                observer=metrics,
            ),
        )
        config = HSVConfig(
            "SYNTHETIC-HSV",
            0.5,
            2,
            0.2,
            0.2,
            0.2,
            0.7,
            0.2,
            12,
            {"red": [[0.95, 0.05]], "blue": [[0.6, 0.75]]},
        )
        artifact = metrics(
            "index_build_total",
            lambda: build_detection_index(
                run,
                model,
                scene_revision="rSYN",
                stride_samples=1,
                index_grid_origin_frame=0,
                index_score_floor=0.3,
                color_config=config,
                observer=metrics,
            ),
        )
        metrics("index_write", lambda: write_index(artifact, output / "index"))
    docs = static_context(
        artifact.manifest, model.class_labels, static_pin=run.manifest.get("static_file_sha256")
    )
    documents = {}
    for name, doc in docs.items():
        path = output / (name + ".json")
        pin = save(path, doc)
        documents[name] = dict(
            path=path.name,
            file_sha256=pin,
            schema_version=doc["schema_version"],
            content_sha256=doc.get("content_sha256"),
        )
    documents["index"] = dict(
        path="index/detection_index.json",
        file_sha256=hashlib.sha256(
            (output / "index/detection_index.json").read_bytes()
        ).hexdigest(),
        schema_version="q-demo.detection-index.v1",
        content_sha256=artifact.manifest["content_sha256"],
    )
    documents["records"] = dict(
        path="index/detection_index.records.jsonl",
        file_sha256=artifact.manifest["records_file_sha256"],
        schema_version="q-demo.detection-record.v1",
    )
    ps = docs["parameter"]
    settings = ParseSettings(
        0.5, 1, "STRONG", 20, "RULE_ONLY", ps["parameter_set_id"], ps["content_sha256"], 2, 2000
    )
    media = {c: [[0, docs["clock"]["source_duration_us"]]] for c in ["A", "B"]}
    registry = dict(
        schema_version="q-demo.api-registry.v1",
        data_root=str(output),
        documents=documents,
        runs=[
            dict(
                index_ref="index",
                clock_ref="clock",
                region_ref="region",
                camera_ref="camera",
                tracking_scope_ref="tracking_scope",
                parameter_ref="parameter",
                aliases_ref="aliases",
                catalog_ref="catalog",
                parse_settings=asdict(settings),
                media_ranges_by_camera=media,
                media_scope_sha256=canonical_hash(media),
                source_kind="SYNTHETIC",
            )
        ],
        recording_root=None,
        recordings=[],
        limits=dict(max_responses=128, max_media_refs=4096, max_recording_bytes=16_777_216),
    )
    sealed(registry)
    save(output / "registry.json", registry)
    candidates = [
        dict(
            observation_id=o["observation_id"],
            frame_ref=row["frame_ref"],
            camera_id=row["camera_id"],
            timestamp_us=row["timestamp_us"],
            score=o["score"],
            color_verdict=o["color"]["verdicts"]["red"] if o["color"] else None,
        )
        for row in json_records(artifact.records_bytes)
        for o in row["detections"] or []
        if o["class_label"] == "person" and o["score"] >= 0.5
    ]
    save(
        output / "SEED_CANDIDATES.json",
        dict(
            candidates=candidates,
            selection_required=True,
            source_index_sha256=artifact.manifest["content_sha256"],
        ),
    )
    save(
        output / "TELEMETRY.json",
        dict(
            stage_metrics=metrics.report(),
            resources=sampler.report(),
            model_calls=artifact.stats["model_calls"],
            source_kind="SYNTHETIC",
            source_rgb_file_sha256=rgb_pin,
            inference_input="RGB_PIXELS_ONLY",
            accuracy=None,
        ),
    )
    return artifact


def json_records(raw):
    return [strict_json(line) for line in raw.splitlines()]


def query_inputs(prepared, registry_pin, selected_observation_id, runtime, output):
    """An explicit operator-selected real observation; never auto-pick a target."""
    prepared, output = Path(prepared), Path(output)
    require(
        not output.exists() and output.parent.is_dir() and output.resolve() == output,
        "NEW_QUERY_OUTPUT_REQUIRED",
    )
    registry = strict_json(read_pinned(prepared / "registry.json", registry_pin))

    def read(name):
        p = registry["documents"][name]
        return read_pinned(metadata_ref(prepared, p["path"]), p["file_sha256"], maximum=16_777_216)

    index = strict_json(read("index"))
    scene_id, run_id = index["scene_id"], index["run_id"]
    raw = read("records")
    rows = json_records(raw)
    require(hashlib.sha256(raw).hexdigest() == index["records_file_sha256"], "INDEX_RECORDS_PIN")
    matches = [
        (row, o)
        for row in rows
        for o in row["detections"] or []
        if o["observation_id"] == selected_observation_id
        and o["class_label"] == "person"
        and o["score"] >= 0.5
    ]
    require(len(matches) == 1, "EXPLICIT_DETECTED_SEED_REQUIRED")
    row, _ = matches[0]
    clock = strict_json(read("clock"))
    ps = strict_json(read("parameter"))
    runtime = dict(runtime)
    runtime["applies_to"] = dict(
        scene_id=scene_id,
        scene_revision="rSYN",
        run_id=run_id,
        detection_index_sha256=index["content_sha256"],
        parameter_set_sha256=ps["content_sha256"],
        clock_mapping_sha256=clock["content_sha256"],
    )
    runtime["content_sha256"] = canonical_hash(runtime, exclude=("content_sha256",))
    validate_config(runtime)
    output.mkdir(mode=0o700)
    save(output / "runtime.json", runtime)
    seed = dict(
        observation_id=selected_observation_id,
        frame_ref=row["frame_ref"],
        run_id=run_id,
        camera_id=row["camera_id"],
        timestamp_us=row["timestamp_us"],
        source_response_sha256=None,
    )
    cases = []
    end_second = clock["source_duration_us"] // 1_000_000
    # This new engineering scene uses class-only pursuit. Color evidence remains
    # unchanged in the index; no HSV threshold or formal question is altered.
    target = "人" if scene_id == "ENGINEERING_DYNAMIC_SCENE" else "紅衣人"
    for task, text in [
        ("ONCE_SEARCH", f"哪幾台拍到人13:00:00到13:00:{end_second:02d}"),
        ("CONTINUOUS_PURSUIT", f"{target}13:00:00到13:00:{end_second:02d}"),
    ]:
        cases.append(
            dict(
                case_id="linked:" + task,
                task=task,
                data_kind="SYNTHETIC",
                binding_id=index["content_sha256"],
                run_id=run_id,
                camera_ids=["A", "B"],
                source_range_us=[0, clock["source_duration_us"]],
                query=dict(
                    kind="TEXT",
                    question_id="ENGINEERING_CONTROL_NOT_FORMAL_Q3",
                    text=text,
                    request_ref=None,
                    request_file_sha256=None,
                    context_sha256=clock["content_sha256"],
                ),
                selected_seed=seed if task == "CONTINUOUS_PURSUIT" else None,
            )
        )
    save(
        output / "cases.jsonl",
        b"".join(
            (json.dumps(c, sort_keys=True, separators=(",", ":")) + "\n").encode() for c in cases
        ),
    )
    save(
        output / "SELECTION.json",
        dict(
            selected_observation_id=selected_observation_id,
            selection_source="EXPLICIT_OPERATOR_ARGUMENT",
            identity_verdict="UNCONFIRMED",
            formal=False,
        ),
    )
    return cases
