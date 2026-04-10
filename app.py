import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

HOY = pd.to_datetime(datetime.today().date())

# =========================================
# CARGA DE ARCHIVOS
# =========================================
st.sidebar.header("Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =========================================
# SEGUIMIENTO A PROVEEDORES
# =========================================
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

# ❌ Eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date
ped["cantidad_entregada"] = pd.to_numeric(ped["cantidad_entregada"], errors="coerce").fillna(0)

# Cantidad solicitada
st.sidebar.subheader("Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox("Columna de cantidad pedida", ped.columns.tolist())
ped["cantidad_pedida"] = pd.to_numeric(ped[col_cant], errors="coerce").fillna(0)

# MR real
ped["entregado"] = ped["cantidad_entregada"] > 0

# Cantidad pendiente
ped["pendiente"] = (ped["cantidad_pedida"] - ped["cantidad_entregada"]).clip(lower=0)

# ✅ Demora contra FECHA COMPROMISO
ped["dias_demora"] = (
    pd.to_datetime(HOY) - pd.to_datetime(ped["fecha_entrega"])
).dt.days.fillna(0).clip(lower=0).astype(int)

def semaforo_proveedor(row):
    if row["entregado"]:
        return "✅ Entregado"
    d = row["dias_demora"]
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped.apply(semaforo_proveedor, axis=1)

# Conteos por PEDIDO
pedidos_pendientes = ped[(ped["pendiente"] > 0) & (~ped["entregado"])]["pedido"].nunique()
pedidos_con_demora = ped[ped["dias_demora"] > 0]["pedido"].nunique()

st.metric("Pedidos con pendiente (SIN MR)", pedidos_pendientes)
st.metric("Pedidos con demora", pedidos_con_demora)

# TOP 10 PROVEEDORES QUE PONEN EN RIESGO EL INVENTARIO
top_prov = (
    ped[(ped["pendiente"] > 0) & (~ped["entregado"])]
    .groupby("proveedor", as_index=False)
    .agg(dias_promedio=("dias_demora", "mean"))
    .sort_values("dias_promedio", ascending=False)
    .head(10)
)

st.plotly_chart(
    px.bar(
        top_prov,
        x="proveedor",
        y="dias_promedio",
        title="TOP PROVEEDORES QUE PONEN EN RIESGO EL INVENTARIO",
        labels={"dias_promedio": "Días de demora"}
    ),
    use_container_width=True
)

# Orden p0
ped = ped.sort_values(by=["entregado", "dias_demora"], ascending=[True, False])

st.dataframe(
    ped[[
        "pedido", "proveedor", "material", "descripcion",
        "grupo", "centro",
        "fecha_pedido", "fecha_entrega",
        "pendiente", "estatus"
    ]],
    use_container_width=True
)

# =========================================
# SEGUIMIENTO A COMPRADORES
# =========================================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Pedido de Compras": "pedido",
    "Grupo de compras": "grupo_compras",
    "Centro": "centro",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["solped"] = sol["solped"].astype(str)
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)
sol["pedido"] = sol["pedido"].replace("nan", "SIN TRATAMIENTO")

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce").dt.date
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce").dt.date

# Días sin atender
sol["dias_demora"] = np.where(
    sol["pedido"] == "SIN TRATAMIENTO",
    (pd.to_datetime(HOY) - pd.to_datetime(sol["fecha_lib"])).dt.days,
    np.nan
)

# Días de atención real
sol["dias_atencion"] = np.where(
    sol["pedido"] != "SIN TRATAMIENTO",
    (pd.to_datetime(sol["fecha_pedido"]) - pd.to_datetime(sol["fecha_lib"])).dt.days,
    np.nan
)

def semaforo_comprador(d):
    if pd.isna(d):
        return ""
    d = int(d)
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol["estatus"] = sol["dias_demora"].apply(semaforo_comprador)

# Orden correcto
sol = sol.sort_values(by=["pedido", "dias_demora"], ascending=[True, False])

st.dataframe(
    sol[[
        "solped", "pedido", "grupo_compras", "centro",
        "fecha_lib", "fecha_pedido",
        "estatus", "dias_atencion"
    ]],
    use_container_width=True
)

# Gráfica compradores
st.subheader("📈 Desempeño por grupo de compras")

f_grupo_comp = st.multiselect(
    "Filtrar grupo de compras",
    sorted(sol["grupo_compras"].dropna().unique())
)

df_grp = sol.dropna(subset=["dias_atencion"])
if f_grupo_comp:
    df_grp = df_grp[df_grp["grupo_compras"].isin(f_grupo_comp)]

fig = px.bar(
    df_grp.groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean")),
    x="grupo_compras",
    y="promedio",
    color="promedio",
    color_continuous_scale=["green", "orange", "red"],
    title="Tiempo promedio para crear pedidos por grupo de compras"
)

st.plotly_chart(fig, use_container_width=True)
``
