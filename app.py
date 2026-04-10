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
# 📂 CARGA DE ARCHIVOS
# =====================================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.info("⬅️ Carga ambos archivos para iniciar")
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES (FOCO PRINCIPAL)
# =====================================================
st.header("🚚 Seguimiento a Proveedores")

# ---------- Normalización mínima ----------
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

# Fechas SIN hora
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date

# Cantidades
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# Selección manual de cantidad solicitada (SAP varía)
st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    options=ped.columns.tolist()
)

ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# 🔑 AGREGACIÓN CORRECTA POR PEDIDO (CLAVE)
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

# Cantidad pendiente correcta
resumen["pendiente_pedido"] = (
    resumen["pedida_total"] - resumen["entregada_total"]
).clip(lower=0)

# SOLO pedidos con pendiente (esto es CLAVE)
resumen = resumen[resumen["pendiente_pedido"] > 0].copy()

# Días de demora contra FECHA COMPROMISO
resumen["dias_demora"] = (
    (HOY - pd.to_datetime(resumen["fecha_entrega"]))
    .dt.days
)
resumen["dias_demora"] = resumen["dias_demora"].fillna(0)
resumen.loc[resumen["dias_demora"] < 0, "dias_demora"] = 0

# Reinyectar al detalle (solo pendientes)
ped = ped.merge(
    resumen[["pedido", "pendiente_pedido", "dias_demora"]],
    on="pedido",
    how="inner"   # 🔥 elimina ENTREGADOS
)

# Semáforo (el que ya te gustaba)
def semaforo_proveedor(d):
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

ped["estatus"] = ped["dias_demora"].apply(semaforo_proveedor)

# =====================================================
# 🔍 FILTROS PROVEEDORES
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
# KPIs (SOLO PENDIENTES)
# =====================================================
kpi_pend = dfp["pedido"].nunique()
kpi_dem = dfp[dfp["dias_demora"] > 0]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos con pendiente", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# =====================================================
# 📊 GRÁFICA TOP PROVEEDORES (RESPONDE A FILTROS)
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
    title="📊 Top proveedores que ponen en riesgo el inventario",
    color_discrete_sequence=["#0096A9"]  # azul corporativo relajado
)
st.plotly_chart(fig1, use_container_width=True)

# =====================================================
# 📋 TABLA FINAL (SOLO PENDIENTES, ORDENADA)
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
# (NO TOCADO DE MOMENTO, SOLO ESTABLE)
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")
st.info("ℹ️ Esta sección se ajusta después de validar proveedores.")
