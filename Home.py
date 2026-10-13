"""Entry point (router). The TCE calculator is the landing page."""
import streamlit as st

st.set_page_config(page_title="TCE Calculator", layout="wide")

pg = st.navigation([
    st.Page("pages/1_TCE_Calculator.py", title="TCE Calculator", default=True),
    st.Page("pages/2_Lumpsum.py", title="Lumpsum", url_path="Lumpsum"),
], position="top")
pg.run()
