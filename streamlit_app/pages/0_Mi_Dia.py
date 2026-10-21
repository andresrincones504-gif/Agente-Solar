"""Pagina Mi Dia con vista compacta y detalle opcional integrado en el hero."""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_get, get_current_user, is_authenticated
from design import render_hero, render_section_header, render_tile
from ui import NOMBRE_PAGINA, puede_ver, render_user_sidebar


st.set_page_config(page_title="Mi Dia", layout="wide", initial_sidebar_state="expanded")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero.")
    st.stop()

user = get_current_user() or {}
empresa_id = user.get("empresa_id")

if not empresa_id:
    empresas = api_get("/empresas/") or []
    if not empresas:
        st.info("No hay empresas disponibles.")
        st.stop()
    seleccion = st.selectbox(
        "Selecciona una empresa",
        options=empresas,
        format_func=lambda e: e["nombre"],
    )
    empresa_id = seleccion["id"] if seleccion else None

if not empresa_id:
    st.stop()

# El resumen tarda unos segundos (clima y radiación del día): mostramos una espera amable
with st.spinner("Preparando el resumen de tu día…"):
    data = api_get(
        f"/insights/diario/{empresa_id}",
        params={"incluir_resumen_llm": "true"},
    )
if not data:
    st.error("No se pudo cargar el resumen del dia.")
    st.stop()

empresa = data.get("empresa", {})
score = data.get("score_global", {})
tarjetas = data.get("tarjetas", {})
resumen_narrativo = data.get("resumen_narrativo")
fuente = data.get("fuente_narrativa", "plantilla")

tone_map = {"verde": "success", "amarillo": "warning", "rojo": "danger"}
score_tone = tone_map.get(score.get("nivel"), "info")

es_hogar = (empresa.get("tipo") == "hogar")
resumen_text = resumen_narrativo or (
    "Resumen diario listo para tomar decisiones en tu hogar sin sobrecarga visual."
    if es_hogar
    else "Resumen diario listo para tomar decisiones sin sobrecarga visual."
)

# Construir version breve y decidir si hay desglose
es_largo = len(resumen_text) > 180
resumen_breve = (
    resumen_text
    if not es_largo
    else resumen_text[:180].rsplit(" ", 1)[0] + "..."
)

# Hero con boton "Ver mas" integrado dentro del cuadro de color
render_hero(
    score.get("titulo", "Tu día energético"),
    resumen_breve,
    icon="sun",
    eyebrow=f"Hogar: {empresa.get('nombre')}" if es_hogar else empresa.get("nombre", "Operación diaria"),
    tone=score_tone,
    expandable_text=resumen_text if es_largo else None,
    variant="solido",
)

consejo = data.get("consejo_aparatos")
if consejo:
    render_section_header(
        "Tus aparatos hoy", "idea", "Un consejo según lo que tengas en casa o en tu negocio.", round_icon=True
    )
    sin_aparatos = consejo.get("tipo") == "sin_aparatos"
    with st.container(border=True):
        render_tile(
            consejo.get("titulo", "Tus aparatos"),
            body=consejo.get("mensaje", ""),
            icon="sun" if consejo.get("tipo") == "franja_solar" else "bolt",
            tone="warning" if sin_aparatos else "brand",
        )
        if st.button(
            "Registrar mis aparatos" if sin_aparatos else "Ver mis aparatos",
            key="mi_dia_ir_aparatos",
        ):
            st.switch_page("pages/0_Mis_Aparatos.py")

render_section_header(
    "Resumen clave",
    "spark",
    "Lectura compacta del estado actual.",
    round_icon=True,
)

# (clave de la tarjeta, título de respaldo, ícono, pantalla a la que lleva su botón,
#  texto del botón cuando la tarjeta no trae una acción propia)
order = [
    ("dia_solar", "Dia solar", "sun", "Recomendaciones_IA", "Ver recomendaciones"),
    ("consumo", "Consumo de hoy", "bolt", "Consumo", "Ver consumo"),
    ("produccion", "Paneles", "chart", "Dashboard", "Ver panel"),
    ("riesgo_apagon", "Continuidad", "alert", "Alertas", "Ver alertas"),
    ("aire", "Aire y polvo", "cloud", "Alertas", "Ver calidad del aire"),
    ("bateria", "Bateria", "battery", "Dashboard", "Ver estado de la red"),
]
DESTINOS = {
    "Recomendaciones_IA": "pages/4_Recomendaciones_IA.py",
    "Consumo": "pages/2_Consumo.py",
    "Dashboard": "pages/1_Dashboard.py",
    "Alertas": "pages/5_Alertas.py",
}

for row_start in range(0, len(order), 3):
    row_items = order[row_start:row_start + 3]
    row_cols = st.columns(3)
    for col_index, column in enumerate(row_cols):
        if col_index >= len(row_items):
            continue
        key, fallback_title, icon_name, destino, boton_respaldo = row_items[col_index]
        tarjeta = tarjetas.get(key) or {}
        with column:
            with st.container(border=True):
                render_tile(
                    tarjeta.get("titulo", fallback_title),
                    body=tarjeta.get("mensaje", ""),
                    icon=icon_name,
                    tone=tone_map.get(tarjeta.get("nivel"), "info"),
                )
                if puede_ver(destino, user) and st.button(
                    tarjeta.get("accion") or boton_respaldo,
                    key=f"mi_dia_tarjeta_{key}",
                    use_container_width=True,
                    help=f"Abre {NOMBRE_PAGINA[destino]}",
                ):
                    st.switch_page(DESTINOS[destino])
