import streamlit as st

from dashboard import access
from dashboard.access_editor import AccessEditError, read_access_document, save_access_document
from dashboard.sessions import get_session_store


def render_page_access_page() -> None:
    st.title("Page Access")
    st.caption("Edit the groups and maximum tigerLevel allowed for each page, then save the YAML file.")
    user = get_session_store().resolve_user(st.session_state.get("_auth_token"))
    if user is None:
        st.error("Your session has expired. Sign in again.")
        return
    try:
        current = read_access_document(user)
    except AccessEditError as error:
        st.error(str(error))
        return

    st.caption(f"File: {access.ACCESS_FILE}")
    if notice := st.session_state.pop("_access_editor_notice", None):
        st.success(notice)
    reload_requested = st.button("Reload from disk", icon=":material/refresh:",
                                 help="Discard the current draft and load the saved file.")
    if reload_requested or "_access_editor_document" not in st.session_state:
        st.session_state["_access_editor_document"] = current
        st.session_state["access_editor_yaml"] = current.text
    document = st.session_state["_access_editor_document"]
    if "access_editor_yaml" not in st.session_state:
        st.session_state["access_editor_yaml"] = document.text
    if document.revision != current.revision:
        st.warning("The saved file has changed. Copy any draft changes you need, then reload from disk.")

    with st.form("page_access_editor"):
        text = st.text_area("page_access.yaml", key="access_editor_yaml", height=450,
                            help="Page URL → group name → maximum tigerLevel. Use {} to deny a page.")
        submitted = st.form_submit_button("Save changes", type="primary")
    st.caption("A matching group and tigerLevel at or below its limit grants access. "
               "The previous file is kept as page_access.yaml.bak.")
    if submitted:
        # Re-resolve the server-side identity at the point of mutation.
        user = get_session_store().resolve_user(st.session_state.get("_auth_token"))
        if user is None:
            st.error("Your session has expired. Sign in again.")
            return
        try:
            saved = save_access_document(user, text, document.revision)
        except AccessEditError as error:
            st.error(str(error))
        else:
            st.session_state["_access_editor_document"] = saved
            st.session_state["_access_editor_notice"] = "Page access saved. Changes apply on each user's next interaction."
            st.rerun()
