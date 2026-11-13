"""SQLite persistence for per-email workflow progress and failures."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from inbox_helper.application.models.email_processing import (
    EmailProcessingError,
    EmailProcessingOutcome,
    EmailProcessingStatus,
)
from inbox_helper.core.exceptions import RepositoryError
from inbox_helper.domain.models.classification import EmailClassification


class SqliteEmailProcessingRepository:
    """Store processing outcomes separately from source emails and drafts."""

    _STALE_PROCESSING_AFTER = timedelta(minutes=10)

    def __init__(self, db_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(db_path), timeout=30)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
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
                    CREATE TABLE IF NOT EXISTS email_processing (
                        email_id TEXT PRIMARY KEY
                            REFERENCES emails(id) ON DELETE CASCADE,
                        status TEXT NOT NULL
                            CHECK (status IN (
                                'processing', 'classification_failed',
                                'draft_generation_failed', 'completed'
                            )),
                        classification_json TEXT,
                        error TEXT CHECK (error IS NULL OR error IN (
                            'transient_provider', 'permanent_provider',
                            'invalid_classification', 'invalid_reply'
                        )),
                        retryable INTEGER NOT NULL DEFAULT 0
                            CHECK (retryable IN (0, 1)),
                        draft_created INTEGER NOT NULL DEFAULT 0
                            CHECK (draft_created IN (0, 1)),
                        updated_at TEXT NOT NULL
                    )
                    """
                )
        except RepositoryError:
            self._connection.close()
            raise
        except sqlite3.Error as error:
            self._connection.close()
            raise RepositoryError(
                "Could not initialize email-processing repository."
            ) from error

    def claim(self, email_id: str, retry: bool, now: datetime) -> bool:
        """Claim a new, failed, or stale operation in one SQLite transaction."""
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM email_processing WHERE email_id = ?", (email_id,)
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO email_processing (email_id, status, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        email_id,
                        EmailProcessingStatus.PROCESSING.value,
                        now.isoformat(),
                    ),
                )
                claimed = True
            else:
                status = EmailProcessingStatus(row["status"])
                stale_processing = (
                    status is EmailProcessingStatus.PROCESSING
                    and datetime.fromisoformat(row["updated_at"])
                    <= now - self._STALE_PROCESSING_AFTER
                )
                retryable_failure = bool(row["retryable"]) and status in {
                    EmailProcessingStatus.CLASSIFICATION_FAILED,
                    EmailProcessingStatus.DRAFT_GENERATION_FAILED,
                }
                claimed = (
                    retry
                    and (stale_processing or retryable_failure)
                )
                if claimed:
                    self._connection.execute(
                        """
                        UPDATE email_processing
                        SET status = ?, error = NULL, retryable = 0, updated_at = ?
                        WHERE email_id = ?
                        """,
                        (
                            EmailProcessingStatus.PROCESSING.value,
                            now.isoformat(),
                            email_id,
                        ),
                    )
            self._connection.commit()
            return claimed
        except (sqlite3.Error, ValueError) as error:
            self._connection.rollback()
            raise RepositoryError("Could not claim email processing.") from error

    def get(self, email_id: str) -> EmailProcessingOutcome | None:
        try:
            row = self._connection.execute(
                "SELECT * FROM email_processing WHERE email_id = ?", (email_id,)
            ).fetchone()
        except sqlite3.Error as error:
            raise RepositoryError("Could not retrieve email processing state.") from error
        return self._to_outcome(row) if row is not None else None

    def list_all(self) -> list[EmailProcessingOutcome]:
        try:
            rows = self._connection.execute(
                "SELECT * FROM email_processing ORDER BY updated_at, email_id"
            ).fetchall()
        except sqlite3.Error as error:
            raise RepositoryError("Could not list email processing state.") from error
        return [self._to_outcome(row) for row in rows]

    def save_classification(
        self, email_id: str, classification: EmailClassification, now: datetime
    ) -> None:
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE email_processing
                    SET classification_json = ?, updated_at = ?
                    WHERE email_id = ? AND status = 'processing'
                    """,
                    (
                        self._serialize_classification(classification),
                        now.isoformat(),
                        email_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RepositoryError(
                        "Email processing state was not available to save classification."
                    )
        except sqlite3.Error as error:
            raise RepositoryError("Could not save email classification state.") from error

    def fail(
        self,
        email_id: str,
        status: EmailProcessingStatus,
        error: EmailProcessingError,
        retryable: bool,
        now: datetime,
    ) -> None:
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE email_processing
                    SET status = ?, error = ?, retryable = ?, updated_at = ?
                    WHERE email_id = ? AND status = 'processing'
                    """,
                    (
                        status.value,
                        error.value,
                        int(retryable),
                        now.isoformat(),
                        email_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RepositoryError(
                        "Email processing state was not available to record failure."
                    )
        except sqlite3.Error as exception:
            raise RepositoryError("Could not save email processing failure.") from exception

    def complete(
        self,
        email_id: str,
        classification: EmailClassification | None,
        draft_created: bool,
        now: datetime,
    ) -> None:
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE email_processing
                    SET status = ?, classification_json =
                            COALESCE(?, classification_json),
                        error = NULL, retryable = 0, draft_created = ?,
                        updated_at = ?
                    WHERE email_id = ? AND status = 'processing'
                    """,
                    (
                        EmailProcessingStatus.COMPLETED.value,
                        self._serialize_classification(classification),
                        int(draft_created),
                        now.isoformat(),
                        email_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RepositoryError(
                        "Email processing state was not available to complete."
                    )
        except sqlite3.Error as error:
            raise RepositoryError("Could not complete email processing.") from error

    @staticmethod
    def _serialize_classification(
        classification: EmailClassification | None,
    ) -> str | None:
        if classification is None:
            return None
        return json.dumps(
            {
                "schema_version": 1,
                "classification": classification.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _to_outcome(row: sqlite3.Row) -> EmailProcessingOutcome:
        serialized = row["classification_json"]
        classification = None
        if serialized is not None:
            try:
                payload = json.loads(serialized)
                if (
                    not isinstance(payload, dict)
                    or payload.get("schema_version") != 1
                    or not isinstance(payload.get("classification"), dict)
                ):
                    raise ValueError("unsupported classification snapshot")
                classification = EmailClassification.model_validate_json(
                    json.dumps(payload["classification"])
                )
            except json.JSONDecodeError as error:
                raise RepositoryError(
                    "Could not decode stored email classification."
                ) from error
            except PydanticValidationError as error:
                raise RepositoryError(
                    "Could not validate stored email classification."
                ) from error
            except (TypeError, ValueError) as error:
                raise RepositoryError(
                    "Could not decode stored email classification."
                ) from error
        try:
            return EmailProcessingOutcome(
                email_id=row["email_id"],
                status=EmailProcessingStatus(row["status"]),
                classification=classification,
                error=EmailProcessingError(row["error"]) if row["error"] else None,
                retryable=bool(row["retryable"]),
                draft_created=bool(row["draft_created"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        except (TypeError, ValueError) as error:
            raise RepositoryError(
                "Could not read stored email processing state."
            ) from error

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SqliteEmailProcessingRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
