from pathlib import Path

import pytest

from inbox_helper.application.services.email_ingestion import EmailIngestionService
from inbox_helper.core.exceptions import IngestionError, RepositoryError
from inbox_helper.domain.models.email import Email
from inbox_helper.infrastructure.csv.email_csv_reader import EmailCsvReader
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)


def test_ingestion_validates_and_persists_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "emails.csv"
    csv_path.write_text(
        "id,sender,subject,body,received_at\n"
        "mail-1, sender@example.com ,Hello,  Message  ,2025-01-02T03:04:05+02:00\n",
        encoding="utf-8",
    )
    repository = SqliteEmailRepository(tmp_path / "inbox.db")
    service = EmailIngestionService(EmailCsvReader(), repository)

    assert service.ingest_csv(csv_path) == 1
    saved = repository.get_by_id("mail-1")
    assert saved.sender == "sender@example.com"
    assert saved.body == "  Message  "
    assert saved.received_at.isoformat() == "2025-01-02T01:04:05+00:00"
    repository.close()


def test_invalid_csv_is_not_partially_persisted(tmp_path: Path) -> None:
    csv_path = tmp_path / "emails.csv"
    csv_path.write_text(
        "sender,subject,body\nvalid@example.com,Hello,Message\n,Missing sender,Message\n",
        encoding="utf-8",
    )
    repository = SqliteEmailRepository(tmp_path / "inbox.db")
    service = EmailIngestionService(EmailCsvReader(), repository)

    with pytest.raises(IngestionError, match="CSV line 3"):
        service.ingest_csv(csv_path)

    assert repository.list_all() == []
    repository.close()


def test_csv_requires_contract_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "emails.csv"
    csv_path.write_text("from,subject,body\nx,Hello,Message\n", encoding="utf-8")

    with pytest.raises(IngestionError, match="sender"):
        EmailCsvReader().read(csv_path)


def test_empty_csv_is_rejected(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(IngestionError, match="no header"):
        EmailCsvReader().read(csv_path)


def test_header_only_csv_is_rejected_by_ingestion(tmp_path: Path) -> None:
    csv_path = tmp_path / "header-only.csv"
    csv_path.write_text("sender,subject,body\n", encoding="utf-8")
    repository = SqliteEmailRepository(tmp_path / "inbox.db")
    service = EmailIngestionService(EmailCsvReader(), repository)

    with pytest.raises(IngestionError, match="no email records"):
        service.ingest_csv(csv_path)

    assert repository.list_all() == []
    repository.close()


def test_invalid_timestamp_is_rejected_before_persistence(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid-time.csv"
    csv_path.write_text(
        "sender,subject,body,received_at\n"
        "sender@example.com,Hello,Message,not-a-timestamp\n",
        encoding="utf-8",
    )
    repository = SqliteEmailRepository(tmp_path / "inbox.db")
    service = EmailIngestionService(EmailCsvReader(), repository)

    with pytest.raises(IngestionError, match="received_at"):
        service.ingest_csv(csv_path)

    assert repository.list_all() == []
    repository.close()


def test_email_accepts_empty_subject_and_body_without_rewriting_content() -> None:
    empty = Email(id="empty", sender="sender", subject="", body="")
    whitespace = Email(id="whitespace", sender="sender", subject="  ", body="\t\n")

    assert (empty.subject, empty.body) == ("", "")
    assert (whitespace.subject, whitespace.body) == ("  ", "\t\n")


def test_sender_does_not_require_email_address_syntax() -> None:
    email = Email(id="non-address-sender", sender="system", subject="", body="")

    assert email.sender == "system"


def test_repository_save_many_is_atomic(tmp_path: Path) -> None:
    repository = SqliteEmailRepository(tmp_path / "inbox.db")
    original = Email(id="same-id", sender="a@example.com", subject="A", body="A")
    duplicate = Email(id="same-id", sender="b@example.com", subject="B", body="B")
    repository.save_many([original])

    with pytest.raises(RepositoryError):
        repository.save_many(
            [
                Email(id="new-id", sender="c@example.com", subject="C", body="C"),
                duplicate,
            ]
        )

    assert [email.id for email in repository.list_all()] == ["same-id"]
    repository.close()


def test_duplicate_ids_within_batch_roll_back_all_records(tmp_path: Path) -> None:
    repository = SqliteEmailRepository(tmp_path / "inbox.db")

    with pytest.raises(RepositoryError):
        repository.save_many(
            [
                Email(id="duplicate", sender="a", subject="A", body="A"),
                Email(id="new", sender="b", subject="B", body="B"),
                Email(id="duplicate", sender="c", subject="C", body="C"),
            ]
        )

    assert repository.list_all() == []
    repository.close()


def test_duplicate_id_against_database_rolls_back_batch(tmp_path: Path) -> None:
    repository = SqliteEmailRepository(tmp_path / "inbox.db")
    repository.save_many(
        [Email(id="existing", sender="a", subject="A", body="A")]
    )

    with pytest.raises(RepositoryError):
        repository.save_many(
            [
                Email(id="new", sender="b", subject="B", body="B"),
                Email(id="existing", sender="c", subject="C", body="C"),
            ]
        )

    assert [email.id for email in repository.list_all()] == ["existing"]
    repository.close()
