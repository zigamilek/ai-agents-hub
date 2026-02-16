from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ai_agents_hub.logging_setup import get_logger


class ObsidianJournalWriter:
    def __init__(self, vault_path: Path, daily_notes_dir: str, write_mode: str = "append"):
        self.vault_path = vault_path
        self.daily_notes_dir = daily_notes_dir
        self.write_mode = write_mode
        self.logger = get_logger(__name__)

    def append_entry(self, *, heading: str, content: str) -> Path:
        now = datetime.now(timezone.utc)
        day = now.date().isoformat()
        time_str = now.strftime("%H:%M UTC")
        target_dir = self.vault_path / self.daily_notes_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{day}.md"
        block = (
            f"\n## {time_str} - {heading.strip() or 'Conversation'}\n\n"
            f"{content.strip()}\n"
        )
        if self.write_mode == "replace":
            target_file.write_text(block.strip() + "\n", encoding="utf-8")
        else:
            with target_file.open("a", encoding="utf-8") as f:
                f.write(block)
        self.logger.debug("Journal updated path=%s mode=%s", target_file, self.write_mode)
        return target_file
