import streamlit as st
import pandas as pd
from datetime import datetime

# ======================================
# CONFIGURACION GENERAL
# ======================================
st.set_page_config(layout="wide")
st.title("Detalle de posiciones en riesgo")

HOY = pd.to_datetime(datetime.today().date())

# ======================================
# CARGA DEL ARCHIVO RAW
# ======================================
file = st.file_uploader("Estatus de pedidos de compra", type=["xlsx"])
if file is None:
    st.stop()

raw = pd.read_excel(file)

# ======================================
# RENOMBRE DE COLUMNAS BASE
# ======================================
df = raw.rename(columns={
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada"
})

# ======================================
# FECHA DE ENTREGA UNIFICADA
# ======================================
if "Fecha de Entrega" in raw.columns:
    df["fecha_entrega"] = pd.to_datetime(raw["Fecha de Entrega"], errors="coerce")
elif "Fecha Entrega" in raw.columns:
    df["fecha_entrega"] = pd.to_datetime(raw["Fecha Entrega"], errors="coerce")
else:
    df["fecha_entrega"] = pd.NaT

# ======================================
# PROVEEDOR UNIFICADO
# ======================================
if "Proveedor TEXT" in raw.columns and "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = raw["Proveedor"].astype(str)
elif "Proveedor" in raw.columns:
    df["proveedor"] = raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# ======================================
# TIPOS NUMERICOS
# ======================================
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)

# ======================================
# CANTIDAD ENTREGADA VISIBLE
# ======================================
df["cantidad_entregada_visible"] = df[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# ======================================
# DIAS DE DEMORA
# ======================================
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days
df["dias_demora"] = df["dias_demora"].fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

# ======================================
# ESTATUS CON EMOJIS (UNICODE SEGURO)
# ======================================
EMOJI_ROJO = "\U0001F534"
EMOJI_AMARILLO = "\U0001F7E1"
EMOJI_VERDE = "\U0001F7E2"

def estatus(d):
    if d > 60:
        return EMOJI_ROJO + " " + str(d)
    if d > 30:
        return EMOJI_AMARILLO + " " + str(d)
    return EMOJI_VERDE + " " + str(d)

df["estatus"] = df["dias_demora"].apply(estatus)

# ======================================
# FILTROS TIPO EXCEL
# ======================================
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

df_view = df.loc[mask]

# ======================================
# TABLA FINAL ESTILO EXCEL
# ======================================
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
            "estatus"
        ]
    ].sort_values("dias_demora", ascending=False),
    use_container_width=True
)
