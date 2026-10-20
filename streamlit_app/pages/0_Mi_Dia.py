"""Pagina Mi Dia con vista compacta y detalle opcional integrado en el hero."""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_get, get_current_user, is_authenticated
from design import render_card, render_hero, render_section_header
from ui import render_user_sidebar


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

# Hero con boton "Ver mas" integrado dentro del cuadro verde
render_hero(
    score.get("titulo", "Tu día energético"),
    resumen_breve,
    icon="sun",
    eyebrow=f"🏠 Hogar: {empresa.get('nombre')}" if es_hogar else empresa.get("nombre", "Operación diaria"),
    tone=score_tone,
    expandable_text=resumen_text if es_largo else None,
)

consejo = data.get("consejo_aparatos")
if consejo:
    render_section_header("Tus aparatos hoy", "idea", "Un consejo según lo que tienes en casa o en tu negocio.")
    render_card(
        consejo.get("titulo", "Tus aparatos"),
        body=consejo.get("mensaje", ""),
        icon="sun" if consejo.get("tipo") == "franja_solar" else "bolt",
        tone="warning" if consejo.get("tipo") == "sin_aparatos" else "brand",
    )
    sin_aparatos = consejo.get("tipo") == "sin_aparatos"
    if st.button(
        "Registrar mis aparatos" if sin_aparatos else "Ver mis aparatos",
        type="primary" if sin_aparatos else "secondary",
        key="mi_dia_ir_aparatos",
    ):
        st.switch_page("pages/0_Mis_Aparatos.py")

render_section_header(
    "Resumen clave",
    "spark",
    "Lectura compacta del estado actual.",
)

order = [
    ("dia_solar", "Dia solar", "sun"),
    ("consumo", "Consumo de hoy", "bolt"),
    ("produccion", "Paneles", "chart"),
    ("riesgo_apagon", "Continuidad", "alert"),
    ("aire", "Aire y polvo", "cloud"),
    ("bateria", "Bateria", "battery"),
]

for row_start in range(0, len(order), 3):
    row_items = order[row_start:row_start + 3]
    row_cols = st.columns(3)
    for col_index, column in enumerate(row_cols):
        if col_index >= len(row_items):
            continue
        key, fallback_title, icon_name = row_items[col_index]
        tarjeta = tarjetas.get(key) or {}
        with column:
            render_card(
                tarjeta.get("titulo", fallback_title),
                body=tarjeta.get("mensaje", ""),
                icon=icon_name,
                tone=tone_map.get(tarjeta.get("nivel"), "info"),
                action=tarjeta.get("accion"),
            )

render_section_header("Acciones rapidas", "bolt")
shortcut_cols = st.columns(4)
with shortcut_cols[0]:
    if st.button("Ver recomendaciones", use_container_width=True):
        st.switch_page("pages/4_Recomendaciones_IA.py")
with shortcut_cols[1]:
    if st.button("Ver alertas", use_container_width=True):
        st.switch_page("pages/5_Alertas.py")
with shortcut_cols[2]:
    if st.button("Abrir consumo", use_container_width=True):
        st.switch_page("pages/2_Consumo.py")
with shortcut_cols[3]:
    if st.button("Detalles tecnicos", use_container_width=True):
        st.switch_page("pages/1_Dashboard.py")

st.caption(
    "La pagina prioriza una lectura compacta. Para ampliar indicadores y contexto tecnico, "
    "usa el acceso directo a Detalles tecnicos."
)