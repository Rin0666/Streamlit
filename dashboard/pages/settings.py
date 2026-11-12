from __future__ import annotations

import streamlit as st

from dashboard.config import MODEL_CONFIGS


def render_settings_page() -> None:
    st.title("Configuration")
    st.caption("Dashboard model and workbook configuration.")

    st.subheader("Registered Models")
    rows = [
        {
            "key": config.key,
            "label": config.label,
            "workbook": str(config.workbook_path),
        }
        for config in MODEL_CONFIGS.values()
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def render_models_availability_page() -> None:
    st.title("Models Availability")
    st.caption("Availability in the dashboard; this does not check database or workbook connectivity.")
    rows = [
        {"Model": config.label, "Status": "Available" if config.available else "Coming soon"}
        for config in MODEL_CONFIGS.values()
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
