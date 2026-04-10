import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA DE ARCHIVOS
# =====================================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None:
    st.warning("⬅️ Sube el archivo de Pedidos de Compras")
    st.stop()

ped = pd.read_excel(file_ped)

# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES (BIEN HECHO)
# =====================================================
st.header("🚚 Seguimiento a Proveedores")

# ---- Normalización de columnas necesarias (SOLO LAS QUE SÍ USAMOS)
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

# ❌ eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# ---- Fechas SIN hora
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date

# ---- Cantidades
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# Selección de columna de cantidad pedida
st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)

ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# 🔑 RESUMEN REAL POR PEDIDO (LÓGICA CORRECTA)
# =====================================================
resumen = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        grupo=("grupo", "first"),
        centro=("centro", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        pedida_total=("cantidad_pedida", "sum"),
        entregada_total=("cantidad_entregada", "sum")
    )
)

# Pendiente correcta: PEDIDO - ENTREGADO
resumen["pendiente_pedido"] = (
    resumen["pedida_total"] - resumen["entregada_total"]
).clip(lower=0)

# ✅ CRITERIO QUE PEDISTE:
# Si tiene MR (entregada_total > 0) → ENTREGADO → fuera de demoras
resumen["tiene_mr"] = resumen["entregada_total"] > 0

# Días de demora SOLO para los que NO tienen MR
resumen["dias_demora"] = (
    (HOY - pd.to_datetime(resumen["fecha_entrega"]))
    .dt.days
    .fillna(0)
    .clip(lower=0)
)

# ---- SOLO pedidos SIN MR (esto es CLAVE)
resumen_abiertos = resumen[~resumen["tiene_mr"]].copy()

# Volver al detalle SOLO con pedidos abiertos
ped = ped.merge(
    resumen_abiertos[
        ["pedido", "pendiente_pedido", "dias_demora"]
    ],
    on="pedido",
    how="inner"
)

# =====================================================
# 🚦 SEMÁFORO (EL QUE TE GUSTA)
# =====================================================
def semaforo_proveedor(d):
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

ped["estatus"] = ped["dias_demora"].apply(semaforo_proveedor)

# =====================================================
# 🔍 FILTROS
# =====================================================
st.subheader("🔍 Filtros Proveedores")

ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

f_prov = st.multiselect("Proveedor", sorted(ped["proveedor"].unique()))
f_grp = st.multiselect("Grupo de artículos", sorted(ped["grupo"].unique()))
f_cen = st.multiselect("Centro", sorted(ped["centro"].unique()))

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp["proveedor"].isin(f_prov)]
if f_grp:
    dfp = dfp[dfp["grupo"].isin(f_grp)]
if f_cen:
    dfp = dfp[dfp["centro"].isin(f_cen)]

# =====================================================
# KPIs (SOLO ABIERTOS)
# =====================================================
kpi_pend = dfp["pedido"].nunique()
kpi_dem = dfp[dfp["dias_demora"] > 0]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos SIN MR", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# =====================================================
# 📊 GRÁFICA PROVEEDORES (COLOR EXACTO)
# RGB 153,217,217  →  #99D9D9
# =====================================================
top10 = (
    dfp.groupby("proveedor", as_index=False)
    .agg(promedio=("dias_demora", "mean"))
    .sort_values("promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="📊 Proveedores con pedidos pendientes",
    color_discrete_sequence=["#99D9D9"]
)

st.plotly_chart(fig1, use_container_width=True)

# =====================================================
# 📋 TABLA FINAL (SOLO PEDIDOS SIN MR)
# =====================================================
dfp = dfp.sort_values("dias_demora", ascending=False)

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
            "estatus"
        ]
    ],
    use_container_width=True
)

# =====================================================
# 🧑‍💼 SEGUIMIENTO A COMPRADORES
# (PAUSADO HASTA CERRAR PROVEEDORES)
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")
st.info("ℹ️ Esta sección se ajusta después de validar proveedores.")
