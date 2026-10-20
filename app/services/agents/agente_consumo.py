"""
Agente de Consumo.
Analiza patrones de consumo y detecta desperdicios o anomalías.
"""
from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
import statistics

from app.models.models import ConsumoEnergetico, Empresa


class AgenteConsumo:
    """Analiza patrones de consumo energético."""

    def analizar(self, db: Session, empresa: Empresa, days: int = 30) -> Dict:
        """Detecta patrones, desperdicios y anomalías."""
        since = datetime.now() - timedelta(days=days)
        escenario = empresa.escenario_default or "demo"
        consumos = (
            db.query(ConsumoEnergetico)
            .filter(
                ConsumoEnergetico.empresa_id == empresa.id,
                ConsumoEnergetico.fecha >= since,
                ConsumoEnergetico.escenario == escenario,
            )
            .order_by(ConsumoEnergetico.fecha)
            .all()
        )

        if not consumos:
            return {
                "total_kwh": 0.0,
                "promedio_diario_kwh": 0.0,
                "costo_total_cop": 0.0,
                "anomalias": [],
                "mensaje": "No hay datos de consumo registrados.",
            }

        valores = [c.consumo_kwh for c in consumos]
        total = sum(valores)
        promedio = total / len(valores)
        std = statistics.stdev(valores) if len(valores) > 1 else 0
        costo_total = sum(c.costo_cop or (c.consumo_kwh * empresa.tarifa_kwh) for c in consumos)

        # Detección de anomalías: valores > promedio + 2*std
        umbral_anomalia = promedio + 2 * std
        anomalias = []
        for c in consumos:
            if c.consumo_kwh > umbral_anomalia and umbral_anomalia > 0:
                anomalias.append({
                    "fecha": c.fecha.isoformat(),
                    "consumo_kwh": c.consumo_kwh,
                    "exceso_pct": round((c.consumo_kwh / promedio - 1) * 100, 1),
                })

        # Demanda pico
        demanda_pico = max(
            (c.demanda_pico_kw for c in consumos if c.demanda_pico_kw is not None),
            default=0,
        )

        # Día con mayor consumo
        max_consumo = max(consumos, key=lambda c: c.consumo_kwh)

        return {
            "total_kwh": round(total, 2),
            "promedio_diario_kwh": round(promedio, 2),
            "std_kwh": round(std, 2),
            "costo_total_cop": round(costo_total, 0),
            "demanda_pico_kw": round(demanda_pico, 2),
            "dia_mayor_consumo": {
                "fecha": max_consumo.fecha.isoformat(),
                "consumo_kwh": max_consumo.consumo_kwh,
            },
            "anomalias": anomalias,
            "num_anomalias": len(anomalias),
            "tarifa_kwh": empresa.tarifa_kwh,
            "mensaje": (
                f"Consumo promedio: {promedio:.1f} kWh/día. "
                f"Total {days} días: {total:.0f} kWh ({costo_total:,.0f} COP). "
                f"Anomalías detectadas: {len(anomalias)}."
            ),
        }


agente_consumo = AgenteConsumo()
