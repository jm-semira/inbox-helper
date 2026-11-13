"""Namespaced Streamlit session-state initialization."""

from typing import Any


def initialize_session_state(state: Any) -> None:
    """Initialize UI-only state without copying email or draft content."""
    defaults: dict[str, object] = {
        "inbox_helper.page": "Dashboard",
        "inbox_helper.selected_email_id": None,
        "inbox_helper.classifications": {},
        "inbox_helper.generated_for_email_ids": set(),
        "inbox_helper.flash": None,
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value
