import json
import sqlite3
from pathlib import Path

import pytest

from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.email_ingestion import EmailIngestionService
from inbox_helper.application.services.email_processing_service import (
    EmailProcessingService,
)
from inbox_helper.application.services.email_query_service import EmailQueryService
from inbox_helper.application.services.reply_draft_service import ReplyDraftService
from inbox_helper.application.services.review_queue_service import (
    ReviewQueueService,
)
from inbox_helper.core.exceptions import (
    LLMProviderError,
    RepositoryError,
    TransientLLMProviderError,
)
from inbox_helper.domain.models.classification import EmailIntent
from inbox_helper.domain.models.reply_draft import DraftStatus, ReplyDraft
from inbox_helper.infrastructure.csv.email_csv_reader import EmailCsvReader
from inbox_helper.infrastructure.persistence.sqlite_email_processing_repository import (
    SqliteEmailProcessingRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


def _classification(intent: str = "job_application") -> str:
    return json.dumps(
        {
            "intent": intent,
            "urgency": "normal",
            "confidence": 0.9,
            "explanation": "The candidate is asking about an application.",
        }
    )


def _reply(text: str = "Thank you for reaching out.") -> str:
    return json.dumps(
        {
            "reply_text": text,
            "requires_human_input": False,
            "human_input_reason": None,
        }
    )


class ScriptedProvider:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _services(
    tmp_path: Path, provider: ScriptedProvider
) -> tuple[
    EmailProcessingService,
    SqliteEmailRepository,
    SqliteReplyDraftRepository,
    SqliteEmailProcessingRepository,
]:
    db_path = tmp_path / "inbox.db"
    emails = SqliteEmailRepository(db_path)
    drafts = SqliteReplyDraftRepository(db_path)
    outcomes = SqliteEmailProcessingRepository(db_path)
    ingestion = EmailIngestionService(EmailCsvReader(), emails)
    service = EmailProcessingService(
        ingestion,
        EmailQueryService(emails),
        EmailClassifier(provider),
        ReplyDraftService(provider, drafts),
        drafts,
        outcomes,
    )
    return service, emails, drafts, outcomes


def _csv(*rows: tuple[str, str, str, str]) -> bytes:
    header = "id,sender,subject,body\n"
    return (header + "".join(",".join(row) + "\n" for row in rows)).encode()


def test_upload_processes_each_email_and_groups_individual_drafts(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider(
        [
            _classification("job_application"),
            _reply("Reply one."),
            _classification("interview_scheduling"),
            _reply("Reply two."),
        ]
    )
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        result = service.ingest_and_process_csv(
            _csv(
                ("email-1", "candidate-1", "Application", "I am applying."),
                ("email-2", "candidate-2", "Interview", "Can we schedule?"),
            )
        )

        assert result.emails_processed == 2
        assert result.classified == 2
        assert result.drafted == 2
        assert result.failed == 0
        saved = drafts.list_drafts()
        assert len(saved) == 2
        assert {draft.source_email_id for draft in saved} == {"email-1", "email-2"}
        assert all(draft.status is DraftStatus.DRAFT for draft in saved)
        groups = ReviewQueueService(drafts).get_grouped_queue()
        assert [group.intent for group in groups] == [
            EmailIntent.JOB_APPLICATION,
            EmailIntent.INTERVIEW_SCHEDULING,
        ]
        assert [len(group.items) for group in groups] == [1, 1]
        assert all(outcome.status.value == "completed" for outcome in result.outcomes)
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_one_classification_failure_does_not_discard_successful_emails(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider(
        [
            "not json",
            _classification("other"),
            _reply("Reply for the second email."),
        ]
    )
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        result = service.ingest_and_process_csv(
            _csv(
                ("email-1", "candidate-1", "Broken", "Malformed response expected."),
                ("email-2", "candidate-2", "Good", "This email can be processed."),
            )
        )

        assert result.failed == 1
        assert result.classified == 1
        assert result.drafted == 1
        assert [draft.source_email_id for draft in drafts.list_drafts()] == [
            "email-2"
        ]
        failed = outcomes.get("email-1")
        assert failed is not None
        assert failed.error.value == "invalid_classification"
        assert failed.retryable is False
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_retrying_one_failed_email_does_not_reprocess_other_emails(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider(
        [
            TransientLLMProviderError("temporary failure"),
            _classification("other"),
            _reply("Second email reply."),
            _classification("job_application"),
            _reply("Recovered first email reply."),
        ]
    )
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        result = service.ingest_and_process_csv(
            _csv(
                ("email-1", "candidate-1", "First", "First body."),
                ("email-2", "candidate-2", "Second", "Second body."),
            )
        )
        assert result.failed == 1
        assert result.drafted == 1

        service.retry_email("email-1")

        assert len(drafts.list_drafts()) == 2
        assert sum("Second body." in prompt for prompt in provider.prompts) == 2
        assert sum("First body." in prompt for prompt in provider.prompts) == 3
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_transient_draft_failure_retry_reuses_saved_classification(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider(
        [
            _classification(),
            TransientLLMProviderError("safe provider error"),
            _reply("Recovered reply."),
        ]
    )
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        content = _csv(("email-1", "candidate", "Application", "I am applying."))
        failed_batch = service.ingest_and_process_csv(content)
        failed = failed_batch.outcomes[0]
        assert failed.status.value == "draft_generation_failed"
        assert failed.classification is not None
        assert failed.retryable is True
        assert drafts.list_drafts() == []

        recovered = service.retry_email("email-1")

        assert recovered is not None
        assert recovered.status.value == "completed"
        assert recovered.draft_created is True
        assert len(provider.prompts) == 3
        assert provider.prompts[0].startswith("Classify the email")
        assert all(
            prompt.startswith("Write a professional")
            for prompt in provider.prompts[1:]
        )
        assert len(drafts.list_drafts()) == 1
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_permanent_provider_failure_is_not_retried(tmp_path: Path) -> None:
    provider = ScriptedProvider([LLMProviderError("permanent failure")])
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        service.ingest_and_process_csv(
            _csv(("email-1", "candidate", "Question", "Message."))
        )

        outcome = service.retry_email("email-1")

        assert outcome is not None
        assert outcome.error.value == "permanent_provider"
        assert outcome.retryable is False
        assert len(provider.prompts) == 1
        assert drafts.list_drafts() == []
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_invalid_reply_is_not_retried_and_preserves_classification(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider([_classification(), '{"reply_text":"missing fields"}'])
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        service.ingest_and_process_csv(
            _csv(("email-1", "candidate", "Question", "Message."))
        )
        outcome = service.retry_email("email-1")

        assert outcome is not None
        assert outcome.error.value == "invalid_reply"
        assert outcome.classification is not None
        assert outcome.retryable is False
        assert len(provider.prompts) == 2
        assert drafts.list_drafts() == []
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_repeat_upload_and_processing_do_not_create_duplicate_drafts(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider([_classification(), _reply()])
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        content = b"sender,subject,body\ncandidate,Application,I am applying.\n"
        first = service.ingest_and_process_csv(content)
        second = service.ingest_and_process_csv(content)

        assert len(emails.list_all()) == 1
        assert len(drafts.list_drafts()) == 1
        assert len(provider.prompts) == 2
        assert first.outcomes[0].email_id == second.outcomes[0].email_id
        assert second.drafted == 1
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_failed_persistence_of_upload_saves_no_partial_emails(tmp_path: Path) -> None:
    provider = ScriptedProvider([])
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        duplicate_ids = _csv(
            ("same-id", "candidate-1", "First", "Body one."),
            ("same-id", "candidate-2", "Second", "Body two."),
        )
        with pytest.raises(RepositoryError):
            service.ingest_and_process_csv(duplicate_ids)

        assert emails.list_all() == []
        assert outcomes.list_all() == []
        assert provider.prompts == []
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_existing_draft_is_preserved_and_not_regenerated(tmp_path: Path) -> None:
    provider = ScriptedProvider([])
    service, emails, drafts, outcomes = _services(tmp_path, provider)
    try:
        content = b"id,sender,subject,body\nemail-1,candidate,Application,I am applying.\n"
        assert EmailIngestionService(EmailCsvReader(), emails).ingest_csv_content(
            content
        ) == 1
        existing = drafts.create(
            ReplyDraft(
                id="existing-draft",
                source_email_id="email-1",
                original_generated_text="Keep this draft.",
                current_text="Keep this draft.",
                requires_human_input=False,
                human_input_reason=None,
            )
        )

        result = service.ingest_and_process_csv(content)

        assert result.drafted == 1
        assert drafts.list_drafts() == [existing]
        assert provider.prompts == []
    finally:
        outcomes.close()
        drafts.close()
        emails.close()


def test_additive_workflow_migration_preserves_existing_email_and_draft(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE emails (
            id TEXT PRIMARY KEY, sender TEXT NOT NULL, subject TEXT NOT NULL,
            body TEXT NOT NULL, received_at TEXT NOT NULL
        );
        CREATE TABLE reply_drafts (
            id TEXT PRIMARY KEY, source_email_id TEXT NOT NULL,
            original_generated_text TEXT NOT NULL, current_text TEXT NOT NULL,
            requires_human_input INTEGER NOT NULL, human_input_reason TEXT,
            status TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, decided_at TEXT
        );
        INSERT INTO emails VALUES (
            'legacy-email', 'candidate', 'Old application', 'Original content',
            '2025-01-01T00:00:00+00:00'
        );
        INSERT INTO reply_drafts VALUES (
            'legacy-draft', 'legacy-email', 'Old reply', 'Edited old reply',
            0, NULL, 'draft', '2025-01-01T00:00:00+00:00',
            '2025-01-01T00:00:00+00:00', NULL
        );
        """
    )
    connection.commit()
    connection.close()

    with SqliteEmailRepository(db_path) as emails:
        with SqliteReplyDraftRepository(db_path) as drafts:
            with SqliteEmailProcessingRepository(db_path) as processing:
                saved_email = emails.get_by_id("legacy-email")
                saved_draft = drafts.get_draft("legacy-draft")
                assert saved_email.body == "Original content"
                assert saved_draft.current_text == "Edited old reply"
                assert saved_draft.classification is None
                assert processing.list_all() == []
