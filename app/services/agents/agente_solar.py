"""
Agente de Análisis Solar.
Procesa datos de radiación y calcula potencial de generación.
"""
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.models.models import RadiacionSolar, Empresa


class AgenteAnalisisSolar:
    """Analiza radiación y estima potencial de generación solar."""

    EFICIENCIA_PANELES = 0.18  # 18% típico
    PERFORMANCE_RATIO = 0.80   # 80% (pérdidas por cables, inversor, suciedad, temperatura)

    def calcular_produccion_estimada_kwh(
        self,
        ghi_kwh_m2_dia: float,
        capacidad_paneles_kw: float,
    ) -> float:
        """
        Estima producción solar (kWh) según GHI y capacidad instalada.
        Fórmula: Producción ≈ GHI × Capacidad × PR
        """
        if not ghi_kwh_m2_dia or not capacidad_paneles_kw:
            return 0.0
        return round(ghi_kwh_m2_dia * capacidad_paneles_kw * self.PERFORMANCE_RATIO, 2)

    def analizar(self, db: Session, empresa: Empresa, days: int = 30) -> Dict:
        """Analiza la radiación reciente para una empresa."""
        since = datetime.now() - timedelta(days=days)
        q = db.query(RadiacionSolar).filter(RadiacionSolar.fecha >= since)
        escenario = empresa.escenario_default or "demo"
        q = q.filter(RadiacionSolar.escenario == escenario)
        datos = q.order_by(RadiacionSolar.fecha).all()

        if not datos:
            return {
                "promedio_ghi": None,
                "max_ghi": None,
                "min_ghi": None,
                "produccion_estimada_diaria_kwh": 0.0,
                "produccion_estimada_mensual_kwh": 0.0,
                "ahorro_estimado_mensual_cop": 0.0,
                "mensaje": "No hay datos de radiación disponibles. Sincronice con NASA POWER.",
            }

        ghi_values = [d.ghi for d in datos if d.ghi]
        promedio_ghi = sum(ghi_values) / len(ghi_values) if ghi_values else 0
        max_ghi = max(ghi_values) if ghi_values else 0
        min_ghi = min(ghi_values) if ghi_values else 0

        prod_diaria = self.calcular_produccion_estimada_kwh(
            promedio_ghi, empresa.capacidad_paneles_kw
        )
        prod_mensual = prod_diaria * 30
        ahorro_mensual = prod_mensual * empresa.tarifa_kwh

        return {
            "promedio_ghi": round(promedio_ghi, 2),
            "max_ghi": round(max_ghi, 2),
            "min_ghi": round(min_ghi, 2),
            "produccion_estimada_diaria_kwh": prod_diaria,
            "produccion_estimada_mensual_kwh": round(prod_mensual, 2),
            "ahorro_estimado_mensual_cop": round(ahorro_mensual, 0),
            "dias_analizados": len(datos),
            "mensaje": (
                f"{getattr(empresa, 'ciudad', None) or get_settings().LOCATION_CITY} tiene radiación excelente: promedio de {promedio_ghi:.2f} kWh/m²/día. "
                f"Con {empresa.capacidad_paneles_kw} kW instalados, podría generar "
                f"~{prod_diaria:.1f} kWh/día."
            ),
        }


agente_solar = AgenteAnalisisSolar()
