"""
Contexto energético de un hogar o empresa a partir de su inventario de aparatos.

Lo usan las recomendaciones, las alertas, Mi Día y el simulador solar:
- resumen_inventario: qué aparatos tiene, cuánto pesa cada uno y cuáles se pueden mover de horario.
- franja_solar: las horas de mayor radiación del pronóstico (hoy o mañana).
- dimensionar_sistema: paneles (kWp) y batería (kWh) sugeridos según su consumo real o estimado.
- consejo_del_dia: un consejo concreto sobre sus propios aparatos.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import AparatoUsuario, ConsumoEnergetico, Empresa, RadiacionSolar
from app.services.aparatos import calcular_estadisticas

PERFORMANCE_RATIO = 0.80          # pérdidas de cableado, inversor, temperatura y polvo
HSP_REFERENCIA = 5.0              # kWh/m²/día; PVGIS TMY para Fonseca (La Guajira) da 4.99
PROFUNDIDAD_DESCARGA = 0.80       # fracción útil de la batería
UMBRAL_FRANJA = 0.70              # horas con al menos 70% de la radiación pico del día

# Cargas que se pueden mover a las horas de sol (solo ahorra dinero si hay paneles:
# la tarifa residencial en Colombia no cambia según la hora).
DESPLAZABLES = {
    "lavadora", "secadora", "plancha", "bomba_agua", "bomba_riego", "horno_electrico",
    "compresor", "herramientas", "soldador", "molino", "ordenadora",
}
# Cargas a respaldar con batería durante un apagón nocturno.
CRITICOS_POR_CODIGO = {"router", "camaras", "cargador_celular", "punto_venta"}
CRITICOS_POR_TIPO = {"refrigeracion", "iluminacion"}

# Referencia cuando no hay ni factura ni aparatos (los valores fijos que usaba la app).
REFERENCIA_KWP = {"hogar": 2.5}
REFERENCIA_BATERIA = {"hogar": 5.0}

CONSEJOS_POR_TIPO = {
    "refrigeracion": "Revisa que cierre bien, que el empaque no esté roto y que no esté pegada a la pared o al sol. Una nevera de más de 10 años puede gastar 50% más que una nueva.",
    "climatizacion": "Programarlo a 24 °C, cerrar puertas y ventanas y limpiar el filtro cada mes baja bastante su consumo. Cada grado más frío sube el gasto cerca de 7%.",
    "iluminacion": "Cambiar bombillos incandescentes o ahorradores por LED reduce entre 50% y 85% lo que gastan, y apagar los de cuartos vacíos suma.",
    "cocina": "Tapar las ollas, usar la olla arrocera solo con la cantidad necesaria y no abrir el horno mientras cocina ahorra energía.",
    "lavado": "Lava con carga completa y en agua fría; plancha la ropa en una sola tanda.",
    "entretenimiento": "Desconecta televisores, decodificadores y equipos de sonido cuando no los uses: en espera también consumen.",
    "cuidado_personal": "Acorta el tiempo de uso; la ducha y el secador tienen potencias muy altas aunque se usen poco.",
    "oficina": "Apaga computadores e impresoras al cerrar y activa el ahorro de energía.",
    "bombas_motores": "Revisa fugas en tanques y tuberías: una fuga hace que la bomba arranque más veces. Úsala en una sola tanda.",
    "otro": "Revisa cuántas horas lo usas realmente y si puede apagarse cuando no se necesita.",
}


def _es_critico(codigo: Optional[str], tipo: str) -> bool:
    return (codigo in CRITICOS_POR_CODIGO) or (tipo in CRITICOS_POR_TIPO)


def resumen_inventario(db: Session, empresa: Empresa) -> Dict:
    """Inventario con consumo, costo y participación por aparato, más banderas útiles para los agentes."""
    aparatos = db.query(AparatoUsuario).filter(AparatoUsuario.empresa_id == empresa.id).all()
    stats = calcular_estadisticas(db, empresa)
    por_id = {f["aparato_id"]: f for f in stats["aparatos"] if f["aparato_id"] is not None}
    filas: List[Dict] = []
    for a in aparatos:
        f = por_id.get(a.id, {})
        codigo = a.catalogo.codigo if a.catalogo else None
        filas.append({
            "id": a.id,
            "codigo": codigo,
            "nombre": a.nombre,
            "cantidad": a.cantidad,
            "tipo_aparato": a.tipo_aparato,
            "potencia_w": a.potencia_efectiva_w,
            "horas_dia": a.horas_efectivas_dia,
            "kwh_mes": f.get("consumo_kwh_mes", a.consumo_kwh_mes),
            "costo_mes": f.get("costo_cop_mes", round(a.consumo_kwh_mes * (empresa.tarifa_kwh or 0))),
            "porcentaje": f.get("porcentaje", 0.0),
            "desplazable": codigo in DESPLAZABLES,
            "critico": _es_critico(codigo, a.tipo_aparato),
        })
    filas.sort(key=lambda x: x["kwh_mes"], reverse=True)
    no_ident = next((f for f in stats["aparatos"] if f["aparato_id"] is None), None)
    return {
        "tiene_aparatos": bool(filas),
        "aparatos": filas,
        "top": filas[:3],
        "desplazables": [f for f in filas if f["desplazable"]],
        "base_calculo": stats["base_calculo"],
        "total_kwh_mes": stats["consumo_total_kwh_mes"],
        "inventario_kwh_mes": stats["consumo_inventario_kwh_mes"],
        "real_kwh_mes": stats["consumo_real_kwh_mes"],
        "no_identificado_kwh_mes": no_ident["consumo_kwh_mes"] if no_ident else 0.0,
        "costo_total_mes": stats["costo_total_cop_mes"],
        "tiene_paneles": _tiene_paneles(db, empresa),
        "tiene_baterias": _tiene_baterias(db, empresa),
    }


def _escenario(empresa: Empresa) -> str:
    return empresa.escenario_default or "real"


def _tiene_paneles(db: Session, empresa: Empresa) -> bool:
    if (empresa.capacidad_paneles_kw or 0) > 0:
        return True
    return db.query(ConsumoEnergetico).filter(
        ConsumoEnergetico.empresa_id == empresa.id,
        ConsumoEnergetico.produccion_solar_kwh > 0,
        ConsumoEnergetico.escenario == _escenario(empresa),
    ).first() is not None


def _tiene_baterias(db: Session, empresa: Empresa) -> bool:
    if (empresa.capacidad_bateria_kwh or 0) > 0:
        return True
    return db.query(ConsumoEnergetico).filter(
        ConsumoEnergetico.empresa_id == empresa.id,
        ConsumoEnergetico.nivel_bateria_pct.isnot(None),
        ConsumoEnergetico.escenario == _escenario(empresa),
    ).first() is not None


# ---------------------------------------------------------------------------
# Franja solar
# ---------------------------------------------------------------------------
def franja_solar(forecast_horario: List[Dict], ahora: Optional[datetime] = None) -> Optional[Dict]:
    """
    Horas de mayor radiación del pronóstico horario (W/m²). Si la franja de hoy ya pasó,
    devuelve la de mañana. None si no hay datos de radiación.
    """
    ahora = ahora or datetime.now()
    por_dia: Dict = {}
    for item in forecast_horario or []:
        fecha = item.get("fecha")
        ghi = item.get("ghi_w_m2")
        if not isinstance(fecha, datetime) or ghi is None:
            continue
        por_dia.setdefault(fecha.date(), []).append((fecha.hour, float(ghi)))

    for dia in sorted(por_dia):
        if dia < ahora.date():
            continue
        horas = sorted(por_dia[dia])
        pico = max(g for _, g in horas)
        if pico <= 0:
            continue
        buenas = [h for h, g in horas if g >= pico * UMBRAL_FRANJA]
        inicio, fin = min(buenas), max(buenas) + 1  # fin exclusivo: 10 -> 14 = de 10:00 a 14:00
        if dia == ahora.date() and ahora.hour >= fin:
            continue  # la franja de hoy ya pasó: mirar mañana
        return {
            "fecha": dia.isoformat(),
            "es_hoy": dia == ahora.date(),
            "inicio": inicio,
            "fin": fin,
            "pico_w_m2": round(pico),
            "ghi_dia_kwh_m2": round(sum(g for _, g in horas) / 1000, 2),
            "texto": f"{'hoy' if dia == ahora.date() else 'mañana'} de {inicio}:00 a {fin}:00",
        }
    return None


async def obtener_franja_solar() -> Optional[Dict]:
    """Franja solar con el pronóstico real de Open-Meteo; None si la API no responde."""
    from app.services.openmeteo import openmeteo_service
    try:
        forecast = await openmeteo_service.get_forecast_horario(days=2, allow_synthetic=False)
    except Exception:
        return None
    return franja_solar(forecast)


# ---------------------------------------------------------------------------
# Dimensionamiento solar
# ---------------------------------------------------------------------------
def _hsp_local(db: Session) -> float:
    """Horas solares pico: promedio de radiación real de los últimos 30 días, o la referencia."""
    desde = datetime.now() - timedelta(days=30)
    valores = [
        r.ghi for r in db.query(RadiacionSolar)
        .filter(RadiacionSolar.fecha >= desde, RadiacionSolar.escenario == "real", RadiacionSolar.fuente == "open_meteo")
        .all() if r.ghi
    ]
    return round(sum(valores) / len(valores), 2) if len(valores) >= 7 else HSP_REFERENCIA


def _redondear(valor: float, paso: float = 0.5, minimo: float = 0.0) -> float:
    return max(minimo, round(round(valor / paso) * paso, 2))


def dimensionar_sistema(db: Session, empresa: Empresa, resumen: Optional[Dict] = None) -> Dict:
    """Sistema solar y batería sugeridos para cubrir el consumo mensual (factura o inventario)."""
    resumen = resumen or resumen_inventario(db, empresa)
    tarifa = float(empresa.tarifa_kwh or 0)
    hsp = _hsp_local(db)
    es_hogar = (empresa.tipo_entidad or ("hogar" if empresa.tipo == "hogar" else None)) == "hogar"

    if resumen["real_kwh_mes"]:
        base, consumo_mes = "factura", float(resumen["real_kwh_mes"])
    elif resumen["tiene_aparatos"]:
        base, consumo_mes = "inventario", float(resumen["inventario_kwh_mes"])
    else:
        base, consumo_mes = "referencia", None

    if consumo_mes:
        kwp = _redondear(consumo_mes / (30 * hsp * PERFORMANCE_RATIO), 0.5, 1.0)
    else:
        kwp = REFERENCIA_KWP.get("hogar" if es_hogar else "otro", 10.0)
    produccion_mes = round(kwp * hsp * PERFORMANCE_RATIO * 30, 1)
    ahorro_mes = round(min(produccion_mes, consumo_mes or produccion_mes) * tarifa, 0)

    criticos_dia = sum(a["kwh_mes"] for a in resumen["aparatos"] if a["critico"]) / 30
    if criticos_dia > 0:
        # Respaldo nocturno: la mitad del consumo diario de las cargas críticas, con descarga útil del 80%
        bateria = _redondear(criticos_dia * 0.5 / PROFUNDIDAD_DESCARGA, 0.5, 2.5)
    else:
        bateria = REFERENCIA_BATERIA.get("hogar" if es_hogar else "otro", 30.0)
    autonomia = round(bateria * PROFUNDIDAD_DESCARGA / (criticos_dia / 24), 1) if criticos_dia > 0 else None

    return {
        "base": base,
        "consumo_mes_kwh": round(consumo_mes, 1) if consumo_mes else None,
        "hsp": hsp,
        "kwp_sugerido": kwp,
        "produccion_mes_kwh": produccion_mes,
        "cobertura_pct": round(min(100.0, produccion_mes / consumo_mes * 100), 0) if consumo_mes else None,
        "ahorro_mes_cop": ahorro_mes,
        "bateria_kwh_sugerida": bateria,
        "cargas_criticas_kwh_dia": round(criticos_dia, 2),
        "autonomia_cargas_criticas_horas": autonomia,
    }


# ---------------------------------------------------------------------------
# Consejo del día
# ---------------------------------------------------------------------------
def _minuscula_inicial(texto: str) -> str:
    """'Aire acondicionado 12.000 BTU' -> 'aire acondicionado 12.000 BTU' (respeta siglas)."""
    return texto[:1].lower() + texto[1:] if texto else texto


def nombre_aparato(aparato: Dict) -> str:
    """'aire acondicionado 12.000 BTU (20 unidades)': el nombre del catálogo no tiene plural."""
    nombre = _minuscula_inicial(aparato["nombre"])
    cantidad = aparato.get("cantidad") or 1
    return f"{nombre} ({cantidad} unidades)" if cantidad > 1 else nombre


def _nombres(aparatos: List[Dict], n: int = 2) -> str:
    nombres = [_minuscula_inicial(a["nombre"]) for a in aparatos[:n]]
    return " y ".join(nombres) if len(nombres) <= 2 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def consejo_del_dia(resumen: Dict, franja: Optional[Dict]) -> Dict:
    """Un consejo concreto sobre los aparatos del usuario para la vista Mi Día."""
    if not resumen["tiene_aparatos"]:
        return {
            "tipo": "sin_aparatos",
            "titulo": "Registra tus aparatos",
            "mensaje": "Cuéntanos qué aparatos tienes y te diremos cuánto gasta cada uno y cuándo conviene usarlos.",
            "accion": "Ir a Mis aparatos",
        }
    if resumen["tiene_paneles"] and franja and resumen["desplazables"]:
        return {
            "tipo": "franja_solar",
            "titulo": f"Mejor hora para tus equipos: {franja['texto']}",
            "mensaje": (
                f"El sol más fuerte será {franja['texto']} (≈{franja['ghi_dia_kwh_m2']:.1f} kWh/m² en el día). "
                f"Deja para esa franja el uso de: {_nombres(resumen['desplazables'])}. Así tus paneles cubren ese consumo."
            ),
            "accion": None,
        }
    mayor = resumen["top"][0]
    consejo = CONSEJOS_POR_TIPO.get(mayor["tipo_aparato"], CONSEJOS_POR_TIPO["otro"])
    if len(resumen["aparatos"]) == 1 and not resumen["no_identificado_kwh_mes"]:
        # Con un solo aparato registrado el porcentaje (100%) no dice nada
        return {
            "tipo": "aparato_mayor",
            "titulo": f"Tu {nombre_aparato(mayor)} gasta ≈{mayor['kwh_mes']:.0f} kWh al mes",
            "mensaje": f"Son ≈${mayor['costo_mes']:,.0f} al mes. {consejo} Registra el resto de tus aparatos para ver cuál pesa más.",
            "accion": None,
        }
    return {
        "tipo": "aparato_mayor",
        "titulo": f"Tu {nombre_aparato(mayor)} es el {mayor['porcentaje']:.0f}% de tu consumo",
        "mensaje": f"Gasta ≈{mayor['kwh_mes']:.0f} kWh al mes (≈${mayor['costo_mes']:,.0f}). {consejo}",
        "accion": None,
    }


def texto_inventario_para_prompt(resumen: Dict, maximo: int = 15) -> str:
    """Inventario en texto plano para el prompt de Gemini."""
    if not resumen["tiene_aparatos"]:
        return "El usuario aún no registró sus aparatos."
    lineas = [
        f"- {a['nombre']} x{a['cantidad']}: {a['potencia_w']:.0f} W, {a['horas_dia']:g} h/día, "
        f"≈{a['kwh_mes']:.0f} kWh/mes ({a['porcentaje']:.0f}% del total, ≈${a['costo_mes']:,.0f}/mes)"
        f"{' [se puede mover de horario]' if a['desplazable'] else ''}"
        for a in resumen["aparatos"][:maximo]
    ]
    if resumen["no_identificado_kwh_mes"]:
        lineas.append(f"- Consumo no identificado (no explicado por los aparatos registrados): ≈{resumen['no_identificado_kwh_mes']:.0f} kWh/mes")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Avisos sobre los aparatos del usuario (se muestran en Mis aparatos, no en Alertas)
# ---------------------------------------------------------------------------
UMBRAL_SOBRE_INVENTARIO = 1.3    # factura 30% mayor que lo que suman los aparatos
UMBRAL_APARATO_DOMINANTE = 40.0  # % del consumo en un solo aparato


def avisos_aparatos(resumen: Dict) -> List[Dict]:
    """Avisos para Mis aparatos: la factura no cuadra con el inventario o un aparato concentra el consumo."""
    avisos: List[Dict] = []
    if not resumen.get("tiene_aparatos"):
        return avisos

    real = resumen.get("real_kwh_mes") or 0.0
    inventario = resumen.get("inventario_kwh_mes") or 0.0
    if real > 0 and inventario > 0 and real > inventario * UMBRAL_SOBRE_INVENTARIO:
        exceso = (real / inventario - 1) * 100
        avisos.append({
            "tipo": "consumo_sobre_inventario",
            "nivel": "amarillo",
            "titulo": "Tu factura no cuadra con tus aparatos",
            "mensaje": (
                f"Tu consumo del último mes ({real:.0f} kWh) es {exceso:.0f}% mayor que lo que suman tus "
                f"aparatos registrados ({inventario:.0f} kWh). Puede que falte algún aparato en la lista, "
                "que alguno se use más horas de las indicadas o que tenga una falla (por ejemplo, una nevera "
                "que no cierra bien)."
            ),
            "accion": "Agrega los aparatos que falten o corrige las horas de uso en la tabla.",
        })

    mayor = resumen["top"][0] if resumen.get("top") else None
    if mayor and mayor["porcentaje"] >= UMBRAL_APARATO_DOMINANTE and len(resumen["aparatos"]) > 1:
        consejo = CONSEJOS_POR_TIPO.get(mayor["tipo_aparato"], CONSEJOS_POR_TIPO["otro"])
        avisos.append({
            "tipo": "aparato_dominante",
            "nivel": "amarillo",
            "titulo": "Un aparato se lleva gran parte de tu consumo",
            "mensaje": (
                f"Tu {nombre_aparato(mayor)} es el {mayor['porcentaje']:.0f}% de tu consumo "
                f"(≈${mayor['costo_mes']:,.0f} al mes). {consejo}"
            ),
            "accion": None,
        })
    return avisos
