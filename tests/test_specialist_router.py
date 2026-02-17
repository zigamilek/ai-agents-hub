from __future__ import annotations

import asyncio
from typing import Any

from ai_agents_hub.config import AppConfig
from ai_agents_hub.orchestration.specialist_router import SpecialistRouter


class StubLLMRouter:
    def __init__(self, outputs: list[str], model_name: str = "gpt-5-nano-2025-08-07") -> None:
        self.outputs = outputs
        self.model_name = model_name
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
        content = self.outputs.pop(0)
        return self.model_name, {"choices": [{"message": {"content": content}}]}


def _config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "models": {
                "default_chat": "gpt-5-nano-2025-08-07",
                "routing": {
                    "general": "gpt-4o-mini",
                    "health": "gpt-4o-mini",
                    "parenting": "gpt-4o-mini",
                    "relationship": "gpt-4o-mini",
                    "homelab": "gemini-2.5-flash",
                    "personal_development": "gpt-4o-mini",
                },
            }
        }
    )


def test_classifier_routes_to_health_domain() -> None:
    llm = StubLLMRouter(
        outputs=[
            '{"specialist":"health","confidence":0.92,"reason":"rehabilitation and injury context"}'
        ]
    )
    router = SpecialistRouter(config=_config(), llm_router=llm)  # type: ignore[arg-type]
    result = asyncio.run(router.classify("Can you help with tennis elbow rehab?"))
    assert result.domain == "health"
    assert result.confidence == 0.92
    assert result.classifier_model == "gpt-5-nano-2025-08-07"


def test_classifier_falls_back_to_general_for_invalid_specialist() -> None:
    llm = StubLLMRouter(
        outputs=[
            '{"specialist":"finance","confidence":0.9,"reason":"not supported"}'
        ]
    )
    router = SpecialistRouter(config=_config(), llm_router=llm)  # type: ignore[arg-type]
    result = asyncio.run(router.classify("How should I budget this month?"))
    assert result.domain == "general"
    assert result.reason == "invalid-specialist"


def test_classifier_falls_back_to_general_for_invalid_json() -> None:
    llm = StubLLMRouter(outputs=["not json"])
    router = SpecialistRouter(config=_config(), llm_router=llm)  # type: ignore[arg-type]
    result = asyncio.run(router.classify("I need advice"))
    assert result.domain == "general"
    assert result.reason == "invalid-specialist"
