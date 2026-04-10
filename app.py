# =====================================================
# 🚚 SEGUIMIENTO A PROVEEDORES (CORRECTO)
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

st.sidebar.subheader("📦 Cantidad solicitada (Pedidos)")
col_cant = st.sidebar.selectbox(
    "Columna de cantidad pedida",
    ped.columns.tolist()
)
ped["cantidad_pedida"] = pd.to_numeric(
    ped[col_cant], errors="coerce"
).fillna(0)

# ===== AGREGACIÓN POR PEDIDO =====
resumen_pedido = (
    ped.groupby("pedido", as_index=False)
    .agg(
        proveedor=("proveedor", "first"),
        grupo=("grupo", "first"),
        centro=("centro", "first"),
        fecha_entrega=("fecha_entrega", "first"),
        cant_pedida=("cantidad_pedida", "sum"),
        cant_entregada=("cantidad_entregada", "sum")
    )
)

resumen_pedido["pendiente_pedido"] = (
    resumen_pedido["cant_pedida"]
    - resumen_pedido["cant_entregada"]
).clip(lower=0)

resumen_pedido["dias_demora"] = (
    (HOY - pd.to_datetime(resumen_pedido["fecha_entrega"]))
    .dt.days
    .fillna(0)
    .clip(lower=0)
    .astype("Int64")
)

# 👉 SOLO PENDIENTES
resumen_pedido = resumen_pedido[
    resumen_pedido["pendiente_pedido"] > 0
].copy()

# regresar al detalle
ped = ped.merge(
    resumen_pedido[
        ["pedido", "pendiente_pedido", "dias_demora"]
    ],
    on="pedido",
    how="inner"   # 👈 esto elimina ENTREGADOS
)

def semaforo_prov(row):
    d = row["dias_demora"]
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

ped["estatus"] = ped.apply(semaforo_prov, axis=1)

# ===== FILTROS =====
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

# ===== KPIs (SOLO PENDIENTES) =====
kpi_pend = dfp["pedido"].nunique()
kpi_dem = dfp[dfp["dias_demora"] > 0]["pedido"].nunique()

c1, c2 = st.columns(2)
c1.metric("📦 Pedidos con pendiente", kpi_pend)
c2.metric("⏰ Pedidos con demora", kpi_dem)

# ===== GRÁFICA (RESPONDE A FILTROS) =====
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
    title="📊 Top proveedores que ponen en riesgo el inventario",
    color_discrete_sequence=["#0096A9"]  # azul relajado
)

st.plotly_chart(fig1, use_container_width=True)

# ===== TABLA FINAL =====
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
