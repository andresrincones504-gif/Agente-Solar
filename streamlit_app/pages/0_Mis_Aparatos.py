"""Mis aparatos: consumo estimado por aparato, los que más consumen y gestión del inventario."""

import os
import sys

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
from html import escape

from design import PALETTE, render_card, render_hero, render_html_block, render_section_header
from inventario import coincide, payload_edicion
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


# Etiqueta y estilo de la columna "Dato" (de dónde sale el consumo de cada aparato)
ORIGEN_DATO = {
    "catalogo": ("Típico", "ag-pill--tipico"),
    "usuario": ("Tuyo", "ag-pill--tuyo"),
    "factura": ("Factura", "ag-pill--factura"),
}


def _barra_pct(pct: float) -> str:
    """Porcentaje con una barrita proporcional."""
    pct = max(0.0, min(100.0, float(pct or 0)))
    return (
        '<div class="ag-tabla__pct">'
        f'<span class="ag-tabla__barra"><span style="width: {pct:.1f}%;"></span></span>'
        f'<span class="ag-tabla__num">{pct:.1f}%</span>'
        "</div>"
    )


# def _tabla_aparatos_html(filas: list, stats: dict) -> str:
#     """Tabla de solo lectura por aparato, con resumen al pie."""
#     cuerpo = []
#     for f in filas:
#         etiqueta, clase = ORIGEN_DATO.get(f["origen_dato"], (str(f["origen_dato"]).title(), "ag-pill--tipico"))
#         cuerpo.append(
#             "<tr>"
#             f'<td class="ag-tabla__nombre">{escape(f["nombre"])}</td>'
#             f'<td class="ag-tabla__centro"><span class="ag-tabla__cantidad">{int(f["cantidad"] or 0)}</span></td>'
#             f'<td class="ag-tabla__derecha ag-tabla__num">{f["consumo_kwh_mes"]:,.1f}</td>'
#             f'<td class="ag-tabla__derecha ag-tabla__num">{_cop(f["costo_cop_mes"])}</td>'
#             f"<td>{_barra_pct(f.get('porcentaje'))}</td>"
#             f'<td class="ag-tabla__centro"><span class="ag-pill {clase}">{etiqueta}</span></td>'
#             "</tr>"
#         )
#     reales = [f for f in filas if f["aparato_id"] is not None]
#     unidades = sum(int(f["cantidad"] or 0) for f in reales)
#     return f"""
#     <div class="ag-tabla-titulo">Por aparato</div>
#     <div class="ag-tabla-wrap">
#         <table class="ag-tabla">
#             <thead><tr>
#                 <th>Aparato</th>
#                 <th class="ag-tabla__centro">Cantidad</th>
#                 <th class="ag-tabla__derecha">kWh / mes</th>
#                 <th class="ag-tabla__derecha">Costo / mes</th>
#                 <th>% del total</th>
#                 <th class="ag-tabla__centro">Dato</th>
#             </tr></thead>
#             <tbody>{"".join(cuerpo)}</tbody>
#         </table>
#         <div class="ag-tabla__pie">
#             <div class="ag-tabla__resumen">
#                 <span>Aparatos listados: <b>{len(reales)} tipos</b></span>
#                 <span>Unidades totales: <b>{unidades} aparatos</b></span>
#                 <span>Costo estimado: <b>{_cop(stats["costo_total_cop_mes"])} /mes</b></span>
#             </div>
#             <div class="ag-tabla__total">
#                 <span>Consumo total estimado:</span>
#                 <span class="ag-tabla__total-valor">{stats["consumo_total_kwh_mes"]:,.1f} kWh/mes</span>
#             </div>
#         </div>
#     </div>
#     """


def _tabla_tipos_html(por_tipo: list) -> str:
    """Tabla de solo lectura por tipo de aparato."""
    cuerpo = "".join(
        "<tr>"
        f'<td class="ag-tabla__nombre">{escape(TIPOS_APARATO.get(t["tipo_aparato"], t["tipo_aparato"]))}</td>'
        f'<td class="ag-tabla__derecha ag-tabla__num">{t["consumo_kwh_mes"]:,.1f}</td>'
        f"<td>{_barra_pct(t.get('porcentaje'))}</td>"
        "</tr>"
        for t in por_tipo
    )
    return f"""
    <div class="ag-tabla-titulo">Por tipo de aparato</div>
    <div class="ag-tabla-wrap">
        <table class="ag-tabla ag-tabla--tipos">
            <thead><tr>
                <th>Tipo</th>
                <th class="ag-tabla__derecha">kWh / mes</th>
                <th>% del total</th>
            </tr></thead>
            <tbody>{cuerpo}</tbody>
        </table>
    </div>
    """


