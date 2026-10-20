"""
Servicio NASA POWER API.
Obtiene datos de radiación solar histórica y temperatura para la ubicación configurada (LOCATION_*).
Documentación: https://power.larc.nasa.gov/docs/services/api/
"""
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.core.config import get_settings

settings = get_settings()


class NASAPowerService:
    """Cliente para NASA POWER API (datos diarios)."""

    PARAMETERS = "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,T2M,CLOUD_AMT"
    # ALLSKY_SFC_SW_DWN: GHI (kWh/m²/día)
    # ALLSKY_SFC_SW_DNI: DNI
    # ALLSKY_SFC_SW_DIFF: DHI
    # T2M: Temperatura a 2m
    # CLOUD_AMT: Cobertura de nubes (%)

    def __init__(self):
        self.base_url = settings.NASA_POWER_BASE_URL
        self.lat = settings.LOCATION_LAT
        self.lon = settings.LOCATION_LON

    async def get_radiation_data(
        self,
        start_date: str,
        end_date: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> List[Dict]:
        """
        Obtener datos de radiación.
        Fechas formato: YYYYMMDD
        """
        params = {
            "parameters": self.PARAMETERS,
            "community": "RE",
            "longitude": lon or self.lon,
            "latitude": lat or self.lat,
            "start": start_date,
            "end": end_date,
            "format": "JSON",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                raise RuntimeError(f"Error consultando NASA POWER: {e}")

        parameters = data.get("properties", {}).get("parameter", {})
        ghi = parameters.get("ALLSKY_SFC_SW_DWN", {})
        dni = parameters.get("ALLSKY_SFC_SW_DNI", {})
        dhi = parameters.get("ALLSKY_SFC_SW_DIFF", {})
        temp = parameters.get("T2M", {})
        clouds = parameters.get("CLOUD_AMT", {})

        results = []
        for fecha_str in ghi.keys():
            try:
                fecha = datetime.strptime(fecha_str, "%Y%m%d")
            except ValueError:
                continue
            ghi_val = ghi.get(fecha_str)
            # NASA usa -999 para valores nulos
            if ghi_val is None or ghi_val == -999:
                continue
            results.append({
                "fecha": fecha,
                "ghi": ghi_val,
                "dni": dni.get(fecha_str) if dni.get(fecha_str) != -999 else None,
                "dhi": dhi.get(fecha_str) if dhi.get(fecha_str) != -999 else None,
                "temperatura": temp.get(fecha_str) if temp.get(fecha_str) != -999 else None,
                "nubosidad": clouds.get(fecha_str) if clouds.get(fecha_str) != -999 else None,
                "fuente": "nasa_power",
                "origen_dato": "real_api",
                "escenario": "real",
                "confiabilidad": 88.0,
                "latitud": lat or self.lat,
                "longitud": lon or self.lon,
            })
        return results

    async def get_last_days(self, days: int = 30) -> List[Dict]:
        """Datos de los últimos N días."""
        # NASA POWER tiene delay de ~2 días en datos diarios
        end = datetime.now() - timedelta(days=3)
        start = end - timedelta(days=max(days - 1, 0))
        return await self.get_radiation_data(
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )


nasa_service = NASAPowerService()
