"""
Servicio Open-Meteo (NUCLEO PRINCIPAL).

Open-Meteo es la fuente principal del sistema porque ofrece:
- GHI / DNI / DHI horarios y diarios sin API key.
- Pronostico hasta 16 dias.
- Archivo historico (ERA5) con algunos dias de retraso.
- Calidad del aire, relevante en La Guajira por el polvo del desierto.

Documentacion: https://open-meteo.com/en/docs
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from app.core.config import get_settings

settings = get_settings()


class OpenMeteoService:
    """Cliente Open-Meteo para datos solares, meteorologicos y de calidad del aire."""

    ARCHIVE_DELAY_DAYS = 3

    HOURLY_VARS = ",".join(
        [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "wind_speed_10m",
            "shortwave_radiation",
            "direct_normal_irradiance",
            "diffuse_radiation",
            "precipitation",
        ]
    )

    DAILY_VARS = ",".join(
        [
            "temperature_2m_max",
            "temperature_2m_min",
            "shortwave_radiation_sum",
            "precipitation_sum",
            "wind_speed_10m_max",
        ]
    )

    # Variables diarias para las alertas generales del municipio (solo pronóstico, no histórico)
    ALERTAS_DAILY_VARS = ",".join(
        [
            "temperature_2m_max",
            "apparent_temperature_max",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "shortwave_radiation_sum",
        ]
    )

    AIR_QUALITY_VARS = ",".join(
        [
            "pm10",
            "pm2_5",
            "dust",
            "uv_index",
        ]
    )

    def __init__(self):
        self.forecast_url = settings.OPENMETEO_FORECAST_URL
        self.archive_url = settings.OPENMETEO_ARCHIVE_URL
        self.air_quality_url = settings.OPENMETEO_AIR_QUALITY_URL
        self.lat = settings.LOCATION_LAT
        self.lon = settings.LOCATION_LON

    async def get_forecast_horario(
        self,
        days: int = 7,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        allow_synthetic: bool = True,
    ) -> List[Dict]:
        """Pronostico horario con radiacion solar (GHI/DNI/DHI)."""
        params = {
            "latitude": lat or self.lat,
            "longitude": lon or self.lon,
            "hourly": self.HOURLY_VARS,
            "wind_speed_unit": "kmh",
            "forecast_days": min(max(days, 1), 16),
            "timezone": "America/Bogota",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(self.forecast_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                if allow_synthetic:
                    return self._synthetic_forecast_horario(days)
                raise RuntimeError("No se pudo consultar Open-Meteo forecast horario en modo real")

        return self._parse_hourly(data)

    async def get_forecast_diario(
        self,
        days: int = 7,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        allow_synthetic: bool = True,
    ) -> List[Dict]:
        """Pronostico diario con radiacion solar acumulada."""
        params = {
            "latitude": lat or self.lat,
            "longitude": lon or self.lon,
            "daily": self.DAILY_VARS,
            "wind_speed_unit": "kmh",
            "forecast_days": min(max(days, 1), 16),
            "timezone": "America/Bogota",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(self.forecast_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                if allow_synthetic:
                    return self._synthetic_forecast_diario(days)
                raise RuntimeError("No se pudo consultar Open-Meteo forecast diario en modo real")

        return self._parse_daily(data)

    async def get_pronostico_alertas(
        self,
        days: int = 3,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> List[Dict]:
        """
        Pronóstico diario para las alertas del municipio: calor, sensación térmica, lluvia, viento y sol.
        Devuelve [] si Open-Meteo no responde: una alerta del clima nunca sale de datos inventados.
        """
        params = {
            "latitude": lat or self.lat,
            "longitude": lon or self.lon,
            "daily": self.ALERTAS_DAILY_VARS,
            "wind_speed_unit": "kmh",
            "forecast_days": min(max(days, 1), 16),
            "timezone": "America/Bogota",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(self.forecast_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                return []

        daily = data.get("daily", {})
        dias = []
        for i, t in enumerate(daily.get("time", [])):
            ghi_mj = self._safe(daily, "shortwave_radiation_sum", i)
            dias.append(
                {
                    "fecha": t,
                    "temp_max": self._safe(daily, "temperature_2m_max", i),
                    "sensacion_max": self._safe(daily, "apparent_temperature_max", i),
                    "lluvia_mm": self._safe(daily, "precipitation_sum", i),
                    "prob_lluvia": self._safe(daily, "precipitation_probability_max", i),
                    "viento_max": self._safe(daily, "wind_speed_10m_max", i),
                    "rafagas_max": self._safe(daily, "wind_gusts_10m_max", i),
                    "ghi": round(ghi_mj / 3.6, 2) if ghi_mj is not None else None,
                }
            )
        return dias

    async def get_historico(
        self,
        start_date: str,
        end_date: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> List[Dict]:
        """
        Historico diario desde ERA5.
        Fechas formato: YYYY-MM-DD
        """
        params = {
            "latitude": lat or self.lat,
            "longitude": lon or self.lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": self.DAILY_VARS,
            "wind_speed_unit": "kmh",
            "timezone": "America/Bogota",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(self.archive_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                raise RuntimeError(f"Error consultando Open-Meteo Archive: {e}")

        return self._parse_daily(data)

    async def get_ultimos_dias(self, days: int = 30) -> List[Dict]:
        """Historico de los ultimos N dias disponibles en Archive."""
        end = self._today_start() - timedelta(days=self.ARCHIVE_DELAY_DAYS)
        start = end - timedelta(days=max(days - 1, 0))
        return await self.get_historico(
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )

    async def get_serie_reciente(self, days: int = 30) -> List[Dict]:
        """
        Serie diaria de los ultimos N dias calendario hasta hoy.

        Combina historico de Archive y pronostico diario para cerrar el hueco
        de los dias mas recientes donde el archivo aun no publica datos.
        """
        today = self._today_start()
        start = today - timedelta(days=max(days - 1, 0))
        archive_end = today - timedelta(days=self.ARCHIVE_DELAY_DAYS)

        historico: List[Dict] = []
        if start <= archive_end:
            historico = await self.get_historico(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=archive_end.strftime("%Y-%m-%d"),
            )

        forecast = await self.get_forecast_diario(
            days=min(days, 16),
            allow_synthetic=False,
        )
        forecast_items: List[Dict] = []
        for item in forecast:
            fecha = item.get("fecha")
            if not fecha:
                continue
            if start <= fecha <= today and fecha > archive_end:
                enriched = dict(item)
                enriched["origen_dato"] = "forecast_api"
                enriched["confiabilidad"] = 75.0
                forecast_items.append(enriched)

        return historico + forecast_items

    async def get_calidad_aire(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict:
        """Calidad del aire actual + pronostico."""
        params = {
            "latitude": lat or self.lat,
            "longitude": lon or self.lon,
            "hourly": self.AIR_QUALITY_VARS,
            "forecast_days": 3,
            "timezone": "America/Bogota",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(self.air_quality_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return {"disponible": False, "datos": []}

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        pm10 = hourly.get("pm10", [])
        pm25 = hourly.get("pm2_5", [])
        dust = hourly.get("dust", [])
        uv = hourly.get("uv_index", [])

        registros = []
        for i, t in enumerate(times):
            registros.append(
                {
                    "fecha": t,
                    "pm10": pm10[i] if i < len(pm10) else None,
                    "pm2_5": pm25[i] if i < len(pm25) else None,
                    "polvo": dust[i] if i < len(dust) else None,
                    "uv_index": uv[i] if i < len(uv) else None,
                }
            )
        return {"disponible": True, "datos": registros}

    def _parse_hourly(self, data: Dict) -> List[Dict]:
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        results = []
        for i, t in enumerate(times):
            try:
                fecha = datetime.fromisoformat(t)
            except ValueError:
                continue
            ghi_w = self._safe(hourly, "shortwave_radiation", i)
            dni_w = self._safe(hourly, "direct_normal_irradiance", i)
            dhi_w = self._safe(hourly, "diffuse_radiation", i)
            results.append(
                {
                    "fecha": fecha,
                    "temperatura": self._safe(hourly, "temperature_2m", i),
                    "humedad": self._safe(hourly, "relative_humidity_2m", i),
                    "nubosidad": self._safe(hourly, "cloud_cover", i),
                    "nubosidad_baja": self._safe(hourly, "cloud_cover_low", i),
                    "nubosidad_media": self._safe(hourly, "cloud_cover_mid", i),
                    "nubosidad_alta": self._safe(hourly, "cloud_cover_high", i),
                    "viento_kmh": self._safe(hourly, "wind_speed_10m", i),  # Open-Meteo entrega km/h por defecto
                    "ghi_w_m2": ghi_w,
                    "dni_w_m2": dni_w,
                    "dhi_w_m2": dhi_w,
                    "precipitacion_mm": self._safe(hourly, "precipitation", i),
                    "fuente": "open_meteo",
                    "origen_dato": "real_api",
                    "escenario": "real",
                    "confiabilidad": 90.0,
                }
            )
        return results

    def _parse_daily(self, data: Dict) -> List[Dict]:
        daily = data.get("daily", {})
        times = daily.get("time", [])
        results = []
        for i, t in enumerate(times):
            try:
                fecha = datetime.fromisoformat(t)
            except ValueError:
                continue
            ghi_mj = self._safe(daily, "shortwave_radiation_sum", i)
            ghi_kwh = round(ghi_mj / 3.6, 3) if ghi_mj is not None else None
            t_max = self._safe(daily, "temperature_2m_max", i)
            t_min = self._safe(daily, "temperature_2m_min", i)
            t_avg = (
                round((t_max + t_min) / 2, 2)
                if t_max is not None and t_min is not None
                else None
            )
            results.append(
                {
                    "fecha": fecha,
                    "ghi": ghi_kwh,
                    "dni": None,
                    "dhi": None,
                    "temperatura": t_avg,
                    "temperatura_max": t_max,
                    "temperatura_min": t_min,
                    "nubosidad": None,
                    "precipitacion_mm": self._safe(daily, "precipitation_sum", i),
                    "viento_kmh_max": self._safe(daily, "wind_speed_10m_max", i),  # km/h
                    "fuente": "open_meteo",
                    "origen_dato": "real_api",
                    "escenario": "real",
                    "confiabilidad": 90.0,
                    "latitud": self.lat,
                    "longitud": self.lon,
                }
            )
        return results

    @staticmethod
    def _safe(d: Dict, key: str, i: int):
        arr = d.get(key) or []
        return arr[i] if i < len(arr) else None

    @staticmethod
    def _mul(value, factor):
        return round(value * factor, 2) if value is not None else None

    def _synthetic_forecast_horario(self, days: int) -> List[Dict]:
        results = []
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        for h in range(0, days * 24):
            f = now + timedelta(hours=h)
            hour = f.hour
            soleado = 8 <= hour <= 17
            results.append(
                {
                    "fecha": f,
                    "temperatura": 30.0 if soleado else 26.0,
                    "humedad": 65,
                    "nubosidad": 20 if soleado else 35,
                    "nubosidad_baja": 10,
                    "nubosidad_media": 5,
                    "nubosidad_alta": 5,
                    "viento_kmh": 18.0,
                    "ghi_w_m2": 800 if soleado else 0,
                    "dni_w_m2": 700 if soleado else 0,
                    "dhi_w_m2": 100 if soleado else 0,
                    "precipitacion_mm": 0,
                    "fuente": "synthetic",
                    "origen_dato": "synthetic_fallback",
                    "escenario": "demo",
                    "confiabilidad": 30.0,
                }
            )
        return results

    def _synthetic_forecast_diario(self, days: int) -> List[Dict]:
        results = []
        today = self._today_start()
        for d in range(days):
            f = today + timedelta(days=d)
            results.append(
                {
                    "fecha": f,
                    "ghi": 5.8,
                    "dni": None,
                    "dhi": None,
                    "temperatura": 28.0,
                    "temperatura_max": 32.0,
                    "temperatura_min": 24.0,
                    "nubosidad": None,
                    "precipitacion_mm": 0,
                    "viento_kmh_max": 25.0,
                    "fuente": "synthetic",
                    "origen_dato": "synthetic_fallback",
                    "escenario": "demo",
                    "confiabilidad": 30.0,
                    "latitud": self.lat,
                    "longitud": self.lon,
                }
            )
        return results

    @staticmethod
    def _today_start() -> datetime:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


openmeteo_service = OpenMeteoService()