# ---------------------------------------------------------------------------
# Tabla para editar: columnas y ventanas de editar / eliminar
# ---------------------------------------------------------------------------
COLUMNAS_EDICION = [3.2, 1.1, 1.3, 1.1, 1.1, 1.3, 1.3]
ENCABEZADOS_EDICION = ("Aparato", "Cantidad", "Potencia", "Horas al día", "Dato", "kWh / mes", "Acciones")
CLASES_EDICION = ("", "ag-edit-td--centro", "ag-edit-td--derecha", "ag-edit-td--centro", "ag-edit-td--centro", "ag-edit-td--derecha", "ag-edit-td--centro")


@st.dialog("Editar aparato")
def _dialogo_editar(a: dict, empresa_id: int) -> None:
    st.markdown(f"**{a['nombre']}**")
    st.caption("Cambia los valores y guarda. El consumo se calcula con potencia × horas de uso × cantidad.")
    cantidad = st.number_input("Cantidad", min_value=1, max_value=500, step=1, value=int(a["cantidad"]), key=f"dlg_cant_{a['id']}")
    # Solo los aparatos del catálogo con valores propios pueden volver al valor típico
    puede_volver = a.get("catalogo_id") is not None and (a.get("potencia_w") is not None or a.get("horas_uso_dia") is not None)
    usar_tipico = puede_volver and st.checkbox(
        "Volver a los valores típicos del catálogo", key=f"dlg_tipico_{a['id']}",
        help="Quita la potencia y las horas que indicaste y usa las de referencia.",
    )
    c1, c2 = st.columns(2)
    potencia = c1.number_input(
        "Potencia (W)", min_value=1.0, max_value=200000.0, step=10.0,
        value=float(a["potencia_efectiva_w"]), key=f"dlg_pot_{a['id']}",
        help="Está en la etiqueta del aparato.", disabled=usar_tipico,
    )
    horas = c2.number_input(
        "Horas al día", min_value=0.0, max_value=24.0, step=0.5,
        value=float(a["horas_efectivas_dia"]), key=f"dlg_horas_{a['id']}",
        help="Horas que lo usas en un día normal.", disabled=usar_tipico,
    )
    if usar_tipico:
        potencia = horas = None
        nota = "Se usarán la potencia y las horas típicas del catálogo."
    else:
        nota = f"Consumo estimado con estos valores: <b>{_kwh_mes(potencia, horas, cantidad):,.1f} kWh/mes</b>"
    st.markdown(f"<div class='ag-dialogo-nota'>{nota}</div>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    if g1.button("Cancelar", use_container_width=True, key=f"dlg_cancelar_{a['id']}"):
        st.rerun()
    if g2.button("Guardar", type="primary", use_container_width=True, key=f"dlg_guardar_{a['id']}"):
        payload = payload_edicion(a, cantidad, potencia, horas)
        if not payload:
            st.info("No cambiaste ningún valor.")
        elif api_patch_detallado(f"/empresas/{empresa_id}/aparatos/{a['id']}", json=payload) is not None:
            _recargar(f"Listo: {a['nombre']} quedó actualizado.")


@st.dialog("Eliminar aparato")
def _dialogo_eliminar(a: dict, empresa_id: int) -> None:
    unidades = f" ({a['cantidad']} unidades)" if int(a["cantidad"]) > 1 else ""
    st.markdown(
        f"<div class='ag-dialogo-borrar'>¿Seguro que quieres eliminar <b>{escape(a['nombre'])}</b>{unidades} de tu lista?</div>",
        unsafe_allow_html=True,
    )
    st.caption("Dejará de contar en tu consumo estimado. Si te equivocas, puedes volver a agregarlo más abajo.")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True, key=f"dlg_no_borrar_{a['id']}"):
        st.rerun()
    if c2.button("Sí, eliminar", type="primary", use_container_width=True, key=f"dlg_si_borrar_{a['id']}"):
        if api_delete(f"/empresas/{empresa_id}/aparatos/{a['id']}"):
            _recargar(f"Listo: eliminamos {a['nombre']} de tu lista.")


def _kwh_mes(potencia_w: float, horas: float, cantidad: int) -> float:
    return (potencia_w or 0) * (horas or 0) * (cantidad or 1) * 30 / 1000


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

    with st.expander("Ver la tabla por tipo"):
        render_html_block(_tabla_tipos_html(stats["por_tipo"]))

