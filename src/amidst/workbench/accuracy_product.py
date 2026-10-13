"""Bounded investigation over existing accuracy-v2 freezes, without rebuilding them.

Both observation modes use their own verified end-to-end artifacts. Immutable
read models live in memory; only scoped CASE/REPORT/REVIEW revisions and their
binding metadata are persisted. No E1 product, appearance/stitch producer, video
encoder, truth, or evaluation result is used to supply missing v2 capabilities.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field

from amidst.domain.common import DomainModel
from amidst.engineering.access import TOOLS, AccessDenied, Mode, TaskContext
from amidst.engineering.facade import (
    EventRequest,
    MediaRequest,
    ReplayRequest,
    ResolveRequest,
    ToolFailure,
    ToolRequest,
)
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import ResourceRef
from amidst.product.contracts import EventDetail, EventSummary, ObservationDetail, ProductContext
from amidst.product.investigation import (
    EvidenceRecord,
    InvestigationCase,
    InvestigationPolicy,
    InvestigationReport,
)
from amidst.product.operator import OperatorWorkspace
from amidst.product.run import digest
from amidst.product.service import (
    ObservationRequest,
    PagedRequest,
    PageInfo,
    ProductService,
    ProposeRequest,
    ReachRequest,
    response_types,
)
from amidst.product.store import (
    CanonicalRecord,
    EntityKind,
    Payload,
    ProductScope,
    RecordQuery,
    RecordSetReceipt,
    Revision,
    SQLiteProductStore,
)
from amidst.product.timeline import timeline_state
from amidst.research_accuracy.adapter import load_service
from amidst.research_accuracy.run import VERSION, frozen, load
from amidst.workbench.product_bridge import (
    AccuracyBinding,
    BinaryResponse,
    BridgeCapabilities,
    BridgeContext,
    BridgeDenied,
    BridgeRequest,
    ExportRequest,
    IntentRequest,
    ProductBridge,
    SessionLookup,
    SourceMetadata,
)
from amidst.workbench.scenes import SceneAdapter

ADAPTER_VERSION = "accuracy.investigation.v1"
MODES: tuple[Mode, ...] = ("photos_only", "photos_plus_observations")
SupportState = Literal["SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES"]


class AccuracyEventSummary(EventSummary):
    experiment_id: str = Field(min_length=1, max_length=200)
    variant: Literal["end_to_end"]
    support_state: SupportState


class AccuracyEventDetail(EventDetail, AccuracyEventSummary):
    pass


class AccuracyEventPage(DomainModel):
    scope: TaskContext
    items: tuple[AccuracyEventSummary, ...]
    retrieval: PageInfo


class AccuracySummaryResponse(AccuracyEventSummary):
    scope: TaskContext


class AccuracyDetailResponse(AccuracyEventDetail):
    scope: TaskContext


class AccuracyEventState(DomainModel):
    event_ref: ResourceRef
    support_state: SupportState


class AccuracyEvidenceSupplement(DomainModel):
    schema_version: Literal["accuracy.investigation.evidence.v1"] = (
        "accuracy.investigation.evidence.v1")
    binding: AccuracyBinding
    record_set_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    events: tuple[AccuracyEventState, ...] = Field(max_length=4096)
    source_authority_changed: Literal[False] = False
    confirmed_identity_or_behavior: Literal[False] = False
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AccuracyCaseRepository(SQLiteProductStore):
    """Memory-only canonical records, with a separate durable revision ledger."""

    def __init__(self, ledger_path: Path, scopes: tuple[ProductScope, ...]) -> None:
        super().__init__(Path(":memory:"))
        try:
            self.ledger = SQLiteProductStore(ledger_path)
            allowed = {scope.run_ref for scope in scopes}
            if any(scope.run_ref not in allowed or self.ledger.verify_run(scope.run_ref).records
                   for scope in self.ledger.list_runs()):
                raise ValueError("ACCURACY_LEDGER_SCOPE_MISMATCH")
            for scope in scopes:
                self.ledger.import_records(scope, (), RecordSetReceipt.create(scope, ()))
        except BaseException:
            self.close()
            raise

    def append_revision(self, run_ref: str, kind: EntityKind, entity_ref: str, payload: Payload,
                        *, expected_version: int) -> Revision:
        return self.ledger.append_revision(run_ref, kind, entity_ref, payload,
                                           expected_version=expected_version)

    def get_revision(self, run_ref: str, kind: EntityKind, entity_ref: str,
                     version: int | None = None) -> Revision | None:
        return self.ledger.get_revision(run_ref, kind, entity_ref, version)

    def list_revisions(self, run_ref: str, kind: EntityKind,
                       entity_ref: str) -> tuple[Revision, ...]:
        return self.ledger.list_revisions(run_ref, kind, entity_ref)

    def list_latest_revisions(self, run_ref: str, kind: EntityKind,
                              *, limit: int = 101) -> tuple[Revision, ...]:
        return self.ledger.list_latest_revisions(run_ref, kind, limit=limit)

    def close(self) -> None:
        super().close()
        if hasattr(self, "ledger"):
            self.ledger.close()


class AccuracyProductService(ProductService):
    """Reuse existing scoped investigation tools, with explicit v2 event DTOs.

