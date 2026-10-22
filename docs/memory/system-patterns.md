# 📐 Patrones del Sistema y Lógica de Dominio

Patrones recurrentes y modelos de cálculo del Agente Solar (Ka'i).

## 1. Orquestación Autónoma de Almacenamiento (Baterías)
- Riesgo de apagón alto (>= 40%): carga al 100% con excedentes y red (respaldo total).
- Riesgo moderado (20-39%): reserva mínima sube de 20% a 60%; excedentes de mediodía a baterías.
- Riesgo bajo (< 20%): umbral de ciclo 20%; excedentes al consumo y descarga en horas pico.

## 2. Capa de Datos Híbrida (Real + Sintética)
- Consulta en tiempo real a APIs climáticas (Open-Meteo; también NASA POWER, OpenWeather y PVGIS).
- Si la conexión falla o es demo, conmuta a `scripts/demo_data/*.json`.
- Indicador transparente de `origen_dato` (`real_api`, `json_demo` o `synthetic_fallback`).
- Escenario `demo` o `real`: admin y analista pueden cambiarlo; los demás ven el suyo.

## 3. Modelo Financiero y Tarifario
- Tarifa base de referencia: $890 COP/kWh (Air-E La Guajira); el código aún usa $943 por defecto.
- Cálculo de ROI: Inversión inicial / (Ahorro solar mensual - Costo mantenimiento).
- Proyección a 5 y 10 años diferenciada por perfil Residencial vs PYME.
- Consumo por aparato: potencia (W) × horas al día × cantidad × 30 / 1000 (kWh/mes).

## 4. Adaptabilidad de Interfaz
- Perfil según el tipo de entidad registrado: hogar = residencial; el resto = comercial.
- Renderizado de métricas adaptadas: lenguaje coloquial vs KPIs de ingeniería.

## 5. Alertas del Municipio
- Umbrales: calor 36/38 °C, sensación térmica 41 °C, lluvia 20/50 mm, viento 40 km/h y ráfagas 60 km/h.
- El pronóstico se consulta como máximo cada 10 minutos y se comparte entre usuarios.
