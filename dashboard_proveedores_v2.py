import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# ======================================
# CONFIGURACIÓN GENERAL
# ======================================
st.set_page_config(layout="wide")
st.markdown("## **Riesgo en Compras | Seguimiento a Proveedores**")

HOY = pd.to_datetime(datetime.today().date())

# ======================================
# CARGA RAW
# ======================================
file = st.file_uploader("Estatus de pedidos de compra (RAW)", type=["xlsx"])
if file is None:
    st.stop()

raw = pd.read_excel(file)

# ======================================
# NORMALIZACIÓN
# ======================================
df = raw.rename(columns={
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo_articulo",
    "Grupo de compras": "grupo_compra",
    "Centro": "centro",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
    "Valor Neto de la Pos": "valor_pos"
})

# Fecha de entrega
if "Fecha de Entrega" in raw.columns:
    df["fecha_entrega"] = pd.to_datetime(raw["Fecha de Entrega"], errors="coerce")
else:
    df["fecha_entrega"] = pd.NaT

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

df["cantidad_pendiente"] = (df["cantidad_pedida"] - df["cantidad_entregada"]).clip(lower=0)

df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days.fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

# ======================================
# FILTROS (INCLUYE PROVEEDOR ✅)
# ======================================
st.sidebar.header("Filtros")

f_prov = st.sidebar.multiselect(
    "Proveedor",
    sorted(df["proveedor"].unique()),
    default=sorted(df["proveedor"].unique())
)

f_gc = st.sidebar.multiselect(
    "Grupo de compras",
    sorted(df["grupo_compra"].dropna().astype(str).unique())
)

f_ga = st.sidebar.multiselect(
    "Grupo de artículos",
    sorted(df["grupo_articulo"].dropna().astype(str).unique())
)

mask = df["proveedor"].isin(f_prov)

if f_gc:
    mask &= df["grupo_compra"].astype(str).isin(f_gc)

if f_ga:
    mask &= df["grupo_articulo"].astype(str).isin(f_ga)

df_view = df.loc[mask].copy()

# ======================================
# KPIs (COMO IMAGEN)
# ======================================
pedidos_riesgo = df_view[df_view["dias_demora"] > 30]["pedido"].nunique()
pedidos_atraso = df_view[df_view["dias_demora"] > 0]["pedido"].nunique()

c1, c2, c3 = st.columns([1.2, 1.2, 2])

with c1:
    st.markdown(
        f"""
        <div style="background:#d9534f;padding:25px;border-radius:10px;color:white;text-align:center">
        <h1>{pedidos_riesgo}</h1>
        <h4>Pedidos en riesgo</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

with c2:
    st.markdown(
        f"""
        <div style="background:#f0ad4e;padding:25px;border-radius:10px;color:white;text-align:center">
        <h1>{pedidos_atraso}</h1>
        <h4>Pedidos con atraso</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

# ======================================
# GRÁFICA PROVEEDORES
# ======================================
prov_plot = (
    df_view.groupby("proveedor", as_index=False)
    .agg(dias_max=("dias_demora", "max"))
    .sort_values("dias_max", ascending=False)
    .head(8)
)

fig = px.bar(
    prov_plot,
    x="proveedor",
    y="dias_max",
    color="dias_max",
    color_continuous_scale=["#5cb85c","#f0ad4e","#d9534f"],
    title="Proveedores con mayor atraso"
)

with c3:
    st.plotly_chart(fig, use_container_width=True)

# ======================================
# RESUMEN POR PROVEEDOR (CORREGIDO ✅)
# ======================================
st.subheader("Resumen por proveedor")

resumen = (
    df_view.groupby("proveedor")
    .agg(
        pedidos=("pedido", "nunique"),
        monto_total=("valor_pos", "sum"),
        dias_maximos=("dias_demora", "max")
    )
    .sort_values("dias_maximos", ascending=False)
)

st.dataframe(resumen, use_container_width=True)

# ======================================
# TABLA PRINCIPAL
# ======================================
st.markdown("### **Proveedores que ponen en riesgo el inventario**")

tabla = df_view[df_view["dias_demora"] > 0][[
    "pedido",
    "proveedor",
    "material",
    "grupo_articulo",
    "cantidad_pendiente",
    "dias_demora"
]].sort_values("dias_demora", ascending=False)

st.dataframe(tabla, use_container_width=True)
