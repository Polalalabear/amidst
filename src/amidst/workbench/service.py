"""Same-origin desktop UI, server-owned role sessions and bounded scene tools.

Role selection is intentionally a trusted local demo, not authenticated identity.
Human-only evaluation and review never extend the existing Agent tool allowlist.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import mimetypes
import re
import secrets
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, ValidationError

from amidst.engineering.registry import content_hash
from amidst.product.run import load_product
from amidst.workbench.blender_association_media import AssociationScene
from amidst.workbench.blender_motion_media import MotionScene
from amidst.workbench.navigation_guidance import GuidanceIndex, mock_decide
from amidst.workbench.operator_study import OperatorStudyStore
from amidst.workbench.physical_review_store import PhysicalReviewStore
from amidst.workbench.presentation_gallery import Gallery, GalleryError
from amidst.workbench.product_bridge import (
    BinaryResponse,
    BridgeDenied,
    BridgeRequest,
    ContextRequest,
    ProductBridge,
)
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.run_jobs import SingleSyntheticRunManager
from amidst.workbench.scenes import SceneAdapter, load_catalog
from amidst.workbench.storage_probe import run_probe as run_storage_probe
from amidst.workbench.system_ports import run_port_probe

VERSION = "amidst-workbench.v1"
Role = Literal["research", "management"]
PUBLIC_EVENT_KEYS = (
    "event_ref", "kind", "time_range", "camera_ids", "media_refs", "uncertainty",
    "evidence_state", "missing_evidence", "support_state",
)
PRODUCT_ACTIONS = frozenset({
    "context", "tool", "intent", "execute", "plan", "case", "cases", "report", "review",
    "videos", "timeline", "export_report",
})


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    session_ref: str = Field(min_length=20, max_length=128)


class SceneRequest(Request):
    scene_id: str = Field(min_length=1, max_length=100)


class QueryRequest(SceneRequest):
    camera_id: str = Field(min_length=1, max_length=150)
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class EventRequest(SceneRequest):
    event_ref: str = Field(min_length=1, max_length=160)


class VersionRequest(SceneRequest):
    version: int = Field(ge=0, strict=True)


class RunStartRequest(SceneRequest):
    annotation_version: int = Field(ge=0, strict=True)
    parameters: dict[str, StrictFloat] = Field(default_factory=dict, max_length=6)
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class RunReferenceRequest(SceneRequest):
    job_ref: str = Field(min_length=10, max_length=160)


class StudyStartRequest(SceneRequest):
    task_ref: str = Field(min_length=10, max_length=160)
    mode: Literal["manual", "assisted"]


class StudyReferenceRequest(SceneRequest):
    study_ref: str = Field(min_length=10, max_length=160)


class StudyRecordRequest(StudyReferenceRequest):
    action: Literal["camera_view", "frame_open", "correction", "evidence_open"]
    camera_id: str | None = Field(default=None, min_length=1, max_length=150)
    frame_ref: str | None = Field(default=None, min_length=1, max_length=160)
    evidence_ref: str | None = Field(default=None, min_length=1, max_length=160)


class StudyViewRequest(StudyReferenceRequest):
    camera_id: str | None = Field(default=None, min_length=1, max_length=150)
    timestamp: float | None = Field(default=None, ge=0)
    frame_ref: str | None = Field(default=None, min_length=1, max_length=160)


class StudySubmitRequest(StudyReferenceRequest):
    answer: dict[str, Any] = Field(min_length=1, max_length=1)


class StudyResumeRequest(StudyReferenceRequest):
    recovery_token: str = Field(min_length=20, max_length=128)


class GuidanceRequest(QueryRequest):
    label: str = Field(min_length=1, max_length=100)
    behavior: Literal["walking", "running", "enter_exit"] = "walking"
    top_k: int = Field(ge=1, le=5, strict=True, default=3)


class DecisionRequest(SceneRequest):
    guide_ref: str = Field(pattern=r"^guide-[0-9a-f]{64}$")


class StorageProbeRequest(SceneRequest):
    stage: Literal["readers", "appends", "publish_conflict", "reopen_replay", "all"] = "all"


class TimelineRequest(SceneRequest):
    camera_ids: list[str] = Field(min_length=1, max_length=4)
    timestamp: float = Field(ge=0)


class FrameQueryRequest(SceneRequest):
    camera_ids: list[str] = Field(min_length=1, max_length=4)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    target_timestamp: float = Field(ge=0)
    top_k: int = Field(ge=1, le=5, strict=True, default=3)
    behavior_intent: Literal["walking", "running", "enter_exit"] = "walking"


class MotionRequest(SceneRequest):
    camera_ids: list[str] = Field(min_length=1, max_length=4)
    start: float = Field(ge=0, strict=True)
    end: float = Field(ge=0, strict=True)


class AssociationRequest(MotionRequest):
    top_k: int = Field(ge=1, le=5, strict=True, default=3)


class TargetReconstructionRequest(AssociationRequest):
    negative_evidence_mode: Literal["NONE", "BASELINE", "BASELINE_AND_FEEDBACK"] = (
        "BASELINE_AND_FEEDBACK")
    negative_evidence_refs: list[str] = Field(default_factory=list, max_length=400)
    previous_response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    observation_ref: str = Field(pattern=r"^observation:[0-9a-f]{24}$", strict=True)


class RetrievalHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hypothesis_refs: list[str] = Field(default_factory=list, max_length=5)
    use: Literal["PATHS", "REACHABLE_REGIONS"]


class FrameRetrievalRequest(SceneRequest):
    schema_version: Literal["office-demo.frame-retrieval-request.v1"] = (
        "office-demo.frame-retrieval-request.v1")
    query_kind: Literal["HYPOTHESIS", "TIME_RANGE"]
    hypothesis: RetrievalHypothesis | None = None
    time_range_s: list[float] | None = Field(default=None, min_length=2, max_length=2)
    camera_ids: list[str] | None = Field(default=None, min_length=1, max_length=4)
    max_frames: int = Field(ge=1, le=64, strict=True)


class FrameWallRequest(MotionRequest):
    slot_count: int = Field(ge=8, le=16, strict=True, default=8)


class PhysicalReviewDecisionRequest(SceneRequest):
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    item_ref: str = Field(min_length=10, max_length=160, strict=True)
    checks: list[dict[str, Any]] = Field(min_length=1, max_length=24)
    expected_revision: int = Field(ge=0, strict=True)
    reviewer: str = Field(min_length=1, max_length=100, strict=True)
    reason: str = Field(min_length=1, max_length=2000, strict=True)


class PhysicalReviewDeltaRequest(SceneRequest):
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    revision: int = Field(ge=1, strict=True)


class PresentationRequest(Request):
    presentation_ref: str = Field(min_length=1, max_length=160)


class GalleryRequest(Request):
    family_ref: str = Field(pattern=r"^gallery-family:[0-9a-f]{24}$", strict=True)


class DraftRequest(SceneRequest):
    object_id: str = Field(min_length=1, max_length=200)
    changes: dict[str, Any]
    base_version: int = Field(ge=0, strict=True)
    reviewer: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)


class ValidateRequest(Request):
    draft_id: str = Field(min_length=1, max_length=160)


class PublishRequest(ValidateRequest):
    expected_version: int = Field(ge=0, strict=True)
    reviewer: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)


class ResultRequest(EventRequest):
    decision: Literal["SUPPORT", "REJECT", "UNKNOWN", "MORE_EVIDENCE"]
    reason: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=100)


class NoteRequest(EventRequest):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"]
    note: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=100)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


@dataclass
class Session:
    role: Role
    scene_ids: frozenset[str]
    media: dict[str, set[str]] = field(default_factory=dict)
    draft_scenes: dict[str, str] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    guides: dict[str, tuple[str, str, dict[str, Any]]] = field(default_factory=dict)
    motion_media: dict[str, set[str]] = field(default_factory=dict)
    association_media: dict[str, set[str]] = field(default_factory=dict)
    physical_media: dict[str, set[str]] = field(default_factory=dict)
    retrieval_evidence_refs: dict[str, set[str]] = field(default_factory=dict)
    blind_responses: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    physical_review_issued: dict[str, tuple[str, frozenset[str]]] = field(default_factory=dict)


class MotionArtifacts(Protocol):
    def manifest(self, scene: MotionScene) -> dict[str, Any]: ...
    def media(self, scene: MotionScene, ref: str) -> tuple[str, bytes]: ...


class AssociationArtifacts(Protocol):
    def manifest(self, scene: AssociationScene) -> dict[str, Any]: ...
    def media(self, scene: AssociationScene, ref: str) -> tuple[str, bytes]: ...


class PhysicalArtifacts(Protocol):
    def manifest(self, scene: Any) -> dict[str, Any]: ...
    def media(self, scene: Any, ref: str) -> tuple[str, bytes]: ...


class Denied(ValueError):
    """Fixed public errors intentionally contain no source paths or raw payloads."""


class Workbench:
    def __init__(self, catalog: dict[str, SceneAdapter], reviews: ReviewStore, *,
                 presentation: Callable[[], dict[str, Any]] | None = None,
                 presentation_media: Callable[[str], tuple[str, bytes]] | None = None,
                 product_bridge: ProductBridge | None = None,
                 product_bridges: dict[str, ProductBridge] | None = None,
                 gallery: Gallery | None = None,
                 motion_media: MotionArtifacts | None = None,
                 association_media: AssociationArtifacts | None = None,
                 physical_media: PhysicalArtifacts | None = None,
                 run_jobs: SingleSyntheticRunManager | None = None,
                 operator_studies: OperatorStudyStore | None = None,
                 unavailable_scenes: list[dict[str, Any]] | None = None) -> None:
        self.catalog, self.reviews = catalog, reviews
        self.unavailable_scenes = list(unavailable_scenes or [])
        self.presentation_provider = presentation
        self.presentation_media_provider = presentation_media
        self.product_bridge, self.gallery = product_bridge, gallery
        self.product_bridges = dict(product_bridges or {})
        self.sessions: dict[str, Session] = {}
        self.guidance_indexes: dict[str, GuidanceIndex] = {}
        self.motion_media_provider = motion_media
        self.association_media_provider = association_media
        self.physical_media_provider = physical_media
        self.physical_review_store = PhysicalReviewStore(reviews.db_path)
        self.run_jobs, self.operator_studies = run_jobs, operator_studies
        self.phase2_suite: Any = None

    def bootstrap(self) -> dict[str, Any]:
        return {"version": VERSION, "scenes": [
            {"scene_id": s.scene_id, "label": s.label, "description": s.description,
             "product_available": self._product_bridge(s.scene_id) is not None}
            for s in self.catalog.values()
        ] + copy.deepcopy(self.unavailable_scenes),
            "identity": "LOCAL_ROLE_SELECTION", "desktop_only": True}

    def _product_bridge(self, scene_id: str) -> ProductBridge | None:
        if self.product_bridge is not None and self.product_bridge.scene.scene_id == scene_id:
            return self.product_bridge
        bridge = self.product_bridges.get(scene_id)
        if bridge is not None and bridge.scene.scene_id == scene_id:
            return bridge
        return None

    def session(self, payload: object) -> dict[str, Any]:
        request = SessionRequest.model_validate(payload)
        token = secrets.token_urlsafe(32)
        self.sessions[token] = Session(request.role, frozenset(self.catalog))
        return {"session_ref": token, "role": request.role, "version": VERSION}

    def _session(self, token: str) -> Session:
        if token not in self.sessions:
            raise Denied("SESSION_DENIED")
        return self.sessions[token]

    def _scene(self, session: Session, scene_id: str) -> SceneAdapter:
        if scene_id not in session.scene_ids or scene_id not in self.catalog:
            raise Denied("SCENE_DENIED")
        return self.catalog[scene_id]

    @staticmethod
    def _research(session: Session) -> None:
        if session.role != "research":
            raise Denied("ROLE_DENIED")

    @staticmethod
    def _issue_media(session: Session, scene_id: str, event: dict[str, Any]) -> None:
        session.media.setdefault(scene_id, set()).update(event.get("media_refs", []))

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        result = {key: event[key] for key in PUBLIC_EVENT_KEYS if key in event}
        # Exact frame provenance is necessary to label evidence, even in a summary view.
        result["source_frames"] = [
            {key: frame[key] for key in ("frame_ref", "camera_id", "timestamp") if key in frame}
            for frame in event.get("source_frames", [])
            if frame.get("frame_ref") in event.get("media_refs", [])
        ]
        result["uncertainty"] = (
            "此路線為盲區推論，保留多種可能；尚未確認人物身分或行為意圖。"
            if event.get("evidence_state") == "INFERRED_GAP" else
            "此為待確認的事件候選，請結合來源影像檢視；尚未確認人物身分或行為意圖。"
        )
        if event.get("missing_evidence"):
            result["uncertainty"] += " 部分來源證據缺失。"
        if event.get("support_state") == "UNKNOWN":
            result["uncertainty"] += " 可見證據不足，行為候選仍未定。"
        return result

    def _notes(self, scene_id: str, event_ref: str, role: Role) -> list[dict[str, Any]]:
        notes = self.reviews.state(scene_id).get("notes", [])
        found = [{**n, "record_status": n["status"], "status": n["handling_status"]}
                 for n in notes if n.get("event_ref") == event_ref]
        if role == "research":
            return found
        return [{k: n[k] for k in ("status", "note", "reviewer", "created_at") if k in n}
                for n in found]

    def call(self, action: str, payload: object) -> dict[str, Any]:
        schemas: dict[str, type[Request]] = {
            "scene": SceneRequest, "query": QueryRequest, "event": EventRequest,
            "timeline": TimelineRequest, "review_state": SceneRequest, "draft": DraftRequest,
            "validate": ValidateRequest, "publish": PublishRequest,
            "result_review": ResultRequest, "note": NoteRequest, "test": QueryRequest,
            "evaluation": SceneRequest, "logs": SceneRequest,
            "export": VersionRequest,
            "presentations": Request, "presentation": PresentationRequest,
            "gallery_list": Request, "gallery_detail": GalleryRequest,
            "semantic_presets": SceneRequest, "navigation_guide": GuidanceRequest,
            "agent_decision": DecisionRequest, "system_ports": SceneRequest,
            "storage_probe": StorageProbeRequest, "export_delta": VersionRequest,
            "frame_query": FrameQueryRequest, "motion_reconstruction": MotionRequest,
            "cross_camera_reconstruction": AssociationRequest,
            "target_reconstruction": TargetReconstructionRequest,
            "frame_retrieval": FrameRetrievalRequest,
            "physical_cross_camera_reconstruction": AssociationRequest,
            "physical_review": MotionRequest,
            "physical_review_decision": PhysicalReviewDecisionRequest,
            "physical_review_delta": PhysicalReviewDeltaRequest,
            "camera_frame_wall": FrameWallRequest,
            "run_context": SceneRequest, "run_start": RunStartRequest,
            "run_list": SceneRequest, "run_get": RunReferenceRequest,
            "run_cancel": RunReferenceRequest, "run_result": RunReferenceRequest,
            "operator_study_context": SceneRequest, "operator_study_start": StudyStartRequest,
            "operator_study_list": SceneRequest, "operator_study_report": StudyReferenceRequest,
            "operator_study_stop": StudyReferenceRequest,
            "operator_study_record": StudyRecordRequest,
            "operator_study_view": StudyViewRequest,
            "operator_study_submit": StudySubmitRequest,
            "operator_study_resume": StudyResumeRequest,
        }
        if action not in schemas:
            raise Denied("ACTION_DENIED")
        request = schemas[action].model_validate(payload)
        session = self._session(request.session_ref)
        started = time.perf_counter()
        try:
            result = self._invoke(action, request, session)
            scene = self.catalog.get(getattr(request, "scene_id", None))
            annotate = getattr(scene, "annotate_contact_quality", None)
            if annotate is not None:
                result = annotate(result)
        except Exception:
            session.logs.append({"action": action, "status": "REJECTED"})
            session.logs[:] = session.logs[-200:]
            raise
        scene_id = getattr(request, "scene_id", None)
        log = {"action": action, "scene_id": scene_id, "status": "OK",
               "duration_ms": round((time.perf_counter() - started) * 1000, 3)}
        if isinstance(request, EventRequest):
            log["event_ref"] = request.event_ref
        session.logs.append(log)
        session.logs[:] = session.logs[-200:]
        return result

    def _invoke(self, action: str, request: Request, session: Session) -> dict[str, Any]:
        if action not in {"scene", "query", "event", "note"}:
            self._research(session)
        if action in {"gallery_list", "gallery_detail", "presentations", "presentation",
                      "validate", "publish"} and self.operator_studies is not None:
            self.operator_studies.guard_external("", request.session_ref, action)
        if action in {"gallery_list", "gallery_detail"}:
            if self.gallery is None:
                return {"items": [], "status": "UNAVAILABLE", "reason": "NO_REGISTERED_GALLERY"}
            if action == "gallery_list":
                return self.gallery.list()
            assert isinstance(request, GalleryRequest)
            return {"family": self.gallery.detail(request.family_ref)}
        if action in {"presentations", "presentation"}:
            if self.presentation_provider is None:
                return {"items": [], "status": "UNAVAILABLE"}
            try:
                presentation = self.presentation_provider()
            except (OSError, ValueError):
                return {"items": [], "status": "UNAVAILABLE",
                        "reason": "SOURCE_BINDING_UNAVAILABLE"}
            if action == "presentations":
                keys = ("presentation_ref", "label", "binding", "origin", "image_measurement",
                        "authority")
                return {"items": [{key: presentation[key] for key in keys}], "status": "AVAILABLE"}
            assert isinstance(request, PresentationRequest)
            if request.presentation_ref != presentation["presentation_ref"]:
                raise Denied("REFERENCE_DENIED")
            return {"presentation": presentation}
        if isinstance(request, ValidateRequest):
            scene_id = session.draft_scenes.get(request.draft_id)
            if scene_id is None:
                # Existing drafts may be resumed, but only from an allowed scene.
                for allowed in session.scene_ids:
                    drafts = self.reviews.state(allowed)["drafts"]
                    if any(d["draft_id"] == request.draft_id for d in drafts):
                        scene_id = allowed
                        break
            if scene_id is None:
                raise Denied("DRAFT_DENIED")
            self._scene(session, scene_id)
            if isinstance(request, PublishRequest):
                publication = self.reviews.publish_draft(
                    request.draft_id, request.reviewer, request.reason, request.expected_version
                )
                return {"publication": publication, "review_state": self.reviews.state(scene_id)}
            return {"validation": self.reviews.validate_draft(request.draft_id)}
        assert isinstance(request, SceneRequest)
        scene = self._scene(session, request.scene_id)
        if action.startswith("run_"):
            if self.operator_studies is not None:
                self.operator_studies.guard_external(scene.scene_id, request.session_ref, action)
            if self.run_jobs is None:
                if action == "run_context":
                    return {"available": False, "reason": "NO_REGISTERED_RUN_PIPELINE"}
                raise RuntimeError("RESOURCE_UNAVAILABLE")
            manager = self.run_jobs
            if scene.scene_id != manager.scene.scene_id:
                if action == "run_context":
                    return {"available": False, "reason": "NO_REGISTERED_RUN_PIPELINE"}
                raise Denied("RUN_PIPELINE_UNAVAILABLE")
            if isinstance(request, RunStartRequest):
                return manager.start(scene.scene_id, request.annotation_version,
                                     request.parameters, request.idempotency_key)
            if isinstance(request, RunReferenceRequest):
                handler = getattr(manager, {"run_get": "get", "run_cancel": "cancel",
                                            "run_result": "result"}[action])
                return cast(dict[str, Any], handler(scene.scene_id, request.job_ref))
            return manager.context(scene.scene_id) if action == "run_context" else (
                manager.list(scene.scene_id))
        if action.startswith("operator_study_"):
            if self.operator_studies is None:
                if action == "operator_study_context":
                    return {"status": "UNAVAILABLE", "reason": "NO_REGISTERED_TASK_PACK"}
                raise RuntimeError("RESOURCE_UNAVAILABLE")
            store, study_owner = self.operator_studies, request.session_ref
            if scene.scene_id not in store.catalog:
                if action == "operator_study_context":
                    return {"available": False, "status": "UNAVAILABLE",
                            "reason": "NO_REGISTERED_TASK_PACK"}
                raise Denied("STUDY_PIPELINE_UNAVAILABLE")
            if isinstance(request, StudyStartRequest):
                if request.mode == "manual" and self.phase2_suite is not None:
                    self.phase2_suite.before_manual_study(study_owner)
                return store.start(scene.scene_id, study_owner, request.task_ref, request.mode)
            if isinstance(request, StudyResumeRequest):
                if self.phase2_suite is not None:
                    self.phase2_suite.before_manual_study(study_owner)
                return store.resume(scene.scene_id, request.study_ref,
                                    request.recovery_token, study_owner)
            if isinstance(request, StudySubmitRequest):
                return store.submit(scene.scene_id, study_owner, request.study_ref, request.answer)
            if isinstance(request, StudyRecordRequest):
                return store.record(scene.scene_id, study_owner, request.study_ref, request.action,
                                    request.camera_id, request.frame_ref, request.evidence_ref)
            if isinstance(request, StudyViewRequest):
                study_view = store.view(scene.scene_id, study_owner, request.study_ref,
                                    request.camera_id, request.timestamp, request.frame_ref)
                ref = study_view.get("frame", {}).get("media_ref")
                if ref:
                    session.media.setdefault(scene.scene_id, set()).add(ref)
                return study_view
            if isinstance(request, StudyReferenceRequest):
                return cast(dict[str, Any], getattr(store, {"operator_study_report": "report",
                                       "operator_study_stop": "stop"}[action])(
                    scene.scene_id, study_owner, request.study_ref))
            return store.context(scene.scene_id) if action == "operator_study_context" else (
                store.list(scene.scene_id, study_owner))
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene.scene_id, request.session_ref, action)
        layer = {"motion_reconstruction": "motion",
                 "cross_camera_reconstruction": "association",
                 "target_reconstruction": "association",
                 "physical_cross_camera_reconstruction": "physical",
                 "physical_review": "physical"}.get(action)
        availability = (scene.snapshot().get("layer_availability", {}).get(layer, {})
                        if layer else {})
        blind_integration = getattr(scene, "_blind_hypothesis", None)
        if availability.get("status") == "UNAVAILABLE" and not (
                action == "target_reconstruction" and blind_integration is not None):
            return {"status": "UNAVAILABLE", "available": False, "layer": layer,
                    "reason": availability["reason"], "scope": scene.live_scope()}
        if action == "frame_retrieval":
            assert isinstance(request, FrameRetrievalRequest)
            retrieval = getattr(scene, "_frame_retrieval", None)
            if retrieval is None:
                from amidst.workbench.frame_retrieval import unavailable_retrieval
                return unavailable_retrieval(request.model_dump(mode="json"), scene.live_scope())
            previous = None
            if request.hypothesis is not None:
                previous = session.blind_responses.get(scene.scene_id, {}).get(request.hypothesis.response_sha256)
            integration = getattr(scene, "_blind_hypothesis", None)
            applied = integration.applied_evidence(previous) if integration and previous else []
            result = retrieval.query(request.model_dump(mode="json"), previous,
                                     applied_evidence=applied)
            issued = session.retrieval_evidence_refs.setdefault(scene.scene_id, set())
            for evidence in result["negative_evidence_candidates"]:
                ref = evidence["negative_evidence_ref"]
                if integration is not None:
                    integration.negative_evidence[ref] = copy.deepcopy(evidence)
                    issued.add(ref)
            session.media.setdefault(scene.scene_id, set()).update(result["frame_evaluations"])
            return result
        if action == "camera_frame_wall":
            assert isinstance(request, FrameWallRequest)
            wall = getattr(scene, "camera_frame_wall", None)
            if (not scene.snapshot().get("capabilities", {}).get("camera_frame_wall", False)
                    or wall is None):
                raise Denied("FRAME_WALL_UNAVAILABLE")
            wall_result = wall(request.camera_ids, request.start, request.end, request.slot_count)
            session.media.setdefault(scene.scene_id, set()).update(
                row["media_ref"] for row in wall_result["frames"] if row.get("media_ref"))
            return cast(dict[str, Any], wall_result)
        if action in {"physical_review", "physical_review_decision", "physical_review_delta"}:
            if not scene.snapshot().get("capabilities", {}).get("physical_review", False):
                raise Denied("PHYSICAL_REVIEW_UNAVAILABLE")
            get_index = getattr(scene, "physical_review_index", None)
            if get_index is None:
                raise Denied("PHYSICAL_REVIEW_UNAVAILABLE")
            index = get_index()
            if action == "physical_review":
                assert isinstance(request, MotionRequest)
                review_snapshot = getattr(scene, "physical_review", None)
                if review_snapshot is None:
                    raise Denied("PHYSICAL_REVIEW_UNAVAILABLE")
                review_result = review_snapshot(request.camera_ids, request.start, request.end)
                digest = review_result["review_sha256"]
                session.physical_review_issued[scene.scene_id] = (
                    digest, frozenset(row["item_ref"] for row in review_result["items"]))
                return {**review_result, "review_state": self.physical_review_store.state(
                    scene.scene_id, digest)}
            issued = session.physical_review_issued.get(scene.scene_id)
            assert isinstance(request, (PhysicalReviewDecisionRequest, PhysicalReviewDeltaRequest))
            if issued is None or issued[0] != request.review_sha256:
                raise Denied("PHYSICAL_REVIEW_REFERENCE_DENIED")
            if index.review_sha256 != request.review_sha256:
                raise Denied("PHYSICAL_REVIEW_REFERENCE_DENIED")
            if action == "physical_review_delta":
                assert isinstance(request, PhysicalReviewDeltaRequest)
                delta = self.physical_review_store.export_delta(
                    scene.scene_id, request.review_sha256, request.revision)
                filename = f"{scene.scene_id}-physical-review-delta-v{request.revision}.json"
                return {"delta": delta, "filename": filename}
            assert isinstance(request, PhysicalReviewDecisionRequest)
            if request.item_ref not in issued[1]:
                raise Denied("PHYSICAL_REVIEW_REFERENCE_DENIED")
            from amidst.workbench.blender_physical_review import validate_review_decision

            decision = validate_review_decision(index, {
                "review_sha256": request.review_sha256, "item_ref": request.item_ref,
                "checks": request.checks})
            record = self.physical_review_store.append(
                scene.scene_id, request.review_sha256, decision,
                expected_revision=request.expected_revision, reviewer=request.reviewer,
                reason=request.reason)
            session.logs.append({"action": "human_physical_review_delta",
                                 "scene_id": scene.scene_id,
                                 "item_ref": request.item_ref, "revision": record["revision"],
                                 "status": "LOCAL_HUMAN_RECORD_ONLY"})
            return {"record": record, "review_state": self.physical_review_store.state(
                scene.scene_id, request.review_sha256), "authority_changed": False,
                "rerun_authorized": False, "post_confirmation_rerun_performed": False}
        if action == "physical_cross_camera_reconstruction":
            assert isinstance(request, AssociationRequest)
            reconstruct = getattr(scene, "physical_cross_camera_reconstruction", None)
            capabilities = scene.snapshot().get("capabilities", {})
            if (not capabilities.get("physical_cross_camera_reconstruction", False)
                    or reconstruct is None):
                raise Denied("PHYSICAL_RECONSTRUCTION_UNAVAILABLE")
            physical: dict[str, Any] = reconstruct(
                request.camera_ids, request.start, request.end, request.top_k)
            physical_artifacts: dict[str, Any] = {
                "status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"}
            if self.physical_media_provider is not None:
                try:
                    physical_artifacts = self.physical_media_provider.manifest(scene)
                except (OSError, ValueError, RuntimeError):
                    physical_artifacts = {"status": "UNAVAILABLE", "items": [],
                                          "reason": "INVALID_OR_STALE_ARTIFACT"}
                    session.logs.append({"action": "physical_artifact",
                                         "scene_id": scene.scene_id, "status": "REJECTED"})
            session.physical_media[scene.scene_id] = {
                item["media_ref"] for item in physical_artifacts.get("items", [])}
            for candidate in physical.get("candidates", []) + physical.get(
                    "rejected_candidates", []):
                session.logs.append({"action": "physical_candidate", "scene_id": scene.scene_id,
                                     "candidate_ref": candidate["candidate_ref"],
                                     "status": candidate.get("physical", {}).get(
                                         "verdict", "UNKNOWN")})
                for path in candidate.get("paths", []):
                    session.logs.append({"action": "physical_event", "scene_id": scene.scene_id,
                                         "event_ref": path["event_ref"], "status": "PROVISIONAL"})
            return {**physical, "artifacts": physical_artifacts}
        if action == "target_reconstruction":
            assert isinstance(request, TargetReconstructionRequest)
            reconstruct = getattr(scene, "cross_camera_reconstruction", None)
            if (not scene.snapshot().get("capabilities", {}).get(
                    "cross_camera_reconstruction", False) or reconstruct is None
                    ) and blind_integration is None:
                raise Denied("CROSS_CAMERA_RECONSTRUCTION_UNAVAILABLE")
            from amidst.workbench.target_reconstruction import TargetScene, reconstruct_target

            target = reconstruct_target(cast(TargetScene, scene), request.camera_ids,
                                        request.start, request.end,
                                        request.top_k, request.observation_ref)
            if blind_integration is not None:
                if (request.negative_evidence_refs
                        and request.negative_evidence_mode != "BASELINE_AND_FEEDBACK"):
                    raise Denied("NEGATIVE_EVIDENCE_MODE_CONFLICT")
                cache = session.blind_responses.setdefault(scene.scene_id, {})
                previous = cache.get(request.previous_response_sha256)
                if any(ref not in session.retrieval_evidence_refs.get(scene.scene_id, set())
                       for ref in request.negative_evidence_refs):
                    raise Denied("NEGATIVE_EVIDENCE_NOT_ISSUED_TO_SESSION")
                target.update(blind_integration.reconstruct(request, previous))
                response = target["blind_hypotheses"]
                cache[response["output_sha256"]] = copy.deepcopy(response)
                while len(cache) > blind_integration.binding["max_cached_responses_per_session"]:
                    cache.pop(next(iter(cache)))
            elif (request.negative_evidence_refs or request.previous_response_sha256
                  or "negative_evidence_mode" in request.model_fields_set):
                raise Denied("BLIND_HYPOTHESES_UNAVAILABLE")
            for entry in target["trace"]:
                session.logs.append({"action": "target_reconstruction_decision",
                                     "scene_id": scene.scene_id, **entry})
            return target
        if action == "cross_camera_reconstruction":
            assert isinstance(request, AssociationRequest)
            reconstruct = getattr(scene, "cross_camera_reconstruction", None)
            capabilities = scene.snapshot().get("capabilities", {})
            if (not capabilities.get("cross_camera_reconstruction", False)
                    or reconstruct is None):
                raise Denied("CROSS_CAMERA_RECONSTRUCTION_UNAVAILABLE")
            association: dict[str, Any] = reconstruct(
                request.camera_ids, request.start, request.end, request.top_k)
            association_artifacts: dict[str, Any] = {
                "status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"}
            if self.association_media_provider is not None:
                try:
                    association_artifacts = self.association_media_provider.manifest(
                        cast(AssociationScene, scene))
                except (OSError, ValueError, RuntimeError):
                    association_artifacts = {"status": "UNAVAILABLE", "items": [],
                                             "reason": "INVALID_OR_STALE_ARTIFACT"}
                    session.logs.append({"action": "association_artifact",
                                         "scene_id": scene.scene_id,
                                         "status": "REJECTED"})
            session.association_media[scene.scene_id] = {
                item["media_ref"] for item in association_artifacts.get("items", [])}
            for candidate in association.get("candidates", []):
                session.logs.append({"action": "association_candidate", "scene_id": scene.scene_id,
                                     "candidate_ref": candidate["candidate_ref"],
                                     "status": "HYPOTHESIS_ONLY"})
                for path in candidate.get("paths", []):
                    session.logs.append({"action": "association_event", "scene_id": scene.scene_id,
                                         "event_ref": path["event_ref"],
                                         "status": "PROVISIONAL"})
            return {**association, "artifacts": association_artifacts}
        if action == "motion_reconstruction":
            assert isinstance(request, MotionRequest)
            reconstruct = getattr(scene, "motion_reconstruction", None)
            if (not scene.snapshot().get("capabilities", {}).get("motion_reconstruction", False)
                    or reconstruct is None):
                raise Denied("MOTION_RECONSTRUCTION_UNAVAILABLE")
            motion: dict[str, Any] = reconstruct(request.camera_ids, request.start, request.end)
            artifacts: dict[str, Any] = {
                "status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"}
            if self.motion_media_provider is not None:
                try:
                    artifacts = self.motion_media_provider.manifest(cast(MotionScene, scene))
                except (OSError, ValueError, RuntimeError):
                    # Optional replay failures do not replace valid motion evidence.
                    artifacts = {"status": "UNAVAILABLE", "items": [],
                                 "reason": "INVALID_OR_STALE_ARTIFACT"}
                    session.logs.append({"action": "motion_artifact", "scene_id": scene.scene_id,
                                         "status": "REJECTED"})
            session.motion_media[scene.scene_id] = {
                item["media_ref"] for item in artifacts.get("items", [])}
            for track in motion.get("tracks", []):
                for event in track.get("events", []):
                    session.logs.append({"action": "motion_candidate", "scene_id": scene.scene_id,
                                         "event_ref": event["event_ref"],
                                         "status": "PROVISIONAL"})
            return {**motion, "artifacts": artifacts}
        if action == "frame_query":
            assert isinstance(request, FrameQueryRequest)
            if not scene.snapshot().get("capabilities", {}).get("frame_query", False):
                raise Denied("FRAME_QUERY_UNAVAILABLE")
            frame_query = getattr(scene, "frame_query", None)
            if frame_query is None:
                raise Denied("FRAME_QUERY_UNAVAILABLE")
            result: dict[str, Any] = frame_query(
                request.camera_ids, request.start, request.end, request.target_timestamp,
                request.top_k, request.behavior_intent,
            )
            session.media.setdefault(scene.scene_id, set()).update(
                item["media_ref"] for item in result.get("items", []) if item.get("media_ref")
            )
            return result
        if action in {"semantic_presets", "navigation_guide", "agent_decision"}:
            if not scene.snapshot().get("capabilities", {}).get("navigation_guidance", True):
                raise Denied("AGENT_GUIDANCE_UNAVAILABLE")
            index = self.guidance_indexes.get(scene.scene_id)
            if index is not None and index.scene is not scene:
                for owner in self.sessions.values():
                    owner.guides = {ref: saved for ref, saved in owner.guides.items()
                                    if saved[0] != scene.scene_id}
                index = None
            if index is None:
                index = GuidanceIndex(scene)
                self.guidance_indexes[scene.scene_id] = index
            if action == "semantic_presets":
                return {"presets": index.presets()}
            snapshot = scene.snapshot()
            binding = content_hash({key: snapshot.get(key) for key in
                                    ("scene_id", "source_hash", "run_id", "config_sha256",
                                     "registry_sha256", "freeze_ref")} | {
                                         "live_binding": scene.service.guard.binding.model_dump(
                                             mode="json"),
                                         "live_stage": scene.service.guard.stage})
            if action == "agent_decision":
                assert isinstance(request, DecisionRequest)
                stored = session.guides.get(request.guide_ref)
                if stored is None or stored[:2] != (scene.scene_id, binding):
                    raise Denied("GUIDE_SCOPE_DENIED")
                agent_input = stored[2]["agent_input"]
                agent_output = mock_decide(agent_input)
                executions = []
                for step in agent_output["next_bounded_actions"]:
                    if step["tool"] != "get_event_detail":
                        raise Denied("GUIDE_TOOL_DENIED")
                    detail = scene.event(step["record_ref"])
                    executions.append({"tool": step["tool"], "event_ref": step["record_ref"],
                                       "response_sha256": content_hash(detail),
                                       "candidate_count": len(detail.get("candidates", [])),
                                       "hypothesis_count": len(detail.get("trajectories", [])),
                                       "status": "PASS"})
                    session.logs.append({"action": "agent_get_event_detail",
                                         "scene_id": scene.scene_id,
                                         "event_ref": step["record_ref"], "status": "OK"})
                return {"status": stored[2]["status"], "agent_input": agent_input,
                        "agent_output": agent_output, "executed_actions": executions,
                        "guide_ref": request.guide_ref}
            assert isinstance(request, GuidanceRequest)
            if request.start > request.end or request.end - request.start > 120:
                raise Denied("FINITE_WINDOW_REQUIRED")
            guidance = index.guide(request.label, request.camera_id, request.start, request.end,
                                   request.behavior, request.top_k)
            guide_ref = "guide-" + content_hash({"scope": binding, "guidance": guidance})
            session.guides[guide_ref] = (scene.scene_id, binding, guidance)
            while len(session.guides) > 20:
                session.guides.pop(next(iter(session.guides)))
            return {**guidance, "guide_ref": guide_ref}
        if action == "system_ports":
            if scene.snapshot().get("capabilities", {}).get("frame_query", False):
                if scene.snapshot().get("capabilities", {}).get(
                        "physical_cross_camera_reconstruction", False):
                    from amidst.workbench.blender_physical_ports import run_physical_port_probe

                    return run_physical_port_probe(scene, self.motion_media_provider,
                        self.association_media_provider, self.physical_media_provider)
                from amidst.workbench.blender_ports import run_blender_port_probe

                return run_blender_port_probe(
                    scene, self.motion_media_provider, self.association_media_provider)
            return {**run_port_probe(), "selected_scene_id": scene.scene_id,
                    "selected_scene_used_as_input": False}
        if action == "storage_probe":
            assert isinstance(request, StorageProbeRequest)
            probe = run_storage_probe(request.stage)
            return {**probe, "status": "PASS" if probe["passed"] else "FAIL",
                    "phases": [{**p, "status": "PASS" if p["passed"] else "FAIL"}
                               for p in probe["phases"]]}
        if action == "export_delta":
            assert isinstance(request, VersionRequest)
            delta = self.reviews.export_delta(scene.scene_id, request.version)
            return {"filename": f"{scene.scene_id}-delta-v{request.version}.json", "delta": delta}
        if action == "scene":
            snapshot = scene.snapshot()
            if session.role == "management":
                snapshot = {k: snapshot[k] for k in
                            ("scene_id", "label", "description", "time_range") if k in snapshot}
                snapshot.update({"objects": [], "capabilities": {
                    "images": True, "scene_review": False, "evaluation": False,
                    "multicamera_3d": False,
                }, "cameras": [{"camera_id": c["camera_id"],
                                  "label": c.get("label", c["camera_id"])}
                                 for c in scene.snapshot()["cameras"]]})
                return {"snapshot": snapshot, "review_state": None}
            return {"snapshot": snapshot, "review_state": self.reviews.state(scene.scene_id)}
        if action in {"query", "test"}:
            assert isinstance(request, QueryRequest)
            if request.start > request.end or request.end - request.start > 120:
                raise Denied("FINITE_WINDOW_REQUIRED")
            result = scene.query(request.camera_id, request.start, request.end)
            if action == "test":
                return self._test(scene, result)
            for event in result["events"]:
                self._issue_media(session, scene.scene_id, event)
            if session.role == "management":
                return {"events": [self._public_event(e) for e in result["events"]],
                        "observations": [], "retrieval": {
                            "truncated": result.get("retrieval", {}).get("truncated", False),
                            "time_range": [request.start, request.end],
                        }}
            return result
        if action in {"event", "result_review", "note"}:
            assert isinstance(request, EventRequest)
            event = scene.event(request.event_ref)
            self._issue_media(session, scene.scene_id, event)
            if isinstance(request, ResultRequest):
                return {"review": self.reviews.record_result(
                    scene.scene_id, request.event_ref, request.decision, request.reason,
                    request.reviewer, scene.run_id,
                )}
            if isinstance(request, NoteRequest):
                record = self.reviews.record_note(
                    scene.scene_id, request.event_ref, request.status, request.note,
                    request.reviewer, scene.run_id,
                )
                record = {**record, "record_status": record["status"],
                          "status": record["handling_status"]}
                return {"note": record if session.role == "research" else {
                    k: record[k] for k in ("status", "note", "reviewer", "created_at")
                    if k in record
                }}
            return {"event": event if session.role == "research" else self._public_event(event),
                    "notes": self._notes(scene.scene_id, request.event_ref, session.role)}
        if action == "timeline":
            assert isinstance(request, TimelineRequest)
            return scene.frames(request.camera_ids, request.timestamp)
        if action == "draft":
            assert isinstance(request, DraftRequest)
            if not scene.snapshot().get("capabilities", {}).get("scene_review", True):
                raise Denied("SCENE_REVIEW_UNAVAILABLE")
            draft = self.reviews.save_draft(
                scene.scene_id, request.object_id, request.changes, request.base_version,
                request.reviewer, request.reason,
            )
            session.draft_scenes[draft["draft_id"]] = scene.scene_id
            return {"draft": draft}
        if action == "review_state":
            return self.reviews.state(scene.scene_id)
        if action == "export":
            assert isinstance(request, VersionRequest)
            state = self.reviews.state(scene.scene_id)
            version = next((v for v in state["versions"] if v["version"] == request.version), None)
            if version is None:
                raise Denied("VERSION_DENIED")
            return {"filename": f"{scene.scene_id}-annotation-v{request.version}.json",
                    "annotation": version.get("overlay", version), "receipt": version}
        if action == "evaluation":
            return {"evaluation": scene.evaluation()}
        if action == "logs":
            return {"items": [row for row in session.logs if row.get("scene_id") == scene.scene_id],
                    "identity": "SELF_DECLARED_LOCAL_OPERATOR"}
        raise Denied("ACTION_DENIED")

    def _test(self, scene: SceneAdapter, result: dict[str, Any]) -> dict[str, Any]:
        """A bounded live data check, distinct from model accuracy or full test suite."""
        checks: list[dict[str, Any]] = []
        def check(name: str, passed: bool, detail: str) -> None:
            checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
        snapshot = scene.snapshot()
        check("場景來源綁定", bool(scene.source_hash), "已由原場景 loader 核對來源與 freeze")
        objects = snapshot["objects"]
        check("物件索引唯一", len({o["object_id"] for o in objects}) == len(objects),
              f"{len(objects)} 個已登錄物件")
        finite = all(math.isfinite(float(x)) for o in objects
                     for p in o.get("geometry", {}).get("points", []) for x in p)
        check("展示座標有效", finite, "已登錄靜態幾何使用有限座標")
        receipt = result.get("retrieval", {})
        check("局部查詢完成", not receipt.get("truncated", False),
              "只檢查所選鏡頭／時間窗；截斷不代表全域完成")
        events = result["events"]
        media = next((r for e in events for r in e.get("media_refs", [])), None)
        if media:
            _, data = scene.media(media)
            check("來源影像讀取", bool(data), "按 reference 核對並讀取一張來源影像")
        else:
            checks.append({"name": "來源影像讀取", "status": "NOT_RUN",
                           "detail": "此範圍沒有事件媒體，未假造測試樣本"})
        state = self.reviews.state(scene.scene_id)
        checks.append({"name": "標註與凍結結果版本", "status":
                       "NEEDS_RERUN" if state["current_version"] else "PASS",
                       "detail": "已發布標註另存；舊結果仍綁定原設定"})
        return {"checks": checks, "summary": {
            "passed": sum(c["status"] == "PASS" for c in checks), "total": len(checks),
            "events": len(events), "observations": len(result.get("observations", [])),
            "scope": "SELECTED_CAMERA_TIME_ONLY", "formal_acceptance": False,
        }, "retrieval": receipt}

    def media(self, token: str, scene_id: str, ref: str) -> tuple[str, bytes]:
        session = self._session(token)
        scene = self._scene(session, scene_id)
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene_id, token, "external_media")
        if session.role == "management" and ref not in session.media.get(scene_id, set()):
            raise Denied("MEDIA_DENIED")
        return scene.media(ref)

    def study_media(self, token: str, scene_id: str, study_ref: str,
                    ref: str) -> tuple[str, bytes]:
        session = self._session(token)
        self._research(session)
        scene = self._scene(session, scene_id)
        if self.operator_studies is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        self.operator_studies.authorize_media(scene_id, token, study_ref, ref)
        return scene.media(ref)

    def presentation_media(self, token: str, ref: str) -> tuple[str, bytes]:
        self._research(self._session(token))
        if self.operator_studies is not None:
            self.operator_studies.guard_external("", token, "presentation_media")
        if self.presentation_media_provider is None:
            raise Denied("RESOURCE_UNAVAILABLE")
        return self.presentation_media_provider(ref)

    def motion_media(self, token: str, scene_id: str, ref: str,
                     range_header: str | None = None) -> BinaryResponse:
        session = self._session(token)
        self._research(session)
        scene = self._scene(session, scene_id)
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene_id, token, "motion_media")
        if ref not in session.motion_media.get(scene_id, set()):
            raise Denied("MOTION_MEDIA_DENIED")
        if self.motion_media_provider is None:
            raise Denied("MOTION_MEDIA_UNAVAILABLE")
        mime, data = self.motion_media_provider.media(cast(MotionScene, scene), ref)
        return self._replay_binary(mime, data, range_header)

    def cross_camera_media(self, token: str, scene_id: str, ref: str,
                           range_header: str | None = None) -> BinaryResponse:
        session = self._session(token)
        self._research(session)
        scene = self._scene(session, scene_id)
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene_id, token, "cross_camera_media")
        if ref not in session.association_media.get(scene_id, set()):
            raise Denied("CROSS_CAMERA_MEDIA_DENIED")
        if self.association_media_provider is None:
            raise Denied("CROSS_CAMERA_MEDIA_UNAVAILABLE")
        mime, data = self.association_media_provider.media(cast(AssociationScene, scene), ref)
        return self._replay_binary(mime, data, range_header)

    def physical_cross_camera_media(self, token: str, scene_id: str, ref: str,
                                    range_header: str | None = None) -> BinaryResponse:
        session = self._session(token)
        self._research(session)
        scene = self._scene(session, scene_id)
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene_id, token, "physical_cross_camera_media")
        if ref not in session.physical_media.get(scene_id, set()):
            raise Denied("PHYSICAL_MEDIA_DENIED")
        if self.physical_media_provider is None:
            raise Denied("PHYSICAL_MEDIA_UNAVAILABLE")
        mime, data = self.physical_media_provider.media(scene, ref)
        return self._replay_binary(mime, data, range_header)

    @staticmethod
    def _replay_binary(mime: str, data: bytes, range_header: str | None) -> BinaryResponse:
        if mime != "video/mp4":
            if range_header is not None:
                raise Denied("RANGE_DENIED")
            return BinaryResponse(200, mime, (), data)
        headers = (("Accept-Ranges", "bytes"),)
        if range_header is None:
            return BinaryResponse(200, mime, headers, data)
        match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", range_header)
        if match and (match[1] or match[2]) and data:
            if match[1]:
                first = int(match[1])
                last = min(int(match[2]), len(data) - 1) if match[2] else len(data) - 1
            else:
                count = int(match[2])
                first, last = max(0, len(data) - count), len(data) - 1
                if count == 0:
                    first = len(data)
            if 0 <= first <= last < len(data):
                return BinaryResponse(206, mime, headers + (("Content-Range",
                    f"bytes {first}-{last}/{len(data)}"),), data[first:last + 1])
        return BinaryResponse(416, "application/json", (("Content-Range",
            f"bytes */{len(data)}"),), b'{"error":"RANGE_DENIED"}')


    def gallery_media(self, token: str, ref: str) -> tuple[str, bytes]:
        self._research(self._session(token))
        if self.operator_studies is not None:
            self.operator_studies.guard_external("", token, "gallery_media")
        if self.gallery is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        return self.gallery.media(ref)

    def _product_access(self, payload: object) -> BridgeRequest:
        if not isinstance(payload, dict):
            raise ValueError("INVALID_REQUEST")
        request = BridgeRequest.model_validate({key: payload.get(key)
                                               for key in ("session_ref", "scene_id")})
        session = self._session(request.session_ref)
        self._research(session)
        self._scene(session, request.scene_id)
        return request

    def product_call(self, action: str, payload: object) -> dict[str, Any] | BinaryResponse:
        if action not in PRODUCT_ACTIONS:
            raise Denied("ACTION_DENIED")
        request = self._product_access(payload)
        if self.operator_studies is not None:
            self.operator_studies.guard_external(request.scene_id, request.session_ref,
                                                "product_" + action)
        session, started = self._session(request.session_ref), time.perf_counter()
        log = {"action": "product_" + action, "scene_id": request.scene_id, "status": "REJECTED"}
        try:
            bridge = self._product_bridge(request.scene_id)
            if bridge is None:
                if action != "context":
                    raise RuntimeError("RESOURCE_UNAVAILABLE")
                # A missing optional product never replaces an existing scene.
                ContextRequest.model_validate(payload)
                result: dict[str, Any] | BinaryResponse = {
                    "scene_id": request.scene_id, "status": "UNAVAILABLE",
                    "reason": "NO_CERTIFIED_PRODUCT",
                    "capabilities": {"investigation": False, "inference_execution": False}}
            else:
                result = bridge.call(action, payload)
            log["status"] = "OK"
            return result
        finally:
            session.logs.append({**log, "duration_ms": round(
                (time.perf_counter() - started) * 1000, 3)})
            session.logs[:] = session.logs[-200:]

    def product_media(self, token: str, scene_id: str, ref: str) -> BinaryResponse:
        self._product_access({"session_ref": token, "scene_id": scene_id})
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene_id, token, "product_media")
        bridge = self._product_bridge(scene_id)
        if bridge is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        return bridge.media(token, scene_id, ref)

    def product_video(self, token: str, scene_id: str, ref: str,
                      range_header: str | None = None) -> BinaryResponse:
        self._product_access({"session_ref": token, "scene_id": scene_id})
        if self.operator_studies is not None:
            self.operator_studies.guard_external(scene_id, token, "product_video")
        bridge = self._product_bridge(scene_id)
        if bridge is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        return bridge.video(token, scene_id, ref, range_header)


def _json(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")


class Application:
    def __init__(self, workbench: Workbench, repo: Path) -> None:
        self.workbench, self.repo = workbench, repo
        self.frontend = repo / "frontend/workbench"

    def __call__(
        self, environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        status = "200 OK"
        content_type = "application/json; charset=utf-8"
        additional_headers: tuple[tuple[str, str], ...] = ()
        try:
            response = self._dispatch(environ)
            if isinstance(response, BinaryResponse):
                code = HTTPStatus(response.status)
                if not 200 <= code.value <= 599:
                    raise ValueError("INVALID_RESPONSE_STATUS")
                status = f"{code.value} {code.phrase}"
                content_type, body = response.mime_type, response.body
                if any(name.lower() not in {"accept-ranges", "content-range", "content-disposition"}
                       or "\r" in value or "\n" in value for name, value in response.headers):
                    raise ValueError("INVALID_RESPONSE_HEADERS")
                additional_headers = response.headers
            else:
                content_type, body = response
        except (Denied, BridgeDenied, GalleryError) as error:
            status = "403 Forbidden"
            content_type, additional_headers = "application/json; charset=utf-8", ()
            body = _json({"error": {"code": str(error),
                                    "message": "此操作或資料不在目前角色範圍內。"}})
        except (ValidationError, ValueError, TypeError, KeyError):
            status = "400 Bad Request"
            content_type, additional_headers = "application/json; charset=utf-8", ()
            body = _json({"error": {"code": "INVALID_OR_STALE_REQUEST",
                                    "message": "資料無效或版本已更新，請重新載入並核對輸入。"}})
        except (OSError, RuntimeError):
            status = "503 Service Unavailable"
            content_type, additional_headers = "application/json; charset=utf-8", ()
            body = _json({"error": {"code": "RESOURCE_UNAVAILABLE",
                                    "message": "所需資料目前無法讀取，請查看場景能力與來源狀態。"}})
        start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body))),
                                ("Cache-Control", "no-store"),
                                ("X-Content-Type-Options", "nosniff"),
                                ("Referrer-Policy", "no-referrer"), ("X-Frame-Options", "DENY"),
                                *additional_headers])
        return [body]

    def _dispatch(self, environ: dict[str, Any]) -> tuple[str, bytes] | BinaryResponse:
        host = environ.get("HTTP_HOST", "")
        parsed_host = urlsplit("//" + host)
        if (parsed_host.hostname not in {"127.0.0.1", "localhost"}
                or parsed_host.username or parsed_host.password or parsed_host.path
                or parsed_host.query or parsed_host.fragment
                or (environ.get("SERVER_PORT") and
                    (parsed_host.port or 80) != int(environ["SERVER_PORT"]))):
            raise Denied("HOST_DENIED")
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/")
        if method == "GET":
            if path == "/api/bootstrap":
                return "application/json; charset=utf-8", _json(self.workbench.bootstrap())
            if path == "/api/operator_study_media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "scene_id", "study_ref", "ref"} or any(
                    len(value) != 1 for value in query.values()
                ):
                    raise ValueError("INVALID_QUERY")
                return self.workbench.study_media(query["session_ref"][0], query["scene_id"][0],
                                                 query["study_ref"][0], query["ref"][0])
            if path in {"/api/motion_media", "/api/cross_camera_media",
                        "/api/physical_cross_camera_media"}:
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "scene_id", "ref"} or any(
                    len(value) != 1 for value in query.values()
                ):
                    raise ValueError("INVALID_QUERY")
                handler = {"/api/motion_media": self.workbench.motion_media,
                           "/api/cross_camera_media": self.workbench.cross_camera_media,
                           "/api/physical_cross_camera_media":
                               self.workbench.physical_cross_camera_media}[path]
                return handler(
                    query["session_ref"][0], query["scene_id"][0], query["ref"][0],
                    environ.get("HTTP_RANGE"))
            if path in {"/api/product_media", "/api/product_video"}:
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "scene_id", "ref"} or any(
                    len(v) != 1 for v in query.values()
                ):
                    raise ValueError("INVALID_QUERY")
                token, scene_id, ref = (query[key][0] for key in ("session_ref", "scene_id", "ref"))
                if path == "/api/product_media":
                    return self.workbench.product_media(token, scene_id, ref)
                return self.workbench.product_video(token, scene_id, ref, environ.get("HTTP_RANGE"))
            if path == "/api/gallery_media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "ref"} or any(len(v) != 1 for v in query.values()):
                    raise ValueError("INVALID_QUERY")
                return self.workbench.gallery_media(query["session_ref"][0], query["ref"][0])
            if path == "/api/presentation_media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "ref"} or any(len(v) != 1 for v in query.values()):
                    raise ValueError("invalid query")
                return self.workbench.presentation_media(query["session_ref"][0], query["ref"][0])
            if path == "/api/media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "scene_id", "ref"} or any(
                    len(value) != 1 for value in query.values()
                ):
                    raise ValueError("invalid query")
                return self.workbench.media(query["session_ref"][0], query["scene_id"][0],
                                            query["ref"][0])
            assets = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css",
                      "/app.mjs": "app.mjs", "/scene.mjs": "scene.mjs",
                      "/geometry.mjs": "geometry.mjs", "/motion.mjs": "motion.mjs",
                      "/presentation.mjs": "presentation.mjs",
                      "/presentation-data.mjs": "presentation-data.mjs",
                      "/investigation.mjs": "investigation.mjs", "/workflow.mjs": "workflow.mjs",
                      "/gallery.mjs": "gallery.mjs", "/blender-motion.mjs": "blender-motion.mjs",
                      "/cross-camera.mjs": "cross-camera.mjs"}
            assets["/physical-review.mjs"] = "physical-review.mjs"
            assets["/physical-review-flow.mjs"] = "physical-review-flow.mjs"
            assets["/investigation-scope.mjs"] = "investigation-scope.mjs"
            assets["/accuracy-evaluation.mjs"] = "accuracy-evaluation.mjs"
            assets["/run-study.mjs"] = "run-study.mjs"
            assets["/phase2-suite.mjs"] = "phase2-suite.mjs"
            assets["/demo-mode.mjs"] = "demo-mode.mjs"
            assets["/demo-steps.office.json"] = "demo-steps.office.json"
            assets["/blind-hypothesis.mjs"] = "blind-hypothesis.mjs"
            assets["/ground-estimate.mjs"] = "ground-estimate.mjs"
            if path == "/product/timeline.mjs":
                return "text/javascript", (self.repo / "frontend/product/timeline.mjs").read_bytes()
            if path in assets:
                name = assets[path]
                mime = "text/javascript" if name.endswith(".mjs") else (
                    mimetypes.guess_type(name)[0] or "application/octet-stream")
                return mime, (self.frontend / name).read_bytes()
            vendor = {"/vendor/three.module.js": "build/three.module.js",
                      "/vendor/three.core.js": "build/three.core.js",
                      "/vendor/OrbitControls.js": "examples/jsm/controls/OrbitControls.js"}
            if path in vendor:
                root = self.repo / "frontend/workbench/node_modules/three"
                return "text/javascript", (root / vendor[path]).read_bytes()
            raise Denied("ROUTE_DENIED")
        if method != "POST" or not path.startswith("/api/"):
            raise Denied("ROUTE_DENIED")
        origin = environ.get("HTTP_ORIGIN")
        if origin and origin != f"http://{host}":
            raise Denied("ORIGIN_DENIED")
        if environ.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
            raise Denied("JSON_REQUIRED")
        length = int(environ.get("CONTENT_LENGTH", "0"))
        if not 0 < length <= 65536:
            raise Denied("REQUEST_SIZE_DENIED")
        payload = json.loads(environ["wsgi.input"].read(length))
        action = path.removeprefix("/api/")
        if action.startswith("product_"):
            result = self.workbench.product_call(action.removeprefix("product_"), payload)
            return result if isinstance(result, BinaryResponse) else (
                "application/json; charset=utf-8", _json(result))
        if action.startswith("suite_"):
            self.workbench._product_access(payload)
            if self.workbench.phase2_suite is None:
                if action != "suite_context":
                    raise RuntimeError("RESOURCE_UNAVAILABLE")
                from amidst.workbench.phase2_suite import SuiteRequest

                request = SuiteRequest.model_validate(payload)
                if self.workbench.operator_studies is not None:
                    self.workbench.operator_studies.guard_external(
                        request.scene_id, request.session_ref, action)
                return "application/json; charset=utf-8", _json({
                    "schema_version": "workbench.phase2-suite.v1",
                    "scene_id": request.scene_id, "status": "UNAVAILABLE",
                    "research": None, "agent": None, "storage": None})
            return "application/json; charset=utf-8", _json(
                self.workbench.phase2_suite.call(action.removeprefix("suite_"), payload))
        data = self.workbench.session(payload) if action == "session" else (
            self.workbench.call(action, payload))
        return "application/json; charset=utf-8", _json(data)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Media query strings contain local session tokens; do not log them.
        pass


def configure_extensions(
    workbench: Workbench, repo: Path, *,
    canonical_root: Path | None = None,
) -> None:
    """Server-owned fixed sources; invalid optional products fail closed independently."""
    runtime = None
    from amidst.workbench.blender_association_media import AssociationMediaProvider
    from amidst.workbench.blender_motion_media import MotionMediaProvider
    from amidst.workbench.blender_physical_media import PhysicalMediaProvider
    from amidst.workbench.blender_physical_source import load_physical_source

    workbench.motion_media_provider = MotionMediaProvider(
        repo / "data/engineering/local_run/blender_motion_v1")
    workbench.association_media_provider = AssociationMediaProvider(
        repo / "data/engineering/local_run/blender_association_v1")
    workbench.physical_media_provider = PhysicalMediaProvider(
        repo / "data/engineering/local_run/blender_physical_v2")
    for physical_scene in workbench.catalog.values():
        if not hasattr(physical_scene, "bind_physical"):
            continue
        try:
            site = physical_scene.snapshot()["source_binding"]["site_id"]
            source = load_physical_source(repo, site)
            physical_scene.bind_physical(source)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            # Missing constraints affect this optional layer, not original observations.
            continue
    try:
        scene = workbench.catalog.get("local-camera")
        if scene is not None:
            runtime = load_product(repo / "data/product/local_run/operator_v2")
            workbench.product_bridge = ProductBridge(runtime, scene, workbench._session)
    except (ValueError, OSError, KeyError, TypeError):
        if runtime is not None:
            runtime.close()
        workbench.product_bridge = None
    accuracy_scene = workbench.catalog.get("local-camera-accuracy-v2")
    if accuracy_scene is not None:
        from amidst.workbench.accuracy_product import load_accuracy_product_bridge

        try:
            workbench.product_bridges[accuracy_scene.scene_id] = load_accuracy_product_bridge(
                repo / "data/engineering/local_run/accuracy_v2/test/final",
                accuracy_scene, workbench._session,
                workbench.reviews.db_path.with_name(
                    workbench.reviews.db_path.stem + "-accuracy-v2.sqlite3"),
            )
        except (ValueError, OSError, KeyError, TypeError, RuntimeError):
            workbench.product_bridges.pop(accuracy_scene.scene_id, None)
    try:
        workbench.gallery = Gallery(repo, canonical_root)
    except (GalleryError, OSError, ValueError, TypeError):
        workbench.gallery = None
    lab = workbench.catalog.get("synthetic-lab")
    if lab is not None:
        # Fixed existing synthetic source; each state database owns its isolated job ledger.
        state_ref = content_hash({"state": str(workbench.reviews.db_path.resolve())})[:20]
        output_root = repo / "data/engineering/local_run/workbench_jobs_v1" / state_ref
        try:
            workbench.run_jobs = SingleSyntheticRunManager(lab, workbench.reviews, output_root)
        except (OSError, ValueError, RuntimeError):
            workbench.run_jobs = None
        try:
            workbench.operator_studies = OperatorStudyStore(
                {lab.scene_id: lab}, workbench.reviews.db_path.with_name(
                    workbench.reviews.db_path.stem + "-operator-study.sqlite3"))
        except (OSError, ValueError, RuntimeError):
            workbench.operator_studies = None
    from amidst.workbench.phase2_suite import Phase2Suite

    try:
        workbench.phase2_suite = Phase2Suite(workbench, repo)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        workbench.phase2_suite = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Amidst shared desktop workbench")
    parser.add_argument("--port", type=int, default=8016)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--catalog", type=Path,
                        help="Server-owned scene catalog; browser callers cannot supply paths")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--canonical-root", type=Path,
                        help="Read-only historical gallery source; server configuration only")
    args = parser.parse_args()
    repo = args.repo.resolve()
    state = args.state or repo / "data/engineering/local_run/workbench_v1/reviews.sqlite3"
    catalog = load_catalog(repo, manifest_path=args.catalog)
    if not catalog:
        parser.error("No verified scenes; materialize the documented checkpoints.")
    review_keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(state, {
        key: {field: scene.snapshot()[field] for field in review_keys}
        for key, scene in catalog.items()
    })
    from amidst.workbench.source_presentation import (
        load_source_presentation,
        source_presentation_media,
    )
    workbench = Workbench(catalog, reviews,
        presentation=lambda: load_source_presentation(repo),
        presentation_media=lambda ref: source_presentation_media(repo, ref))
    canonical_root = args.canonical_root or (
        repo.parent.parent if repo.parent.name == ".local-worktrees" else repo)
    configure_extensions(workbench, repo, canonical_root=canonical_root)
    app = Application(workbench, repo)
    print(f"Amidst workbench: http://127.0.0.1:{args.port} "
          f"({len(catalog)} verified scenes)", flush=True)
    try:
        with make_server("127.0.0.1", args.port, app, handler_class=QuietHandler) as server:
            server.serve_forever()
    finally:
        if workbench.phase2_suite is not None:
            workbench.phase2_suite.close()
        if workbench.run_jobs is not None:
            workbench.run_jobs.close()
        if workbench.product_bridge is not None and workbench.product_bridge.runtime is not None:
            workbench.product_bridge.runtime.close()
        for bridge in workbench.product_bridges.values():
            close = getattr(bridge, "close", None)
            if callable(close):
                close()


if __name__ == "__main__":
    main()
