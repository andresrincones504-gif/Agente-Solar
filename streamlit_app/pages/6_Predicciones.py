"""Pagina de predicciones con vista compacta y detalle opcional."""

from datetime import datetime
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import api_get, api_post, get_current_user, is_authenticated
from design import render_card, render_hero, render_section_header
from ubicacion import CIUDAD
from ui import render_user_sidebar


st.set_page_config(page_title="Predicciones", layout="wide", initial_sidebar_state="expanded")
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

# Inferencia dinámica de equipamiento en caliente basado en el historial de telemetría del usuario
escenario_actual = user.get("escenario_usuario", "real")
consumos_recientes = api_get(f"/consumo/empresa/{empresa_id}", params={"days": 30, "escenario": escenario_actual}) or []
tiene_telemetria_bateria = any(c.get("nivel_bateria_pct") is not None for c in consumos_recientes)
tiene_telemetria_solar = any((c.get("produccion_solar_kwh") or 0.0) > 0.0 for c in consumos_recientes)

tiene_baterias = ((empresa_sel.get("capacidad_bateria_kwh") or 0.0) > 0.0) or tiene_telemetria_bateria
tiene_paneles = ((empresa_sel.get("capacidad_paneles_kw") or 0.0) > 0.0) or tiene_telemetria_solar

# Sistema sugerido según la factura o los aparatos del usuario (si no hay datos, valores de referencia)
_es_hogar_perfil = (empresa_sel.get("tipo") == "hogar")
sistema_sugerido = (
    api_get(f"/empresas/{empresa_id}/aparatos/dimensionamiento")
    if not (tiene_baterias and tiene_paneles) else None
) or {}
bateria_sugerida = sistema_sugerido.get("bateria_kwh_sugerida") or (5.0 if _es_hogar_perfil else 30.0)
kwp_sugerido = sistema_sugerido.get("kwp_sugerido") or (2.5 if _es_hogar_perfil else 10.0)
autonomia_criticas = sistema_sugerido.get("autonomia_cargas_criticas_horas")



def _future_rows(items):
    out = []
    for item in items:
        try:
            fecha = datetime.fromisoformat(item["fecha_objetivo"].replace("Z", ""))
        except Exception:
            continue
        if fecha >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            out.append((fecha, item))
    return sorted(out, key=lambda row: row[0])


preds_prod = api_get(f"/predicciones/{empresa_id}", params={"tipo": "produccion_solar"}) or []
preds_cons = api_get(f"/predicciones/{empresa_id}", params={"tipo": "consumo"}) or []
preds_cost = api_get(f"/predicciones/{empresa_id}", params={"tipo": "costo"}) or []
preds_risk = api_get(f"/predicciones/{empresa_id}", params={"tipo": "riesgo_apagon"}) or []

prod_fut = _future_rows(preds_prod)
cons_fut = _future_rows(preds_cons)
cost_fut = _future_rows(preds_cost)
risk_fut = _future_rows(preds_risk)

prod_next = prod_fut[0][1]["valor"] if prod_fut else 0
cons_next = cons_fut[0][1]["valor"] if cons_fut else 0
cost_next = cost_fut[0][1]["valor"] if cost_fut else 0
risk_next = risk_fut[0][1]["valor"] if risk_fut else 0
coverage = (prod_next / cons_next * 100) if cons_next else 0
saving = prod_next * empresa_sel.get("tarifa_kwh", 943.0)

if risk_next >= 40:
    risk_title = "Riesgo alto de continuidad"
    risk_body = f"Se estima una probabilidad de {risk_next:.0f}% de interrupcion en 24 horas."
    risk_tone = "danger"
elif risk_next >= 20:
    risk_title = "Riesgo medio de continuidad"
    risk_body = f"Probabilidad estimada de {risk_next:.0f}% en 24 horas."
    risk_tone = "warning"
else:
    risk_title = "Riesgo bajo de continuidad"
    risk_body = f"Probabilidad estimada de {risk_next:.0f}% en 24 horas."
    risk_tone = "success"

render_hero(
    risk_title,
    risk_body if (preds_prod or preds_cons or preds_cost or preds_risk) else "Genera predicciones para ver el panorama de las proximas horas.",
    icon="forecast",
    eyebrow=empresa_sel["nombre"],
    tone=risk_tone if (preds_prod or preds_cons or preds_cost or preds_risk) else "info",
)

