from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from mobius.config import AppConfig
from mobius.state.models import StateContextSnapshot, StateDecision
from mobius.state.pipeline import StatePipeline


@dataclass
class _FakeStatus:
    ready: bool = True


@dataclass
class _FakeStateStore:
    status: _FakeStatus = field(default_factory=_FakeStatus)


class _FakeLLMRouter:
    pass


class _FakeStorage:
    def fetch_context_snapshot(
        self, *, user_key: str | None, routed_domain: str
    ) -> StateContextSnapshot:
        return StateContextSnapshot()


class _FailingDecisionEngine:
    async def decide(
        self,
        *,
        user_text: str,
        assistant_text: str,
        routed_domain: str,
        context: StateContextSnapshot,
    ) -> StateDecision:
        return StateDecision(reason="state-model-unavailable", is_failure=True)


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
                "enabled": True,
                "database": {"dsn": "postgresql://user:pass@localhost:5432/mobius"},
            },
        }
    )


def test_state_pipeline_emits_footer_warning_when_decision_fails() -> None:
    cfg = _config()
    cfg.state.decision.on_failure = "footer_warning"
    pipeline = StatePipeline(
        config=cfg,
        state_store=_FakeStateStore(),  # type: ignore[arg-type]
        llm_router=_FakeLLMRouter(),  # type: ignore[arg-type]
    )
    pipeline.storage = _FakeStorage()  # type: ignore[assignment]
    pipeline.decision_engine = _FailingDecisionEngine()  # type: ignore[assignment]

    footer = asyncio.run(
        pipeline.process_turn(
            request_user="alice",
            session_key="s1",
            routed_domain="health",
            user_text="Today update",
            assistant_text="Thanks",
            used_model="gpt-5.2",
            request_payload={
                "model": "mobius",
                "messages": [{"role": "user", "content": "Today update"}],
            },
        )
    )
    assert "*State warning:*" in footer
    assert "state-model-unavailable" in footer
    assert "state/users/alice/" in footer


def test_state_pipeline_can_silence_failure_footer() -> None:
    cfg = _config()
    cfg.state.decision.on_failure = "silent"
    pipeline = StatePipeline(
        config=cfg,
        state_store=_FakeStateStore(),  # type: ignore[arg-type]
        llm_router=_FakeLLMRouter(),  # type: ignore[arg-type]
    )
    pipeline.storage = _FakeStorage()  # type: ignore[assignment]
    pipeline.decision_engine = _FailingDecisionEngine()  # type: ignore[assignment]

    footer = asyncio.run(
        pipeline.process_turn(
            request_user="alice",
            session_key="s1",
            routed_domain="health",
            user_text="Today update",
            assistant_text="Thanks",
            used_model="gpt-5.2",
            request_payload={
                "model": "mobius",
                "messages": [{"role": "user", "content": "Today update"}],
            },
        )
    )
    assert footer == ""
