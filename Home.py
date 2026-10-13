import streamlit as st

st.set_page_config(page_title="Voyage Dashboard", layout="wide")
st.title("Voyage Dashboard")
st.write("Calculateurs de voyage tanker : TCE (Worldscale) et Lumpsum, avec bunkers ECA, EU ETS, "
         "break-even, sensibilité et export Excel.")
st.page_link("pages/1_TCE_Calculator.py", label="TCE Calculator")
st.page_link("pages/2_Lumpsum.py", label="Lumpsum Calculator")
st.caption("Hypothèses, ports, distances et flat rates : voir config.py (valeurs illustratives à remplacer).")
