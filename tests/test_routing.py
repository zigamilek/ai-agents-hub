from __future__ import annotations

from pathlib import Path

from ai_agents_hub.config import AppConfig
from ai_agents_hub.orchestration.specialists import rank_specialists
from ai_agents_hub.prompts.manager import PromptManager


def test_health_specialist_ranked_first() -> None:
    ranked = rank_specialists("I need help improving sleep and workout recovery")
    assert ranked
    assert ranked[0][0].domain == "health"
    assert ranked[0][1] >= 0.6


def test_homelab_specialist_detected() -> None:
    ranked = rank_specialists("Proxmox LXC backup strategy with docker on my homelab")
    domains = [profile.domain for profile, _ in ranked]
    assert "homelab" in domains


def test_prompt_file_reload_and_general_prompt_override(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "supervisor.md": "Supervisor prompt one",
        "general.md": "General prompt one",
        "health.md": "Health prompt",
        "parenting.md": "Parenting prompt",
        "relationship.md": "Relationship prompt",
        "homelab.md": "Homelab prompt",
        "personal_development.md": "Personal development prompt",
    }
    for name, content in files.items():
        (prompt_dir / name).write_text(content, encoding="utf-8")

    config = AppConfig.model_validate(
        {
            "specialists": {
                "prompts": {
                    "directory": str(prompt_dir),
                    "auto_reload": True,
                }
            }
        }
    )
    manager = PromptManager(config)
    assert manager.get("general") == "General prompt one"

    (prompt_dir / "general.md").write_text("General prompt two", encoding="utf-8")
    assert manager.get("general") == "General prompt two"
