import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from ui import run_page

st.set_page_config(page_title="TCE Calculator", layout="wide")
run_page("tce")
