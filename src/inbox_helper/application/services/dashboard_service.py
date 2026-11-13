"""Application dashboard queries."""

from inbox_helper.application.models.dashboard_stats import DashboardStats
from inbox_helper.application.ports.email_repository import EmailRepository
from inbox_helper.application.ports.reply_draft_repository import (
    ReplyDraftRepository,
)
from inbox_helper.domain.models.reply_draft import DraftStatus


class DashboardService:
    """Build dashboard totals using repository-level aggregate queries."""

    def __init__(
        self,
        email_repository: EmailRepository,
        draft_repository: ReplyDraftRepository,
    ) -> None:
        self._email_repository = email_repository
        self._draft_repository = draft_repository

    def get_stats(self) -> DashboardStats:
        """Return imported-email and lifecycle-specific draft counts."""
        counts = self._draft_repository.count_drafts_by_status()
        return DashboardStats(
            total_emails=self._email_repository.count_emails(),
            classified_drafts=self._draft_repository.count_classified_drafts(),
            pending_drafts=counts[DraftStatus.DRAFT],
            approved_drafts=counts[DraftStatus.APPROVED],
            rejected_drafts=counts[DraftStatus.REJECTED],
        )
