from __future__ import annotations

from pathlib import Path

from mobius.config import AppConfig
from mobius.orchestration.specialists import get_specialist, normalize_domain
from mobius.prompts.manager import PromptManager


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
                "public_model_id": "mobius",
                "allow_provider_model_passthrough": False,
            },
            "specialists": {
                "prompts_directory": str(prompt_dir),
                "auto_reload": True,
                "orchestrator_prompt_file": "_orchestrator.md",
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


def test_specialist_lookup_returns_general_for_unknown() -> None:
    specialist = get_specialist("not-a-domain")
    assert specialist.domain == "general"


def test_specialist_domain_normalization() -> None:
    assert normalize_domain("personal-development") == "personal_development"
    assert get_specialist("personal-development").domain == "personal_development"


def test_prompt_file_reload_and_general_prompt_override(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "_orchestrator.md": "Orchestrator prompt one",
        "general.md": "General prompt one",
        "health.md": "Health prompt",
        "parenting.md": "Parenting prompt",
        "relationships.md": "Relationships prompt",
        "homelab.md": "Homelab prompt",
        "personal_development.md": "Personal development prompt",
    }
    for name, content in files.items():
        (prompt_dir / name).write_text(content, encoding="utf-8")

    config = _config(prompt_dir)
    manager = PromptManager(config)
    assert manager.get("general") == "General prompt one"

    (prompt_dir / "general.md").write_text("General prompt two", encoding="utf-8")
    assert manager.get("general") == "General prompt two"
