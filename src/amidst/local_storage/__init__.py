"""Real local PostgreSQL persistence; never a fallback to synthetic SQLite."""

from amidst.local_storage.postgres import PostgresProductStore, PostgresSettings

__all__ = ["PostgresProductStore", "PostgresSettings"]
