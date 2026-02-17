from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ai_agents_hub.config import AppConfig
from ai_agents_hub.logging_setup import get_logger
from ai_agents_hub.orchestration.specialists import SPECIALISTS, get_specialist, normalize_domain
from ai_agents_hub.providers.litellm_router import LiteLLMRouter

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class SpecialistRoute:
    domain: str
    confidence: float
    reason: str
    classifier_model: str | None


def _response_to_dict(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    if hasattr(chunk, "model_dump"):
        return chunk.model_dump(exclude_none=True)  # type: ignore[no-any-return]
    if hasattr(chunk, "dict"):
        return chunk.dict()  # type: ignore[no-any-return]
    raise TypeError(f"Unsupported response type: {type(chunk)}")


def _extract_text(response: dict[str, Any]) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except Exception:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"].strip())
        return "\n".join([part for part in parts if part]).strip()
    return ""


def _extract_json_payload(text: str) -> dict[str, Any]:
    candidate = text.strip()
    match = JSON_BLOCK_RE.search(candidate)
    if match:
        candidate = match.group(1).strip()
    else:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = candidate[start : end + 1]
    try:
        loaded = json.loads(candidate)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


class SpecialistRouter:
    def __init__(self, *, config: AppConfig, llm_router: LiteLLMRouter) -> None:
        self.config = config
        self.llm_router = llm_router
        self.logger = get_logger(__name__)
        self.allowed_domains = [profile.domain for profile in SPECIALISTS]

    @property
    def model(self) -> str:
        return self.config.models.default_chat

    async def classify(self, latest_user_text: str) -> SpecialistRoute:
        user_text = latest_user_text.strip()
        if not user_text:
            return SpecialistRoute(
                domain="general",
                confidence=0.0,
                reason="empty-user-message",
                classifier_model=None,
            )

        specialist_lines = "\n".join(
            f"- {profile.domain}: {profile.routing_hint}" for profile in SPECIALISTS
        )
        system_prompt = (
            "You are the routing classifier for AI Agents Hub.\n"
            "Your job: choose exactly ONE specialist for the latest user message.\n"
            "Always respond with ONLY a single JSON object and nothing else.\n"
            "Do not include markdown, code fences, commentary, or extra keys.\n"
            "JSON schema:\n"
            '{'
            '"specialist":"<one of allowed domains>",'
            '"confidence":<float 0..1>,'
            '"reason":"<short reason>"'
            '}\n'
            "If unsure, choose general.\n"
            "Allowed specialists:\n"
            f"{specialist_lines}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        try:
            used_model, raw = await self.llm_router.chat_completion(
                primary_model=self.model,
                messages=messages,
                stream=False,
                passthrough={"temperature": 0.0, "max_tokens": 120},
            )
            parsed = _response_to_dict(raw)
            text = _extract_text(parsed)
            payload = _extract_json_payload(text)
            domain = normalize_domain(str(payload.get("specialist", "") or ""))
            if domain not in self.allowed_domains:
                self.logger.warning(
                    "Classifier returned invalid specialist '%s'; using general.", domain
                )
                return SpecialistRoute(
                    domain="general",
                    confidence=0.0,
                    reason="invalid-specialist",
                    classifier_model=used_model,
                )
            confidence_raw = payload.get("confidence", 0.0)
            try:
                confidence = float(confidence_raw)
            except Exception:
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            reason = str(payload.get("reason", "") or "").strip()
            chosen = get_specialist(domain)
            self.logger.debug(
                "Classifier routed domain=%s confidence=%.2f reason=%s model=%s",
                chosen.domain,
                confidence,
                reason,
                used_model,
            )
            return SpecialistRoute(
                domain=chosen.domain,
                confidence=confidence,
                reason=reason,
                classifier_model=used_model,
            )
        except Exception as exc:
            self.logger.warning(
                "Classifier routing failed model=%s error=%s",
                self.model,
                exc.__class__.__name__,
            )
            self.logger.debug("Classifier routing details: %s", str(exc))
            return SpecialistRoute(
                domain="general",
                confidence=0.0,
                reason=f"classifier-error:{exc.__class__.__name__}",
                classifier_model=None,
            )
