import csv
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from inbox_helper.application.services.approved_reply_export_service import (
    ApprovedReplyExportService,
)
from inbox_helper.core.exceptions import ExportError
from inbox_helper.domain.models.classification import (
    EmailClassification,
    EmailIntent,
    EmailUrgency,
)
from inbox_helper.domain.models.email import Email
from inbox_helper.domain.models.reply_draft import ReplyDraft
from inbox_helper.infrastructure.csv.approved_reply_exporter import (
    ApprovedReplyCsvExporter,
)
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


def _classification() -> EmailClassification:
    return EmailClassification(
        intent=EmailIntent.GENERAL_INQUIRY,
        urgency=EmailUrgency.NORMAL,
        confidence=0.8,
        explanation="Routine inquiry.",
    )


def _create_draft(
    repository: SqliteReplyDraftRepository,
    draft_id: str,
    source_email_id: str,
    text: str,
) -> None:
    repository.create(
        ReplyDraft(
            id=draft_id,
            source_email_id=source_email_id,
            original_generated_text="Original reply.",
            current_text=text,
            requires_human_input=False,
            human_input_reason=None,
            classification=_classification(),
        )
    )


def test_exports_only_approved_current_text_and_preserves_source_link(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "export.db"
    emails = SqliteEmailRepository(db_path)
    emails.save_many(
        [
            Email(
                id="approved-email",
                sender="sender, with comma",
                subject='Subject "quoted"\nsecond line',
                body="not exported",
            ),
            Email(id="pending-email", sender="pending", subject="Pending", body=""),
            Email(id="rejected-email", sender="rejected", subject="Rejected", body=""),
        ]
    )
    emails.close()
    repository = SqliteReplyDraftRepository(db_path)
    _create_draft(repository, "approved", "approved-email", "Edited, approved\nreply")
    _create_draft(repository, "pending", "pending-email", "Pending reply")
    _create_draft(repository, "rejected", "rejected-email", "Rejected reply")
    repository.decide("approved", "approved", datetime.now(UTC))
    repository.decide("rejected", "rejected", datetime.now(UTC))

    target = tmp_path / "approved.csv"
    try:
        exported = ApprovedReplyExportService(
            repository, ApprovedReplyCsvExporter()
        ).export(target)
        with target.open(encoding="utf-8", newline="") as input_file:
            rows = list(csv.DictReader(input_file))

        assert exported == 1
        assert list(rows[0]) == list(ApprovedReplyCsvExporter.FIELDNAMES)
        assert rows == [
            {
                "draft_id": "approved",
                "source_email_id": "approved-email",
                "sender": "sender, with comma",
                "subject": 'Subject "quoted"\nsecond line',
                "reply_text": "Edited, approved\nreply",
                "approved_at": repository.get_draft("approved")
                .decided_at.isoformat(),
            }
        ]
        assert "not exported" not in target.read_text(encoding="utf-8")
    finally:
        repository.close()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("  =1+1", "'  =1+1"),
        ("\t=1+1", "'\t=1+1"),
        ("\tordinary text", "'\tordinary text"),
        ("\x00@SUM(A1)", "'\x00@SUM(A1)"),
        ("\ufeff=1+1", "'\ufeff=1+1"),
        ("safe text", "safe text"),
        ("-ordinary text", "'-ordinary text"),
    ],
)
def test_csv_export_formula_protection_applies_only_to_written_cells(
    tmp_path: Path, value: str, expected: str
) -> None:
    db_path = tmp_path / "safety.db"
    email_repository = SqliteEmailRepository(db_path)
    email_repository.save_many(
        [Email(id="safe-email", sender="sender", subject=value, body="body")]
    )
    email_repository.close()
    repository = SqliteReplyDraftRepository(db_path)
    reply_value = value if not value.startswith("\x00") else "Safe reply"
    expected_reply = expected if reply_value == value else reply_value
    _create_draft(repository, "safe-draft", "safe-email", reply_value)
    repository.decide("safe-draft", "approved", datetime.now(UTC))
    stored_email = SqliteEmailRepository(db_path)
    target = tmp_path / "safe.csv"
    try:
        original_email = stored_email.get_by_id("safe-email")
        original_draft = repository.get_draft("safe-draft")
        ApprovedReplyExportService(
            repository, ApprovedReplyCsvExporter()
        ).export(target)
        with target.open(encoding="utf-8", newline="") as input_file:
            row = next(csv.DictReader(input_file))

        assert row["sender"] == "sender"
        assert row["subject"] == expected
        assert row["reply_text"] == expected_reply
        assert stored_email.get_by_id("safe-email") == original_email
        assert repository.get_draft("safe-draft") == original_draft
    finally:
        stored_email.close()
        repository.close()


def test_export_failure_leaves_existing_target_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "existing.csv"
    target.write_text("previous content", encoding="utf-8")
    writer = ApprovedReplyCsvExporter()

    def fail_replace(source: str, destination: Path) -> None:
        raise OSError("sensitive path details")

    monkeypatch.setattr(
        "inbox_helper.infrastructure.csv.approved_reply_exporter.os.replace",
        fail_replace,
    )
    with pytest.raises(ExportError):
        writer.write([], target)
    assert target.read_text(encoding="utf-8") == "previous content"


def test_empty_subject_is_exported_as_an_empty_csv_field(tmp_path: Path) -> None:
    db_path = tmp_path / "empty-subject.db"
    email_repository = SqliteEmailRepository(db_path)
    email_repository.save_many(
        [Email(id="empty-subject", sender="sender", subject="", body="")]
    )
    email_repository.close()
    repository = SqliteReplyDraftRepository(db_path)
    _create_draft(repository, "approved-empty-subject", "empty-subject", "Reply")
    repository.decide("approved-empty-subject", "approved", datetime.now(UTC))
    target = tmp_path / "empty-subject.csv"
    try:
        ApprovedReplyExportService(
            repository, ApprovedReplyCsvExporter()
        ).export(target)
        with target.open(encoding="utf-8", newline="") as input_file:
            row = next(csv.DictReader(input_file))
        assert row["subject"] == ""
    finally:
        repository.close()


def test_existing_day3_schema_migrates_without_losing_draft_data(
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
            id TEXT PRIMARY KEY,
            source_email_id TEXT NOT NULL REFERENCES emails(id) ON DELETE RESTRICT,
            original_generated_text TEXT NOT NULL,
            current_text TEXT NOT NULL,
            requires_human_input INTEGER NOT NULL,
            human_input_reason TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            decided_at TEXT
        );
        INSERT INTO emails VALUES (
            'legacy-email', 'sender', 'subject', 'body',
            '2026-01-01T00:00:00+00:00'
        );
        INSERT INTO reply_drafts VALUES (
            'legacy-draft', 'legacy-email', 'generated text', 'edited text',
            0, NULL, 'draft', '2026-01-02T00:00:00+00:00',
            '2026-01-03T00:00:00+00:00', NULL
        );
        """
    )
    connection.commit()
    connection.close()

    repository = SqliteReplyDraftRepository(db_path)
    try:
        draft = repository.get_draft("legacy-draft")
        columns = {
            row["name"]
            for row in repository._connection.execute(
                "PRAGMA table_info(reply_drafts)"
            ).fetchall()
        }
        assert draft.current_text == "edited text"
        assert draft.original_generated_text == "generated text"
        assert draft.classification is None
        assert draft.status.value == "draft"
        assert "classification_json" in columns
        assert len(repository.list_pending_review_items()) == 1
    finally:
        repository.close()
