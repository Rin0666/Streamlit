from __future__ import annotations

import streamlit as st

from dashboard.auth import AuthenticationError, LDAPSettings, authenticate
from dashboard.sessions import begin_session


def render_login_page() -> None:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.caption("Sign in with your network username, without an email address or domain.")
        with st.form("login", clear_on_submit=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            try:
                settings = LDAPSettings.from_mapping()
                with st.spinner("Signing in..."):
                    identity = authenticate(username, password, settings)
            except AuthenticationError as error:
                st.error(str(error))
            else:
                begin_session(identity)
                st.rerun()
