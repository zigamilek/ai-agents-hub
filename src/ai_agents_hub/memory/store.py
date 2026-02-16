from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from ai_agents_hub.logging_setup import get_logger
from ai_agents_hub.memory.events import MemoryEvents
from ai_agents_hub.memory.index import MemoryIndex

ENTRY_LINE_RE = re.compile(r"^\s*-\s+\[(?P<id>[^\]]+)\]\s+(?P<text>.+?)\s*$")
REMOVED_PREFIX = "[REMOVED] "


def _extract_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    loaded = yaml.safe_load(content[4:end]) or {}
    frontmatter = loaded if isinstance(loaded, dict) else {}
    body = content[end + 5 :]
    return frontmatter, body


def _render_markdown(frontmatter: dict, body: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


def _normalize_domain(domain: str) -> str:
    normalized = domain.strip().lower().replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "_", normalized).strip("_") or "general"


def _normalize_summary(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^a-z0-9 ]+", "", lowered).strip()


def _title_from_domain(domain: str) -> str:
    return domain.replace("_", " ").strip().title() or "General"


def _default_body_for_domain(domain: str) -> str:
    title = _title_from_domain(domain)
    return f"# {title} Memory\n\n"


@dataclass
class MemoryRecord:
    memory_id: str
    domain: str
    path: Path
    summary: str
    created: bool = True


