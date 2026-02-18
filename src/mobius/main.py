from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from mobius.api.openai_compatible_api import create_openai_router
from mobius.config import AppConfig, load_config
from mobius.diagnostics import diagnostics_payload, health_payload, readiness_payload
from mobius.logging_setup import configure_logging, get_logger
from mobius.orchestration.orchestrator import Orchestrator
from mobius.orchestration.specialist_router import SpecialistRouter
from mobius.prompts.manager import PromptManager
from mobius.providers.litellm_router import LiteLLMRouter
from mobius.state.store import StateStore


def _ensure_runtime_dirs(config: AppConfig) -> None:
    config.specialists.prompts_directory.mkdir(parents=True, exist_ok=True)
    if config.logging.output in {"file", "both"}:
        config.logging.directory.mkdir(parents=True, exist_ok=True)
    if config.state.enabled:
        config.state.projection.output_directory.mkdir(parents=True, exist_ok=True)


def _build_services(config: AppConfig) -> dict[str, Any]:
    _ensure_runtime_dirs(config)
    state_store = StateStore(config.state)
    state_store.initialize()
    llm_router = LiteLLMRouter(config)
    specialist_router = SpecialistRouter(config=config, llm_router=llm_router)
    prompt_manager = PromptManager(config)
    orchestrator = Orchestrator(
        config=config,
        llm_router=llm_router,
        specialist_router=specialist_router,
        prompt_manager=prompt_manager,
    )
    return {
        "config": config,
        "state_store": state_store,
        "specialist_router": specialist_router,
        "llm_router": llm_router,
        "prompt_manager": prompt_manager,
        "orchestrator": orchestrator,
    }


def create_app(config_path: str | Path | None = None) -> FastAPI:
    config = load_config(config_path)
    configure_logging(config.logging)
    logger = get_logger(__name__)
    logger.info("Initializing Mobius app...")

    services = _build_services(config)
    logger.info(
        "Services initialized (orchestrator_model=%s, prompts_dir=%s, state_enabled=%s, state_ready=%s)",
        config.models.orchestrator,
        config.specialists.prompts_directory,
        config.state.enabled,
        services["state_store"].status.ready,
    )

    app = FastAPI(title="Mobius", version="0.1.0")
    app.state.services = services
    app.include_router(create_openai_router())

    endpoints = config.diagnostics.endpoints

    @app.get(endpoints.health, tags=["diagnostics"])
    async def healthz() -> dict[str, Any]:
        return health_payload()

    @app.get(endpoints.readiness, tags=["diagnostics"])
    async def readyz() -> dict[str, Any]:
        return readiness_payload(config, state_store=services["state_store"])

    @app.get(endpoints.diagnostics, tags=["diagnostics"])
    async def diagnostics() -> dict[str, Any]:
        return diagnostics_payload(
            config=config,
            llm_router=services["llm_router"],
            prompt_manager=services["prompt_manager"],
            state_store=services["state_store"],
        )

    logger.info(
        "Diagnostics routes active (%s, %s, %s)",
        endpoints.health,
        endpoints.readiness,
        endpoints.diagnostics,
    )

    return app


app = create_app()
