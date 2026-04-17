import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Seguimiento a Proveedores – Compras")

HOY = pd.to_datetime(datetime.today().date())

file_ped = st.file_uploader("Estatus de pedidos de compra", type=["xlsx"])
if file_ped is None:
    st.stop()

df_raw = pd.read_excel(file_ped)

df = df_raw.rename(columns={
    "Pedido de Compras": "pedido",
    "Material": "material",
    "Texto Breve Posicion": "descripcion",
    "Grupo artículos": "grupo",
    "Centro": "centro",
    "Fecha de Entrega": "fecha_entrega",
    "Cantidad de Mat en U": "cantidad_pedida",
    "Cantidad Entregada": "cantidad_entregada",
    "Valor Neto de la Pos": "valor_pos"
})

# Unificar proveedor
if "Proveedor TEXT" in df_raw.columns and "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor TEXT"].fillna("").astype(str)
    df.loc[df["proveedor"].str.strip() == "", "proveedor"] = df_raw["Proveedor"].astype(str)
elif "Proveedor" in df_raw.columns:
    df["proveedor"] = df_raw["Proveedor"].astype(str)
else:
    df["proveedor"] = "SIN_PROVEEDOR"

df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce")
df["cantidad_pedida"] = pd.to_numeric(df["cantidad_pedida"], errors="coerce").fillna(0)
df["cantidad_entregada"] = pd.to_numeric(df["cantidad_entregada"], errors="coerce").fillna(0)
df["valor_pos"] = pd.to_numeric(df["valor_pos"], errors="coerce").fillna(0)

df["cantidad_entregada_visible"] = df[["cantidad_entregada","cantidad_pedida"]].min(axis=1)
df["dias_demora"] = (HOY - df["fecha_entrega"]).dt.days.fillna(0).astype(int)

def estatus(row):
    if row["cantidad_entregada_visible"] < row["cantidad_pedida"]:
        if row["dias_demora"] > 60:
            return "🔴"
        if row["dias_demora"] > 30:
            return "🟡"
        return "🟢"
    return "✅"

df["estatus"] = df.apply(estatus, axis=1)

st.dataframe(df, use_container_width=True)
