from __future__ import annotations

from pathlib import Path

from ai_agents_hub.config import AppConfig
from ai_agents_hub.prompts.manager import DEFAULT_PROMPTS, PromptManager


def _config(prompt_dir: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "server": {"api_keys": []},
            "providers": {
                "openai": {"api_key": "test-openai-key"},
                "gemini": {
                    "api_key": "test-gemini-key",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                },
            },
            "models": {"orchestrator": "gpt-5-nano-2025-08-07", "fallbacks": []},
            "api": {
                "public_model_id": "ai-agents-hub",
                "allow_provider_model_passthrough": False,
            },
            "specialists": {
                "prompts_directory": str(prompt_dir),
                "auto_reload": True,
                "orchestrator_prompt_file": "orchestrator.md",
                "by_domain": {
                    "general": {"model": "gpt-4o-mini", "prompt_file": "general.md"},
                    "health": {"model": "gpt-4o-mini", "prompt_file": "health.md"},
                    "parenting": {
                        "model": "gpt-4o-mini",
                        "prompt_file": "parenting.md",
                    },
                    "relationships": {
                        "model": "gpt-4o-mini",
                        "prompt_file": "relationships.md",
                    },
                    "homelab": {"model": "gemini-2.5-flash", "prompt_file": "homelab.md"},
                    "personal_development": {
                        "model": "gpt-4o-mini",
                        "prompt_file": "personal_development.md",
                    },
                },
            },
        }
    )


def test_missing_prompt_file_uses_fallback(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "general.md").write_text("General from file", encoding="utf-8")

    config = _config(prompt_dir)
    manager = PromptManager(config)

    assert manager.get("general") == "General from file"
    assert manager.get("health") == DEFAULT_PROMPTS["health"]


def test_prompt_auto_reload_on_change(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for key in (
        "orchestrator",
        "general",
        "health",
        "parenting",
        "relationships",
        "homelab",
        "personal_development",
    ):
        (prompt_dir / f"{key}.md").write_text(f"{key} v1", encoding="utf-8")

    config = _config(prompt_dir)
    manager = PromptManager(config)
    assert manager.get("orchestrator") == "orchestrator v1"

    (prompt_dir / "orchestrator.md").write_text("orchestrator v2", encoding="utf-8")
    assert manager.get("orchestrator") == "orchestrator v2"
