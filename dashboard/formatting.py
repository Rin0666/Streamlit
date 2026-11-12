from __future__ import annotations

import pandas as pd


def format_percent(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return f"{value:.1%}"


def format_number(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return f"{value:,.0f}"
