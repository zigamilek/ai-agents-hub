from __future__ import annotations

from pathlib import Path

import yaml

from ai_agents_hub.memory.store import MemoryStore


def _load_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    end = raw.find("\n---\n", 4)
    return yaml.safe_load(raw[4:end]) or {}


def test_memory_write_is_deduplicated_in_domain_file(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memories")
    first = store.write_memory(
        domain="health",
        summary="interested in tennis elbow rehabilitation",
        body="",
        confidence=0.88,
        tags=["health"],
        created_by_agent="memory-curator",
    )
    second = store.write_memory(
        domain="health",
        summary="interested in tennis elbow rehabilitation",
        body="",
        confidence=0.93,
        tags=["health"],
        created_by_agent="memory-curator",
    )

    assert first.created is True
    assert second.created is False
    assert first.path.exists()
    assert first.path == second.path
    assert first.path.name == "health.md"

    frontmatter = _load_frontmatter(first.path)
    assert frontmatter["domain"] == "health"
    assert frontmatter["entry_count"] == 1

    content = first.path.read_text(encoding="utf-8")
    assert content.count("interested in tennis elbow rehabilitation") == 1
    assert content.count("- [mem_") == 1


def test_memory_write_and_undo(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memories")
    record = store.write_memory(
        domain="parenting",
        summary="looking to solve son's disobedience",
        body="",
        confidence=0.8,
        tags=["parenting"],
        created_by_agent="memory-curator",
    )
    assert store.undo_memory(record.memory_id) is True
    updated = _load_frontmatter(record.path)
    assert updated["tombstone"] is True
    content = record.path.read_text(encoding="utf-8")
    assert "[REMOVED] looking to solve son's disobedience" in content


def test_memory_edit_appends_note(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memories")
    record = store.write_memory(
        domain="homelab",
        summary="wants resilient lxc update workflow",
        body="",
        confidence=0.75,
        tags=["lxc"],
        created_by_agent="memory-curator",
    )
    assert store.edit_memory(record.memory_id, "Add rollback command") is True
    content = record.path.read_text(encoding="utf-8")
    assert "wants resilient lxc update workflow (user note: Add rollback command)" in content
