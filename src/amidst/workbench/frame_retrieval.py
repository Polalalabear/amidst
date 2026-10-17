"""C5 range-indexed frame retrieval and verified perception lookups, no GT."""

from __future__ import annotations

import copy
import hashlib
import time
from bisect import bisect_left, bisect_right
from pathlib import Path

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from amidst.blind_hypothesis import negative_evidence_from_retrieval, verify_output_sha256
from amidst.engineering.registry import content_hash
from amidst.workbench.scene_errors import DataIntegrityError


def seal_retrieval(value):
    body = copy.deepcopy(value)
    body.pop("output_sha256", None)
    body["stats"].pop("latency_ms", None)
    value["output_sha256"] = content_hash(body)
    return value


def unavailable_retrieval(request, provenance):
    started = time.monotonic()
    query = copy.deepcopy(request)
    query.pop("session_ref", None)
    result = {
        "schema_version": "workbench.frame-retrieval.v1",
        "status": "UNKNOWN",
        "reason": "VISIBILITY_INDEX_UNAVAILABLE",
        "query_id": "frq:" + content_hash(query)[:24],
        "query": query,
        "results": [],
        "scan_mode": "INDEX",
        "truncated": False,
        "frame_evaluations": {},
        "visibility_entries": {},
        "frame_outcomes": [],
        "negative_evidence_candidates": [],
        "identity_verdict": "UNCONFIRMED",
        "agent_used": False,
        "provenance": provenance | {"producer": "frame-retrieval", "gt_read": False},
        "stats": {
            "frame_records_read": 0,
            "index_records_read": 0,
            "frames_in_scope_total": None,
            "frames_matched_total": None,
            "frames_suggested": 0,
            "frames_unavailable": None,
        },
    }
    result["stats"]["latency_ms"] = {"total": (time.monotonic() - started) * 1000}
    return seal_retrieval(result)


class TimeFrameIndex:
    def __init__(self, records):
        self.records = {}
        self.times = {}
        for row in records:
            self.records.setdefault(row["camera_id"], []).append(row)
        for camera, rows in self.records.items():
            rows.sort(key=lambda r: (r["timestamp_s"], r["frame_ref"]))
            self.times[camera] = [r["timestamp_s"] for r in rows]

    def window(self, camera, start, end):
        ts = self.times.get(camera, [])
        lo, hi = bisect_left(ts, start), bisect_right(ts, end)
        return self.records.get(camera, []), lo, hi


