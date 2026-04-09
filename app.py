import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(page_title="Dashboard Riesgo de Inventarios", layout="wide")

st.title("📊 Dashboard de Riesgo de Inventarios")
st.caption("Pedidos y órdenes de entrega – atraso y pendiente REAL")

# ======================================================
# CARGA DE ARCHIVO
# ======================================================
st.sidebar.header("📂 Carga de archivos SAP")

file_pedidos = st.sidebar.file_uploader(
    "Sube raw_estatus_pedidos_compras.xlsx",
    type=["xlsx"]
)

if not file_pedidos:
    st.warning("⬅️ Sube el archivo para iniciar el análisis")
    st.stop()

# ======================================================
# LECTURA
# ======================================================
pedidos = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN SAP
# ======================================================
pedidos = pedidos.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor': 'num_proveedor',
    'Proveedor TEXT': 'nombre_proveedor',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'cantidad_entregada',
    'Cantidad (Ejercido)': 'cantidad_pedida'
})

# ======================================================
# FECHAS
# ======================================================
pedidos['fecha_pedido'] = pd.to_datetime(pedidos['fecha_pedido'], errors='coerce')
pedidos = pedidos[pedidos['fecha_pedido'].notna()].copy()

# ======================================================
# ELIMINAR CONVENIOS
# ======================================================
pedidos['pedido'] = pedidos['pedido'].astype(str)
pedidos = pedidos[~pedidos['pedido'].str.startswith(('256', '266'))]

# ======================================================
# LIMPIEZA DE CANTIDADES
# ======================================================
pedidos['cantidad_pedida'] = pd.to_numeric(pedidos['cantidad_pedida'], errors='coerce').fillna(0)
pedidos['cantidad_entregada'] = pd.to_numeric(pedidos['cantidad_entregada'], errors='coerce').fillna(0)

base = pedidos.copy()

# ======================================================
# MR CORRECTO (HAY ENTREGA SI ENTREGADA > 0)
# ======================================================
base['entregado'] = base['cantidad_entregada'] > 0

# ======================================================
# ✅ CANTIDAD PENDIENTE REAL (AJUSTE FINAL)
# ======================================================
base['cantidad_pendiente'] = (
    base['cantidad_pedida'] - base['cantidad_entregada']
).clip(lower=0)

# ======================================================
# DÍAS DE ATRASO
# ======================================================
fecha_hoy = pd.to_datetime(datetime.today().date())

base['dias_atraso'] = np.where(
    base['entregado'],
    0,
    (fecha_hoy - base['fecha_pedido']).dt.days
)

base['dias_atraso'] = base['dias_atraso'].clip(lower=0).astype("Int64")

# ======================================================
# SEMÁFORO + DÍAS
# ======================================================
def estatus_atraso(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return "✅ Entregado"
    d = row['dias_atraso']
    if d > 60:
        return f"🔴 {d}"
    elif d > 30:
        return f"🟡 {d}"
    else:
        return f"🟢 {d}"

base['estatus_atraso'] = base.apply(estatus_atraso, axis=1)

# ======================================================
# PRIORIDAD
# ======================================================
def prioridad(row):
    if row['entregado'] and row['cantidad_pendiente'] == 0:
        return 4
    if row['dias_atraso'] > 60:
        return 1
    if row['dias_atraso'] > 30:
        return 2
    return 3

base['orden_prioridad'] = base.apply(prioridad, axis=1)

# ======================================================
# FILTROS
# ======================================================
base['grupo_articulos'] = base['grupo_articulos'].astype(str)
base['centro'] = base['centro'].astype(str)
base['nombre_proveedor'] = base['nombre_proveedor'].astype(str)

st.sidebar.header("🎛️ Filtros")

grupo_sel = st.sidebar.multiselect("Grupo de artículos", sorted(base['grupo_articulos'].unique()))
centro_sel = st.sidebar.multiselect("Centro", sorted(base['centro'].unique()))
proveedor_sel = st.sidebar.multiselect("Proveedor", sorted(base['nombre_proveedor'].unique()))

df = base.copy()
if grupo_sel:
    df = df[df['grupo_articulos'].isin(grupo_sel)]
if centro_sel:
    df = df[df['centro'].isin(centro_sel)]
if proveedor_sel:
    df = df[df['nombre_proveedor'].isin(proveedor_sel)]

# ======================================================
# KPIs
# ======================================================
df_no_entregados = df[df['cantidad_pendiente'] > 0]

col1, col2 = st.columns(2)
col1.metric("Pedidos en seguimiento", len(df_no_entregados))
col2.metric("Pedidos críticos (>60 días)", len(df_no_entregados[df_no_entregados['dias_atraso'] > 60]))

# ======================================================
# TABLAS
# ======================================================
columnas_tabla = [
    'pedido',
    'num_proveedor',
    'nombre_proveedor',
    'material_sap',
    'descripcion_material',
    'grupo_articulos',
    'centro',
    'cantidad_pendiente',
    'estatus_atraso'
