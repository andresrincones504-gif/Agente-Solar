"""
Capa de traducción para alertas: convierte alertas técnicas en mensajes
accionables con emoji + acción sugerida concreta.

Tipos de alerta soportados (definidos en agente_alertas):
- consumo_alto, pico_demanda, bateria_baja, baja_radiacion, riesgo_apagon
- consumo_sobre_inventario, aparato_dominante (según los aparatos del usuario)
- recordatorio_pago (lo crea la carga de la factura mensual)
"""
from typing import Dict, Optional

from app.core.config import get_settings


SEVERIDAD_NIVEL = {
    "critica": "rojo",
    "alta": "rojo",
    "media": "amarillo",
    "baja": "verde",
}

ICONO_TIPO = {
    "consumo_alto": "⚡",
    "pico_demanda": "📈",
    "bateria_baja": "🔋",
    "baja_radiacion": "☁️",
    "riesgo_apagon": "🔌",
    "consumo_sobre_inventario": "🔎",
    "aparato_dominante": "🔌",
    "recordatorio_pago": "🧾",
}

# Plantillas de mensaje + acción por tipo de alerta.
# El mensaje original técnico se conserva como detail.
PLANTILLAS = {
    "consumo_alto": {
        "titulo": "Tu consumo está disparado",
        "accion": "Revisa qué equipos están encendidos sin necesidad y apágalos ahora.",
    },
    "pico_demanda": {
        "titulo": "Pico de demanda detectado",
        "accion": "Distribuye el uso de equipos pesados para evitar cargo por potencia máxima.",
    },
    "bateria_baja": {
        "titulo": "Batería baja",
        "accion": "Reduce cargas no esenciales y conecta a red mientras se recarga.",
    },
    "baja_radiacion": {
        "titulo": "Día con poca radiación solar",
        "accion": "Hoy tus paneles producen menos. Pospón equipos pesados si es posible.",
    },
    "riesgo_apagon": {
        "titulo": "Riesgo de apagón próximo",
        "accion": "Carga las baterías al máximo y prepara tu plan de contingencia.",
    },
    "consumo_sobre_inventario": {
        "titulo": "Tu factura no cuadra con tus aparatos",
        "accion": "Revisa tu lista en Mis aparatos: agrega los que falten o corrige las horas de uso.",
    },
    "aparato_dominante": {
        "titulo": "Un aparato se lleva gran parte de tu consumo",
        "accion": "Mira su detalle en Mis aparatos y aplica el consejo para bajar su gasto.",
    },
    "recordatorio_pago": {
        "titulo": "Recordatorio de pago",
        "accion": "Paga tu factura antes de la fecha límite para evitar recargos o suspensión.",
    },
}


def humanizar_alerta(alerta: Dict, tiene_baterias: bool = True, tiene_paneles: bool = True) -> Dict:
    """
    Toma un dict de alerta crudo (de la BD) y devuelve la versión humanizada
    adaptada dinámicamente al equipamiento de paneles y baterías del usuario.
    No modifica el original.
    """
    tipo = alerta.get("tipo", "")
    severidad = alerta.get("severidad", "media")
    plantilla = PLANTILLAS.get(tipo, {
        "titulo": "Aviso del sistema",
        "accion": "Revisa el detalle y toma la acción que corresponda.",
    })

    accion = plantilla["accion"]
    if tipo == "riesgo_apagon":
        if not tiene_baterias:
            accion = "Prepara iluminación de emergencia y asegura carga de celulares y linternas portátiles."
        else:
            accion = "Carga las baterías al máximo y prepara tu plan de contingencia solar de respaldo."
    elif tipo == "bateria_baja" and not tiene_baterias:
        accion = "Se sugiere ignorar esta alerta o configurar un banco de almacenamiento en tu perfil."
    elif tipo == "baja_radiacion" and not tiene_paneles:
        accion = f"Menor brillo solar típico en {get_settings().LOCATION_CITY} para esta jornada."

    return {
        "id": alerta.get("id"),
        "emoji": ICONO_TIPO.get(tipo, "🚨"),
        "nivel": SEVERIDAD_NIVEL.get(severidad, "amarillo"),
        "titulo": plantilla["titulo"],
        "mensaje": alerta.get("mensaje", ""),
        "accion": accion,
        "tipo_original": tipo,
        "severidad": severidad,
        "leida": alerta.get("leida", False),
        "created_at": alerta.get("created_at"),
        "empresa_id": alerta.get("empresa_id"),
    }


def humanizar_lote(alertas: list, tiene_baterias: bool = True, tiene_paneles: bool = True) -> list:
    return [humanizar_alerta(a, tiene_baterias=tiene_baterias, tiene_paneles=tiene_paneles) for a in alertas]
