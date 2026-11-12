from __future__ import annotations

import altair as alt
import pandas as pd

from dashboard.config import EXCEL_COLORS


def line_chart(
    data: pd.DataFrame,
    colors: list[str] | None = None,
    y_format: str = ".3f",
) -> alt.Chart:
    chart_data = data.reset_index().melt(
        id_vars=data.index.name or "index",
        var_name="Metric",
        value_name="Value",
    )
    x_col = data.index.name or "index"
    return (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(f"{x_col}:T", title=None),
            y=alt.Y("Value:Q", title=None, axis=alt.Axis(format=y_format)),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=colors or list(EXCEL_COLORS.values())),
                legend=alt.Legend(orient="bottom"),
            ),
            tooltip=[x_col, "Metric", alt.Tooltip("Value:Q", format=y_format)],
        )
        .properties(height=320)
    )


def bar_chart(
    data: pd.DataFrame,
    colors: list[str] | None = None,
    y_format: str = ".3f",
) -> alt.Chart:
    x_col = data.index.name or "index"
    chart_data = data.reset_index()
    if pd.api.types.is_datetime64_any_dtype(chart_data[x_col]):
        chart_data[x_col] = chart_data[x_col].dt.strftime("%b %d")
    else:
        chart_data[x_col] = chart_data[x_col].astype(str)

    chart_data = chart_data.melt(
        id_vars=x_col,
        var_name="Metric",
        value_name="Value",
    )
    return (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X(f"{x_col}:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Value:Q", title=None, axis=alt.Axis(format=y_format)),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(range=colors or list(EXCEL_COLORS.values())),
                legend=alt.Legend(orient="bottom"),
            ),
            tooltip=[x_col, "Metric", alt.Tooltip("Value:Q", format=y_format)],
        )
        .properties(height=300)
    )
