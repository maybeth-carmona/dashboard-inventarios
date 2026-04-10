import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Dashboard Compras", layout="wide")
st.title("📊 Dashboard Operativo de Compras")

hoy = pd.to_datetime(datetime.today().date())

# =========================
# CARGA DE ARCHIVOS
# =========================
st.sidebar.header("Archivos SAP")

file_ped = st.sidebar.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =========================
# SEGUIMIENTO PROVEEDORES
# =========================
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
    "Cantidad Entregada": "entregada"
})

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce")
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce")
ped = ped[ped["fecha_pedido"].notna()].copy()

ped["entregada"] = pd.to_numeric(ped["entregada"], errors="coerce").fillna(0)

st.sidebar.subheader("Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox("Columna cantidad pedida", ped.columns.tolist())
ped["cantidad_pedida"] = pd.to_numeric(ped[col_cant], errors="coerce").fillna(0)

ped["pendiente"] = (ped["cantidad_pedida"] - ped["entregada"]).clip(lower=0)
ped["entregado"] = ped["entregada"] > 0

ped["dias_demora"] = pd.Series(
    np.where(
        ped["fecha_entrega"].notna(),
        (hoy - ped["fecha_entrega"]).dt.days,
        (hoy - ped["fecha_pedido"]).dt.days,
    ),
    index=ped.index,
).clip(lower=0).astype("Int64")

def sem_prov(row):
    if row["entregado"] and row["pendiente"] == 0:
        return "✅ Entregado"
    d = int(row["dias_demora"])
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped.apply(sem_prov, axis=1)

f_proveedor = st.multiselect("Proveedor", sorted(ped["proveedor"].dropna().unique()))
f_grupo = st.multiselect("Grupo artículos", sorted(ped["grupo"].dropna().unique()))
f_centro = st.multiselect("Centro", sorted(ped["centro"].dropna().unique()))

dfp = ped.copy()
if f_proveedor:
    dfp = dfp[dfp["proveedor"].isin(f_proveedor)]
if f_grupo:
    dfp = dfp[dfp["grupo"].isin(f_grupo)]
if f_centro:
    dfp = dfp[dfp["centro"].isin(f_centro)]

st.metric("Pedidos con pendiente", len(dfp[dfp["pendiente"] > 0]))

top_prov = (
    dfp[dfp["pendiente"] > 0]
    .groupby("proveedor", as_index=False)
    .agg(dias_promedio=("dias_demora", "mean"))
    .sort_values("dias_promedio", ascending=False)
)

st.plotly_chart(
    px.bar(top_prov, x="proveedor", y="dias_promedio", title="Demora por proveedor"),
    use_container_width=True,
)

dfp = dfp.sort_values(["entregado", "dias_demora"], ascending=[True, False])

st.dataframe(
    dfp[
        [
            "pedido",
            "proveedor",
            "material",
            "descripcion",
            "grupo",
            "centro",
            "fecha_pedido",
            "fecha_entrega",
            "pendiente",
            "estatus",
        ]
    ],
    use_container_width=True,
)

# =========================
# SEGUIMIENTO COMPRADORES
# =========================
st.header("🧑‍💼 Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Pedido de Compras": "pedido",
    "Grupo de compras": "grupo_compras",
    "Centro": "centro",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")
sol["pedido"] = sol["pedido"].fillna("SIN TRATAMIENTO")

sol["dias_sin_atender"] = pd.Series(
    np.where(
        sol["pedido"] == "SIN TRATAMIENTO",
        (hoy - sol["fecha_lib"]).dt.days,
        np.nan,
    ),
    index=sol.index,
)

sol["dias_atencion"] = pd.Series(
    np.where(
        sol["pedido"] != "SIN TRATAMIENTO",
        (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
        np.nan,
    ),
    index=sol.index,
)

def sem_comp(d):
    if pd.isna(d):
        return ""
    d = int(d)
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol["estatus"] = sol["dias_sin_atender"].apply(sem_comp)

sol = sol.sort_values(
    by=["pedido", "dias_sin_atender"], ascending=[True, False]
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
    use_container_width=True,
)

grp = (
    sol.dropna(subset=["dias_atencion"])
    .groupby("grupo_compras", as_index=False)
    .agg(promedio=("dias_atencion", "mean"))
    .sort_values("promedio")
)

st.plotly_chart(
    px.bar(grp, x="grupo_compras", y="promedio", title="Desempeño grupos de compra"),
    use_container_width=True,
)
