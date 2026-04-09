import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Dashboard Riesgo de Inventarios",
    layout="wide"
)

st.title("📊 Dashboard de Riesgo de Inventarios")
st.caption("Días EXACTOS de demora – semáforo integrado por pedido")

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
# LECTURA DE ARCHIVOS
# ======================================================
solped = pd.read_excel(file_solped)
pedidos = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN SAP (SOLO LO NECESARIO)
# ======================================================
pedidos = pedidos.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor': 'num_proveedor',
    'Proveedor TEXT': 'nombre_proveedor',
    'Fecha de Entrega': 'fecha_mr',          # MR (si existe)
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'cantidad_entregada',
    'Cantidad (Ejercido)': 'cantidad_pedida'
})

# ======================================================
# CONVERSIÓN DE FECHAS
# ======================================================
for c in ['fecha_mr', 'fecha_pedido']:
    pedidos[c] = pd.to_datetime(pedidos[c], errors='coerce')

# ======================================================
# ELIMINAR CONVENIOS (256XXXX / 266XXXX)
# ======================================================
pedidos['pedido'] = pedidos['pedido'].astype(str)
pedidos = pedidos[
    ~pedidos['pedido'].str.startswith(('256', '266'))
]

# ======================================================
# CANTIDAD PENDIENTE
# ======================================================
pedidos['cantidad_entregada'] = pedidos['cantidad_entregada'].fillna(0)
pedidos['cantidad_pendiente'] = pedidos['cantidad_pedida'] - pedidos['cantidad_entregada']
base = pedidos[pedidos['cantidad_pendiente'] > 0].copy()

# ======================================================
# CÁLCULO DE DÍAS DE ATRASO (VECTORIAL, CORRECTO)
# Regla:
# - Si hay MR → MR - fecha pedido
# - Si no hay MR → hoy - fecha pedido
# ======================================================
fecha_hoy = pd.to_datetime(datetime.today().date())

base['dias_atraso'] = np.where(
    base['fecha_mr'].notna(),
    (base['fecha_mr'] - base['fecha_pedido']).dt.days,
    (fecha_hoy - base['fecha_pedido']).dt.days
)

base['dias_atraso'] = base['dias_atraso'].clip(lower=0).astype(int)

# ======================================================
# SEMÁFORO + DÍAS EN LA MISMA CELDA
# ======================================================
def dias_con_semaforo(d):
    if d > 60:
        return f"🔴 {d}"
    elif d > 30:
        return f"🟡 {d}"
    else:
        return f"🟢 {d}"

base['dias_atraso_visual'] = base['dias_atraso'].apply(dias_con_semaforo)

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
# TOP 10 PROVEEDORES
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
        title="Top 10 Proveedores – Días EXACTOS de atraso promedio",
        labels={
            'nombre_proveedor': 'Proveedor',
            'dias_promedio': 'Días de atraso',
            'pedidos': 'Cantidad de pedidos'
        }
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay datos suficientes para generar el Top 10.")

# ======================================================
# TABLAS FINALES (ORDEN CORRECTO ✅)
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
    'dias_atraso_visual'
]

st.subheader("📋 Centros 1000 / 8000")
st.dataframe(
    df[df['centro'].isin([1000, 8000])]
      .sort_values('dias_atraso', ascending=False)
      [columnas_tabla],
    use_container_width=True
)

st.subheader("📋 Centros 2000 / 7000")
st.dataframe(
    df[df['centro'].isin([2000, 7000])]
      .sort_values('dias_atraso', ascending=False)
      [columnas_tabla],
    use_container_width=True
)
