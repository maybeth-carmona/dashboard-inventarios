# --- LIBRERÍAS
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Dashboard Operativo Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

# =====================================================
# 📂 CARGA DE ARCHIVOS
# =====================================================
st.sidebar.header("Carga de archivos SAP")

file_pedidos = st.sidebar.file_uploader(
    "Pedidos de Compras",
    type=["xlsx"]
)

file_solped = st.sidebar.file_uploader(
    "Solicitudes de Pedido (Solped)",
    type=["xlsx"]
)

if not file_pedidos or not file_solped:
    st.warning("Sube ambos archivos para continuar")
    st.stop()

ped = pd.read_excel(file_pedidos)
sol = pd.read_excel(file_solped)

hoy = pd.to_datetime(datetime.today().date())

# =====================================================
# ================= PROVEEDORES ========================
# =====================================================
st.header("🚚 Seguimiento a Proveedores")

ped = ped.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material',
    'Texto Breve Posicion': 'descripcion',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor TEXT': 'proveedor',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'entregada'
})

ped['fecha_pedido'] = pd.to_datetime(ped['fecha_pedido'], errors='coerce')
ped['entregada'] = pd.to_numeric(ped['entregada'], errors='coerce').fillna(0)

# selector cantidad solicitada
col_cant = st.sidebar.selectbox(
    "Columna cantidad solicitada",
    ped.columns
)
ped['cantidad_pedida'] = pd.to_numeric(ped[col_cant], errors='coerce').fillna(0)

ped['cantidad_pendiente'] = (ped['cantidad_pedida'] - ped['entregada']).clip(lower=0)
ped['entregado'] = ped['entregada'] > 0

ped['dias_atraso'] = np.where(
    ped['entregado'],
    0,
    (hoy - ped['fecha_pedido']).dt.days
)

ped['dias_atraso'] = ped['dias_atraso'].clip(lower=0)

def sem(row):
    if row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    if row['dias_atraso'] > 60:
        return f"🔴 {row['dias_atraso']}"
    if row['dias_atraso'] > 30:
        return f"🟡 {row['dias_atraso']}"
    return f"🟢 {row['dias_atraso']}"

ped['estatus'] = ped.apply(sem, axis=1)

df_pend = ped[ped['cantidad_pendiente'] > 0]

st.metric("Pedidos con pendiente", len(df_pend))

top = (
    df_pend.groupby('proveedor', as_index=False)
    .agg(dias_promedio=('dias_atraso','mean'))
    .sort_values('dias_promedio', ascending=False)
    .head(10)
)

fig = px.bar(top, x='proveedor', y='dias_promedio',
             title="Top 10 proveedores con mayor atraso")
st.plotly_chart(fig, use_container_width=True)

columnas = [
    'pedido','proveedor','material','descripcion',
    'grupo_articulos','centro',
    'fecha_pedido','cantidad_pendiente','estatus'
]

vis = st.multiselect("Columnas visibles", columnas, columnas)

st.dataframe(
    ped.sort_values(['entregado','dias_atraso'], ascending=[True,False])[vis],
    use_container_width=True
)

# =====================================================
# ================ COMPRADORES =========================
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    'Número de Solped': 'solped',
    'Grupo de compras': 'grupo_compras',
    'Centro': 'centro',
    'Fecha Liberación Solped': 'fecha_lib'
})

sol['fecha_lib'] = pd.to_datetime(sol['fecha_lib'], errors='coerce')

# relación solped-pedido
rel = sol.merge(
    ped[['pedido']],
    left_index=True,
    right_index=True,
    how='left'
)

rel['pedido'] = rel['pedido'].fillna("SIN TRATAMIENTO")

rel['dias_creacion'] = np.where(
    rel['pedido'] != "SIN TRATAMIENTO",
    (hoy - rel['fecha_lib']).dt.days,
    (hoy - rel['fecha_lib']).dt.days
)

st.dataframe(rel, use_container_width=True)

grp = (
    rel.groupby('grupo_compras', as_index=False)
    .agg(dias_promedio=('dias_creacion','mean'))
    .sort_values('dias_promedio')
)

fig2 = px.bar(
    grp, x='grupo_compras', y='dias_promedio',
    title="Tiempo promedio para creación de pedidos (por grupo)"
)
st.plotly_chart(fig2, use_container_width=True)
