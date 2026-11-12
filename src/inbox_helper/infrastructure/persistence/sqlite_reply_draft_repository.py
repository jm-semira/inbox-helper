"""SQLite persistence for reply drafts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from inbox_helper.application.models.approved_reply_export import (
    ApprovedReplyExportRow,
)
from inbox_helper.application.models.review_queue import ReviewQueueItem
from inbox_helper.application.ports.reply_draft_repository import DraftDecision
from inbox_helper.core.exceptions import (
    DraftStateError,
    EntityNotFoundError,
    RepositoryError,
)
from inbox_helper.domain.models.classification import EmailClassification
from inbox_helper.domain.models.reply_draft import DraftStatus, ReplyDraft


class SqliteReplyDraftRepository:
    """Persist drafts in SQLite with atomic lifecycle transitions."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
        except RepositoryError:
            self._connection.close()
            raise
        except sqlite3.Error as error:
            self._connection.close()
            raise RepositoryError(
                f"Could not initialize SQLite reply-draft repository: {error}"
            ) from error

    def _create_schema(self) -> None:
        with self._connection:
            email_table = self._connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'emails'
                """
            ).fetchone()
            if email_table is None:
                raise RepositoryError(
                    "The email repository must initialize the emails table first."
                )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reply_drafts (
                    id TEXT PRIMARY KEY,
                    source_email_id TEXT NOT NULL
                        REFERENCES emails(id) ON DELETE RESTRICT,
                    original_generated_text TEXT NOT NULL
                        CHECK (length(trim(original_generated_text)) > 0),
                    current_text TEXT NOT NULL
                        CHECK (length(trim(current_text)) > 0),
                    requires_human_input INTEGER NOT NULL
                        CHECK (requires_human_input IN (0, 1)),
                    human_input_reason TEXT,
                    classification_json TEXT,
                    status TEXT NOT NULL
                        CHECK (status IN ('draft', 'approved', 'rejected')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    decided_at TEXT,
                    CHECK (
                        (requires_human_input = 1
                            AND human_input_reason IS NOT NULL
                            AND length(trim(human_input_reason)) > 0)
                        OR (requires_human_input = 0
                            AND human_input_reason IS NULL)
                    ),
                    CHECK (
                        (status = 'draft' AND decided_at IS NULL)
                        OR (status IN ('approved', 'rejected')
                            AND decided_at IS NOT NULL)
                    )
                )
                """
            )
            columns = {
                row["name"]
                for row in self._connection.execute(
                    "PRAGMA table_info(reply_drafts)"
                ).fetchall()
            }
            if "classification_json" not in columns:
                self._connection.execute(
                    "ALTER TABLE reply_drafts ADD COLUMN classification_json TEXT"
                )

    def create(self, draft: ReplyDraft) -> ReplyDraft:
        """Insert a new draft referencing an existing email."""
        if draft.status is not DraftStatus.DRAFT or draft.decided_at is not None:
            raise DraftStateError("A new reply draft must be undecided.")
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO reply_drafts (
                        id, source_email_id, original_generated_text, current_text,
                        requires_human_input, human_input_reason,
                        classification_json, status,
                        created_at, updated_at, decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft.id,
                        draft.source_email_id,
                        draft.original_generated_text,
                        draft.current_text,
                        int(draft.requires_human_input),
                        draft.human_input_reason,
                        self._serialize_classification(draft.classification),
                        draft.status.value,
                        draft.created_at.isoformat(),
                        draft.updated_at.isoformat(),
                        None,
                    ),
                )
            return self.get_draft(draft.id)
        except sqlite3.IntegrityError as error:
            try:
                source_exists = self._email_exists(draft.source_email_id)
            except sqlite3.Error as lookup_error:
                raise RepositoryError(
                    f"Could not verify reply draft source email: {lookup_error}"
                ) from lookup_error
            if not source_exists:
                raise EntityNotFoundError("Email", draft.source_email_id) from error
            raise RepositoryError(f"Could not save reply draft: {error}") from error
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not save reply draft: {error}") from error

    def get_draft(self, draft_id: str) -> ReplyDraft:
        """Retrieve a saved reply draft."""
        try:
            row = self._connection.execute(
                "SELECT * FROM reply_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not retrieve reply draft: {error}") from error
        if row is None:
            raise EntityNotFoundError("Reply draft", draft_id)
        return self._to_draft(row)

    def list_drafts(
        self, status: DraftStatus | None = None
    ) -> list[ReplyDraft]:
        """Return saved drafts in creation order."""
        try:
            if status is None:
                rows = self._connection.execute(
                    "SELECT * FROM reply_drafts ORDER BY rowid"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT * FROM reply_drafts WHERE status = ? ORDER BY rowid",
                    (status.value,),
                ).fetchall()
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not list reply drafts: {error}") from error
        return [self._to_draft(row) for row in rows]

    def list_pending_review_items(self) -> list[ReviewQueueItem]:
        """Select undecided drafts with only the source fields needed for review."""
        try:
            rows = self._connection.execute(
                """
                SELECT d.*, e.sender, e.subject, e.received_at
                FROM reply_drafts AS d
                JOIN emails AS e ON e.id = d.source_email_id
                WHERE d.status = 'draft' AND d.decided_at IS NULL
                ORDER BY d.rowid
                """
            ).fetchall()
        except sqlite3.Error as error:
            raise RepositoryError(
                f"Could not list pending reply drafts: {error}"
            ) from error
        items: list[ReviewQueueItem] = []
        for row in rows:
            draft = self._to_draft(row)
            items.append(
                ReviewQueueItem(
                    draft=draft,
                    sender=row["sender"],
                    subject=row["subject"],
                    received_at=datetime.fromisoformat(row["received_at"]),
                    intent=(
                        draft.classification.intent
                        if draft.classification is not None
                        else None
                    ),
                    urgency=(
                        draft.classification.urgency.value
                        if draft.classification is not None
                        else None
                    ),
                )
            )
        return items

    def list_approved_export_rows(self) -> list[ApprovedReplyExportRow]:
        """Select only explicitly approved replies and their source-email metadata."""
        try:
            rows = self._connection.execute(
                """
                SELECT d.id AS draft_id, d.source_email_id, e.sender, e.subject,
                       d.current_text AS reply_text, d.decided_at AS approved_at
                FROM reply_drafts AS d
                JOIN emails AS e ON e.id = d.source_email_id
                WHERE d.status = 'approved' AND d.decided_at IS NOT NULL
                ORDER BY d.decided_at, d.id
                """
            ).fetchall()
        except sqlite3.Error as error:
            raise RepositoryError(
                f"Could not select approved reply drafts: {error}"
            ) from error
        return [
            ApprovedReplyExportRow(
                draft_id=row["draft_id"],
                source_email_id=row["source_email_id"],
                sender=row["sender"],
                subject=row["subject"],
                reply_text=row["reply_text"],
                approved_at=datetime.fromisoformat(row["approved_at"]),
            )
            for row in rows
        ]

    def edit_current_text(
        self, draft_id: str, current_text: str, updated_at: datetime
    ) -> ReplyDraft:
        """Atomically edit text only while the draft is undecided."""
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE reply_drafts
                    SET current_text = ?, updated_at = ?
                    WHERE id = ? AND status = 'draft' AND decided_at IS NULL
                    """,
                    (current_text, updated_at.isoformat(), draft_id),
                )
                if cursor.rowcount == 0:
                    self._raise_transition_failure(draft_id)
            return self.get_draft(draft_id)
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not edit reply draft: {error}") from error

    def decide(
        self, draft_id: str, decision: DraftDecision, decided_at: datetime
    ) -> ReplyDraft:
        """Atomically approve or reject a draft that is still undecided."""
        if decision not in (DraftStatus.APPROVED.value, DraftStatus.REJECTED.value):
            raise DraftStateError("Decision must be approved or rejected.")
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE reply_drafts
                    SET status = ?, updated_at = ?, decided_at = ?
                    WHERE id = ? AND status = 'draft' AND decided_at IS NULL
                    """,
                    (
                        decision,
                        decided_at.isoformat(),
                        decided_at.isoformat(),
                        draft_id,
                    ),
                )
                if cursor.rowcount == 0:
                    self._raise_transition_failure(draft_id)
            return self.get_draft(draft_id)
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not decide reply draft: {error}") from error

    def _raise_transition_failure(self, draft_id: str) -> None:
        row = self._connection.execute(
            "SELECT status FROM reply_drafts WHERE id = ?", (draft_id,)
        ).fetchone()
        if row is None:
            raise EntityNotFoundError("Reply draft", draft_id)
        raise DraftStateError(
            f"Reply draft '{draft_id}' is already {row['status']}."
        )

    def _email_exists(self, email_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _to_draft(row: sqlite3.Row) -> ReplyDraft:
        draft_fields = {
            "id",
            "source_email_id",
            "original_generated_text",
            "current_text",
            "requires_human_input",
            "human_input_reason",
            "classification_json",
            "status",
            "created_at",
            "updated_at",
            "decided_at",
        }
        values = {key: row[key] for key in draft_fields if key in row.keys()}
        serialized_classification = values.pop("classification_json", None)
        values["classification"] = (
            SqliteReplyDraftRepository._deserialize_classification(
                serialized_classification
            )
        )
        values["requires_human_input"] = bool(values["requires_human_input"])
        values["status"] = DraftStatus(values["status"])
        for field in ("created_at", "updated_at", "decided_at"):
            if values[field] is not None:
                values[field] = datetime.fromisoformat(values[field])
        return ReplyDraft.model_validate(values)

    @staticmethod
    def _serialize_classification(
        classification: EmailClassification | None,
    ) -> str | None:
        if classification is None:
            return None
        payload = {
            "schema_version": 1,
            "classification": classification.model_dump(mode="json"),
        }
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @staticmethod
    def _deserialize_classification(
        serialized: str | None,
    ) -> EmailClassification | None:
        if serialized is None:
            return None
        try:
            payload = json.loads(serialized)
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != 1
                or not isinstance(payload.get("classification"), dict)
            ):
                raise ValueError("unsupported classification snapshot format")
            return EmailClassification.model_validate_json(
                json.dumps(payload["classification"])
            )
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            raise RepositoryError(
                "Could not decode stored classification snapshot."
            ) from error
        except PydanticValidationError as error:
            raise RepositoryError(
                "Could not validate stored classification snapshot."
            ) from error

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SqliteReplyDraftRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
