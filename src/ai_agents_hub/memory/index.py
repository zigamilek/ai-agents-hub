from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class MemoryIndex:
    def __init__(self, root_path: Path) -> None:
        self.db_path = root_path / "_index" / "memory_index.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    confidence REAL,
                    tags_json TEXT,
                    archived INTEGER DEFAULT 0,
                    tombstone INTEGER DEFAULT 0,
                    created_by_agent TEXT,
                    last_updated_by_agent TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at)"
            )

    def upsert(self, frontmatter: dict[str, Any], path: Path) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id, domain, path, created_at, updated_at, confidence,
                    tags_json, archived, tombstone, created_by_agent, last_updated_by_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    domain=excluded.domain,
                    path=excluded.path,
                    updated_at=excluded.updated_at,
                    confidence=excluded.confidence,
                    tags_json=excluded.tags_json,
                    archived=excluded.archived,
                    tombstone=excluded.tombstone,
                    last_updated_by_agent=excluded.last_updated_by_agent
                """,
                (
                    frontmatter.get("id"),
                    frontmatter.get("domain"),
                    str(path),
                    frontmatter.get("created_at"),
                    frontmatter.get("updated_at"),
                    frontmatter.get("confidence"),
                    json.dumps(frontmatter.get("tags", [])),
                    int(bool(frontmatter.get("archived", False))),
                    int(bool(frontmatter.get("tombstone", False))),
                    frontmatter.get("created_by_agent"),
                    frontmatter.get("last_updated_by_agent"),
                ),
            )

    def get_path(self, memory_id: str) -> Path | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT path FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if not row:
            return None
        return Path(row[0])

    def mark_tombstone(self, memory_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET tombstone = 1 WHERE id = ?",
                (memory_id,),
            )

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE tombstone = 0 AND archived = 0"
            ).fetchone()[0]
            tombstoned = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE tombstone = 1"
            ).fetchone()[0]
            by_domain_rows = conn.execute(
                "SELECT domain, COUNT(*) FROM memories GROUP BY domain ORDER BY domain"
            ).fetchall()
        return {
            "total": total,
            "active": active,
            "tombstoned": tombstoned,
            "by_domain": {row[0]: row[1] for row in by_domain_rows},
        }
