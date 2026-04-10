import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

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
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

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

# ❌ eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# fechas
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce")
ped = ped[ped["fecha_pedido"].notna()].copy()
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce")

# cantidades
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# cantidad solicitada
st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)
ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# 🔑 AGREGACIÓN POR PEDIDO (estatus y KPIs)
# =====================================================
resumen = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        grupo=("grupo", "first"),
        centro=("centro", "first"),
        fecha_pedido=("fecha_pedido", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        cantidad_pedida_total=("cantidad_pedida", "sum"),
        cantidad_entregada_total=("cantidad_entregada", "sum")
    )
)

resumen["cantidad_pendiente_pedido"] = (
    resumen["cantidad_pedida_total"]
    - resumen["cantidad_entregada_total"]
).clip(lower=0)

resumen["entregado_pedido"] = resumen["cantidad_pendiente_pedido"] == 0

resumen["dias_demora"] = (
    (HOY - resumen["fecha_entrega"])
    .dt.days
    .fillna(0)
)
resumen.loc[resumen["dias_demora"] < 0, "dias_demora"] = 0
resumen["dias_demora"] = resumen["dias_demora"].astype("Int64")

# regresar info al detalle
ped = ped.merge(
    resumen[
        ["pedido", "cantidad_pendiente_pedido", "entregado_pedido", "dias_demora"]
    ],
    on="pedido",
    how="left"
)

def estatus_proveedor(row):
    if row["entregado_pedido"]:
        return "✅ Entregado"
    if row["dias_demora"] > 60:
        return f"🔴 {row['dias_demora']}"
    if row["dias_demora"] > 30:
        return f"🟡 {row['dias_demora']}"
    return f"🟢 {row['dias_demora']}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

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

# KPIs por pedido
kpi_pend = resumen[resumen["cantidad_pendiente_pedido"] > 0]["pedido"].nunique()
kpi_dem = resumen[
    (resumen["cantidad_pendiente_pedido"] > 0) &
    (resumen["dias_demora"] > 0)
]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos con pendiente", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# =====================================================
# 📊 TOP 10 PROVEEDORES EN RIESGO
# =====================================================
top10 = (
    resumen[resumen["cantidad_pendiente_pedido"] > 0]
    .groupby("proveedor", as_index=False)
    .agg(dias_promedio=("dias_demora", "mean"))
    .sort_values("dias_promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="dias_promedio",
    title="🚨 TOP PROVEEDORES QUE PONEN EN RIESGO EL INVENTARIO",
    labels={"dias_promedio": "Días de demora"}
)
st.plotly_chart(fig1, use_container_width=True)

# tabla detalle ordenada
dfp = dfp.sort_values(
    by=["entregado_pedido", "dias_demora"],
    ascending=[True, False]
)

st.dataframe(
    dfp[
        [
            "pedido", "proveedor", "material", "descripcion",
            "grupo", "centro",
            "fecha_pedido", "fecha_entrega",
            "cantidad_pedida", "cantidad_entregada",
            "cantidad_pendiente_pedido", "estatus"
        ]
    ],
    use_container_width=True
)

# =====================================================
# 🧑‍💼 SEGUIMIENTO A COMPRADORES
# =====================================================
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
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)
sol["pedido"] = sol["pedido"].replace("nan", "SIN TRATAMIENTO")

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

sol["dias_demora"] = np.where(
    sol["pedido"] == "SIN TRATAMIENTO",
    (HOY - sol["fecha_lib"]).dt.days,
    np.nan
)

sol["dias_atencion"] = np.where(
    sol["pedido"] != "SIN TRATAMIENTO",
    (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
    np.nan
)

def estatus_comprador(d):
    if pd.isna(d):
        return ""
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

sol["estatus"] = sol["dias_demora"].apply(estatus_comprador)

sol = sol.sort_values(by=["pedido", "dias_demora"], ascending=[True, False])

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

# =====================================================
# 📈 GRÁFICA COMPRADORES
# =====================================================
st.subheader("📈 Tiempo de atención por grupo de compras")

f_gc = st.multiselect(
    "Filtrar grupo de compras",
    sorted(sol["grupo_compras"].dropna().unique())
)

df_gc = sol.dropna(subset=["dias_atencion"])
if f_gc:
    df_gc = df_gc[df_gc["grupo_compras"].isin(f_gc)]

fig2 = px.bar(
    df_gc.groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean")),
    x="grupo_compras",
    y="promedio",
    color="promedio",
    color_continuous_scale=["green", "orange", "red"],
    title="⏱️ Tiempo promedio para crear pedidos por grupo de compras"
)
st.plotly_chart(fig2, use_container_width=True)
