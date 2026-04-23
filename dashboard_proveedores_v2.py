import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# ======================================
# CONFIGURACIÓN GENERAL
# ======================================
st.set_page_config(layout="wide")
st.markdown("## Riesgo en Compras | Seguimiento a Proveedores")

HOY = pd.to_datetime(datetime.today().date())

# ======================================
# CARGA DEL RAW
# ======================================
file = st.file_uploader("Estatus de pedidos de compra (RAW SAP)", type=["xlsx"])
if file is None:
    st.stop()

raw = pd.read_excel(file)

# ======================================
# RENOMBRE DE COLUMNAS BASE
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

# ======================================
# FECHA DE CREACIÓN (ROBUSTO ✅)
# ======================================
fecha_creacion_col = None
for col in raw.columns:
    if "fecha" in col.lower() and (
        "crea" in col.lower()
        or "doc" in col.lower()
        or "pedido" in col.lower()
    ):
        fecha_creacion_col = col
        break

if fecha_creacion_col:
    df["fecha_creacion"] = pd.to_datetime(raw[fecha_creacion_col], errors="coerce")
else:
    df["fecha_creacion"] = pd.NaT

# ======================================
# FECHA DE ENTREGA
# ======================================
fecha_entrega_col = None
for col in raw.columns:
    if "fecha" in col.lower() and "entreg" in col.lower():
        fecha_entrega_col = col
        break

if fecha_entrega_col:
    df["fecha_entrega"] = pd.to_datetime(raw[fecha_entrega_col], errors="coerce").dt.date
else:
    df["fecha_entrega"] = pd.NaT

# ======================================
# PROVEEDOR
# ======================================
if "Proveedor TEXT" in raw.columns and "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = raw["Proveedor"].astype(str)
elif "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# ======================================
# NUMÉRICOS
# ======================================
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

# ======================================
# CÁLCULOS CLAVE
# ======================================
df["cantidad_pendiente"] = (df["cantidad_pedida"] - df["cantidad_entregada"]).clip(lower=0)

df["dias_demora"] = (HOY - pd.to_datetime(df["fecha_entrega"])).dt.days
df["dias_demora"] = df["dias_demora"].fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

def semaforo(d):
    if d > 60:
        return "🔴 " + str(d)
    if d > 30:
        return "🟡 " + str(d)
    return "🟢 " + str(d)

df["semaforo"] = df["dias_demora"].apply(semaforo)

# ======================================
# FILTROS
# ======================================
st.sidebar.header("Filtros")

f_prov = st.sidebar.multiselect("Proveedor", sorted(df["proveedor"].unique()))
f_gc = st.sidebar.multiselect("Grupo de compras", sorted(df["grupo_compra"].dropna().astype(str).unique()))
f_ga = st.sidebar.multiselect("Grupo de artículos", sorted(df["grupo_articulo"].dropna().astype(str).unique()))
f_cen = st.sidebar.multiselect("Centro", sorted(df["centro"].dropna().astype(str).unique()))

mask = pd.Series(True, index=df.index)
if f_prov: mask &= df["proveedor"].isin(f_prov)
if f_gc: mask &= df["grupo_compra"].astype(str).isin(f_gc)
if f_ga: mask &= df["grupo_articulo"].astype(str).isin(f_ga)
if f_cen: mask &= df["centro"].astype(str).isin(f_cen)

df_view = df[mask].copy()

# ======================================
# KPIs
# ======================================
k1, k2 = st.columns(2)
k1.metric("Pedidos en riesgo", df_view[df_view["dias_demora"] > 30]["pedido"].nunique())
k2.metric("Pedidos con atraso", df_view[df_view["dias_demora"] > 0]["pedido"].nunique())

st.markdown("---")

# ======================================
# GRÁFICA PROVEEDORES
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
    title="Proveedores que ponen en riesgo el inventario",
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

resumen["semaforo"] = resumen["dias_maximos"].apply(semaforo)
st.dataframe(resumen, use_container_width=True)

# ======================================
# DETALLE FINAL
# ======================================
st.subheader("Detalle de pedidos pendientes")

detalle = df_view[df_view["cantidad_pendiente"] > 0][
    [
        "pedido",
        "proveedor",
        "material_sap",
        "material_desc",
        "grupo_articulo",
        "cantidad_entregada",
        "cantidad_pendiente",
        "semaforo",
        "fecha_creacion",
        "fecha_entrega",
        "centro"
    ]
].sort_values("dias_demora", ascending=False)

st.dataframe(detalle, use_container_width=True)
