"""Pagina de datos solares."""

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_get, api_post, is_authenticated
from design import render_hero, render_section_header
from ubicacion import CIUDAD, LAT, LON, NOMBRE
from ui import render_user_sidebar


st.set_page_config(page_title="Datos Solares", layout="wide", initial_sidebar_state="expanded")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero.")
    st.stop()

render_hero(
    f"Datos solares de {CIUDAD}",
    "Open-Meteo como fuente principal, OpenWeather como complemento y PVGIS como linea base.",
    icon="sun",
    eyebrow=NOMBRE,
    tone="warning",
)

st.info(f"Ubicacion: {NOMBRE} ({LAT:.4f}, {LON:.4f}). La linea base de radiacion es el TMY de PVGIS.")

render_section_header("Enlace con Fuentes Externas", "upload", "Consulta manual de satelites e inst. meteorologicos.")
col_sync, col_sources = st.columns([1, 2])

with col_sync:
    days_sync = st.number_input("Dias a sincronizar", min_value=7, max_value=365, value=30, key="historico_days")
    if st.button("Sincronizar historico solar", type="primary", key="historico_sync"):
        with st.spinner("Consultando Open-Meteo y NASA POWER..."):
            data = api_post("/solar/sync/historico", params={"days": days_sync})
            if data is not None:
                st.success(
                    "Sincronizacion completada. "
                    f"Open-Meteo: {data.get('openmeteo', 0)}, "
                    f"NASA POWER: {data.get('nasa_power', 0)}, "
                    f"total: {data.get('total', 0)}."
                )
                st.rerun()
    st.caption(f"Esta accion actualiza la tabla global de radiacion para {CIUDAD} y funciona igual en demo o real.")

with col_sources:
    st.markdown(
        "**Open-Meteo** entrega GHI y variables meteorologicas recientes.\n\n"
        "- Forecast horario hasta 16 dias.\n"
        "- Archive historico con retraso corto.\n\n"
        "**NASA POWER** funciona como respaldo historico y validacion cruzada."
    )

tab_pvgis = st.tabs(["PVGIS"])

with tab_pvgis[0]:
    if st.button(f"Obtener TMY de {CIUDAD}", key="pvgis_tmy"):
        with st.spinner("Consultando PVGIS..."):
            tmy = api_get("/solar/pvgis/tmy")
            if tmy and tmy.get("disponible"):
                cols = st.columns(3)
                cols[0].metric("GHI promedio", f"{tmy.get('ghi_promedio_diario_kwh_m2', 0):.2f} kWh/m2/dia")
                cols[1].metric("Temperatura promedio", f"{tmy.get('temperatura_promedio_c', 0):.1f} C")
                cols[2].metric("GHI maximo horario", f"{tmy.get('ghi_max_horario_w_m2', 0):.0f} W/m2")
                st.caption("Linea base climatologica para comparar pronosticos y desvio operativo.")
            else:
                st.warning(tmy.get("motivo", "PVGIS no disponible") if tmy else "Sin respuesta")

st.divider()
render_section_header("Historico de Radiacion", "chart", "Analisis de la energia captada en el terreno.")

filtros = st.columns(2)
with filtros[0]:
    days_view = st.slider("Periodo de visualizacion (dias)", 7, 365, 60)
with filtros[1]:
    fuente_filtro = st.selectbox("Filtro de Fuente", options=["(todas)", "open_meteo", "nasa_power"], index=0)

params_get = {"days": days_view}
if fuente_filtro != "(todas)":
    params_get["fuente"] = fuente_filtro