top = st.columns(4)
with top[0]:
    render_card("Produccion prevista", value=f"{prod_next:,.0f} kWh", body="Siguiente bloque disponible.", icon="sun", tone="success")
with top[1]:
    render_card("Consumo previsto", value=f"{cons_next:,.0f} kWh", body="Estimacion operativa base.", icon="bolt", tone="info")
with top[2]:
    render_card("Costo previsto", value=f"${cost_next:,.0f}", body="Antes de ajustes operativos.", icon="money", tone="warning")
with top[3]:
    render_card("Cobertura solar", value=f"{coverage:,.0f}%", body=f"Ahorro estimado ${saving:,.0f}.", icon="chart", tone=risk_tone)

st.markdown("""
<style>
/* Estilo para banner del Motor Predictivo IA */
.prediction-banner {
    background: rgba(235, 175, 54, 0.08);
    border: 1px dashed rgba(235, 175, 54, 0.3);
    border-radius: 16px;
    padding: 1rem 1.2rem;
    margin: 1.5rem 0;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.prediction-banner__icon {
    font-size: 1.8rem;
    animation: bounce-pulse 2.5s infinite ease-in-out;
}
@keyframes bounce-pulse {
    0% { transform: translateY(0) scale(1); opacity: 0.9; }
    50% { transform: translateY(-4px) scale(1.03); opacity: 1; }
    100% { transform: translateY(0) scale(1); opacity: 0.9; }
}
.prediction-banner__text {
    font-size: 0.92rem;
    color: #9AB0BB;
    line-height: 1.5;
}
.prediction-banner__title {
    font-weight: 700;
    color: #EBAF36;
    margin-bottom: 0.2rem;
}
</style>
""", unsafe_allow_html=True)

