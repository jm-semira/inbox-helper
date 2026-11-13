from pathlib import Path

from inbox_helper.application.services.dashboard_service import DashboardService
from inbox_helper.application.services.email_query_service import EmailQueryService
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


def test_email_query_service_lists_and_retrieves_imported_emails(
    tmp_path: Path,
) -> None:
    email_repository = SqliteEmailRepository(tmp_path / "inbox.db")
    email = Email(id="email-1", sender="sender", subject="subject", body="body")
    email_repository.save_many([email])

    service = EmailQueryService(email_repository)

    assert service.list_emails() == [email]
    assert service.get_email(email.id) == email
    email_repository.close()


def test_dashboard_reports_email_and_draft_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "inbox.db"
    email_repository = SqliteEmailRepository(db_path)
    emails = [
        Email(id=f"email-{index}", sender="sender", subject="", body="")
        for index in range(1, 4)
    ]
    email_repository.save_many(emails)
    draft_repository = SqliteReplyDraftRepository(db_path)
    for index, status in enumerate(
        (DraftStatus.DRAFT, DraftStatus.APPROVED, DraftStatus.REJECTED), start=1
    ):
        draft_repository.create(
            ReplyDraft(
                id=f"draft-{index}",
                source_email_id=emails[index - 1].id,
                original_generated_text="Reply",
                current_text="Reply",
                requires_human_input=False,
                human_input_reason=None,
                classification=EmailClassification(
                    intent=EmailIntent.OTHER,
                    urgency=EmailUrgency.NORMAL,
                    confidence=0.8,
                    explanation="Stored test snapshot.",
                ),
            )
        )
        if status is not DraftStatus.DRAFT:
            draft_repository.decide(
                f"draft-{index}", status.value, emails[index - 1].received_at
            )

    stats = DashboardService(email_repository, draft_repository).get_stats()

    assert stats.total_emails == 3
    assert stats.classified_drafts == 3
    assert stats.pending_drafts == 1
    assert stats.approved_drafts == 1
    assert stats.rejected_drafts == 1
    draft_repository.close()
    email_repository.close()
