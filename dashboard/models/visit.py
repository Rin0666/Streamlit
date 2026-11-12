from __future__ import annotations

import streamlit as st

from dashboard.config import ModelConfig


def render_placeholder(config: ModelConfig) -> None:
    st.title("Visit Prediction Monitoring")
    st.caption("Ready for visit prediction model monitoring.")
    st.info(
        f"Add a visit monitoring workbook at `{config.workbook_path}` and map its data "
        "sheets in `dashboard/models/visit.py`."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Cycles", "-")
    col2.metric("Prediction Target", "Visit")
    col3.metric("Status", "Scaffolded")
