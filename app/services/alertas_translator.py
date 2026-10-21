"""
Capa de traducción para alertas: convierte las alertas guardadas en mensajes
para el usuario, con emoji, título y una acción concreta.

Las alertas son generales del municipio (ver app/services/alertas_fonseca.py):
calor_extremo, lluvia_fuerte, riesgo_apagon, polvo_aire, baja_radiacion y sin_pronostico.
"""
from typing import Dict


SEVERIDAD_NIVEL = {
    "critica": "rojo",
    "alta": "rojo",
    "media": "amarillo",
    "baja": "verde",
}

ICONO_TIPO = {
    "calor_extremo": "🌡️",
    "lluvia_fuerte": "🌧️",
    "riesgo_apagon": "🔌",
    "polvo_aire": "🌫️",
    "baja_radiacion": "☁️",
    "sin_pronostico": "📡",
}

# Título y acción por tipo. El detalle con las cifras del pronóstico va en el mensaje.
PLANTILLAS = {
    "calor_extremo": {
        "titulo": "Calor extremo",
        "accion": "Hidrátate y deja el aire acondicionado en 24 °C.",
    },
    "lluvia_fuerte": {
        "titulo": "Lluvias fuertes",
        "accion": "Desconecta equipos sensibles durante la tormenta.",
    },
    "riesgo_apagon": {
        "titulo": "Riesgo de cortes de luz",
        "accion": "Carga celulares y linternas desde ahora.",
    },
    "polvo_aire": {
        "titulo": "Mucho polvo en el aire",
        "accion": "Cierra puertas y ventanas en las horas de más viento.",
    },
    "baja_radiacion": {
        "titulo": "Día con poco sol",
        "accion": "Los paneles solares producirán menos hoy.",
    },
    "sin_pronostico": {
        "titulo": "Pronóstico no disponible",
        "accion": "Revisa de nuevo en unos minutos.",
    },
}


def humanizar_alerta(alerta: Dict, **_ignorado) -> Dict:
    """Versión para el usuario de una alerta guardada. No modifica el original."""
    tipo = alerta.get("tipo", "")
    severidad = alerta.get("severidad", "media")
    plantilla = PLANTILLAS.get(tipo, {
        "titulo": "Aviso",
        "accion": "Revisa el detalle.",
    })
    return {
        "id": alerta.get("id"),
        "emoji": ICONO_TIPO.get(tipo, "🚨"),
        "nivel": SEVERIDAD_NIVEL.get(severidad, "amarillo"),
        "titulo": plantilla["titulo"],
        "mensaje": alerta.get("mensaje", ""),
        "accion": plantilla["accion"],
        "tipo_original": tipo,
        "severidad": severidad,
        "leida": alerta.get("leida", False),
        "created_at": alerta.get("created_at"),
        "empresa_id": alerta.get("empresa_id"),
    }


def humanizar_lote(alertas: list, **_ignorado) -> list:
    return [humanizar_alerta(a) for a in alertas]
