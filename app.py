import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# 📂 CARGA DE ARCHIVOS
# =====================================================
st.sidebar.header("📂 Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES
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

# ❌ eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# fechas limpias
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date

ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

# cantidad solicitada
st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)

ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# 🔑 AGREGACIÓN POR PEDIDO (PARA ESTATUS Y KPIs)
# =====================================================
resumen_pedido = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        grupo=("grupo", "first"),
        centro=("centro", "first"),
        fecha_pedido=("fecha_pedido", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        cantidad_pedida_total=("cantidad_pedida", "sum"),
        cantidad_entregada_total=("cantidad_entregada", "sum"),
    )
)

resumen_pedido["cantidad_pendiente_pedido"] = (
    resumen_pedido["cantidad_pedida_total"]
    - resumen_pedido["cantidad_entregada_total"]
)
resumen_pedido.loc[
    resumen_pedido["cantidad_pendiente_pedido"] < 0,
    "cantidad_pendiente_pedido"
] = 0

# ✅ UN PEDIDO SOLO ES ENTREGADO SI YA NO FALTA NADA
resumen_pedido["entregado_pedido"] = (
    resumen_pedido["cantidad_pendiente_pedido"] == 0
)

# demora contra FECHA COMPROMISO
resumen_pedido["dias_demora"] = (
    (pd.to_datetime(HOY) - pd.to_datetime(resumen_pedido["fecha_entrega"]))
    .dt.days
)
resumen_pedido["dias_demora"] = resumen_pedido["dias_demora"].fillna(0)
resumen_pedido.loc[
    resumen_pedido["dias_demora"] < 0,
    "dias_demora"
] = 0
resumen_pedido["dias_demora"] = resumen_pedido["dias_demora"].astype(int)

# regresar datos al detalle
ped = ped.merge(
    resumen_pedido[
        [
            "pedido",
            "cantidad_pendiente_pedido",
            "entregado_pedido",
            "dias_demora",
        ]
    ],
    on="pedido",
    how="left"
)

def estatus_proveedor(row):
    if row["entregado_pedido"]:
        return "✅ Entregado"
    if row["dias_demora"] > 60:
        return f"🔴 {row['dias_demora']}"
    if row["dias_demora"] > 30:
        return f"🟡 {row['dias_demora']}"
    return f"🟢 {row['dias_demora']}"

ped["estatus"] = ped.apply(estatus_proveedor, axis=1)

# =====================================================
# KPIs (POR PEDIDO)
# =====================================================
pedidos_pendientes = resumen_pedido[
    resumen_pedido["cantidad_pendiente_pedido"] > 0
].shape[0]

pedidos_con_demora = resumen_pedido[
    (resumen_pedido["cantidad_pendiente_pedido"] > 0)
    & (resumen_pedido["dias_demora"] > 0)
].shape[0]

col1, col2 = st.columns(2)
col1.metric("📦 Pedidos con pendiente", pedidos_pendientes)
col2.metric("⏰ Pedidos con demora", pedidos_con_demora)

# =====================================================
# TOP 10 PROVEEDORES EN RIESGO
# =====================================================
top10 = (
    resumen_pedido[resumen_pedido["cantidad_pendiente_pedido"] > 0]
    .groupby("proveedor", as_index=False)
    .agg(dias_promedio=("dias_demora", "mean"))
    .sort_values("dias_promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="dias_promedio",
    title="🚨 TOP PROVEEDORES QUE PONEN EN RIESGO EL INVENTARIO",
    labels={"dias_promedio": "Días de demora"},
)
st.plotly_chart(fig1, use_container_width=True)

# ordenar detalle (pendientes arriba, entregados abajo)
ped = ped.sort_values(
    by=["entregado_pedido", "dias_demora"],
    ascending=[True, False]
)

st.dataframe(
    ped[
        [
            "pedido",
            "proveedor",
            "material",
            "descripcion",
            "grupo",
            "centro",
            "fecha_pedido",
            "fecha_entrega",
            "cantidad_pedida",
            "cantidad_entregada",
            "cantidad_pendiente_pedido",
            "estatus",
        ]
    ],
    use_container_width=True
)

# =====================================================
# 🧑‍💼 SEGUIMIENTO A COMPRADORES
# =====================================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Pedido de Compras": "pedido",
    "Grupo de compras": "grupo_compras",
    "Centro": "centro",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido",
})

sol["solped"] = sol["solped"].astype(str)

# limpiar pedido (.0 y nan)
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)
sol["pedido"] = sol["pedido"].replace("nan", "SIN TRATAMIENTO")

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

# demora sin pedido
sol["dias_demora"] = np.where(
    sol["pedido"] == "SIN TRATAMIENTO",
    (HOY - sol["fecha_lib"]).dt.days,
    np.nan,
)

# días reales de atención
sol["dias_atencion"] = np.where(
    sol["pedido"] != "SIN TRATAMIENTO",
    (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
    np.nan,
)

def estatus_comprador(d):
    if pd.isna(d):
        return ""
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

sol["estatus"] = sol["dias_demora"].apply(estatus_comprador)

# ordenar: sin tratamiento arriba
sol = sol.sort_values(
    by=["pedido", "dias_demora"],
    ascending=[True, False]
)

st.dataframe(
    sol[
        [
            "solped",
            "pedido",
            "grupo_compras",
            "centro",
            "fecha_lib",
            "fecha_pedido",
            "estatus",
            "dias_atencion",
        ]
    ],
    use_container_width=True
)
