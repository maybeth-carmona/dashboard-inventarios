import streamlit as st
import pandas as pd
from datetime import datetime
import io
import plotly.express as px

# ======================================
# CONFIGURACION GENERAL
# ======================================
st.set_page_config(layout="wide")
st.title("Seguimiento a Proveedores – Posiciones en Riesgo")

HOY = pd.to_datetime(datetime.today().date())

# ======================================
# CARGA DEL EXCEL RAW
# ======================================
file = st.file_uploader("Estatus de pedidos de compra (RAW)", type=["xlsx"])
if file is None:
    st.stop()

raw = pd.read_excel(file)

# ======================================
# RENOMBRE DE COLUMNAS BASE
# ======================================
df = raw.rename(columns={
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo_articulo",
    "Grupo de compras": "grupo_compra",
    "Centro": "centro",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada"
})

# ======================================
# FECHA DE ENTREGA
# ======================================
if "Fecha de Entrega" in raw.columns:
    df["fecha_entrega"] = pd.to_datetime(raw["Fecha de Entrega"], errors="coerce")
elif "Fecha Entrega" in raw.columns:
    df["fecha_entrega"] = pd.to_datetime(raw["Fecha Entrega"], errors="coerce")
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
# NUMERICOS
# ======================================
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["cantidad_entregada_visible"] = df[["cantidad_entregada","cantidad_pedida"]].min(axis=1)

# ======================================
# DIAS DE DEMORA
# ======================================
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days
df["dias_demora"] = df["dias_demora"].fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

# ======================================
# ESTATUS
# ======================================
def estatus(d):
    if d > 60:
        return "ROJO"
    if d > 30:
        return "AMARILLO"
    return "VERDE"

df["estatus"] = df["dias_demora"].apply(estatus)

# ======================================
# FILTROS
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

f_mat = st.sidebar.multiselect(
    "Material",
    sorted(df["material"].astype(str).unique())
)

f_ped = st.sidebar.multiselect(
    "Pedido",
    sorted(df["pedido"].astype(str).unique())
)

solo_pendientes = st.sidebar.checkbox("Solo pendientes")

mask = df["proveedor"].isin(f_prov)
if f_gc:
    mask &= df["grupo_compra"].astype(str).isin(f_gc)
if f_ga:
    mask &= df["grupo_articulo"].astype(str).isin(f_ga)
if f_mat:
    mask &= df["material"].astype(str).isin(f_mat)
if f_ped:
    mask &= df["pedido"].astype(str).isin(f_ped)
if solo_pendientes:
    mask &= df["cantidad_entregada_visible"] < df["cantidad_pedida"]

df_view = df.loc[mask].copy()

# ======================================
# KPIs
# ======================================
c1, c2, c3 = st.columns(3)

c1.metric("Pedidos visibles", df_view["pedido"].nunique())
c2.metric("Posiciones pendientes", (df_view["cantidad_entregada_visible"] < df_view["cantidad_pedida"]).sum())
c3.metric("Días promedio de demora", round(df_view["dias_demora"].mean(), 1))

st.markdown("---")

# ======================================
# GRAFICA PROVEEDORES
# ======================================
graf = (
    df_view.groupby("proveedor", as_index=False)
    .agg(dias_promedio=("dias_demora","mean"))
    .sort_values("dias_promedio", ascending=False)
    .head(10)
)

fig = px.bar(
    graf,
    x="proveedor",
    y="dias_promedio",
    title="Top proveedores con mayor demora promedio"
)

st.plotly_chart(fig, use_container_width=True)

# ======================================
# TABLA RESUMEN POR PROVEEDOR
# ======================================
st.subheader("Resumen por proveedor")

resumen = (
    df_view.groupby("proveedor")
    .agg(
        pedidos=("pedido","nunique"),
        posiciones=("material","count"),
        dias_promedio=("dias_demora","mean"),
        dias_max=("dias_demora","max"),
        pendiente_total=("cantidad_pedida","sum")
    )
    .sort_values("dias_promedio", ascending=False)
)

st.dataframe(resumen)

# ======================================
# EXPORTAR A EXCEL
# ======================================
st.subheader("Detalle de posiciones en riesgo")

output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df_view.to_excel(writer, index=False)

st.download_button(
    "Descargar Excel",
    data=output.getvalue(),
    file_name="posiciones_riesgo.xlsx"
)

st.dataframe(
    df_view[
        [
            "pedido","proveedor","grupo_compra","grupo_articulo",
            "material","descripcion","centro",
            "cantidad_pedida","cantidad_entregada_visible",
            "dias_demora","estatus"
        ]
    ].sort_values("dias_demora", ascending=False),
    use_container_width=True
)
