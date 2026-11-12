from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from dashboard.loadings import (
    MANILA, LoadingsDataError, fetch_loadings, filter_loadings, load_loadings,
    read_loadings_query, save_loadings_query, summarize_loadings, summarize_monitoring,
)


def manila_today():
    return datetime.now(MANILA).date()


def toggle_query_editor() -> None:
    st.session_state["show_loadings_query_editor"] = not st.session_state.get(
        "show_loadings_query_editor", False)


def render_loadings_page() -> None:
    st.title("Loadings Monitoring")
    st.caption("Monitor loading adjustments recorded in Engage.")
    refresh, edit, _ = st.columns([1, 1, 4])
    refresh.button("Refresh data", key="refresh_loadings", on_click=fetch_loadings.clear,
                   icon=":material/refresh:")
    edit.button("Edit query", key="edit_loadings_query", on_click=toggle_query_editor,
                icon=":material/edit:")
    if st.session_state.get("show_loadings_query_editor", False):
        try:
            current_query = read_loadings_query()
        except LoadingsDataError as error:
            st.error(str(error))
            return
        edited_query = st.text_area(
            "Loadings.sql", value=current_query, height=360, key="loadings_query_editor",
        )
        if st.button("Save query", type="primary", key="save_loadings_query",
                     icon=":material/save:"):
            try:
                save_loadings_query(edited_query)
            except LoadingsDataError as error:
                st.error(str(error))
            else:
                fetch_loadings.clear()
                st.success("Loadings query saved. Data below was refreshed using the updated query.")

    today = manila_today()
    default_start = today - timedelta(days=6)
    date_range = st.date_input(
        "Adjustment dates", value=(default_start, today), key="loadings_dates",
        help="Each selected date runs from 6:00 AM through 5:59:59 AM the following day.",
    )
    if len(date_range) != 2:
        st.info("Select both a start and end date.")
        return
    start, end = date_range
    try:
        with st.spinner("Reading loadings..."):
            data, fetched_at = load_loadings(start, end)
    except LoadingsDataError as error:
        st.error(str(error))
        return
    st.caption(f"Last fetched: {fetched_at:%b %d, %Y %H:%M:%S} Manila time. "
               "Results are cached for up to 60 seconds; use Refresh data for the latest records.")
    if data.empty:
        st.info("No loading adjustments were returned.")
        return

    dates = data["AdjustmentDate"].dropna()
    if (data["AdjustmentDate"].isna().any() or data["OfferDate"].isna().any()
            or data["AdjustmentAmount"].isna().any()):
        st.warning("Some records have missing or invalid dates or amounts. "
                   "Date filters exclude undated records; amount totals exclude missing amounts.")
    left, middle, right = st.columns(3)
    employees = left.multiselect("Transaction employee", sorted(data["TransEmployee"].dropna().unique()),
                                 key="loadings_employees")
    events = middle.multiselect("Event name", sorted(data["EventName"].dropna().unique()),
                                key="loadings_events")
    actions = right.multiselect("Adjustment action", sorted(data["AdjustmentAction"].dropna().unique()),
                                 key="loadings_actions")
    left, right = st.columns(2)
    offer_date = left.date_input("Offer date", value=None, key="loadings_offer_date")
    patron = right.text_input("Patron ID", key="loadings_patron", placeholder="Exact patron ID")
    filtered = filter_loadings(data, start, end, employees, actions, patron,
                               offer_date=offer_date, events=events)
    if filtered.empty:
        st.info("No loading adjustments match these filters.")
        return

    records, patrons, amount = st.columns(3)
    records.metric("Adjustment records", f"{len(filtered):,}")
    patrons.metric("Unique patrons", f"{filtered['Universalplayerid'].nunique():,}")
    total = filtered["AdjustmentAmount"].sum(min_count=1)
    hc = filtered["Universalplayerid"].nunique()
    amount.metric("Recorded adjustment amount", f"{total:,.2f}" if total == total else "—")
    st.caption("Amounts use the values returned by Engage. Actions are kept separate below; "
               "totals do not infer credits, debits, or successful delivery.")

    summary_group = st.radio(
        "Summary group", ("Transaction employee", "Event name"), horizontal=True,
        key="loadings_summary_group",
    )
    summary_column = "TransEmployee" if summary_group == "Transaction employee" else "EventName"
    st.subheader(f"{summary_group} and action summary")
    summary = summarize_monitoring(filtered, summary_column)
    st.dataframe(summary, hide_index=True, width="stretch")

    daily_data = filtered.dropna(subset=["AdjustmentDate"]).assign(
        Date=lambda frame: frame["AdjustmentDate"].dt.normalize())
    daily_hc = daily_data.groupby("Date", dropna=False)["Universalplayerid"].nunique().rename("Patrons")
    if not daily_data.empty:
        st.subheader("Daily adjustments")
        daily = summarize_loadings(daily_data, ["Date", "AdjustmentAction"])
        st.bar_chart(daily, x="Date", y="Amount", color="AdjustmentAction")
    if not daily_hc.empty:
        st.subheader("Daily unique patrons")
        st.line_chart(daily_hc)
    st.subheader("Raw loading records")
    st.dataframe(filtered, hide_index=True, width="stretch")
