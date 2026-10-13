"""Required real local PostgreSQL tests. Missing service is a failure, not a skip."""

import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import SecretStr, ValidationError

from amidst.engineering.access import digest
from amidst.engineering.local_index import CameraLink, ScopedTopology
from amidst.engineering.registry import ResourceScope, opaque_ref
from amidst.local_storage.bootstrap import ROOT, SETTINGS_PATH, backup, restore
from amidst.local_storage.postgres import PostgresProductStore, PostgresSettings
from amidst.product.appearance import AppearanceIndex, DescriptorBundle
from amidst.product.run import ProductManifest
from amidst.product.store import (
    CanonicalRecord,
    ProductScope,
    RecordQuery,
    RecordSetReceipt,
    SQLiteProductStore,
    StoreConflict,
    StoreError,
    StoreIntegrityError,
)


@pytest.fixture
def settings():
    original = PostgresSettings.load(SETTINGS_PATH)
    return PostgresSettings(dsn=original.dsn, schema_name="amidst_test_" + uuid.uuid4().hex[:16])


@pytest.fixture
def store(settings):
    value = PostgresProductStore(settings)
    yield value
    value.close()


def scope(run_id="fixture-1"):
    resource = ResourceScope(
        place_id="fixture-lab",
        model_id="storage-fixture",
        model_revision="1",
        run_id=run_id,
        source_id="synthetic-storage-fixture",
        source_sha256="a" * 64,
        spatial_context_id="configured-fixture",
        spatial_context_sha256="b" * 64,
        clock_id="fixture-clock",
    )
    return ProductScope.model_validate_json(
        json.dumps(
            {
                "resource_scope": resource.model_dump(mode="json"),
                "observation_mode": "photos_only",
                **{
                    key + "_sha256": "c" * 64
                    for key in (
                        "dataset",
                        "config",
                        "producer",
                        "registry",
                        "media",
                        "inference",
                        "freeze",
                    )
                },
            }
        )
    )


