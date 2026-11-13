from pathlib import Path
from tempfile import gettempdir

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from inbox_helper.core.config import set_config
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.llm.mock import DemoMockLLMProvider
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


APP_PATH = Path(__file__).parents[1] / "streamlit_app.py"


def _app_test(monkeypatch, tmp_path: Path, demo_mode: bool = True) -> AppTest:
    monkeypatch.setenv("INBOX_HELPER_DB_PATH", str(tmp_path / "inbox.db"))
    monkeypatch.setenv("INBOX_HELPER_DEMO_MODE", str(demo_mode).lower())
    monkeypatch.setenv("INBOX_HELPER_LLM_PROVIDER", "mock")
    monkeypatch.setenv("INBOX_HELPER_LOG_LEVEL", "CRITICAL")
    set_config(None)
    return AppTest.from_file(str(APP_PATH)).run()


def _navigate(app: AppTest, page: str) -> AppTest:
    return app.selectbox(key="inbox_helper.page").select(page).run()


def _import_csv(app: AppTest, content: bytes) -> AppTest:
    app.file_uploader(key="inbox_helper.csv_upload").upload(
        "emails.csv", content, "text/csv"
    )
    return app.run()


def test_streamlit_dashboard_empty_state_and_navigation(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_test(monkeypatch, tmp_path)

    assert any("Your inbox is empty" in item.value for item in app.info)
    assert len(app.metric) == 5
    assert any("Demo Mode" in item.value for item in app.warning)

    _navigate(app, "Inbox")
    assert any("No imported emails" in item.value for item in app.info)
    _navigate(app, "Review Queue")
    assert any("No drafts are awaiting review" in item.value for item in app.info)


def test_streamlit_import_classify_generate_edit_decide_and_export(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    _import_csv(
        app,
        b"id,sender,subject,body\n"
        b"email-1,candidate,Question,Please share information.\n"
        b"email-2,candidate,Another question,Please share more information.\n",
    )
    assert any("Processed 2 of 2 email(s)" in item.value for item in app.success)
    assert any("General Inquiry · 2" in item.value for item in app.header)

    app.run()
    with SqliteEmailRepository(tmp_path / "inbox.db") as email_repository:
        with SqliteReplyDraftRepository(tmp_path / "inbox.db") as draft_repository:
            assert email_repository.count_emails() == 2
            assert len(draft_repository.list_drafts()) == 2

    _navigate(app, "Review Queue")
    assert any("Please share information" in item.value for item in app.text)
    first_draft_id = _draft_id_for_email(tmp_path, "email-1")
    app.text_area(key="inbox_helper.draft_editor." + first_draft_id).set_value(
        "Human-edited response."
    ).run()
    assert app.button(key=f"approve-{first_draft_id}").disabled
    app.button(key=f"save-{first_draft_id}").click().run()
    assert any("still pending review" in item.value for item in app.success)

    app.button(key=f"approve-{first_draft_id}").click().run()
    assert any("No email was sent" in item.value for item in app.success)
    download = app.get("download_button")
    assert len(download) == 1
    assert download[0].label == "Download approved replies as CSV"

    _navigate(app, "Inbox")
    app.selectbox(key="inbox_helper.selected_email_id").select("email-2").run()
    rejected_draft_id = _draft_id_for_email(tmp_path, "email-2")
    _navigate(app, "Review Queue")
    app.button(key=f"reject-{rejected_draft_id}").click().run()
    assert any("Draft rejected" in item.value for item in app.success)
    assert any("No drafts are awaiting review" in item.value for item in app.info)

    with SqliteReplyDraftRepository(tmp_path / "inbox.db") as repository:
        rows = repository.list_approved_export_rows()
        assert len(rows) == 1
        assert rows[0].reply_text == "Human-edited response."
        assert rows[0].source_email_id == "email-1"
        assert repository.get_draft(rejected_draft_id).status.value == "rejected"


def test_streamlit_duplicate_upload_is_blocked_in_session(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    content = b"id,sender,subject,body\nemail-1,sender,Subject,Body\n"
    _import_csv(app, content)

    _navigate(app, "Inbox")
    _import_csv(app, content)

    assert any("already processed during this session" in item.value for item in app.info)
    with SqliteEmailRepository(tmp_path / "inbox.db") as repository:
        assert repository.count_emails() == 1


def test_streamlit_reruns_do_not_repeat_classification_or_generation(
    monkeypatch, tmp_path: Path
) -> None:
    class CountingProvider:
        def __init__(self) -> None:
            self.calls = 0
            self.provider = DemoMockLLMProvider()

        def complete(self, prompt: str) -> str:
            self.calls += 1
            return self.provider.complete(prompt)

    provider = CountingProvider()
    monkeypatch.setattr(
        "inbox_helper.composition.create_llm_provider",
        lambda config: provider,
    )
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    _import_csv(app, b"id,sender,subject,body\nemail-1,sender,Subject,Body\n")

    assert provider.calls == 2
    app.run()
    assert provider.calls == 2
    with SqliteReplyDraftRepository(tmp_path / "inbox.db") as repository:
        assert len(repository.list_drafts()) == 1


def test_streamlit_retries_only_the_failed_email(
    monkeypatch, tmp_path: Path
) -> None:
    from inbox_helper.core.exceptions import TransientLLMProviderError

    class RecoveringProvider:
        def __init__(self) -> None:
            self.available = False
            self.calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            if not self.available:
                raise TransientLLMProviderError("private provider details")
            if prompt.startswith("Classify the email"):
                return DemoMockLLMProvider._CLASSIFICATION_RESPONSE
            return DemoMockLLMProvider._REPLY_RESPONSE

    provider = RecoveringProvider()
    monkeypatch.setattr(
        "inbox_helper.composition.create_llm_provider",
        lambda config: provider,
    )
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    _import_csv(app, b"id,sender,subject,body\nemail-1,sender,Subject,Body\n")

    assert provider.calls == 1
    assert any("temporarily unavailable" in item.value for item in app.error)
    assert not any("private provider details" in item.value for item in app.error)

    provider.available = True
    _navigate(app, "Review Queue")
    app.button(key="retry-email-1").click().run()

    assert provider.calls == 3
    with SqliteReplyDraftRepository(tmp_path / "inbox.db") as repository:
        drafts = repository.list_drafts()
        assert len(drafts) == 1
        assert drafts[0].status.value == "draft"


def test_streamlit_invalid_csv_shows_safe_error_without_partial_import(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    _import_csv(
        app,
        b"sender,subject,body\nvalid@example.com,Hello,Message\n,Missing,Message\n",
    )

    assert any("CSV import failed" in item.value for item in app.error)
    with SqliteEmailRepository(tmp_path / "inbox.db") as repository:
        assert repository.list_all() == []


def test_streamlit_demo_mode_disabled_surfaces_invalid_mock_safely(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_test(monkeypatch, tmp_path, demo_mode=False)
    assert not any("Demo Mode" in item.value for item in app.warning)
    assert any("Mock Mode" in item.value for item in app.caption)
    _navigate(app, "Inbox")
    _import_csv(app, b"id,sender,subject,body\nemail-1,sender,Subject,Body\n")

    assert any("invalid classification" in item.value for item in app.error)
    assert not any("Mock response" in item.value for item in app.error)


def test_streamlit_shows_human_input_warning_for_generated_draft(
    monkeypatch, tmp_path: Path
) -> None:
    class HumanInputProvider:
        def __init__(self) -> None:
            self.responses = [
                DemoMockLLMProvider._CLASSIFICATION_RESPONSE,
                (
                    '{"reply_text":"Thank you for reaching out.",'
                    '"requires_human_input":true,'
                    '"human_input_reason":"Please confirm the response details."}'
                ),
            ]

        def complete(self, prompt: str) -> str:
            return self.responses.pop(0)

    provider = HumanInputProvider()
    monkeypatch.setattr(
        "inbox_helper.composition.create_llm_provider",
        lambda config: provider,
    )
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    _import_csv(app, b"id,sender,subject,body\nemail-1,sender,Subject,Body\n")

    assert any("Human input is required" in item.value for item in app.warning)
    assert "Please confirm the response details." in {
        item.value for item in app.text
    }


def test_streamlit_configuration_error_is_safe(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("INBOX_HELPER_DB_PATH", str(tmp_path / "inbox.db"))
    monkeypatch.setenv("INBOX_HELPER_LLM_PROVIDER", "openai")
    monkeypatch.setenv("INBOX_HELPER_DEMO_MODE", "false")
    from inbox_helper.core.config import set_config

    set_config(None)
    app = AppTest.from_file(str(APP_PATH)).run()

    assert any("Configuration is invalid" in item.value for item in app.error)
    assert not any("not implemented" in item.value for item in app.error)


def test_streamlit_ollama_mode_label_and_unavailable_message(
    monkeypatch, tmp_path: Path
) -> None:
    from urllib.error import URLError

    monkeypatch.setenv("INBOX_HELPER_DB_PATH", str(tmp_path / "inbox.db"))
    monkeypatch.setenv("INBOX_HELPER_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("INBOX_HELPER_LLM_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("INBOX_HELPER_DEMO_MODE", "false")
    monkeypatch.setenv("INBOX_HELPER_LOG_LEVEL", "CRITICAL")
    from inbox_helper.core.config import set_config

    set_config(None)
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            URLError("private network detail")
        ),
    )
    app = AppTest.from_file(str(APP_PATH)).run()

    assert any("Ollama AI Mode" in item.value for item in app.info)
    assert any("qwen2.5:3b" in item.value for item in app.text)
    app.button(key="inbox_helper.ollama_health_check").click().run()
    assert any("Ollama is unavailable" in item.value for item in app.warning)
    _navigate(app, "Inbox")
    _import_csv(app, b"id,sender,subject,body\nemail-1,sender,Subject,Body\n")

    assert any("temporarily unavailable" in item.value for item in app.error)
    assert not any("private network detail" in item.value for item in app.error)


def test_streamlit_rejects_uploads_over_ten_mib(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Inbox")
    oversized_csv = (
        b"sender,subject,body\nsender,"
        + b"x" * (10 * 1024 * 1024)
        + b",body\n"
    )
    app.file_uploader(key="inbox_helper.csv_upload").upload(
        "large.csv", oversized_csv, "text/csv"
    )
    app.run()

    assert any("exceeds the 10 MiB limit" in item.value for item in app.error)
    with SqliteEmailRepository(tmp_path / "inbox.db") as repository:
        assert repository.count_emails() == 0


def test_streamlit_export_removes_temporary_files(
    monkeypatch, tmp_path: Path
) -> None:
    before = set(Path(gettempdir()).glob("inbox-helper-export-*"))
    app = _app_test(monkeypatch, tmp_path)
    _navigate(app, "Review Queue")
    after = set(Path(gettempdir()).glob("inbox-helper-export-*"))

    assert after == before


def _draft_id(db_path: Path) -> str:
    return _draft_ids(db_path)[0]


def _draft_ids(db_path: Path) -> list[str]:
    with SqliteEmailRepository(db_path / "inbox.db"):
        with SqliteReplyDraftRepository(db_path / "inbox.db") as repository:
            return [draft.id for draft in repository.list_drafts()]


def _draft_id_for_email(db_path: Path, email_id: str) -> str:
    with SqliteEmailRepository(db_path / "inbox.db"):
        with SqliteReplyDraftRepository(db_path / "inbox.db") as repository:
            draft = repository.get_by_source_email_id(email_id)
            assert draft is not None
            return draft.id
