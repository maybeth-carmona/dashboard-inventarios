import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Dashboard Operativo Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

hoy = pd.to_datetime(datetime.today().date())

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
ped['fecha_entrega'] = pd.to_datetime(ped.get('fecha_entrega'), errors='coerce')

# seleccionar cantidad solicitada
col_cant = st.sidebar.selectbox(
    "Columna de cantidad solicitada (Pedidos)",
    ped.columns
)

ped['cantidad_pedida'] = pd.to_numeric(ped[col_cant], errors='coerce').fillna(0)
ped['cantidad_entregada'] = pd.to_numeric(ped['cantidad_entregada'], errors='coerce').fillna(0)

# MR correcto
ped['entregado'] = ped['cantidad_entregada'] > 0

# ✅ cantidad pendiente real
ped['cantidad_pendiente'] = (ped['cantidad_pedida'] - ped['cantidad_entregada']).clip(lower=0)

# días de atraso (enteros)
ped['dias_atraso'] = np.where(
    ped['entregado'],
    0,
    (hoy - ped['fecha_pedido']).dt.days
).astype("Int64")

def semaforo_prov(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    d = row['dias_atraso']
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

ped['estatus'] = ped.apply(semaforo_prov, axis=1)

df_pend = ped[ped['cantidad_pendiente'] > 0]

st.metric("Pedidos con pendiente", len(df_pend))

top_prov = (
    df_pend.groupby('proveedor', as_index=False)
    .agg(dias_promedio=('dias_atraso', 'mean'))
    .sort_values('dias_promedio', ascending=False)
    .head(10)
)

fig1 = px.bar(
    top_prov,
    x='proveedor',
    y='dias_promedio',
    title="Top 10 proveedores con mayor atraso"
)
st.plotly_chart(fig1, use_container_width=True)

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

sol['pedido'] = sol['fecha_pedido'].apply(
    lambda x: "SIN TRATAMIENTO" if pd.isna(x) else "ASIGNADO"
)

# días de demora en atención (solo sin pedido)
sol['dias_demora_sin_pedido'] = np.where(
    sol['pedido'] == "SIN TRATAMIENTO",
    (hoy - sol['fecha_lib']).dt.days,
    np.nan
)

# días reales de atención (cuando sí hay pedido)
sol['dias_atencion_real'] = np.where(
    sol['pedido'] != "SIN TRATAMIENTO",
    (sol['fecha_pedido'] - sol['fecha_lib']).dt.days,
    np.nan
)

def semaforo_comp(d):
    if pd.isna(d):
        return ""
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

sol['semaforo_demora'] = sol['dias_demora_sin_pedido'].apply(semaforo_comp)

st.subheader("Detalle de seguimiento a Solpeds")

cols_comp = [
    'solped','pedido','grupo_compras','centro',
    'fecha_lib','fecha_pedido',
    'semaforo_demora','dias_atencion_real'
]

st.dataframe(sol[cols_comp], use_container_width=True)

# =====================================================
# 📊 GRÁFICA GRUPO DE COMPRAS
# =====================================================
st.subheader("📈 Tiempo promedio de creación de pedidos por grupo de compras")

grp = (
    sol.dropna(subset=['dias_atencion_real'])
       .groupby('grupo_compras', as_index=False)
       .agg(dias_promedio=('dias_atencion_real','mean'))
       .sort_values('dias_promedio')
)

fig2 = px.bar(
    grp,
    x='grupo_compras',
    y='dias_promedio',
    title="Desempeño histórico de grupos de compras",
    labels={'dias_promedio':'Días promedio'}
)

st.plotly_chart(fig2, use_container_width=True)
``
