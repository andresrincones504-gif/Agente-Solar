"""Mis aparatos: consumo estimado por aparato, los que más consumen y gestión del inventario."""

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import (
    api_delete,
    api_get,
    api_patch_detallado,
    api_post,
    get_catalogo_aparatos,
    get_current_user,
    is_authenticated,
)
from design import PALETTE, render_card, render_hero, render_section_header
from inventario import calcular_cambios, coincide
from ui import render_user_sidebar

st.set_page_config(page_title="Mis aparatos", layout="wide", initial_sidebar_state="expanded")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero.")
    st.stop()

COLOR_BARRA = PALETTE["brand"]          # una sola serie: el verde de la marca
COLOR_NO_IDENTIFICADO = "#4A5A63"       # neutro; siempre lleva nombre y valor visibles
TIPOS_APARATO = {
    "refrigeracion": "Refrigeración",
    "climatizacion": "Aire y ventilación",
    "iluminacion": "Iluminación",
    "cocina": "Cocina",
    "lavado": "Lavado y planchado",
    "entretenimiento": "Entretenimiento",
    "cuidado_personal": "Cuidado personal",
    "oficina": "Oficina y tecnología",
    "bombas_motores": "Bombas, motores y herramientas",
    "otro": "Otros (propios)",
    "no_identificado": "No identificado",
}

ss = st.session_state
ss.setdefault("aparatos_version", 0)


def _recargar(mensaje: str) -> None:
    ss["aparatos_msg"] = mensaje
    ss["aparatos_version"] += 1
    st.rerun()


def _cop(valor: float) -> str:
    return f"${valor:,.0f}"


# ---------------------------------------------------------------------------
# Empresa
# ---------------------------------------------------------------------------
user = get_current_user() or {}
empresas = api_get("/empresas/") or []
if not empresas:
    st.warning("No hay empresas disponibles.")
    st.stop()
if user.get("role") == "empresa" and user.get("empresa_id"):
    empresa_id = user["empresa_id"]
    empresa_sel = next((e for e in empresas if e["id"] == empresa_id), empresas[0])
else:
    opciones = {f"{e['nombre']} (ID:{e['id']})": e for e in empresas}
    seleccion = st.selectbox("Empresa", list(opciones.keys()))
    empresa_sel = opciones[seleccion]
    empresa_id = empresa_sel["id"]

tipo_entidad = empresa_sel.get("tipo_entidad") or ("hogar" if empresa_sel.get("tipo") == "hogar" else None)
es_hogar = tipo_entidad == "hogar"
aparatos = api_get(f"/empresas/{empresa_id}/aparatos") or []
stats = api_get(f"/empresas/{empresa_id}/aparatos/estadisticas")

if ss.get("aparatos_msg"):
    st.success(ss.pop("aparatos_msg"))

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
if stats and stats.get("base_calculo") == "factura":
    subtitulo = (
        f"Estimación ajustada a tu consumo real de los últimos 30 días "
        f"({stats['dias_con_datos']} días con datos)."
    )
else:
    subtitulo = (
        "Estimación con la potencia y las horas de uso de cada aparato. "
        "Registra tu factura en Consumo para ajustarla a tu gasto real."
    )
render_hero("Mis aparatos", subtitulo, icon="bolt", eyebrow=empresa_sel["nombre"], tone="brand")

if not aparatos:
    st.info(
        "Todavía no tienes aparatos registrados. Agrégalos abajo para ver cuánto consume cada uno "
        "y recibir alertas y consejos sobre tus propios equipos."
    )
