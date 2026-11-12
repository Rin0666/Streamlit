from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


DATA_SHEETS = [
    "Metrics Data",
    "Threshold Data",
    "Decile Data",
    "P Campaign Data",
    "Score PSI Data",
    "Feature PSI Data",
    "Top Features (SHAP)",
]


@st.cache_data
def load_excel_data(workbook_path: Path) -> dict[str, pd.DataFrame]:
    if not workbook_path.exists():
        return {}

    workbook = pd.ExcelFile(workbook_path)
    available_sheets = [sheet for sheet in DATA_SHEETS if sheet in workbook.sheet_names]
    if not available_sheets:
        return {}
    return pd.read_excel(workbook_path, sheet_name=available_sheets)


def normalize_ref_date(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    if "ref_date" in normalized:
        normalized["ref_date"] = pd.to_datetime(normalized["ref_date"])
    return normalized


def get_cycle_options(workbook_path: Path) -> list[pd.Timestamp]:
    data = load_excel_data(workbook_path)
    if not data or "Metrics Data" not in data:
        return []

    ref_dates = pd.to_datetime(data["Metrics Data"]["ref_date"]).dropna().drop_duplicates()
    return sorted(ref_dates, reverse=True)


def resolve_cycle_date(cycle_date: object | None, fallback_data: pd.DataFrame) -> pd.Timestamp:
    if cycle_date is not None:
        return pd.Timestamp(cycle_date)
    if fallback_data.empty or "ref_date" not in fallback_data:
        return pd.Timestamp.today().normalize()
    return pd.Timestamp(pd.to_datetime(fallback_data["ref_date"]).max())
