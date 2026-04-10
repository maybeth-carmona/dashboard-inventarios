import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# ==============================
# CARGA DE ARCHIVOS
# ==============================
st.sidebar.header("Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# ==============================
# SEGUIMIENTO PROVEEDORES
# ==============================
st.header("🚚 Seguimiento a Proveedores")

ped = ped.rename(columns={
    "Pedido de Compras": "pedido",
    "Proveedor TEXT": "proveedor",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha Creación Pedido": "fecha_pedido",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad Entregada": "cantidad_entregada"
})

ped["pedido"] = ped["pedido"].astype(str)

# ❌ Eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce")
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce")

ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# Cantidad solicitada
st.sidebar.subheader("Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox("Columna de cantidad pedida", ped.columns.tolist())

ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# MR real
ped["entregado"] = ped["cantidad_entregada"] > 0

# Cantidad pendiente
ped["pendiente"] = (
    ped["cantidad_pedida"] - ped["cantidad_entregada"]
).clip(lower=0)

# ✅ DÍAS DE DEMORA (FORMA SEGURA)
dias_calc = (HOY - ped["fecha_entrega"]).dt.days

ped["dias_demora"] = (
    dias_calc
    .fillna(0)
    .clip(lower=0)
    .astype("Int64")
)

def semaforo_proveedor(row):
    if row["entregado"] and row["pendiente"] == 0:
        return "✅ Entregado"
    d = int(row["dias_demora"])
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped.apply(semaforo_proveedor, axis=1)

# Filtros
st.subheader("Filtros Proveedores")

ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

f_prov = st.multiselect("Proveedor", sorted(ped["proveedor"].unique()))
f_grupo = st.multiselect("Grupo de artículos", sorted(ped["grupo"].unique()))
f_centro = st.multiselect("Centro", sorted(ped["centro"].unique()))

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp["proveedor"].isin(f_prov)]
if f_grupo:
    dfp = dfp[dfp["grupo"].isin(f_grupo)]
if f_centro:
    dfp = dfp[dfp["centro"].isin(f_centro)]

st.metric(
    "Pedidos con pendiente (SIN MR)",
    len(dfp[(dfp["pendiente"] > 0) & (~dfp["entregado"])])
)

# Gráfica proveedores
top_prov = (
    dfp[(dfp["pendiente"] > 0) & (~dfp["entregado"])]
    .groupby("proveedor", as_index=False)
    .agg(dias_promedio=("dias_demora", "mean"))
    .sort_values("dias_promedio", ascending=False)
)

st.plotly_chart(
    px.bar(
        top_prov,
        x="proveedor",
        y="dias_promedio",
        title="Top proveedores con mayor demora",
        labels={"dias_promedio": "Días de demora"}
    ),
    use_container_width=True
)

dfp = dfp.sort_values(
    by=["entregado", "dias_demora"],
    ascending=[True, False]
)

st.dataframe(
    dfp[
        [
            "pedido", "proveedor", "material", "descripcion",
            "grupo", "centro",
            "fecha_pedido", "fecha_entrega",
            "pendiente", "estatus"
        ]
    ],
    use_container_width=True
)

# ==============================
# SEGUIMIENTO COMPRADORES
# ==============================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Pedido de Compras": "pedido",
    "Grupo de compras": "grupo_compras",
    "Centro": "centro",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")
sol["pedido"] = sol["pedido"].fillna("SIN TRATAMIENTO")

# Días sin atender
sol["dias_demora"] = (
    (HOY - sol["fecha_lib"])
    .dt.days
    .where(sol["pedido"] == "SIN TRATAMIENTO")
    .astype("Int64")
)

# Días reales de atención
sol["dias_atencion"] = (
    (sol["fecha_pedido"] - sol["fecha_lib"])
    .dt.days
    .astype("Int64")
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

sol["estatus"] = sol["dias_demora"].apply(semaforo_comprador)

sol = sol.sort_values(
    by=["pedido", "dias_demora"],
    ascending=[True, False]
)

st.dataframe(
    sol[
        [
            "solped", "pedido", "grupo_compras", "centro",
            "fecha_lib", "fecha_pedido",
            "estatus", "dias_atencion"
        ]
    ],
    use_container_width=True
)

# Gráfica compradores
st.subheader("📈 Desempeño por grupo de compras")

grp = (
    sol.dropna(subset=["dias_atencion"])
    .groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean"))
    .sort_values("promedio")
)

st.plotly_chart(
    px.bar(
        grp,
        x="grupo_compras",
        y="promedio",
        color="promedio",
        color_continuous_scale=["green", "orange", "red"],
        title="Promedio de días para crear pedidos"
    ),
    use_container_width=True
)
