"""Server-owned integration of synthetic diagnostics, local Agent and PostgreSQL.

No browser-selected locator, provider, source or SQL is accepted. Optional local
services fail closed; the old immutable source and product freezes remain intact.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

from pydantic import Field, FiniteFloat

from amidst.engineering.access import Mode
from amidst.engineering.registry import ResourceRef, opaque_ref
from amidst.product.operator import OperatorWorkspace
from amidst.product.run import digest
from amidst.product.store import EntityKind, Payload, SQLiteProductStore
from amidst.workbench.product_bridge import BridgeDenied, BridgeRequest


class SuiteRequest(BridgeRequest):
    observation_mode: Mode = "photos_plus_observations"


class SuiteQuery(SuiteRequest):
    camera_id: str = Field(min_length=1, max_length=150, strict=True)
    start: FiniteFloat = Field(ge=0)
    end: FiniteFloat = Field(ge=0)


class SuiteEvent(SuiteRequest):
    event_ref: str = Field(min_length=1, max_length=160, strict=True)


class AgentStart(SuiteRequest):
    message: str = Field(min_length=1, max_length=3000, strict=True)
    camera_refs: tuple[ResourceRef, ...] = Field(min_length=1, max_length=4)
    time_range: tuple[FiniteFloat, FiniteFloat]


class AgentReference(SuiteRequest):
    agent_ref: str = Field(min_length=10, max_length=160, strict=True)


class AgentReply(AgentReference):
    message: str = Field(min_length=1, max_length=3000, strict=True)


class AgentRecover(AgentReference):
    recovery_token: str = Field(min_length=20, max_length=128, strict=True)


SCHEMAS: dict[str, type[SuiteRequest]] = {
    "context": SuiteRequest, "diagnostics": SuiteRequest, "query": SuiteQuery,
    "event": SuiteEvent, "agent_start": AgentStart, "agent_list": SuiteRequest,
    "agent_get": AgentReference, "agent_advance": AgentReference,
    "agent_stop": AgentReference, "agent_resume": AgentReference,
    "agent_reply": AgentReply, "agent_recover": AgentRecover,
    "repair05_diagnostics": SuiteRequest, "repair05_query": SuiteQuery,
}


def migrate_product_store(bridges: list[Any], store: Any) -> dict[str, Any]:
    """Import verified bytes and revisions, then route all product reads/writes to PG."""
    imported, old_repositories = [], {}
    for bridge in bridges:
        for service in bridge.services.values():
            old: SQLiteProductStore = service.repository
            scope = service.scope
            receipt = old.verify_run(scope.run_ref)
            rows = tuple(old.get_record(scope.run_ref, row.kind, row.record_ref)
                         for row in receipt.records)
            if any(row is None for row in rows):
                raise BridgeDenied("POSTGRES_SOURCE_IMPORT_DENIED")
            store.import_records(scope, rows, receipt)
            if store.verify_run(scope.run_ref) != receipt:
                raise BridgeDenied("POSTGRES_EQUIVALENCE_DENIED")
            for frame in service.base.frames.values():
                store.register_media(scope.run_ref, frame.media_ref, {
                    "source_sha256": scope.resource_scope.source_sha256,
                    "sha256": frame.sha256, "size_bytes": frame.size_bytes,
                    "mime_type": frame.media_type, "camera_id": frame.camera_id,
                    "timestamp": frame.timestamp})
            topology = service.base.index.topology(service.base.scope)
            store.ensure_topology(scope.run_ref, topology)
            store.cache_topology(scope.run_ref, digest(topology), digest("scoped-cameras"), {
                "camera_ids": list(topology.camera_ids),
                "topology_complete": topology.topology_complete})
            if hasattr(service, "descriptors"):
                store.ensure_descriptors(scope.run_ref, service.descriptors)
            for kind in ("CASE", "REPORT", "REVIEW"):
                entity_kind: EntityKind = kind
                latest = old.list_latest_revisions(scope.run_ref, entity_kind, limit=500)
                if len(latest) == 500:
                    raise BridgeDenied("POSTGRES_REVISION_IMPORT_LIMIT")
                for entity in latest:
                    for revision in old.list_revisions(scope.run_ref, entity_kind,
                                                       entity.entity_ref):
                        existing = store.get_revision(scope.run_ref, entity_kind,
                                                      entity.entity_ref, revision.version)
                        if existing is None:
                            existing = store.append_revision(scope.run_ref, entity_kind,
                                entity.entity_ref, revision.payload,
                                expected_version=revision.version - 1)
                        # Preserve payload/version/order; backend revision receipts are new.
                        if existing.payload != revision.payload:
                            raise BridgeDenied("POSTGRES_REVISION_IMPORT_DENIED")
            imported.append({"run_ref": scope.run_ref,
                             "receipt_sha256": receipt.receipt_sha256,
                             "record_count": len(rows)})
            old_repositories[id(old)] = old
    # Only switch once every run has a verified equivalent PostgreSQL import.
    for bridge in bridges:
        for service in bridge.services.values():
            service.repository = store
            if hasattr(service, "descriptors"):
                service.appearance = store.appearance_index(service.scope.run_ref)
        bridge.workspaces = {mode: OperatorWorkspace(service, bridge.policy)
                             for mode, service in bridge.services.items()}
        if hasattr(bridge, "repository"):
            bridge.repository = store
    for old in old_repositories.values():
        old.close()
    return {"status": "VERIFIED", "runs": imported, "backend": "POSTGRESQL"}


class Phase2Suite:
    def __init__(self, workbench: Any, repo: Path) -> None:
        self.workbench, self.repo = workbench, repo
        self.research: dict[str, Any] = {}
        self.repair05: dict[str, Any] = {}
        self.agent: Any = None
        self.storage: Any = None
        self.storage_import: dict[str, Any] | None = None
        self.unavailable_reasons: dict[str, str] = {}
        root = repo / "data/engineering/local_run/phase2_abc"
        settings = root / "postgres/settings.json"
        if settings.is_file():
            try:
                from amidst.local_storage import PostgresProductStore, PostgresSettings

                store = PostgresProductStore(PostgresSettings.load(settings))
                bridges = ([workbench.product_bridge] if workbench.product_bridge else []) + list(
                    workbench.product_bridges.values())
                try:
                    self.storage_import = migrate_product_store(bridges, store)
                    self.storage = store
                except BaseException:
                    store.close()
                    raise
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                self.unavailable_reasons["storage"] = "LOCAL_STORAGE_NOT_VERIFIED"
        frozen_root = root / "research/test/certified"
        if frozen_root.is_dir():
            try:
                from amidst.phase2_research.adapter import load_service

                release_path = repo / "data/engineering/phase2_abc_20261013/research_release.json"
                if release_path.is_symlink():
                    raise BridgeDenied("RESEARCH_RELEASE_DENIED")
                release = json.loads(release_path.read_bytes())
                if release["active_variant"] != "baseline":
                    raise BridgeDenied("RESEARCH_RELEASE_DENIED")
                for mode in ("photos_only", "photos_plus_observations"):
                    self.research[mode] = load_service(frozen_root, variant="baseline", mode=mode,
                        expected_manifest_sha256=release["manifest_sha256"],
                        expected_evaluation_sha256=release["evaluation_sha256"])
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                self.research.clear()
                self.unavailable_reasons["research"] = "RESEARCH_RELEASE_NOT_VERIFIED"
        repair_root = repo / "data/engineering/local_run/phase2_repair_0511/research/test/final"
        if repair_root.is_dir():
            try:
                from amidst.phase2_research.repair05_runtime import load_service as load_repair

                release_path = (repo / "data/engineering/phase2_repair_0511_20261013"
                                / "research_runtime_release.json")
                if release_path.is_symlink():
                    raise BridgeDenied("REPAIR05_RELEASE_DENIED")
                release = json.loads(release_path.read_bytes())
                if (release["schema_version"] != "phase2.repair05.runtime-release.v1"
                    or release["active_variant"] != "baseline"
                    or release["acceptance_outcome"] != "REJECTED_RETAIN_BASELINE"):
                    raise BridgeDenied("REPAIR05_RELEASE_DENIED")
                for mode in ("photos_only", "photos_plus_observations"):
                    service = load_repair(repair_root, variant="baseline", mode=mode,
                        expected_manifest_sha256=release["manifest_sha256"],
                        expected_evaluation_sha256=release["evaluation_sha256"],
                        expected_runtime_sha256=release["runtime_sha256"])
                    bound = service.context()["binding"]
                    if (bound["freeze_ref"] != release["modes"][mode]["freeze_ref"]
                        or bound["source_sha256"] != release["source_sha256"]
                        or bound["source_run_id"] != release["source_run_id"]):
                        raise BridgeDenied("REPAIR05_RELEASE_BINDING_DENIED")
                    self.repair05[mode] = service
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                self.repair05.clear()
                self.unavailable_reasons["repair05"] = "REPAIR05_RELEASE_NOT_VERIFIED"
        provider_settings = root / "agent_provider.json"
        if self.storage is not None and provider_settings.is_file():
            try:
                from amidst.local_agent import LocalAgentManager, OllamaProvider

                if provider_settings.is_symlink():
                    raise BridgeDenied("AGENT_CONFIGURATION_DENIED")
                config = json.loads(provider_settings.read_bytes())
                provider = OllamaProvider(**config)
                ledger_path = workbench.reviews.db_path.with_name(
                    workbench.reviews.db_path.stem + "-local-agent.sqlite3")
                self.agent = LocalAgentManager(ledger_path, provider=provider,
                    binding_resolver=self.resolve_binding, executor=self.execute_tool)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                self.unavailable_reasons["agent"] = "LOCAL_AGENT_NOT_VERIFIED"

    def resolve_binding(self, owner_key: str, scene_id: str, mode: Mode) -> Any:
        from amidst.local_agent.contracts import AgentBinding, AgentCamera

        self.workbench._product_access({"session_ref": owner_key, "scene_id": scene_id})
        if self.workbench.operator_studies is not None:
            self.workbench.operator_studies.guard_external(scene_id, owner_key, "suite_agent")
        bridge = self.workbench._product_bridge(scene_id)
        if bridge is None or self.storage is None:
            raise BridgeDenied("LOCAL_AGENT_SOURCE_UNAVAILABLE")
        ctx = bridge.call("context", {"session_ref": owner_key, "scene_id": scene_id})
        if ctx["observation_mode"] != mode:
            raise BridgeDenied("LOCAL_AGENT_MODE_CHANGED")
        product = ctx["product_context"]
        base = product["context"]
        service = bridge.services[mode]
        return AgentBinding(scene_id=scene_id, session_ref=product["session_ref"],
            run_id=base["run_id"], run_ref=product["run_ref"], source_ref=base["source_ref"],
            source_sha256=ctx["source"]["source_sha256"], observation_mode=mode,
            decision_stage=base["decision_stage"], freeze_ref=base["freeze_ref"],
            product_freeze_ref=product["product_freeze_ref"],
            config_sha256=service.scope.config_sha256,
            allowed_tools=tuple(tool for tool in product["allowed_tools"] if tool != "get_media"),
            cameras=tuple(AgentCamera.model_validate({key: camera[key] for key in (
                "camera_id", "camera_ref", "region_ids")}) for camera in ctx["cameras"]),
            time_range=ctx["source"]["time_range"])

    def execute_tool(self, owner_key: str, binding: Any, tool: str,
                     params: dict[str, Any]) -> dict[str, Any]:
        if self.resolve_binding(owner_key, binding.scene_id, binding.observation_mode) != binding:
            raise BridgeDenied("LOCAL_AGENT_BINDING_DENIED")
        bridge = self.workbench._product_bridge(binding.scene_id)
        if bridge is None or self.storage is None:
            raise BridgeDenied("LOCAL_AGENT_SOURCE_UNAVAILABLE")
        topology = bridge.services[binding.observation_mode].base.index.topology(
            bridge.scene.service.scope)
        self.storage.read_topology_cache(
            binding.run_ref, digest(topology), digest("scoped-cameras"))
        result = self.workbench.product_call("tool", {
            "session_ref": owner_key, "scene_id": binding.scene_id, "tool": tool,
            "params": params})
        if not isinstance(result, dict):
            raise BridgeDenied("LOCAL_AGENT_TOOL_RESPONSE_DENIED")
        return result

    def _research_service(self, scene: Any, mode: Mode) -> Any:
        service = self.research.get(mode)
        if service is None:
            raise RuntimeError("RESEARCH_UNAVAILABLE")
        binding = service.context()["binding"]
        if (binding["scene_id"] != scene.scene_id or binding["source_run_id"] != scene.run_id
            or binding["source_sha256"] != scene.source_hash or binding["mode"] != mode):
            raise BridgeDenied("RESEARCH_SOURCE_BINDING_DENIED")
        return service

    def _repair05_service(self, scene: Any, mode: Mode) -> Any:
        service = self.repair05.get(mode)
        if service is None:
            raise RuntimeError("REPAIR05_UNAVAILABLE")
        bound = service.context()["binding"]
        if (bound["scene_id"] != scene.scene_id or bound["source_run_id"] != scene.run_id
            or bound["source_sha256"] != scene.source_hash or bound["mode"] != mode):
            raise BridgeDenied("REPAIR05_SOURCE_BINDING_DENIED")
        return service

    def context(self, request: SuiteRequest, scene: Any) -> dict[str, Any]:
        research = None
        try:
            research = self._research_service(scene, request.observation_mode).context()
        except RuntimeError:
            pass
        except ValueError:
            pass
        agent = None
        repair05 = None
        try:
            repair05 = self._repair05_service(scene, request.observation_mode).context()
        except (RuntimeError, ValueError):
            pass
        if self.agent is not None and self.workbench._product_bridge(scene.scene_id) is not None:
            try:
                agent = self.agent.context(scene_id=scene.scene_id, owner_key=request.session_ref,
                                           mode=request.observation_mode)
            except (ValueError, RuntimeError, OSError):
                agent = None
        return {"schema_version": "workbench.phase2-suite.v1", "scene_id": scene.scene_id,
                "source_run_id": scene.run_id, "source_sha256": scene.source_hash,
                "observation_mode": request.observation_mode,
                "research": research, "repair05": repair05, "agent": agent,
                "storage": None if self.storage is None else self.storage.context(),
                "storage_import": self.storage_import, "origin": "SYNTHETIC",
                "unavailable_reasons": dict(self.unavailable_reasons),
                "formal_phase1_acceptance": False}

    def call(self, action: str, payload: object) -> dict[str, Any]:
        if action not in SCHEMAS:
            raise BridgeDenied("ACTION_DENIED")
        request = SCHEMAS[action].model_validate(payload)
        self.workbench._product_access(payload)
        session = self.workbench._session(request.session_ref)
        scene = self.workbench._scene(session, request.scene_id)
        if self.workbench.operator_studies is not None:
            self.workbench.operator_studies.guard_external(scene.scene_id, request.session_ref,
                                                           "suite_" + action)
        if action == "context":
            bridge = self.workbench._product_bridge(scene.scene_id)
            if bridge is not None:
                bridge.call("context", {"session_ref": request.session_ref,
                    "scene_id": scene.scene_id, "observation_mode": request.observation_mode})
            return self.context(request, scene)
        if action in {"repair05_diagnostics", "repair05_query"}:
            service = self._repair05_service(scene, request.observation_mode)
            if action == "repair05_diagnostics":
                return cast(dict[str, Any], service.diagnostics())
            assert isinstance(request, SuiteQuery)
            if request.end < request.start or request.end - request.start > 120:
                raise BridgeDenied("FINITE_WINDOW_REQUIRED")
            source_start, source_end = scene.snapshot()["time_range"]
            if request.start < source_start or request.end > source_end:
                raise BridgeDenied("REPAIR05_SOURCE_WINDOW_DENIED")
            result = service.query(scene_id=scene.scene_id, run_id=scene.run_id,
                camera_id=request.camera_id, start=request.start, end=request.end)
            self.workbench._issue_media(session, scene.scene_id, {"media_refs": [
                frame["media_ref"] for track in result["tracks"]
                for frame in track["source_frames"]]})
            return cast(dict[str, Any], result)
        if action in {"diagnostics", "query", "event"}:
            service = self._research_service(scene, request.observation_mode)
            if action == "diagnostics":
                return cast(dict[str, Any], service.diagnostics())
            if isinstance(request, SuiteQuery):
                if (not math.isfinite(request.start) or not math.isfinite(request.end)
                    or request.end < request.start or request.end - request.start > 120):
                    raise BridgeDenied("FINITE_WINDOW_REQUIRED")
                source_start, source_end = scene.snapshot()["time_range"]
                if request.start < source_start or request.end > source_end:
                    raise BridgeDenied("RESEARCH_SOURCE_WINDOW_DENIED")
                return cast(dict[str, Any], service.query(scene_id=scene.scene_id,
                    run_id=scene.run_id, camera_id=request.camera_id,
                    start=request.start, end=request.end))
            assert isinstance(request, SuiteEvent)
            detail = service.event(scene_id=scene.scene_id, run_id=scene.run_id,
                                   event_ref=request.event_ref)
            event = detail.get("event", detail)
            self.workbench._issue_media(session, scene.scene_id, event)
            return cast(dict[str, Any], detail)
        if self.agent is None:
            raise RuntimeError("LOCAL_AGENT_UNAVAILABLE")
        if action in {"agent_start", "agent_recover"}:
            bridge = self.workbench._product_bridge(scene.scene_id)
            if bridge is None:
                raise RuntimeError("LOCAL_AGENT_UNAVAILABLE")
            bridge.call("context", {"session_ref": request.session_ref,
                "scene_id": scene.scene_id, "observation_mode": request.observation_mode})
        arguments = {"scene_id": scene.scene_id, "owner_key": request.session_ref,
                     "mode": request.observation_mode}
        if isinstance(request, AgentStart):
            result = self.agent.start(**arguments, message=request.message,
                                     camera_refs=list(request.camera_refs),
                                     time_range=list(request.time_range))
        elif action == "agent_list":
            result = self.agent.list(**arguments)
        else:
            assert isinstance(request, AgentReference)
            arguments["agent_ref"] = request.agent_ref
            if not isinstance(request, AgentRecover):
                case = self.agent.get(scene.scene_id, request.session_ref, request.agent_ref)
                if case["binding"]["observation_mode"] != request.observation_mode:
                    raise BridgeDenied("LOCAL_AGENT_MODE_DENIED")
                arguments.pop("mode")
            if isinstance(request, AgentReply):
                arguments["message"] = request.message
            if isinstance(request, AgentRecover):
                arguments["recovery_token"] = request.recovery_token
            method = action.removeprefix("agent_")
            result = getattr(self.agent, method)(**arguments)
        if isinstance(result, dict) and result.get("agent_ref") and self.storage is not None:
            binding = self.resolve_binding(request.session_ref, scene.scene_id,
                                           request.observation_mode)
            job_ref = opaque_ref("job", digest({"agent_ref": result["agent_ref"]}))
            safe = cast(Payload, {key: result[key] for key in (
                "agent_ref", "state", "binding", "metrics", "answer", "citations",
                "execution_version", "answer_verification", "goal", "refusal", "can_continue")
                if key in result})
            old = self.storage.get_job(binding.run_ref, job_ref)
            if old is None or old["payload"] != safe:
                self.storage.append_job(binding.run_ref, job_ref, safe,
                                        expected_version=0 if old is None else old["version"])
            result["storage_receipt"] = {"backend": "POSTGRESQL", "job_ref": job_ref,
                                         "run_ref": binding.run_ref}
        return cast(dict[str, Any], result)

    def close(self) -> None:
        if self.agent is not None:
            self.agent.close()
        if self.storage is not None:
            self.storage.close()

    def before_manual_study(self, owner_key: str) -> None:
        """Invalidate pending model work before a new manual baseline can begin."""
        if self.agent is None:
            return
        self.agent.stop_all_pending_for_owner(owner_key)
