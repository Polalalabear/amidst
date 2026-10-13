"""PostgreSQL implementation of existing frozen ProductStore contracts.

The compatibility layer reuses canonical validation, cursor signatures and
receipt/revision semantics from ProductStore. Every statement executes through
psycopg on PostgreSQL. There is no SQLite connection or fallback, and no caller
SQL endpoint. Registered media bytes remain in their original read-only store.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Literal, Self

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from pydantic import Field, SecretStr, model_validator

from amidst.domain.common import Timestamp
from amidst.engineering.access import digest
from amidst.engineering.local_index import ScopedTopology
from amidst.engineering.registry import RegistryModel, Sha256, opaque_ref
from amidst.local_storage.migrations import IMMUTABLE, MIGRATIONS
from amidst.product.appearance import AppearanceIndex, DescriptorBundle
from amidst.product.store import (
    EntityKind,
    Payload,
    Revision,
    SQLiteProductStore,
    StoreConflict,
    StoreError,
    StoreIntegrityError,
    _check_payload,
    _json,
)


class PostgresSettings(RegistryModel):
    dsn: SecretStr
    schema_name: str = Field(default="amidst_local", pattern=r"^amidst_[a-z0-9_]{1,48}$")
    connect_timeout: int = Field(default=5, ge=1, le=30)

    @model_validator(mode="after")
    def local_only(self) -> Self:
        try:
            values = conninfo_to_dict(self.dsn.get_secret_value())
        except psycopg.Error:
            raise ValueError("POSTGRES_SETTINGS_INVALID") from None
        host = str(values.get("host", ""))
        local_socket = host.startswith(("/private/tmp/", "/tmp/"))
        if (
            not local_socket
            and host not in {"localhost", "127.0.0.1"}
            or not re.fullmatch(r"amidst_[a-z0-9_]{1,48}", str(values.get("dbname", "")))
            or "service" in values
            or "hostaddr" in values
        ):
            raise ValueError("POSTGRES_LOCAL_SCOPE_DENIED")
        return self

    @classmethod
    def load(cls, path: Path) -> PostgresSettings:
        if path.is_symlink():
            raise ValueError("POSTGRES_SETTINGS_PATH_DENIED")
        return cls.model_validate_json(path.read_bytes())


class MediaBinding(RegistryModel):
    source_sha256: Sha256
    sha256: Sha256
    size_bytes: int = Field(ge=0, le=10**12)
    mime_type: Literal["image/png", "image/jpeg", "video/mp4"]
    camera_id: str = Field(min_length=1, max_length=150)
    timestamp: Timestamp


class _Row:
    def __init__(self, value: dict[str, Any]):
        self.value = value

    def __getitem__(self, key: int | str) -> Any:
        return tuple(self.value.values())[key] if isinstance(key, int) else self.value[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.value.values())


class _Cursor:
    def __init__(self, cursor: psycopg.Cursor[dict[str, Any]]):
        self.cursor = cursor

    def fetchone(self) -> _Row | None:
        row = self.cursor.fetchone()
        return None if row is None else _Row(row)

    def __iter__(self) -> Iterator[_Row]:
        return (_Row(row) for row in self.cursor)


class _SQLConnection:
    """Only translates fixed ProductStore dialect markers; executes real PostgreSQL."""

    def __init__(self, connection: psycopg.Connection[dict[str, Any]]):
        self.connection = connection

    def execute(self, statement: str, parameters: Sequence[Any] = ()) -> _Cursor:
        if statement == "PRAGMA data_version":
            # Canonical tables are immutable on the server. Verification is cached
            # after a complete receipt check; mutable ledger heads live separately.
            statement = "SELECT 1"
        statement = statement.replace("BEGIN IMMEDIATE", "BEGIN")
        statement = re.sub(r" INDEXED BY [a-z_]+", "", statement)
        statement = statement.replace(" CROSS JOIN records r ON ", " JOIN records r ON ")
        statement = statement.replace(" AND 0", " AND FALSE").replace("?", "%s")
        try:
            return _Cursor(self.connection.execute(statement, parameters))
        except psycopg.Error:
            raise StoreError("POSTGRES_STATEMENT_FAILED") from None

    def executemany(self, statement: str, parameters: Iterable[Sequence[Any]]) -> None:
        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(statement.replace("?", "%s"), parameters)
        except psycopg.Error:
            raise StoreError("POSTGRES_STATEMENT_FAILED") from None

    def close(self) -> None:
        self.connection.close()


class PostgresProductStore(SQLiteProductStore):
    """Compatible canonical API backed solely by a dedicated PostgreSQL schema."""

    def __init__(self, settings: PostgresSettings):
        self.settings = PostgresSettings.model_validate(settings.model_dump(mode="python"))
        self._lock = threading.RLock()
        try:
            connection = psycopg.connect(
                settings.dsn.get_secret_value(),
                autocommit=True,
                connect_timeout=settings.connect_timeout,
                row_factory=dict_row,
            )
            self._connection = connection
            # ProductStore's shared validation methods consume a row/execute protocol.
            # Any describes that internal protocol, not the runtime database type.
            self._db: Any = _SQLConnection(connection)
            self._migrate()
            row = self._db.execute(
                "SELECT value FROM metadata WHERE key=?", ("cursor_key",)
            ).fetchone()
            if row is None or re.fullmatch(r"[0-9a-f]{64}", row[0]) is None:
                raise StoreIntegrityError("CURSOR_KEY_INVALID")
            self._cursor_key = bytes.fromhex(row[0])
            self._verified: dict[str, int] = {}
        except (psycopg.Error, OSError):
            if hasattr(self, "_db"):
                self._db.close()
            raise StoreError("POSTGRES_UNAVAILABLE") from None
        except StoreError:
            if hasattr(self, "_db"):
                self._db.close()
            raise

    def __enter__(self) -> PostgresProductStore:
        return self

    def _migrate(self) -> None:
        connection = self._connection
        with connection.transaction():
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (self.settings.schema_name + ":migration",),
            )
            connection.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(self.settings.schema_name)
                )
            )
            connection.execute(
                sql.SQL("SET search_path TO {}, pg_catalog").format(
                    sql.Identifier(self.settings.schema_name)
                )
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, source_sha256 TEXT NOT NULL)"
            )
            applied = {
                r["version"]: r["source_sha256"]
                for r in connection.execute("SELECT version,source_sha256 FROM schema_migrations")
            }
            if not set(applied) <= {v for v, _ in MIGRATIONS}:
                raise StoreIntegrityError("POSTGRES_SCHEMA_VERSION_INVALID")
            for version, statements in MIGRATIONS:
                expected = hashlib.sha256(statements.encode()).hexdigest()
                if version in applied:
                    if applied[version] != expected:
                        raise StoreIntegrityError("POSTGRES_MIGRATION_CHANGED")
                else:
                    connection.execute(statements)
                    connection.execute(
                        "INSERT INTO schema_migrations VALUES (%s,%s)", (version, expected)
                    )
            for table in IMMUTABLE:
                trigger = sql.Identifier(table + "_immutable")
                target = sql.Identifier(table)
                exists = connection.execute(
                    "SELECT 1 FROM pg_trigger WHERE tgname=%s AND tgrelid=%s::regclass",
                    (table + "_immutable", table),
                ).fetchone()
                if exists is None:
                    connection.execute(
                        sql.SQL(
                            "CREATE TRIGGER {} BEFORE UPDATE OR DELETE ON {} "
                            "FOR EACH ROW EXECUTE FUNCTION deny_mutation()"
                        ).format(trigger, target)
                    )
            connection.execute(
                "INSERT INTO metadata VALUES ('schema_version','product.postgres.v1') "
                "ON CONFLICT DO NOTHING"
            )
            connection.execute(
                "INSERT INTO metadata VALUES ('cursor_key',%s) ON CONFLICT DO NOTHING",
                (secrets.token_hex(32),),
            )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        try:
            with self._lock, self._connection.transaction():
                # Serializes mutations in this small local schema. Reads use independent
                # connections/MVCC. CAS still compares the supplied version under lock.
                self._connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (self.settings.schema_name + ":writer",),
                )
                yield
        except psycopg.Error:
            raise StoreError("POSTGRES_TRANSACTION_FAILED") from None

    def append_revision(
        self,
        run_ref: str,
        kind: EntityKind,
        entity_ref: str,
        payload: Payload,
        *,
        expected_version: int,
    ) -> Revision:
        if kind not in {"CASE", "REPORT", "REVIEW"}:
            raise StoreError("REVISION_KIND_INVALID")
        return super().append_revision(
            run_ref, kind, entity_ref, payload, expected_version=expected_version
        )

    def append_job(
        self, run_ref: str, job_ref: str, payload: Payload, *, expected_version: int
    ) -> dict[str, Any]:
        self.get_scope(run_ref)
        _check_payload(payload)
        if (
            type(expected_version) is not int
            or expected_version < 0
            or re.fullmatch(r"(?:job:[0-9a-f]{24}|runjob-[0-9a-f]{32})", job_ref) is None
        ):
            raise StoreError("JOB_REFERENCE_OR_VERSION_INVALID")
        with self._transaction():
            previous = self.get_job(run_ref, job_ref)
            actual = 0 if previous is None else previous["version"]
            if expected_version != actual:
                raise StoreConflict("JOB_VERSION_CONFLICT")
            values = {
                "run_ref": run_ref,
                "job_ref": job_ref,
                "version": actual + 1,
                "previous_sha256": None if previous is None else previous["revision_sha256"],
                "payload": payload,
                "payload_sha256": digest(payload),
            }
            result = values | {"revision_sha256": digest(values)}
            self._db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?)",
                (
                    run_ref,
                    job_ref,
                    actual + 1,
                    values["previous_sha256"],
                    _json(result),
                    result["revision_sha256"],
                ),
            )
        return result

    def get_job(self, run_ref: str, job_ref: str) -> dict[str, Any] | None:
        self.get_scope(run_ref)
        rows = tuple(
            self._db.execute(
                "SELECT * FROM jobs WHERE run_ref=? AND job_ref=? ORDER BY version",
                (run_ref, job_ref),
            )
        )
        previous = None
        result = None
        for version, row in enumerate(rows, 1):
            result = json.loads(row["payload_json"])
            core = {k: v for k, v in result.items() if k != "revision_sha256"}
            if (
                result["version"] != version
                or result["previous_sha256"] != previous
                or result["run_ref"] != run_ref
                or result["job_ref"] != job_ref
                or digest(core) != row["revision_sha256"]
                or digest(result["payload"]) != result["payload_sha256"]
            ):
                raise StoreIntegrityError("JOB_CHAIN_INVALID")
            previous = result["revision_sha256"]
        return result

    def list_jobs(self, run_ref: str, *, limit: int = 100) -> list[dict[str, Any]]:
        self.get_scope(run_ref)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise StoreError("JOB_LIMIT_INVALID")
        rows = self._db.execute(
            "SELECT DISTINCT job_ref FROM jobs WHERE run_ref=? ORDER BY job_ref LIMIT ?",
            (run_ref, limit),
        )
        return [item for row in rows if (item := self.get_job(run_ref, row[0])) is not None]

    def install_descriptors(
        self, run_ref: str, bundle: DescriptorBundle, *, expected_version: int
    ) -> dict[str, Any]:
        scope = self.get_scope(run_ref)
        checked = DescriptorBundle.model_validate_json(bundle.model_dump_json())
        if (
            checked.scope != scope.resource_scope
            or checked.dataset_sha256 != scope.dataset_sha256
            or checked.registry_sha256 != scope.registry_sha256
            or checked.media_sha256 != scope.media_sha256
        ):
            raise StoreError("DESCRIPTOR_SCOPE_DENIED")
        _check_payload(checked.model_dump(mode="json"))
        sha = digest(checked)
        ref = opaque_ref("descriptorindex", run_ref, sha)
        with self._transaction():
            head = self._db.execute(
                "SELECT index_ref,version FROM index_heads WHERE run_ref=?", (run_ref,)
            ).fetchone()
            actual = 0 if head is None else head[1]
            if expected_version != actual:
                raise StoreConflict("DESCRIPTOR_VERSION_CONFLICT")
            existing = self._db.execute(
                "SELECT bundle_sha256 FROM descriptor_indexes WHERE run_ref=? AND index_ref=?",
                (run_ref, ref),
            ).fetchone()
            if existing is None:
                self._db.execute(
                    "INSERT INTO descriptor_indexes VALUES (?,?,?,?)",
                    (run_ref, ref, checked.model_dump_json(), sha),
                )
            elif existing[0] != sha:
                raise StoreIntegrityError("DESCRIPTOR_HASH_INVALID")
            self._db.execute(
                "INSERT INTO index_heads VALUES (?,?,?) ON CONFLICT(run_ref) "
                "DO UPDATE SET index_ref=excluded.index_ref,version=excluded.version",
                (run_ref, ref, actual + 1),
            )
        return {
            "index_ref": ref,
            "version": actual + 1,
            "bundle_sha256": sha,
            "trained_reid": False,
            "descriptor_version": checked.config.descriptor_version,
        }

    def load_descriptors(self, run_ref: str, index_ref: str | None = None) -> DescriptorBundle:
        self.get_scope(run_ref)
        if index_ref is None:
            head = self._db.execute(
                "SELECT index_ref FROM index_heads WHERE run_ref=?", (run_ref,)
            ).fetchone()
            if head is None:
                raise StoreError("DESCRIPTOR_INDEX_UNAVAILABLE")
            index_ref = head[0]
        row = self._db.execute(
            "SELECT bundle_json,bundle_sha256 FROM descriptor_indexes "
            "WHERE run_ref=? AND index_ref=?",
            (run_ref, index_ref),
        ).fetchone()
        if row is None:
            raise StoreError("DESCRIPTOR_INDEX_UNAVAILABLE")
        bundle = DescriptorBundle.model_validate_json(row[0])
        if digest(bundle) != row[1] or opaque_ref("descriptorindex", run_ref, row[1]) != index_ref:
            raise StoreIntegrityError("DESCRIPTOR_HASH_INVALID")
        return bundle

    def appearance_index(self, run_ref: str) -> AppearanceIndex:
        return AppearanceIndex(self.load_descriptors(run_ref))

    def ensure_descriptors(self, run_ref: str, bundle: DescriptorBundle) -> dict[str, Any]:
        """Idempotent restart binding; changing the active index requires explicit CAS."""
        with self._transaction():
            head = self._db.execute(
                "SELECT index_ref,version FROM index_heads WHERE run_ref=?", (run_ref,)
            ).fetchone()
            if head is None:
                return self.install_descriptors(run_ref, bundle, expected_version=0) | {
                    "reused": False
                }
            current = self.load_descriptors(run_ref, head[0])
            if current != DescriptorBundle.model_validate_json(bundle.model_dump_json()):
                raise StoreConflict("DESCRIPTOR_RESTART_BINDING_CONFLICT")
            return {
                "index_ref": head[0],
                "version": head[1],
                "bundle_sha256": digest(current),
                "trained_reid": False,
                "descriptor_version": current.config.descriptor_version,
                "reused": True,
            }

    def register_media(self, run_ref: str, media_ref: str, payload: Payload) -> None:
        self.get_scope(run_ref)
        _check_payload(payload)
        try:
            checked = MediaBinding.model_validate_json(_json(payload))
        except ValueError:
            raise StoreError("MEDIA_BINDING_INVALID") from None
        if (
            checked.source_sha256 != self.get_scope(run_ref).resource_scope.source_sha256
            or re.fullmatch(r"[a-z]+:[0-9a-f]{24}", media_ref) is None
        ):
            raise StoreError("MEDIA_BINDING_INVALID")
        sha = digest(payload)
        with self._transaction():
            row = self._db.execute(
                "SELECT payload_sha256 FROM media_bindings WHERE run_ref=? AND media_ref=?",
                (run_ref, media_ref),
            ).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO media_bindings VALUES (?,?,?,?)",
                    (run_ref, media_ref, _json(payload), sha),
                )
            elif row[0] != sha:
                raise StoreConflict("IMMUTABLE_MEDIA_CONFLICT")

    def get_media_binding(self, run_ref: str, media_ref: str) -> Payload:
        self.get_scope(run_ref)
        row = self._db.execute(
            "SELECT payload_json,payload_sha256 FROM media_bindings "
            "WHERE run_ref=? AND media_ref=?",
            (run_ref, media_ref),
        ).fetchone()
        if row is None:
            raise StoreError("MEDIA_UNAVAILABLE")
        payload: Payload = json.loads(row[0])
        if digest(payload) != row[1]:
            raise StoreIntegrityError("MEDIA_HASH_INVALID")
        return payload

    def install_topology(
        self, run_ref: str, topology: ScopedTopology, *, expected_version: int
    ) -> dict[str, Any]:
        if topology.scope != self.get_scope(run_ref).resource_scope:
            raise StoreError("TOPOLOGY_SCOPE_DENIED")
        topology = ScopedTopology.model_validate_json(topology.model_dump_json())
        _check_payload(topology.model_dump(mode="json"))
        sha = digest(topology)
        with self._transaction():
            row = self._db.execute(
                "SELECT topology_sha256,version FROM topology_heads WHERE run_ref=?", (run_ref,)
            ).fetchone()
            actual = 0 if row is None else row[1]
            if expected_version != actual:
                raise StoreConflict("TOPOLOGY_VERSION_CONFLICT")
            self._db.execute(
                "INSERT INTO topologies VALUES (?,?,?) ON CONFLICT DO NOTHING",
                (run_ref, sha, topology.model_dump_json()),
            )
            self._db.execute(
                "INSERT INTO topology_heads VALUES (?,?,?) ON CONFLICT(run_ref) "
                "DO UPDATE SET topology_sha256=excluded.topology_sha256,version=excluded.version",
                (run_ref, sha, actual + 1),
            )
        return {
            "topology_sha256": sha,
            "version": actual + 1,
            "previous_cache_invalidated": row is not None and row[0] != sha,
        }

    def _topology_head(self, run_ref: str, topology_sha256: str) -> None:
        self.get_scope(run_ref)
        row = self._db.execute(
            "SELECT topology_sha256 FROM topology_heads WHERE run_ref=?", (run_ref,)
        ).fetchone()
        if row is None or row[0] != topology_sha256:
            raise StoreError("TOPOLOGY_CACHE_STALE")

    def ensure_topology(self, run_ref: str, topology: ScopedTopology) -> dict[str, Any]:
        """Retain the exact configured topology on restart; never overwrite silently."""
        with self._transaction():
            row = self._db.execute(
                "SELECT topology_sha256,version FROM topology_heads WHERE run_ref=?", (run_ref,)
            ).fetchone()
            if row is None:
                return self.install_topology(run_ref, topology, expected_version=0) | {
                    "reused": False
                }
            stored = self._db.execute(
                "SELECT payload_json FROM topologies WHERE run_ref=? AND topology_sha256=?",
                (run_ref, row[0]),
            ).fetchone()
            if stored is None or digest(json.loads(stored[0])) != row[0]:
                raise StoreIntegrityError("TOPOLOGY_HASH_INVALID")
            checked = ScopedTopology.model_validate_json(stored[0])
            if topology != checked or checked.scope != self.get_scope(run_ref).resource_scope:
                raise StoreConflict("TOPOLOGY_RESTART_BINDING_CONFLICT")
            return {
                "topology_sha256": row[0],
                "version": row[1],
                "reused": True,
                "previous_cache_invalidated": False,
            }

    def cache_topology(
        self, run_ref: str, topology_sha256: str, query_sha256: str, payload: Payload
    ) -> None:
        _check_payload(payload)
        if re.fullmatch(r"[0-9a-f]{64}", query_sha256) is None:
            raise StoreError("CACHE_QUERY_HASH_INVALID")
        with self._transaction():
            self._topology_head(run_ref, topology_sha256)
            row = self._db.execute(
                "SELECT payload_sha256 FROM topology_cache WHERE run_ref=? "
                "AND topology_sha256=? AND query_sha256=?",
                (run_ref, topology_sha256, query_sha256),
            ).fetchone()
            if row is not None and row[0] != digest(payload):
                raise StoreConflict("CACHE_RESULT_CONFLICT")
            self._db.execute(
                "INSERT INTO topology_cache VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                (run_ref, topology_sha256, query_sha256, _json(payload), digest(payload)),
            )

    def read_topology_cache(
        self, run_ref: str, topology_sha256: str, query_sha256: str
    ) -> Payload | None:
        self._topology_head(run_ref, topology_sha256)
        row = self._db.execute(
            "SELECT payload_json,payload_sha256 FROM topology_cache WHERE "
            "run_ref=? AND topology_sha256=? AND query_sha256=?",
            (run_ref, topology_sha256, query_sha256),
        ).fetchone()
        if row is None:
            return None
        result: Payload = json.loads(row[0])
        if digest(result) != row[1]:
            raise StoreIntegrityError("CACHE_RESULT_HASH_INVALID")
        return result

    def content_manifest(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        hashes: dict[str, str] = {}
        for table in (*IMMUTABLE, "metadata", "schema_migrations", "index_heads", "topology_heads"):
            rows = list(
                self._connection.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
            )
            encoded = sorted(_json(row) for row in rows)
            counts[table] = len(encoded)
            hashes[table] = digest(encoded)
        return {
            "schema_version": "local.postgres.manifest.v1",
            "counts": counts,
            "table_sha256": hashes,
            "content_sha256": digest(hashes),
        }

    def context(self) -> dict[str, Any]:
        return {
            "schema_version": "local.postgres.context.v1",
            "backend": "POSTGRESQL",
            "local_only": True,
            "server_version": self._connection.info.server_version,
            "migration_versions": [version for version, _ in MIGRATIONS],
            "counts": {
                table: next(
                    iter(
                        self._connection.execute(
                            sql.SQL("SELECT COUNT(*) AS n FROM {}").format(sql.Identifier(table))
                        )
                    )
                )["n"]
                for table in (*IMMUTABLE, "index_heads", "topology_heads")
            },
            "query_limit": 500,
            "media_storage": "HASH_BOUND_REFERENCES_ONLY",
            "trained_reid": False,
            "production_capacity_certified": False,
        }


def _serialized(method: Callable[..., Any]) -> Callable[..., Any]:
    """A whole public operation shares one lock, including inherited contracts."""

    @wraps(method)
    def guarded(self: PostgresProductStore, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    return guarded


for _method in (
    "import_records",
    "list_runs",
    "get_scope",
    "get_record",
    "verify_run",
    "query_records",
    "append_revision",
    "get_revision",
    "list_revisions",
    "list_latest_revisions",
    "append_job",
    "get_job",
    "list_jobs",
    "install_descriptors",
    "load_descriptors",
    "appearance_index",
    "ensure_descriptors",
    "register_media",
    "get_media_binding",
    "install_topology",
    "ensure_topology",
    "cache_topology",
    "read_topology_cache",
    "content_manifest",
    "context",
    "close",
):
    setattr(PostgresProductStore, _method, _serialized(getattr(PostgresProductStore, _method)))
