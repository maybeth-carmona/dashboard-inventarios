import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
st.set_page_config(
    page_title="Seguimiento a Proveedores | Compras",
    layout="wide"
)

st.title("Seguimiento a Proveedores – Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA ARCHIVO
# =====================================================
st.sidebar.header("📂 Archivo SAP")

file_ped = st.sidebar.file_uploader(
    "Estatus de pedidos de compra",
    type=["xlsx"]
)

if file_ped is None:
    st.stop()

df_raw = pd.read_excel(file_ped)

# =====================================================
# RENOMBRE DE COLUMNAS SAP
# =====================================================
df = df_raw.rename(columns={
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
    "Valor Neto de la Pos": "valor_pos"
})

# =====================================================
# UNIFICAR PROVEEDOR (SAP TRAE DOS CAMPOS)
# =====================================================
if "Proveedor TEXT" in df_raw.columns and "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = df_raw["Proveedor"].astype(str)
elif "Proveedor TEXT" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].astype(str)
elif "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# =====================================================
# LIMPIEZA BÁSICA (SIN ELIMINAR FILAS)
# =====================================================
df["pedido"] = df["pedido"].astype(str)
df["material"] = df["material"].astype(str)
df["proveedor"] = df["proveedor"].astype(str)
df["grupo"] = df["grupo"].astype(str)
df["centro"] = df["centro"].astype(str)

df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce")

df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

df["cantidad_entregada_visible"] = df[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# CÁLCULO DE DEMORA Y ESTATUS
# =====================================================
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

def estatus(row):
    if row["cantidad_entregada_visible"] < row["cantidad_pedida"]:
        if row["dias_demora"] > 60:
            return f"🔴 {int(row['dias_demora'])}"
        if row["dias_demora"] > 30:
            return f"🟡 {int(row['dias_demora'])}"
        return f"🟢 {int(row['dias_demora'])}"
    return "✅ Entregado"

df["estatus"] = df.apply(estatus, axis=1)

# =====================================================
# CONTROLES TIPO EXCEL
# =====================================================
st.sidebar.subheader("🔍 Filtros")

f_prov = st.sidebar.multiselect(
    "Proveedor",
    sorted(df["proveedor"].unique()),
    default=sorted(df["proveedor"].unique())
)

f_ped = st.sidebar.multiselect(
    "Pedido",
    sorted(df["pedido"].unique())
)

f_mat = st.sidebar.multiselect(
    "Material",
    sorted(df["material"].unique())
)

f_grp = st.sidebar.multiselect(
    "Grupo de artículos",
    sorted(df["grupo"].unique())
)

f_cen = st.sidebar.multiselect(
    "Centro",
    sorted(df["centro"].unique())
)

# Checkbox estilo Excel
solo_pendientes = st.checkbox("Mostrar SOLO posiciones pendientes")

df_f = df.copy()

if f_prov:
    df_f = df_f[df_f["proveedor"].isin(f_prov)]
if f_ped:
    df_f = df_f[df_f["pedido"].isin(f_ped)]
if f_mat:
    df_f = df_f[df_f["material"].isin(f_mat)]
if f_grp:
    df_f = df_f[df_f["grupo"].isin(f_grp)]
if f_cen:
    df_f = df_f[df_f["centro"].isin(f_cen)]

if solo_pendientes:
    df_f = df_f[df_f["cantidad_entregada_visible"] < df_f["cantidad_pedida"]]

# =====================================================
# KPIs
# =====================================================
c1, c2, c3 = st.columns(3)

c1.metric("Pedidos totales", df_f["pedido"].nunique())
c2.metric("Posiciones pendientes", (df_f["cantidad_entregada_visible"] < df_f["cantidad_pedida"]).sum())
c3.metric("Monto total", f"${df_f['valor_pos'].sum():,.0f}")

st.markdown("---")

# =====================================================
# GRÁFICA DE PROVEEDORES (SIEMPRE CON TODO)
# =====================================================
graf = (
    df_f.groupby("proveedor", as_index=False)
        .agg(atraso_promedio=("dias_demora", "mean"))
        .sort_values("atraso_promedio", ascending=False)
        .head(10)
)

fig = px.bar(
    graf,
    x="proveedor",
    y="atraso_promedio",
    color="atraso_promedio",
    color_continuous_scale=["#70AD47", "#FFC000", "#C00000"],
    title="Proveedores con mayor atraso promedio"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLA DETALLE (TODO, COMO EN EXCEL)
# =====================================================
st.subheader("Detalle de pedidos y posiciones")

st.dataframe(
    df_f.sort_values("dias_demora", ascending=False),
    use_container_width=True
)
