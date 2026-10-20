"""Pagina de consumo con resumen compacto y detalle opcional."""

from datetime import datetime, timedelta
import os
import sys

import pandas as pd
import requests
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import (
    API_BASE_URL,
    API_PREFIX,
    api_get,
    api_post,
    get_active_scenario,
    get_current_user,
    is_authenticated,
)
from design import render_card, render_hero, render_section_header
from ui import render_user_sidebar


st.set_page_config(page_title="Consumo Energetico", layout="wide", initial_sidebar_state="expanded")
render_user_sidebar()

if not is_authenticated():
    st.warning("Debe iniciar sesion primero.")
    st.stop()

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

consumos_mes = api_get(f"/consumo/empresa/{empresa_id}", params={"days": 30}) or []
consumos_anterior = api_get(f"/consumo/empresa/{empresa_id}", params={"days": 60}) or []
tarifa = empresa_sel.get("tarifa_kwh", 943.0)

if consumos_mes:
    df_mes = pd.DataFrame(consumos_mes)
    df_mes["fecha"] = pd.to_datetime(df_mes["fecha"])
    df_anterior = pd.DataFrame(consumos_anterior)
    if not df_anterior.empty:
        df_anterior["fecha"] = pd.to_datetime(df_anterior["fecha"])
        limite = datetime.now() - timedelta(days=30)
        df_anterior = df_anterior[df_anterior["fecha"] < limite]

    consumo_mes = df_mes["consumo_kwh"].sum()
    costo_mes = df_mes["costo_cop"].fillna(df_mes["consumo_kwh"] * tarifa).sum()
    produccion_mes = df_mes["produccion_solar_kwh"].fillna(0).sum() if "produccion_solar_kwh" in df_mes.columns else 0
    ahorro_solar = produccion_mes * tarifa
    consumo_anterior = df_anterior["consumo_kwh"].sum() if not df_anterior.empty else 0
    delta_pct = ((consumo_mes - consumo_anterior) / consumo_anterior * 100) if consumo_anterior > 0 else 0
else:
    df_mes = pd.DataFrame()
    consumo_mes = costo_mes = produccion_mes = ahorro_solar = delta_pct = 0

if delta_pct > 10:
    hero_tone = "danger"
    hero_text = f"El gasto del periodo subio {delta_pct:.0f}% frente al mes anterior."
elif delta_pct < -5:
    hero_tone = "success"
    hero_text = f"El consumo bajo {abs(delta_pct):.0f}% frente al mes anterior."
else:
    hero_tone = "info"
    hero_text = "El comportamiento del mes se mantiene estable frente al periodo anterior."

render_hero(
    "Consumo y gasto",
    hero_text,
    icon="bolt",
    eyebrow=empresa_sel["nombre"],
    tone=hero_tone,
)

if not consumos_mes:
    st.info("Aún no hay registros de consumo para esta empresa.")
else:
    cards = st.columns(4)
    with cards[0]:
        render_card("Costo estimado", value=f"${costo_mes:,.0f}", body="Últimos 30 días.", icon="money", tone=hero_tone)
    with cards[1]:
        render_card("Energía consumida", value=f"{consumo_mes:,.0f} kWh", body="Acumulado mensual.", icon="bolt", tone="info")
    with cards[2]:
        render_card("Producción solar", value=f"{produccion_mes:,.0f} kWh", body="Generación reportada.", icon="sun", tone="success")
    with cards[3]:
        render_card("Ahorro solar", value=f"${ahorro_solar:,.0f}", body="Estimado compensado.", icon="chart", tone="warning")

st.divider()

show_details = st.toggle("Habilitar Herramientas de Datos", key="consumo_detalles", help="Baja datos, sube CSVs o edita historiales")
if not show_details:
    st.caption("👈 Activa este interruptor para cargar archivos o revisar la tabla histórica.")
    st.stop()

render_section_header("Gestión de Datos", "settings", "Sube archivos o modifica registros individualmente.")
st.caption("Referencia rápida: 'Demanda pico' es la máxima potencia requerida en un intervalo; ayuda a detectar sobrecargas y penalizaciones.")

tab1, tab2, tab3, tab4 = st.tabs(["Histórico", "Cargar archivo CSV", "Registro manual", "Registrar Factura Mensual"])

