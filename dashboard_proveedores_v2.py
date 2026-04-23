import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# ===============================
# CONFIGURACIÓN GENERAL
# ===============================
st.set_page_config(layout="wide")
st.markdown("## Riesgo en Compras | Seguimiento a Proveedores")

HOY = pd.to_datetime(datetime.today().date())

# ===============================
# CARGA DEL RAW
# ===============================
file = st.file_uploader("Estatus de pedidos de compra (RAW SAP)", type=["xlsx"])
if file is None:
    st.stop()

raw = pd.read_excel(file)

# ===============================
# MAPEO BASE
# ===============================
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

# ===============================
# PROVEEDOR
# ===============================
if "Proveedor TEXT" in raw.columns and "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = raw["Proveedor"].astype(str)
elif "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# ===============================
# DETECCIÓN ROBUSTA DE FECHAS
# ===============================
def detectar_fecha(cols, palabras):
    for c in cols:
        c_low = c.lower()
        if all(p in c_low for p in palabras):
            return c
    return None

col_creacion = detectar_fecha(raw.columns, ["fecha", "crea"])
df["fecha_creacion"] = (
    pd.to_datetime(raw[col_creacion], errors="coerce") if col_creacion else pd.NaT
)

col_entrega = detectar_fecha(raw.columns, ["fecha", "entreg"])
df["fecha_entrega"] = (
    pd.to_datetime(raw[col_entrega], errors="coerce").dt.date if col_entrega else pd.NaT
)

# ===============================
# NUMÉRICOS
# ===============================
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

# ===============================
# CÁLCULOS CLAVE
# ===============================
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

# ===============================
# FILTROS
# ===============================
st.sidebar.header("Filtros")

f_prov = st.sidebar.multiselect("Proveedor", sorted(df["proveedor"].unique()))
f_gc = st.sidebar.multiselect("Grupo de compras", sorted(df["grupo_compra"].dropna().astype(str).unique()))
f_ga = st.sidebar.multiselect("Grupo de artículos", sorted(df["grupo_articulo"].dropna().astype(str).unique()))
f_cen = st.sidebar.multiselect("Centro", sorted(df["centro"].dropna().astype(str).unique()))

mask = pd.Series(True, index=df.index)
if f_prov:
    mask &= df["proveedor"].isin(f_prov)
if f_gc:
    mask &= df["grupo_compra"].astype(str).isin(f_gc)
if f_ga:
    mask &= df["grupo_articulo"].astype(str).isin(f_ga)
if f_cen:
    mask &= df["centro"].astype(str).isin(f_cen)

df_view = df.loc[mask].copy()

# ===============================
# KPIs (CUADROS)
# ===============================
k1, k2 = st.columns(2)
k1.metric("Pedidos en riesgo", df_view[df_view["dias_demora"] > 30]["pedido"].nunique())
k2.metric("Pedidos con atraso", df_view[df_view["dias_demora"] > 0]["pedido"].nunique())

st.markdown("---")

# ===============================
# GRÁFICA FINAL (SOLO ROJO Y AMARILLO)
# ===============================
df_riesgo = df_view[
    (df_view["cantidad_pendiente"] > 0) &
    (df_view["dias_demora"] > 30)
]

prov_plot = (
    df_riesgo.groupby("proveedor", as_index=False)
    .agg(dias_max=("dias_demora", "max"))
    .sort_values("dias_max", ascending=False)
)

fig = px.bar(
    prov_plot,
    x="proveedor",
    y="dias_max",
    color="dias_max",
    title="Proveedores que ponen en riesgo el inventario",
    color_continuous_scale=["#f0ad4e", "#d9534f"]
)

fig.update_layout(
    xaxis_title="proveedores",
    yaxis_title="Días máximos de atraso",
    showlegend=False
)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# RESUMEN POR PROVEEDOR
# ===============================
st.subheader("Resumen por proveedor")

resumen = (
    df_view[df_view["cantidad_pendiente"] > 0]
    .groupby(["proveedor", "moneda"], as_index=False)
    .agg(
        pedidos_pendientes=("pedido", "nunique"),
        monto_total=("valor_pos", "sum"),
        dias_maximos=("dias_demora", "max")
    )
    .sort_values("dias_maximos", ascending=False)
)

resumen["semaforo"] = resumen["dias_maximos"].apply(semaforo)
st.dataframe(resumen, use_container_width=True)

# ===============================
# DETALLE DE PEDIDOS PENDIENTES
# ===============================
st.subheader("Detalle de pedidos pendientes")

detalle = (
    df_view[df_view["cantidad_pendiente"] > 0]
    .sort_values("dias_demora", ascending=False)
    [
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
    ]
)

st.dataframe(detalle, use_container_width=True)
