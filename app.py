import streamlit as st

from dashboard.application import main


st.set_page_config(
    page_title="SMART",
    page_icon=":bar_chart:",
    layout="wide",
)

if __name__ == "__main__":
    main()
