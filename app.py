import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =========================================
# CARGA DE ARCHIVOS
# =========================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =========================================
# 🚚 SEGUIMIENTO A PROVEEDORES
# =========================================
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

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)

# Selección cantidad solicitada
st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox("Columna de cantidad pedida", ped.columns.tolist())
ped["cantidad_pedida"] = pd.to_numeric(ped[col_cant], errors="coerce").fillna(0)

# MR
ped["entregado"] = ped["cantidad_entregada"] > 0

# Pendiente real
ped["pendiente"] = ped["cantidad_pedida"] - ped["cantidad_entregada"]
ped.loc[ped["pendiente"] < 0, "pendiente"] = 0

# Demora contra fecha compromiso
ped["dias_demora"] = (HOY - pd.to_datetime(ped["fecha_entrega"])).dt.days
ped["dias_demora"] = ped["dias_demora"].fillna(0)
ped.loc[ped["dias_demora"] < 0, "dias_demora"] = 0
ped["dias_demora"] = ped["dias_demora"].astype(int)

def estatus_proveedor(row):
    if row["entregado"]:
        return "✅ Entregado"
    if row["dias_demora"] > 60:
        return f"🔴 {row['dias_demora']}"
    if row["dias_demora"] > 30:
        return f"🟡 {row['dias_demora']}"
    return f"🟢 {row['dias_demora']}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

# Filtros
st.subheader("🔍 Filtros Proveedores")

ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

f_prov = st.multiselect("Proveedor", sorted(ped["proveedor"].unique()))
f_grp = st.multiselect("Grupo de artículos", sorted(ped["grupo"].unique()))
f_ctro = st.multiselect("Centro", sorted(ped["centro"].unique()))

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp["proveedor"].isin(f_prov)]
if f_grp:
    dfp = dfp[dfp["grupo"].isin(f_grp)]
if f_ctro:
    dfp = dfp[dfp["centro"].isin(f_ctro)]

# KPIs
pedidos_pendientes = dfp[(dfp["pendiente"] > 0) & (~dfp["entregado"])]["pedido"].nunique()
pedidos_con_demora = dfp[dfp["dias_demora"] > 0]["pedido"].nunique()

col1, col2 = st.columns(2)
col1.metric("📦 Pedidos con pendiente (sin MR)", pedidos_pendientes)
col2.metric("⏰ Pedidos con demora", pedidos_con_demora)

# Gráfica top proveedores
top10 = (
    dfp[(dfp["pendiente"] > 0) & (~dfp["entregado"])]
    .groupby("proveedor", as_index=False)
    .agg(promedio=("dias_demora", "mean"))
    .sort_values("promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="🚨 TOP PROVEEDORES QUE PONEN EN RIESGO EL INVENTARIO",
    labels={"promedio": "Días de demora"}
)

st.plotly_chart(fig1, use_container_width=True)

# Orden p0
dfp = dfp.sort_values(["entregado", "dias_demora"], ascending=[True, False])

st.dataframe(
    dfp[
        [
            "pedido", "proveedor", "material", "descripcion",
            "grupo", "centro", "fecha_pedido", "fecha_entrega",
            "pendiente", "estatus"
        ]
    ],
    use_container_width=True
)

# =========================================
# 🧑‍💼 SEGUIMIENTO A COMPRADORES
# =========================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Pedido de Compras": "pedido",
    "Grupo de compras": "grupo_compras",
    "Centro": "centro",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["solped"] = sol["solped"].astype(str)
sol["pedido"] = sol["pedido"].astype(str).replace("nan", "SIN TRATAMIENTO")

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce").dt.date
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce").dt.date

sol["dias_sin_pedido"] = np.nan
mask_sin = sol["pedido"] == "SIN TRATAMIENTO"
sol.loc[mask_sin, "dias_sin_pedido"] = (HOY - pd.to_datetime(sol.loc[mask_sin, "fecha_lib"])).dt.days

sol["dias_atencion"] = np.nan
mask_con = sol["pedido"] != "SIN TRATAMIENTO"
sol.loc[mask_con, "dias_atencion"] = (
    pd.to_datetime(sol.loc[mask_con, "fecha_pedido"])
    - pd.to_datetime(sol.loc[mask_con, "fecha_lib"])
).dt.days

sol["dias_sin_pedido"] = sol["dias_sin_pedido"].fillna(0).astype(int)
sol["dias_atencion"] = sol["dias_atencion"].fillna(0).astype(int)

def estatus_comprador(d):
    if d == 0:
        return ""
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol["estatus"] = sol["dias_sin_pedido"].apply(estatus_comprador)

sol = sol.sort_values(by=["pedido", "dias_sin_pedido"], ascending=[True, False])

st.dataframe(
    sol[
        [
            "solped", "pedido", "grupo_compras", "centro",
            "fecha_lib", "fecha_pedido", "estatus", "dias_atencion"
        ]
    ],
    use_container_width=True
)

# Gráfica compradores
grp = (
    sol[sol["dias_atencion"] > 0]
    .groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean"))
    .sort_values("promedio")
)

fig2 = px.bar(
    grp,
    x="grupo_compras",
    y="promedio",
    color="promedio",
    color_continuous_scale=["green", "orange", "red"],
    title="⏱️ Tiempo promedio para crear pedidos por grupo de compras"
)

st.plotly_chart(fig2, use_container_width=True)
