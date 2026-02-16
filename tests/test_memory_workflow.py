from __future__ import annotations

from pathlib import Path

import yaml

from ai_agents_hub.memory.store import MemoryStore


def _load_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    end = raw.find("\n---\n", 4)
    return yaml.safe_load(raw[4:end]) or {}


def test_memory_write_and_undo(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memories")
    record = store.write_memory(
        domain="health",
        summary="Morning workout",
        body="Did a 5km run and felt good.",
        confidence=0.88,
        tags=["exercise"],
        created_by_agent="supervisor",
    )
    assert record.path.exists()
    frontmatter = _load_frontmatter(record.path)
    assert frontmatter["domain"] == "health"
    assert frontmatter["tombstone"] is False

    assert store.undo_memory(record.memory_id) is True
    updated = _load_frontmatter(record.path)
    assert updated["tombstone"] is True


def test_memory_edit_appends_note(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memories")
    record = store.write_memory(
        domain="homelab",
        summary="Container restart policy",
        body="Set restart always on service.",
        confidence=0.75,
        tags=["lxc"],
        created_by_agent="supervisor",
    )
    assert store.edit_memory(record.memory_id, "Add rollback command") is True
    content = record.path.read_text(encoding="utf-8")
    assert "## Manual Edit Note" in content
    assert "Add rollback command" in content