class MemoryStore:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.events = MemoryEvents(root_path)
        self.index = MemoryIndex(root_path)
        self.logger = get_logger(__name__)

    def _path_for_domain(self, domain: str) -> Path:
        normalized = _normalize_domain(domain)
        path = self.root_path / "domains" / f"{normalized}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _iter_entries(body: str) -> list[tuple[int, str, str, bool]]:
        entries: list[tuple[int, str, str, bool]] = []
        for idx, line in enumerate(body.splitlines()):
            match = ENTRY_LINE_RE.match(line)
            if not match:
                continue
            memory_id = match.group("id").strip()
            text = match.group("text").strip()
            removed = text.startswith(REMOVED_PREFIX)
            clean_text = text[len(REMOVED_PREFIX) :].strip() if removed else text
            entries.append((idx, memory_id, clean_text, removed))
        return entries

    @staticmethod
    def _replace_line(body: str, line_index: int, new_line: str) -> str:
        lines = body.splitlines()
        if line_index < 0 or line_index >= len(lines):
            return body
        lines[line_index] = new_line
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _append_entry_line(body: str, entry_line: str) -> str:
        lines = body.splitlines()
        if not lines:
            return entry_line + "\n"
        if lines[-1].strip():
            lines.append("")
        lines.append(entry_line)
        return "\n".join(lines).strip() + "\n"

    def read_domain_memory(self, domain: str, max_chars: int | None = None) -> str:
        path = self._path_for_domain(domain)
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[-max_chars:]

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
        normalized_domain = _normalize_domain(domain)
        path = self._path_for_domain(normalized_domain)
        summary_text = summary.strip() or body.strip().split("\n")[0].strip()
        if not summary_text:
            summary_text = "conversation context"

        raw = path.read_text(encoding="utf-8") if path.exists() else ""
        frontmatter, existing_body = _extract_frontmatter(raw)
        if not existing_body.strip():
            existing_body = _default_body_for_domain(normalized_domain)
        entries = self._iter_entries(existing_body)
        wanted = _normalize_summary(summary_text)

        for _, existing_id, existing_text, removed in entries:
            if removed:
                continue
            if _normalize_summary(existing_text) == wanted:
                self.index.upsert(
                    {
                        "id": existing_id,
                        "domain": normalized_domain,
                        "created_at": frontmatter.get("created_at", now.isoformat()),
                        "updated_at": now.isoformat(),
                        "confidence": round(confidence, 3),
                        "tags": tags,
                        "archived": False,
                        "tombstone": False,
                        "created_by_agent": frontmatter.get(
                            "created_by_agent", created_by_agent
                        ),
                        "last_updated_by_agent": created_by_agent,
                    },
                    path,
                )
                self.events.append(
                    "memory_skipped_duplicate",
                    {
                        "memory_id": existing_id,
                        "path": str(path),
                        "domain": normalized_domain,
                    },
                )
                self.logger.debug(
                    "Memory skipped duplicate id=%s domain=%s summary=%s",
                    existing_id,
                    normalized_domain,
                    summary_text,
                )
                return MemoryRecord(
                    memory_id=existing_id,
                    domain=normalized_domain,
                    path=path,
                    summary=summary_text,
                    created=False,
                )

        memory_id = f"mem_{date_str}_{uuid4().hex[:8]}"
        entry_line = f"- [{memory_id}] {summary_text}"
        updated_body = self._append_entry_line(existing_body, entry_line)
        active_count = sum(1 for _, _, _, removed in entries if not removed) + 1
        frontmatter.setdefault("domain", normalized_domain)
        frontmatter.setdefault("created_at", now.isoformat())
        frontmatter["updated_at"] = now.isoformat()
        frontmatter["entry_count"] = active_count
        frontmatter["created_by_agent"] = frontmatter.get("created_by_agent", created_by_agent)
        frontmatter["last_updated_by_agent"] = created_by_agent
        frontmatter["archived"] = False
        frontmatter["tombstone"] = False

        markdown = _render_markdown(frontmatter, updated_body)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(markdown, encoding="utf-8")
        temp_path.replace(path)

        self.index.upsert(
            {
                "id": memory_id,
                "domain": normalized_domain,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "confidence": round(confidence, 3),
                "tags": tags,
                "archived": False,
                "tombstone": False,
                "created_by_agent": created_by_agent,
                "last_updated_by_agent": created_by_agent,
            },
            path,
        )
        self.events.append(
            "memory_written",
            {"memory_id": memory_id, "path": str(path), "domain": normalized_domain},
        )
        self.logger.info(
            "Memory written id=%s domain=%s path=%s summary=%s",
            memory_id,
            normalized_domain,
            path,
            summary_text,
        )
        return MemoryRecord(
            memory_id=memory_id,
            domain=normalized_domain,
            path=path,
            summary=summary_text,
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
        entries = self._iter_entries(body)
        target_line: int | None = None
        target_text = ""
        for line_idx, entry_id, entry_text, removed in entries:
            if entry_id != memory_id:
                continue
            if removed:
                target_line = None
                break
            target_line = line_idx
            target_text = entry_text
            break
        if target_line is None:
            self.logger.debug("Undo failed: memory line not found id=%s path=%s", memory_id, path)
            return False
        updated_body = self._replace_line(
            body,
            target_line,
            f"- [{memory_id}] {REMOVED_PREFIX}{target_text}",
        )
        updated_at = datetime.now(timezone.utc).isoformat()
        frontmatter["updated_at"] = updated_at
        frontmatter["last_updated_by_agent"] = actor
        active_count = max(
            0,
            sum(1 for _, _, _, removed in entries if not removed) - 1,
        )
        frontmatter["entry_count"] = active_count
        frontmatter["tombstone"] = active_count == 0
        path.write_text(_render_markdown(frontmatter, updated_body), encoding="utf-8")
        self.index.upsert(
            {
                "id": memory_id,
                "domain": frontmatter.get("domain", path.stem),
                "created_at": frontmatter.get("created_at", updated_at),
                "updated_at": updated_at,
                "confidence": None,
                "tags": [frontmatter.get("domain", path.stem)],
                "archived": False,
                "tombstone": True,
                "created_by_agent": frontmatter.get("created_by_agent", actor),
                "last_updated_by_agent": actor,
            },
            path,
        )
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
        entries = self._iter_entries(body)
        target_line: int | None = None
        target_text = ""
        for line_idx, entry_id, entry_text, removed in entries:
            if entry_id != memory_id:
                continue
            target_line = line_idx
            target_text = entry_text
            if removed:
                target_text = f"{REMOVED_PREFIX}{entry_text}"
            break
        if target_line is None:
            self.logger.debug("Edit failed: memory line not found id=%s path=%s", memory_id, path)
            return False

        note = instructions.strip()
        replacement = f"- [{memory_id}] {target_text} (user note: {note})"
        updated_body = self._replace_line(body, target_line, replacement)
        updated_at = datetime.now(timezone.utc).isoformat()
        frontmatter["updated_at"] = updated_at
        frontmatter["last_updated_by_agent"] = actor
        frontmatter["tombstone"] = target_text.startswith(REMOVED_PREFIX)
        path.write_text(_render_markdown(frontmatter, updated_body), encoding="utf-8")
        self.index.upsert(
            {
                "id": memory_id,
                "domain": frontmatter.get("domain", path.stem),
                "created_at": frontmatter.get("created_at", updated_at),
                "updated_at": updated_at,
                "confidence": None,
                "tags": [frontmatter.get("domain", path.stem)],
                "archived": False,
                "tombstone": target_text.startswith(REMOVED_PREFIX),
                "created_by_agent": frontmatter.get("created_by_agent", actor),
                "last_updated_by_agent": actor,
            },
            path,
        )
        self.events.append(
            "memory_edited",
            {"memory_id": memory_id, "path": str(path), "instructions": instructions},
        )
        self.logger.info("Memory edited id=%s path=%s", memory_id, path)
        return True
