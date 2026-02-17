from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialistProfile:
    domain: str
    label: str
    routing_hint: str


SPECIALISTS: tuple[SpecialistProfile, ...] = (
    SpecialistProfile(
        domain="general",
        label="General Specialist",
        routing_hint=(
            "Use for broad requests, unclear intent, mixed topics, or anything that does not "
            "clearly belong to another specialist."
        ),
    ),
    SpecialistProfile(
        domain="health",
        label="Health Specialist",
        routing_hint=(
            "Physical or mental health, symptoms, rehabilitation, fitness, sleep, nutrition, "
            "recovery, injury, medical-care planning."
        ),
    ),
    SpecialistProfile(
        domain="parenting",
        label="Parenting Specialist",
        routing_hint=(
            "Parent-child challenges, discipline, routines, school behavior, communication "
            "with children, age-appropriate parenting guidance."
        ),
    ),
    SpecialistProfile(
        domain="relationship",
        label="Relationship Specialist",
        routing_hint=(
            "Couple/partner issues, communication conflicts, boundaries, trust, intimacy, "
            "relationship repair and maintenance."
        ),
    ),
    SpecialistProfile(
        domain="homelab",
        label="Homelab Specialist",
        routing_hint=(
            "Homelab infrastructure, Proxmox, LXC, Docker, networking, server setup, backups, "
            "automation, observability, rollback-safe ops."
        ),
    ),
    SpecialistProfile(
        domain="personal_development",
        label="Personal Development Specialist",
        routing_hint=(
            "Habits, goals, productivity, planning, accountability, self-improvement, "
            "learning and personal growth."
        ),
    ),
)

SPECIALISTS_BY_DOMAIN: dict[str, SpecialistProfile] = {
    specialist.domain: specialist for specialist in SPECIALISTS
}


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().replace("-", "_")


def get_specialist(domain: str) -> SpecialistProfile:
    normalized = normalize_domain(domain)
    return SPECIALISTS_BY_DOMAIN.get(normalized, SPECIALISTS_BY_DOMAIN["general"])
