from datetime import UTC, datetime, timedelta
from pathlib import Path

from inbox_helper.application.models.review_queue import ReviewQueueItem
from inbox_helper.application.services.review_queue_service import (
    ReviewQueueService,
)
from inbox_helper.domain.models.classification import (
    EmailClassification,
    EmailIntent,
    EmailUrgency,
)
from inbox_helper.domain.models.email import Email
from inbox_helper.domain.models.reply_draft import DraftStatus, ReplyDraft
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


def _classification(
    intent: EmailIntent, urgency: EmailUrgency
) -> EmailClassification:
    return EmailClassification(
        intent=intent,
        urgency=urgency,
        confidence=0.8,
        explanation="Test classification.",
    )


def test_queue_groups_with_explicit_intent_and_urgency_order(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "queue.db"
    email_repository = SqliteEmailRepository(db_path)
    emails = [
        Email(
            id=f"email-{i}",
            sender=f"sender-{i}",
            subject=f"Subject {i}",
            body="Body",
        )
        for i in range(1, 8)
    ]
    email_repository.save_many(emails)
    email_repository.close()
    repository = SqliteReplyDraftRepository(db_path)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    draft_specs = [
        (
            "draft-general",
            emails[0],
            EmailIntent.GENERAL_INQUIRY,
            EmailUrgency.CRITICAL,
        ),
        (
            "draft-interview-low",
            emails[1],
            EmailIntent.INTERVIEW_SCHEDULING,
            EmailUrgency.LOW,
        ),
        (
            "draft-interview-high",
            emails[2],
            EmailIntent.INTERVIEW_SCHEDULING,
            EmailUrgency.HIGH,
        ),
        (
            "draft-job-rejected",
            emails[3],
            EmailIntent.JOB_APPLICATION,
            EmailUrgency.NORMAL,
        ),
        ("draft-job", emails[4], EmailIntent.JOB_APPLICATION, EmailUrgency.NORMAL),
        (
            "draft-general-pending",
            emails[5],
            EmailIntent.GENERAL_INQUIRY,
            EmailUrgency.NORMAL,
        ),
        ("draft-unclassified", emails[6], None, None),
    ]
    for index, (draft_id, source, intent, urgency) in enumerate(draft_specs):
        repository.create(
            ReplyDraft(
                id=draft_id,
                source_email_id=source.id,
                original_generated_text="Generated reply.",
                current_text="Generated reply.",
                requires_human_input=False,
                human_input_reason=None,
                classification=(
                    _classification(intent, urgency)
                    if intent is not None and urgency is not None
                    else None
                ),
                created_at=base_time + timedelta(minutes=index),
                updated_at=base_time + timedelta(minutes=index),
            )
        )
    repository.decide("draft-general", "approved", base_time)
    repository.decide("draft-job-rejected", "rejected", base_time)

    try:
        groups = ReviewQueueService(repository).get_grouped_queue()

        assert [group.intent for group in groups] == [
            EmailIntent.JOB_APPLICATION,
            EmailIntent.INTERVIEW_SCHEDULING,
            EmailIntent.GENERAL_INQUIRY,
            None,
        ]
        assert [item.draft.id for item in groups[0].items] == [
            "draft-job"
        ]
        assert [item.draft.id for item in groups[1].items] == [
            "draft-interview-high",
            "draft-interview-low",
        ]
        assert [item.draft.id for item in groups[2].items] == [
            "draft-general-pending"
        ]
        assert [item.draft.id for item in groups[3].items] == [
            "draft-unclassified"
        ]
        assert all(
            item.draft.status is DraftStatus.DRAFT
            for group in groups
            for item in group.items
        )
    finally:
        repository.close()


def test_unknown_urgency_sorts_after_supported_urgency() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    unknown_item = ReviewQueueItem(
        draft=ReplyDraft(
            id="unknown",
            source_email_id="email",
            original_generated_text="Reply",
            current_text="Reply",
            requires_human_input=False,
            human_input_reason=None,
            created_at=base,
            updated_at=base,
        ),
        sender="sender",
        subject="subject",
        received_at=base,
        intent=EmailIntent.JOB_APPLICATION,
        urgency="unexpected",
    )
    high_item = unknown_item.model_copy(
        update={
            "draft": unknown_item.draft.model_copy(update={"id": "high"}),
            "urgency": "high",
        }
    )

    assert [
        item.draft.id
        for item in sorted(
            [unknown_item, high_item], key=ReviewQueueService._item_order
        )
    ] == ["high", "unknown"]


def test_equal_urgency_uses_received_time_then_created_time_then_id() -> None:
    received = datetime(2026, 1, 1, tzinfo=UTC)
    created = received + timedelta(days=1)

    def item(
        draft_id: str, received_at: datetime, created_at: datetime
    ) -> ReviewQueueItem:
        return ReviewQueueItem(
            draft=ReplyDraft(
                id=draft_id,
                source_email_id="email",
                original_generated_text="Reply",
                current_text="Reply",
                requires_human_input=False,
                human_input_reason=None,
                created_at=created_at,
                updated_at=created_at,
            ),
            sender="sender",
            subject="subject",
            received_at=received_at,
            intent=EmailIntent.JOB_APPLICATION,
            urgency="normal",
        )

    items = [
        item("z", received, created),
        item("b", received + timedelta(hours=1), created),
        item("c", received, created),
        item("a", received, created),
    ]

    assert [
        value.draft.id
        for value in sorted(items, key=ReviewQueueService._item_order)
    ] == ["a", "c", "z", "b"]
