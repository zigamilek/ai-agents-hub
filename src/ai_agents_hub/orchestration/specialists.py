from __future__ import annotations

from ai_agents_hub.specialist_catalog import (
    SPECIALIST_CATALOG,
    SPECIALISTS_BY_DOMAIN,
    SpecialistDefinition,
    normalize_domain,
)

SpecialistProfile = SpecialistDefinition
SPECIALISTS: tuple[SpecialistProfile, ...] = SPECIALIST_CATALOG


def get_specialist(domain: str) -> SpecialistProfile:
    normalized = normalize_domain(domain)
    return SPECIALISTS_BY_DOMAIN.get(normalized, SPECIALISTS_BY_DOMAIN["general"])