else:
    filas = stats["aparatos"] if stats else []
    reales = [f for f in filas if f["aparato_id"] is not None]
    mayor = max(reales, key=lambda f: f["consumo_kwh_mes"]) if reales else None
    no_ident = next((f for f in filas if f["aparato_id"] is None), None)

    # Dos filas de dos: con cuatro en fila, los valores en pesos no caben en pantallas medianas
    fila_1, fila_2 = st.columns(2), st.columns(2)
    cards = [fila_1[0], fila_1[1], fila_2[0], fila_2[1]]
    with cards[0]:
        render_card(
            "Consumo al mes",
            value=f"{stats['consumo_total_kwh_mes']:,.0f} kWh",
            body=f"De {len(aparatos)} aparatos registrados" + (" y consumo no identificado." if no_ident else "."),
            icon="bolt", tone="info",
        )
    with cards[1]:
        render_card(
            "Costo al mes",
            value=_cop(stats["costo_total_cop_mes"]),
            body=f"Con tu tarifa de {_cop(stats['tarifa_kwh'])}/kWh.",
            icon="money", tone="warning",
        )
    with cards[2]:
        if mayor:
            render_card(
                "El que más consume",
                value=f"{mayor['porcentaje']:.0f}%",
                body=f"{mayor['nombre']}: {mayor['consumo_kwh_mes']:,.0f} kWh, {_cop(mayor['costo_cop_mes'])} al mes.",
                icon="alert", tone="danger" if mayor["porcentaje"] >= 40 else "success",
            )
    with cards[3]:
        if stats["base_calculo"] == "factura":
            render_card(
                "Base del cálculo",
                value="Tu factura",
                body=(
                    f"Tus aparatos explican {100 - no_ident['porcentaje']:.0f}% de lo que pagas."
                    if no_ident else "Tus aparatos explican todo tu consumo registrado."
                ),
                icon="report", tone="success",
            )
        else:
            render_card(
                "Base del cálculo",
                value="Valores típicos",
                body="Sin factura registrada, usamos potencia × horas de uso de cada aparato.",
                icon="report", tone="info",
            )

    # Avisos sobre el inventario (antes estaban en Alertas; ahora Alertas es solo del clima del municipio)
    for aviso in api_get(f"/empresas/{empresa_id}/aparatos/avisos") or []:
        render_card(
            aviso["titulo"],
            body=aviso["mensaje"],
            action=aviso.get("accion"),
            icon="chart" if aviso["tipo"] == "consumo_sobre_inventario" else "bolt",
            tone="warning",
        )

    # -----------------------------------------------------------------------
    # Gráfico: los que más consumen (una serie, barras horizontales ordenadas)
    # -----------------------------------------------------------------------
    render_section_header("Los que más consumen", "chart", "Consumo estimado al mes por aparato (kWh).")
    top = sorted(filas, key=lambda f: f["consumo_kwh_mes"], reverse=True)
    if no_ident:  # el no identificado va al final aunque sea el mayor: no es un aparato
        top = [f for f in top if f["aparato_id"] is not None][:9] + [no_ident]
    else:
        top = top[:10]
    nombres = [f"{f['nombre']} ×{f['cantidad']}" if f["cantidad"] > 1 else f["nombre"] for f in top]
    fig = go.Figure(
        go.Bar(
            x=[f["consumo_kwh_mes"] for f in top],
            y=nombres,
            orientation="h",
            width=0.6,
            marker=dict(
                color=[COLOR_NO_IDENTIFICADO if f["aparato_id"] is None else COLOR_BARRA for f in top],
                cornerradius=4,
            ),
            text=[f"{f['consumo_kwh_mes']:,.0f} kWh · {f['porcentaje']:.0f}%" for f in top],
            textposition="outside",
            textfont=dict(color=PALETTE["muted"], size=12),
            cliponaxis=False,
            customdata=[[_cop(f["costo_cop_mes"]), f["porcentaje"]] for f in top],
            hovertemplate="<b>%{y}</b><br>%{x:,.1f} kWh/mes · %{customdata[0]} · %{customdata[1]:.1f}% del total<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(220, 44 * len(top) + 40),
        margin=dict(l=10, r=110, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["text"]),
        yaxis=dict(autorange="reversed", showgrid=False, ticks="", tickfont=dict(color=PALETTE["text"], size=13)),
        xaxis=dict(showgrid=True, gridcolor=PALETTE["border"], zeroline=False, tickfont=dict(color=PALETTE["muted"]), title=None),
        showlegend=False,
        bargap=0.35,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if no_ident:
        st.caption(
            f"Consumo no identificado: {no_ident['consumo_kwh_mes']:,.0f} kWh al mes de tu factura que no explican los aparatos "
            "registrados. Puede ser un aparato que falta en tu lista o uno que usas más horas de las indicadas."
        )
    elif stats.get("factor_ajuste") and stats["factor_ajuste"] < 1:
        st.caption(
            f"Tus aparatos sumaban {stats['consumo_inventario_kwh_mes']:,.0f} kWh/mes, más de lo que registra tu factura; "
            "ajustamos todos en la misma proporción. Revisa las horas de uso para afinar la estimación."
        )

    with st.expander("Ver la tabla por aparato y por tipo"):
        tabla = pd.DataFrame(
            {
                "Aparato": [f["nombre"] for f in filas],
                "Cantidad": [f["cantidad"] for f in filas],
                "kWh/mes": [round(f["consumo_kwh_mes"], 1) for f in filas],
                "Costo/mes (COP)": [f["costo_cop_mes"] for f in filas],
                "% del total": [f["porcentaje"] for f in filas],
                "Dato": [{"usuario": "Tuyo", "catalogo": "Típico", "factura": "Factura"}.get(f["origen_dato"], f["origen_dato"]) for f in filas],
            }
        )
        st.dataframe(
            tabla, hide_index=True, use_container_width=True,
            column_config={"Costo/mes (COP)": st.column_config.NumberColumn(format="$%d")},
        )
        por_tipo = pd.DataFrame(
            {
                "Tipo": [TIPOS_APARATO.get(t["tipo_aparato"], t["tipo_aparato"]) for t in stats["por_tipo"]],
                "kWh/mes": [round(t["consumo_kwh_mes"], 1) for t in stats["por_tipo"]],
                "% del total": [t["porcentaje"] for t in stats["por_tipo"]],
            }
        )
        st.dataframe(por_tipo, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Editar inventario
# ---------------------------------------------------------------------------
if aparatos:
    render_section_header(
        "Editar mis aparatos",
        "settings",
        "Cambia cantidades, potencia u horas de uso, o marca los que quieres eliminar. Si borras la potencia o las horas, vuelve el valor típico.",
    )
    original = pd.DataFrame(
        {
            "id": [a["id"] for a in aparatos],
            "Aparato": [a["nombre"] for a in aparatos],
            "Cantidad": [a["cantidad"] for a in aparatos],
            "Potencia (W)": pd.Series([a["potencia_efectiva_w"] for a in aparatos], dtype="float64"),
            "Horas al día": pd.Series([a["horas_efectivas_dia"] for a in aparatos], dtype="float64"),
            "Dato": ["Tuyo" if a["origen_dato"] == "usuario" else "Típico" for a in aparatos],
            "kWh/mes": [round(a["consumo_kwh_mes"], 1) for a in aparatos],
            "Eliminar": [False for _ in aparatos],
        }
    )
    editado = st.data_editor(
        original,
        key=f"editor_aparatos_{empresa_id}_{ss['aparatos_version']}",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["Aparato", "Dato", "kWh/mes"],
        column_config={
            "id": None,
            "Cantidad": st.column_config.NumberColumn(min_value=1, max_value=500, step=1, required=True),
            "Potencia (W)": st.column_config.NumberColumn(min_value=1, max_value=200000, step=1, format="%.0f", help="Está en la etiqueta del aparato. Borra el valor para volver al típico."),
            "Horas al día": st.column_config.NumberColumn(min_value=0, max_value=24, step=0.5, format="%g", help="Horas que lo usas en un día normal. Borra el valor para volver al típico."),
            "Dato": st.column_config.TextColumn(help="Típico: valor de referencia del catálogo. Tuyo: lo indicaste tú."),
            "kWh/mes": st.column_config.NumberColumn(format="%.1f", help="Estimación con los valores actuales (antes de ajustar a la factura)."),
            "Eliminar": st.column_config.CheckboxColumn(help="Marca y guarda para quitarlo de tu lista."),
        },
    )

    cambios, borrar = calcular_cambios(original, editado, aparatos)

    if cambios or borrar:
        partes = []
        if cambios:
            partes.append(f"{len(cambios)} con cambios")
        if borrar:
            partes.append(f"{len(borrar)} para eliminar: " + ", ".join(n for _, n in borrar))
        st.caption("Pendiente de guardar: " + "; ".join(partes) + ".")
    if st.button("Guardar cambios", type="primary", disabled=not (cambios or borrar), key="guardar_aparatos"):
        ok_cambios = sum(1 for aid, _, p in cambios if api_patch_detallado(f"/empresas/{empresa_id}/aparatos/{aid}", json=p) is not None)
        ok_borrar = sum(1 for aid, _ in borrar if api_delete(f"/empresas/{empresa_id}/aparatos/{aid}"))
        if ok_cambios == len(cambios) and ok_borrar == len(borrar):
            mensaje = []
            if ok_cambios:
                mensaje.append(f"{ok_cambios} aparato(s) actualizados")
            if ok_borrar:
                mensaje.append(f"{ok_borrar} eliminado(s)")
            _recargar("Listo: " + " y ".join(mensaje) + ".")

# ---------------------------------------------------------------------------
# Agregar aparatos
# ---------------------------------------------------------------------------
render_section_header("Agregar aparatos", "upload", "Busca por nombre, con o sin tildes, y marca uno o varios.")
catalogo = get_catalogo_aparatos(tipo_entidad) or []
if not catalogo:
    st.warning("No pudimos cargar la lista de aparatos en este momento.")
else:
    por_id = {a["id"]: a for a in catalogo}
    seleccion = ss.setdefault("agregar_sel", [])  # ids elegidos; se conservan al cambiar la búsqueda
    seleccion[:] = [i for i in seleccion if i in por_id]

    def _alternar_agregar(aparato_id: int) -> None:
        marcado = ss.get(f"agregar_chk_{aparato_id}")
        if marcado and aparato_id not in ss["agregar_sel"]:
            ss["agregar_sel"].append(aparato_id)
        elif not marcado and aparato_id in ss["agregar_sel"]:
            ss["agregar_sel"].remove(aparato_id)

    busqueda = st.text_input(
        "Buscar en el catálogo",
        placeholder="Escribe por ejemplo: nevera, aire, portatil, bomba…",
        key="agregar_buscar",
    )
    filtrados = [a for a in catalogo if coincide(a, busqueda)]
    st.caption(f"{len(seleccion)} elegidos · mostrando {len(filtrados)} de {len(catalogo)} aparatos")
    with st.container(height=260, border=True):
        if not filtrados:
            st.info("Ningún aparato coincide. Puedes agregarlo como aparato propio más abajo.")
        for a in filtrados:
            st.checkbox(
                f"{a['nombre']} — {a.get('descripcion') or ''}",
                value=a["id"] in seleccion,
                key=f"agregar_chk_{a['id']}",
                on_change=_alternar_agregar,
                args=(a["id"],),
                help=f"Uso típico: {a['potencia_w']:.0f} W durante {a['horas_uso_dia']:g} h/día ≈ {a['consumo_kwh_mes']:.0f} kWh/mes",
            )
    elegidos = list(seleccion)
    cantidades = {}
    if elegidos:
        cols = st.columns(min(len(elegidos), 4))
        for n, i in enumerate(elegidos):
            cantidades[i] = cols[n % len(cols)].number_input(
                f"Cantidad · {por_id[i]['nombre']}", min_value=1, max_value=500, value=1, step=1,
                key=f"agregar_cant_{i}_{ss['aparatos_version']}",
            )
    if st.button(
        f"Agregar {len(elegidos)} aparato(s)" if elegidos else "Agregar",
        disabled=not elegidos, key="agregar_btn",
    ):
        resp = api_post(f"/empresas/{empresa_id}/aparatos", json=[{"catalogo_id": i, "cantidad": int(cantidades.get(i, 1))} for i in elegidos])
        if resp is not None:
            for i in elegidos:
                ss.pop(f"agregar_chk_{i}", None)
            ss["agregar_sel"] = []
            _recargar(f"Agregados: {', '.join(a['nombre'] for a in resp)}.")

with st.expander("¿No está en la lista? Agrega un aparato propio"):
    with st.form("form_aparato_propio", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        nombre_p = c1.text_input("Nombre", placeholder="Ej: acuario, vitrina calentadora")
        potencia_p = c2.number_input("Potencia (W)", min_value=1.0, max_value=200000.0, value=None, placeholder="Ej: 300")
        horas_p = c3.number_input("Horas al día", min_value=0.0, max_value=24.0, value=None, step=0.5, placeholder="Ej: 2")
        cantidad_p = c4.number_input("Cantidad", min_value=1, max_value=500, value=1, step=1)
        if st.form_submit_button("Agregar aparato propio"):
            if len((nombre_p or "").strip()) < 2 or potencia_p is None or horas_p is None:
                st.error("Completa nombre, potencia y horas de uso.")
            else:
                resp = api_post(
                    f"/empresas/{empresa_id}/aparatos",
                    json=[{"nombre": nombre_p.strip(), "potencia_w": potencia_p, "horas_uso_dia": horas_p, "cantidad": int(cantidad_p)}],
                )
                if resp is not None:
                    _recargar(f"Agregado: {nombre_p.strip()}.")
