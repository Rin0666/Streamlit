import streamlit as st

from dashboard.navigation import Category


def open_page(page: str) -> None:
    if page == "Home":
        st.session_state.pop("selected_category", None)
    st.session_state["_requested_page"] = page


def open_category(title: str | None) -> None:
    st.session_state["selected_category"] = title


def render_home_page(categories: tuple[Category, ...]) -> None:
    selected = next((category for category in categories
                     if category.title == st.session_state.get("selected_category")), None)
    if selected:
        st.button("All categories", icon=":material/arrow_back:",
                  on_click=open_category, args=(None,))
        st.title(selected.title)
        st.caption(selected.description or "Choose a page to get started.")
        items = selected.pages
    else:
        st.session_state.pop("selected_category", None)
        st.title("SMART")
        st.caption("Choose a category to get started.")
        items = categories
        if not items:
            st.info("No pages are assigned to your account. Contact your administrator.")
    for offset in range(0, len(items), 3):
        columns = st.columns(3)
        for column, item in zip(columns, items[offset:offset + 3]):
            with column, st.container(border=True):
                st.subheader(item.title)
                st.write(item.description)
                if selected:
                    st.button("Open page", key=f"tile_{item.title}", icon=item.icon,
                              on_click=open_page, args=(item.title,), use_container_width=True)
                else:
                    count = len(item.pages)
                    st.caption(f"{count} {'page' if count == 1 else 'pages'} available")
                    st.button("Open category", key=f"category_{item.title}", icon=item.icon,
                              on_click=open_category, args=(item.title,), use_container_width=True)
