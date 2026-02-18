from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialistDefinition:
    domain: str
    label: str
    routing_hint: str


SPECIALIST_CATALOG: tuple[SpecialistDefinition, ...] = (
    SpecialistDefinition(
        domain="general",
        label="General Specialist",
        routing_hint=(
            "Use for broad requests, unclear intent, mixed topics, or anything that does not "
            "clearly belong to another specialist."
        ),
    ),
    SpecialistDefinition(
        domain="health",
        label="Health Specialist",
        routing_hint=(
            "Physical or mental health, symptoms, rehabilitation, fitness, sleep, nutrition, "
            "recovery, injury, medical-care planning."
        ),
    ),
    SpecialistDefinition(
        domain="parenting",
        label="Parenting Specialist",
        routing_hint=(
            "Parent-child challenges, discipline, routines, school behavior, communication "
            "with children, age-appropriate parenting guidance."
        ),
    ),
    SpecialistDefinition(
        domain="relationships",
        label="Relationships Specialist",
        routing_hint=(
            "Couple/partner issues, communication conflicts, boundaries, trust, intimacy, "
            "repairing and maintaining relationships."
        ),
    ),
    SpecialistDefinition(
        domain="homelab",
        label="Homelab Specialist",
        routing_hint=(
            "Homelab infrastructure, Proxmox, LXC, Docker, networking, server setup, backups, "
            "automation, observability, rollback-safe ops."
        ),
    ),
    SpecialistDefinition(
        domain="personal_development",
        label="Personal Development Specialist",
        routing_hint=(
            "Habits, goals, productivity, planning, accountability, self-improvement, "
            "learning and personal growth."
        ),
    ),
)

SPECIALIST_DOMAINS: tuple[str, ...] = tuple(item.domain for item in SPECIALIST_CATALOG)

SPECIALISTS_BY_DOMAIN: dict[str, SpecialistDefinition] = {
    specialist.domain: specialist for specialist in SPECIALIST_CATALOG
}


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().replace("-", "_")

