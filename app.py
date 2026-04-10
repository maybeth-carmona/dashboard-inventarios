import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Dashboard Compras – Versión Estable")

HOY = pd.to_datetime(datetime.today().date())

# =========================
# CARGA DE ARCHIVOS
# =========================
file_ped = st.file_uploader("Pedidos de Compras", type=["xlsx"])
file_sol = st.file_uploader("Solpeds", type=["xlsx"])

if file_ped is None or file_sol is None:
    st.stop()

ped = pd.read_excel(file_ped)
sol = pd.read_excel(file_sol)

# =========================
# PROVEEDORES
# =========================
st.header("Seguimiento a Proveedores")

ped = ped.rename(columns={
    "Pedido de Compras": "pedido",
    "Proveedor TEXT": "proveedor",
    "Fecha Creación Pedido": "fecha_pedido",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad Entregada": "entregada"
})

ped["pedido"] = ped["pedido"].astype(str)

# eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce")
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce")

ped = ped[ped["fecha_pedido"].notna()].copy()

ped["entregada"] = pd.to_numeric(ped["entregada"], errors="coerce").fillna(0)
ped["entregado"] = ped["entregada"] > 0

ped["dias_demora"] = (
    HOY - ped["fecha_entrega"]
).dt.days.fillna(0).clip(lower=0)

st.dataframe(
    ped[["pedido", "proveedor", "fecha_pedido", "fecha_entrega", "dias_demora"]],
    use_container_width=True
)

# =========================
# COMPRADORES
# =========================
st.header("Seguimiento a Compradores")

sol = sol.rename(columns={
    "Número de Solped": "solped",
    "Pedido de Compras": "pedido",
    "Fecha Liberación Solped": "fecha_lib",
    "Fecha Creación Pedido": "fecha_pedido"
})

sol["pedido"] = sol["pedido"].astype(str).replace("nan", "SIN TRATAMIENTO")
sol["fecha_lib"] = pd.to_datetime(sol["fecha_lib"], errors="coerce")
sol["fecha_pedido"] = pd.to_datetime(sol["fecha_pedido"], errors="coerce")

sol["dias_demora"] = np.where(
    sol["pedido"] == "SIN TRATAMIENTO",
    (HOY - sol["fecha_lib"]).dt.days,
    np.nan
)

st.dataframe(
    sol[["solped", "pedido", "fecha_lib", "fecha_pedido", "dias_demora"]],
    use_container_width=True
)
``
