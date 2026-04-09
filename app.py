import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Dashboard Riesgo de Inventarios",
    layout="wide"
)

st.title("📊 Dashboard de Riesgo de Inventarios")
st.caption("Días EXACTOS de demora por proveedor (cálculo automático diario)")

# ======================================================
# CARGA DE ARCHIVOS
# ======================================================
st.sidebar.header("📂 Carga de archivos SAP")

file_solped = st.sidebar.file_uploader(
    "Sube raw_estatus_sol_pedidos.xlsx",
    type=["xlsx"]
)

file_pedidos = st.sidebar.file_uploader(
    "Sube raw_estatus_pedidos_compras.xlsx",
    type=["xlsx"]
)

if not file_solped or not file_pedidos:
