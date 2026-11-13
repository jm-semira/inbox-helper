"""Inbox browsing, import, classification, and draft generation."""

import hashlib
import json

import streamlit as st

from inbox_helper.composition import UiApplicationServices
from inbox_helper.core.exceptions import InboxHelperError
from inbox_helper.domain.models.classification import EmailClassification
from inbox_helper.ui.errors import safe_error_message


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def render(services: UiApplicationServices) -> None:
    """Render imported email browsing and explicit AI workflow actions."""
    st.title("Email Inbox")
    _render_upload(services)
    try:
        emails = services.email_query.list_emails()
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))
        return

    if not emails:
        st.info("No imported emails yet. Upload a CSV above to begin.")
        return

    email_ids = [email.id for email in emails]
    valid_ids = set(email_ids)
    if st.session_state.get("inbox_helper.selected_email_id") not in valid_ids:
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

    generated_ids = st.session_state["inbox_helper.generated_for_email_ids"]
    classifications = st.session_state["inbox_helper.classifications"]
    if st.button(
        "Classify email",
        key=f"classify-{email.id}",
        disabled=email.id in generated_ids,
    ):
        try:
            result = services.classifier.classify(email)
            classifications[email.id] = result.model_dump(mode="json")
            st.session_state["inbox_helper.classifications"] = classifications
        except InboxHelperError as error:
            st.error(safe_error_message(error, services.llm_provider))

    classification_data = classifications.get(email.id)
    if classification_data is None:
        st.info("Classify this email to review its intent and urgency.")
        return

    try:
        classification = EmailClassification.model_validate_json(
            json.dumps(classification_data)
        )
    except (TypeError, ValueError):
        classifications.pop(email.id, None)
        st.error(
            "Saved session classification was invalid. Classify the email again."
        )
        return
    st.markdown("#### Classification")
    st.write(f"**Intent:** {classification.intent.value}")
    st.write(f"**Urgency:** {classification.urgency.value}")
    st.write(f"**Confidence:** {classification.confidence:.0%}")
    st.text(classification.explanation)

    if email.id in generated_ids:
        st.info("A draft was generated for this email during this session.")
        try:
            drafts = services.reply_drafts.list_drafts(status=None)
            existing_drafts = [
                draft for draft in drafts if draft.source_email_id == email.id
            ]
            if existing_drafts:
                latest = max(existing_drafts, key=lambda draft: draft.created_at)
                if latest.requires_human_input:
                    st.warning(
                        "Human input is required before this draft is finalized."
                    )
                    st.text(latest.human_input_reason or "")
                st.text(latest.current_text)
        except InboxHelperError as error:
            st.error(safe_error_message(error, services.llm_provider))
        return
    if st.button("Generate reply draft", key=f"generate-{email.id}"):
        try:
            draft = services.reply_drafts.generate_draft(email, classification)
            generated_ids.add(email.id)
            st.session_state["inbox_helper.generated_for_email_ids"] = generated_ids
            st.success("Draft saved to the review queue. It has not been approved.")
            if draft.requires_human_input:
                st.warning("Human input is required before this draft is finalized.")
                st.text(draft.human_input_reason or "")
            st.text(draft.current_text)
        except InboxHelperError as error:
            st.error(safe_error_message(error, services.llm_provider))


def _render_upload(services: UiApplicationServices) -> None:
    st.subheader("Import email CSV")
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
    if not st.button("Import CSV", key="inbox_helper.import_csv"):
        return

    digest = hashlib.sha256(content).hexdigest()
    imported = st.session_state.setdefault("inbox_helper.imported_uploads", set())
    if digest in imported:
        st.info("This file was already imported during this session.")
        return
    try:
        count = services.ingestion.ingest_csv_content(content)
        imported.add(digest)
        st.session_state["inbox_helper.imported_uploads"] = imported
        st.success(f"Imported {count} email(s).")
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))
