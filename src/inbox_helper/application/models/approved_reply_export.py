"""Minimal projection of an explicitly approved reply for CSV export."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApprovedReplyExportRow(BaseModel):
    """Approved draft content and source-email relationship for export."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    source_email_id: str
    sender: str
    subject: str
    reply_text: str
    approved_at: datetime
