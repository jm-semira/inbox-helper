"""Local Streamlit entry point for Inbox Helper."""

import streamlit as st

from inbox_helper.composition import create_ui_application
from inbox_helper.core.config import get_config
from inbox_helper.core.exceptions import InboxHelperError
from inbox_helper.ui.errors import safe_error_message
from inbox_helper.ui.pages import dashboard, inbox, review_queue
from inbox_helper.ui.session_state import initialize_session_state


PAGES = ("Dashboard", "Inbox", "Review Queue")


def main() -> None:
    """Render the local triage application."""
    st.set_page_config(page_title="Inbox Helper", layout="wide")
    initialize_session_state(st.session_state)
    flash = st.session_state.pop("inbox_helper.flash", None)
    if flash is not None:
        kind, message = flash
        getattr(st, kind)(message)
    navigate_to = st.session_state.pop("inbox_helper.navigate_to", None)
    if navigate_to in PAGES:
        st.session_state["inbox_helper.page"] = navigate_to
    try:
        config = get_config()
        if config.demo_mode:
            st.warning(
                "**Demo Mode:** responses are predefined mock outputs, "
                "not actual AI-generated results."
            )
        elif config.llm_provider == "ollama":
            st.info("Ollama AI Mode")
            st.text(f"Local model: {config.llm_model}")
        else:
            st.caption("**Mock Mode:** deterministic mock provider.")
        page_name = st.sidebar.selectbox(
            "Navigate",
            options=PAGES,
            key="inbox_helper.page",
        )
        with create_ui_application(config) as services:
            if config.llm_provider == "ollama" and st.sidebar.button(
                "Check Ollama connection",
                key="inbox_helper.ollama_health_check",
            ):
                if services.provider_health.check():
                    st.sidebar.success(
                        "Ollama service is reachable. This does not confirm "
                        "the configured model is available."
                    )
                else:
                    st.sidebar.warning(
                        "Ollama is unavailable. Start the local service and "
                        "verify OLLAMA_BASE_URL."
                    )
            if page_name == "Dashboard":
                dashboard.render(services)
            elif page_name == "Inbox":
                inbox.render(services)
            else:
                review_queue.render(services)
    except InboxHelperError as error:
        st.error(safe_error_message(error))
    except OSError:
        st.error("The local database could not be opened.")


if __name__ == "__main__":
    main()
