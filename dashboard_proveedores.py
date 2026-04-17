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
# RENOMBRE COLUMNAS (SAP REAL)
# =====================================================
ped = ped.rename(columns={
    "Pedido de Compras": "pedido",
    "Proveedor TEXT": "proveedor",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
    "Valor Neto de la Pos": "valor_pos"   # ✅ AF1
})

# =====================================================
# LIMPIEZA BASE
# =====================================================
ped["pedido"] = ped["pedido"].astype(str)
ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

# Quitar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce")
ped = ped[ped["fecha_entrega"].notna()].copy()

ped["cantidad_pedida"] = pd.to_numeric(ped["cantidad_pedida"], errors="coerce").fillna(0)
ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)
ped["valor_pos"] = pd.to_numeric(ped["valor_pos"], errors="coerce").fillna(0)

# Cantidad entregada visible (no mayor al pedido)
ped["cantidad_entregada_visible"] = ped[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# SOLO POSICIONES PENDIENTES (OPTIMIZA Y ES REAL)
# =====================================================
ped = ped[ped["cantidad_entregada_visible"] < ped["cantidad_pedida"]].copy()

# =====================================================
# DEMORA
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
    ped["proveedor"].isin(f_prov) &
    ped["grupo"].isin(f_grp) &
    ped["centro"].isin(f_cen)
].copy()

# =====================================================
# KPIs EJECUTIVOS (VISUALES)
# =====================================================
kpi_pedidos = df["pedido"].nunique()
kpi_atraso = df[df["dias_demora"] > 0]["pedido"].nunique()
kpi_monto = df["valor_pos"].sum()

k1, k2, k3 = st.columns(3)
k1.metric("Pedidos en riesgo", f"{kpi_pedidos}")
k2.metric("Pedidos con atraso", f"{kpi_atraso}")
k3.metric("Monto en riesgo", f"${kpi_monto:,.0f}")

# =====================================================
# GRÁFICA DE RIESGO (DEGRADADO)
# =====================================================
prov_plot = (
    df.groupby("proveedor", as_index=False)
      .agg(atraso_prom=("dias_demora", "mean"))
      .sort_values("atraso_prom", ascending=False)
      .head(10)
)

fig = px.bar(
    prov_plot,
    x="proveedor",
    y="atraso_prom",
    color="atraso_prom",
    color_continuous_scale=["#70AD47", "#FFC000", "#C00000"],
    title="Top proveedores que ponen en riesgo los niveles de inventario"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLA RESUMEN POR PROVEEDOR
# =====================================================
st.subheader("Proveedores que ponen en riesgo el inventario")

tabla_resumen = (
    df.groupby("proveedor")
      .agg(
          pedidos_pendientes=("pedido", "nunique"),
          posiciones_pendientes=("material", "count"),
          atraso_promedio=("dias_demora", "mean"),
          atraso_maximo=("dias_demora", "max"),
          monto_riesgo=("valor_pos", "sum")
      )
      .sort_values("monto_riesgo", ascending=False)
)

st.dataframe(
    tabla_resumen.style.format({
        "atraso_promedio": "{:.1f}",
        "monto_riesgo": "${:,.0f}"
    }),
    use_container_width=True
)

# =====================================================
# TABLA DETALLE FINAL
# =====================================================
st.subheader("Detalle de posiciones en riesgo")

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
            "cantidad_pedida",
            "cantidad_entregada_visible",
            "valor_pos",
            "dias_demora",
            "estatus"
        ]
    ],
    use_container_width=True
)
``
