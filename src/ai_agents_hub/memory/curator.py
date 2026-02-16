from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ai_agents_hub.config import AppConfig
from ai_agents_hub.logging_setup import get_logger
from ai_agents_hub.memory.store import MemoryRecord, MemoryStore
from ai_agents_hub.providers.litellm_router import LiteLLMRouter

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass
class CuratorDecision:
    should_write: bool
    summary: str
    confidence: float
    reason: str


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
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text.strip())
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


class MemoryCurator:
    def __init__(
        self,
        *,
        config: AppConfig,
        llm_router: LiteLLMRouter,
        memory_store: MemoryStore,
    ) -> None:
        self.config = config
        self.llm_router = llm_router
        self.memory_store = memory_store
        self.logger = get_logger(__name__)

    @property
    def enabled(self) -> bool:
        return bool(self.config.memory.auto_write and self.config.memory.curator.enabled)

    @property
    def model(self) -> str:
        return self.config.memory.curator.model

    async def maybe_capture(
        self,
        *,
        domain: str,
        user_text: str,
        assistant_text: str,
    ) -> MemoryRecord | None:
        if not self.enabled:
            return None
        if not user_text.strip() or not assistant_text.strip():
            return None

        existing = self.memory_store.read_domain_memory(
            domain=domain,
            max_chars=self.config.memory.curator.max_existing_chars,
        )
        decision = await self._decide(
            domain=domain,
            user_text=user_text,
            assistant_text=assistant_text,
            existing_memory=existing,
        )

        summary = decision.summary.strip()
        if not decision.should_write or not summary:
            return None
        if decision.confidence < self.config.memory.curator.min_confidence:
            self.logger.debug(
                "Memory curator skipped write due to low confidence %.2f < %.2f",
                decision.confidence,
                self.config.memory.curator.min_confidence,
            )
            return None

        max_len = max(32, int(self.config.memory.curator.max_summary_chars))
        if len(summary) > max_len:
            summary = summary[: max_len - 1].rstrip() + "..."

        record = self.memory_store.write_memory(
            domain=domain,
            summary=summary,
            body="",
            confidence=decision.confidence,
            tags=[domain],
            created_by_agent="memory-curator",
        )
        if not record.created:
            return None
        return record

    async def _decide(
        self,
        *,
        domain: str,
        user_text: str,
        assistant_text: str,
        existing_memory: str,
    ) -> CuratorDecision:
        system_prompt = (
            "You are a memory curator for a personal multi-agent assistant.\n"
            "Your job is to decide whether the latest exchange should update long-term memory.\n"
            "Be very selective. Do NOT store temporary requests, greetings, or step-by-step chatter.\n"
            "Prefer stable preferences, ongoing problems, goals, recurring constraints, or project context.\n"
            "If existing memory already captures the same idea, do not write a duplicate.\n"
            "Return JSON only with keys:\n"
            '- "should_write": boolean\n'
            '- "summary": short lowercase-ish memory sentence (max 160 chars)\n'
            '- "confidence": number in [0,1]\n'
            '- "reason": short explanation\n'
        )
        user_prompt = (
            f"Domain: {domain}\n\n"
            "Existing domain memory (markdown):\n"
            f"{existing_memory or '(empty)'}\n\n"
            "Latest user message:\n"
            f"{user_text.strip()}\n\n"
            "Latest assistant reply:\n"
            f"{assistant_text.strip()}\n"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        candidates: list[str] = []
        for model_name in (self.model, self.config.models.default_chat):
            if model_name and model_name not in candidates:
                candidates.append(model_name)

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                used_model, raw = await self.llm_router.chat_completion(
                    primary_model=candidate,
                    messages=messages,
                    stream=False,
                    passthrough={"temperature": 0.1},
                )
                parsed = _response_to_dict(raw)
                text = _extract_text(parsed)
                payload = _extract_json_payload(text)
                should_write = bool(payload.get("should_write", False))
                summary = str(payload.get("summary", "") or "").strip()
                confidence_raw = payload.get("confidence", 0.0)
                try:
                    confidence = float(confidence_raw)
                except Exception:
                    confidence = 0.0
                confidence = max(0.0, min(1.0, confidence))
                reason = str(payload.get("reason", "") or "").strip()
                self.logger.debug(
                    "Memory curator decision model=%s domain=%s should_write=%s confidence=%.2f reason=%s summary=%s",
                    used_model,
                    domain,
                    should_write,
                    confidence,
                    reason,
                    summary,
                )
                return CuratorDecision(
                    should_write=should_write,
                    summary=summary,
                    confidence=confidence,
                    reason=reason,
                )
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "Memory curator failed for domain=%s model=%s error=%s",
                    domain,
                    candidate,
                    exc.__class__.__name__,
                )
                self.logger.debug("Memory curator failure details: %s", str(exc))

        error_name = last_error.__class__.__name__ if last_error else "UnknownError"
        return CuratorDecision(
            should_write=False,
            summary="",
            confidence=0.0,
            reason=f"curator-error:{error_name}",
        )
