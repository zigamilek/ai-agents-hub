from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from duckduckgo_search import DDGS
except Exception:  # pragma: no cover - optional dependency at runtime
    DDGS = None  # type: ignore[assignment]


@dataclass
class SearchSource:
    title: str
    url: str
    snippet: str
    fetched_at: str
    source: str = "duckduckgo"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def search_web(query: str, max_results: int = 5) -> list[SearchSource]:
    if DDGS is None:
        return []
    timestamp = datetime.now(timezone.utc).isoformat()
    results: list[SearchSource] = []
    with DDGS() as ddgs:
        items = ddgs.text(query, max_results=max_results)
        for item in items:
            title = str(item.get("title", "")).strip()
            href = str(item.get("href", "")).strip()
            snippet = str(item.get("body", "")).strip()
            if not title or not href:
                continue
            results.append(
                SearchSource(
                    title=title,
                    url=href,
                    snippet=snippet,
                    fetched_at=timestamp,
                )
            )
    return results
