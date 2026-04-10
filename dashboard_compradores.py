import streamlit as st
import pandas as pd
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(page_title="Dashboard Compradores", layout="wide")
st.title("🧑‍💼 Seguimiento a Compradores – Solped")

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
    "Grupo de compras": "grupo_compras",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["solped"] = sol["solped"].astype(str)
sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

# =====================================================
# CÁLCULOS
# =====================================================
sol["dias_desde_lib"] = (HOY - sol["fecha_lib"]).dt.days

sol["dias_atencion"] = (
    sol["fecha_pedido"] - sol["fecha_lib"]
).dt.days

def estatus_comprador(row):
    if pd.notna(row["dias_atencion"]):
        return f"✅ ATENDIDO ({int(row['dias_atencion'])} días)"
    if row["dias_desde_lib"] <= 20:
        return f"🟢 {row['dias_desde_lib']}"
    if row["dias_desde_lib"] <= 30:
        return f"🟡 {row['dias_desde_lib']}"
    return f"🔴 {row['dias_desde_lib']}"

sol["estatus"] = sol.apply(estatus_comprador, axis=1)

# =====================================================
# FILTROS
# =====================================================
st.sidebar.subheader("🔍 Filtros")

sol["grupo_compras"] = sol["grupo_compras"].astype(str)
f_grp = st.sidebar.multiselect(
    "Grupo de Compras",
    sorted(sol["grupo_compras"].unique())
)

df = sol.copy()
if f_grp:
    df = df[df["grupo_compras"].isin(f_grp)]

# =====================================================
# TABLA FINAL
# =====================================================
st.subheader("📋 Detalle de Solicitudes")

df = df.sort_values(
    by=["fecha_pedido", "dias_desde_lib"],
    ascending=[True, False]
)

st.dataframe(
    df[
        [
            "solped",
            "grupo_compras",
            "fecha_lib",
            "fecha_pedido",
            "estatus"
        ]
    ],
    use_container_width=True
)