radiacion = api_get("/solar/radiacion", params=params_get)
if radiacion:
    df = pd.DataFrame(radiacion)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha")
    if "origen_dato" in df.columns and (df["origen_dato"] == "forecast_api").any():
        st.caption("Los dias mas recientes se completan con pronostico diario de Open-Meteo mientras el Archive publica el historico definitivo.")

    cols = st.columns(4)
    cols[0].metric("Promedio GHI", f"{df['ghi'].mean():.2f} kWh/m2/dia")
    cols[1].metric("Maximo GHI", f"{df['ghi'].max():.2f} kWh/m2/dia")
    cols[2].metric("Minimo GHI", f"{df['ghi'].min():.2f} kWh/m2/dia")
    if "temperatura" in df.columns and df["temperatura"].notna().any():
        cols[3].metric("Temp. promedio", f"{df['temperatura'].mean():.1f} C")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["fecha"],
            y=df["ghi"],
            name="GHI",
            mode="lines+markers",
            line=dict(color="#C88A2E", width=2),
            fill="tozeroy",
            fillcolor="rgba(200, 138, 46, 0.2)",
        )
    )
    if "dni" in df.columns and df["dni"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df["fecha"],
                y=df["dni"],
                name="DNI",
                mode="lines",
                line=dict(color="#1E6B5C", width=1.5, dash="dash"),
            )
        )
    fig.update_layout(xaxis_title="Fecha", yaxis_title="kWh/m2/dia", height=400, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sin datos. Sincroniza una fuente para comenzar.")

st.divider()
render_section_header("Pronostico solar", "forecast", "Referencia tecnica para los proximos dias.")
forecast_om = api_get("/solar/forecast/horario", params={"days": 5})
if forecast_om:
    df_fo = pd.DataFrame(forecast_om)
    df_fo["fecha"] = pd.to_datetime(df_fo["fecha"])

    fig_om = go.Figure()
    fig_om.add_trace(
        go.Scatter(
            x=df_fo["fecha"],
            y=df_fo["ghi_w_m2"],
            name="GHI (W/m2)",
            line=dict(color="#C88A2E", width=2),
            fill="tozeroy",
            fillcolor="rgba(200, 138, 46, 0.2)",
        )
    )
    if "dni_w_m2" in df_fo.columns:
        fig_om.add_trace(
            go.Scatter(
                x=df_fo["fecha"],
                y=df_fo["dni_w_m2"],
                name="DNI (W/m2)",
                line=dict(color="#1E6B5C", dash="dash"),
            )
        )
    fig_om.add_trace(
        go.Scatter(
            x=df_fo["fecha"],
            y=df_fo["nubosidad"],
            name="Nubosidad (%)",
            line=dict(color="#245C81"),
            yaxis="y2",
        )
    )
    fig_om.update_layout(yaxis=dict(title="W/m2"), yaxis2=dict(title="%", overlaying="y", side="right"), height=380, hovermode="x unified")
    st.plotly_chart(fig_om, use_container_width=True)

st.divider()
render_section_header("Clima y validacion cruzada", "cloud")
col_now, col_cross = st.columns([1, 2])
with col_now:
    st.markdown("**Clima actual**")
    weather = api_get("/solar/weather/current")
    if weather:
        wm1, wm2 = st.columns(2)
        wm1.metric("Temperatura", f"{weather.get('temperatura', 0):.1f} C")
        wm2.metric("Humedad", f"{weather.get('humedad', 0)} %")
        wm1.metric("Nubosidad", f"{weather.get('nubosidad', 0)} %")
        wm2.metric("Viento", f"{weather.get('viento_kmh', 0):.1f} km/h")

        descripcion = str(weather.get('descripcion', '')).capitalize()
        fuente = weather.get('fuente', '?')
        origen = weather.get('origen_dato', '?')
        st.caption(f"{descripcion} - Fuente: {fuente} ({origen})")

        if origen == "synthetic_fallback":
            st.warning(
                "OpenWeather no está disponible en este entorno; los valores mostrados son un fallback sintético. "
                "Configura OPENWEATHER_API_KEY para datos reales."
            )
    else:
        st.error(
            "No se pudo cargar el clima actual de OpenWeather. "
            "Verifica las credenciales y el estado del servicio."
        )

with col_cross:
    st.markdown("**Comparacion entre fuentes**")
    if st.button("Comparar fuentes ahora"):
        with st.spinner("Comparando..."):
            cross = api_get("/solar/weather/cross-check")
            if cross:
                # Guardar resultado en session_state para que persista
                st.session_state["last_cross_check"] = cross
                st.success("✓ Datos actualizados")
    
    # Mostrar tabla si hay datos en session_state
    if "last_cross_check" in st.session_state:
        cross = st.session_state["last_cross_check"]
        delta = cross.get("delta_temperatura_c")
        if cross.get("consistente"):
            st.info(f"Fuentes consistentes. Delta de temperatura: {delta} C")
        else:
            st.warning(f"Discrepancia detectada. Delta de temperatura: {delta} C")

        def _fmt(val, is_int=False):
            if not isinstance(val, (int, float)):
                return "--"
            return f"{int(val)}" if is_int else f"{val:.1f}"

        om_d = cross.get("open_meteo") or {}
        ow_d = cross.get("openweather") or {}

        comp_df = pd.DataFrame(
            {
                "Metrica": ["Temperatura (C)", "Humedad (%)", "Nubosidad (%)", "Viento (km/h)"],
                "Open-Meteo": [
                    _fmt(om_d.get("temperatura")),
                    _fmt(om_d.get("humedad"), True),
                    _fmt(om_d.get("nubosidad"), True),
                    _fmt(om_d.get("viento_kmh")),
                ],
                "OpenWeather": [
                    _fmt(ow_d.get("temperatura")),
                    _fmt(ow_d.get("humedad"), True),
                    _fmt(ow_d.get("nubosidad"), True),
                    _fmt(ow_d.get("viento_kmh")),
                ],
            }
        )

        with st.expander("Ver Tabla de Validacion Tecnica"):
            st.dataframe(comp_df, hide_index=True, use_container_width=True)

    st.markdown(" ")
    st.markdown("**Calidad del aire**")
    aqi = api_get("/solar/air-quality")
    if aqi and aqi.get("disponible") and aqi.get("datos"):
        primer = aqi["datos"][0]
        cols = st.columns(3)
        cols[0].metric("PM10", f"{primer.get('pm10', 0) or 0:.1f} ug/m3")
        cols[1].metric("PM2.5", f"{primer.get('pm2_5', 0) or 0:.1f} ug/m3")
        cols[2].metric("Polvo", f"{primer.get('polvo', 0) or 0:.1f} ug/m3")
        st.caption("Una carga alta de polvo puede reducir la eficiencia de los paneles.")
