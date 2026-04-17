import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Prueba Dashboard")

file = st.file_uploader("Sube un Excel", type=["xlsx"])
if file is None:
    st.stop()

df = pd.read_excel(file)
st.dataframe(df.head())
``
