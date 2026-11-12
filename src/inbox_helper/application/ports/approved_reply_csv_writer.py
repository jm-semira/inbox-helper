"""Output boundary for writing approved reply CSV exports."""

from pathlib import Path
from typing import Protocol

from inbox_helper.application.models.approved_reply_export import (
    ApprovedReplyExportRow,
)


class ApprovedReplyCsvWriter(Protocol):
    """Write approved export rows to the caller-selected destination."""

    def write(
        self, rows: list[ApprovedReplyExportRow], destination: str | Path
    ) -> int:
        """Atomically write rows and return the number of exported records."""