class FrameRetrievalIndex:
    def __init__(
        self, records, evaluations, entries, *, index_sha256, provenance, interval_s, paths=None
    ):
        self.time_index = TimeFrameIndex(records)
        self.evaluations = evaluations
        self.index_sha256 = index_sha256
        self.entries = {e["camera_id"]: copy.deepcopy(e) for e in entries}
        self.provenance = provenance
        self.interval_s = interval_s
        self.paths = paths or {}
        self.footprints = {
            c: unary_union([Polygon(r) for r in e["polygons"]]) for c, e in self.entries.items()
        }
        self.visibility_entries = {
            e["visibility_ref"]: {k: e[k] for k in ("method", "floor_z_m", "polygons")}
            | {"index_sha256": index_sha256}
            for e in entries
        }

    @classmethod
    def from_scene(cls, scene, bundle, index_sha256, interval_s):
        if bundle["output_sha256"] != content_hash(
            {k: v for k, v in bundle.items() if k != "output_sha256"}
        ):
            raise DataIntegrityError("VISIBILITY_OUTPUT_HASH_MISMATCH")
        if (
            bundle.get("gt_read") is not False
            or bundle.get("renderer_visibility_read") is not False
            or bundle.get("annotations_as_occluders") is not False
        ):
            raise DataIntegrityError("VISIBILITY_AUTHORITY_MISMATCH")
        binding = scene._inputs["source_binding"]
        for key in ("run_id", "clock_id", "source_sha256"):
            if bundle[key] != binding[key]:
                raise DataIntegrityError("VISIBILITY_SOURCE_BINDING_MISMATCH")
        if bundle["safe_inputs_sha256"] != hashlib.sha256(scene._inputs_raw).hexdigest():
            raise DataIntegrityError("VISIBILITY_SAFE_INPUTS_MISMATCH")
        frames = scene._perception_frames
        by_source = {r["frame_ref"]: r for r in scene._inputs["frames"]}
        records = []
        evaluations = {}
        paths = {}
        params = next(iter(scene._ground_estimates.values()))["provenance"]["run_parameters"]
        for entry in bundle["entries"]:
            if entry["sha256"] != content_hash({k: v for k, v in entry.items() if k != "sha256"}):
                raise DataIntegrityError("VISIBILITY_ENTRY_HASH_MISMATCH")
            p = entry["provenance"]
            if (
                p["run_parameters"] != params
                or p["calibration_sha256"]
                != content_hash([c["calibration"] for c in scene._inputs["cameras"]])
                or p["floor_sha256"] != content_hash(scene._inputs["floor_plane"])
            ):
                raise DataIntegrityError("VISIBILITY_CALIBRATION_OR_RUN_PARAMETERS_MISMATCH")
        for ref, source in by_source.items():
            measured = frames.get(ref)
            valid = measured is not None and not any(
                r != "NO_DETECTION" for r in measured["reasons"]
            )
            path = Path(source["local_path"])
            paths[ref] = (path, source["sha256"])
            evaluation = {
                "frame_available": path.is_file(),
                "rgb_hash_verified": False,
                "provenance_ok": True,
                "perception_evaluated": valid,
                "measurement_count": len(measured["components"]) if valid else None,
                "detection_producer": {
                    "producer": "rgb-mask-contact",
                    "version": "rgb-mask-contact-v2",
                },
            }
            if path.is_file():
                if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                    raise DataIntegrityError("RGB_HASH_MISMATCH")
                evaluation["rgb_hash_verified"] = True
            evaluations[ref] = evaluation
            records.append(
                {
                    "frame_ref": ref,
                    "camera_id": source["camera_id"],
                    "timestamp_s": source["timestamp"],
                }
            )
        provenance = copy.deepcopy(next(iter(scene._ground_estimates.values()))["provenance"])
        provenance.update(
            producer="frame-retrieval", visibility_index_sha256=index_sha256, run_parameters=params
        )
        return cls(
            records,
            evaluations,
            bundle["entries"],
            index_sha256=index_sha256,
            provenance=provenance,
            interval_s=interval_s,
            paths=paths,
        )

    def _evaluation(self, ref):
        result = copy.deepcopy(self.evaluations.get(ref, {}))
        if ref in self.paths:
            path, expected = self.paths[ref]
            if path.is_symlink():
                raise DataIntegrityError("RGB_SYMLINK_REJECTED")
            result["frame_available"] = path.is_file()
            if path.is_file():
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise DataIntegrityError("RGB_HASH_MISMATCH")
                result["rgb_hash_verified"] = True
            else:
                result["rgb_hash_verified"] = False
        return result

    def verify_evidence_frames(self, entries):
        refs = {frame["frame_ref"] for entry in entries for frame in entry["frame_refs"]}
        if len(refs) > 512:
            return False
        valid = True
        for ref in sorted(refs):
            evaluation = self._evaluation(ref)
            if (
                any(
                    evaluation.get(k) is not True
                    for k in (
                        "frame_available",
                        "rgb_hash_verified",
                        "provenance_ok",
                        "perception_evaluated",
                    )
                )
                or type(evaluation.get("measurement_count")) is not int
                or evaluation["measurement_count"] != 0
            ):
                valid = False
        return valid

    def query(self, request, hypothesis=None):
        started = time.monotonic()
        kind = request["query_kind"]
        selection = request.get("hypothesis")
        query = copy.deepcopy(request)
        query.pop("session_ref", None)
        interval = self.interval_s
        problem = None
        if kind == "HYPOTHESIS":
            if hypothesis is None:
                problem = "HYPOTHESIS_NOT_FOUND"
            elif not verify_output_sha256(hypothesis):
                problem = "PROVENANCE_MISMATCH"
            elif hypothesis["status"] != "READY":
                problem = "HYPOTHESIS_NOT_READY"
            else:
                active = {
                    h["hypothesis_ref"] for h in hypothesis["hypotheses"] if h["status"] == "ACTIVE"
                }
                if any(ref not in active for ref in selection["hypothesis_refs"]):
                    problem = "HYPOTHESIS_NOT_FOUND"
                interval = [hypothesis["interval"]["start_s"], hypothesis["interval"]["end_s"]]
                query["hypothesis_interval"] = copy.deepcopy(hypothesis["interval"])
                query["endpoint_substitutions"] = copy.deepcopy(
                    hypothesis["endpoint_substitutions"]
                )
        bounds = request.get("time_range_s") or interval
        if len(bounds) != 2 or not 0 <= bounds[0] <= bounds[1] or bounds[1] - bounds[0] > 20:
            problem = "TIME_RANGE_INVALID"
        if kind == "HYPOTHESIS" and not interval[0] <= bounds[0] <= bounds[1] <= interval[1]:
            problem = "TIME_RANGE_INVALID"
        available_times = [ts for ts in self.time_index.times.values() if ts]
        if available_times and not min(ts[0] for ts in available_times) <= bounds[0] <= bounds[
            1
        ] <= max(ts[-1] for ts in available_times):
            problem = "TIME_RANGE_INVALID"
        if kind == "TIME_RANGE" and selection is not None:
            problem = "TIME_RANGE_INVALID"
        query["time_range_s"] = list(bounds)
        cameras = request.get("camera_ids") or sorted(self.time_index.records)
        if (
            len(cameras) != len(set(cameras))
            or len(cameras) > 4
            or any(c not in self.time_index.records or c not in self.entries for c in cameras)
        ):
            problem = "TOO_MANY_CAMERAS" if len(cameras) > 4 else "CAMERA_NOT_IN_SCENE"
        if any(c not in self.entries for c in cameras):
            problem = "VISIBILITY_INDEX_UNAVAILABLE"
        query_id = "frq:" + content_hash({"query": query, "index": self.index_sha256})[:24]
        result = {
            "schema_version": "workbench.frame-retrieval.v1",
            "status": "UNKNOWN" if problem else "READY",
            "reason": problem,
            "query_id": query_id,
            "query": query,
            "results": [],
            "stats": {
                "frame_records_read": 0,
                "index_records_read": 0,
                "frames_in_scope_total": 0,
                "frames_matched_total": 0,
                "frames_suggested": 0,
                "frames_unavailable": 0,
            },
            "truncated": False,
            "scan_mode": "INDEX",
            "negative_evidence_candidates": [],
            "frame_outcomes": [],
            "frame_evaluations": {},
            "visibility_entries": {},
            "identity_verdict": "UNCONFIRMED",
            "agent_used": False,
            "provenance": copy.deepcopy(self.provenance),
        }
        matched = []
        lookup_done = time.monotonic()
        if not problem:
            windows = []
            for camera in sorted(cameras):
                rows, lo, hi = self.time_index.window(camera, *bounds)
                windows.append((camera, rows, lo, hi))
                result["stats"]["frames_in_scope_total"] += hi - lo
                result["stats"]["index_records_read"] += 1
            lookup_done = time.monotonic()
            if result["stats"]["frames_in_scope_total"] > 512:
                result.update(status="UNKNOWN", reason="SEARCH_BUDGET_EXHAUSTED")
            else:
                for camera, rows, lo, hi in windows:
                    end = hi
                    for row in rows[lo:end]:
                        if time.monotonic() - started > 5.0:
                            result.update(status="UNKNOWN", reason="SEARCH_BUDGET_EXHAUSTED")
                            matched = []
                            break
                        result["stats"]["frame_records_read"] += 1
                        evaluation = self._evaluation(row["frame_ref"])
                        if not evaluation.get("frame_available") or not evaluation.get(
                            "rgb_hash_verified"
                        ):
                            result["stats"]["frames_unavailable"] += 1
                            continue
                        score = 0.0
                        reason = {
                            "kind": "TIME_RANGE_ONLY",
                            "walkable_status": None,
                            "hypothesis_refs": [],
                            "overlap_area_m2": None,
                            "in_view_count": None,
                            "footprint_method": self.entries[camera]["method"],
                        }
                        if kind == "HYPOTHESIS":
                            reason.update(walkable_status="TRUE")
                            use = selection["use"]
                            t = row["timestamp_s"]
                            footprint = self.footprints[camera]
                            if use == "PATHS":
                                paths = [
                                    h
                                    for h in hypothesis["hypotheses"]
                                    if not selection["hypothesis_refs"]
                                    or h["hypothesis_ref"] in selection["hypothesis_refs"]
                                ]
                                refs = []
                                for h in paths:
                                    sample = next(
                                        (
                                            s
                                            for s in h["samples"]
                                            if abs(s["timestamp_s"] - t) < 0.1 - 1e-9
                                        ),
                                        None,
                                    )
                                    if sample and Point(sample["position_m"][:2]).buffer(
                                        hypothesis["configuration"]["body_radius_m"]
                                    ).intersects(footprint):
                                        refs.append(h["hypothesis_ref"])
                                        if h["checks"]["walkable"].get("unconfirmed_area_crossed"):
                                            reason["walkable_status"] = "UNKNOWN"
                                score = len(refs)
                                reason.update(
                                    kind="HYPOTHESIS_PATH_IN_VIEW",
                                    hypothesis_refs=refs,
                                    in_view_count=len(refs),
                                )
                            else:
                                region = next(
                                    (
                                        r
                                        for r in hypothesis["reachable_regions"]
                                        if abs(r["timestamp_s"] - t) < 0.1 - 1e-9
                                    ),
                                    None,
                                )
                                if region and region.get("truncated"):
                                    result.update(
                                        status="UNKNOWN", reason="HYPOTHESIS_REGION_TRUNCATED"
                                    )
                                    matched = []
                                    break
                                if region:
                                    half = region["cell_size_m"] / 2
                                    geom = unary_union(
                                        [
                                            box(x - half, y - half, x + half, y + half)
                                            for x, y in region["samples"]
                                        ]
                                    )
                                    score = geom.intersection(footprint).area
                                    if region["walkable_unknown_sample_indices"]:
                                        reason["walkable_status"] = "UNKNOWN"
                                reason.update(
                                    kind="REACHABLE_REGION_IN_VIEW", overlap_area_m2=score
                                )
                            if score <= 0:
                                continue
                        matched.append((camera, row, reason, score, evaluation))
                result["stats"]["frames_matched_total"] = len(matched)
                result["stats"]["frames_in_scope_total"] -= result["stats"]["frames_unavailable"]
                # Form windows first, then rank windows (contract §4), not individual frames.
                groups = []
                for camera, row, reason, score, evaluation in sorted(
                    matched,
                    key=lambda item: (item[0], item[1]["timestamp_s"], item[1]["frame_ref"]),
                ):
                    if (
                        not groups
                        or groups[-1]["camera"] != camera
                        or row["timestamp_s"] - groups[-1]["items"][-1][1]["timestamp_s"]
                        > 0.2 + 1e-6
                    ):
                        groups.append({"camera": camera, "items": [], "score": 0})
                    groups[-1]["items"].append((camera, row, reason, score, evaluation))
                    groups[-1]["score"] = max(groups[-1]["score"], score)
                groups.sort(
                    key=lambda g: (-g["score"], g["camera"], g["items"][0][1]["timestamp_s"])
                )
                kept = 0
                blocks = {}
                if result["status"] == "READY":
                    for group in groups:
                        items = group["items"][: max(0, request["max_frames"] - kept)]
                        if not items:
                            continue
                        camera = group["camera"]
                        entry = self.entries[camera]
                        block = blocks.setdefault(
                            camera,
                            {
                                "camera_id": camera,
                                "visibility_ref": entry["visibility_ref"],
                                "method": entry["method"],
                                "windows": [],
                            },
                        )
                        frames = [
                            {
                                "frame_ref": row["frame_ref"],
                                "timestamp_s": row["timestamp_s"],
                                "reason": reason,
                            }
                            for _, row, reason, _, _ in items
                        ]
                        block["windows"].append(
                            {
                                "start_s": frames[0]["timestamp_s"],
                                "end_s": frames[-1]["timestamp_s"],
                                "frames": frames,
                            }
                        )
                        for _, row, _, _, evaluation in items:
                            result["frame_evaluations"][row["frame_ref"]] = evaluation
                        result["visibility_entries"][entry["visibility_ref"]] = (
                            self.visibility_entries[entry["visibility_ref"]]
                        )
                        kept += len(items)
                    result["results"] = list(blocks.values())
                    result["stats"]["frames_suggested"] = kept
                    result["truncated"] = result["stats"]["frames_matched_total"] > kept
                    converted = negative_evidence_from_retrieval(
                        result,
                        frame_evaluations=result["frame_evaluations"],
                        visibility_entries=result["visibility_entries"],
                        interval_s=interval,
                    )
                    result.update(converted)
        finished = time.monotonic()
        result["stats"]["latency_ms"] = {
            "index_lookup": (lookup_done - started) * 1000,
            "frame_lookup": (finished - lookup_done) * 1000,
            "total": (finished - started) * 1000,
        }
        return seal_retrieval(result)

    def baseline_entries(self):
        response = self.query(
            {
                "query_kind": "TIME_RANGE",
                "hypothesis": None,
                "time_range_s": self.interval_s,
                "camera_ids": None,
                "max_frames": 64,
            }
        )
        entries = []
        for raw in response["negative_evidence_candidates"]:
            entry = copy.deepcopy(raw)
            entry["origin"] = "BLIND_INTERVAL_BASELINE"
            entry["retrieval_query_id"] = None
            entry.pop("sha256")
            entry["negative_evidence_ref"] = (
                "negev:" + content_hash({"origin": entry["origin"], "entry": entry})[:24]
            )
            entry["sha256"] = content_hash(entry)
            entries.append(entry)
        return entries
