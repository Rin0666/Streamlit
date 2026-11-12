from __future__ import annotations

import streamlit as st

from dashboard.access import DirectoryUser, is_master_user
from dashboard.deployment import DeploymentClient, DeploymentClientError


ACTIVE_STATUSES = {
    "queued", "checking", "fetching", "pulling", "building", "starting",
    "health_check", "rolling_back",
}


def short_commit(value) -> str:
    return str(value)[:12] if value else "Unknown"


def render_deployment_page(user: DirectoryUser) -> None:
    st.title("Application Deployment")
    st.caption("Check the approved main branch and request a host-managed Docker deployment.")
    if not is_master_user(user):
        st.error("Only a master administrator can deploy the application.")
        return
    try:
        client = DeploymentClient()
    except DeploymentClientError as error:
        st.info(str(error))
        return

    active_id = st.session_state.get("deployment_id")
    active = None
    if active_id:
        try:
            active = client.status(active_id)
        except DeploymentClientError as error:
            st.warning(str(error))
        if active:
            status = active.get("status", "unknown")
            st.subheader("Deployment progress")
            st.write(f"Status: **{status.replace('_', ' ').title()}**")
            st.write(active.get("message", ""))
            if status in ACTIVE_STATUSES:
                st.info("The deployment continues on the host even if this page or container restarts.")
            elif status == "success":
                st.success(f"Deployment completed at commit {short_commit(active.get('new_commit'))}.")
            elif status == "rolled_back":
                st.warning("The update failed and the previous image was restored.")
            elif status == "failed":
                st.error(active.get("message", "Deployment failed."))

    try:
        version = client.version()
    except DeploymentClientError as error:
        st.error(str(error))
        return

    current, remote = st.columns(2)
    current.metric("Deployed commit", short_commit(version.get("deployed_commit")))
    remote.metric("Remote main commit", short_commit(version.get("remote_commit")))
    st.caption(f"Production checkout: {short_commit(version.get('repository_commit'))} · "
               f"Branch: {version.get('branch', 'main')}")

    service_active = version.get("deployment_in_progress")
    update_available = bool(version.get("update_available"))
    if service_active:
        st.info(f"Deployment {service_active.get('deployment_id', '')} is already in progress.")
    elif update_available:
        st.warning("An application update is available.")
    else:
        st.success("The deployed application is up to date.")

    if st.button("Update Application", type="primary", icon=":material/system_update_alt:",
                 disabled=bool(service_active) or not update_available,
                 key="start_application_deployment"):
        try:
            record = client.deploy(user.username)
        except DeploymentClientError as error:
            st.error(str(error))
        else:
            st.session_state["deployment_id"] = record["deployment_id"]
            st.rerun()
    st.button("Refresh status", icon=":material/refresh:", key="refresh_deployment_status")
