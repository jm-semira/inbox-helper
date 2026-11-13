from pathlib import Path

from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.reply_draft_service import ReplyDraftService
from inbox_helper.composition import (
    create_application,
    create_classification_service,
    create_reply_draft_service,
    create_ui_application,
)
from inbox_helper.core.config import AppConfig
from inbox_helper.domain.models.email import Email
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


def test_composition_wires_ingestion_and_closes_repository(
    tmp_path: Path, monkeypatch
) -> None:
    csv_path = tmp_path / "emails.csv"
    csv_path.write_text(
        "sender,subject,body\nsender@example.com,Hello,Message\n",
        encoding="utf-8",
    )
    close_calls = 0
    original_close = SqliteEmailRepository.close

    def track_close(repository: SqliteEmailRepository) -> None:
        nonlocal close_calls
        close_calls += 1
        original_close(repository)

    monkeypatch.setattr(SqliteEmailRepository, "close", track_close)
    config = AppConfig(db_path=str(tmp_path / "inbox.db"), log_level="CRITICAL")

    with create_application(config) as ingestion:
        assert ingestion.ingest_csv(csv_path) == 1

    assert close_calls == 1


def test_classification_service_is_constructible_without_ingestion_database(
    tmp_path: Path, monkeypatch
) -> None:
    class JsonProvider:
        def complete(self, prompt: str) -> str:
            return (
                '{"intent":"other","urgency":"low","confidence":0.8,'
                '"explanation":"Informational message."}'
            )

    monkeypatch.setattr(
        "inbox_helper.composition.create_llm_provider",
        lambda config: JsonProvider(),
    )
    config = AppConfig(db_path=str(tmp_path / "must-not-be-created.db"))

    classifier = create_classification_service(config)
    result = classifier.classify(
        Email(id="email-1", sender="sender", subject="Note", body="For your information")
    )

    assert isinstance(classifier, EmailClassifier)
    assert result.intent.value == "other"
    assert not (tmp_path / "must-not-be-created.db").exists()


def test_reply_draft_service_is_independently_constructible_and_closes_repository(
    tmp_path: Path, monkeypatch
) -> None:
    class JsonProvider:
        def complete(self, prompt: str) -> str:
            return (
                '{"reply_text":"Thank you.","requires_human_input":false,'
                '"human_input_reason":null}'
            )

    close_calls = 0
    draft_close_calls = 0
    original_close = SqliteEmailRepository.close
    original_draft_close = SqliteReplyDraftRepository.close

    def track_close(repository: SqliteEmailRepository) -> None:
        nonlocal close_calls
        close_calls += 1
        original_close(repository)

    def track_draft_close(repository: SqliteReplyDraftRepository) -> None:
        nonlocal draft_close_calls
        draft_close_calls += 1
        original_draft_close(repository)

    monkeypatch.setattr(
        "inbox_helper.composition.create_llm_provider",
        lambda config: JsonProvider(),
    )
    monkeypatch.setattr(SqliteEmailRepository, "close", track_close)
    monkeypatch.setattr(SqliteReplyDraftRepository, "close", track_draft_close)
    config = AppConfig(db_path=str(tmp_path / "drafts.db"), log_level="CRITICAL")

    with create_reply_draft_service(config) as service:
        assert isinstance(service, ReplyDraftService)

    assert close_calls == 1
    assert draft_close_calls == 1


def test_ui_composition_constructs_all_services_and_closes_repositories(
    tmp_path: Path,
) -> None:
    config = AppConfig(db_path=str(tmp_path / "ui.db"), log_level="CRITICAL")

    with create_ui_application(config) as services:
        assert services.ingestion is not None
        assert services.email_query is not None
        assert services.classifier is not None
        assert services.reply_drafts is not None
        assert services.review_queue is not None
        assert services.dashboard is not None
        assert services.approved_export is not None
        assert services.demo_mode is False