with tab1:
    st.markdown(" ") # Spacer 
    days = st.slider("Días a mostrar en la tabla", 7, 365, 30, key="dias_hist", help="Filtra cuántos registros quieres previsualizar.")
    consumos = api_get(f"/consumo/empresa/{empresa_id}", params={"days": days})

    if consumos:
        df = pd.DataFrame(consumos)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.sort_values("fecha", ascending=False)
        metrics = st.columns(3)
        with metrics[0]:
            st.metric("Total registros", len(df))
        with metrics[1]:
            st.metric("Consumo total", f"{df['consumo_kwh'].sum():.1f} kWh")
        with metrics[2]:
            total_cost = df["costo_cop"].fillna(df["consumo_kwh"] * empresa_sel["tarifa_kwh"]).sum()
            st.metric("Costo total", f"${total_cost:,.0f}")

        # Optimizando la tabla para no saturar al instante
        cols_mostrar = [c for c in ["fecha", "consumo_kwh", "costo_cop", "demanda_pico_kw", "produccion_solar_kwh", "nivel_bateria_pct", "periodo"] if c in df.columns]
        st.dataframe(
            df[cols_mostrar].head(15),
            use_container_width=True,
            hide_index=True,
        )
        
        if len(df) > 15:
            with st.expander(f"Ver los {len(df)-15} registros restantes"):
                st.dataframe(
                    df[cols_mostrar].iloc[15:],
                    use_container_width=True,
                    hide_index=True,
                )
    else:
        st.info("Sin registros de consumo.")

with tab2:
    st.markdown(" ") # Spacer
    st.markdown(
        """
        #### Carga Batch de Datos
        - `fecha`: YYYY-MM-DD o YYYY-MM-DD HH:MM:SS
        - `consumo_kwh`: numero requerido
        - Opcionales: `costo_cop`, `demanda_pico_kw`, `produccion_solar_kwh`, `nivel_bateria_pct`, `periodo`
        """
    )

    plantilla = pd.DataFrame(
        {
            "fecha": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "consumo_kwh": [120.5, 135.2, 110.8],
            "costo_cop": [113550, 127430, 104484],
            "demanda_pico_kw": [15.2, 18.4, 14.1],
            "produccion_solar_kwh": [45.0, 50.2, 42.8],
            "nivel_bateria_pct": [85.0, 78.0, 90.0],
            "periodo": ["diario", "diario", "diario"],
        }
    )
    csv_template = plantilla.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar plantilla CSV", data=csv_template, file_name="plantilla_consumo.csv", mime="text/csv")

    archivo = st.file_uploader("Selecciona un archivo CSV o XLSX", type=["csv", "xlsx", "xls"])
    if archivo:
        st.success(f"Archivo seleccionado: {archivo.name} ({archivo.size / 1024:.1f} KB)")
        try:
            df_preview = pd.read_csv(archivo) if archivo.name.endswith(".csv") else pd.read_excel(archivo)
            st.dataframe(df_preview.head(), use_container_width=True)
            archivo.seek(0)
        except Exception as exc:
            st.error(f"Error leyendo archivo: {exc}")

        if st.button("Subir y procesar", type="primary"):
            token = st.session_state.get("token")
            files = {"file": (archivo.name, archivo.getvalue(), archivo.type)}
            try:
                response = requests.post(
                    f"{API_BASE_URL}{API_PREFIX}/consumo/upload/{empresa_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    files=files,
                    params={"escenario": get_active_scenario()},
                    timeout=120,
                )
                if response.status_code == 200:
                    payload = response.json()
                    st.success(payload.get("mensaje", "Carga completada."))
                    st.metric("Registros insertados", payload.get("registros_insertados", 0))
                    if payload.get("errores"):
                        with st.expander(f"Errores detectados ({len(payload['errores'])})"):
                            for error in payload["errores"][:50]:
                                st.text(error)
                else:
                    detalle = response.json().get("detail", response.text)
                    st.error(f"Error {response.status_code}: {detalle}")
            except Exception as exc:
                st.error(f"Error en carga: {exc}")