def rows(binding):
    return tuple(
        CanonicalRecord.create(
            run_ref=binding.run_ref,
            kind="EVENT" if i % 2 else "OBSERVATION",
            record_ref=opaque_ref("record", str(i)),
            time_range=(float(i // 3), float(i // 3) + 1),
            camera_ids=("CAM_A" if i % 3 else "CAM_B",),
            region_ids=("west" if i % 4 else "east",),
            payload={
                "status": "PROVISIONAL",
                "complete": False,
                "alternatives": [{"rank": 2}, {"rank": 1}],
                "fixture_index": i,
            },
        )
        for i in range(32)
    )


def put(store, binding):
    records = rows(binding)
    receipt = RecordSetReceipt.create(binding, records)
    return store.import_records(binding, records, receipt)


def pages(store, query):
    collected = []
    while True:
        result = store.query_records(query)
        collected.extend(result.records)
        if result.next_cursor is None:
            return collected
        query = RecordQuery.model_validate(query.model_dump() | {"cursor": result.next_cursor})


def test_actual_postgres_matches_sqlite_bounded_queries_and_restart(
    store, settings, tmp_path, record_property
):
    binding = scope()
    put(store, binding)
    with SQLiteProductStore(tmp_path / "comparison.sqlite") as sqlite:
        put(sqlite, binding)
        for kind in ("OBSERVATION", "EVENT"):
            for camera in (None, "CAM_A", "CAM_B", "MISSING"):
                for region in (None, "west", "east", "MISSING"):
                    query = RecordQuery(
                        run_ref=binding.run_ref,
                        kind=kind,
                        time_range=(2, 7),
                        camera_id=camera,
                        region_id=region,
                        limit=3,
                    )
                    assert pages(store, query) == pages(sqlite, query)
        query = RecordQuery(
            run_ref=binding.run_ref,
            kind="EVENT",
            time_range=(0, 20),
            record_refs=tuple(r.record_ref for r in rows(binding)[1:15:2]),
            limit=2,
        )
        assert pages(store, query) == pages(sqlite, query)
        assert not pages(store, query.model_copy(update={"record_refs": ()}))
    with PostgresProductStore(settings) as reopened:
        assert not put(reopened, binding).inserted
        assert reopened.verify_run(binding.run_ref) == store.verify_run(binding.run_ref)
        assert reopened.context()["backend"] == "POSTGRESQL"
    record_property("query_equivalence_cases", 33)


def test_scope_cursor_and_source_isolation(store):
    a, b = scope("first"), scope("second")
    put(store, a)
    put(store, b)
    query = RecordQuery(run_ref=a.run_ref, kind="EVENT", time_range=(0, 30), limit=2)
    page = store.query_records(query)
    with pytest.raises(StoreError, match="CURSOR"):
        store.query_records(
            query.model_copy(update={"run_ref": b.run_ref, "cursor": page.next_cursor})
        )
    changed = rows(a)[0].model_copy(update={"run_ref": b.run_ref})
    with pytest.raises(StoreConflict):
        RecordSetReceipt.create(a, (changed,))
    assert store.get_record(a.run_ref, rows(a)[0].kind, rows(a)[0].record_ref).run_ref == a.run_ref


def test_real_independent_connections_optimistic_case_conflict(store, settings, record_property):
    binding = scope()
    put(store, binding)
    barrier = Barrier(4)

    def mutate(i):
        with PostgresProductStore(settings) as client:
            barrier.wait(timeout=10)
            try:
                client.append_revision(
                    binding.run_ref,
                    "CASE",
                    opaque_ref("case", "conflict"),
                    {"writer": i},
                    expected_version=0,
                )
                return "COMMITTED"
            except StoreConflict:
                return "CONFLICT"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(mutate, range(4)))
    assert results.count("COMMITTED") == 1 and results.count("CONFLICT") == 3
    assert len(store.list_revisions(binding.run_ref, "CASE", opaque_ref("case", "conflict"))) == 1
    record_property("writers", 4)
    record_property("committed", results.count("COMMITTED"))
    record_property("conflicts", results.count("CONFLICT"))


def test_same_store_background_and_http_transaction_serialization(store, record_property):
    binding = scope()
    put(store, binding)
    barrier = Barrier(4)

    def mutate(i):
        barrier.wait(timeout=10)
        try:
            store.append_revision(
                binding.run_ref,
                "REPORT",
                opaque_ref("report", "shared"),
                {"writer": i},
                expected_version=0,
            )
            return "COMMITTED"
        except StoreConflict:
            return "CONFLICT"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(mutate, range(4)))
    assert results.count("COMMITTED") == 1 and results.count("CONFLICT") == 3
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: pages(
                    store,
                    RecordQuery(
                        run_ref=binding.run_ref, kind="OBSERVATION", time_range=(0, 20), limit=2
                    ),
                ),
                range(4),
            )
        )
    assert all(result == results[0] for result in results)
    record_property("same_instance_writers", 4)
    record_property("same_instance_readers", 4)


def test_jobs_chain_and_cross_run_refs(store):
    a, b = scope("a"), scope("b")
    put(store, a)
    put(store, b)
    ref = opaque_ref("job", "one")
    first = store.append_job(a.run_ref, ref, {"state": "QUEUED"}, expected_version=0)
    second = store.append_job(a.run_ref, ref, {"state": "COMPLETED"}, expected_version=1)
    assert second["previous_sha256"] == first["revision_sha256"]
    assert store.get_job(b.run_ref, ref) is None
    assert store.get_job(a.run_ref, ref) == second
    assert store.list_jobs(a.run_ref, limit=1) == [second]
    with pytest.raises(StoreConflict):
        store.append_job(a.run_ref, ref, {"state": "FAILED"}, expected_version=0)
    with pytest.raises(StoreError):
        store.list_jobs(a.run_ref, limit=101)


