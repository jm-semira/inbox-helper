"""Persistence boundary for reply drafts."""

from datetime import datetime
from typing import Literal, Protocol

from inbox_helper.application.models.approved_reply_export import (
    ApprovedReplyExportRow,
)
from inbox_helper.application.models.review_queue import ReviewQueueItem
from inbox_helper.domain.models.reply_draft import DraftStatus, ReplyDraft


DraftDecision = Literal["approved", "rejected"]


class ReplyDraftRepository(Protocol):
    """Operations required to preserve and transition human-review drafts."""

    def create(self, draft: ReplyDraft) -> ReplyDraft:
        """Insert a new draft and require an existing source email."""

    def get_draft(self, draft_id: str) -> ReplyDraft:
        """Retrieve a saved draft."""

    def get_by_source_email_id(self, email_id: str) -> ReplyDraft | None:
        """Return one existing draft for an email without generating another."""

    def list_drafts(
        self, status: DraftStatus | None = None
    ) -> list[ReplyDraft]:
        """List saved drafts, optionally limited to a lifecycle state."""

    def count_drafts_by_status(self) -> dict[DraftStatus, int]:
        """Return draft counts by lifecycle status."""

    def count_classified_drafts(self) -> int:
        """Return the number of drafts with a stored classification snapshot."""

    def list_pending_review_items(self) -> list[ReviewQueueItem]:
        """List only undecided drafts with their source-email metadata."""

    def list_approved_export_rows(self) -> list[ApprovedReplyExportRow]:
        """List only approved drafts and their source-email metadata."""

    def edit_current_text(
        self, draft_id: str, current_text: str, updated_at: datetime
    ) -> ReplyDraft:
        """Update only the current text while the draft remains undecided."""

    def decide(
        self, draft_id: str, decision: DraftDecision, decided_at: datetime
    ) -> ReplyDraft:
        """Atomically transition an undecided draft to an explicit decision."""