# Banner premium indicando motor predictivo y simulación IA activa
st.markdown(f"""
<div class="prediction-banner">
    <div class="prediction-banner__icon">🔮</div>
    <div class="prediction-banner__text">
        <div class="prediction-banner__title">Motor Predictivo y Simulación IA Activa</div>
        Nuestro agente orquesta y proyecta automáticamente la generación solar fotovoltaica, demanda y riesgos de continuidad en {CIUDAD} para las próximas 24h, 48h y 72h.
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")
render_section_header("Orquestación Autónoma de Respaldo", "spark", "Orquestador inteligente de baterías y excedentes solares ante apagones.")

st.markdown(
    f"El Agente Solar de {CIUDAD} implementa un **algoritmo de orquestación proactiva** "
    "que vincula las predicciones de apagones con el control físico del banco de baterías "
    "y los excedentes fotovoltaicos. Ajusta el simulador de abajo para ver cómo responde la IA:"
)

# Slider interactivo
sim_riesgo = st.slider(
    "Simular Probabilidad de Apagón para las próximas 24h (%)",
    min_value=0, max_value=100,
    value=int(risk_next) if risk_next > 0 else 45,
    step=5,
    key="sim_riesgo_slider"
)

# Algoritmo de orquestación
capacidad_bateria = empresa_sel.get("capacidad_bateria_kwh", 0.0) or 0.0
es_hogar = (empresa_sel.get("tipo") == "hogar")

if not tiene_baterias:
    st.info(
        "💡 **Simulador Solar Activo:** Actualmente este perfil no posee un banco de baterías físicas "
        "registrado (capacidad = 0 kWh). A continuación se muestra cómo funcionaría el "
        f"Orquestador Autónomo si equiparas tu sistema con el banco de baterías sugerido "
        f"para tus cargas críticas (**{bateria_sugerida:g} kWh**)."
    )
    bateria_sim = bateria_sugerida
else:
    bateria_sim = capacidad_bateria if capacidad_bateria > 0.0 else bateria_sugerida

# Lógica del orquestador basado en el slider
if sim_riesgo >= 40:
    estado_orq = "🔴 MÁXIMA PREVENTIVA"
    desc_orq = (
        "**Acción del Agente IA:** El riesgo de apagón es CRÍTICO. El orquestador ha bloqueado "
        "el uso de la batería para ahorro de OpEx diurno. El 100% de la generación solar sobrante "
        "y energía de la red se destina a cargar las baterías "
        "al 100% de inmediato para asegurar el máximo de horas de respaldo nocturno."
    )
    reserva_target = "100% (Respaldo Total)"
    rutado_solar = "100% a Baterías"
    color_banner = "#B8473F"
elif sim_riesgo >= 20:
    estado_orq = "🟡 RESPALDO PROACTIVO"
    desc_orq = (
        "**Acción del Agente IA:** Riesgo de apagón moderado detectado. El orquestador incrementa el "
        "umbral mínimo de batería (de 20% a 60%). Los excedentes solares de mediodía se desvían de forma "
        "prioritaria al banco de baterías para alcanzar este colchón de seguridad antes del atardecer."
    )
    reserva_target = "60% (Preventivo)"
    rutado_solar = "Batería > Consumo"
    color_banner = "#C88A2E"
else:
    estado_orq = "🟢 OPTIMIZACIÓN OPEX"
    desc_orq = (
        "**Acción del Agente IA:** Riesgo de apagón muy bajo. El orquestador opera en modo de máxima "
        "eficiencia económica: los excedentes solares se inyectan directamente a las cargas internas "
        "para reducir la compra a la red de Air-E, y la batería se descarga de forma "
        "controlada para aplanar la demanda en horas pico."
    )
    reserva_target = "20% (Umbral de Ciclo)"
    rutado_solar = "Consumo Directo (Ahorro)"
    color_banner = "#1E6B5C"

# Mostrar métricas del orquestador
cols_orq = st.columns(4)
with cols_orq[0]:
    st.metric("Modo Orquestador", estado_orq)
with cols_orq[1]:
    st.metric("Objetivo de Carga", reserva_target)
with cols_orq[2]:
    st.metric("Flujo Fotovoltaico", rutado_solar)
with cols_orq[3]:
    consumo_prom = cons_next if cons_next > 0 else (400.0 if not es_hogar else 15.0)
    consumo_hora = (consumo_prom / 24.0)
    pct_carga = 1.0 if sim_riesgo >= 40 else (0.6 if sim_riesgo >= 20 else 0.2)
    autonomia_horas = (bateria_sim * pct_carga) / (consumo_hora if consumo_hora > 0 else 1.0)
    st.metric("Autonomía Apagón", f"{autonomia_horas:.1f} horas")

st.markdown(
    f"""
    <div style="background-color: rgba(30, 30, 30, 0.4); border-left: 4px solid {color_banner}; padding: 15px; border-radius: 4px; margin-bottom: 25px;">
        <p style="margin: 0; font-size: 1rem; color: #f0f2f6;">
            {desc_orq}
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()


if prod_fut:
    render_section_header("Proximos dias", "calendar", "Vista compacta del potencial esperado.")
    preview_cols = st.columns(min(len(prod_fut[:5]), 5))
    for index, (fecha, pred) in enumerate(prod_fut[:5]):
        valor = pred["valor"]
        tone = "success" if valor >= cons_next * 0.6 else "warning" if valor >= cons_next * 0.3 else "danger"
        with preview_cols[index]:
            render_card(
                fecha.strftime("%a %d/%m"),
                value=f"{valor:,.0f} kWh",
                body="Produccion proyectada.",
                icon="calendar",
                tone=tone,
            )
elif not (preds_prod or preds_cons or preds_cost or preds_risk):
    st.info("Aun no hay predicciones generadas para esta empresa.")

st.divider()

show_details = st.toggle("Habilitar Gráficos y Modelos Paramétricos", key="pred_detalles", help="Profundiza en las estimaciones por rango de horas e índices de confianza.")
if not show_details:
    st.caption("👈 Activa este interruptor para examinar los gráficos de tendencia, recálculos de horizonte y raw data.")
    st.stop()

render_section_header("Análisis de Tendencias", "chart", "Confianza de la IA, horizontes y desglose de problemáticas clave.")
st.caption(f"ℹ️ El motor predictivo evalúa el impacto financiero de las tarifas comerciales (Air-E) y la probabilidad de apagones meteorológicos en {CIUDAD}.")

h_col, hr_btn_col = st.columns([1, 3])
with h_col:
    # Restricción estricta de horizontes a 24h, 48h y 72h
    horizonte = st.selectbox("Horizonte a evaluar", [24, 48, 72], index=2, format_func=lambda x: f"Próximas {x}h")
with hr_btn_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↻ Recalcular con este horizonte", key="btn_recalc_horizont"):
        with st.spinner("⏳ Actualizando motores de predicción..."):
            resultado = api_post(f"/predicciones/generar/{empresa_id}", params={"horas_horizonte": horizonte})
            if resultado:
                st.success(f"Predicciones actualizadas: {resultado.get('total_predicciones_guardadas', 0)}")
                st.rerun()

tab1, tab2 = st.tabs([
    "Continuidad & Resiliencia (Riesgo de Apagón y Banco de Baterías)",
    "Costos Operativos & Ahorro (Proyecciones de Gasto y Banco de Paneles)"
])

with tab1:
    st.markdown("### Proyección de Continuidad y Estado de Baterías")
    preds = api_get(f"/predicciones/{empresa_id}", params={"tipo": "riesgo_apagon"})
    if preds:
        df = pd.DataFrame(preds)
        df["fecha_objetivo"] = pd.to_datetime(df["fecha_objetivo"])
        df = df.sort_values("fecha_objetivo")
        limit_time = pd.Timestamp.now() + pd.Timedelta(hours=horizonte)
        df_filtered = df[df["fecha_objetivo"] <= limit_time]
        
        if not df_filtered.empty:
            unidad = df_filtered["unidad"].iloc[0] if "unidad" in df_filtered.columns else "%"
            confianza = df_filtered["confianza_pct"].mean() if "confianza_pct" in df_filtered.columns else 0
            
            capacidad_bateria = empresa_sel.get("capacidad_bateria_kwh", 0.0)
            es_hogar = (empresa_sel.get("tipo") == "hogar")
            tiene_baterias = (capacidad_bateria > 0.0)
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Puntos Evaluados", len(df_filtered))
            with m2:
                st.metric("Confianza IA", f"{confianza:.0f}%")
            with m3:
                max_riesgo = df_filtered["valor"].max()
                st.metric("Riesgo Máximo", f"{max_riesgo:.0f}%")
                
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=df_filtered["fecha_objetivo"],
                    y=df_filtered["valor"],
                    name="Probabilidad de Apagón",
                    text=df_filtered["valor"].round(1).astype(str) + "%",
                    textposition="outside",
                    marker_color="#B8473F"
                )
            )
            fig.update_layout(xaxis_title="Fecha y Hora", yaxis_title="Riesgo (%)", height=350, yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
            
            if tiene_baterias:
                cap_label = f"**{capacidad_bateria:.1f} kWh**" if capacidad_bateria > 0.0 else "**Activo (Inferencia de Historial)**"
                st.success(
                    f"🔋 **Respaldo Físico Disponible:** Cuentas con un banco de baterías {cap_label} "
                    f"que amortigua los riesgos del {max_riesgo:.0f}% proyectados anteriormente. "
                    f"El orquestador mantendrá una reserva objetivo adecuada al horizonte seleccionado."
                )
            else:
                st.warning(
                    f"⚠️ **Sin Baterías Físicas:** No registras banco de baterías en tu perfil. "
                    f"Bajo un apagón en este horizonte de **{horizonte}h**, quedarías sin energía de respaldo. "
                    + (
                        f"Recomendamos instalar un almacenamiento de **{bateria_sugerida:g} kWh**, que mantendría tus "
                        f"cargas críticas (nevera, luces, internet) durante unas **{autonomia_criticas:.0f} horas**."
                        if autonomia_criticas else
                        f"Recomendamos instalar un almacenamiento de **{bateria_sugerida:g} kWh** "
                        f"para asegurar hasta **{bateria_sugerida / (cons_next/24.0 if cons_next else 1.0):.1f} horas** de continuidad autónoma completa."
                    )
                )
                
            st.markdown("**Desglose de Predicción:**")
            st.dataframe(df_filtered[["fecha_objetivo", "valor", "unidad", "confianza_pct"]], use_container_width=True, hide_index=True)
        else:
            st.info(f"No hay predicciones de apagones activas para las próximas {horizonte} horas.")
    else:
        st.info("No hay predicciones registradas para el riesgo de continuidad.")

with tab2:
    st.markdown("### Proyección de Costo Operativo y Offset Fotovoltaico")
    preds_cost = api_get(f"/predicciones/{empresa_id}", params={"tipo": "costo"})
    preds_solar = api_get(f"/predicciones/{empresa_id}", params={"tipo": "produccion_solar"})
    
    if preds_cost:
        df_cost = pd.DataFrame(preds_cost)
        df_cost["fecha_objetivo"] = pd.to_datetime(df_cost["fecha_objetivo"])
        df_cost = df_cost.sort_values("fecha_objetivo")
        limit_time = pd.Timestamp.now() + pd.Timedelta(hours=horizonte)
        df_cost_filtered = df_cost[df_cost["fecha_objetivo"] <= limit_time]
        
        if not df_cost_filtered.empty:
            costo_total = df_cost_filtered["valor"].sum()
            confianza_cost = df_cost_filtered["confianza_pct"].mean() if "confianza_pct" in df_cost_filtered.columns else 0
            
            tiene_paneles = (empresa_sel.get("capacidad_paneles_kw", 0.0) > 0.0)
            solar_total = 0.0
            
            if preds_solar:
                df_solar = pd.DataFrame(preds_solar)
                df_solar["fecha_objetivo"] = pd.to_datetime(df_solar["fecha_objetivo"])
                df_solar = df_solar.sort_values("fecha_objetivo")
                df_solar_filtered = df_solar[df_solar["fecha_objetivo"] <= limit_time]
                if not df_solar_filtered.empty:
                    solar_total = df_solar_filtered["valor"].sum()
            
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                st.metric("Gasto Estimado de Red", f"${costo_total:,.0f} COP")
            with mc2:
                if tiene_paneles:
                    st.metric("Aporte Solar Previsto", f"{solar_total:,.1f} kWh")
                else:
                    st.metric("Aporte Solar Físico", "0.0 kWh")
            with mc3:
                tarifa = float(empresa_sel.get("tarifa_kwh", 943.0))
                gasto_mitigado = solar_total * tarifa
                st.metric("Ahorro Estimado COP", f"${gasto_mitigado:,.0f} COP")
                
            from plotly.subplots import make_subplots
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Bar(
                    x=df_cost_filtered["fecha_objetivo"],
                    y=df_cost_filtered["valor"],
                    name="Costo de Red (COP)",
                    marker_color="#1E6B5C",
                ),
                secondary_y=False
            )
            
            if tiene_paneles and solar_total > 0.0:
                df_solar_aligned = df_solar_filtered[df_solar_filtered["fecha_objetivo"].isin(df_cost_filtered["fecha_objetivo"])]
                if not df_solar_aligned.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=df_solar_aligned["fecha_objetivo"],
                            y=df_solar_aligned["valor"],
                            name="Producción Solar (kWh)",
                            line=dict(color="#C88A2E", width=3),
                            mode="lines+markers"
                        ),
                        secondary_y=True
                    )
            
            fig.update_layout(
                title_text="Tendencia de Gasto de Red vs. Aporte Fotovoltaico",
                height=380,
                xaxis_title="Fecha y Hora"
            )
            fig.update_yaxes(title_text="Costo Operativo (COP)", secondary_y=False)
            if tiene_paneles:
                fig.update_yaxes(title_text="Generación Solar (kWh)", secondary_y=True)
                
            st.plotly_chart(fig, use_container_width=True)
            
            if tiene_paneles:
                cap_paneles = empresa_sel.get('capacidad_paneles_kw', 0.0) or 0.0
                cap_paneles_label = f"de **{cap_paneles:.1f} kW**" if cap_paneles > 0.0 else "**Activa (Inferencia de Historial)**"
                st.success(
                    f"☀️ **Banco de Paneles Solar Activo:** Tu infraestructura {cap_paneles_label} "
                    f"reducirá tu consumo de red en **{solar_total:,.1f} kWh**, lo que equivale a un ahorro directo proyectado "
                    f"de **${gasto_mitigado:,.0f} COP** en este horizonte de {horizonte}h."
                )
            else:
                pot_ahorro = sistema_sugerido.get("ahorro_mes_cop") or kwp_sugerido * 5.0 * 0.8 * 30 * tarifa
                st.warning(
                    f"💡 **Recomendación de Banco Solar:** Actualmente este perfil no cuenta con paneles fotovoltaicos activos. "
                    f"Si decidieras instalar el sistema sugerido para tu consumo de **{kwp_sugerido:g} kWp**, "
                    f"podrías mitigar hasta **${(pot_ahorro / 30.0) * (horizonte / 24.0):,.0f} COP** del costo total de red de este horizonte."
                )
                
            st.markdown("**Desglose de Costo Operativo Proyectado:**")
            st.dataframe(df_cost_filtered[["fecha_objetivo", "valor", "unidad", "confianza_pct"]], use_container_width=True, hide_index=True)
        else:
            st.info(f"No hay predicciones de costos activas para las próximas {horizonte} horas.")
    else:
        st.info("No hay predicciones de costos registradas.")
