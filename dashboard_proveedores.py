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
# CARGA DE ARCHIVO
# =====================================================
st.sidebar.header("Archivo SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
if file_ped is None:
    st.stop()

ped = pd.read_excel(file_ped)

# =====================================================
# RENOMBRE DE COLUMNAS (SAP REAL)
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
    "Valor Neto de la Pos": "valor_pos"  # AF1
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

# Cantidad entregada visible (no mayor a pedida)
ped["cantidad_entregada_visible"] = ped[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# SOLO POSICIONES PENDIENTES (OPTIMIZA Y ES REALIDAD)
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
st.sidebar.subheader("Filtros")

prov_opts = sorted(ped["proveedor"].dropna().unique().tolist())
grp_opts = sorted(ped["grupo"].dropna().unique().tolist())
cen_opts = sorted(ped["centro"].dropna().unique().tolist())

f_prov = st.sidebar.multiselect("Proveedor", prov_opts, default=prov_opts)
f_grp = st.sidebar.multiselect("Grupo artículos", grp_opts, default=grp_opts)
f_cen = st.sidebar.multiselect("Centro", cen_opts, default=cen_opts)

df = ped[
    ped["proveedor"].isin(f_prov) &
    ped["grupo"].isin(f_grp) &
    ped["centro"].isin(f_cen)
].copy()

# =====================================================
# KPIs GRANDES Y COLOREADOS (COMO LA IMAGEN)
# =====================================================
kpi_pedidos = df["pedido"].nunique()
kpi_atraso = df[df["dias_demora"] > 0]["pedido"].nunique()
kpi_monto = df["valor_pos"].sum()

k1, k2, k3 = st.columns(3)

k1.markdown(
    f"""
    <div style="background:#E74C3C;padding:20px;border-radius:12px;text-align:center;color:white">
        <h2>{kpi_pedidos}</h2>
        <p>Pedidos en riesgo</p>
    </div>
    """,
    unsafe_allow_html=True
)

k2.markdown(
    f"""
    <div style="background:#F39C12;padding:20px;border-radius:12px;text-align:center;color:white">
        <h2>{kpi_atraso}</h2>
        <p>Pedidos con atraso</p>
    </div>
    """,
    unsafe_allow_html=True
)

k3.markdown(
    f"""
    <div style="background:#F7DC6F;padding:20px;border-radius:12px;text-align:center;color:black">
        <h2>${kpi_monto:,.0f}</h2>
        <p>Monto en riesgo</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# =====================================================
# GRÁFICA DE PROVEEDORES EN RIESGO (DEGRADADO)
# =====================================================
prov_plot = (
    df.groupby("proveedor", as_index=False)
      .agg(atraso_promedio=("dias_demora", "mean"))
      .sort_values("atraso_promedio", ascending=False)
      .head(10)
)

fig = px.bar(
    prov_plot,
    x="proveedor",
    y="atraso_promedio",
    color="atraso_promedio",
    color_continuous_scale=["#70AD47", "#FFC000", "#C00000"],
    title="Top proveedores que ponen en riesgo los niveles de inventario"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLA RESUMEN VISUAL POR PROVEEDOR
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
# TABLA DETALLE FINAL (OPERATIVA)
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
