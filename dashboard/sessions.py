"""Restore a server-validated login after a browser-tab refresh."""
from __future__ import annotations

import secrets

import streamlit as st
from streamlit.components.v2 import component

from dashboard.session_store import SessionStore
from dashboard.access import DirectoryUser


# Only an opaque token is stored in this tab. No URL parameters or credentials.
_browser_bridge = component("dashboard_session", js="""
const handled = new WeakMap();
export default function({parentElement, data, setStateValue}) {
    if (handled.get(parentElement) === data.id) return;
    handled.set(parentElement, data.id);
    const key = "model-monitoring.session:/" + data.base_path;
    try {
        if (data.action === "write") sessionStorage.setItem(key, data.token);
        if (data.action === "clear") sessionStorage.removeItem(key);
        setStateValue("snapshot", {
            id: data.id, token: sessionStorage.getItem(key), error: false
        });
    } catch (_) {
        setStateValue("snapshot", {id: data.id, token: null, error: true});
    }
}
""")


@st.cache_resource
def get_session_store() -> SessionStore:
    # One store per server process, shared across Streamlit WebSocket sessions.
    return SessionStore()


def _command(action: str, token: str | None = None) -> dict:
    return {"id": secrets.token_hex(16), "action": action, "token": token,
            "base_path": st.get_option("server.baseUrlPath").strip("/")}


def begin_session(user: DirectoryUser) -> None:
    store = get_session_store()
    store.revoke(st.session_state.get("_auth_token"))
    token = store.create(user)
    st.session_state["_auth_token"] = token
    st.session_state["_auth_command"] = _command("write", token)
    st.session_state["selected_page"] = "Home"


def end_session() -> None:
    get_session_store().revoke(st.session_state.get("_auth_token"))
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state["_auth_command"] = _command("clear")


def restore_session(page_path: str = "") -> DirectoryUser | None:
    # Streamlit clears component state when switching pages, while the browser
    # may reuse its DOM. Issue a fresh read so the bridge publishes a new snapshot.
    previous_path = st.session_state.get("_auth_page_path")
    if previous_path is not None and previous_path != page_path:
        st.session_state["_auth_command"] = _command("read")
    st.session_state["_auth_page_path"] = page_path
    command = st.session_state.setdefault("_auth_command", _command("read"))
    result = _browser_bridge(
        data=command, key="session_bridge", height=1,
        default={"snapshot": None}, on_snapshot_change=lambda: None,
    )
    snapshot = result.snapshot
    if not isinstance(snapshot, dict) or snapshot.get("id") != command["id"]:
        st.caption("Restoring your session...")
        st.stop()
    if snapshot.get("error"):
        st.error("Allow browser storage for this site, then reload to sign in.")
        st.stop()

    token = snapshot.get("token")
    # The browser supplies no trusted identity: validate the token on every run.
    user = get_session_store().resolve_user(token)
    if user:
        st.session_state["_auth_token"] = token
        st.session_state["authenticated_user"] = user.username
        return user

    st.session_state.pop("authenticated_user", None)
    st.session_state.pop("_auth_token", None)
    if token:
        # Expired, revoked, or from a previous server process.
        st.session_state["_auth_command"] = _command("clear")
        st.rerun()
    return None
