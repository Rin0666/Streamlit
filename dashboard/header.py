"""Authenticated account action beside Streamlit's menu."""
from streamlit.components.v2 import component

from dashboard.sessions import end_session


_header_actions = component("account_header", js="""
export default function({setTriggerValue}) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Sign out";
    button.setAttribute("aria-label", "Sign out");
    button.dataset.dashboardSignOut = "true";
    button.style.cssText = "width:auto;white-space:nowrap;padding:0.35rem 0.75rem;cursor:pointer;";
    button.onclick = () => {
        button.disabled = true;
        setTriggerValue("sign_out", true);
    };
    function placeButton() {
        const menu = document.querySelector('[data-testid="stMainMenu"]');
        if (!menu) return;
        const template = document.querySelector('[data-testid="stAppDeployButton"] button')
            || menu.querySelector("button");
        if (template) button.className = template.className;
        if (button.nextSibling !== menu) menu.parentNode.insertBefore(button, menu);
    }
    const observer = new MutationObserver(placeButton);
    observer.observe(document.body, {childList: true, subtree: true});
    placeButton();
    return () => { observer.disconnect(); button.remove(); };
}
""")


def render_account_header() -> None:
    _header_actions(key="account_header", height=1, on_sign_out_change=end_session)
