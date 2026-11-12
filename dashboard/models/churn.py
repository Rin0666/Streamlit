from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.charts import bar_chart, line_chart
from dashboard.config import EXCEL_COLORS, ModelConfig
from dashboard.data import load_excel_data, normalize_ref_date, resolve_cycle_date
from dashboard.formatting import format_number, format_percent


def load_model_data(config: ModelConfig) -> dict[str, pd.DataFrame]:
    return load_excel_data(config.workbook_path)


def render_missing_data_source(config: ModelConfig) -> None:
    st.error(f"Data source workbook was not found at `{config.workbook_path}`.")
    st.info(
        "Place the Excel monitoring data workbook in the `data_sources` folder, or run "
        "`run_streamlit_local.bat` so the launcher copies it to the local temp app."
    )


def render_executive_summary(config: ModelConfig, cycle_date: object | None = None) -> None:
    data = load_model_data(config)
    if not data:
        render_missing_data_source(config)
        return

    metrics = normalize_ref_date(data["Metrics Data"])
    campaign = normalize_ref_date(data["P Campaign Data"])
    score_psi = normalize_ref_date(data["Score PSI Data"])
    shap = data["Top Features (SHAP)"].copy()
    decile = normalize_ref_date(data["Decile Data"])

    full_population = metrics[metrics["segment"].eq("Full Population")]
    selected_date = resolve_cycle_date(cycle_date, full_population)
    latest = full_population[full_population["ref_date"].eq(selected_date)].iloc[0]
    latest_psi = score_psi[score_psi["ref_date"].eq(selected_date)].iloc[0]
    latest_decile = decile[decile["ref_date"].eq(selected_date)]

    st.title("Churn Model Monitoring")
    st.caption("Streamlit view based on the workbook visual layout. Data comes from workbook data sheets.")
    st.markdown(
        f"""
        Monitoring cycle: **{selected_date:%B %d, %Y}**  
        Population: **Full Population**
        """
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Samples", format_number(latest["n_samples"]))
    kpi2.metric("Actual Churn", format_percent(latest["actual_churn_rate"]))
    kpi3.metric("Predicted Churn", format_percent(latest["avg_predicted_probability"]))
    kpi4.metric("Score PSI", f"{latest_psi['score_psi']:.3f}", str(latest_psi["severity"]).title())

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Actual vs Predicted Churn")
        trend = full_population.set_index("ref_date")[
            ["actual_churn_rate", "avg_predicted_probability"]
        ]
        st.altair_chart(
            line_chart(
                trend,
                colors=[EXCEL_COLORS["deep_purple"], EXCEL_COLORS["orange"]],
                y_format=".1%",
            ),
            width="stretch",
        )

    with right:
        st.subheader("Model Health")
        st.markdown('<span class="status-stable">Within threshold</span>', unsafe_allow_html=True)
        st.metric("AUC ROC", f"{latest['auc_roc']:.3f}")
        st.metric("Average Precision", f"{latest['average_precision']:.3f}")
        st.metric("Calibration Gap", format_percent(latest["calibration_gap_actual_minus_pred"]))

    st.subheader("Risk Decile Performance")
    latest_full_decile = latest_decile[latest_decile["segment"].eq("Full Population")].copy()
    latest_full_decile["decile"] = pd.to_numeric(latest_full_decile["decile"])
    latest_full_decile = latest_full_decile.sort_values("decile")
    latest_full_decile["decile"] = latest_full_decile["decile"].astype(str)
    decile_chart = latest_full_decile.set_index("decile")[
        ["decile_churn_rate", "avg_predicted_prob"]
    ]
    st.altair_chart(
        bar_chart(
            decile_chart,
            colors=[EXCEL_COLORS["bright_purple"], EXCEL_COLORS["teal"]],
            y_format=".1%",
        ),
        width="stretch",
    )
    st.dataframe(
        latest_full_decile[
            ["decile", "n_patrons", "n_churners", "decile_churn_rate", "lift", "avg_predicted_prob"]
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("Top Model Drivers")
    top_features = shap.head(10).set_index("feature")[["mean_abs_shap"]]
    st.altair_chart(bar_chart(top_features, colors=[EXCEL_COLORS["purple"]]), width="stretch")

    st.subheader("Campaign Effect")
    latest_campaign = campaign[campaign["ref_date"].eq(selected_date)]
    st.dataframe(
        latest_campaign[
            [
                "comparison",
                "n_treatment",
                "n_control",
                "churn_rate_T",
                "churn_rate_C",
                "abs_diff_T_minus_C",
            ]
        ],
        width="stretch",
        hide_index=True,
    )


def render_model_performance(config: ModelConfig, cycle_date: object | None = None) -> None:
    data = load_model_data(config)
    if not data:
        render_missing_data_source(config)
        return

    metrics = normalize_ref_date(data["Metrics Data"])

    st.title("Model Performance")
    segment = st.selectbox("Segment", sorted(metrics["segment"].dropna().unique()))
    segment_data = metrics[metrics["segment"].eq(segment)].sort_values("ref_date")
    selected_date = resolve_cycle_date(cycle_date, segment_data)
    selected_rows = segment_data[segment_data["ref_date"].eq(selected_date)]

    if not selected_rows.empty:
        current = selected_rows.iloc[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Cycle AUC ROC", f"{current['auc_roc']:.3f}")
        col2.metric("Cycle Avg Precision", f"{current['average_precision']:.3f}")
        col3.metric("Cycle Calibration Gap", format_percent(current["calibration_gap_actual_minus_pred"]))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Churn Calibration")
        st.altair_chart(
            line_chart(
                segment_data.set_index("ref_date")[
                    ["actual_churn_rate", "avg_predicted_probability"]
                ],
                colors=[EXCEL_COLORS["deep_purple"], EXCEL_COLORS["orange"]],
                y_format=".1%",
            ),
            width="stretch",
        )
    with col2:
        st.subheader("Ranking Quality")
        st.altair_chart(
            line_chart(
                segment_data.set_index("ref_date")[["auc_roc", "average_precision"]],
                colors=[EXCEL_COLORS["blue"], EXCEL_COLORS["green"]],
            ),
            width="stretch",
        )

    st.subheader("Metrics Table")
    st.dataframe(segment_data, width="stretch", hide_index=True)


def render_campaign(config: ModelConfig, cycle_date: object | None = None) -> None:
    data = load_model_data(config)
    if not data:
        render_missing_data_source(config)
        return

    campaign = normalize_ref_date(data["P Campaign Data"])

    st.title("Campaign Monitoring")
    comparison = st.selectbox("Comparison", sorted(campaign["comparison"].dropna().unique()))
    selected = campaign[campaign["comparison"].eq(comparison)].sort_values("ref_date")
    selected_date = resolve_cycle_date(cycle_date, selected)
    cycle_rows = selected[selected["ref_date"].eq(selected_date)]

    if not cycle_rows.empty:
        current = cycle_rows.iloc[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Treatment Churn", format_percent(current["churn_rate_T"]))
        col2.metric("Control Churn", format_percent(current["churn_rate_C"]))
        col3.metric("Difference", format_percent(current["abs_diff_T_minus_C"]))

    st.subheader("Treatment vs Control Churn")
    st.altair_chart(
        line_chart(
            selected.set_index("ref_date")[["churn_rate_T", "churn_rate_C"]],
            colors=[EXCEL_COLORS["bright_purple"], EXCEL_COLORS["blue"]],
            y_format=".1%",
        ),
        width="stretch",
    )

    st.subheader("Absolute Difference")
    st.altair_chart(
        bar_chart(
            selected.set_index("ref_date")[["abs_diff_T_minus_C"]],
            colors=[EXCEL_COLORS["red"]],
            y_format=".1%",
        ),
        width="stretch",
    )

    st.dataframe(selected, width="stretch", hide_index=True)


def render_drift(config: ModelConfig, cycle_date: object | None = None) -> None:
    data = load_model_data(config)
    if not data:
        render_missing_data_source(config)
        return

    score_psi = normalize_ref_date(data["Score PSI Data"])
    feature_psi = data["Feature PSI Data"].copy()

    st.title("Drift Monitoring")

    selected_date = resolve_cycle_date(cycle_date, score_psi)
    latest = score_psi[score_psi["ref_date"].eq(selected_date)].iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Latest Score PSI", f"{latest['score_psi']:.3f}")
    col2.metric("Severity", str(latest["severity"]).title())
    col3.metric("Flagged Population", format_percent(latest["pct_flagged_prod"]))

    st.subheader("Score PSI Trend")
    st.altair_chart(
        line_chart(
            score_psi.set_index("ref_date")[["score_psi"]],
            colors=[EXCEL_COLORS["purple"]],
        ),
        width="stretch",
    )

    st.subheader("Feature PSI")
    st.dataframe(
        feature_psi.sort_values("psi", ascending=False).head(50),
        width="stretch",
        hide_index=True,
    )
