"""Persistence boundary for reply drafts."""

from datetime import datetime
from typing import Literal, Protocol

from inbox_helper.domain.models.reply_draft import DraftStatus, ReplyDraft


DraftDecision = Literal["approved", "rejected"]


class ReplyDraftRepository(Protocol):
    """Operations required to preserve and transition human-review drafts."""

    def create(self, draft: ReplyDraft) -> ReplyDraft:
        """Insert a new draft and require an existing source email."""

    def get_draft(self, draft_id: str) -> ReplyDraft:
        """Retrieve a saved draft."""

    def list_drafts(
        self, status: DraftStatus | None = None
    ) -> list[ReplyDraft]:
        """List saved drafts, optionally limited to a lifecycle state."""

    def edit_current_text(
        self, draft_id: str, current_text: str, updated_at: datetime
    ) -> ReplyDraft:
        """Update only the current text while the draft remains undecided."""

    def decide(
        self, draft_id: str, decision: DraftDecision, decided_at: datetime
    ) -> ReplyDraft:
        """Atomically transition an undecided draft to an explicit decision."""
