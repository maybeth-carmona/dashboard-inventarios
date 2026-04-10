import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Compradores", layout="wide")
st.title("🧑‍💼 Seguimiento a Compradores – Atención de Solped")

HOY = pd.to_datetime(datetime.today().date())

# =====================================================
# CARGA ARCHIVO
# =====================================================
st.sidebar.header("📂 Archivo SAP")

file_sol = st.sidebar.file_uploader("Solicitudes de Pedido (Solped)", type=["xlsx"])

if file_sol is None:
    st.info("⬅️ Carga el archivo de Solped")
    st.stop()

sol = pd.read_excel(file_sol)

# =====================================================
# NORMALIZACIÓN DE COLUMNAS
# =====================================================
sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido",
    "Pedido de Compras": "pedido",
    "Grupo de compras": "grupo_compras",
    "Usuario Creador": "usuario",
    "Grupo artículos": "grupo_articulos",
    "Material": "material",
    "Texto Material": "material_desc",
    "Centro": "centro"
})

# -----------------------------------------------------
# Limpieza básica
# -----------------------------------------------------
sol["solped"] = sol["solped"].astype(str)
sol["pedido"] = sol["pedido"].astype(str).str.replace(".0", "", regex=False)

sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

# =====================================================
# CÁLCULOS
# =====================================================
sol["dias_desde_lib"] = (HOY - sol["fecha_lib"]).dt.days

# Asegurar que dias_desde_lib nunca sea NaN
sol["dias_desde_lib"] = sol["dias_desde_lib"].fillna(0).astype(int)

# días de atención solo si hay pedido
sol["dias_atencion"] = np.where(
    sol["pedido"].notna() & (sol["pedido"] != "") & (sol["pedido"] != "nan"),
    (sol["fecha_pedido"] - sol["fecha_lib"]).dt.days,
    np.nan
)

# =====================================================
# ESTATUS CON SEMÁFORO (CORREGIDO)
# =====================================================
def estatus_solped(row):
    # Ya atendidas
    if pd.notna(row["dias_atencion"]):
        return f"✅ ATENDIDA ({int(row['dias_atencion'])} días)"

    # No atendidas → semáforo por días
    d = row["dias_desde_lib"]

    if d > 100:
        return f"🔥 {d}"
    if d > 60:
        return f"🔴 {d}"
    if d > 20:
        return f"🟡 {d}"
    return f"🟢 {d}"

sol["estatus"] = sol.apply(estatus_solped, axis=1)

# =====================================================
# FILTROS (BARRA LATERAL)
# =====================================================
st.sidebar.subheader("🔍 Filtros")

for col in ["grupo_compras", "usuario", "grupo_articulos", "centro"]:
    sol[col] = sol[col].astype(str)

f_gc = st.sidebar.multiselect("Grupo de Compras", sorted(sol["grupo_compras"].unique()))
f_usr = st.sidebar.multiselect("Usuario Creador", sorted(sol["usuario"].unique()))
f_ga = st.sidebar.multiselect("Grupo de Artículos", sorted(sol["grupo_articulos"].unique()))
f_ct = st.sidebar.multiselect("Centro", sorted(sol["centro"].unique()))

df = sol.copy()
if f_gc:
    df = df[df["grupo_compras"].isin(f_gc)]
if f_usr:
    df = df[df["usuario"].isin(f_usr)]
if f_ga:
    df = df[df["grupo_articulos"].isin(f_ga)]
if f_ct:
    df = df[df["centro"].isin(f_ct)]

# =====================================================
# 📊 GRÁFICA – DESEMPEÑO POR GRUPO DE COMPRAS
# =====================================================
st.subheader("📊 Desempeño por Grupo de Compras")

graf = (
    df[pd.notna(df["dias_atencion"])]
    .groupby("grupo_compras", as_index=False)
    .agg(promedio_dias=("dias_atencion", "mean"))
)

fig = px.bar(
    graf,
    x="grupo_compras",
    y="promedio_dias",
    color="promedio_dias",
    color_continuous_scale=["green", "yellow", "red"],
    title="Promedio de días para atender solicitudes"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# 📋 TABLA – ANÁLISIS DE ATENCIÓN
# =====================================================
st.subheader("📋 Análisis de Atención a Solicitudes")

# Orden: no atendidas arriba, más demoradas primero
df["orden_atendida"] = df["dias_atencion"].apply(lambda x: 1 if pd.notna(x) else 0)

df = df.sort_values(
    by=["orden_atendida", "dias_desde_lib"],
    ascending=[True, False]
)

st.dataframe(
    df[
        [
            "solped",
            "fecha_lib",
            "grupo_compras",
            "usuario",
            "grupo_articulos",
            "material",
            "material_desc",
            "centro",
            "pedido",
            "fecha_pedido",
            "dias_atencion",
            "estatus"
        ]
    ],
    use_container_width=True
)
