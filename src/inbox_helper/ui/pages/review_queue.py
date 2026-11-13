"""Pending draft review and approved-only export."""

from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from inbox_helper.composition import UiApplicationServices
from inbox_helper.core.exceptions import InboxHelperError
from inbox_helper.domain.models.reply_draft import DraftStatus
from inbox_helper.ui.errors import safe_error_message


def render(services: UiApplicationServices) -> None:
    """Render ordered pending drafts and separate edit and decision actions."""
    st.title("Review Queue")
    _render_export(services)
    try:
        groups = services.review_queue.get_grouped_queue()
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))
        return

    if not groups:
        st.info("No drafts are awaiting review.")
        return

    for group in groups:
        title = (
            group.intent.value.replace("_", " ").title()
            if group.intent
            else "Unclassified"
        )
        st.header(title)
        for item in group.items:
            urgency = item.urgency or "unknown"
            heading = f"Pending draft · {urgency.upper()}"
            with st.expander(heading):
                st.caption(
                    f"Received {item.received_at.isoformat()} · "
                    f"Draft {item.draft.id}"
                )
                st.markdown("**Source email**")
                st.text(f"Subject: {item.subject or '(no subject)'}")
                st.text(f"From: {item.sender}")
                st.text(item.body or "(empty body)")
                if item.draft.requires_human_input:
                    st.warning(
                        "Human input is required before this draft is finalized."
                    )
                    st.text(item.draft.human_input_reason or "")
                editor_key = f"inbox_helper.draft_editor.{item.draft.id}"
                current_text = st.text_area(
                    "Current reply draft",
                    value=item.draft.current_text,
                    key=editor_key,
                    height=180,
                )
                changed = current_text != item.draft.current_text
                save_column, approve_column, reject_column = st.columns(3)
                if save_column.button(
                    "Save edit",
                    key=f"save-{item.draft.id}",
                    disabled=not changed,
                ):
                    try:
                        services.reply_drafts.edit_draft(
                            item.draft.id, current_text
                        )
                        st.session_state["inbox_helper.flash"] = (
                            "success",
                            "Edit saved. The draft is still pending review.",
                        )
                        st.rerun()
                    except InboxHelperError as error:
                        st.error(safe_error_message(error, services.llm_provider))
                if approve_column.button(
                    "Approve",
                    key=f"approve-{item.draft.id}",
                    disabled=changed,
                ):
                    _decide(services, item.draft.id, DraftStatus.APPROVED)
                if reject_column.button(
                    "Reject",
                    key=f"reject-{item.draft.id}",
                    disabled=changed,
                ):
                    _decide(services, item.draft.id, DraftStatus.REJECTED)
                if changed:
                    st.info("Save your edit before making an explicit decision.")


def _decide(
    services: UiApplicationServices, draft_id: str, decision: DraftStatus
) -> None:
    try:
        if decision is DraftStatus.APPROVED:
            services.reply_drafts.approve_draft(draft_id)
            message = "Draft approved. No email was sent."
        else:
            services.reply_drafts.reject_draft(draft_id)
            message = "Draft rejected."
        st.session_state["inbox_helper.flash"] = ("success", message)
        st.rerun()
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))


def _render_export(services: UiApplicationServices) -> None:
    try:
        with TemporaryDirectory(prefix="inbox-helper-export-") as directory:
            export_path = Path(directory) / "approved-replies.csv"
            services.approved_export.export(export_path)
            data = export_path.read_bytes()
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))
        return
    except OSError:
        st.error("The approved-reply export could not be prepared.")
        return

    st.download_button(
        "Download approved replies as CSV",
        data=data,
        file_name="approved-replies.csv",
        mime="text/csv",
        key="inbox_helper.approved_export",
    )