with tab3:
    st.markdown(" ") # Spacer
    with st.form("registro_manual"):
        col_a, col_b = st.columns(2)
        with col_a:
            fecha = st.date_input("Fecha")
            hora = st.time_input("Hora")
            consumo = st.number_input("Consumo (kWh)", min_value=0.0, step=0.1)
            costo = st.number_input("Costo (COP) opcional", min_value=0.0, step=100.0)
        with col_b:
            demanda = st.number_input("Demanda pico (kW) opcional", min_value=0.0, step=0.1)
            produccion = st.number_input("Produccion solar (kWh) opcional", min_value=0.0, step=0.1)
            bateria = st.number_input("Bateria (%) opcional", min_value=0.0, max_value=100.0, step=1.0)
            periodo = st.selectbox("Periodo", ["diario", "horario", "mensual"])

        if st.form_submit_button("Guardar"):
            payload = {
                "empresa_id": empresa_id,
                "fecha": datetime.combine(fecha, hora).isoformat(),
                "consumo_kwh": consumo,
                "costo_cop": costo or None,
                "demanda_pico_kw": demanda or None,
                "produccion_solar_kwh": produccion,
                "nivel_bateria_pct": bateria or None,
                "periodo": periodo,
            }
            response = api_post("/consumo/", json=payload)
            if response:
                st.success("Registro guardado.")
                st.rerun()

with tab4:
    st.markdown(" ") # Spacer
    render_section_header("Registrar Recibo de Luz Mensual", "report", "Ingresa los datos resumidos de tu factura de energia.")
    
    with st.form("registro_factura_mensual"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            anio_fact = st.selectbox("Año de la factura", [2025, 2026, 2027], index=1)
            mes_fact_lbl = st.selectbox("Mes de la factura", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=4)
            meses_map = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
            mes_fact = meses_map[mes_fact_lbl]
            
            st.markdown("**Fechas Preventivas (Air-E)**")
            fecha_emision = st.date_input("Fecha de Emisión", value=None, help="La fecha en que se expidió la factura.")
            fecha_pago = st.date_input("Fecha Oportuna de Pago", value=None, help="La fecha límite para pagar a tiempo.")
            fecha_suspension = st.date_input("Suspensión a partir de", value=None, help="La fecha a partir de la cual se suspende el servicio si no pagas.")

        with col_m2:
            consumo_mensual = st.number_input(
                "Consumo mensual total (kWh)",
                min_value=1.0,
                value=250.0,
                step=10.0,
                help="Busca en tu recibo de luz el consumo total facturado en el mes (ej: 52 kWh)."
            )
            costo_energia = st.number_input(
                "Costo del concepto de Energía (COP)",
                min_value=0.0,
                value=180000.0,
                step=5000.0,
                help="El valor del concepto de Energía Activa o Consumo. Este cobro es el único que puede compensarse con paneles solares."
            )
            costo_total = st.number_input(
                "Monto total facturado (COP) - Opcional",
                min_value=0.0,
                value=0.0,
                step=5000.0,
                help="El valor total a pagar de tu recibo, incluyendo otros cobros ajenos al consumo (aseo, alumbrado, etc.)."
            )

        if st.form_submit_button("Guardar e Interpolación"):
            if costo_energia <= 0:
                st.error("Por favor, ingresa un costo de energía válido (mayor a $0 COP).")
            else:
                payload_mensual = {
                    "empresa_id": empresa_id,
                    "anio": anio_fact,
                    "mes": mes_fact,
                    "consumo_total_kwh": consumo_mensual,
                    "costo_energia_cop": costo_energia,
                    "costo_total_cop": costo_total if costo_total > 0 else None,
                    "fecha_emision": datetime.combine(fecha_emision, datetime.min.time()).isoformat() if fecha_emision else None,
                    "fecha_pago_oportuno": datetime.combine(fecha_pago, datetime.min.time()).isoformat() if fecha_pago else None,
                    "fecha_suspension": datetime.combine(fecha_suspension, datetime.min.time()).isoformat() if fecha_suspension else None,
                }
                response = api_post("/consumo/monthly", json=payload_mensual)
                if response:
                    st.success(response.get("mensaje", "Factura mensual registrada y distribuida exitosamente."))
                    st.rerun()
