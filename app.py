import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Proveedores", layout="wide")
st.title("📊 Seguimiento a Proveedores – Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# BARRA LATERAL – ARCHIVO Y FILTROS
# =====================================================
st.sidebar.header("📂 Archivo SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])

if file_ped is None:
    st.info("⬅️ Carga el archivo de Pedidos de Compras")
    st.stop()

ped = pd.read_excel(file_ped)

st.sidebar.divider()
st.sidebar.subheader("🔍 Filtros")

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
    "Cantidad Entregada": "cantidad_entregada",
    "Indicador Entrega Final": "entrega_final",  # Q1
})

# -------- Normalización básica --------
ped["pedido"] = ped["pedido"].astype(str)
ped["entrega_final"] = ped["entrega_final"].astype(str).str.upper()

# Quitar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# Fechas sin hora
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

# Cantidades (POR PARTIDA, sin sumar)
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

col_cant = st.sidebar.selectbox(
    "📦 Columna de cantidad pedida (partida)",
    ped.columns.tolist()
)
ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# CÁLCULO DE DEMORA Y ESTATUS
# =====================================================
ped["dias_demora"] = (
    HOY - pd.to_datetime(ped["fecha_entrega"])
).dt.days.fillna(0)

ped.loc[ped["dias_demora"] < 0, "dias_demora"] = 0

def estatus_proveedor(row):
    if row["entrega_final"] == "X":
        return "✅ Entregado"
    d = int(row["dias_demora"])
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

# =====================================================
# FILTROS LATERALES
# =====================================================
ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

f_prov = st.sidebar.multiselect("Proveedor", sorted(ped["proveedor"].unique()))
f_grp = st.sidebar.multiselect("Grupo artículos", sorted(ped["grupo"].unique()))
f_cen = st.sidebar.multiselect("Centro", sorted(ped["centro"].unique()))

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp["proveedor"].isin(f_prov)]
if f_grp:
    dfp = dfp[dfp["grupo"].isin(f_grp)]
if f_cen:
    dfp = dfp[dfp["centro"].isin(f_cen)]

# =====================================================
# KPIs (por pedido, usando Q1)
# =====================================================
kpi_pend = dfp[dfp["entrega_final"] != "X"]["pedido"].nunique()
kpi_dem = dfp[(dfp["entrega_final"] != "X") & (dfp["dias_demora"] > 0)]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos SIN Entrega Final", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# =====================================================
# 📊 GRÁFICA – SOLO PENDIENTES
# =====================================================
top10 = (
    dfp[dfp["entrega_final"] != "X"]
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
    color_discrete_sequence=["#69A341"]  # verde corporativo
)
st.plotly_chart(fig, use_container_width=True)

# =====================================================
# 📋 TABLA FINAL – ORDENADA COMO PEDISTE
# =====================================================
dfp = dfp.sort_values(
    by=["entrega_final", "dias_demora"],
    ascending=[True, False]
)

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
            "estatus",
        ]
    ],
    use_container_width=True
)
