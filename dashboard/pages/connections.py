from datetime import datetime

import streamlit as st

from dashboard.connections import CHECK_OPTIONS, run_checks
from dashboard.loadings import MANILA


def render_connections_page() -> None:
    st.title("Connections Checker")
    st.caption("Check the connections used by this app from the machine running it.")
    selection = st.selectbox("Check", CHECK_OPTIONS, key="connections_selection")
    if st.button("Run checks", type="primary", key="run_connection_checks"):
        with st.spinner("Checking connections..."):
            results = run_checks(selection)
        st.session_state["connection_results"] = (selection, datetime.now(MANILA), results)

    saved = st.session_state.get("connection_results")
    if saved:
        checked, checked_at, results = saved
        st.caption(f"Last check: {checked_at:%b %d, %Y %H:%M:%S} Manila time · {checked}")
        columns = st.columns(3)
        for column, status in zip(columns, ("Passed", "Failed", "Skipped")):
            column.metric(status, sum(row["status"] == status for row in results))
        for result in results:
            message = f"**{result['check']}** — {result['detail']} ({result['elapsed_ms']:,} ms)"
            {"Passed": st.success, "Failed": st.error, "Skipped": st.info}[result["status"]](message)
    else:
        st.info("Choose a connection and select Run checks.")
    st.caption("Checks are read-only. LDAP checks verify the secure connection, not your password. "
               "Database checks use each connector's configured credentials or Windows authentication; "
               "they do not use your LDAP login.")
