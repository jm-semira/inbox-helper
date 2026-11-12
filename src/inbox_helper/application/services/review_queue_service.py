"""Group and prioritize pending reply drafts for human review."""

from datetime import datetime

from inbox_helper.application.models.review_queue import (
    ReviewQueueGroup,
    ReviewQueueItem,
)
from inbox_helper.application.ports.reply_draft_repository import (
    ReplyDraftRepository,
)
from inbox_helper.domain.models.classification import EmailIntent, EmailUrgency


_INTENT_ORDER = {
    EmailIntent.JOB_APPLICATION: 0,
    EmailIntent.INTERVIEW_SCHEDULING: 1,
    EmailIntent.APPLICATION_STATUS: 2,
    EmailIntent.GENERAL_INQUIRY: 3,
    EmailIntent.OTHER: 4,
}
_URGENCY_ORDER = {
    "critical": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}


class ReviewQueueService:
    """Organize pending drafts without changing their lifecycle or classification."""

    def __init__(self, repository: ReplyDraftRepository) -> None:
        self._repository = repository

    def get_grouped_queue(self) -> list[ReviewQueueGroup]:
        """Return non-empty intent groups in explicit deterministic order."""
        grouped: dict[EmailIntent | None, list[ReviewQueueItem]] = {}
        for item in self._repository.list_pending_review_items():
            intent = item.intent if item.intent in _INTENT_ORDER else None
            grouped.setdefault(intent, []).append(item)

        ordered_intents = sorted(
            grouped,
            key=lambda intent: _INTENT_ORDER.get(intent, len(_INTENT_ORDER)),
        )
        return [
            ReviewQueueGroup(
                intent=intent,
                items=tuple(sorted(grouped[intent], key=self._item_order)),
            )
            for intent in ordered_intents
        ]

    @staticmethod
    def _item_order(item: ReviewQueueItem) -> tuple[int, float, datetime, str]:
        urgency = (
            item.urgency.value
            if isinstance(item.urgency, EmailUrgency)
            else item.urgency
        )
        return (
            _URGENCY_ORDER.get(urgency, len(_URGENCY_ORDER)),
            item.received_at.timestamp(),
            item.draft.created_at,
            item.draft.id,
        )
