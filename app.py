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
st.caption("Pedidos y órdenes de entrega – atraso y pendiente REAL")

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
pedidos = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN SAP
# ======================================================
pedidos = pedidos.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor': 'num_proveedor',
    'Proveedor TEXT': 'nombre_proveedor',
    'Fecha de Entrega': 'fecha_mr',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'cantidad_entregada',
    'Cantidad (Ejercido)': 'cantidad_pedida'
})

# ======================================================
# FECHAS
# ======================================================
for c in ['fecha_mr', 'fecha_pedido']:
    pedidos[c] = pd.to_datetime(pedidos[c], errors='coerce')

# ======================================================
# ELIMINAR SIN FECHA DE PEDIDO
# ======================================================
pedidos = pedidos[pedidos['fecha_pedido'].notna()].copy()

# ======================================================
# ELIMINAR CONVENIOS
# ======================================================
pedidos['pedido'] = pedidos['pedido'].astype(str)
pedidos = pedidos[~pedidos['pedido'].str.startswith(('256', '266'))]

# ======================================================
# LIMPIEZA DE CANTIDAD PEDIDA
# ======================================================
pedidos['cantidad_pedida'] = pd.to_numeric(
    pedidos['cantidad_pedida'], errors='coerce'
).fillna(0)

base = pedidos.copy()

# ======================================================
# ENTREGADO / NO ENTREGADO
# ======================================================
base['entregado'] = base['fecha_mr'].notna()

# ======================================================
# CANTIDAD PENDIENTE REAL ✅
# ======================================================
base['cantidad_pendiente'] = np.where(
    base['entregado'],
    0,
    base['cantidad_pedida']
)

# ======================================================
# DÍAS DE ATRASO
# ======================================================
fecha_hoy = pd.to_datetime(datetime.today().date())

base['dias_atraso'] = np.where(
    base['entregado'],
    (base['fecha_mr'] - base['fecha_pedido']).dt.days,
    (fecha_hoy - base['fecha_pedido']).dt.days
)

base['dias_atraso'] = base['dias_atraso'].clip(lower=0).astype("Int64")

# ======================================================
# SEMÁFORO + DÍAS
# ======================================================
def estatus_atraso(row):
    if row['entregado']:
        return "✅ Entregado"
    d = row['dias_atraso']
    if d > 60:
        return f"🔴 {d}"
    elif d > 30:
        return f"🟡 {d}"
    else:
        return f"🟢 {d}"

base['estatus_atraso'] = base.apply(estatus_atraso, axis=1)

# ======================================================
# PRIORIDAD
# ======================================================
def prioridad(row):
    if row['entregado']:
        return 4
    if row['dias_atraso'] > 60:
        return 1
    if row['dias_atraso'] > 30:
        return 2
    return 3

base['orden_prioridad'] = base.apply(prioridad, axis=1)

# ======================================================
# PREPARAR FILTROS
# ======================================================
base['grupo_articulos'] = base['grupo_articulos'].astype(str)
base['centro'] = base['centro'].astype(str)
base['nombre_proveedor'] = base['nombre_proveedor'].astype(str)

st.sidebar.header("🎛️ Filtros")

grupo_sel = st.sidebar.multiselect(
    "Grupo de artículos",
    options=sorted(base['grupo_articulos'].unique())
)

centro_sel = st.sidebar.multiselect(
    "Centro",
    options=sorted(base['centro'].unique())
)

proveedor_sel = st.sidebar.multiselect(
    "Proveedor",
    options=sorted(base['nombre_proveedor'].unique())
)

df = base.copy()
if grupo_sel:
    df = df[df['grupo_articulos'].isin(grupo_sel)]
if centro_sel:
    df = df[df['centro'].isin(centro_sel)]
if proveedor_sel:
    df = df[df['nombre_proveedor'].isin(proveedor_sel)]

# ======================================================
# KPIs
# ======================================================
df_no_entregados = df[~df['entregado']]

col1, col2 = st.columns(2)
col1.metric("Pedidos en seguimiento", len(df_no_entregados))
col2.metric("Pedidos críticos (>60 días)", len(df_no_entregados[df_no_entregados['dias_atraso'] > 60]))

# ======================================================
# TOP 10 PROVEEDORES
# ======================================================
st.subheader("📈 Top 10 proveedores con mayor atraso (activo)")

top10 = (
    df_no_entregados.groupby(['num_proveedor', 'nombre_proveedor'], as_index=False)
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
        title="Top 10 Proveedores – Atraso promedio",
        labels={'dias_promedio': 'Días de atraso'}
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
