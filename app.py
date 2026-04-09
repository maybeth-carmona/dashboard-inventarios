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
st.caption("Atraso y pendiente operativo según estatus SAP")

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

# ======================================================
# LECTURA
# ======================================================
df_raw = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN SAP
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
    'Cantidad Entregada': 'cantidad_entregada',
    'Cantidad (Ejercido)': 'cantidad_pedida'
})

# ======================================================
# FECHAS
# ======================================================
df_raw['fecha_pedido'] = pd.to_datetime(df_raw['fecha_pedido'], errors='coerce')
df_raw = df_raw[df_raw['fecha_pedido'].notna()].copy()

# ======================================================
# ELIMINAR CONVENIOS
# ======================================================
df_raw['pedido'] = df_raw['pedido'].astype(str)
df_raw = df_raw[~df_raw['pedido'].str.startswith(('256', '266'))]

# ======================================================
# LIMPIEZA DE CANTIDADES
# ======================================================
df_raw['cantidad_pedida'] = pd.to_numeric(df_raw['cantidad_pedida'], errors='coerce').fillna(0)
df_raw['cantidad_entregada'] = pd.to_numeric(df_raw['cantidad_entregada'], errors='coerce').fillna(0)

# ======================================================
# MR CORRECTO
# ======================================================
df_raw['entregado'] = df_raw['cantidad_entregada'] > 0

# ======================================================
# ✅ CANTIDAD PENDIENTE OPERATIVA (SAP REAL)
# ======================================================
df_raw['cantidad_pendiente'] = (
    df_raw['cantidad_pedida'] - df_raw['cantidad_entregada']
).clip(lower=0)

# NOTA IMPORTANTE:
# Si SAP ajusta cantidad_pedida = entregada,
# no existe forma técnica de recuperar pendiente real
# sin la columna "Cantidad Pedido Original"

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
def estatus_atraso(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    d = row['dias_atraso']
    if d > 60:
        return f"🔴 {d}"
    elif d > 30:
        return f"🟡 {d}"
    else:
        return f"🟢 {d}"

df_raw['estatus_atraso'] = df_raw.apply(estatus_atraso, axis=1)

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

grupo_sel = st.sidebar.multiselect("Grupo de artículos", sorted(df_raw['grupo_articulos'].unique()))
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
df_no_entregados = df[df['cantidad_pendiente'] > 0]

col1, col2 = st.columns(2)
col1.metric("Pedidos en seguimiento", len(df_no_entregados))
col2.metric("Pedidos críticos (>60 días)", len(df_no_entregados[df_no_entregados['dias_atraso'] > 60]))

# ======================================================
# ✅ GRÁFICA TOP 10 PROVEEDORES (DE REGRESO)
# ======================================================
st.subheader("📈 Top 10 proveedores con mayor atraso (activo)")

top10 = (
    df_no_entregados.groupby(['nombre_proveedor'], as_index=False)
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
        labels={'dias_promedio': 'Días de atraso'},
        title="Top 10 Proveedores – Atraso promedio"
    )
    st.plotly_chart(fig, use_container_width=True)

# ======================================================
# TABLAS
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

st.subheader("📋 Centros 1000 / 8000")
st.dataframe(
    df[df['centro'].isin(['1000', '8000'])]
      .sort_values(['orden_prioridad', 'dias_atraso'], ascending=[True, False])
      [columnas_tabla],
    use_container_width=True
)

st.subheader("📋 Centros 2000 / 7000")
st.dataframe(
    df[df['centro'].isin(['2000', '7000'])]
      .sort_values(['orden_prioridad', 'dias_atraso'], ascending=[True, False])
      [columnas_tabla],
    use_container_width=True
)
