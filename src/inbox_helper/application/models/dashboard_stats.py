"""Application projection of inbox and draft status totals."""

from pydantic import BaseModel, ConfigDict, Field


class DashboardStats(BaseModel):
    """Aggregate counts for the local inbox workflow."""

    model_config = ConfigDict(frozen=True)

    total_emails: int = Field(ge=0)
    classified_drafts: int = Field(ge=0)
    pending_drafts: int = Field(ge=0)
    approved_drafts: int = Field(ge=0)
    rejected_drafts: int = Field(ge=0)
