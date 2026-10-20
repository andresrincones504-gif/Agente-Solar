"""Pagina de reportes."""

from datetime import datetime
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_download, api_get, get_current_user, is_authenticated
from design import render_card, render_hero, render_section_header
from ui import render_user_sidebar


st.set_page_config(page_title="Reportes", layout="wide", initial_sidebar_state="expanded")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero.")
    st.stop()

user = get_current_user() or {}

empresas = api_get("/empresas/") or []
if not empresas:
    st.warning("Sin empresas disponibles.")
    st.stop()

if user.get("role") == "empresa" and user.get("empresa_id"):
    empresa_id = user["empresa_id"]
    empresa_sel = next((e for e in empresas if e["id"] == empresa_id), empresas[0])
else:
    opciones = {f"{e['nombre']} (ID:{e['id']})": e for e in empresas}
    seleccion = st.selectbox("Empresa", list(opciones.keys()))
    empresa_sel = opciones[seleccion]
    empresa_id = empresa_sel["id"]

render_hero(
    "Reportes inteligentes",
    "Exporta entregables para seguimiento ejecutivo y analisis tecnico.",
    icon="report",
    eyebrow=empresa_sel["nombre"],
    tone="info",
)

col_a, col_b = st.columns(2)
with col_a:
    days = st.slider("Periodo (dias)", min_value=7, max_value=365, value=30)
with col_b:
    render_section_header("Contenido esperado", "chart")
    st.caption("Incluye KPIs, recomendaciones, alertas y detalle de consumo, produccion y costos.")

cards = st.columns(2)
with cards[0]:
    render_card("Reporte PDF", body="Ideal para presentaciones y resumen ejecutivo.", icon="report", tone="brand")
with cards[1]:
    render_card("Reporte Excel", body="Ideal para analisis tecnico y seguimiento detallado.", icon="chart", tone="success")

st.divider()

show_details = st.toggle("Habilitar Generadores Multiformato", key="descargas", help="Activa la exportación a archivos estáticos como Excel o PDF.")
if not show_details:
    st.caption("👈 Activa este interruptor para generar el reporte con los días estipulados y guardarlo localmente.")
    st.stop()

col_pdf, col_excel = st.columns(2)
with col_pdf:
    render_section_header("PDF", "download", "Archivo de lectura")
    if st.button("Generar y descargar PDF", type="primary", use_container_width=True):
        with st.spinner("Generando reporte PDF..."):
            pdf_bytes = api_download(f"/reportes/pdf/{empresa_id}", params={"days": days})
            if pdf_bytes:
                filename = f"reporte_{empresa_sel['nombre'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                st.download_button("Guardar PDF en el equipo", data=pdf_bytes, file_name=filename, mime="application/pdf", use_container_width=True)
                st.success("Reporte generado correctamente.")
            else:
                st.error("No se pudo generar el PDF.")

with col_excel:
    render_section_header("Excel", "download", "Libro de cálculo")
    if st.button("Generar y descargar Excel", type="primary", use_container_width=True):
        with st.spinner("Generando reporte Excel..."):
            xlsx_bytes = api_download(f"/reportes/excel/{empresa_id}", params={"days": days})
            if xlsx_bytes:
                filename = f"reporte_{empresa_sel['nombre'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                st.download_button(
                    "Guardar Excel en el equipo",
                    data=xlsx_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
                st.success("Reporte generado correctamente.")
            else:
                st.error("No se pudo generar el Excel.")
