from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mobius.config import StateConfig
from mobius.logging_setup import get_logger
from mobius.state.migrations import migration_sql, migration_versions


@dataclass
class StateStoreStatus:
    enabled: bool
    configured: bool
    connected: bool
    ready: bool
    auto_migrate: bool
    projection_mode: str
    projection_directory: str
    min_supported_schema_version: str
    max_supported_schema_version: str
    current_schema_version: str | None = None
    pending_migrations: list[str] = field(default_factory=list)
    migrations_applied: list[str] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "connected": self.connected,
            "ready": self.ready,
            "auto_migrate": self.auto_migrate,
            "projection_mode": self.projection_mode,
            "projection_directory": self.projection_directory,
            "min_supported_schema_version": self.min_supported_schema_version,
            "max_supported_schema_version": self.max_supported_schema_version,
            "current_schema_version": self.current_schema_version,
            "pending_migrations": self.pending_migrations,
            "migrations_applied": self.migrations_applied,
            "error": self.error,
        }


class StateStore:
    def __init__(self, config: StateConfig) -> None:
        self.config = config
        self.logger = get_logger(__name__)
        self.status = StateStoreStatus(
            enabled=config.enabled,
            configured=bool(config.database.dsn),
            connected=False,
            ready=not config.enabled,
            auto_migrate=config.database.auto_migrate,
            projection_mode=config.projection.mode,
            projection_directory=str(config.projection.output_directory),
            min_supported_schema_version=config.database.min_schema_version,
            max_supported_schema_version=config.database.max_schema_version,
        )

    @staticmethod
    def _import_psycopg() -> Any:
        try:
            import psycopg  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError(
                "psycopg is required when state.enabled=true. Install dependency 'psycopg[binary]'."
            ) from exc
        return psycopg

    @staticmethod
    def _ensure_schema_migrations_table(conn: Any) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
            )
        conn.commit()

    @staticmethod
    def _load_applied_versions(conn: Any) -> set[str]:
        with conn.cursor() as cursor:
            cursor.execute("SELECT version FROM schema_migrations")
            rows = cursor.fetchall()
        return {str(row[0]) for row in rows}

    @staticmethod
    def _latest_schema_version(conn: Any) -> str | None:
        with conn.cursor() as cursor:
            cursor.execute("SELECT MAX(version) FROM schema_migrations")
            row = cursor.fetchone()
        if not row:
            return None
        value = row[0]
        return str(value) if value is not None else None

    @staticmethod
    def _apply_migration(conn: Any, version: str, sql: str) -> None:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            cursor.execute(
                "INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING",
                (version,),
            )
        conn.commit()

    def initialize(self) -> None:
        if not self.config.enabled:
            return

        if not self.config.database.dsn:
            self.status.error = "state.database.dsn is not configured."
            self.status.ready = False
            raise RuntimeError(self.status.error)

        psycopg = self._import_psycopg()

        try:
            with psycopg.connect(
                self.config.database.dsn,
                connect_timeout=self.config.database.connect_timeout_seconds,
            ) as conn:
                self._ensure_schema_migrations_table(conn)
                applied = self._load_applied_versions(conn)
                ordered_versions = migration_versions()
                pending = [version for version in ordered_versions if version not in applied]
                self.status.pending_migrations = pending

                if pending and not self.config.database.auto_migrate:
                    raise RuntimeError(
                        f"Pending state migrations found: {pending}. "
                        "Enable state.database.auto_migrate or apply migrations manually."
                    )

                for version in pending:
                    self.logger.info("Applying state migration version=%s", version)
                    self._apply_migration(conn, version, migration_sql(version))
                    self.status.migrations_applied.append(version)

                current = self._latest_schema_version(conn)
                self.status.current_schema_version = current

                if current is None:
                    raise RuntimeError("No state schema version detected after initialization.")
                if current < self.config.database.min_schema_version:
                    raise RuntimeError(
                        "State schema is older than supported minimum "
                        f"(current={current}, min={self.config.database.min_schema_version})."
                    )
                if current > self.config.database.max_schema_version:
                    raise RuntimeError(
                        "State schema is newer than supported maximum "
                        f"(current={current}, max={self.config.database.max_schema_version})."
                    )

                self.status.connected = True
                self.status.ready = True
                self.status.pending_migrations = []
                self.status.error = None
        except Exception as exc:
            self.status.connected = False
            self.status.ready = False
            self.status.error = f"{exc.__class__.__name__}: {exc}"
            raise
