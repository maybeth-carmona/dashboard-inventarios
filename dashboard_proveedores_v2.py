# =====================================================
# TABLA BASE: DETALLE DE POSICIONES EN RIESGO
# (NO EXCLUIR MATERIALES, PEDIDOS NI PROVEEDORES)
# =====================================================

df_tabla = df.copy()

# Cantidad entregada visible
df_tabla["cantidad_entregada_visible"] = df_tabla[
    ["cantidad_entregada", "cantidad_pedida"]
].min(axis=1)

# Días de demora (siempre visibles)
df_tabla["dias_demora"] = (HOY - df_tabla["fecha_entrega"]).dt.days
df_tabla["dias_demora"] = df_tabla["dias_demora"].fillna(0).astype(int)
df_tabla.loc[df_tabla["dias_demora"] < 0, "dias_demora"] = 0

# Estatus visual (semáforo + días)
def estatus_visual(d):
    if d > 60:
        return f"🔴 {d}"
    if d > 30:
        return f"🟡 {d}"
    return f"🟢 {d}"

df_tabla["estatus"] = df_tabla["dias_demora"].apply(estatus_visual)

st.subheader("Detalle de posiciones en riesgo")

st.dataframe(
    df_tabla[
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
``
