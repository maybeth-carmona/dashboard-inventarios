import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
st.set_page_config(
    page_title="Dashboard Riesgo de Inventarios",
    layout="wide"
)

st.title("📊 Dashboard de Riesgo de Inventarios")
st.caption("Días EXACTOS de demora por proveedor (cálculo automático diario)")

# ======================================================
# CARGA DE ARCHIVOS
# ======================================================
st.sidebar.header("📂 Carga de archivos SAP")

file_solped = st.sidebar.file_uploader(
    "Sube raw_estatus_sol_pedidos.xlsx",
    type=["xlsx"]
)

file_pedidos = st.sidebar.file_uploader(
    "Sube raw_estatus_pedidos_compras.xlsx",
    type=["xlsx"]
)

if not file_solped or not file_pedidos:
    st.warning("⬅️ Sube ambos archivos para iniciar el análisis")
    st.stop()

# ======================================================
# LECTURA DE EXCELES
# ======================================================
solped = pd.read_excel(file_solped)
pedidos = pd.read_excel(file_pedidos)

# ======================================================
# NORMALIZACIÓN DE COLUMNAS (SAP)
# ======================================================
pedidos = pedidos.rename(columns={
    'Pedido de Compras': 'pedido',
    'Material': 'material_sap',
    'Texto Breve Posicion': 'descripcion_material',
    'Grupo artículos': 'grupo_articulos',
    'Centro': 'centro',
    'Proveedor': 'num_proveedor',            # número proveedor
    'Proveedor TEXT': 'nombre_proveedor',    # nombre proveedor
    'Fecha de Entrega': 'fecha_entrega',
    'Fecha Creación Pedido': 'fecha_pedido',
    'Cantidad Entregada': 'cantidad_entregada',
    'Cantidad (Ejercido)': 'cantidad_pedida',
    'Número de Solped': 'solped',
    'Partida de la Solped': 'partida'
})

solped = solped.rename(columns={
    'Número de Solped': 'solped',
    'Partida de la Solped': 'partida',
    'Fecha Liberación Solped': 'fecha_lib_solped'
})

# ======================================================
# MERGE SOLPED – PEDIDO
# ======================================================
base = pedidos.merge(
    solped[['solped', 'partida', 'fecha_lib_solped']],
    on=['solped', 'partida'],
    how='left'
)

# ======================================================
# CONVERSIÓN DE FECHAS
# ======================================================
for c in ['fecha_entrega', 'fecha_pedido', 'fecha_lib_solped']:
    base[c] = pd.to_datetime(base[c], errors='coerce')

# ======================================================
# LIMPIEZA Y CÁLCULOS (DÍAS EXACTOS, SIN REDONDEAR)
# ======================================================
base['cantidad_entregada'] = base['cantidad_entregada'].fillna(0)
base['cantidad_pendiente'] = base['cantidad_pedida'] - base['cantidad_entregada']
base = base[base['cantidad_pendiente'] > 0]

# ❗ Eliminar registros sin fecha de entrega (no se puede calcular atraso)
# Si no hay fecha de entrega, usamos fecha de pedido como referencia temporal
base['fecha_entrega'] = base['fecha_entrega'].fillna(base['fecha_pedido'])


fecha_hoy = pd.to_datetime(datetime.today().date())

# DÍAS EXACTOS DE ATRASO (ENTEROS NATURALES)
base['dias_atraso'] = (fecha_hoy - base['fecha_entrega']).dt.days
base['dias_atraso'] = base['dias_atraso'].clip(lower=0)

# ======================================================
# RANGO DE ATRASO (SOLO VISUAL)
# ======================================================
def rango_atraso(d):
    if d >= 61:
        return "+60 días"
    elif d >= 8:
        return "8–60 días"
    return "0–30 días"

base['rango_atraso'] = base['dias_atraso'].apply(rango_atraso)

# ======================================================
# FILTROS
# ======================================================
st.sidebar.header("🎛️ Filtros")

rango_sel = st.sidebar.multiselect(
    "Rango de días",
    options=base['rango_atraso'].unique(),
    default=base['rango_atraso'].unique()
)

grupo_sel = st.sidebar.multiselect(
    "Grupo de artículos",
    options=base['grupo_articulos'].dropna().unique()
)

df = base.copy()

if rango_sel:
    df = df[df['rango_atraso'].isin(rango_sel)]

if grupo_sel:
    df = df[df['grupo_articulos'].isin(grupo_sel)]

# ======================================================
# KPIs
# ======================================================
col1, col2 = st.columns(2)

col1.metric("Total pedidos con atraso", len(df))
col2.metric("Pedidos +60 días", len(df[df['rango_atraso'] == "+60 días"]))

# ======================================================
# TOP 10 PROVEEDORES (CORREGIDO)
# ======================================================
st.subheader("📈 Top 10 proveedores con mayor atraso")

top10 = (
    df.groupby(['num_proveedor', 'nombre_proveedor'], as_index=False)
    .agg(
        dias_promedio=('dias_atraso', 'mean'),
        pedidos=('pedido', 'nunique')
    )
    .sort_values(['dias_promedio', 'pedidos'], ascending=[False, False])
    .head(10)
)

if not top10.empty:
    fig = px.bar(
        top10,
        x='nombre_proveedor',
        y='dias_promedio',
        text='pedidos',
        title="Top 10 Proveedores – DÍAS EXACTOS de atraso promedio",
        labels={
            'nombre_proveedor': 'Proveedor',
            'dias_promedio': 'Días exactos de atraso',
            'pedidos': 'Cantidad de pedidos'
        }
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay datos suficientes para generar el Top 10.")

# ======================================================
# TABLAS LIMPIAS POR CENTRO
# ======================================================
columnas_tabla = [
    'pedido',
    'solped',
    'num_proveedor',
    'nombre_proveedor',
    'material_sap',
    'descripcion_material',
    'grupo_articulos',
    'centro',
    'cantidad_pendiente',
    'dias_atraso',
    'rango_atraso'
]

st.subheader("📋 Centros 1000 / 8000")
st.dataframe(
    df[df['centro'].isin([1000, 8000])]
        [columnas_tabla]
        .sort_values('dias_atraso', ascending=False),
    use_container_width=True
)

st.subheader("📋 Centros 2000 / 7000")
st.dataframe(
    df[df['centro'].isin([2000, 7000])]
        [columnas_tabla]
        .sort_values('dias_atraso', ascending=False),
    use_container_width=True
)
