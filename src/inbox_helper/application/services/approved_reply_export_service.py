"""Application use case for exporting explicitly approved replies."""

from pathlib import Path

from inbox_helper.application.ports.approved_reply_csv_writer import (
    ApprovedReplyCsvWriter,
)
from inbox_helper.application.ports.reply_draft_repository import (
    ReplyDraftRepository,
)


class ApprovedReplyExportService:
    """Export approved current draft text without sending or changing drafts."""

    def __init__(
        self,
        repository: ReplyDraftRepository,
        writer: ApprovedReplyCsvWriter,
    ) -> None:
        self._repository = repository
        self._writer = writer

    def export(self, destination: str | Path) -> int:
        """Write approved draft rows and return the number of exported records."""
        rows = self._repository.list_approved_export_rows()
        return self._writer.write(rows, destination)
