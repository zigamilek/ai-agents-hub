from __future__ import annotations

import asyncio
from typing import Any

from ai_agents_hub.config import AppConfig
from ai_agents_hub.providers.litellm_router import LiteLLMRouter


def _config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "providers": {
                "openai": {"api_key": "openai-key"},
                "gemini": {
                    "api_key": "gemini-key",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                },
            },
            "models": {
                "orchestrator": "gpt-5-nano-2025-08-07",
                "specialists": {
                    "general": "gpt-4o-mini",
                    "health": "gpt-4o-mini",
                    "parenting": "gpt-4o-mini",
                    "relationships": "gpt-4o-mini",
                    "homelab": "gemini-2.5-flash",
                    "personal_development": "gpt-4o-mini",
                },
                "fallbacks": [],
            },
        }
    )


def test_gemini_model_is_rewritten_to_openai_prefix_for_call() -> None:
    router = LiteLLMRouter(_config())
    assert router._litellm_model_for_call("gemini-2.5-flash") == "openai/gemini-2.5-flash"


def test_non_gemini_model_is_not_rewritten() -> None:
    router = LiteLLMRouter(_config())
    assert router._litellm_model_for_call("gpt-4o-mini") == "gpt-4o-mini"


def test_already_prefixed_gemini_keeps_prefix_and_uses_gemini_credentials() -> None:
    router = LiteLLMRouter(_config())
    assert (
        router._litellm_model_for_call("openai/gemini-2.5-flash")
        == "openai/gemini-2.5-flash"
    )
    kwargs = router._provider_kwargs("openai/gemini-2.5-flash")
    assert kwargs["api_key"] == "gemini-key"
    assert kwargs["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_chat_completion_uses_rewritten_model(monkeypatch: Any) -> None:
    router = LiteLLMRouter(_config())
    seen: dict[str, Any] = {}

    async def fake_acompletion(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr("ai_agents_hub.providers.litellm_router.acompletion", fake_acompletion)

    used_model, response = asyncio.run(
        router.chat_completion(
            primary_model="gemini-2.5-flash",
            messages=[{"role": "user", "content": "hello"}],
            stream=False,
            passthrough=None,
            include_fallbacks=False,
        )
    )
    assert used_model == "gemini-2.5-flash"
    assert seen["model"] == "openai/gemini-2.5-flash"
    assert seen["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert seen["api_key"] == "gemini-key"
    assert response["choices"][0]["message"]["content"] == "ok"
