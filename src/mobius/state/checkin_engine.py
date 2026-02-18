from __future__ import annotations

from mobius.logging_setup import get_logger
from mobius.state.models import CheckinWrite, WriteSummaryItem
from mobius.state.storage import PostgresStore


class CheckinEngine:
    def __init__(self, *, store: PostgresStore) -> None:
        self.store = store
        self.logger = get_logger(__name__)

    def apply(
        self,
        *,
        user_id: str,
        turn_id: str,
        payload: CheckinWrite,
        idempotency_key: str,
        source_model: str | None,
    ) -> WriteSummaryItem:
        item = self.store.write_checkin(
            user_id=user_id,
            turn_id=turn_id,
            payload=payload,
            idempotency_key=idempotency_key,
            source_model=source_model,
        )
        self.logger.debug(
            "Check-in write result status=%s target=%s details=%s",
            item.status,
            item.target,
            item.details,
        )
        return item
