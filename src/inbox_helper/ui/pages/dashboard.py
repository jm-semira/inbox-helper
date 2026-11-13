"""Dashboard presentation."""

import streamlit as st

from inbox_helper.composition import UiApplicationServices
from inbox_helper.core.exceptions import InboxHelperError
from inbox_helper.ui.errors import safe_error_message


def render(services: UiApplicationServices) -> None:
    """Render workflow totals without accessing persistence directly."""
    st.title("Inbox Helper")
    st.caption("Local email triage with human-controlled reply review.")
    try:
        stats = services.dashboard.get_stats()
    except InboxHelperError as error:
        st.error(safe_error_message(error, services.llm_provider))
        return

    columns = st.columns(4)
    columns[0].metric("Imported emails", stats.total_emails)
    columns[1].metric("Pending drafts", stats.pending_drafts)
    columns[2].metric("Approved drafts", stats.approved_drafts)
    columns[3].metric("Rejected drafts", stats.rejected_drafts)
    st.metric("Drafts with classification snapshots", stats.classified_drafts)
    st.caption(
        "This metric counts snapshots stored with drafts. A classification "
        "retained for processing recovery is not included."
    )
    if stats.total_emails == 0:
        st.info("Your inbox is empty. Import a CSV from the Inbox page to begin.")
    elif stats.pending_drafts == 0:
        st.info("There are no drafts awaiting review.")
