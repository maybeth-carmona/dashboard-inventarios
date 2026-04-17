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

# quitar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce")
ped = ped[ped["fecha_entrega"].notna()].copy()

ped["cantidad_pedida"] = pd.to_numeric(ped["cantidad_pedida"], errors="coerce").fillna(0)
ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)

ped["cantidad_entregada_visible"] = ped[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# SOLO PEDIDOS AÚN PENDIENTES (OPTIMIZA)
# =====================================================
ped = ped[ped["cantidad_entregada_visible"] < ped["cantidad_pedida"]].copy()

# =====================================================
# DEMORA Y SEMÁFORO
# =====================================================
ped["dias_demora"] = (HOY - ped["fecha_entrega"]).dt.days
ped.loc[ped["dias_demora"] < 0, "dias_demora"] = 0

def semaforo(d):
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped["dias_demora"].apply(semaforo)

# =====================================================
# FILTROS TIPO EXCEL
# =====================================================
st.sidebar.subheader("🔍 Filtros")

f_prov = st.sidebar.multiselect(
    "Proveedor",
    sorted(ped["proveedor"].unique()),
    default=sorted(ped["proveedor"].unique())
)

f_grp = st.sidebar.multiselect(
    "Grupo artículos",
    sorted(ped["grupo"].unique()),
    default=sorted(ped["grupo"].unique())
)

f_cen = st.sidebar.multiselect(
    "Centro",
    sorted(ped["centro"].unique()),
    default=sorted(ped["centro"].unique())
)

df = ped[
    (ped["proveedor"].isin(f_prov)) &
    (ped["grupo"].isin(f_grp)) &
    (ped["centro"].isin(f_cen))
].copy()

# =====================================================
# KPIs GRANDES
# =====================================================
kpi_total = df["pedido"].nunique()
kpi_atraso = df[df["dias_demora"] > 0]["pedido"].nunique()

k1, k2 = st.columns(2)
k1.metric("Pedidos en riesgo", kpi_total)
k2.metric("Pedidos con atraso", kpi_atraso)

# =====================================================
# GRÁFICA DE RIESGO (DEGRADADO)
# =====================================================
prov_plot = (
    df.groupby("proveedor", as_index=False)
      .agg(promedio_atraso=("dias_demora", "mean"))
      .sort_values("promedio_atraso", ascending=False)
)

fig = px.bar(
    prov_plot.head(10),
    x="proveedor",
    y="promedio_atraso",
    color="promedio_atraso",
    color_continuous_scale=["#70AD47", "#FFC000", "#C00000"],
    title="Top proveedores que ponen en riesgo los niveles de inventario"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLA RESUMEN POR PROVEEDOR (NUEVA)
# =====================================================
st.subheader("Proveedores que ponen en riesgo el inventario")

tabla_prov = (
    df.groupby("proveedor")
      .agg(
          pedidos_pendientes=("pedido", "nunique"),
          atraso_promedio=("dias_demora", "mean"),
          atraso_maximo=("dias_demora", "max")
      )
      .sort_values("atraso_promedio", ascending=False)
)

st.dataframe(tabla_prov, use_container_width=True)

# =====================================================
# TABLA DETALLE FINAL
# =====================================================
st.subheader("Detalle de pedidos en riesgo")

df = df.sort_values("dias_demora", ascending=False)

st.dataframe(
    df[
        [
            "pedido",
            "proveedor",
            "material",
            "descripcion",
            "grupo",
            "centro",
            "fecha_entrega",
            "cantidad_pedida",
            "cantidad_entregada_visible",
            "estatus"
        ]
    ],
    use_container_width=True
)
