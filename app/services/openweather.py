"""
Servicio OpenWeather (complemento).
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from app.core.config import get_settings

settings = get_settings()


class OpenWeatherService:
    """Cliente OpenWeather usado como capa de validacion y AQI."""

    def __init__(self):
        self.base_url = settings.OPENWEATHER_BASE_URL
        self.api_key = settings.OPENWEATHER_API_KEY
        self.lat = settings.LOCATION_LAT
        self.lon = settings.LOCATION_LON

    async def get_current_weather(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        allow_synthetic: bool = True,
    ) -> Dict:
        if not self.api_key:
            if allow_synthetic:
                return self._synthetic_current()
            raise RuntimeError("OpenWeather no disponible sin API key en modo real")

        params = {
            "lat": lat or self.lat,
            "lon": lon or self.lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "es",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/weather", params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                if allow_synthetic:
                    return self._synthetic_current()
                raise RuntimeError("No se pudo consultar OpenWeather en modo real")

        return {
            "fecha": datetime.now(),
            "temperatura": data.get("main", {}).get("temp"),
            "humedad": data.get("main", {}).get("humidity"),
            "nubosidad": data.get("clouds", {}).get("all"),
            "descripcion": data.get("weather", [{}])[0].get("description"),
            "viento_kmh": data.get("wind", {}).get("speed", 0) * 3.6,
            "fuente": "openweather",
            "origen_dato": "real_api",
            "escenario": "real",
            "confiabilidad": 90.0,
        }

    async def get_forecast(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        allow_synthetic: bool = True,
    ) -> List[Dict]:
        if not self.api_key:
            if allow_synthetic:
                return self._synthetic_forecast()
            raise RuntimeError("OpenWeather forecast no disponible sin API key en modo real")

        params = {
            "lat": lat or self.lat,
            "lon": lon or self.lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "es",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/forecast", params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                if allow_synthetic:
                    return self._synthetic_forecast()
                raise RuntimeError("No se pudo consultar OpenWeather forecast en modo real")

        results = []
        for item in data.get("list", []):
            results.append(
                {
                    "fecha": datetime.fromtimestamp(item["dt"]),
                    "temperatura": item.get("main", {}).get("temp"),
                    "humedad": item.get("main", {}).get("humidity"),
                    "nubosidad": item.get("clouds", {}).get("all"),
                    "descripcion": item.get("weather", [{}])[0].get("description"),
                    "viento_kmh": item.get("wind", {}).get("speed", 0) * 3.6,
                    "fuente": "openweather",
                    "origen_dato": "real_api",
                    "escenario": "real",
                    "confiabilidad": 90.0,
                }
            )
        return results

    def _synthetic_current(self) -> Dict:
        hour = datetime.now().hour
        return {
            "fecha": datetime.now(),
            "temperatura": 30.0 if 10 <= hour <= 16 else 26.0,
            "humedad": 65,
            "nubosidad": 20 if 10 <= hour <= 16 else 35,
            "descripcion": "soleado" if 8 <= hour <= 17 else "despejado",
            "viento_kmh": 18.0,
            "fuente": "synthetic",
            "origen_dato": "synthetic_fallback",
            "escenario": "demo",
            "confiabilidad": 30.0,
        }

    def _synthetic_forecast(self) -> List[Dict]:
        now = datetime.now()
        results = []
        for h in range(0, 120, 3):
            future = now + timedelta(hours=h)
            hour = future.hour
            results.append(
                {
                    "fecha": future,
                    "temperatura": 30.0 if 10 <= hour <= 16 else 26.0,
                    "humedad": 65,
                    "nubosidad": 20 if 10 <= hour <= 16 else 35,
                    "descripcion": "soleado",
                    "viento_kmh": 18.0,
                    "fuente": "synthetic",
                    "origen_dato": "synthetic_fallback",
                    "escenario": "demo",
                    "confiabilidad": 30.0,
                }
            )
        return results

    async def get_air_pollution(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict:
        if not self.api_key:
            return {"disponible": False, "motivo": "Sin API key"}

        params = {
            "lat": lat or self.lat,
            "lon": lon or self.lon,
            "appid": self.api_key,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/air_pollution",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                return {"disponible": False, "motivo": str(exc)}

        items = data.get("list", [])
        if not items:
            return {"disponible": False}
        first = items[0]
        comp = first.get("components", {})
        return {
            "disponible": True,
            "fecha": datetime.fromtimestamp(first.get("dt", 0)),
            "aqi": first.get("main", {}).get("aqi"),
            "pm10": comp.get("pm10"),
            "pm2_5": comp.get("pm2_5"),
            "co": comp.get("co"),
            "no2": comp.get("no2"),
            "so2": comp.get("so2"),
            "o3": comp.get("o3"),
            "fuente": "openweather_air_pollution",
        }

    async def validar_pronostico(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        allow_synthetic: bool = True,
    ) -> Dict:
        actual = await self.get_current_weather(
            lat=lat,
            lon=lon,
            allow_synthetic=allow_synthetic,
        )
        return {"fuente": "openweather", "clima_actual": actual}


openweather_service = OpenWeatherService()

