import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA ARCHIVOS
# =====================================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES (CONGELADO ✅)
# =====================================================
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

# Quitar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# Fechas sin hora
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

# Cantidades
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# Cantidad solicitada
st.sidebar.subheader("📦 Cantidad solicitada")
col_cant = st.sidebar.selectbox("Columna de cantidad pedida", ped.columns.tolist())
ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# -----------------------------------------------------
# RESUMEN POR PEDIDO (NEGOCIO)
# -----------------------------------------------------
resumen = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        grupo=("grupo", "first"),
        centro=("centro", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        pedida_total=("cantidad_pedida", "sum"),
        entregada_total=("cantidad_entregada", "sum"),
    )
)

resumen["pendiente_pedido"] = (
    resumen["pedida_total"] - resumen["entregada_total"]
).clip(lower=0)

# Criterio operativo
resumen["tiene_mr"] = resumen["entregada_total"] > 0

resumen["dias_demora"] = (
    (HOY - pd.to_datetime(resumen["fecha_entrega"]))
    .dt.days
    .fillna(0)
    .clip(lower=0)
)

ped = ped.merge(
    resumen[["pedido", "pendiente_pedido", "tiene_mr", "dias_demora"]],
    on="pedido",
    how="left"
)

def estatus_proveedor(row):
    if row["tiene_mr"]:
        return "✅ Entregado"
    d = row["dias_demora"]
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

# =====================================================
# 🔍 FILTROS
# =====================================================
st.subheader("🔍 Filtros")

ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

f_prov = st.multiselect("Proveedor", sorted(ped["proveedor"].unique()))
f_grp = st.multiselect("Grupo artículos", sorted(ped["grupo"].unique()))
f_cen = st.multiselect("Centro", sorted(ped["centro"].unique()))

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp["proveedor"].isin(f_prov)]
if f_grp:
    dfp = dfp[dfp["grupo"].isin(f_grp)]
if f_cen:
    dfp = dfp[dfp["centro"].isin(f_cen)]

# =====================================================
# KPIs
# =====================================================
kpi_pend = dfp[~dfp["tiene_mr"]]["pedido"].nunique()
kpi_dem = dfp[(~dfp["tiene_mr"]) & (dfp["dias_demora"] > 0)]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos SIN MR", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# =====================================================
# 📊 GRÁFICA
# =====================================================
top10 = (
    dfp[~dfp["tiene_mr"]]
    .groupby("proveedor", as_index=False)
    .agg(promedio=("dias_demora", "mean"))
    .sort_values("promedio", ascending=False)
    .head(10)
)

fig = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="📊 Proveedores con pedidos pendientes",
    color_discrete_sequence=["#FF671D", "#BABD13", "#CDC1AC"]
)

st.plotly_chart(fig, use_container_width=True)

st.dataframe(dfp, use_container_width=True)

# =====================================================
# 🧑‍💼 SEGUIMIENTO A COMPRADORES (ARREGLADO ✅)
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")

# Renombrar columnas reales del Excel
sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Grupo de compras": "grupo_compras",
    "Pedido de Compras": "pedido",
    "Fecha Liberación Solped": "fecha_lib",   # J1
    "Fecha Creación Pedido": "fecha_pedido"  # K1
})

sol["solped"] = sol["solped"].astype(str)
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)

# Todas las solpeds tienen fecha de liberación
sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

# Días desde liberación
sol["dias_desde_lib"] = (HOY - sol["fecha_lib"]).dt.days

# Días en atención (solo si ya hay pedido)
sol["dias_atencion"] = np.where(
    sol["pedido"].notna() & (sol["pedido"] != ""),
    (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
    np.nan
)

def estatus_comprador(row):
    if pd.notna(row["dias_atencion"]):
        return f"✅ ATENDIDO ({int(row['dias_atencion'])} días)"
    if row["dias_desde_lib"] <= 20:
        return f"🟢 {row['dias_desde_lib']}"
    if row["dias_desde_lib"] <= 30:
        return f"🟡 {row['dias_desde_lib']}"
    return f"🔴 {row['dias_desde_lib']}"

sol["estatus"] = sol.apply(estatus_comprador, axis=1)

st.dataframe(
    sol[
        [
            "solped",
            "grupo_compras",
            "fecha_lib",
            "pedido",
            "fecha_pedido",
            "estatus"
        ]
    ],
    use_container_width=True
)
