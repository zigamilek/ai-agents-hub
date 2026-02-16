from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ai_agents_hub.config import AppConfig
from ai_agents_hub.memory.curator import MemoryCurator
from ai_agents_hub.memory.store import MemoryStore


class StubLLMRouter:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    async def chat_completion(
        self,
        *,
        primary_model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        passthrough: dict[str, Any] | None = None,
    ) -> tuple[str, Any]:
        self.calls.append(
            {
                "primary_model": primary_model,
                "messages": messages,
                "stream": stream,
                "passthrough": passthrough or {},
            }
        )
        text = self.outputs.pop(0)
        return primary_model, {"choices": [{"message": {"content": text}}]}


def _build_config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "memory": {
                "root_path": str(tmp_path / "memories"),
                "curator": {
                    "enabled": True,
                    "model": "gemini-2.5-flash",
                    "min_confidence": 0.55,
                    "max_existing_chars": 8000,
                    "max_summary_chars": 160,
                },
            }
        }
    )


def test_memory_curator_writes_selected_memory(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    store = MemoryStore(config.memory.root_path)
    router = StubLLMRouter(
        outputs=[
            '{"should_write": true, "summary": "interested in tennis elbow rehabilitation", "confidence": 0.88, "reason": "stable health topic"}'
        ]
    )
    curator = MemoryCurator(config=config, llm_router=router, memory_store=store)  # type: ignore[arg-type]

    record = asyncio.run(
        curator.maybe_capture(
            domain="health",
            user_text="Can you help me construct a rehabilitation program for tennis elbow?",
            assistant_text="Sure. We can design a progressive program.",
        )
    )
    assert record is not None
    assert record.summary == "interested in tennis elbow rehabilitation"
    assert (config.memory.root_path / "domains" / "health.md").exists()


def test_memory_curator_skips_duplicate_summary(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    store = MemoryStore(config.memory.root_path)
    router = StubLLMRouter(
        outputs=[
            '{"should_write": true, "summary": "looking to solve son\'s disobedience", "confidence": 0.90, "reason": "recurring parenting concern"}',
            '{"should_write": true, "summary": "looking to solve son\'s disobedience", "confidence": 0.92, "reason": "same concern"}',
        ]
    )
    curator = MemoryCurator(config=config, llm_router=router, memory_store=store)  # type: ignore[arg-type]

    first = asyncio.run(
        curator.maybe_capture(
            domain="parenting",
            user_text="How can I make my son obey my instructions?",
            assistant_text="Let's focus on calm boundaries and consistency.",
        )
    )
    second = asyncio.run(
        curator.maybe_capture(
            domain="parenting",
            user_text="He still ignores me after school.",
            assistant_text="Try one instruction at a time and clear consequences.",
        )
    )

    assert first is not None
    assert second is None
    content = (config.memory.root_path / "domains" / "parenting.md").read_text(
        encoding="utf-8"
    )
    assert content.count("looking to solve son's disobedience") == 1


def test_memory_curator_skips_low_confidence(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    store = MemoryStore(config.memory.root_path)
    router = StubLLMRouter(
        outputs=[
            '{"should_write": true, "summary": "asked for one-off dinner ideas", "confidence": 0.20, "reason": "not durable"}'
        ]
    )
    curator = MemoryCurator(config=config, llm_router=router, memory_store=store)  # type: ignore[arg-type]

    record = asyncio.run(
        curator.maybe_capture(
            domain="general",
            user_text="What should I cook tonight?",
            assistant_text="How about pasta with vegetables?",
        )
    )
    assert record is None
    assert not (config.memory.root_path / "domains" / "general.md").exists()
