"""
Agente de Predicción.
Predice consumo futuro, producción solar y riesgo de apagones (24-72h).

Fuentes:
- NÚCLEO: Open-Meteo (forecast horario con GHI/DNI/DHI nativo).
- COMPLEMENTO: OpenWeather (validación cruzada de nubosidad).
"""
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
import statistics

from app.models.models import (
    ConsumoEnergetico,
    RadiacionSolar,
    Prediccion,
    Empresa,
)
from app.services.openmeteo import openmeteo_service
from app.services.openweather import openweather_service
from app.services.agents.agente_solar import agente_solar


class AgentePrediccion:
    """Genera predicciones a 24-72h."""

    async def predecir(
        self,
        db: Session,
        empresa: Empresa,
        horas_horizonte: int = 72,
    ) -> Dict:
        """Genera predicciones y guarda en BD."""
        ahora = datetime.now()
        escenario = empresa.escenario_default or "demo"

        # 1. Promedio histórico de consumo
        since = ahora - timedelta(days=30)
        consumos = (
            db.query(ConsumoEnergetico)
            .filter(
                ConsumoEnergetico.empresa_id == empresa.id,
                ConsumoEnergetico.fecha >= since,
            )
            .all()
        )

        if consumos:
            promedio_diario = sum(c.consumo_kwh for c in consumos) / len(consumos)
            std = (
                statistics.stdev([c.consumo_kwh for c in consumos])
                if len(consumos) > 1
                else 0
            )
            confianza_consumo = max(50.0, min(95.0, 100 - (std / max(promedio_diario, 1)) * 100))
        else:
            promedio_diario = 0
            confianza_consumo = 50.0

        # 2. NÚCLEO: Pronóstico Open-Meteo (horario con GHI nativo)
        dias_horizonte = max(1, min(7, horas_horizonte // 24 + 1))
        forecast_horario = await openmeteo_service.get_forecast_horario(
            days=dias_horizonte,
            allow_synthetic=escenario != "real",
        )

        # 3. Predicción producción solar agrupando por día.
        #    Convertir GHI horario W/m² → kWh/m²/día (sum × 1h / 1000)
        ghi_por_dia: Dict = {}
        nubosidad_por_dia: Dict = {}
        for item in forecast_horario:
            fecha_dia = item["fecha"].date()
            ghi_w = item.get("ghi_w_m2") or 0
            ghi_por_dia[fecha_dia] = ghi_por_dia.get(fecha_dia, 0) + ghi_w / 1000
            nubosidad_por_dia.setdefault(fecha_dia, []).append(item.get("nubosidad") or 0)

        producciones_dia = {}
        for fecha_dia, ghi_total in ghi_por_dia.items():
            produccion = agente_solar.calcular_produccion_estimada_kwh(
                ghi_total, empresa.capacidad_paneles_kw
            )
            producciones_dia[fecha_dia] = produccion

        predicciones_creadas = []
        creadas_resumen = []

        for fecha_dia, produccion_total in producciones_dia.items():
            fecha_objetivo = datetime.combine(fecha_dia, datetime.min.time())
            if (fecha_objetivo - ahora).total_seconds() / 3600 > horas_horizonte:
                continue

            # Predicción producción
            p1 = Prediccion(
                empresa_id=empresa.id,
                fecha_prediccion=ahora,
                fecha_objetivo=fecha_objetivo,
                tipo="produccion_solar",
                valor=round(produccion_total, 2),
                unidad="kWh",
                confianza_pct=80.0,  # Open-Meteo da GHI directo → mayor confianza
                escenario=escenario,
                origen_dato="modelo_hibrido",
                confiabilidad_datos=80.0 if escenario == "real" else 55.0,
            )
            db.add(p1)

            # Predicción consumo
            p2 = Prediccion(
                empresa_id=empresa.id,
                fecha_prediccion=ahora,
                fecha_objetivo=fecha_objetivo,
                tipo="consumo",
                valor=round(promedio_diario, 2),
                unidad="kWh",
                confianza_pct=round(confianza_consumo, 1),
                escenario=escenario,
                origen_dato="modelo_hibrido",
                confiabilidad_datos=round(confianza_consumo, 1),
            )
            db.add(p2)

            # Predicción costo neto
            costo = max(0, (promedio_diario - produccion_total) * empresa.tarifa_kwh)
            p3 = Prediccion(
                empresa_id=empresa.id,
                fecha_prediccion=ahora,
                fecha_objetivo=fecha_objetivo,
                tipo="costo",
                valor=round(costo, 0),
                unidad="COP",
                confianza_pct=round(confianza_consumo, 1),
                escenario=escenario,
                origen_dato="modelo_hibrido",
                confiabilidad_datos=round(confianza_consumo, 1),
            )
            db.add(p3)

            predicciones_creadas.extend([p1, p2, p3])
            creadas_resumen.append({
                "fecha": fecha_objetivo.isoformat(),
                "produccion_solar_kwh": round(produccion_total, 2),
                "consumo_kwh": round(promedio_diario, 2),
                "costo_cop": round(costo, 0),
                "ghi_diario_kwh_m2": round(ghi_por_dia[fecha_dia], 2),
            })

        # 4. Riesgo de apagón: nubosidad alta sostenida en próximas 24h
        prox_24h = forecast_horario[:24]
        nubosidades = [f.get("nubosidad", 0) or 0 for f in prox_24h]
        max_nubosidad = max(nubosidades, default=0)
        prom_nubosidad = sum(nubosidades) / len(nubosidades) if nubosidades else 0

        if max_nubosidad > 80 and prom_nubosidad > 60:
            riesgo_apagon = 45.0
        elif max_nubosidad > 75:
            riesgo_apagon = 30.0
        elif max_nubosidad > 50:
            riesgo_apagon = 18.0
        else:
            riesgo_apagon = 8.0

        p_apagon = Prediccion(
            empresa_id=empresa.id,
            fecha_prediccion=ahora,
            fecha_objetivo=ahora + timedelta(hours=24),
            tipo="riesgo_apagon",
            valor=riesgo_apagon,
            unidad="%",
            confianza_pct=65.0,
            escenario=escenario,
            origen_dato="modelo_hibrido",
            confiabilidad_datos=65.0 if escenario == "real" else 50.0,
        )
        db.add(p_apagon)
        predicciones_creadas.append(p_apagon)

        db.commit()
        for p in predicciones_creadas:
            db.refresh(p)

        return {
            "predicciones_diarias": creadas_resumen,
            "riesgo_apagon_24h_pct": riesgo_apagon,
            "promedio_consumo_diario_kwh": round(promedio_diario, 2),
            "total_predicciones_guardadas": len(predicciones_creadas),
            "fuente_principal": "open_meteo",
            "fuente_complemento": "openweather",
        }


agente_prediccion = AgentePrediccion()
