"""Pagina de dashboard principal."""

from datetime import datetime, timedelta
import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_get, get_current_user, is_authenticated
from design import render_hero, render_section_header
from ubicacion import CIUDAD
from ui import render_user_sidebar


st.set_page_config(page_title="Dashboard", layout="wide", initial_sidebar_state="expanded")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero. Vaya a Home.")
    st.stop()

user = get_current_user() or {}

empresas = api_get("/empresas/") or []
if not empresas:
    st.warning("No hay empresas registradas.")
    st.stop()

if user.get("role") == "empresa" and user.get("empresa_id"):
    empresa_id = user["empresa_id"]
    empresa_sel = next((e for e in empresas if e["id"] == empresa_id), empresas[0])
else:
    opciones = {f"{e['nombre']} (ID:{e['id']})": e for e in empresas}
    seleccion = st.selectbox("Selecciona una empresa", list(opciones.keys()))
    empresa_sel = opciones[seleccion]
    empresa_id = empresa_sel["id"]

paneles_instalados = empresa_sel.get("capacidad_paneles_kw", 0.0) or 0.0
es_simulado = (paneles_instalados == 0.0)
simulated_capacity = 2.5 if empresa_sel.get("tipo") == "hogar" else 10.0
PERFORMANCE_RATIO = 0.8  # pérdidas reales: temperatura, polvo, inversor y cableado
sistema_sugerido = None
if es_simulado:
    # Tamaño calculado con la factura o los aparatos del usuario (si no hay datos, un sistema de referencia)
    sistema_sugerido = api_get(f"/empresas/{empresa_id}/aparatos/dimensionamiento")
    if sistema_sugerido and sistema_sugerido.get("kwp_sugerido"):
        simulated_capacity = sistema_sugerido["kwp_sugerido"]
BASE_SISTEMA = {
    "factura": "calculado con tu consumo real",
    "inventario": "calculado con los aparatos que registraste",
    "referencia": "de referencia: registra tus aparatos o tu factura para ajustarlo",
}

render_hero(
    "Dashboard energetico",
    f"Tipo: {empresa_sel.get('tipo', 'N/A')} · Tarifa: ${empresa_sel.get('tarifa_kwh', 0):,.0f} COP/kWh" + 
    (f" · Simulador: Activo ({simulated_capacity} kWp)" if es_simulado else f" · Paneles: {paneles_instalados} kW"),
    icon="chart",
    eyebrow=empresa_sel["nombre"],
    tone="info",
)

if es_simulado:
    st.info(
        f"💡 **Simulación Solar Activa:** Tu perfil no tiene paneles registrados en la base de datos. "
        f"Simulamos el potencial de generación y ahorro para un sistema de **{simulated_capacity} kWp** "
        f"({BASE_SISTEMA.get((sistema_sugerido or {}).get('base'), BASE_SISTEMA['referencia'])}) en {CIUDAD}, "
        "utilizando radiación real y descontando un 20% de pérdidas."
    )

kpis = api_get(f"/consumo/kpis/{empresa_id}")
if kpis:
    st.markdown("### Resumen Rápido")
    
    # Cálculos para simulación
    tarifa = empresa_sel.get("tarifa_kwh", 943.0)
    ghi_hoy = kpis.get("radiacion_actual_kwh") if kpis.get("radiacion_actual_kwh") is not None else 5.5
    prod_hoy_simulada = simulated_capacity * ghi_hoy * PERFORMANCE_RATIO
    ahorro_hoy_simulado = prod_hoy_simulada * tarifa
    
    prod_mes_simulada = (
        sistema_sugerido["produccion_mes_kwh"]
        if sistema_sugerido and sistema_sugerido.get("produccion_mes_kwh")
        else simulated_capacity * 5.0 * 30 * PERFORMANCE_RATIO
    )
    ahorro_mes_simulado = prod_mes_simulada * tarifa
    
    cols = st.columns(4)
    with cols[0]:
        st.metric("Consumo hoy", f"{kpis.get('consumo_hoy_kwh') or 0:.1f} kWh")
    with cols[1]:
        if es_simulado:
            st.metric("Potencial Solar Hoy (Simulado)", f"{prod_hoy_simulada:.1f} kWh")
        else:
            st.metric("Producción solar hoy", f"{kpis.get('produccion_solar_hoy_kwh') or 0:.1f} kWh")
    with cols[2]:
        st.metric("Costo hoy", f"${kpis.get('costo_hoy_cop') or 0:,.0f}")
    with cols[3]:
        if es_simulado:
            st.metric("Ahorro Proyectado Hoy", f"${ahorro_hoy_simulado:,.0f}", delta="Potencial")
        else:
            ahorro = kpis.get("ahorro_estimado_cop") or 0
            st.metric("Ahorro solar hoy", f"${ahorro:,.0f}", delta=f"{(ahorro / max(kpis.get('costo_hoy_cop') or 1, 1) * 100):.0f}%")

    with st.expander("Ver más KPIs detallados"):
        cols_det = st.columns(4)
        with cols_det[0]:
            st.metric("Consumo mes", f"{kpis.get('consumo_mes_kwh') or 0:.1f} kWh")
        with cols_det[1]:
            if es_simulado:
                st.metric("Ahorro Proyectado Mes", f"${ahorro_mes_simulado:,.0f}", help="Ahorro estimado en base al potencial solar mensual.")
            else:
                st.metric("Costo mes", f"${kpis.get('costo_mes_cop') or 0:,.0f}")
        with cols_det[2]:
            st.metric("Radiación actual GHI", f"{kpis.get('radiacion_actual_kwh') or 0:.2f} kWh/m2/dia" if kpis.get('radiacion_actual_kwh') else "5.50 kWh/m2/dia (Est.)")
        with cols_det[3]:
            if es_simulado:
                st.metric("Producción Proyectada Mes", f"{prod_mes_simulada:,.1f} kWh")
            else:
                bat = kpis.get("nivel_bateria_pct")
                st.metric("Batería", f"{bat:.0f}%" if bat is not None else "N/A")

