from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from ai_agents_hub.logging_setup import get_logger
from ai_agents_hub.memory.events import MemoryEvents
from ai_agents_hub.memory.index import MemoryIndex


def _slugify(text: str) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return candidate.strip("-") or "memory"


def _extract_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    frontmatter = yaml.safe_load(content[4:end]) or {}
    body = content[end + 5 :]
    return frontmatter, body


def _render_markdown(frontmatter: dict, body: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


@dataclass
class MemoryRecord:
    memory_id: str
    domain: str
    path: Path
    summary: str


class MemoryStore:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.events = MemoryEvents(root_path)
        self.index = MemoryIndex(root_path)
        self.logger = get_logger(__name__)

    def write_memory(
        self,
        *,
        domain: str,
        summary: str,
        body: str,
        confidence: float,
        tags: list[str],
        created_by_agent: str,
    ) -> MemoryRecord:
        now = datetime.now(timezone.utc)
        date_str = now.date().isoformat()
        year = str(now.year)
        memory_id = f"mem_{date_str}_{uuid4().hex[:8]}"
        filename = f"{date_str}-{memory_id}-{_slugify(summary)[:32]}.md"
        directory = self.root_path / "domains" / domain / year
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename

        frontmatter = {
            "id": memory_id,
            "domain": domain,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "confidence": round(confidence, 3),
            "tags": tags,
            "created_by_agent": created_by_agent,
            "last_updated_by_agent": created_by_agent,
            "archived": False,
            "tombstone": False,
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        markdown = _render_markdown(frontmatter, body)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(markdown, encoding="utf-8")
        temp_path.replace(path)

        self.index.upsert(frontmatter, path)
        self.events.append(
            "memory_written",
            {"memory_id": memory_id, "path": str(path), "domain": domain},
        )
        self.logger.info("Memory written id=%s domain=%s path=%s", memory_id, domain, path)
        return MemoryRecord(
            memory_id=memory_id,
            domain=domain,
            path=path,
            summary=summary,
        )

    def undo_memory(self, memory_id: str, actor: str = "user") -> bool:
        path = self.index.get_path(memory_id)
        if not path or not path.exists():
            self.logger.debug("Undo failed: memory not found id=%s", memory_id)
            return False
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = _extract_frontmatter(raw)
        if not frontmatter:
            self.logger.warning("Undo failed: invalid frontmatter path=%s", path)
            return False
        frontmatter["tombstone"] = True
        frontmatter["updated_at"] = datetime.now(timezone.utc).isoformat()
        frontmatter["last_updated_by_agent"] = actor
        path.write_text(_render_markdown(frontmatter, body), encoding="utf-8")
        self.index.upsert(frontmatter, path)
        self.index.mark_tombstone(memory_id)
        self.events.append("memory_undone", {"memory_id": memory_id, "path": str(path)})
        self.logger.info("Memory tombstoned id=%s path=%s", memory_id, path)
        return True

    def edit_memory(self, memory_id: str, instructions: str, actor: str = "user") -> bool:
        path = self.index.get_path(memory_id)
        if not path or not path.exists():
            self.logger.debug("Edit failed: memory not found id=%s", memory_id)
            return False
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = _extract_frontmatter(raw)
        if not frontmatter:
            self.logger.warning("Edit failed: invalid frontmatter path=%s", path)
            return False
        frontmatter["updated_at"] = datetime.now(timezone.utc).isoformat()
        frontmatter["last_updated_by_agent"] = actor
        updated_body = (
            body.strip()
            + "\n\n"
            + "## Manual Edit Note\n"
            + instructions.strip()
            + "\n"
        )
        path.write_text(_render_markdown(frontmatter, updated_body), encoding="utf-8")
        self.index.upsert(frontmatter, path)
        self.events.append(
            "memory_edited",
            {"memory_id": memory_id, "path": str(path), "instructions": instructions},
        )
        self.logger.info("Memory edited id=%s path=%s", memory_id, path)
        return True