def test_actual_frozen_descriptor_index_versions_and_equivalent_search(store):
    # Read certified existing descriptors only; no RGB producer or model rerun.
    root = SETTINGS_PATH.parents[4] / "product/local_run/operator_v2"
    manifest = ProductManifest.model_validate_json((root / "product_manifest.json").read_bytes())
    mode = manifest.modes[0]
    bundle = DescriptorBundle.model_validate_json(
        (root / f"appearance_{mode.mode}.json").read_bytes()
    )
    store.import_records(mode.scope, (), RecordSetReceipt.create(mode.scope, ()))
    installed = store.install_descriptors(mode.scope.run_ref, bundle, expected_version=0)
    assert store.load_descriptors(mode.scope.run_ref) == bundle
    assert store.ensure_descriptors(mode.scope.run_ref, bundle)["reused"]
    assert store.ensure_descriptors(mode.scope.run_ref, bundle)["version"] == 1
    query = next(track for track in bundle.track_descriptors if track.vector is not None)
    allowed = [track.track_ref for track in bundle.track_descriptors]
    kwargs = {
        "scope": bundle.scope,
        "allowed_track_refs": allowed,
        "camera_id": None,
        "time_range": (0, 30),
        "top_k": 5,
    }
    assert store.appearance_index(mode.scope.run_ref).search(query.track_ref, **kwargs) == (
        AppearanceIndex(bundle).search(query.track_ref, **kwargs)
    )
    changed = DescriptorBundle.model_validate(
        bundle.model_dump() | {"complete": not bundle.complete}
    )
    replacement = store.install_descriptors(mode.scope.run_ref, changed, expected_version=1)
    assert replacement["index_ref"] != installed["index_ref"] and replacement["version"] == 2
    assert store.load_descriptors(mode.scope.run_ref, installed["index_ref"]) == bundle
    with pytest.raises(StoreConflict, match="DESCRIPTOR_RESTART_BINDING_CONFLICT"):
        store.ensure_descriptors(mode.scope.run_ref, bundle)
    with pytest.raises(StoreConflict):
        store.install_descriptors(mode.scope.run_ref, bundle, expected_version=1)


def test_media_reference_metadata_no_copy_and_topology_invalidation(store):
    binding = scope()
    put(store, binding)
    ref = opaque_ref("media", "one")
    media = {
        "source_sha256": "a" * 64,
        "sha256": "d" * 64,
        "size_bytes": 17,
        "mime_type": "image/png",
        "camera_id": "CAM_A",
        "timestamp": 0.0,
    }
    store.register_media(binding.run_ref, ref, media)
    assert store.get_media_binding(binding.run_ref, ref) == media
    with pytest.raises(StoreConflict):
        store.register_media(binding.run_ref, ref, media | {"sha256": "e" * 64})
    with pytest.raises(ValueError):
        store.register_media(binding.run_ref, ref, media | {"private_path": "forbidden"})
    topology = ScopedTopology(scope=binding.resource_scope, camera_ids=("CAM_A", "CAM_B"))
    first = store.install_topology(binding.run_ref, topology, expected_version=0)
    assert store.ensure_topology(binding.run_ref, topology)["version"] == 1
    assert store.ensure_topology(binding.run_ref, topology)["reused"]
    query = digest({"camera": "CAM_A"})
    store.cache_topology(
        binding.run_ref, first["topology_sha256"], query, {"camera_ids": ["CAM_A"]}
    )
    assert store.read_topology_cache(binding.run_ref, first["topology_sha256"], query) == {
        "camera_ids": ["CAM_A"]
    }
    changed = ScopedTopology(
        scope=binding.resource_scope,
        camera_ids=("CAM_A", "CAM_B"),
        camera_links=(CameraLink(from_camera_id="CAM_A", to_camera_id="CAM_B"),),
    )
    replacement = store.install_topology(binding.run_ref, changed, expected_version=1)
    assert replacement["previous_cache_invalidated"]
    with pytest.raises(StoreConflict, match="TOPOLOGY_RESTART_BINDING_CONFLICT"):
        store.ensure_topology(binding.run_ref, topology)
    with pytest.raises(StoreError, match="TOPOLOGY_CACHE_STALE"):
        store.read_topology_cache(binding.run_ref, first["topology_sha256"], query)
    assert store.read_topology_cache(binding.run_ref, replacement["topology_sha256"], query) is None


