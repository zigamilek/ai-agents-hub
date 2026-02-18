from __future__ import annotations

from typing import Any

from litellm import acompletion, aembedding

from mobius.config import AppConfig
from mobius.logging_setup import get_logger


class LiteLLMRouter:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.logger = get_logger(__name__)

    def list_models(self) -> list[str]:
        specialist_models = [
            item.model for item in self.config.specialists.by_domain.values()
        ]
        candidates = {
            self.config.models.orchestrator,
            *specialist_models,
            *self.config.models.fallbacks,
        }
        return sorted([model for model in candidates if model])

    @staticmethod
    def _is_gemini_model(model: str) -> bool:
        lower = model.lower()
        return lower.startswith("gemini") or lower.startswith("openai/gemini")

    def _provider_kwargs(self, model: str) -> dict[str, Any]:
        if self._is_gemini_model(model):
            return {
                "api_key": self.config.providers.gemini.api_key,
                "base_url": self.config.providers.gemini.base_url,
            }
        return {
            "api_key": self.config.providers.openai.api_key,
            "base_url": self.config.providers.openai.base_url,
        }

    def _litellm_model_for_call(self, model: str) -> str:
        if not self._is_gemini_model(model):
            return model

        # Force Gemini to go through Google's OpenAI-compatible endpoint when
        # configured, avoiding accidental Vertex/Google SDK code paths.
        base_url = (self.config.providers.gemini.base_url or "").lower()
        if "/openai" not in base_url:
            return model
        if model.startswith("openai/"):
            return model
        return f"openai/{model}"

    @staticmethod
    def _clean(kwargs: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in kwargs.items() if v is not None}

    async def chat_completion(
        self,
        *,
        primary_model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        passthrough: dict[str, Any] | None = None,
        include_fallbacks: bool = True,
    ) -> tuple[str, Any]:
        models_to_try = (
            [primary_model, *self.config.models.fallbacks]
            if include_fallbacks
            else [primary_model]
        )
        seen: set[str] = set()
        ordered_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_error: Exception | None = None
        for model in ordered_models:
            try:
                self.logger.debug(
                    "Trying model=%s stream=%s fallback_count=%d",
                    model,
                    stream,
                    max(0, len(ordered_models) - 1),
                )
                litellm_model = self._litellm_model_for_call(model)
                call_kwargs = {
                    "model": litellm_model,
                    "messages": messages,
                    "stream": stream,
                    **self._provider_kwargs(model),
                    **(passthrough or {}),
                }
                response = await acompletion(**self._clean(call_kwargs))
                if model != primary_model:
                    self.logger.warning(
                        "Primary model failed, fallback model used: %s -> %s",
                        primary_model,
                        model,
                    )
                else:
                    self.logger.debug("Model request succeeded with primary model=%s", model)
                return model, response
            except Exception as exc:  # pragma: no cover - provider-dependent
                last_error = exc
                self.logger.warning(
                    "Model call failed for model=%s error=%s",
                    model,
                    exc.__class__.__name__,
                )
                self.logger.debug("Model failure details: %s", str(exc))
                continue

        if last_error is not None:
            self.logger.error("All model candidates failed.")
            raise last_error
        raise RuntimeError("No model candidates configured.")

    async def embedding(
        self,
        *,
        primary_model: str,
        input_text: str,
        include_fallbacks: bool = False,
    ) -> tuple[str, list[float]]:
        if not input_text.strip():
            raise ValueError("Embedding input text must not be empty.")

        models_to_try = (
            [primary_model, *self.config.models.fallbacks]
            if include_fallbacks
            else [primary_model]
        )
        seen: set[str] = set()
        ordered_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_error: Exception | None = None
        for model in ordered_models:
            try:
                litellm_model = self._litellm_model_for_call(model)
                call_kwargs = {
                    "model": litellm_model,
                    "input": input_text,
                    **self._provider_kwargs(model),
                }
                raw = await aembedding(**self._clean(call_kwargs))
                parsed = self._response_to_dict(raw)
                vector = self._extract_embedding(parsed)
                if model != primary_model:
                    self.logger.warning(
                        "Primary embedding model failed, fallback used: %s -> %s",
                        primary_model,
                        model,
                    )
                return model, vector
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "Embedding call failed for model=%s error=%s",
                    model,
                    exc.__class__.__name__,
                )
                self.logger.debug("Embedding failure details: %s", str(exc))
                continue

        if last_error is not None:
            raise last_error
        raise RuntimeError("No embedding model candidates configured.")

    @staticmethod
    def _response_to_dict(chunk: Any) -> dict[str, Any]:
        if isinstance(chunk, dict):
            return chunk
        if hasattr(chunk, "model_dump"):
            return chunk.model_dump(exclude_none=True)  # type: ignore[no-any-return]
        if hasattr(chunk, "dict"):
            return chunk.dict()  # type: ignore[no-any-return]
        return {}

    @staticmethod
    def _extract_embedding(response: dict[str, Any]) -> list[float]:
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Embedding response missing data.")
        first = data[0]
        if not isinstance(first, dict):
            raise ValueError("Embedding response has invalid item.")
        vector = first.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError("Embedding vector is missing.")
        normalized: list[float] = []
        for value in vector:
            normalized.append(float(value))
        return normalized
