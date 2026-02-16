from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SpecialistProfile:
    domain: str
    label: str
    system_prompt: str
    keywords: tuple[str, ...]


SPECIALISTS: tuple[SpecialistProfile, ...] = (
    SpecialistProfile(
        domain="health",
        label="Health Specialist",
        system_prompt=(
            "You are the health specialist. Be practical and cautious. "
            "Do not provide diagnosis claims; recommend professional care "
            "for high-risk symptoms."
        ),
        keywords=(
            "health",
            "sleep",
            "exercise",
            "workout",
            "nutrition",
            "diet",
            "symptom",
            "doctor",
            "supplement",
            "injury",
        ),
    ),
    SpecialistProfile(
        domain="parenting",
        label="Parenting Specialist",
        system_prompt=(
            "You are the parenting specialist. Give empathetic, actionable, "
            "age-appropriate guidance."
        ),
        keywords=("parent", "child", "kid", "baby", "school", "tantrum", "bedtime"),
    ),
    SpecialistProfile(
        domain="relationship",
        label="Relationship Specialist",
        system_prompt=(
            "You are the relationship specialist. Support respectful communication, "
            "boundaries, and practical conflict resolution."
        ),
        keywords=(
            "relationship",
            "partner",
            "couple",
            "wife",
            "husband",
            "girlfriend",
            "boyfriend",
            "conflict",
        ),
    ),
    SpecialistProfile(
        domain="homelab",
        label="Homelab Specialist",
        system_prompt=(
            "You are the homelab specialist. Prefer reliable, reproducible, "
            "ops-friendly solutions with clear steps and rollback notes."
        ),
        keywords=(
            "proxmox",
            "lxc",
            "docker",
            "kubernetes",
            "homelab",
            "nas",
            "server",
            "network",
            "ansible",
            "vpn",
        ),
    ),
    SpecialistProfile(
        domain="personal_development",
        label="Personal Development Specialist",
        system_prompt=(
            "You are the personal development specialist. Help with habits, "
            "planning, accountability, and measurable progress."
        ),
        keywords=(
            "habit",
            "focus",
            "goal",
            "journal",
            "reflection",
            "productivity",
            "learn",
            "career",
        ),
    ),
)


def rank_specialists(user_text: str) -> list[tuple[SpecialistProfile, float]]:
    text = user_text.lower()
    ranked: list[tuple[SpecialistProfile, float]] = []
    for specialist in SPECIALISTS:
        hits = 0
        for keyword in specialist.keywords:
            if keyword in text:
                hits += 1
        if hits:
            # Basic bounded confidence score, good enough for MVP.
            confidence = min(0.95, 0.4 + 0.1 * hits)
            ranked.append((specialist, confidence))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def specialist_prompt(specialists: Iterable[SpecialistProfile]) -> str:
    chosen = list(specialists)
    if not chosen:
        return (
            "You are a reliable general assistant. Return one coherent answer. "
            "Use concise structure and practical next steps."
        )
    joined = "\n".join(
        f"- {item.label} ({item.domain}): {item.system_prompt}" for item in chosen
    )
    return (
        "You are the supervisor-synthesizer. Combine specialist perspectives into "
        "one coherent response with no contradictions.\n"
        f"{joined}"
    )
