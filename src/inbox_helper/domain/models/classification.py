"""Provider-neutral email classification model."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmailIntent(str, Enum):
    """Supported high-level email intents."""

    JOB_APPLICATION = "job_application"
    INTERVIEW_SCHEDULING = "interview_scheduling"
    APPLICATION_STATUS = "application_status"
    GENERAL_INQUIRY = "general_inquiry"
    OTHER = "other"


class EmailUrgency(str, Enum):
    """Attention level indicated by concrete time pressure in the email."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EmailClassification(BaseModel):
    """Validated, provider-neutral classification result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intent: EmailIntent
    urgency: EmailUrgency
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1)

    @field_validator("explanation")
    @classmethod
    def require_non_whitespace_explanation(cls, value: str) -> str:
        explanation = value.strip()
        if not explanation:
            raise ValueError("explanation must not be empty")
        return explanation
