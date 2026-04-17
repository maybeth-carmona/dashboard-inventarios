import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Riesgo en Compras | Seguimiento a Proveedores", layout="wide")
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

ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped = ped[ped["fecha_entrega"].notna()].copy()

ped["cantidad_pedida"] = pd.to_numeric(ped["cantidad_pedida"], errors="coerce").fillna(0)
ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)

ped["cantidad_entregada_visible"] = ped[["cantidad_entregada","cantidad_pedida"]].min(axis=1)

# =====================================================
# QUITAR ENTREGADOS COMPLETOS (OPTIMIZACIÓN)
# =====================================================
ped = ped[ped["cantidad_entregada_visible"] < ped["cantidad_pedida"]].copy()

# =====================================================
# DEMORA Y ESTATUS
# =====================================================
ped["dias_demora"] = (HOY - pd.to_datetime(ped["fecha_entrega"])).dt.days.fillna(0)
ped.loc[ped["dias_demora"] < 0, "dias_demora"] = 0

def estatus_proveedor(d):
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped["dias_demora"].apply(estatus_proveedor)

# =====================================================
# FILTROS TIPO EXCEL (PALOMITAS POR COLUMNA)
# =====================================================
st.sidebar.subheader("🔍 Filtros")

f_prov = st.sidebar.multiselect("Proveedor", sorted(ped["proveedor"].unique()), default=sorted(ped["proveedor"].unique()))
f_ped = st.sidebar.multiselect("Pedido", sorted(ped["pedido"].unique()), default=sorted(ped["pedido"].unique()))
f_grp = st.sidebar.multiselect("Grupo artículos", sorted(ped["grupo"].unique()), default=sorted(ped["grupo"].unique()))
f_cen = st.sidebar.multiselect("Centro", sorted(ped["centro"].unique()), default=sorted(ped["centro"].unique()))
f_mat = st.sidebar.multiselect("Material", sorted(ped["material"].astype(str).unique()))

df = ped[
    (ped["proveedor"].isin(f_prov)) &
    (ped["pedido"].isin(f_ped)) &
    (ped["grupo"].isin(f_grp)) &
    (ped["centro"].isin(f_cen))
].copy()

if f_mat:
    df = df[df["material"].astype(str).isin(f_mat)]

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
      .agg(promedio=("dias_demora","mean"))
      .sort_values("promedio", ascending=False)
      .head(10)
)

fig = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="Proveedores que ponen en riesgo el inventario",
    color_discrete_sequence=["#69A341"]
)
st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLA FINAL
# =====================================================
df = df.sort_values("dias_demora", ascending=False)

st.subheader("Detalle de pedidos en riesgo")

st.dataframe(
    df[
        [
            "pedido","proveedor","material","descripcion",
            "grupo","centro","fecha_pedido","fecha_entrega",
            "cantidad_pedida","cantidad_entregada_visible",
            "estatus"
        ]
    ],
    use_container_width=True
)
