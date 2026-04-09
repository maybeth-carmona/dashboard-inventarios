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
st.caption("Días EXACTOS de demora – semáforo visual por proveedor")

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
    st.warning("⬅️ Sube ambos archivos para iniciar el análisis")
    st.stop()

# ======================================================
# LECTURA
# ======================================================
solped = pd.read_excel(file_solped)
pedidos = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN SAP (LIMPIA)
# ======================================================
pedidos = pedidos.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor': 'num_proveedor',
    'Proveedor TEXT': 'nombre_proveedor',
    'Fecha de Entrega': 'fecha_mr',              # fecha MR (si existe)
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'cantidad_entregada',
    'Cantidad (Ejercido)': 'cantidad_pedida'
})

# ======================================================
# CONVERSIÓN DE FECHAS
# ======================================================
for c in ['fecha_mr', 'fecha_pedido']:
    if c in pedidos.columns:
        pedidos[c] = pd.to_datetime(pedidos[c], errors='coerce')

# ======================================================
# LIMPIEZA Y CANTIDAD PENDIENTE
# ======================================================
pedidos['cantidad_entregada'] = pedidos['cantidad_entregada'].fillna(0)
pedidos['cantidad_pendiente'] = pedidos['cantidad_pedida'] - pedidos['cantidad_entregada']
base = pedidos[pedidos['cantidad_pendiente'] > 0].copy()

# ======================================================
# CÁLCULO DE DÍAS DE ATRASO (REGLA DE NEGOCIO)
# ======================================================
fecha_hoy = pd.to_datetime(datetime.today().date())

def calcular_dias_atraso(row):
    if pd.notna(row['fecha_mr']):
        return (row['fecha_mr'] - row['fecha_pedido']).days
    else:
        return (fecha_hoy - row['fecha_pedido']).days

base['dias_atraso'] = base.apply(calcular_dias_atraso, axis=1)
base['dias_atraso'] = base['dias_atraso'].clip(lower=0)

# ======================================================
# FILTROS
# ======================================================
st.sidebar.header("🎛️ Filtros")

grupo_sel = st.sidebar.multiselect(
    "Grupo de artículos",
    options=base['grupo_articulos'].dropna().unique()
)

df = base.copy()

if grupo_sel:
    df = df[df['grupo_articulos'].isin(grupo_sel)]

# ======================================================
# KPIs
# ======================================================
col1, col2 = st.columns(2)

col1.metric("Total pedidos con atraso", len(df))
col2.metric("Pedidos > 60 días", len(df[df['dias_atraso'] > 60]))

# ======================================================
# TOP 10 PROVEEDORES (FUNCIONAL)
# ======================================================
st.subheader("📈 Top 10 proveedores con mayor atraso")

top10 = (
    df.groupby(['num_proveedor', 'nombre_proveedor'], as_index=False)
    .agg(
        dias_promedio=('dias_atraso', 'mean'),
        pedidos=('pedido', 'nunique')
    )
    .sort_values(['dias_promedio', 'pedidos'], ascending=[False, False])
    .head(10)
)

if not top10.empty:
    fig = px.bar(
        top10,
        x='nombre_proveedor',
        y='dias_promedio',
        text='pedidos',
        title="Top 10 proveedores – Días EXACTOS de atraso promedio",
        labels={
            'nombre_proveedor': 'Proveedor',
            'dias_promedio': 'Días de atraso',
