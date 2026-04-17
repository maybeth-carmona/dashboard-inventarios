import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(
    page_title="Riesgo en Compras | Seguimiento a Proveedores",
    layout="wide"
)
st.title("Riesgo en Compras | Seguimiento a Proveedores")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA ARCHIVO
# =====================================================
st.sidebar.header("📂 Archivo SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
if file_ped is None:
    st.info("Carga el archivo de pedidos")
    st.stop()

ped = pd.read_excel(file_ped)

# =====================================================
# NORMALIZACIÓN DE COLUMNAS
# =====================================================
ped = ped.rename(columns={
    "Pedido de Compras": "pedido",
    "Proveedor TEXT": "proveedor",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha Creación Pedido": "fecha_pedido",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada"
})

# =====================================================
# LIMPIEZA BASE
# =====================================================
ped["pedido"] = ped["pedido"].astype(str)
ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)
ped["material"] = ped["material"].astype(str)

# Quitar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped = ped[ped["fecha_entrega"].notna()].copy()

ped["cantidad_pedida"] = pd.to_numeric(ped["cantidad_pedida"], errors="coerce").fillna(0)
ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)

ped["cantidad_entregada_visible"] = ped[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# SOLO PENDIENTES (OPTIMIZA Y LIMPIA)
# =====================================================
ped = ped[ped["cantidad_entregada_visible"] < ped["cantidad_pedida"]].copy()

# =====================================================
# DEMORA Y SEMÁFORO
# =====================================================
ped["dias_demora"] = (
    HOY - pd.to_datetime(ped["fecha_entrega"])
).dt.days.fillna(0)
ped.loc[ped["dias_demora"] < 0, "dias_demora"] = 0

def estatus_proveedor(d):
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped["dias_demora"].apply(estatus_proveedor)

# =====================================================
# FILTROS TIPO EXCEL (PALOMITAS)
# =====================================================
st.sidebar.subheader("🔍 Filtros")

prov_opts = sorted(ped["proveedor"].dropna().unique().tolist())
grp_opts = sorted(ped["grupo"].dropna().unique().tolist())
cen_opts = sorted(ped["centro"].dropna().unique().tolist())
mat_opts = sorted(ped["material"].dropna().unique().tolist())
ped_opts = sorted(ped["pedido"].dropna().unique().tolist())

f_prov = st.sidebar.multiselect("Proveedor", prov_opts, default=prov_opts)
f_grp = st.sidebar.multiselect("Grupo artículos", grp_opts, default=grp_opts)
f_cen = st.sidebar.multiselect("Centro", cen_opts, default=cen_opts)
f_mat = st.sidebar.multiselect("Material", mat_opts)
f_ped = st.sidebar.multiselect("Pedido", ped_opts)

df = ped[
    ped["proveedor"].isin(f_prov) &
    ped["grupo"].isin(f_grp) &
    ped["centro"].isin(f_cen)
].copy()

if f_mat:
    df = df[df["material"].isin(f_mat)]
if f_ped:
    df = df[df["pedido"].isin(f_ped)]

# =====================================================
# KPIs
# =====================================================
c1, c2 = st.columns(2)
c1.metric("Pedidos en riesgo", df["pedido"].nunique())
c2.metric("Pedidos con atraso", df[df["dias_demora"] > 0]["pedido"].nunique())

# =====================================================
# GRÁFICA
# =====================================================
top10 = (
    df.groupby("proveedor", as_index=False)
      .agg(promedio=("dias_demora", "mean"))
      .sort_values("promedio", ascending=False)
      .head(10)
)

fig = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="Top 10 proveedores que ponen en riesgo los niveles de inventario",
    color_discrete_sequence=["#69A341"]
)
st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLA FINAL
# =====================================================
st.subheader("Detalle de pedidos en riesgo")

df = df.sort_values("dias_demora", ascending=False)

st.dataframe(
    df[
        [
            "pedido", "proveedor", "material", "descripcion",
            "grupo", "centro", "fecha_entrega",
            "cantidad_pedida", "cantidad_entregada_visible",
            "estatus"
        ]
    ],
    use_container_width=True
)