# ---------------------------------------------------------------------------
# Editar inventario
# ---------------------------------------------------------------------------
if aparatos:
    render_section_header(
        "Editar mis aparatos",
        "settings",
        "Usa el lápiz para cambiar cantidad, potencia u horas de uso, o la caneca para quitar un aparato de tu lista.",
    )
    with st.container(border=True):
        # Encabezado de la tabla (el marcador le da el estilo a todo el recuadro)
        cab = st.columns(COLUMNAS_EDICION, vertical_alignment="center")
        for col, titulo, clase in zip(cab, ENCABEZADOS_EDICION, CLASES_EDICION):
            with col:
                render_html_block(f'<div class="ag-edit-th {clase}">{titulo}</div>')
        for a in aparatos:
            fila = st.columns(COLUMNAS_EDICION, vertical_alignment="center")
            propio = a["origen_dato"] == "usuario"
            celdas = (
                f'<div class="ag-edit-td ag-edit-td--nombre">{escape(a["nombre"])}</div>',
                f'<div class="ag-edit-td ag-edit-td--centro"><span class="ag-edit-chip">{a["cantidad"]}</span></div>',
                f'<div class="ag-edit-td ag-edit-td--derecha ag-edit-num">{a["potencia_efectiva_w"]:,.0f} <small>W</small></div>',
                f'<div class="ag-edit-td ag-edit-td--centro ag-edit-num">{a["horas_efectivas_dia"]:g} <small>h</small></div>',
                '<div class="ag-edit-td ag-edit-td--centro">'
                + ('<span class="ag-pill ag-pill--tuyo">Tuyo</span>' if propio else '<span class="ag-pill ag-pill--info">Típico</span>')
                + "</div>",
                f'<div class="ag-edit-td ag-edit-td--derecha ag-edit-num">{a["consumo_kwh_mes"]:,.1f}</div>',
            )
            for col, celda in zip(fila[:-1], celdas):
                with col:
                    render_html_block(celda)
            with fila[-1]:
                b_editar, b_borrar = st.columns(2, gap="small")
                if b_editar.button(":material/edit:", key=f"editar_aparato_{a['id']}", help=f"Editar {a['nombre']}"):
                    _dialogo_editar(a, empresa_id)
                if b_borrar.button(":material/delete:", key=f"borrar_aparato_{a['id']}", help=f"Eliminar {a['nombre']}"):
                    _dialogo_eliminar(a, empresa_id)
        unidades = sum(int(a["cantidad"]) for a in aparatos)
        total_kwh = sum(float(a["consumo_kwh_mes"]) for a in aparatos)
        render_html_block(
            f"""
            <div class="ag-edit-pie">
                <div class="ag-edit-pie__resumen">
                    <span>Aparatos listados: <b>{len(aparatos)} tipos</b></span>
                    <span>Unidades totales: <b>{unidades} aparatos</b></span>
                </div>
                <div class="ag-edit-pie__total">
                    <span>Consumo estimado:</span>
                    <span class="ag-edit-pie__valor">{total_kwh:,.1f} kWh/mes</span>
                </div>
            </div>
            """
        )

# ---------------------------------------------------------------------------
# Agregar aparatos
# ---------------------------------------------------------------------------
# Ícono (Material) de cada categoría en la lista para agregar
ICONO_CATEGORIA = {
    "refrigeracion": ":material/kitchen:",
    "climatizacion": ":material/mode_fan:",
    "iluminacion": ":material/lightbulb:",
    "cocina": ":material/blender:",
    "lavado": ":material/local_laundry_service:",
    "entretenimiento": ":material/tv:",
    "cuidado_personal": ":material/spa:",
    "oficina": ":material/computer:",
    "bombas_motores": ":material/build:",
}

with st.container(border=True):
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
        render_html_block(
            f'<div class="ag-add-caption">{len(seleccion)} elegidos · mostrando {len(filtrados)} de {len(catalogo)} aparatos</div>'
        )
        with st.container(height=470, border=False):
            if not filtrados:
                st.info("Ningún aparato coincide. Puedes agregarlo como aparato propio más abajo.")
            # Una sección desplegable por categoría, en el orden del catálogo
            orden = {t: n for n, t in enumerate(TIPOS_APARATO)}
            categorias = sorted({a["tipo_aparato"] for a in filtrados}, key=lambda t: orden.get(t, 99))
            for tipo in categorias:
                del_tipo = [a for a in filtrados if a["tipo_aparato"] == tipo]
                marcados = sum(1 for a in del_tipo if a["id"] in seleccion)
                etiqueta = f"**{TIPOS_APARATO.get(tipo, tipo.title())}** :gray-background[{len(del_tipo)} disponibles]"
                with st.expander(etiqueta, expanded=bool(busqueda) or marcados > 0, icon=ICONO_CATEGORIA.get(tipo, ":material/category:")):
                    render_html_block(f'<span class="ag-cat ag-cat--{tipo}"></span>')
                    for a in del_tipo:
                        st.checkbox(
                            f"{a['nombre']} :gray[{a.get('descripcion') or ''}]",
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
