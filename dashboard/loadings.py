"""Read and summarize the supplied Engage loading-adjustment query."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


QUERY_PATH = Path(__file__).resolve().parent.parent / "queries" / "engage" / "Loadings.sql"
COLUMNS = ["EventName", "TransEmployee", "OfferDate", "Universalplayerid",
           "AdjustmentDate", "AdjustmentAmount", "AdjustmentAction"]
MANILA = timezone(timedelta(hours=8))


class LoadingsDataError(Exception):
    pass


def normalize_loadings(raw: pd.DataFrame) -> pd.DataFrame:
    missing = set(COLUMNS) - set(raw.columns)
    if missing:
        raise LoadingsDataError("The loadings query did not return the expected columns.")
    data = raw[COLUMNS].copy()
    for column in ("OfferDate", "AdjustmentDate"):
        data[column] = pd.to_datetime(data[column], errors="coerce")
    data["AdjustmentAmount"] = pd.to_numeric(data["AdjustmentAmount"], errors="coerce")
    for column in ("EventName", "TransEmployee", "Universalplayerid", "AdjustmentAction"):
        data[column] = data[column].astype("string")
    return data.sort_values("AdjustmentDate", ascending=False, na_position="last")


@st.cache_data(ttl=60, max_entries=2, show_spinner=False)
def fetch_loadings(query: str) -> tuple[pd.DataFrame, datetime]:
    try:
        # The supplied helper's HALO server hosts the fully qualified ENGAGEDB tables.
        # Import lazily: other dashboard pages do not open a database connection.
        from okada import SQL

        raw = SQL("Engage").get_loader().load_data(query)
    except Exception as error:
        from dashboard.connections import sql_failure_detail
        raise LoadingsDataError(
            "Unable to read loadings from Engage. " + sql_failure_detail(error)
            + " Open Connections Checker and run the Engage SQL checks for details."
        ) from None
    return normalize_loadings(raw), datetime.now(MANILA)


def adjustment_window(start: date, end: date) -> tuple[datetime, datetime]:
    if start > end:
        raise LoadingsDataError("The adjustment start date must be on or before the end date.")
    return (
        datetime.combine(start, time(hour=6)),
        datetime.combine(end + timedelta(days=1), time(hour=6)),
    )


def render_loadings_query(query: str, start: date, end: date) -> str:
    start_at, end_at = adjustment_window(start, end)
    placeholders = ("{{ADJUSTMENT_START}}", "{{ADJUSTMENT_END}}")
    if any(placeholder not in query for placeholder in placeholders):
        raise LoadingsDataError(
            "The loadings query must contain {{ADJUSTMENT_START}} and {{ADJUSTMENT_END}} placeholders."
        )
    return query.replace(placeholders[0], start_at.isoformat(sep=" ")).replace(
        placeholders[1], end_at.isoformat(sep=" ")
    )


def load_loadings(start: date, end: date) -> tuple[pd.DataFrame, datetime]:
    query = read_loadings_query()
    return fetch_loadings(render_loadings_query(query, start, end))


def read_loadings_query() -> str:
    try:
        return QUERY_PATH.read_text(encoding="utf-8-sig")
    except OSError:
        raise LoadingsDataError("The loadings query file is missing or unreadable. Restart the local launcher.") from None


def save_loadings_query(query: str) -> None:
    if not query.strip():
        raise LoadingsDataError("The loadings query cannot be empty.")
    if any(placeholder not in query for placeholder in ("{{ADJUSTMENT_START}}", "{{ADJUSTMENT_END}}")):
        raise LoadingsDataError(
            "The loadings query must keep the {{ADJUSTMENT_START}} and {{ADJUSTMENT_END}} placeholders."
        )
    try:
        QUERY_PATH.write_text(query, encoding="utf-8")
    except OSError:
        raise LoadingsDataError("Unable to save the loadings query. Check access to the query file.") from None


def filter_loadings(data, start, end, employees=(), actions=(), patron="",
                    offer_date=None, events=()):
    filtered = data
    if start is not None and end is not None:
        start_at, end_at = adjustment_window(start, end)
        dates = filtered["AdjustmentDate"]
        filtered = filtered[(dates >= pd.Timestamp(start_at)) &
                            (dates < pd.Timestamp(end_at))]
    if employees:
        filtered = filtered[filtered["TransEmployee"].isin(employees)]
    if events:
        filtered = filtered[filtered["EventName"].isin(events)]
    if actions:
        filtered = filtered[filtered["AdjustmentAction"].isin(actions)]
    if patron.strip():
        filtered = filtered[filtered["Universalplayerid"].eq(patron.strip()).fillna(False)]
    if offer_date is not None:
        offer_dates = filtered["OfferDate"]
        filtered = filtered[offer_dates.dt.date.eq(offer_date)]
    return filtered.copy()


def summarize_loadings(data: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    return data.groupby(groups, dropna=False).agg(
        Records=("AdjustmentAmount", "size"),
        Patrons=("Universalplayerid", "nunique"),
        Amount=("AdjustmentAmount", lambda amounts: amounts.sum(min_count=1)),
    ).reset_index()


def summarize_monitoring(data: pd.DataFrame, group: str) -> pd.DataFrame:
    if group not in {"TransEmployee", "EventName"}:
        raise ValueError("Summary group must be TransEmployee or EventName.")
    return data.groupby([group, "AdjustmentAction"], dropna=False).agg(**{
        "Total Loadings test": ("AdjustmentAmount", "sum"),
        "Unique Headcount": ("Universalplayerid", "nunique"),
        "Load Count": ("AdjustmentAmount", "size"),
        "Max Adjustment Date": ("AdjustmentDate", "max"),
    }).reset_index()
