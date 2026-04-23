import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# ======================================
# CONFIGURACIÓN
# ======================================
st.set_page_config(layout="wide")
st.markdown("## **Riesgo en Compras | Seguimiento a Proveedores**")

HOY = pd.to_datetime(datetime.today().date())

# ======================================
# CARGA RAW
# ======================================
file = st.file_uploader("Estatus de pedidos de compra (RAW SAP)", type=["xlsx"])
if file is None:
    st.stop()

raw = pd.read_excel(file)

# ======================================
# NORMALIZACIÓN DE COLUMNAS
# ======================================
df = raw.rename(columns={
    "Pedido de Compras": "pedido",
    "Material": "material_sap",
    "Texto Breve Posicion": "material_desc",
    "Grupo artículos": "grupo_articulo",
    "Grupo de compras": "grupo_compra",
    "Centro": "centro",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
    "Valor Neto de la Pos": "valor_pos",
    "Moneda": "moneda"
})

# Fechas
df["fecha_creacion"] = pd.to_datetime(raw["Fecha de Creación"], errors="coerce") \
    if "Fecha de Creación" in raw.columns else pd.NaT

df["fecha_entrega"] = pd.to_datetime(raw["Fecha de Entrega"], errors="coerce") \
    if "Fecha de Entrega" in raw.columns else pd.NaT

# Proveedor
if "Proveedor TEXT" in raw.columns and "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = raw["Proveedor"].astype(str)
elif "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# Numéricos
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

# Pendiente real
df["cantidad_pendiente"] = (df["cantidad_pedida"] - df["cantidad_entregada"]).clip(lower=0)

# Días de demora
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days.fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

# ======================================
# FILTROS GLOBALES
# ======================================
st.sidebar.header("Filtros")

f_prov = st.sidebar.multiselect("Proveedor", sorted(df["proveedor"].unique()))
f_gc = st.sidebar.multiselect("Grupo de compras", sorted(df["grupo_compra"].dropna().astype(str).unique()))
f_ga = st.sidebar.multiselect("Grupo de artículos", sorted(df["grupo_articulo"].dropna().astype(str).unique()))
f_centro = st.sidebar.multiselect("Centro", sorted(df["centro"].dropna().astype(str).unique()))

mask = pd.Series(True, index=df.index)
if f_prov: mask &= df["proveedor"].isin(f_prov)
if f_gc: mask &= df["grupo_compra"].astype(str).isin(f_gc)
if f_ga: mask &= df["grupo_articulo"].astype(str).isin(f_ga)
if f_centro: mask &= df["centro"].astype(str).isin(f_centro)

df_view = df[mask].copy()

# ======================================
# KPIs
# ======================================
pedidos_riesgo = df_view[df_view["dias_demora"] > 30]["pedido"].nunique()
pedidos_atraso = df_view[df_view["dias_demora"] > 0]["pedido"].nunique()

c1, c2 = st.columns(2)

c1.metric("Pedidos en riesgo", pedidos_riesgo)
c2.metric("Pedidos con atraso", pedidos_atraso)

st.markdown("---")

# ======================================
# GRÁFICA PROVEEDORES (REAL)
# ======================================
prov_plot = (
    df_view.groupby("proveedor", as_index=False)
    .agg(dias_max=("dias_demora", "max"))
    .sort_values("dias_max", ascending=False)
    .head(10)
)

fig = px.bar(
    prov_plot,
    x="proveedor",
    y="dias_max",
    color="dias_max",
    title="Proveedores con mayor atraso (días máximos)",
    color_continuous_scale=["#5cb85c", "#f0ad4e", "#d9534f"]
)

st.plotly_chart(fig, use_container_width=True)

# ======================================
# RESUMEN POR PROVEEDOR
# ======================================
st.subheader("Resumen por proveedor")

resumen = (
    df_view[df_view["cantidad_pendiente"] > 0]
    .groupby(["proveedor", "moneda"])
    .agg(
        pedidos_pendientes=("pedido", "nunique"),
        monto_total=("valor_pos", "sum"),
        dias_maximos=("dias_demora", "max")
    )
    .reset_index()
    .sort_values("dias_maximos", ascending=False)
)

st.dataframe(resumen, use_container_width=True)

# ======================================
# DETALLE DE PEDIDOS PENDIENTES
# ======================================
st.subheader("Detalle de pedidos pendientes")

detalle = df_view[df_view["cantidad_pendiente"] > 0][
    [
        "pedido",
        "proveedor",
        "material_desc",
        "material_sap",
        "grupo_articulo",
        "cantidad_pendiente",
        "dias_demora",
        "fecha_creacion",
        "fecha_entrega",
        "centro"
    ]
].sort_values("dias_demora", ascending=False)

st.dataframe(detalle, use_container_width=True)
