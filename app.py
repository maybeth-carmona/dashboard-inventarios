# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES (CORREGIDO DEFINITIVO)
# =====================================================
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
    "Cantidad Entregada": "cantidad_entregada"
})

ped["pedido"] = ped["pedido"].astype(str)

# ❌ eliminar convenios
ped = ped[~ped["pedido"].str.startswith(("256", "266"))].copy()

# fechas SIN hora
ped["fecha_pedido"] = pd.to_datetime(ped["fecha_pedido"], errors="coerce").dt.date
ped = ped[ped["fecha_pedido"].notna()].copy()
ped["fecha_entrega"] = pd.to_datetime(ped["fecha_entrega"], errors="coerce").dt.date

# cantidades
ped["cantidad_entregada"] = pd.to_numeric(
    ped["cantidad_entregada"], errors="coerce"
).fillna(0)

st.sidebar.subheader("📦 Cantidad solicitada")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)
ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# =====================================================
# 🔑 RESUMEN REAL POR PEDIDO
# =====================================================
resumen = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        grupo=("grupo", "first"),
        centro=("centro", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        cantidad_pedida_total=("cantidad_pedida", "sum"),
        cantidad_entregada_total=("cantidad_entregada", "sum")
    )
)

# ✅ Pendiente correcta
resumen["pendiente_pedido"] = (
    resumen["cantidad_pedida_total"]
    - resumen["cantidad_entregada_total"]
).clip(lower=0)

# ✅ CRITERIO OPERATIVO QUE PIDES:
# Si hay MR → entregado
resumen["tiene_mr"] = resumen["cantidad_entregada_total"] > 0

# ✅ DÍAS DE DEMORA (solo si NO tiene MR)
resumen["dias_demora"] = (
    (HOY - pd.to_datetime(resumen["fecha_entrega"]))
    .dt.days
    .fillna(0)
    .clip(lower=0)
)

# =====================================================
# 🔴 SOLO PEDIDOS SIN MR PARA DEMORAS
# =====================================================
resumen_abiertos = resumen[~resumen["tiene_mr"]].copy()

# volver al detalle SOLO abiertos
ped = ped.merge(
    resumen_abiertos[
        ["pedido", "pendiente_pedido", "dias_demora"]
    ],
    on="pedido",
    how="inner"
)

def semaforo_proveedor(d):
    if d > 60:
        return f"🔴 {int(d)}"
    if d > 30:
        return f"🟡 {int(d)}"
    return f"🟢 {int(d)}"

ped["estatus"] = ped["dias_demora"].apply(semaforo_proveedor)

# =====================================================
# 🔍 FILTROS
# =====================================================
st.subheader("🔍 Filtros Proveedores")

ped["proveedor"] = ped["proveedor"].astype(str)
ped["grupo"] = ped["grupo"].astype(str)
ped["centro"] = ped["centro"].astype(str)

f_prov = st.multiselect("Proveedor", sorted(ped["proveedor"].unique()))
f_grp = st.multiselect("Grupo de artículos", sorted(ped["grupo"].unique()))
f_cen = st.multiselect("Centro", sorted(ped["centro"].unique()))

dfp = ped.copy()
if f_prov:
    dfp = dfp[dfp["proveedor"].isin(f_prov)]
if f_grp:
    dfp = dfp[dfp["grupo"].isin(f_grp)]
if f_cen:
    dfp = dfp[dfp["centro"].isin(f_cen)]

# =====================================================
# KPIs CORRECTOS
# =====================================================
kpi_pend = dfp["pedido"].nunique()
kpi_dem = dfp[dfp["dias_demora"] > 0]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos SIN MR", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# =====================================================
# 📊 GRÁFICA (COLOR PEDIDO EXACTO)
# =====================================================
top10 = (
    dfp.groupby("proveedor", as_index=False)
    .agg(promedio=("dias_demora", "mean"))
    .sort_values("promedio", ascending=False)
    .head(10)
)

fig1 = px.bar(
    top10,
    x="proveedor",
    y="promedio",
    title="📊 Pedidos pendientes por proveedor",
    color_discrete_sequence=["#99D9D9"]
)

st.plotly_chart(fig1, use_container_width=True)

# =====================================================
# 📋 TABLA FINAL
# =====================================================
dfp = dfp.sort_values("dias_demora", ascending=False)

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
            "cantidad_pedida",
            "cantidad_entregada",
            "pendiente_pedido",
            "estatus"
        ]
    ],
    use_container_width=True
)
