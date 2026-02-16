from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from ai_agents_hub.api.openai_compat import create_openai_router
from ai_agents_hub.config import AppConfig, load_config
from ai_agents_hub.diagnostics import diagnostics_payload, health_payload, readiness_payload
from ai_agents_hub.journal.obsidian_writer import ObsidianJournalWriter
from ai_agents_hub.logging_setup import configure_logging, get_logger
from ai_agents_hub.memory.curator import MemoryCurator
from ai_agents_hub.memory.store import MemoryStore
from ai_agents_hub.orchestration.supervisor import Supervisor
from ai_agents_hub.prompts.manager import PromptManager
from ai_agents_hub.providers.litellm_router import LiteLLMRouter
from ai_agents_hub.tools.runner import ToolRunner


def _ensure_runtime_dirs(config: AppConfig) -> None:
    config.memory.root_path.mkdir(parents=True, exist_ok=True)
    if config.journal.enabled:
        config.journal.obsidian_vault_path.mkdir(parents=True, exist_ok=True)
    config.specialists.prompts.directory.mkdir(parents=True, exist_ok=True)
    if config.logging.output in {"file", "both"}:
        config.logging.directory.mkdir(parents=True, exist_ok=True)


def _build_services(config: AppConfig) -> dict[str, Any]:
    _ensure_runtime_dirs(config)
    memory_store = MemoryStore(config.memory.root_path)
    llm_router = LiteLLMRouter(config)
    memory_curator = MemoryCurator(
        config=config,
        llm_router=llm_router,
        memory_store=memory_store,
    )
    tool_runner = ToolRunner(config)
    prompt_manager = PromptManager(config)
    journal_writer = (
        ObsidianJournalWriter(
            vault_path=config.journal.obsidian_vault_path,
            daily_notes_dir=config.journal.daily_notes_dir,
            write_mode=config.journal.write_mode,
        )
        if config.journal.enabled
        else None
    )
    supervisor = Supervisor(
        config=config,
        llm_router=llm_router,
        memory_store=memory_store,
        memory_curator=memory_curator,
        tool_runner=tool_runner,
        prompt_manager=prompt_manager,
        journal_writer=journal_writer,
    )
    return {
        "config": config,
        "memory_store": memory_store,
        "memory_curator": memory_curator,
        "llm_router": llm_router,
        "tool_runner": tool_runner,
        "prompt_manager": prompt_manager,
        "journal_writer": journal_writer,
        "supervisor": supervisor,
    }


def create_app(config_path: str | Path | None = None) -> FastAPI:
    config = load_config(config_path)
    configure_logging(config.logging)
    logger = get_logger(__name__)
    logger.info("Initializing AI Agents Hub app...")

    services = _build_services(config)
    logger.info(
        "Services initialized (memory_root=%s, journal_enabled=%s, prompts_dir=%s)",
        config.memory.root_path,
        config.journal.enabled,
        config.specialists.prompts.directory,
    )

    app = FastAPI(title="AI Agents Hub", version="0.1.0")
    app.state.services = services
    app.include_router(create_openai_router())

    endpoints = config.diagnostics.endpoints

    @app.get(endpoints.health, tags=["diagnostics"])
    async def healthz() -> dict[str, Any]:
        return health_payload()

    @app.get(endpoints.readiness, tags=["diagnostics"])
    async def readyz() -> dict[str, Any]:
        return readiness_payload(config)

    @app.get(endpoints.diagnostics, tags=["diagnostics"])
    async def diagnostics() -> dict[str, Any]:
        return diagnostics_payload(
            config=config,
            memory_store=services["memory_store"],
            llm_router=services["llm_router"],
            prompt_manager=services["prompt_manager"],
        )

    logger.info(
        "Diagnostics routes active (%s, %s, %s)",
        endpoints.health,
        endpoints.readiness,
        endpoints.diagnostics,
    )

    return app


app = create_app()
