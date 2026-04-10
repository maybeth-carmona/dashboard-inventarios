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

# fechas limpias (sin hora)
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date

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

# cantidad pendiente REAL
ped["cantidad_pendiente"] = ped["cantidad_pedida"] - ped["cantidad_entregada"]
ped.loc[ped["cantidad_pendiente"] < 0, "cantidad_pendiente"] = 0

# ✅ ENTREGADO solo cuando pendiente = 0
ped["entregado"] = ped["cantidad_pendiente"] == 0

# demora contra FECHA COMPROMISO
ped["dias_demora"] = (
    pd.to_datetime(HOY) - pd.to_datetime(ped["fecha_entrega"])
).dt.days.fillna(0)

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

# ---- filtros proveedores
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

# KPIs por PEDIDO
pedidos_pendientes = dfp[(dfp["cantidad_pendiente"] > 0)]["pedido"].nunique()
pedidos_con_demora = dfp[(dfp["cantidad_pendiente"] > 0) & (dfp["dias_demora"] > 0)]["pedido"].nunique()

col1, col2 = st.columns(2)
col1.metric("📦 Pedidos con pendiente (sin surtir)", pedidos_pendientes)
col2.metric("⏰ Pedidos con demora", pedidos_con_demora)

# TOP 10 PROVEEDORES EN RIESGO
top10 = (
    dfp[(dfp["cantidad_pendiente"] > 0)]
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

# orden p0
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
            "cantidad_pendiente", "estatus"
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

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce").dt.date
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce").dt.date

# días sin atender
sol["dias_demora"] = np.where(
    sol["pedido"] == "SIN TRATAMIENTO",
    (pd.to_datetime(HOY) - pd.to_datetime(sol["fecha_lib"])).dt.days,
    np.nan
)

# días reales de atención
sol["dias_atencion"] = np.where(
    sol["pedido"] != "SIN TRATAMIENTO",
    (pd.to_datetime(sol["fecha_pedido"]) - pd.to_datetime(sol["fecha_lib"])).dt.days,
    np.nan
)

def estatus_comprador(d):
    if pd.isna(d):
        return ""
    d = int(d)
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol["estatus"] = sol["dias_demora"].apply(estatus_comprador)

# orden compradores
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

# gráfica compradores
st.subheader("📈 Desempeño por grupo de compras")

f_grp_comp = st.multiselect(
    "Filtrar grupo de compras",
    sorted(sol["grupo_compras"].dropna().unique())
)

df_grp = sol.dropna(subset=["dias_atencion"])
if f_grp_comp:
    df_grp = df_grp[df_grp["grupo_compras"].isin(f_grp_comp)]

fig2 = px.bar(
    df_grp.groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean")),
    x="grupo_compras",
    y="promedio",
    color="promedio",
    color_continuous_scale=["green", "orange", "red"],
    title="⏱️ Tiempo promedio para crear pedidos por grupo de compras"
)

st.plotly_chart(fig2, use_container_width=True)
