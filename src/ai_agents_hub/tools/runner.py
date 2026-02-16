from __future__ import annotations

import asyncio
from typing import Any

from ai_agents_hub.config import AppConfig
from ai_agents_hub.logging_setup import get_logger
from ai_agents_hub.tools.web_search import SearchSource, search_web

WEB_HINTS = ("search", "latest", "current", "news", "update", "web")


class ToolRunner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.logger = get_logger(__name__)

    @staticmethod
    def should_web_search(user_text: str) -> bool:
        lower = user_text.lower()
        return any(hint in lower for hint in WEB_HINTS)

    async def maybe_search(
        self, user_text: str, max_results: int = 5
    ) -> list[SearchSource]:
        if not self.config.tools.web_search:
            self.logger.debug("Web search disabled by config.")
            return []
        if not self.should_web_search(user_text):
            self.logger.debug("No web-search hint detected in user message.")
            return []
        self.logger.info("Running web search (max_results=%d).", max_results)
        try:
            results = await asyncio.to_thread(search_web, user_text, max_results)
        except Exception as exc:
            self.logger.warning("Web search failed: %s", exc.__class__.__name__)
            self.logger.debug("Web search error details: %s", str(exc))
            return []
        self.logger.debug("Web search returned %d source(s).", len(results))
        return results

    @staticmethod
    def sources_context_block(sources: list[SearchSource]) -> str:
        if not sources:
            return ""
        lines = [
            "Web search results are available. Use them and cite them as [S1], [S2], ... when referenced."
        ]
        for idx, source in enumerate(sources, start=1):
            lines.append(f"[S{idx}] {source.title} | {source.url}")
            if source.snippet:
                lines.append(f"Snippet: {source.snippet}")
        return "\n".join(lines)

    @staticmethod
    def serialize_sources(sources: list[SearchSource]) -> list[dict[str, Any]]:
        return [source.as_dict() for source in sources]
