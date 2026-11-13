"""Inbox browsing and upload-triggered email processing."""

import hashlib

import streamlit as st

from inbox_helper.application.models.email_processing import (
    EmailProcessingOutcome,
    EmailProcessingStatus,
)
from inbox_helper.composition import UiApplicationServices
from inbox_helper.core.exceptions import InboxHelperError
from inbox_helper.ui.errors import safe_error_message


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def render(services: UiApplicationServices) -> None:
    """Render uploaded emails and their end-to-end processing state."""
    st.title("Email Inbox")
    _render_upload(services)
    try:
        emails = services.email_query.list_emails()
        outcomes = {
            outcome.email_id: outcome
            for outcome in services.email_processing.list_outcomes()
        }
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))
        return

    if not emails:
        st.info("No imported emails yet. Upload a CSV above to begin.")
        return

    email_ids = [email.id for email in emails]
    if st.session_state.get("inbox_helper.selected_email_id") not in set(email_ids):
        st.session_state["inbox_helper.selected_email_id"] = emails[0].id
    selected_id = st.selectbox(
        "Select an email",
        options=email_ids,
        format_func=lambda email_id: f"Email {email_ids.index(email_id) + 1}",
        key="inbox_helper.selected_email_id",
    )
    email = next(item for item in emails if item.id == selected_id)
    st.subheader("Selected email")
    st.text(f"Subject: {email.subject or '(no subject)'}")
    st.text(f"From: {email.sender}")
    st.text(f"Received: {email.received_at.isoformat()}")
    st.text(email.body or "(empty body)")

    outcome = outcomes.get(email.id)
    if outcome is None:
        st.info("This email has not been processed.")
        if st.button("Process email", key=f"process-{email.id}"):
            try:
                services.email_processing.process_email(email.id)
                st.session_state["inbox_helper.flash"] = (
                    "success",
                    "Processing finished. Any generated draft remains pending human review.",
                )
                st.rerun()
            except InboxHelperError as error:
                st.error(safe_error_message(error, services.llm_provider))
        return

    _render_outcome(outcome, services.llm_provider)
    if outcome.draft_created:
        try:
            draft = services.reply_drafts.list_drafts(status=None)
            source_drafts = [
                item for item in draft if item.source_email_id == email.id
            ]
            if source_drafts:
                latest = max(source_drafts, key=lambda item: item.created_at)
                st.subheader("Suggested reply")
                if latest.requires_human_input:
                    st.warning(
                        "Human input is required before this draft is finalized."
                    )
                    st.text(latest.human_input_reason or "")
                st.text(latest.current_text)
                if latest.status.value == "draft":
                    st.info("This draft is awaiting explicit human review.")
        except InboxHelperError as error:
            st.error(safe_error_message(error, services.llm_provider))


def _render_upload(services: UiApplicationServices) -> None:
    st.subheader("Import and process email CSV")
    uploaded = st.file_uploader(
        "Choose a CSV file (maximum 10 MiB)",
        type=["csv"],
        key="inbox_helper.csv_upload",
    )
    if uploaded is None:
        return
    if uploaded.size > MAX_UPLOAD_BYTES:
        st.error("Upload exceeds the 10 MiB limit. No emails were imported.")
        return
    content = uploaded.getvalue()
    if len(content) > MAX_UPLOAD_BYTES:
        st.error("Upload exceeds the 10 MiB limit. No emails were imported.")
        return

    digest = hashlib.sha256(content).hexdigest()
    processed_uploads = st.session_state.setdefault(
        "inbox_helper.processed_uploads", set()
    )
    if digest in processed_uploads:
        st.info("This file was already processed during this session.")
        return

    try:
        result = services.email_processing.ingest_and_process_csv(content)
        processed_uploads.add(digest)
        st.session_state["inbox_helper.processed_uploads"] = processed_uploads
        message = (
            f"Processed {result.emails_processed} of "
            f"{len(result.outcomes)} email(s): {result.classified} classified, "
            f"{result.drafted} drafted, {result.failed} failed. "
            "Generated drafts are pending human review; no email was sent."
        )
        st.session_state["inbox_helper.flash"] = (
            "warning" if result.failed else "success",
            message,
        )
        st.session_state["inbox_helper.navigate_to"] = "Review Queue"
        st.rerun()
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))


def _render_outcome(outcome: EmailProcessingOutcome, llm_provider: str) -> None:
    if outcome.status is EmailProcessingStatus.PROCESSING:
        st.info("This email is being processed or a previous run was interrupted.")
    elif outcome.error_message is not None:
        st.error(outcome.error_message)
        if (
            outcome.error is not None
            and outcome.error.value == "transient_provider"
            and llm_provider == "ollama"
        ):
            st.caption(
                "Check that the local Ollama service is running and "
                "OLLAMA_BASE_URL is correct."
            )
    if outcome.classification is not None:
        classification = outcome.classification
        st.markdown("#### Classification")
        st.write(f"**Intent:** {classification.intent.value}")
        st.write(f"**Urgency:** {classification.urgency.value}")
        st.write(f"**Confidence:** {classification.confidence:.0%}")
        st.text(classification.explanation)
    if outcome.status is EmailProcessingStatus.COMPLETED:
        st.success("Processing complete.")
