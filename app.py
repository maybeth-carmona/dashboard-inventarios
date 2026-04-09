import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(page_title="Dashboard Riesgo de Inventarios", layout="wide")
st.title("📊 Dashboard de Riesgo de Inventarios")
st.caption("Pendiente REAL = Cantidad solicitada − Cantidad entregada")

# ======================================================
# CARGA DE ARCHIVO
# ======================================================
st.sidebar.header("📂 Carga de archivos SAP")

file_pedidos = st.sidebar.file_uploader(
    "Sube raw_estatus_pedidos_compras.xlsx",
    type=["xlsx"]
)

if not file_pedidos:
    st.warning("⬅️ Sube el archivo para iniciar el análisis")
    st.stop()

df_raw = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN DE COLUMNAS CLAVE
# ======================================================
df_raw = df_raw.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor': 'num_proveedor',
    'Proveedor TEXT': 'nombre_proveedor',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'cantidad_entregada'
})

# ======================================================
# SELECCIÓN MANUAL DE CANTIDAD SOLICITADA ✅
# ======================================================
st.sidebar.subheader("📦 Cantidad solicitada")

columnas_numericas = df_raw.columns.tolist()

col_cantidad_pedida = st.sidebar.selectbox(
    "Selecciona la columna de CANTIDAD SOLICITADA",
    options=columnas_numericas
)

# Convertimos esa columna a numérica
df_raw['cantidad_pedida_real'] = pd.to_numeric(
    df_raw[col_cantidad_pedida], errors='coerce'
).fillna(0)

df_raw['cantidad_entregada'] = pd.to_numeric(
    df_raw['cantidad_entregada'], errors='coerce'
).fillna(0)

# ======================================================
# FECHA DE PEDIDO (BASE DE ATRASO)
# ======================================================
df_raw['fecha_pedido'] = pd.to_datetime(df_raw['fecha_pedido'], errors='coerce')
df_raw = df_raw[df_raw['fecha_pedido'].notna()].copy()

# ======================================================
# ELIMINAR CONVENIOS
# ======================================================
df_raw['pedido'] = df_raw['pedido'].astype(str)
df_raw = df_raw[~df_raw['pedido'].str.startswith(('256', '266'))]

# ======================================================
# MR CORRECTO (SI ENTREGÓ ALGO)
# ======================================================
df_raw['entregado'] = df_raw['cantidad_entregada'] > 0

# ======================================================
# ✅ CANTIDAD PENDIENTE REAL
# ======================================================
df_raw['cantidad_pendiente'] = (
    df_raw['cantidad_pedida_real'] - df_raw['cantidad_entregada']
).clip(lower=0)

# ======================================================
# DÍAS DE ATRASO
# ======================================================
fecha_hoy = pd.to_datetime(datetime.today().date())

df_raw['dias_atraso'] = np.where(
    df_raw['entregado'],
    0,
    (fecha_hoy - df_raw['fecha_pedido']).dt.days
)

df_raw['dias_atraso'] = df_raw['dias_atraso'].clip(lower=0).astype("Int64")

# ======================================================
# SEMÁFORO + TEXTO
# ======================================================
def estatus(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    d = row['dias_atraso']
    if d > 60:
        return f"🔴 {d}"
    elif d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

df_raw['estatus_atraso'] = df_raw.apply(estatus, axis=1)

# ======================================================
# PRIORIDAD
# ======================================================
def prioridad(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return 4
    if row['dias_atraso'] > 60:
        return 1
    if row['dias_atraso'] > 30:
        return 2
    return 3

df_raw['orden_prioridad'] = df_raw.apply(prioridad, axis=1)

# ======================================================
# FILTROS
# ======================================================
df_raw['grupo_articulos'] = df_raw['grupo_articulos'].astype(str)
df_raw['centro'] = df_raw['centro'].astype(str)
df_raw['nombre_proveedor'] = df_raw['nombre_proveedor'].astype(str)

st.sidebar.header("🎛️ Filtros")

grupo_sel = st.sidebar.multiselect("Grupo artículos", sorted(df_raw['grupo_articulos'].unique()))
centro_sel = st.sidebar.multiselect("Centro", sorted(df_raw['centro'].unique()))
proveedor_sel = st.sidebar.multiselect("Proveedor", sorted(df_raw['nombre_proveedor'].unique()))

df = df_raw.copy()
if grupo_sel:
    df = df[df['grupo_articulos'].isin(grupo_sel)]
if centro_sel:
    df = df[df['centro'].isin(centro_sel)]
if proveedor_sel:
    df = df[df['nombre_proveedor'].isin(proveedor_sel)]

# ======================================================
# KPIs
# ======================================================
df_pendientes = df[df['cantidad_pendiente'] > 0]

col1, col2 = st.columns(2)
col1.metric("Pedidos con pendiente", len(df_pendientes))
col2.metric("Pedidos críticos (>60 días)", len(df_pendientes[df_pendientes['dias_atraso'] > 60]))

# ======================================================
# GRÁFICA TOP 10 PROVEEDORES ✅
# ======================================================
st.subheader("📈 Top 10 proveedores con mayor atraso")

top10 = (
    df_pendientes.groupby('nombre_proveedor', as_index=False)
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
        labels={'dias_promedio': 'Días atraso'},
        title="Top 10 Proveedores con atraso y pendiente"
    )
    st.plotly_chart(fig, use_container_width=True)

# ======================================================
# TABLA FINAL
# ======================================================
columnas_tabla = [
    'pedido',
    'num_proveedor',
    'nombre_proveedor',
    'material_sap',
    'descripcion_material',
    'grupo_articulos',
    'centro',
    'cantidad_pendiente',
    'estatus_atraso'
]

st.subheader("📋 Detalle de pedidos")
st.dataframe(
    df.sort_values('orden_prioridad')[columnas_tabla],
    use_container_width=True
)
