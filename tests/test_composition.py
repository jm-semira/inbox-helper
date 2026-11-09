from pathlib import Path

from inbox_helper.composition import create_application
from inbox_helper.core.config import AppConfig
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
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
