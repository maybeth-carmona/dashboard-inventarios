import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIGURACIÓN GENERAL
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
st.sidebar.header("Archivo SAP")
file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
if file_ped is None:
    st.stop()

df_raw = pd.read_excel(file_ped)

# =====================================================
# RENOMBRE DE COLUMNAS (SIN PROVEEDOR)
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
# UNIFICAR PROVEEDOR (SAP REAL)
# =====================================================
if "Proveedor TEXT" in df_raw.columns and "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = df_raw["Proveedor"].astype(str)
elif "Proveedor TEXT" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].astype(str)
elif "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# =====================================================
# LIMPIEZA BASE
# =====================================================
df["pedido"] = df["pedido"].astype(str)
df["proveedor"] = df["proveedor"].astype(str)
df["grupo"] = df["grupo"].astype(str)
df["centro"] = df["centro"].astype(str)

# Quitar convenios
df = df[~df["pedido"].str.startswith(("256", "266"))].copy()

df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce")
df = df[df["fecha_entrega"].notna()].copy()

df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

# Cantidad entregada visible
df["cantidad_entregada_visible"] = df[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# SOLO POSICIONES PENDIENTES
# =====================================================
df = df[df["cantidad_entregada_visible"] < df["cantidad_pedida"]].copy()

# =====================================================
# DEMORA Y SEMÁFORO
# =====================================================
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

def semaforo(d):
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

df["estatus"] = df["dias_demora"].apply(semaforo)

# =====================================================
# FILTROS TIPO EXCEL
# =====================================================
st.sidebar.subheader("Filtros")

prov_opts = sorted(df["proveedor"].dropna().unique().tolist())
grp_opts = sorted(df["grupo"].dropna().unique().tolist())
cen_opts = sorted(df["centro"].dropna().unique().tolist())

f_prov = st.sidebar.multiselect("Proveedor", prov_opts, default=prov_opts)
f_grp = st.sidebar.multiselect("Grupo artículos", grp_opts, default=grp_opts)
f_cen = st.sidebar.multiselect("Centro", cen_opts, default=cen_opts)

df = df[
    df["proveedor"].isin(f_prov) &
    df["grupo"].isin(f_grp) &
    df["centro"].isin(f_cen)
].copy()

# =====================================================
# KPIs VISUALES (COLOREADOS)
# =====================================================
kpi_pedidos = df["pedido"].nunique()
kpi_atraso = df[df["dias_demora"] > 0]["pedido"].nunique()
kpi_monto = df["valor_pos"].sum()

k1, k2, k3 = st.columns(3)

k1.markdown(
    f"<div style='background:#E74C3C;padding:20px;border-radius:12px;color:white;text-align:center'>"
    f"<h2>{kpi_pedidos}</h2><p>Pedidos en riesgo</p></div>",
    unsafe_allow_html=True
)

k2.markdown(
    f"<div style='background:#F39C12;padding:20px;border-radius:12px;color:white;text-align:center'>"
    f"<h2>{kpi_atraso}</h2><p>Pedidos con atraso</p></div>",
    unsafe_allow_html=True
)

k3.markdown(
    f"<div style='background:#F7DC6F;padding:20px;border-radius:12px;color:black;text-align:center'>"
    f"<h2>${kpi_monto:,.0f}</h2><p>Monto en riesgo</p></div>",
    unsafe_allow_html=True
)

st.markdown("---")

# =====================================================
# GRÁFICA DE RIESGO (DEGRADADO)
# =====================================================
graf = (
    df.groupby("proveedor", as_index=False)
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
    tabla_resumen
        .style
        .bar(subset=["atraso_promedio"], color="#E74C3C")
        .format({
            "atraso_promedio": "{:.1f}",
            "monto_riesgo": "${:,.0f}"
        }),
    use_container_width=True
)

# =====================================================
# TABLA DETALLE FINAL
# =====================================================
st.subheader("Detalle de posiciones en riesgo")

st.dataframe(
    df.sort_values("dias_demora", ascending=False)[
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
