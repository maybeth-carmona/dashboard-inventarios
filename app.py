import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# =========================================
# CONFIGURACIÓN
# =========================================
st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =========================================
# CARGA ARCHIVOS
# =========================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =====================================================
# 🚚 PROVEEDORES (RESTAURADO - NO SE TOCA MÁS)
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

ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

col_cant = st.sidebar.selectbox(
    "📦 Columna cantidad pedida",
    ped.columns.tolist()
)
ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

resumen = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        pedida=("cantidad_pedida", "sum"),
        entregada=("cantidad_entregada", "sum")
    )
)

resumen["pendiente"] = (resumen["pedida"] - resumen["entregada"]).clip(lower=0)
resumen["tiene_mr"] = resumen["entregada"] > 0
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
        return f"🔴 {row['dias_demora']}"
    if row["dias_demora"] > 30:
        return f"🟡 {row['dias_demora']}"
    return f"🟢 {row['dias_demora']}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

dfp = ped.copy()

top10 = (
    dfp[~dfp["tiene_mr"]]
    .groupby("proveedor", as_index=False)
    .agg(promedio=("dias_demora", "mean"))
    .sort_values("promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="📊 Proveedores con pedidos pendientes",
    color_discrete_sequence=["#BABD13"]  # RGB(186,187,19)
)
st.plotly_chart(fig1, use_container_width=True)

st.dataframe(dfp, use_container_width=True)

# =====================================================
# 🧑‍💼 COMPRADORES (AHORA SÍ INTERPRETABLE)
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Grupo de compras": "grupo_compras",
    "Pedido de Compras": "pedido",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["solped"] = sol["solped"].astype(str)
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

sol["dias_desde_lib"] = (HOY - sol["fecha_lib"]).dt.days

sol["dias_atencion"] = np.where(
    sol["pedido"].notna() & (sol["pedido"] != ""),
    (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
    np.nan
)

def estatus_comprador(row):
    if pd.notna(row["dias_atencion"]):
        return f"✅ ATENDIDO ({int(row['dias_atencion'])} días)"
    if row["dias_desde_lib"] <= 20:
        return f"🟢 {row['dias_desde_lib']}"
    if row["dias_desde_lib"] <= 30:
        return f"🟡 {row['dias_desde_lib']}"
    return f"🔴 {row['dias_desde_lib']}"

sol["estatus"] = sol.apply(estatus_comprador, axis=1)

st.dataframe(
    sol[
        [
            "solped",
            "grupo_compras",
            "fecha_lib",
            "pedido",
            "fecha_pedido",
            "estatus"
        ]
    ],
    use_container_width=True
)
