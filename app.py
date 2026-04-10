import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA ARCHIVOS
# =====================================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES (YA CORRECTO)
# =====================================================
st.header("🚚 Seguimiento a Proveedores")

ped = ped.rename(columns={
    "Pedido de Compras": "pedido",
    "Proveedor TEXT": "proveedor",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha Creación Pedido": "fecha_pedido",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad Entregada": "cantidad_entregada"
})

ped["pedido"] = ped["pedido"].astype(str)
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date

ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)

col_cant = st.sidebar.selectbox("📦 Columna cantidad pedida", ped.columns.tolist())
ped["cantidad_pedida"] = pd.to_numeric(ped[col_cant], errors="coerce").fillna(0)

resumen = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        pedida_total=("cantidad_pedida", "sum"),
        entregada_total=("cantidad_entregada", "sum"),
    )
)

resumen["pendiente"] = (resumen["pedida_total"] - resumen["entregada_total"]).clip(lower=0)
resumen["tiene_mr"] = resumen["entregada_total"] > 0
resumen["dias_demora"] = (
    (HOY - pd.to_datetime(resumen["fecha_entrega"]))
    .dt.days.fillna(0).clip(lower=0)
)

ped = ped.merge(
    resumen[["pedido", "pendiente", "tiene_mr", "dias_demora"]],
    on="pedido",
    how="left"
)

def estatus_proveedor(row):
    if row["tiene_mr"]:
        return "✅ Entregado"
    if row["dias_demora"] > 60:
        return f"🔴 {int(row['dias_demora'])}"
    if row["dias_demora"] > 30:
        return f"🟡 {int(row['dias_demora'])}"
    return f"🟢 {int(row['dias_demora'])}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

dfp = ped[~ped["tiene_mr"]].copy()

top10 = (
    dfp.groupby("proveedor", as_index=False)
    .agg(promedio=("dias_demora", "mean"))
    .sort_values("promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="📊 Proveedores con pedidos pendientes",
    color_discrete_sequence=["#BABD13"]
)
st.plotly_chart(fig1, use_container_width=True)

# =====================================================
# 🧑‍💼 SEGUIMIENTO A COMPRADORES (BIEN HECHO)
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Usuario Creador": "usuario",
    "Grupo de compras": "grupo_compras",
    "Pedido de Compras": "pedido",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["solped"] = sol["solped"].astype(str)
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)
sol["pedido"] = sol["pedido"].replace("nan", "SIN TRATAMIENTO")

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

# días desde liberación
sol["dias_desde_lib"] = (HOY - sol["fecha_lib"]).dt.days

# días de atención
sol["dias_atencion"] = np.where(
    sol["pedido"] != "SIN TRATAMIENTO",
    (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
    np.nan
)

def estatus_comprador(row):
    if row["pedido"] != "SIN TRATAMIENTO":
        return "✅ ATENDIDO"
    if row["dias_desde_lib"] <= 20:
        return f"🟢 {row['dias_desde_lib']}"
    if row["dias_desde_lib"] <= 30:
        return f"🟡 {row['dias_desde_lib']}"
    return f"🔴 {row['dias_desde_lib']}"

sol["estatus"] = sol.apply(estatus_comprador, axis=1)

# filtro por grupo de compras
st.subheader("🔍 Filtro Grupo de Compras")
sol["grupo_compras"] = sol["grupo_compras"].astype(str)
f_gc = st.multiselect(
    "Grupo de compras",
    sorted(sol["grupo_compras"].unique())
)

df_sol = sol.copy()
if f_gc:
    df_sol = df_sol[df_sol["grupo_compras"].isin(f_gc)]

st.dataframe(
    df_sol[
        [
            "solped",
            "usuario",
            "grupo_compras",
            "fecha_lib",
            "pedido",
            "fecha_pedido",
            "dias_atencion",
            "estatus"
        ]
    ],
    use_container_width=True
)

# gráfica compradores
fig2 = px.bar(
    df_sol[df_sol["pedido"] != "SIN TRATAMIENTO"]
    .groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean")),
    x="grupo_compras",
    y="promedio",
    title="⏱️ Tiempo promedio de atención por grupo de compras",
    color_discrete_sequence=["#0096A9"]
)

st.plotly_chart(fig2, use_container_width=True)