st.divider()
days = st.slider("Periodo de analisis (dias)", min_value=7, max_value=180, value=30, help="Desliza para cambiar el rango de datos en las gráficas.")
consumos = api_get(f"/consumo/empresa/{empresa_id}", params={"days": days}) or []
radiacion = api_get("/solar/radiacion", params={"days": days}) or []

tab_general, tab_economico, tab_tecnico = st.tabs(["Operación", "Financiero", "Entorno Solar"])

with tab_general:
    render_section_header("Consumo vs Producción Solar", "bolt")
    if consumos:
        df_c = pd.DataFrame(consumos)
        df_c["fecha"] = pd.to_datetime(df_c["fecha"])
        df_c = df_c.sort_values("fecha")

        if es_simulado:
            rad_map = {}
            if radiacion:
                for r in radiacion:
                    try:
                        # Extraer fecha del registro
                        if isinstance(r["fecha"], str):
                            f_date = pd.to_datetime(r["fecha"].replace("Z", "")).date()
                        else:
                            f_date = pd.to_datetime(r["fecha"]).date()
                        rad_map[f_date] = r.get("ghi") or 5.5
                    except Exception:
                        pass
            
            def _get_ghi_simulada(fecha):
                d = fecha.date()
                return rad_map.get(d, 5.5)
            
            df_c["ghi_diaria"] = df_c["fecha"].apply(_get_ghi_simulada)
            df_c["produccion_solar_simulada"] = df_c["ghi_diaria"] * simulated_capacity * PERFORMANCE_RATIO

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_c["fecha"], y=df_c["consumo_kwh"], name="Consumo", mode="lines+markers", line=dict(color="#245C81", width=2)))
        
        if es_simulado:
            fig.add_trace(
                go.Scatter(
                    x=df_c["fecha"],
                    y=df_c["produccion_solar_simulada"],
                    name=f"Potencial Solar Estimado (Simulado {simulated_capacity} kWp)",
                    mode="lines",
                    line=dict(color="#C88A2E", width=2, dash="dash"),
                    fill="tozeroy",
                    fillcolor="rgba(200, 138, 46, 0.08)",
                )
            )
        elif "produccion_solar_kwh" in df_c.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_c["fecha"],
                    y=df_c["produccion_solar_kwh"],
                    name="Produccion solar",
                    mode="lines+markers",
                    line=dict(color="#C88A2E", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(200, 138, 46, 0.2)",
                )
            )
        
        fig.update_layout(xaxis_title="Fecha", yaxis_title="Energía (kWh)", hovermode="x unified", height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de consumo para mostrar la gráfica operativa.")

with tab_economico:
    render_section_header("Rendimiento de Costos", "money")
    if consumos:
        df_c = pd.DataFrame(consumos)
        df_c["fecha"] = pd.to_datetime(df_c["fecha"])
        df_c["dia"] = df_c["fecha"].dt.date
        df_c["costo_cop"] = df_c["costo_cop"].fillna(df_c["consumo_kwh"] * empresa_sel["tarifa_kwh"])
        df_costos = df_c.groupby("dia").agg({"costo_cop": "sum", "consumo_kwh": "sum"}).reset_index()
        fig = px.bar(df_costos, x="dia", y="costo_cop", labels={"costo_cop": "Costo Estimado (COP)", "dia": "Día"}, color_discrete_sequence=["#1E6B5C"])
        fig.update_layout(height=450, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos suficientes para procesar visualización financiera.")

with tab_tecnico:
    render_section_header("Radiación Solar Histórica (GHI)", "sun")
    if radiacion:
        df_r = pd.DataFrame(radiacion)
        df_r["fecha"] = pd.to_datetime(df_r["fecha"])
        df_r = df_r.sort_values("fecha")
        if "origen_dato" in df_r.columns and (df_r["origen_dato"] == "forecast_api").any():
            st.caption("La cola mas reciente de esta serie usa pronostico diario de Open-Meteo hasta que el historico oficial quede disponible.")

        fig = px.line(df_r, x="fecha", y="ghi", labels={"ghi": "Radicación GHI (kWh/m²/día)", "fecha": "Fecha"}, color_discrete_sequence=["#C88A2E"])
        fig.update_traces(mode="lines+markers", line=dict(width=2), fill="tozeroy", fillcolor="rgba(200, 138, 46, 0.1)")
        fig.update_layout(height=450, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos climáticos registrados.")
