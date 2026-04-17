import streamlit as st
import pandas as pd
from datetime import datetime

# =====================================================
# CONFIG GENERAL
# =====================================================
st.set_page_config(layout="wide")
st.title("Detalle de posiciones en riesgo")

HOY = pd.to_datetime(datetime.today().date())

file = st.file_uploader("Estatus de pedidos de compra", type=["xlsx"])
if file is None:
    st.stop()

df_raw = pd.read_excel(file)

# =====================================================
# RENOMBRE DE COLUMNAS
# =====================================================
rename_map = {
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
}

df = df_raw.rename(columns=rename_map)

# =====================================================
# FECHA DE ENTREGA — UNIFICADA (CLAVE 🔴)
# =====================================================
if "Fecha de Entrega" in df_raw.columns:
    df["fecha_entrega"] = pd.to_datetime(df_raw["Fecha de Entrega"], errors="coerce")
elif "Fecha Entrega" in df_raw.columns:
    df["fecha_entrega"] = pd.to_datetime(df_raw["Fecha Entrega"], errors="coerce")
else:
    df["fecha_entrega"] = pd.NaT

# =====================================================
# PROVEEDOR UNIFICADO
# =====================================================
if "Proveedor TEXT" in df_raw.columns and "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = df_raw["Proveedor"].astype(str)
elif "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# =====================================================
# TIPOS NUMÉRICOS
# =====================================================
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)

# =====================================================
# CANTIDAD ENTREGADA VISIBLE (CORRECTA)
# =====================================================
df["cantidad_entregada_visible"] = df[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# =====================================================
# DÍAS DE DEMORA (SIN EXCLUIR FILAS)
# =====================================================
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days
df["dias_demora"] = df["dias_demora"].fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

# =====================================================
# ESTATUS VISUAL (SEMÁFORO + NÚMERO)
# =====================================================
def estatus(d):
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

df["estatus"] = df["dias_demora"].apply(estatus)

# =====================================================
# FILTROS TIPO EXCEL (ELIMINAN FILAS)
# =====================================================
st.sidebar.header("Filtros")

f_prov = st.sidebar.multiselect(
    "Proveedor",
    sorted(df["proveedor"].unique()),
    default=sorted(df["proveedor"].unique())
)

f_mat = st.sidebar.multiselect(
    "Material",
    sorted(df["material"].astype(str).unique())
)

f_ped = st.sidebar.multiselect(
    "Pedido",
    sorted(df["pedido"].astype(str).unique())
)

solo_pendientes = st.sidebar.checkbox("Mostrar solo posiciones pendientes")

mask = df["proveedor"].isin(f_prov)

if f_mat:
    mask &= df["material"].astype(str).isin(f_mat)

if f_ped:
    mask &= df["pedido"].astype(str).isin(f_ped)

if solo_pendientes:
    mask &= df["cantidad_entregada_visible"] < df["cantidad_pedida"]

df_view = df.loc[mask].copy()

# =====================================================
# TABLA FINAL (COMO EXCEL)
# =====================================================
st.dataframe(
    df_view[
        [
            "pedido",
            "proveedor",
            "material",
            "descripcion",
            "grupo",
            "centro",
            "cantidad_pedida",
            "cantidad_entregada_visible",
            "dias_demora",
            "estatus",
        ]
    ].sort_values("dias_demora", ascending=False),
    use_container_width=True
)
``
