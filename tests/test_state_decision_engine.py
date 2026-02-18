from __future__ import annotations

import asyncio
import json
from typing import Any

from mobius.config import AppConfig
from mobius.state.decision_engine import StateDecisionEngine
from mobius.state.models import StateContextSnapshot


class FailingLLMRouter:
    async def chat_completion(
        self,
        *,
        primary_model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        passthrough: dict[str, Any] | None = None,
        include_fallbacks: bool = True,
    ) -> tuple[str, Any]:
        raise RuntimeError("forced failure for fallback test")


class StubLLMRouter:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def chat_completion(
        self,
        *,
        primary_model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        passthrough: dict[str, Any] | None = None,
        include_fallbacks: bool = True,
    ) -> tuple[str, Any]:
        return primary_model, {"choices": [{"message": {"content": json.dumps(self.payload)}}]}


class SequencedLLMRouter:
    def __init__(self, payloads: list[str]) -> None:
        self.payloads = payloads
        self.calls = 0

    async def chat_completion(
        self,
        *,
        primary_model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        passthrough: dict[str, Any] | None = None,
        include_fallbacks: bool = True,
    ) -> tuple[str, Any]:
        idx = min(self.calls, len(self.payloads) - 1)
        self.calls += 1
        return primary_model, {"choices": [{"message": {"content": self.payloads[idx]}}]}


def _config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "server": {"api_keys": ["dev-key"]},
            "providers": {
                "openai": {"api_key": "test-openai-key"},
                "gemini": {"api_key": "test-gemini-key"},
            },
            "models": {"orchestrator": "gpt-5-nano-2025-08-07", "fallbacks": []},
            "api": {"public_model_id": "mobius"},
            "specialists": {
                "prompts_directory": "./system_prompts",
                "orchestrator_prompt_file": "_orchestrator.md",
                "by_domain": {
                    "general": {"model": "gpt-5.2", "prompt_file": "general.md"},
                    "health": {"model": "gpt-5.2", "prompt_file": "health.md"},
                    "parenting": {"model": "gpt-5.2", "prompt_file": "parenting.md"},
                    "relationships": {"model": "gpt-5.2", "prompt_file": "relationships.md"},
                    "homelab": {"model": "gpt-5.2", "prompt_file": "homelab.md"},
                    "personal_development": {
                        "model": "gpt-5.2",
                        "prompt_file": "personal_development.md",
                    },
                },
            },
            "state": {
                "enabled": False,
                "decision": {"enabled": True},
                "checkin": {"enabled": True},
                "journal": {"enabled": True},
                "memory": {"enabled": True},
            },
        }
    )


def test_model_failure_returns_no_writes() -> None:
    cfg = _config()
    engine = StateDecisionEngine(
        config=cfg,
        llm_router=FailingLLMRouter(),  # type: ignore[arg-type]
    )
    decision = asyncio.run(
        engine.decide(
            user_text="Today I decided I'll finally lose fat.",
            assistant_text="Great, let's define a plan.",
            routed_domain="health",
            context=StateContextSnapshot(),
        )
    )
    assert decision.checkin is None
    assert decision.journal is None
    assert decision.memory is None
    assert decision.reason == "state-model-unavailable"
    assert decision.is_failure is True


def test_model_json_can_trigger_all_three_write_types() -> None:
    cfg = _config()
    payload = {
        "checkin": {
            "write": True,
            "domain": "health",
            "track_type": "goal",
            "title": "Lose fat",
            "summary": "Started focused fat-loss plan.",
            "outcome": "partial",
            "confidence": 0.84,
            "wins": ["Committed to meal prep"],
            "barriers": ["Late-night snacking"],
            "next_actions": ["Prepare tomorrow meals in advance"],
            "tags": ["fat_loss"],
        },
        "journal": {
            "write": True,
            "title": "Lose fat commitment",
            "body_md": "Today I committed to a consistent fat-loss process.",
            "domain_hints": ["health"],
        },
        "memory": {
            "write": True,
            "domain": "health",
            "title": "Recurring fat-loss goal",
            "summary": "User repeatedly re-commits to losing fat.",
            "narrative": "Pattern appears repeatedly over months.",
            "confidence": 0.79,
            "tags": ["fat_loss", "recurring_goal"],
        },
        "reason": "explicit_goal_signal",
    }
    engine = StateDecisionEngine(
        config=cfg,
        llm_router=StubLLMRouter(payload),  # type: ignore[arg-type]
    )
    decision = asyncio.run(
        engine.decide(
            user_text="Today I decided I'll finally lose fat.",
            assistant_text="Great, let's define a plan.",
            routed_domain="health",
            context=StateContextSnapshot(),
        )
    )
    assert decision.checkin is not None
    assert decision.journal is not None
    assert decision.memory is not None
    assert decision.reason == "explicit_goal_signal"


def test_invalid_json_is_retried_and_second_attempt_succeeds() -> None:
    cfg = _config()
    cfg.state.decision.max_json_retries = 1
    valid_payload = {
        "checkin": {
            "write": True,
            "domain": "health",
            "track_type": "goal",
            "title": "Lose fat",
            "summary": "Progressing.",
            "outcome": "partial",
            "confidence": 0.7,
            "wins": [],
            "barriers": [],
            "next_actions": [],
            "tags": [],
        },
        "journal": {
            "write": False,
            "title": "",
            "body_md": "",
            "domain_hints": [],
        },
        "memory": {
            "write": False,
            "domain": "",
            "title": "",
            "summary": "",
            "narrative": "",
            "confidence": None,
            "tags": [],
        },
        "reason": "checkin_only",
    }
    router = SequencedLLMRouter(["not json", json.dumps(valid_payload)])
    engine = StateDecisionEngine(
        config=cfg,
        llm_router=router,  # type: ignore[arg-type]
    )
    decision = asyncio.run(
        engine.decide(
            user_text="Quick update on my fat-loss progress.",
            assistant_text="Thanks.",
            routed_domain="health",
            context=StateContextSnapshot(),
        )
    )
    assert router.calls == 2
    assert decision.checkin is not None
    assert decision.journal is None
    assert decision.memory is None
