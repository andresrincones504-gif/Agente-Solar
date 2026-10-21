"""
Alertas generales del municipio: clima y riesgo para el servicio de energía.

Son las mismas para todos los usuarios de la ubicación configurada (LOCATION_*) y salen del
pronóstico de Open-Meteo para hoy y mañana: calor extremo, lluvias fuertes, vientos que pueden
causar cortes de luz, polvo en el aire y días con poco sol. No dependen de los aparatos del usuario.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from app.core.config import get_settings

# Umbrales (mismos para todos). Fonseca tiene una máxima normal de 34 °C (IDEAM 1981-2010).
CALOR_MEDIO_C = 36.0          # día muy caluroso
CALOR_ALTO_C = 38.0           # calor extremo
SENSACION_ALTA_C = 41.0       # sensación térmica peligrosa
OLA_DE_CALOR_C = 37.0         # máxima que, repetida 3 días o más, es ola de calor
LLUVIA_FUERTE_MM = 20.0
LLUVIA_MUY_FUERTE_MM = 50.0
VIENTO_FUERTE_KMH = 40.0
RAFAGAS_FUERTES_KMH = 60.0
PM10_ALTO = 100.0             # µg/m³; la OMS recomienda no pasar de 45 en promedio diario
PM10_MUY_ALTO = 150.0
POCO_SOL_KWH_M2 = 3.5         # lo normal en Fonseca es cerca de 5 kWh/m² al día

# Tipos de alerta general. "sin_pronostico" avisa que no se pudo consultar el clima.
TIPOS_GENERALES = ("calor_extremo", "lluvia_fuerte", "riesgo_apagon", "polvo_aire", "baja_radiacion", "sin_pronostico")

SEGUNDOS_CACHE = 600  # el pronóstico es el mismo para todos: se consulta como máximo cada 10 minutos
_cache: Dict = {"alertas": None, "revisado": 0.0}

CRITERIOS = [
    {"alerta": "Calor extremo", "cuando": f"Máxima de {CALOR_MEDIO_C:.0f} °C o más (atención) y de {CALOR_ALTO_C:.0f} °C o sensación térmica de {SENSACION_ALTA_C:.0f} °C o más (urgente). Si pasa de {OLA_DE_CALOR_C:.0f} °C tres días seguidos, se avisa como ola de calor."},
    {"alerta": "Lluvias fuertes", "cuando": f"{LLUVIA_FUERTE_MM:.0f} mm o más en el día (atención) y {LLUVIA_MUY_FUERTE_MM:.0f} mm o más (urgente)."},
    {"alerta": "Riesgo de cortes de luz por viento", "cuando": f"Vientos de {VIENTO_FUERTE_KMH:.0f} km/h o ráfagas de {RAFAGAS_FUERTES_KMH:.0f} km/h o más."},
    {"alerta": "Polvo en el aire", "cuando": f"Partículas PM10 de {PM10_ALTO:.0f} µg/m³ o más en las próximas 24 horas (urgente desde {PM10_MUY_ALTO:.0f})."},
    {"alerta": "Poco sol", "cuando": f"Menos de {POCO_SOL_KWH_M2} kWh/m² de radiación solar en el día."},
]


def _cuando(i: int) -> str:
    return "Hoy" if i == 0 else "Mañana"


def _num(valor) -> Optional[float]:
    return float(valor) if isinstance(valor, (int, float)) else None


def _alerta_calor(dias: List[Dict], ciudad: str) -> Optional[Dict]:
    peor = None
    for i, d in enumerate(dias[:2]):
        t, s = _num(d.get("temp_max")), _num(d.get("sensacion_max"))
        if t is None:
            continue
        alto = t >= CALOR_ALTO_C or (s is not None and s >= SENSACION_ALTA_C)
        if t >= CALOR_MEDIO_C or alto:
            nivel = 2 if alto else 1
            if peor is None or nivel > peor[0]:
                peor = (nivel, i, t, s)
    if peor is None:
        return None
    nivel, i, t, s = peor
    seguidos = 0
    for d in dias:
        if (_num(d.get("temp_max")) or 0) >= OLA_DE_CALOR_C:
            seguidos += 1
        else:
            break
    sensacion = f", con sensación térmica de {s:.0f} °C" if s is not None and s > t else ""
    ola = f" Es una ola de calor: seguirá así al menos {seguidos} días." if seguidos >= 3 else ""
    return {
        "tipo": "calor_extremo",
        "severidad": "alta" if nivel == 2 else "media",
        "mensaje": (
            f"{_cuando(i)} en {ciudad} se esperan hasta {t:.0f} °C{sensacion}.{ola} "
            "Toma agua seguido y evita el sol entre las 11 de la mañana y las 3 de la tarde. "
            "Si usas aire acondicionado, déjalo en 24 °C: cada grado más frío sube el consumo cerca de un 7%."
        ),
    }


def _alerta_lluvia(dias: List[Dict], ciudad: str) -> Optional[Dict]:
    candidatos = [(i, _num(d.get("lluvia_mm")), _num(d.get("prob_lluvia"))) for i, d in enumerate(dias[:2])]
    candidatos = [c for c in candidatos if c[1] is not None and c[1] >= LLUVIA_FUERTE_MM]
    if not candidatos:
        return None
    i, mm, prob = max(candidatos, key=lambda c: c[1])
    probabilidad = f", con {prob:.0f}% de probabilidad" if prob is not None else ""
    return {
        "tipo": "lluvia_fuerte",
        "severidad": "alta" if mm >= LLUVIA_MUY_FUERTE_MM else "media",
        "mensaje": (
            f"{_cuando(i)} se esperan lluvias fuertes en {ciudad} (unos {mm:.0f} mm{probabilidad}). "
            "Las tormentas pueden traer cortes y subidas de voltaje: desconecta televisores y computadores "
            "mientras llueve fuerte y ten a mano una linterna."
        ),
    }


def _alerta_viento(dias: List[Dict], ciudad: str) -> Optional[Dict]:
    candidatos = []
    for i, d in enumerate(dias[:2]):
        v, r = _num(d.get("viento_max")) or 0.0, _num(d.get("rafagas_max")) or 0.0
        if v >= VIENTO_FUERTE_KMH or r >= RAFAGAS_FUERTES_KMH:
            candidatos.append((i, v, r))
    if not candidatos:
        return None
    i, v, r = max(candidatos, key=lambda c: (c[2], c[1]))
    rafagas = f" y ráfagas de {r:.0f} km/h" if r > v else ""
    return {
        "tipo": "riesgo_apagon",
        "severidad": "alta",
        "mensaje": (
            f"{_cuando(i)} habrá vientos de hasta {v:.0f} km/h{rafagas} en {ciudad}. "
            "El viento fuerte puede tumbar ramas sobre las redes y causar cortes de luz. "
            "Carga celulares y linternas; si se va la luz, abre la nevera lo menos posible para que no pierda el frío."
        ),
    }


def _alerta_polvo(aire: Optional[Dict], ciudad: str) -> Optional[Dict]:
    if not aire or not aire.get("disponible"):
        return None
    valores = [_num(r.get("pm10")) for r in (aire.get("datos") or [])[:24]]
    valores = [v for v in valores if v is not None]
    if not valores or max(valores) < PM10_ALTO:
        return None
    pm = max(valores)
    return {
        "tipo": "polvo_aire",
        "severidad": "alta" if pm >= PM10_MUY_ALTO else "media",
        "mensaje": (
            f"En las próximas horas habrá mucho polvo en el aire de {ciudad} (hasta {pm:.0f} µg/m³ de partículas PM10; "
            "la OMS recomienda no pasar de 45 en un día). Cierra puertas y ventanas en las horas de más viento "
            "y, si tienes paneles solares, límpialos cuando pase: el polvo les quita producción."
        ),
    }


def _alerta_poco_sol(dias: List[Dict], ciudad: str) -> Optional[Dict]:
    ghi = _num(dias[0].get("ghi")) if dias else None
    if ghi is None or ghi >= POCO_SOL_KWH_M2:
        return None
    return {
        "tipo": "baja_radiacion",
        "severidad": "baja",
        "mensaje": (
            f"Hoy habrá poco sol en {ciudad} (≈{ghi:.1f} kWh/m² en el día; lo normal es cerca de 5). "
            "Los paneles solares producirán menos de lo habitual."
        ),
    }


def calcular_alertas_generales(dias: List[Dict], aire: Optional[Dict], ciudad: Optional[str] = None) -> List[Dict]:
    """Alertas del municipio a partir del pronóstico diario (hoy primero) y de la calidad del aire."""
    ciudad = ciudad or get_settings().LOCATION_CITY
    if not dias:
        return [{
            "tipo": "sin_pronostico",
            "severidad": "baja",
            "mensaje": (
                f"No pudimos consultar el pronóstico del clima de {ciudad} en este momento. "
                "Volveremos a revisarlo en unos minutos."
            ),
        }]
    alertas = [
        _alerta_viento(dias, ciudad),
        _alerta_calor(dias, ciudad),
        _alerta_lluvia(dias, ciudad),
        _alerta_polvo(aire, ciudad),
        _alerta_poco_sol(dias, ciudad),
    ]
    return [a for a in alertas if a]


async def obtener_alertas_generales(refrescar: bool = False) -> List[Dict]:
    """Consulta Open-Meteo (pronóstico y calidad del aire) y calcula las alertas, con caché de 10 minutos."""
    ahora = time.monotonic()
    if not refrescar and _cache["alertas"] is not None and ahora - _cache["revisado"] < SEGUNDOS_CACHE:
        return _cache["alertas"]

    from app.services.openmeteo import openmeteo_service

    try:
        dias = await openmeteo_service.get_pronostico_alertas(days=5)
    except Exception as e:  # nunca romper la pantalla por el clima
        print(f"[ALERTAS] Sin pronóstico: {e}")
        dias = []
    try:
        aire = await openmeteo_service.get_calidad_aire()
    except Exception:
        aire = None

    alertas = calcular_alertas_generales(dias, aire)
    # Si no hubo pronóstico se vuelve a intentar en la siguiente consulta, sin esperar la caché
    if dias:
        _cache.update(alertas=alertas, revisado=ahora)
    return alertas
