from __future__ import annotations

import streamlit as st


def apply_dashboard_style() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppDeployButton"] {
            display: none;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button {
            justify-content: flex-start;
            border-radius: 8px;
            padding: 0.65rem 0.85rem;
        }
        [data-testid="stSidebar"] button[kind="secondary"] {
            background: transparent;
            border-color: transparent;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background: rgba(128, 100, 162, 0.12);
            color: #76397b;
        }
        [data-testid="stMetric"] {
            background: #fbfaf6;
            border: 1px solid #ded9ca;
            border-radius: 6px;
            padding: 14px 16px;
        }
        [data-testid="stMetricLabel"] {
            color: #76397b;
        }
        .status-stable {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #eaf2dd;
            color: #4f6f28;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
