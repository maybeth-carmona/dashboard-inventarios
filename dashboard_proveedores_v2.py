import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Detalle de posiciones en riesgo")

HOY = pd.to_datetime(datetime.today().date())

file = st.file_uploader("Estatus de pedidos de compra", type=["xlsx"])
if file is None:
    st.stop()

df_raw = pd.read_excel(file)

# --- Renombrar columnas base ---
rename_map = {
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
    "Valor Neto de la Pos": "valor_pos",
}

df = df_raw.rename(columns=rename_map)

# --- Proveedor unificado (NO excluir nada) ---
if "Proveedor TEXT" in df_raw.columns and "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = df_raw["Proveedor"].astype(str)
elif "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

# --- Tipos ---
df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce")
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

# --- Cantidad entregada visible ---
df["cantidad_entregada_visible"] = df[["cantidad_entregada", "cantidad_pedida"]].min(axis=1)

# --- Días de demora (NO excluir filas) ---
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days
df["dias_demora"] = df["dias_demora"].fillna(0).astype(int)
df.loc[df["dias_demora"] < 0, "dias_demora"] = 0

# --- Estatus como Excel (semáforo + número) ---
def estatus(d):
    if d > 60:
        return "🔴 " + str(d)
    if d > 30:
        return "🟡 " + str(d)
    return "🟢 " + str(d)

df["estatus"] = df["dias_demora"].apply(estatus)

# ============================
# FILTROS TIPO EXCEL (NO OCULTOS)
# ============================
st.sidebar.header("Filtros")

f_prov = st.sidebar.multiselect(
    "Proveedor",
    sorted(df["proveedor"].unique()),
    default=sorted(df["proveedor"].unique())
)

f_ped = st.sidebar.multiselect(
    "Pedido",
    sorted(df["pedido"].astype(str).unique())
)

f_mat = st.sidebar.multiselect(
    "Material",
    sorted(df["material"].astype(str).unique())
)

f_grp = st.sidebar.multiselect(
    "Grupo de artículos",
    sorted(df["grupo"].astype(str).unique())
)

f_cen = st.sidebar.multiselect(
    "Centro",
    sorted(df["centro"].astype(str).unique())
)

solo_pendientes = st.sidebar.checkbox("Mostrar solo posiciones pendientes")

df_view = df.copy()

if f_prov:
    df_view = df_view[df_view["proveedor"].isin(f_prov)]
if f_ped:
    df_view = df_view[df_view["pedido"].astype(str).isin(f_ped)]
if f_mat:
    df_view = df_view[df_view["material"].astype(str).isin(f_mat)]
if f_grp:
    df_view = df_view[df_view["grupo"].astype(str).isin(f_grp)]
if f_cen:
    df_view = df_view[df_view["centro"].astype(str).isin(f_cen)]

if solo_pendientes:
    df_view = df_view[df_view["cantidad_entregada_visible"] < df_view["cantidad_pedida"]]

# ============================
# TABLA FINAL (ESTILO EXCEL)
# ============================
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
            "valor_pos",
            "dias_demora",
            "estatus",
        ]
    ].sort_values("dias_demora", ascending=False),
    use_container_width=True
)