The inherited appearance/stitch methods are never exposed. No descriptor or
stitch bundle is manufactured merely to satisfy the legacy ProductRuntime.
"""

    def __init__(self, base: LocalPilotService, repository: AccuracyCaseRepository,
                 scope: ProductScope) -> None:
        from amidst.engineering.registry import opaque_ref

        self.base, self.repository, self.scope = base, repository, scope
        self.product_freeze_ref = opaque_ref("freeze", scope.freeze_sha256)
        self.logs = []
        self._events_by_track = {}
        self._tracks = {row["local_track_ref"] for row in base.observations.values()}
        for ref, row in base.events.items():
            event = AccuracyEventDetail.model_validate(row)
            for track in event.local_track_refs:
                self._events_by_track.setdefault(track, []).append(ref)

    def context(self) -> ProductContext:
        from amidst.engineering.registry import opaque_ref

        return ProductContext(
            session_ref=self.base.guard.session_ref, run_ref=self.scope.run_ref,
            context=self.base.guard.context(tuple(self.base.cameras)),
            product_freeze_ref=self.product_freeze_ref,
            operator_ref=opaque_ref("operator", self.scope.run_ref, ADAPTER_VERSION),
            allowed_tools=(*TOOLS, "get_observation_detail", "query_reachable_cameras",
                           "propose_feasible_trajectories"),
        )

    def _seed_tracks(self, refs: tuple[str, ...]) -> set[str]:
        selected = set()
        for ref in refs:
            if ref in self._tracks:
                selected.add(ref)
            else:
                record = self.repository.get_record(self.scope.run_ref, "OBSERVATION", ref)
                if record is None:
                    raise ToolFailure("REFERENCE_DENIED")
                selected.add(ObservationDetail.model_validate(record.payload).local_track_ref)
        return selected

    def call(self, tool: str, payload: object) -> dict[str, Any]:
        schemas: dict[str, type[ToolRequest]] = {
            "resolve_place": ResolveRequest, "list_cameras": ToolRequest,
            "query_observations": PagedRequest, "query_events": PagedRequest,
            "get_event_summary": EventRequest, "get_event_detail": EventRequest,
            "get_media": MediaRequest, "get_replay": ReplayRequest,
            "get_observation_detail": ObservationRequest,
            "query_reachable_cameras": ReachRequest,
            "propose_feasible_trajectories": ProposeRequest,
        }
        if tool not in schemas:
            raise ToolFailure("TOOL_UNAVAILABLE")
        types = response_types() | {
            "query_events": AccuracyEventPage,
            "propose_feasible_trajectories": AccuracyEventPage,
            "get_event_summary": AccuracySummaryResponse,
            "get_event_detail": AccuracyDetailResponse,
        }
        try:
            request = schemas[tool].model_validate(payload)
            self._guard(request, tool)
            response = types[tool].model_validate(self._invoke(tool, request)).model_dump(
                mode="json")
        except (ToolFailure, AccessDenied) as error:
            raise ToolFailure(str(error)) from None
        except (ValueError, KeyError, TypeError, OSError):
            raise ToolFailure("INVALID_OR_UNAVAILABLE") from None
        self.logs.append({"tool": tool, "stage": "RESULTS", "status": "OK",
                          "response_sha256": digest(response)})
        return response

    def _invoke(self, tool: str, request: ToolRequest) -> dict[str, Any]:
        context = self.base.guard.context(tuple(self.base.cameras))
        if tool in {"query_events", "propose_feasible_trajectories"}:
            assert isinstance(request, PagedRequest)
            camera_id = self._camera(request.camera_ref)
            if camera_id is None and request.region_id is None:
                raise ToolFailure("LOCAL_ANCHOR_REQUIRED")
            if request.region_id is not None and request.region_id not in {
                region for camera in self.base.cameras.values() for region in camera.region_ids
            }:
                raise ToolFailure("REFERENCE_DENIED")
            selected_refs = None
            if isinstance(request, ProposeRequest) and request.seed_refs:
                selected_refs = tuple(sorted({ref for track in self._seed_tracks(request.seed_refs)
                                             for ref in self._events_by_track.get(track, ())}))
            page = self.repository.query_records(RecordQuery(
                run_ref=self.scope.run_ref, kind="EVENT", camera_id=camera_id,
                time_range=request.time_range, region_id=request.region_id,
                limit=request.limit, cursor=request.cursor, record_refs=selected_refs,
            ))
            items = tuple(self._accuracy_summary(AccuracyEventDetail.model_validate(row.payload))
                          for row in page.records)
            return AccuracyEventPage(scope=context, items=items, retrieval=PageInfo(
                records_read=len(page.records), index_entries_touched=len(page.records),
                time_range=request.time_range, truncated=not page.query_complete,
                next_cursor=page.next_cursor,
                record_set_receipt_sha256=page.record_set_receipt_sha256,
            )).model_dump(mode="json")
        if tool in {"get_event_summary", "get_event_detail", "get_replay"}:
            assert isinstance(request, EventRequest)
            record = self.repository.get_record(self.scope.run_ref, "EVENT", request.event_ref)
            if record is None:
                raise ToolFailure("REFERENCE_DENIED")
            event = AccuracyEventDetail.model_validate(record.payload)
            if tool == "get_event_summary":
                return {"scope": context.model_dump(mode="json"),
                        **self._accuracy_summary(event).model_dump(mode="json")}
            if tool == "get_event_detail":
                return {"scope": context.model_dump(mode="json"), **event.model_dump(mode="json")}
            assert isinstance(request, ReplayRequest)
            if not event.time_range[0] <= request.timestamp <= event.time_range[1]:
                raise ToolFailure("TIME_OUTSIDE_EVENT")
            return timeline_state(self.scope.run_ref, request.timestamp,
                                  tuple(self.base.frames.values()), (event,)).model_dump(
                                      mode="json")
        return super()._invoke(tool, request)

    @staticmethod
    def _accuracy_summary(event: AccuracyEventDetail) -> AccuracyEventSummary:
        return AccuracyEventSummary.model_validate(event.model_dump(mode="json", exclude={
            "projected_path", "candidates", "trajectories"}))


class AccuracyProductBridge(ProductBridge):
    """ProductBridge-compatible transport over an independent bounded v2 adapter."""

    def __init__(self, output: Path, scene: SceneAdapter, session_lookup: SessionLookup,
                 ledger_path: Path, policy: InvestigationPolicy | None = None) -> None:
        output = output.resolve()
        package, registry, manifest, _ = load(output)
        snapshot = scene.snapshot()
        if (snapshot.get("evidence_level") != "E1_FROZEN_ACCURACY_V2_RGB"
            or snapshot.get("experiment_id") != manifest["experiment_id"]
            or snapshot.get("variant") != "end_to_end"
            or snapshot.get("experiment_config_sha256") != manifest["config_sha256"]
            or scene.service.guard.binding.registry_version != VERSION):
            raise BridgeDenied("ACCURACY_SCOPE_MISMATCH")
        source = Path(manifest["source_locator"]).resolve()
        destination = ledger_path.resolve()
        if (ledger_path.is_symlink() or destination.is_relative_to(output)
            or destination.is_relative_to(source)):
            raise BridgeDenied("ACCURACY_LEDGER_LOCATION_DENIED")
        self.runtime = None
        self.scene, self.session_lookup = scene, session_lookup
        self.policy = InvestigationPolicy() if policy is None else (
            InvestigationPolicy.model_validate_json(policy.model_dump_json()))
        self.capabilities = BridgeCapabilities(appearance=False, stitch=False, videos=False,
                                              supported_tasks=("TRACE", "BEHAVIOR"))
        self.available_modes = MODES
        self._modes = {}
        self._bindings = {}
        self._scene_binding = digest(scene.service.guard.binding)
        bases = {mode: load_service(output, variant="end_to_end", mode=mode) for mode in MODES}
        self.accuracy_bindings: dict[Mode, AccuracyBinding] = {}
        scopes = []
        for mode, base in bases.items():
            state = frozen(output, "end_to_end", mode, manifest, package, registry)
            binding = base.guard.binding
            if (base.guard.stage != "RESULTS" or binding != state.receipt.binding
                or base.scope != scene.service.scope
                or digest(binding.model_dump(exclude={"observation_mode"})) != digest(
                    scene.service.guard.binding.model_dump(exclude={"observation_mode"}))
                or digest(base.cameras) != digest(scene.service.cameras)
                or self._frames_hash(base.frames) != self._frame_hash_scene()
                or not base.frames):
                raise BridgeDenied("ACCURACY_SCOPE_MISMATCH")
            self._bindings[mode] = digest(binding)
            self.accuracy_bindings[mode] = AccuracyBinding(
                experiment_id=manifest["experiment_id"],
                experiment_config_sha256=manifest["config_sha256"],
                mode_config_sha256=binding.config_sha256,
                original_freeze_ref="freeze-" + state.receipt.receipt_sha256,
                source_run_id=manifest["source_run_id"],
            )
            scopes.append(ProductScope(
                resource_scope=base.scope, observation_mode=mode,
                dataset_sha256=binding.dataset_sha256, config_sha256=binding.config_sha256,
                producer_sha256=binding.producer_sha256, registry_sha256=binding.registry_sha256,
                media_sha256=binding.media_sha256, inference_sha256=state.receipt.inference_sha256,
                freeze_sha256=digest({"adapter_version": ADAPTER_VERSION,
                    "binding": self.accuracy_bindings[mode].model_dump(mode="json"),
                    "source_receipt_sha256": state.receipt.receipt_sha256,
                    "observations": base.observations, "events": base.events}),
            ))
        self.repository = AccuracyCaseRepository(destination, tuple(scopes))
        self.record_receipts: dict[Mode, str] = {}
        try:
            self.services = {}
            for scope in scopes:
                base = bases[scope.observation_mode]
                records = []
                for kind, rows, model, ref_key in (
                    ("OBSERVATION", base.observations, ObservationDetail, "observation_ref"),
                    ("EVENT", base.events, AccuracyEventDetail, "event_ref"),
                ):
                    for row in rows.values():
                        raw = model.model_validate(row).model_dump(mode="json")
                        records.append(CanonicalRecord.create(
                            run_ref=scope.run_ref, kind=cast(Literal["OBSERVATION", "EVENT"], kind),
                            record_ref=raw[ref_key], camera_ids=tuple(raw["camera_ids"]),
                            region_ids=tuple(raw["region_ids"]),
                            time_range=tuple(raw["time_range"]), payload=cast(Payload, raw),
                        ))
                rows_tuple = tuple(records)
                self.repository.import_records(scope, rows_tuple,
                                               RecordSetReceipt.create(scope, rows_tuple))
                self.record_receipts[scope.observation_mode] = self.repository.verify_run(
                    scope.run_ref).receipt_sha256
                self.services[scope.observation_mode] = AccuracyProductService(
                    base, self.repository, scope)
            self.workspaces = {mode: OperatorWorkspace(service, self.policy)
                               for mode, service in self.services.items()}
            location = next(model for model in registry.models
                            if model.scope == scene.service.scope)
            self.clock, self.coordinates = location.clock, location.coordinates
            frames = tuple(scene.service.frames.values())
            resource = scene.service.scope
            original = json_source_metadata(source)
            self.source = SourceMetadata(source_ref=scene.service.guard.binding.source_ref,
                source_sha256=resource.source_sha256, model_id=resource.model_id,
                model_revision=resource.model_revision, run_id=resource.run_id,
                clock_id=resource.clock_id,
                camera_count=len(scene.service.cameras), frame_count=len(frames),
                time_range=(min(frame.timestamp for frame in frames),
                            max(frame.timestamp for frame in frames)), source_rgb_rate_hz=original)
        except BaseException:
            self.repository.close()
            raise

    def _context(self, service: ProductService) -> BridgeContext:
        context = super()._context(service)
        return context.model_copy(update={
            "accuracy_binding": self.accuracy_bindings[service.scope.observation_mode]})

    def _invoke(self, action: str, request: BridgeRequest, service: ProductService,
                workspace: OperatorWorkspace) -> Any:
        if isinstance(request, IntentRequest):
            task = request.intent.task
            if task is None and request.intent.text is not None:
                text = request.intent.text.strip().casefold()
                task = "TRACE" if text in {"trace", "trace target", "追查", "追查目標"} else (
                    "BEHAVIOR" if text in {"behavior", "inspect behavior", "行為", "查詢行為"}
                    else None)
            if task not in self.capabilities.supported_tasks:
                raise BridgeDenied("TASK_UNAVAILABLE")
        result = super()._invoke(action, request, service, workspace)
        if isinstance(result, (InvestigationCase, InvestigationReport)):
            return result.model_dump(mode="json") | {"accuracy_evidence":
                self._evidence_supplement(service, result.evidence).model_dump(mode="json")}
        if isinstance(request, ExportRequest) and isinstance(result, BinaryResponse):
            record = service.repository.get_revision(service.scope.run_ref, "REPORT",
                                                      request.report_ref)
            if record is None:
                raise BridgeDenied("REPORT_UNAVAILABLE")
            report = InvestigationReport.model_validate(record.payload)
            supplement = self._evidence_supplement(service, report.evidence)
            rows = "".join("<tr><td>" + escape(item.event_ref) + "</td><td>" +
                           escape(item.support_state) + "</td></tr>" for item in supplement.events)
            section = ("<h2>v2 來源證據狀態</h2><p>SUPPORTED／UNKNOWN／GAP_ALTERNATIVES"
                " 是凍結來源的證據狀態；未確認人物或行為，未變更來源權威。</p>"
                "<table><tr><th>Event reference</th><th>Source evidence state</th></tr>" + rows +
                "</table><p>來源補充 hash：<code>" + supplement.content_sha256 + "</code></p>")
            body = result.body.decode().replace("</html>", section + "</html>")
            return BinaryResponse(result.status, result.mime_type, result.headers, body.encode())
        return result

    def _evidence_supplement(self, service: ProductService,
                             evidence: tuple[EvidenceRecord, ...]) -> AccuracyEvidenceSupplement:
        states = []
        for item in evidence:
            if item.kind != "EVENT":
                continue
            row = service.repository.get_record(service.scope.run_ref, "EVENT", item.record_ref)
            if row is None:
                raise BridgeDenied("REFERENCE_DENIED")
            event = AccuracyEventDetail.model_validate(row.payload)
            states.append(AccuracyEventState(event_ref=event.event_ref,
                                             support_state=event.support_state))
        payload = {"schema_version": "accuracy.investigation.evidence.v1",
            "binding": self.accuracy_bindings[service.scope.observation_mode].model_dump(
                mode="json"),
            "record_set_receipt_sha256": self.record_receipts[service.scope.observation_mode],
            "events": [item.model_dump(mode="json") for item in states],
            "source_authority_changed": False, "confirmed_identity_or_behavior": False}
        return AccuracyEvidenceSupplement.model_validate(payload | {"content_sha256":
                                                                   digest(payload)})

    def _timeline_events(self, service: ProductService, refs: tuple[str, ...]) -> tuple[
        EventDetail, ...
    ]:
        return tuple(AccuracyEventDetail.model_validate(service.base.events[ref]) for ref in refs)

    def close(self) -> None:
        self.repository.close()


def json_source_metadata(source: Path) -> float:
    """Read only the source sampling declaration already covered by its loader."""
    import json
    import math

    fps = json.loads((source / "package.json").read_bytes())["fps"]
    if isinstance(fps, bool) or not isinstance(fps, (float, int)) or (
        not math.isfinite(fps) or fps <= 0
    ):
        raise BridgeDenied("ACCURACY_SCOPE_MISMATCH")
    return float(fps)


def load_accuracy_product_bridge(output: Path, scene: SceneAdapter,
                                 session_lookup: SessionLookup, ledger_path: Path) -> ProductBridge:
    """Load both existing v2 freezes; persist only an isolated investigation ledger."""
    try:
        return AccuracyProductBridge(output, scene, session_lookup, ledger_path)
    except BridgeDenied:
        raise
    except (ValueError, KeyError, TypeError, OSError, StopIteration):
        raise BridgeDenied("ACCURACY_INVESTIGATION_UNAVAILABLE") from None
