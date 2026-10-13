"""Explicit local-only PostgreSQL lifecycle and real dump/restore helpers.

No service manager/autostart, shared cluster, arbitrary executable or remote
database is accepted. Runtime settings/dumps are ignored local artifacts.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import SecretStr

from amidst.local_storage.postgres import PostgresSettings

BIN = Path("/opt/homebrew/opt/postgresql@18/bin")
REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "data/engineering/local_run/phase2_abc/postgres"
SOCKET = Path("/private/tmp/amidst-pg-abc")
SETTINGS_PATH = ROOT / "settings.json"
PORT = 55432
USER = "amidst_local"
DATABASE = "amidst_abc"


def _run(argv: list[str]) -> None:
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("POSTGRES_BOOTSTRAP_COMMAND_FAILED")


def start() -> PostgresSettings:
    if not (BIN / "postgres").is_file():
        raise RuntimeError("POSTGRES_BINARIES_UNAVAILABLE")
    if any(path.is_symlink() for path in (ROOT, SOCKET, SETTINGS_PATH)):
        raise RuntimeError("POSTGRES_RUNTIME_PATH_DENIED")
    ROOT.mkdir(parents=True, exist_ok=True)
    ROOT.chmod(0o700)
    SOCKET.mkdir(mode=0o700, exist_ok=True)
    SOCKET.chmod(0o700)
    cluster = ROOT / "cluster"
    if not (cluster / "PG_VERSION").exists():
        if cluster.exists() and any(cluster.iterdir()):
            raise RuntimeError("POSTGRES_CLUSTER_NOT_EMPTY")
        _run(
            [
                str(BIN / "initdb"),
                "-D",
                str(cluster),
                "--username=" + USER,
                "--auth-local=trust",
                "--auth-host=reject",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
    status = subprocess.run(
        [str(BIN / "pg_ctl"), "-D", str(cluster), "status"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if status.returncode:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", PORT))
            except OSError:
                raise RuntimeError("POSTGRES_DEDICATED_PORT_IN_USE") from None
        _run(
            [
                str(BIN / "pg_ctl"),
                "-D",
                str(cluster),
                "-l",
                str(ROOT / "server.log"),
                "-o",
                f"-h 127.0.0.1 -p {PORT} -k {SOCKET} -c max_connections=32",
                "-w",
                "start",
            ]
        )
    admin_dsn = make_conninfo(dbname="postgres", user=USER, host=str(SOCKET), port=PORT)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        if (
            connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()
            is None
        ):
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    dsn = make_conninfo(dbname=DATABASE, user=USER, host=str(SOCKET), port=PORT)
    SETTINGS_PATH.write_text(
        json.dumps(
            {"dsn": dsn, "schema_name": "amidst_local", "connect_timeout": 5}, sort_keys=True
        )
        + "\n"
    )
    SETTINGS_PATH.chmod(0o600)
    return PostgresSettings(dsn=SecretStr(dsn))


def stop() -> None:
    _run([str(BIN / "pg_ctl"), "-D", str(ROOT / "cluster"), "-m", "fast", "-w", "stop"])


def backup(settings: PostgresSettings, path: Path) -> None:
    if path.is_symlink() or path.exists() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("POSTGRES_BACKUP_PATH_DENIED")
    path.parent.mkdir(parents=True, exist_ok=True)
    # The local socket DSN has no password; all files remain local/ignored.
    _run(
        [
            str(BIN / "pg_dump"),
            "--dbname",
            settings.dsn.get_secret_value(),
            "--format=custom",
            "--schema",
            settings.schema_name,
            "--no-owner",
            "--no-privileges",
            "--file",
            str(path),
        ]
    )
    path.chmod(0o600)


def restore(settings: PostgresSettings, path: Path, *, database: str) -> PostgresSettings:
    if (
        not database.startswith("amidst_restore_")
        or len(database) > 60
        or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in database)
        or path.is_symlink()
        or not path.resolve().is_relative_to(ROOT.resolve())
    ):
        raise ValueError("POSTGRES_RESTORE_SCOPE_DENIED")
    values = conninfo_to_dict(settings.dsn.get_secret_value())
    admin: dict[str, Any] = values | {"dbname": "postgres"}
    with psycopg.connect(make_conninfo(**admin), autocommit=True) as connection:
        if connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone():
            raise ValueError("POSTGRES_RESTORE_DATABASE_EXISTS")
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    target_values: dict[str, Any] = values | {"dbname": database}
    target = make_conninfo(**target_values)
    _run([str(BIN / "pg_restore"), "--dbname", target, "--no-owner", "--no-privileges", str(path)])
    return PostgresSettings(dsn=SecretStr(target), schema_name=settings.schema_name)
