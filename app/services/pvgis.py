"""
Servicio PVGIS (OPCIONAL).

PVGIS provee datos climatológicos típicos (TMY) de 15+ años, ideal como
LÍNEA BASE para la ubicación configurada. Se usa puntualmente, no en runtime continuo.

Endpoints clave (PVGIS API v5_3 — la más estable disponible públicamente):
- /tmy: Año Meteorológico Típico (datos horarios típicos de un año "promedio").
- /MRcalc: Radiación mensual.
- /PVcalc: Estimación de generación PV (requiere capacidad).

Nota: PVGIS "v6" se refiere al portal/dataset interno; la API REST pública
se mantiene en v5_3 con los mismos endpoints.

Documentación: https://joint-research-centre.ec.europa.eu/pvgis-online-tool/getting-started-pvgis/api-non-interactive-service_en
"""
import httpx
from typing import Dict, Optional, List

from app.core.config import get_settings

settings = get_settings()


class PVGISService:
    """Cliente PVGIS para baseline climatológico y simulación PV."""

    def __init__(self):
        self.base_url = settings.PVGIS_BASE_URL
        self.lat = settings.LOCATION_LAT
        self.lon = settings.LOCATION_LON
        self.enabled = settings.PVGIS_ENABLED

    async def get_tmy(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict:
        """
        Obtiene el Año Meteorológico Típico (TMY) de la ubicación.
        Devuelve resumen estadístico (no las 8760 horas para no saturar BD).
        """
        if not self.enabled:
            return {"disponible": False, "motivo": "PVGIS deshabilitado"}

        params = {
            "lat": lat or self.lat,
            "lon": lon or self.lon,
            "outputformat": "json",
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/tmy", params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                return {"disponible": False, "motivo": f"Error PVGIS: {e}"}

        outputs = data.get("outputs", {}).get("tmy_hourly", [])
        if not outputs:
            return {"disponible": False, "motivo": "TMY vacío"}

        # Resumen estadístico (sin volcar 8760 puntos)
        ghi_values = [r.get("G(h)") for r in outputs if r.get("G(h)") is not None]
        temp_values = [r.get("T2m") for r in outputs if r.get("T2m") is not None]

        ghi_diario_kwh = (
            round(sum(ghi_values) / 1000 / 365, 3) if ghi_values else None
        )

        return {
            "disponible": True,
            "fuente": "pvgis_tmy",
            "latitud": lat or self.lat,
            "longitud": lon or self.lon,
            "horas_disponibles": len(outputs),
            "ghi_promedio_diario_kwh_m2": ghi_diario_kwh,
            "ghi_max_horario_w_m2": round(max(ghi_values), 1) if ghi_values else None,
            "temperatura_promedio_c": (
                round(sum(temp_values) / len(temp_values), 2) if temp_values else None
            ),
            "temperatura_max_c": round(max(temp_values), 1) if temp_values else None,
            "temperatura_min_c": round(min(temp_values), 1) if temp_values else None,
            "metadata": data.get("inputs", {}),
        }

    async def get_radiacion_mensual(
        self,
        anio_inicio: int = 2010,
        anio_fin: int = 2020,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> List[Dict]:
        """Promedios mensuales históricos de radiación (MRcalc)."""
        if not self.enabled:
            return []

        params = {
            "lat": lat or self.lat,
            "lon": lon or self.lon,
            "horirrad": 1,
            "startyear": anio_inicio,
            "endyear": anio_fin,
            "outputformat": "json",
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/MRcalc", params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return []

        return data.get("outputs", {}).get("monthly", [])

    async def estimar_generacion_pv(
        self,
        capacidad_kwp: float,
        perdidas_pct: float = 14.0,
        inclinacion: int = 10,
        azimut: int = 0,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict:
        """
        Estimación de generación PV anual usando PVcalc.
        Útil para validar contra cálculos propios del agente_solar.
        """
        if not self.enabled or capacidad_kwp <= 0:
            return {"disponible": False}

        params = {
            "lat": lat or self.lat,
            "lon": lon or self.lon,
            "peakpower": capacidad_kwp,
            "loss": perdidas_pct,
            "angle": inclinacion,
            "aspect": azimut,
            "outputformat": "json",
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/PVcalc", params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                return {"disponible": False, "motivo": str(e)}

        totals = data.get("outputs", {}).get("totals", {}).get("fixed", {})
        return {
            "disponible": True,
            "capacidad_kwp": capacidad_kwp,
            "energia_anual_kwh": totals.get("E_y"),
            "energia_diaria_kwh": totals.get("E_d"),
            "irradiacion_anual_kwh_m2": totals.get("H(i)_y"),
            "perdidas_totales_pct": totals.get("l_total"),
            "fuente": "pvgis_pvcalc",
        }


pvgis_service = PVGISService()
