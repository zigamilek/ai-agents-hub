from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryEvents:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        (self.root_path / "_events").mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        day = now.date().isoformat()
        event_file = self.root_path / "_events" / f"{day}.jsonl"
        record = {
            "timestamp": now.isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with event_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
