import streamlit as st

from dashboard.member_profile import SAMPLE_SIZES, MemberProfileDataError, load_member_profile


def render_member_profile_page() -> None:
    st.title("Member Profile")
    st.caption("Search Datamart using at least one field. Names use case-insensitive exact matches; "
               "all supplied fields must match.")
    id_column, first_column, last_column = st.columns(3)
    universal_player_id = id_column.text_input("UniversalPlayerID", key="member_profile_id").strip()
    first_name = first_column.text_input("FirstName", key="member_profile_first_name").strip()
    last_name = last_column.text_input("LastName", key="member_profile_last_name").strip()
    row_limit = st.selectbox("Result limit", SAMPLE_SIZES, format_func=lambda value: f"{value:,} rows",
                             key="member_profile_sample_size")
    if st.button("Search", type="primary", key="load_member_profile"):
        st.session_state.pop("member_profile_datamart_results", None)
        if not any((universal_player_id, first_name, last_name)):
            st.warning("Enter at least one of UniversalPlayerID, FirstName, or LastName.")
            return
        try:
            with st.spinner("Loading member profiles..."):
                data, fetched_at = load_member_profile(
                    row_limit, universal_player_id=universal_player_id,
                    first_name=first_name, last_name=last_name,
                )
            st.session_state["member_profile_datamart_results"] = (data, fetched_at, row_limit)
        except MemberProfileDataError as error:
            st.error(str(error))
            return

    saved = st.session_state.get("member_profile_datamart_results")
    if saved is None:
        st.info("Enter UniversalPlayerID, FirstName, or LastName and select Search.")
        return
    data, fetched_at, loaded_limit = saved
    st.caption(f"Last loaded: {fetched_at:%b %d, %Y %H:%M:%S} Manila time. "
               f"Result limit: {loaded_limit:,} rows. Select Search to refresh.")
    if data.empty:
        st.info("No member profiles were returned.")
    st.metric("Rows loaded", f"{len(data):,}")
    st.dataframe(data, hide_index=True, width="stretch")
