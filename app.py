import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

# ==============================================
# CONFIGURACIÓN GENERAL
# ==============================================
st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

hoy = pd.to_datetime(datetime.today().date())

# ==============================================
# CARGA DE ARCHIVOS
# ==============================================
st.sidebar.header("Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solpeds", type=["xlsx"])

if not file_ped or not file_sol:
    st.warning("Sube ambos archivos para continuar")
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# ==============================================
# ========= SEGUIMIENTO PROVEEDORES =============
# ==============================================
st.header("🚚 Seguimiento a Proveedores")

ped = ped.rename(columns={
    'Pedido de Compras': 'pedido',
    'Proveedor TEXT': 'proveedor',
    'Material': 'material',
    'Texto Breve Posicion': 'descripcion',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Fecha de Entrega': 'fecha_entrega',
    'Cantidad Entregada': 'cantidad_entregada'
})

ped['fecha_pedido'] = pd.to_datetime(ped['fecha_pedido'], errors='coerce')
ped['fecha_entrega'] = pd.to_datetime(ped['fecha_entrega'], errors='coerce')
ped = ped[ped['fecha_pedido'].notna()].copy()

ped['cantidad_entregada'] = pd.to_numeric(
    ped['cantidad_entregada'], errors='coerce'
).fillna(0)

# Selección de cantidad solicitada
st.sidebar.subheader("Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)

ped['cantidad_pedida'] = pd.to_numeric(
    ped[col_cant], errors='coerce'
).fillna(0)

# MR real
ped['entregado'] = ped['cantidad_entregada'] > 0

# Cantidad pendiente real
ped['cantidad_pendiente'] = (
    ped['cantidad_pedida'] - ped['cantidad_entregada']
).clip(lower=0)

# Días de demora vs fecha compromiso
ped['dias_demora'] = pd.Series(
    np.where(
        ped['fecha_entrega'].notna(),
        (hoy - ped['fecha_entrega']).dt.days,
        (hoy - ped['fecha_pedido']).dt.days
    ),
    index=ped.index
).clip(lower=0).astype("Int64")

def semaforo_prov(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    d = int(row['dias_demora'])
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped['estatus'] = ped.apply(semaforo_prov, axis=1)

# Filtros proveedores
st.subheader("Filtros Proveedores")

f_prov = st.multiselect(
    "Proveedor", sorted(ped['proveedor'].dropna().unique())
)
f_grupo = st.multiselect(
    "Grupo de artículos", sorted(ped['grupo_articulos'].dropna().unique())
)
f_centro = st.multiselect(
    "Centro", sorted(ped['centro'].dropna().unique())
)

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp['proveedor'].isin(f_prov)]
if f_grupo:
    dfp = dfp[dfp['grupo_articulos'].isin(f_grupo)]
if f_centro:
    dfp = dfp[dfp['centro'].isin(f_centro)]

st.metric(
    "Pedidos con pendiente (sin MR)",
    len(dfp[dfp['cantidad_pendiente'] > 0])
)

# Gráfica proveedores
top_prov = (
    dfp[dfp['cantidad_pendiente'] > 0]
    .groupby('proveedor', as_index=False)
    .agg(dias_promedio=('dias_demora', 'mean'))
    .sort_values('dias_promedio', ascending=False)
    .head(10)
)

fig1 = px.bar(
    top_prov,
    x='proveedor',
    y='dias_promedio',
    title="Top 10 proveedores con mayor demora",
    labels={'dias_promedio': 'Días de demora'}
)
st.plotly_chart(fig1, use_container_width=True)

st.subheader("Detalle de pedidos")

dfp_ord = dfp.sort_values(
    by=['entregado', 'dias_demora'],
    ascending=[True, False]
)

st.dataframe(
    dfp_ord[[
        'pedido','proveedor','material','descripcion',
        'grupo_articulos','centro',
        'fecha_pedido','fecha_entrega',
        'cantidad_pendiente','estatus'
    ]],
    use_container_width=True
)

# ==============================================
# ========= SEGUIMIENTO COMPRADORES =============
# ==============================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    'Número de Solped': 'solped',
    'Pedido de Compras': 'pedido',
    'Grupo de compras': 'grupo_compras',
    'Centro': 'centro',
    'Fecha Liberación Solped': 'fecha_lib',
    'Fecha Creación Pedido': 'fecha_pedido'
})

sol['fecha_lib'] = pd.to_datetime(sol['fecha_lib'], errors='coerce')
sol['fecha_pedido'] = pd.to_datetime(sol['fecha_pedido'], errors='coerce')

sol['pedido'] = sol['pedido'].fillna("SIN TRATAMIENTO")

# Días sin atender
sol['dias_sin_pedido'] = pd.Series(
    np.where(
        sol['pedido'] == "SIN TRATAMIENTO",
        (hoy - sol['fecha_lib']).dt.days,
        np.nan
    ),
    index=sol.index
)

# Días reales de atención
sol['dias_atencion'] = pd.Series(
    np.where(
        sol['pedido'] != "SIN TRATAMIENTO",
        (sol['fecha_pedido'] - sol['fecha_lib']).dt.days,
        np.nan
    ),
    index=sol.index
)

def semaforo_comp(d):
    if pd.isna(d):
        return ""
    d = int(d)
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol['estatus_demora'] = sol['dias_sin_pedido'].apply(semaforo_comp)

sol_ord = sol.sort_values(
    by=['pedido', 'dias_sin_pedido'],
    ascending=[True, False]
)

st.subheader("Detalle de Solpeds")

st.dataframe(
    sol_ord[[
        'solped','pedido','grupo_compras','centro',
        'fecha_lib','fecha_pedido',
        'estatus_demora','dias_atencion'
    ]],
    use_container_width=True
)

# Gráfica compradores
st.subheader("Desempeño por grupo de compras")

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
    title="Promedio de días para crear pedidos",
    labels={'dias_promedio':'Días promedio'}
)
st.plotly_chart(fig2, use_container_width=True)
``
