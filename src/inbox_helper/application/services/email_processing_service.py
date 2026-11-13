"""Coordinate ingestion, classification, individual drafting, and recovery."""

from datetime import UTC, datetime, timedelta

from inbox_helper.application.models.email_processing import (
    EmailProcessingBatch,
    EmailProcessingError,
    EmailProcessingOutcome,
    EmailProcessingStatus,
)
from inbox_helper.application.ports.email_processing_repository import (
    EmailProcessingRepository,
)
from inbox_helper.application.ports.reply_draft_repository import (
    ReplyDraftRepository,
)
from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.email_ingestion import EmailIngestionService
from inbox_helper.application.services.email_query_service import EmailQueryService
from inbox_helper.application.services.reply_draft_service import ReplyDraftService
from inbox_helper.core.exceptions import (
    ClassificationError,
    LLMProviderError,
    RepositoryError,
    ReplyGenerationError,
    TransientLLMProviderError,
)
from inbox_helper.domain.models.email import Email


class EmailProcessingService:
    """Run the full upload-to-review workflow with recoverable per-email state."""

    _STALE_PROCESSING_AFTER = timedelta(minutes=10)

    def __init__(
        self,
        ingestion: EmailIngestionService,
        email_query: EmailQueryService,
        classifier: EmailClassifier,
        reply_drafts: ReplyDraftService,
        draft_repository: ReplyDraftRepository,
        processing_repository: EmailProcessingRepository,
    ) -> None:
        self._ingestion = ingestion
        self._email_query = email_query
        self._classifier = classifier
        self._reply_drafts = reply_drafts
        self._draft_repository = draft_repository
        self._processing_repository = processing_repository

    def ingest_and_process_csv(self, content: bytes) -> EmailProcessingBatch:
        """Persist a validated upload atomically, then process each email alone."""
        emails = self._ingestion.ingest_csv_content_records(content)
        for email in emails:
            self._process(email, retry=False)
        return self._summarize(emails)

    def process_email(self, email_id: str) -> EmailProcessingOutcome | None:
        """Run the whole workflow for one legacy or otherwise unprocessed email."""
        email = self._email_query.get_email(email_id)
        return self._process(email, retry=False)

    def retry_email(self, email_id: str) -> EmailProcessingOutcome | None:
        """Retry a transient or stale in-progress operation for one email."""
        email = self._email_query.get_email(email_id)
        return self._process(email, retry=True)

    def list_outcomes(self) -> list[EmailProcessingOutcome]:
        """Expose persisted outcomes for safe UI presentation."""
        return self._processing_repository.list_all()

    def can_retry(self, outcome: EmailProcessingOutcome) -> bool:
        """Allow only transient failures or operations whose processing lease expired."""
        if outcome.retryable:
            return True
        return (
            outcome.status is EmailProcessingStatus.PROCESSING
            and datetime.now(UTC) - outcome.updated_at >= self._STALE_PROCESSING_AFTER
        )

    def _process(self, email: Email, retry: bool) -> EmailProcessingOutcome | None:
        now = datetime.now(UTC)
        if not self._processing_repository.claim(email.id, retry, now):
            return self._processing_repository.get(email.id)

        prior = self._processing_repository.get(email.id)
        classification = prior.classification if prior is not None else None

        existing_draft = self._draft_repository.get_by_source_email_id(email.id)
        if existing_draft is not None:
            self._processing_repository.complete(
                email.id,
                existing_draft.classification or classification,
                draft_created=True,
                now=datetime.now(UTC),
            )
            return self._processing_repository.get(email.id)

        if classification is None:
            try:
                classification = self._classifier.classify(email)
            except LLMProviderError as error:
                return self._record_failure(
                    email.id,
                    EmailProcessingStatus.CLASSIFICATION_FAILED,
                    self._provider_error(error),
                )
            except ClassificationError:
                return self._record_failure(
                    email.id,
                    EmailProcessingStatus.CLASSIFICATION_FAILED,
                    EmailProcessingError.INVALID_CLASSIFICATION,
                )
            self._processing_repository.save_classification(
                email.id, classification, datetime.now(UTC)
            )
        if classification is None:
            raise RepositoryError(
                "Validated classification was unavailable for reply generation."
            )

        existing_draft = self._draft_repository.get_by_source_email_id(email.id)
        if existing_draft is not None:
            self._processing_repository.complete(
                email.id,
                existing_draft.classification or classification,
                draft_created=True,
                now=datetime.now(UTC),
            )
            return self._processing_repository.get(email.id)

        try:
            self._reply_drafts.generate_draft(email, classification)
        except LLMProviderError as error:
            return self._record_failure(
                email.id,
                EmailProcessingStatus.DRAFT_GENERATION_FAILED,
                self._provider_error(error),
            )
        except ReplyGenerationError:
            return self._record_failure(
                email.id,
                EmailProcessingStatus.DRAFT_GENERATION_FAILED,
                EmailProcessingError.INVALID_REPLY,
            )

        self._processing_repository.complete(
            email.id,
            classification,
            draft_created=True,
            now=datetime.now(UTC),
        )
        return self._processing_repository.get(email.id)

    def _record_failure(
        self,
        email_id: str,
        status: EmailProcessingStatus,
        error: EmailProcessingError,
    ) -> EmailProcessingOutcome:
        self._processing_repository.fail(
            email_id,
            status,
            error,
            retryable=error is EmailProcessingError.TRANSIENT_PROVIDER,
            now=datetime.now(UTC),
        )
        outcome = self._processing_repository.get(email_id)
        if outcome is None:
            raise RepositoryError("Persisted processing failure could not be retrieved.")
        return outcome

    @staticmethod
    def _provider_error(error: LLMProviderError) -> EmailProcessingError:
        return (
            EmailProcessingError.TRANSIENT_PROVIDER
            if isinstance(error, TransientLLMProviderError)
            else EmailProcessingError.PERMANENT_PROVIDER
        )

    def _summarize(self, emails: list[Email]) -> EmailProcessingBatch:
        outcomes = tuple(
            outcome
            for email in emails
            if (outcome := self._processing_repository.get(email.id)) is not None
        )
        failed_statuses = {
            EmailProcessingStatus.CLASSIFICATION_FAILED,
            EmailProcessingStatus.DRAFT_GENERATION_FAILED,
        }
        return EmailProcessingBatch(
            emails_processed=sum(
                outcome.status is not EmailProcessingStatus.PROCESSING
                for outcome in outcomes
            ),
            classified=sum(outcome.classification is not None for outcome in outcomes),
            drafted=sum(outcome.draft_created for outcome in outcomes),
            failed=sum(outcome.status in failed_statuses for outcome in outcomes),
            outcomes=outcomes,
        )
