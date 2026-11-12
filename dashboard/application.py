from __future__ import annotations

import streamlit as st

from dashboard.access import AccessConfigurationError, is_master_user, load_access_rules
from dashboard.config import MODEL_CONFIGS
from dashboard.data import get_cycle_options
from dashboard.header import render_account_header
from dashboard.models import churn, visit
from dashboard.navigation import (NavigationConfigurationError, accessible_categories,
                                  load_page_categories)
from dashboard.pages.home import open_page, render_home_page
from dashboard.pages.redemption import render_redemption_page
from dashboard.pages.ggr import render_ggr_page
from dashboard.pages.fex_ratings import render_fex_ratings_page
from dashboard.pages.login import render_login_page
from dashboard.pages.settings import render_settings_page, render_models_availability_page
from dashboard.pages.loadings import render_loadings_page
from dashboard.pages.member_profile import render_member_profile_page
from dashboard.pages.connections import render_connections_page
from dashboard.pages.deployment import render_deployment_page
from dashboard.pages.page_access import render_page_access_page
from dashboard.sessions import restore_session
from dashboard.theme import apply_dashboard_style


def main() -> None:
    apply_dashboard_style()
    page_renderers = {
        "redemption": render_redemption_page,
        "ggr": render_ggr_page,
        "fex_ratings": render_fex_ratings_page,
        "configuration": render_settings_page,
        "models_availability": render_models_availability_page,
        "loadings": render_loadings_page,
        "connections": render_connections_page,
        "member_profile": render_member_profile_page,
        "page_access": render_page_access_page,
        "deployment": None,
    }
    model_renderers = {
        "executive_summary": churn.render_executive_summary,
        "model_performance": churn.render_model_performance,
        "campaign": churn.render_campaign,
        "drift": churn.render_drift,
    }
    navigation_error = None
    try:
        categories = load_page_categories()
        pages = {page.title: page for category in categories for page in category.pages}
        if any(page.renderer not in page_renderers and page.renderer not in model_renderers
               for page in pages.values()):
            raise NavigationConfigurationError("Unknown page renderer in dashboard/pages.yaml.")
    except NavigationConfigurationError as error:
        navigation_error = str(error)
        categories, pages = (), {}
    # Register URLs before login so signing in at a deep link preserves the target.
    routes = {"Home": st.Page(lambda: None, title="Home", icon=":material/home:", default=True)}
    routes.update({title: st.Page(lambda: None, title=title, icon=page.icon,
                                 url_path=page.path.strip("/")) for title, page in pages.items()})
    selected = st.navigation(list(routes.values()), position="hidden")
    user = restore_session(selected.url_path)
    if not user:
        render_login_page()
        return
    render_account_header()
    if navigation_error:
        st.error(navigation_error)
        return
    try:
        rules = load_access_rules()
    except AccessConfigurationError as error:
        if not is_master_user(user):
            st.error(str(error))
            return
        rules = {}
        st.warning("Page access rules are unavailable or invalid. Your master access remains active; "
                   "use Page Access to repair the file.")
    visible_categories = accessible_categories(categories, user, rules)
    allowed_pages = [page.title for category in visible_categories for page in category.pages]
    requested = st.session_state.pop("_requested_page", None)
    if requested in ["Home", *allowed_pages]:
        st.switch_page(routes[requested])
        return
    page = selected.title
    st.session_state["selected_page"] = page
    st.sidebar.title("SMART")
    st.sidebar.text(f"Signed in as {user.username}")
    st.sidebar.button("Home", key="nav_Home", icon=":material/home:",
                      type="primary" if page == "Home" else "secondary",
                      on_click=open_page, args=("Home",), use_container_width=True)
    for category in visible_categories:
        with st.sidebar.expander(category.title,
                                 expanded=any(item.title == page for item in category.pages)):
            for item in category.pages:
                st.button(item.title, key=f"nav_{item.title}", icon=item.icon,
                          type="primary" if page == item.title else "secondary",
                          on_click=open_page, args=(item.title,), use_container_width=True)
    st.sidebar.divider()
    # Always guard dispatch: a hidden tile alone does not protect a direct URL.
    if page != "Home" and page not in allowed_pages:
        st.error("You do not have access to this page. Contact your administrator.")
        return
    selected.run()
    if page == "Home":
        render_home_page(visible_categories)
        return
    renderer = pages[page].renderer
    if renderer == "deployment":
        render_deployment_page(user)
        return
    if renderer in page_renderers:
        page_renderers[renderer]()
        return

    model_key = st.sidebar.selectbox("Model", list(MODEL_CONFIGS),
                                     format_func=lambda key: MODEL_CONFIGS[key].label,
                                     key="selected_model")
    config = MODEL_CONFIGS[model_key]
    if model_key == "visit":
        visit.render_placeholder(config)
        return

    st.sidebar.subheader("Filters")
    cycles = get_cycle_options(config.workbook_path)
    selected_cycle = None
    if cycles:
        selected_cycle = st.sidebar.selectbox(
            "Cycle date", cycles, format_func=lambda value: value.strftime("%b %d, %Y"),
            key=f"cycle_{model_key}",
        )
    model_renderers[renderer](config, selected_cycle)
