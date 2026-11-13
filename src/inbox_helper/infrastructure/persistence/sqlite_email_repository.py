"""SQLite implementation of the email repository."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from inbox_helper.core.exceptions import EntityNotFoundError, RepositoryError
from inbox_helper.domain.models.email import Email


class SqliteEmailRepository:
    """Persist emails in SQLite using a connection owned by this instance."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._connection = sqlite3.connect(self._db_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not initialize SQLite repository: {error}") from error

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS emails (
                    id TEXT PRIMARY KEY,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS email_imports (
                    fingerprint TEXT PRIMARY KEY,
                    email_ids_json TEXT NOT NULL
                )
                """
            )

    def save_many(self, emails: list[Email]) -> None:
        if not emails:
            return
        try:
            with self._connection:
                self._connection.executemany(
                    """
                    INSERT INTO emails (id, sender, subject, body, received_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            email.id,
                            email.sender,
                            email.subject,
                            email.body,
                            email.received_at.isoformat(),
                        )
                        for email in emails
                    ],
                )
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not save emails to SQLite: {error}") from error

    def save_import(self, emails: list[Email], fingerprint: str) -> list[Email]:
        """Persist a CSV upload once and return the same emails on exact re-upload."""
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            existing = self._connection.execute(
                "SELECT email_ids_json FROM email_imports WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if existing is not None:
                email_ids = json.loads(existing["email_ids_json"])
                rows = [
                    self._connection.execute(
                        """
                        SELECT id, sender, subject, body, received_at
                        FROM emails WHERE id = ?
                        """,
                        (email_id,),
                    ).fetchone()
                    for email_id in email_ids
                ]
                if any(row is None for row in rows):
                    raise RepositoryError(
                        "Previously imported email records are incomplete."
                    )
                self._connection.commit()
                return [Email.model_validate(dict(row)) for row in rows]

            self._connection.executemany(
                """
                INSERT INTO emails (id, sender, subject, body, received_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        email.id,
                        email.sender,
                        email.subject,
                        email.body,
                        email.received_at.isoformat(),
                    )
                    for email in emails
                ],
            )
            self._connection.execute(
                """
                INSERT INTO email_imports (fingerprint, email_ids_json)
                VALUES (?, ?)
                """,
                (
                    fingerprint,
                    json.dumps([email.id for email in emails], separators=(",", ":")),
                ),
            )
            self._connection.commit()
            return emails
        except RepositoryError:
            self._connection.rollback()
            raise
        except (sqlite3.Error, ValueError, TypeError) as error:
            self._connection.rollback()
            raise RepositoryError("Could not persist uploaded email CSV.") from error

    def get_by_id(self, email_id: str) -> Email:
        try:
            row = self._connection.execute(
                "SELECT id, sender, subject, body, received_at FROM emails WHERE id = ?",
                (email_id,),
            ).fetchone()
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not retrieve email from SQLite: {error}") from error
        if row is None:
            raise EntityNotFoundError("Email", email_id)
        return Email.model_validate(dict(row))

    def list_all(self) -> list[Email]:
        try:
            rows = self._connection.execute(
                "SELECT id, sender, subject, body, received_at FROM emails ORDER BY rowid"
            ).fetchall()
        except sqlite3.Error as error:
            raise RepositoryError(f"Could not list emails from SQLite: {error}") from error
        return [Email.model_validate(dict(row)) for row in rows]

    def count_emails(self) -> int:
        try:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM emails"
            ).fetchone()
        except sqlite3.Error as error:
            raise RepositoryError(
                f"Could not count emails in SQLite: {error}"
            ) from error
        return int(row["count"])

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SqliteEmailRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
