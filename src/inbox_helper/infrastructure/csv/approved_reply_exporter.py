"""Spreadsheet-safe CSV output for approved reply drafts."""

from __future__ import annotations

import csv
import logging
import os
import tempfile
import unicodedata
from pathlib import Path

from inbox_helper.application.models.approved_reply_export import (
    ApprovedReplyExportRow,
)
from inbox_helper.core.exceptions import ExportError
from inbox_helper.core.logging import get_logger


class ApprovedReplyCsvExporter:
    """Write approved rows atomically without altering their stored values."""

    FIELDNAMES = (
        "draft_id",
        "source_email_id",
        "sender",
        "subject",
        "reply_text",
        "approved_at",
    )
    FORMULA_PREFIXES = frozenset("=+-@")

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or get_logger("csv.export")

    def write(
        self, rows: list[ApprovedReplyExportRow], destination: str | Path
    ) -> int:
        target = Path(destination)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary_path = output.name
                writer = csv.DictWriter(output, fieldnames=self.FIELDNAMES)
                writer.writeheader()
                for row in rows:
                    writer.writerow(
                        {
                            "draft_id": self._safe_cell(row.draft_id),
                            "source_email_id": self._safe_cell(row.source_email_id),
                            "sender": self._safe_cell(row.sender),
                            "subject": self._safe_cell(row.subject),
                            "reply_text": self._safe_cell(row.reply_text),
                            "approved_at": row.approved_at.isoformat(),
                        }
                    )
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, target)
            return len(rows)
        except OSError as error:
            raise ExportError("Could not write approved reply CSV export.") from error
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                try:
                    os.unlink(temporary_path)
                except OSError:
                    self._logger.warning(
                        "Could not remove temporary approved reply export file."
                    )

    @classmethod
    def _safe_cell(cls, value: str) -> str:
        index = 0
        leading_control = False
        while index < len(value):
            char = value[index]
            category = unicodedata.category(char)
            if category in {"Cc", "Cf"}:
                leading_control = True
                index += 1
                continue
            if char.isspace():
                index += 1
                continue
            break
        if leading_control or (
            index < len(value) and value[index] in cls.FORMULA_PREFIXES
        ):
            return "'" + value
        return value
