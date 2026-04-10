import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
st.set_page_config(
    page_title="Dashboard Operativo de Compras",
    layout="wide"
)

st.title("📊 Dashboard Operativo de Compras")
st.caption("Seguimiento a proveedores y compradores")

hoy = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA DE ARCHIVOS
# =====================================================
st.sidebar.header("📂 Carga de archivos SAP")

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

# =====================================================
# ================= PROVEEDORES ========================
# =====================================================
st.header("🚚 Seguimiento a Proveedores")

ped = ped.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor TEXT': 'proveedor',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Fecha de Entrega': 'fecha_entrega',
    'Cantidad Entregada': 'cantidad_entregada'
})

ped['fecha_pedido'] = pd.to_datetime(ped['fecha_pedido'], errors='coerce')
ped['fecha_entrega'] = pd.to_datetime(ped['fecha_entrega'], errors='coerce')
ped = ped[ped['fecha_pedido'].notna()].copy()

# Selección de cantidad solicitada
st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Selecciona la columna",
    ped.columns.tolist()
)

ped['cantidad_pedida'] = pd.to_numeric(ped[col_cant], errors='coerce').fillna(0)
ped['cantidad_entregada'] = pd.to_numeric(ped['cantidad_entregada'], errors='coerce').fillna(0)

# MR correcto
ped['entregado'] = ped['cantidad_entregada'] > 0

# Cantidad pendiente real
ped['cantidad_pendiente'] = (
    ped['cantidad_pedida'] - ped['cantidad_entregada']
).clip(lower=0)

# Días de atraso
ped['dias_atraso'] = np.where(
    ped['entregado'],
    0,
    (hoy - ped['fecha_pedido']).dt.days
).clip(lower=0).astype("Int64")

def semaforo_proveedor(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    d = int(row['dias_atraso'])
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped['estatus'] = ped.apply(semaforo_proveedor, axis=1)

# KPI correcto (solo con pendiente)
df_pendientes = ped[ped['cantidad_pendiente'] > 0]
st.metric("Pedidos con pendiente (sin MR)", len(df_pendientes))

# Gráfico Top 10 proveedores
top_prov = (
    df_pendientes
    .groupby('proveedor', as_index=False)
    .agg(dias_promedio=('dias_atraso', 'mean'))
    .sort_values('dias_promedio', ascending=False)
    .head(10)
)

fig1 = px.bar(
    top_prov,
    x='proveedor',
    y='dias_promedio',
    title="Top 10 proveedores con mayor atraso",
    labels={'dias_promedio': 'Días de atraso'}
)
st.plotly_chart(fig1, use_container_width=True)

# Tabla proveedores (orden p0)
st.subheader("Detalle de pedidos a proveedores")

cols_prov = [
    'pedido','proveedor','material_sap','descripcion_material',
    'grupo_articulos','centro',
    'fecha_pedido','fecha_entrega',
    'cantidad_pendiente','estatus'
]

df_prov_ord = ped.sort_values(
    by=['entregado','dias_atraso'],
    ascending=[True, False]
)

st.dataframe(df_prov_ord[cols_prov], use_container_width=True)

# =====================================================
# ================= COMPRADORES ========================
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    'Número de Solped': 'solped',
    'Grupo de compras': 'grupo_compras',
    'Centro': 'centro',
    'Fecha Liberación Solped': 'fecha_lib',
    'Fecha Creación Pedido': 'fecha_pedido'
})

sol['fecha_lib'] = pd.to_datetime(sol['fecha_lib'], errors='coerce')
sol['fecha_pedido'] = pd.to_datetime(sol['fecha_pedido'], errors='coerce')

sol['pedido_status'] = np.where(
    sol['fecha_pedido'].isna(),
    "SIN TRATAMIENTO",
    "ASIGNADO"
)

# Días de demora sin pedido
sol['dias_demora'] = np.where(
    sol['pedido_status'] == "SIN TRATAMIENTO",
    (hoy - sol['fecha_lib']).dt.days,
    np.nan
)

# Días reales de atención
sol['dias_atencion'] = np.where(
    sol['pedido_status'] == "ASIGNADO",
    (sol['fecha_pedido'] - sol['fecha_lib']).dt.days,
    np.nan
)

def semaforo_comprador(d):
    if pd.isna(d):
        return ""
    d = int(d)
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol['estatus_demora'] = sol['dias_demora'].apply(semaforo_comprador)

st.subheader("Detalle de seguimiento a Solped")

cols_comp = [
    'solped','pedido_status','grupo_compras','centro',
    'fecha_lib','fecha_pedido',
    'estatus_demora','dias_atencion'
]

st.dataframe(sol[cols_comp], use_container_width=True)

# Gráfico grupos de compras
st.subheader("📈 Desempeño por grupo de compras")

grp = (
    sol.dropna(subset=['dias_atencion'])
    .groupby('grupo_compras', as_index=False)
    .agg(dias_promedio=('dias_atencion','mean'))
    .sort_values('dias_promedio')
)

fig2 = px.bar(
    grp,
    x='grupo_compras',
    y='dias_promedio',
    title="Promedio de días para crear pedidos por grupo de compras",
    labels={'dias_promedio': 'Días promedio'}
)
st.plotly_chart(fig2, use_container_width=True)
