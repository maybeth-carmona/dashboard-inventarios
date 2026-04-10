import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Proveedores", layout="wide")
st.title("📊 Seguimiento a Proveedores – Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA ARCHIVO
# =====================================================
st.sidebar.header("📂 Archivo SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])

if file_ped is None:
    st.info("⬅️ Carga el archivo de Pedidos de Compras")
    st.stop()

ped = pd.read_excel(file_ped)

# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES
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

# ❌ Quitar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# ✅ Fechas SIN hora
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

# ✅ Cantidades
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# ✅ Cantidad solicitada
st.sidebar.subheader("📦 Cantidad solicitada")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)

ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# RESUMEN POR PEDIDO (LÓGICA VALIDADA)
# =====================================================
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

# ✅ Criterio operativo
resumen["tiene_mr"] = resumen["entregada_total"] > 0

resumen["dias_demora"] = (
    (HOY - pd.to_datetime(resumen["fecha_entrega"]))
    .dt.days
    .fillna(0)
    .clip(lower=0)
)

# Volver a detalle
ped = ped.merge(
    resumen[["pedido", "pendiente_pedido", "tiene_mr", "dias_demora"]],
    on="pedido",
    how="left"
)

# =====================================================
# SEMÁFORO (CONSERVADO)
# =====================================================
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
# 📊 GRÁFICA FINAL (VERDE CORPORATIVO)
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
    color_discrete_sequence=["#69A341"]
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# 📋 TABLA FINAL
# =====================================================
dfp = dfp.sort_values(by=["tiene_mr", "dias_demora"], ascending=[True, False])

st.dataframe(
    dfp[
        [
            "pedido",
            "proveedor",
            "material",
            "descripcion",
            "grupo",
            "centro",
            "fecha_pedido",
            "fecha_entrega",
            "cantidad_pedida",
            "cantidad_entregada",
            "pendiente_pedido",
            "estatus",
        ]
    ],
    use_container_width=True
)
``