def test_real_pg_dump_restore_preserves_full_content_and_query(store, settings, record_property):
    binding = scope()
    put(store, binding)
    store.append_revision(
        binding.run_ref,
        "CASE",
        opaque_ref("case", "backup"),
        {"state": "COMPLETED"},
        expected_version=0,
    )
    store.append_job(
        binding.run_ref, opaque_ref("job", "backup"), {"state": "COMPLETED"}, expected_version=0
    )
    media = {
        "source_sha256": "a" * 64,
        "sha256": "d" * 64,
        "size_bytes": 17,
        "mime_type": "image/png",
        "camera_id": "CAM_A",
        "timestamp": 0.0,
    }
    store.register_media(binding.run_ref, opaque_ref("media", "backup"), media)
    topology = ScopedTopology(scope=binding.resource_scope, camera_ids=("CAM_A",))
    top = store.install_topology(binding.run_ref, topology, expected_version=0)
    store.cache_topology(
        binding.run_ref, top["topology_sha256"], digest("query"), {"complete": False}
    )
    root = SETTINGS_PATH.parents[4] / "product/local_run/operator_v2"
    manifest = ProductManifest.model_validate_json((root / "product_manifest.json").read_bytes())
    mode = manifest.modes[0]
    bundle = DescriptorBundle.model_validate_json(
        (root / f"appearance_{mode.mode}.json").read_bytes()
    )
    store.import_records(mode.scope, (), RecordSetReceipt.create(mode.scope, ()))
    store.install_descriptors(mode.scope.run_ref, bundle, expected_version=0)
    before = store.content_manifest()
    path = ROOT / "backups" / (uuid.uuid4().hex + ".dump")
    backup(settings, path)
    assert path.is_file() and path.stat().st_size > 0
    restored = restore(settings, path, database="amidst_restore_" + uuid.uuid4().hex[:16])
    with PostgresProductStore(restored) as target:
        assert target.content_manifest() == before
        query = RecordQuery(run_ref=binding.run_ref, kind="EVENT", time_range=(0, 20), limit=3)
        assert pages(target, query) == pages(store, query)
        assert target.load_descriptors(mode.scope.run_ref) == bundle
    record_property("backup_sha256", hashlib.sha256(path.read_bytes()).hexdigest())
    record_property("restored_content_sha256", before["content_sha256"])
    record_property("restored_record_count", before["counts"]["records"])
    record_property("restored_descriptor_indexes", before["counts"]["descriptor_indexes"])


def test_rollback_and_append_only_server_enforcement(store):
    binding = scope()
    put(store, binding)
    before = store.content_manifest()
    with pytest.raises(StoreError):
        with store._transaction():
            store._db.execute(
                "UPDATE records SET start_time=100 WHERE run_ref=?", (binding.run_ref,)
            )
    assert store.content_manifest() == before
    with pytest.raises(StoreError):
        with store._transaction():
            store._db.execute(
                "INSERT INTO media_bindings VALUES (?,?,?,?)",
                (binding.run_ref, opaque_ref("media", "rollback"), "{}", "d" * 64),
            )
            store._db.execute("SELECT deliberately_missing_column FROM runs")
    assert store.content_manifest() == before


@pytest.mark.parametrize(
    "dsn",
    [
        "host=remote.example dbname=amidst_abc",
        "host=127.0.0.1 dbname=unrelated",
        "host=127.0.0.1 hostaddr=8.8.8.8 dbname=amidst_abc",
        "service=other dbname=amidst_abc",
    ],
)
def test_no_external_or_unrelated_database_selection(dsn):
    with pytest.raises(ValidationError):
        PostgresSettings(dsn=SecretStr(dsn))


def test_wrong_migration_hash_rejected_preserving_database(store, settings):
    store._connection.execute(
        "UPDATE schema_migrations SET source_sha256=%s WHERE version=1", ("0" * 64,)
    )
    with pytest.raises(StoreIntegrityError, match="POSTGRES_MIGRATION_CHANGED"):
        PostgresProductStore(settings)


def test_no_fake_sqlite_fallback_on_unavailable_postgres():
    settings = PostgresSettings(
        dsn=SecretStr(
            "host=/private/tmp/amidst-pg-not-running "
            "dbname=amidst_unavailable user=amidst_local port=55439"
        ),
        connect_timeout=1,
    )
    with pytest.raises(StoreError, match="POSTGRES_UNAVAILABLE"):
        PostgresProductStore(settings)
