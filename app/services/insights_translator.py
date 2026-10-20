"""
Capa de traducción: convierte métricas crudas en mensajes accionables.

Pensado para usuarios no técnicos (vista 'simple'). Cada función devuelve un dict
con: emoji, nivel (verde/amarillo/rojo), titulo y mensaje en lenguaje natural.
"""
from typing import Dict, Optional

from app.core.config import get_settings


# ---------------------------------------------------------------------------
# Niveles estándar (semáforo)
# ---------------------------------------------------------------------------
NIVEL_VERDE = "verde"
NIVEL_AMARILLO = "amarillo"
NIVEL_ROJO = "rojo"


def _pkg(emoji: str, nivel: str, titulo: str, mensaje: str, accion: Optional[str] = None) -> Dict:
    return {
        "emoji": emoji,
        "nivel": nivel,
        "titulo": titulo,
        "mensaje": mensaje,
        "accion": accion,
    }


# ---------------------------------------------------------------------------
# Radiación / día solar
# ---------------------------------------------------------------------------
def traducir_radiacion(ghi: Optional[float], tipo_empresa: str = "pyme") -> Dict:
    """Traduce GHI (kWh/m²/día) a mensaje accionable."""
    es_hogar = (tipo_empresa == "hogar")
    
    if ghi is None:
        return _pkg("❓", NIVEL_AMARILLO, "Sin datos solares", "Aún no hay datos de radiación. Sincroniza Open-Meteo.", "Ir a Datos Solares")
    
    if ghi >= 6.0:
        msg = (
            f"Hoy el sol está espectacular para tu hogar (≈{ghi:.1f} kWh/m²). "
            "Es ideal encender electrodomésticos de mayor consumo como lavadora, secadora o aire acondicionado entre 10 AM y 2 PM."
            if es_hogar else
            f"Hoy el sol está fuerte (≈{ghi:.1f} kWh/m²). Es ideal operar a máxima carga entre 10 AM y 2 PM."
        )
        action = "Usa electrodomésticos pesados a media mañana" if es_hogar else "Programa equipos pesados a media mañana"
        return _pkg("☀️", NIVEL_VERDE, "Día solar excelente", msg, action)
        
    if ghi >= 4.5:
        msg = (
            f"Buen día solar para tu casa (≈{ghi:.1f} kWh/m²). La radiación solar de hoy cubrirá una parte importante del consumo de tu refrigerador y luces."
            if es_hogar else
            f"La radiación de hoy (≈{ghi:.1f} kWh/m²) cubrirá una parte importante de tu consumo."
        )
        return _pkg("⛅", NIVEL_VERDE, "Buen día solar", msg, "Aprovecha la franja 11 AM - 1 PM")
        
    if ghi >= 3.0:
        msg = (
            f"Hoy el sol está más suave (≈{ghi:.1f} kWh/m²). Te sugerimos optimizar el uso del aire acondicionado y apagar las luces en habitaciones vacías."
            if es_hogar else
            f"Hoy hay menos sol (≈{ghi:.1f} kWh/m²). Limita el uso de aire acondicionado y equipos no esenciales."
        )
        action = "Evita dejar cargadores o luces encendidas" if es_hogar else "Reduce cargas no críticas"
        return _pkg("🌥️", NIVEL_AMARILLO, "Día solar regular", msg, action)
        
    msg = (
        f"Muy poca radiación hoy en {get_settings().LOCATION_CITY} (≈{ghi:.1f} kWh/m²). Tu hogar consumirá principalmente de la red eléctrica general de Air-E."
        if es_hogar else
        f"Muy poca radiación hoy (≈{ghi:.1f} kWh/m²). Prioriza consumir desde batería o red."
    )
    action = None if es_hogar else "Carga baterías cuando haya luz"
    return _pkg("🌧️", NIVEL_ROJO, "Día solar bajo", msg, action)


# ---------------------------------------------------------------------------
# Consumo vs comparativa
# ---------------------------------------------------------------------------
def traducir_consumo(
    consumo_hoy_kwh: Optional[float],
    consumo_ayer_kwh: Optional[float],
    tarifa_kwh: float = 943.0,
    tipo_empresa: str = "pyme",
) -> Dict:
    es_hogar = (tipo_empresa == "hogar")
    
    if consumo_hoy_kwh is None:
        return _pkg(
            "❓", NIVEL_AMARILLO, 
            "Sin datos de consumo", 
            "Registra tu recibo de luz mensual en la pestaña Consumo para ver el análisis de tu hogar." if es_hogar else "Carga tu archivo de consumo para ver el análisis.", 
            "Registrar Factura Mensual" if es_hogar else "Subir CSV/Excel"
        )

    costo_hoy = consumo_hoy_kwh * tarifa_kwh
    if consumo_ayer_kwh and consumo_ayer_kwh > 0:
        delta_pct = ((consumo_hoy_kwh - consumo_ayer_kwh) / consumo_ayer_kwh) * 100
    else:
        delta_pct = 0

    if delta_pct > 20:
        msg = f"Tu hogar lleva {consumo_hoy_kwh:.1f} kWh hoy (≈ ${costo_hoy:,.0f}). ¡Es {delta_pct:+.0f}% más que ayer!" if es_hogar else f"Llevas {consumo_hoy_kwh:.0f} kWh hoy (≈ ${costo_hoy:,.0f}). Es {delta_pct:+.0f}% más que ayer."
        action = "Revisa luces o electrodomésticos encendidos sin uso" if es_hogar else "Revisa equipos encendidos sin uso"
        return _pkg("🔺", NIVEL_ROJO, "Consumo elevado", msg, action)
        
    if delta_pct > 5:
        msg = f"Tu hogar lleva {consumo_hoy_kwh:.1f} kWh hoy (≈ ${costo_hoy:,.0f}), {delta_pct:+.0f}% vs ayer." if es_hogar else f"Llevas {consumo_hoy_kwh:.0f} kWh hoy (≈ ${costo_hoy:,.0f}), {delta_pct:+.0f}% vs ayer."
        action = "Vigila el uso del aire acondicionado hoy" if es_hogar else "Vigila los próximos picos"
        return _pkg("📈", NIVEL_AMARILLO, "Consumo en aumento", msg, action)
        
    if delta_pct < -10:
        msg = f"¡Buen ahorro familiar! Solo {consumo_hoy_kwh:.1f} kWh hoy (≈ ${costo_hoy:,.0f}). Es {abs(delta_pct):.0f}% menos que ayer." if es_hogar else f"Solo {consumo_hoy_kwh:.0f} kWh hoy (≈ ${costo_hoy:,.0f}). Es {abs(delta_pct):.0f}% menos que ayer. ¡Bien!"
        action = "¡Excelente hábito familiar!" if es_hogar else "Mantén el ritmo"
        return _pkg("📉", NIVEL_VERDE, "Buen ahorro", msg, action)
        
    msg = f"Tu hogar registra {consumo_hoy_kwh:.1f} kWh hoy (≈ ${costo_hoy:,.0f}). Similar a ayer." if es_hogar else f"Llevas {consumo_hoy_kwh:.0f} kWh hoy (≈ ${costo_hoy:,.0f}). Similar a ayer."
    return _pkg("✅", NIVEL_VERDE, "Consumo estable", msg, None)


# ---------------------------------------------------------------------------
# Producción solar
# ---------------------------------------------------------------------------
def traducir_produccion_solar(
    produccion_kwh: Optional[float],
    consumo_kwh: Optional[float],
    tarifa_kwh: float = 943.0,
    tipo_empresa: str = "pyme",
    capacidad_paneles_kw: float = 0.0,
    sistema_sugerido: Optional[Dict] = None,
) -> Dict:
    es_hogar = (tipo_empresa == "hogar")
    
    if not capacidad_paneles_kw:
        if sistema_sugerido and sistema_sugerido.get("kwp_sugerido") and sistema_sugerido.get("consumo_mes_kwh"):
            mensaje = (
                f"No tienes paneles registrados. Un sistema de {sistema_sugerido['kwp_sugerido']} kWp produciría "
                f"≈{sistema_sugerido['produccion_mes_kwh']:.0f} kWh al mes, cerca del {sistema_sugerido['cobertura_pct']:.0f}% "
                f"de tu consumo (ahorro ≈ ${sistema_sugerido['ahorro_mes_cop']:,.0f} al mes)."
            )
        else:
            sim_capacity = (sistema_sugerido or {}).get("kwp_sugerido") or (2.5 if es_hogar else 10.0)
            mensaje = f"No tienes paneles registrados. Estimamos que un sistema sugerido de {sim_capacity} kWp cubriría gran parte de tu consumo diario."
        return _pkg(
            "💡", NIVEL_VERDE,
            "Simulador Solar Activo",
            mensaje,
            "Simula tu ahorro en el Dashboard"
        )
        
    if not produccion_kwh:
        return _pkg(
            "🪫", NIVEL_AMARILLO,
            "Sin paneles activos",
            "No hay producción solar registrada en tu hogar. Verifica que el interruptor solar esté encendido." if es_hogar else "No hay producción solar registrada. Si tienes paneles, verifica el inversor.",
            "Verificar interruptor solar" if es_hogar else "Configura capacidad de paneles"
        )
        
    ahorro = produccion_kwh * tarifa_kwh
    cobertura = (produccion_kwh / consumo_kwh * 100) if consumo_kwh else 0

    if cobertura >= 60:
        msg = f"¡Tus paneles solares están rindiendo al máximo! Generaste {produccion_kwh:.1f} kWh hoy. Cubriste el {cobertura:.0f}% del consumo de tu casa (ahorro familiar ≈ ${ahorro:,.0f})." if es_hogar else f"Generaste {produccion_kwh:.0f} kWh hoy. Cubrió el {cobertura:.0f}% de tu consumo (ahorro ≈ ${ahorro:,.0f})."
        return _pkg("🌞", NIVEL_VERDE, "Rendimiento pleno", msg, None)
        
    if cobertura >= 30:
        msg = f"Tus paneles generaron {produccion_kwh:.1f} kWh hoy, cubriendo el {cobertura:.0f}% de tu consumo (ahorro ≈ ${ahorro:,.0f})." if es_hogar else f"Tus paneles generaron {produccion_kwh:.0f} kWh (ahorro ≈ ${ahorro:,.0f})."
        return _pkg("🌤️", NIVEL_VERDE, "Producción solar correcta", msg, None)
        
    msg = f"Baja generación hoy ({produccion_kwh:.1f} kWh). Puede deberse a nubosidad o suciedad por polvo del desierto." if es_hogar else f"Solo {produccion_kwh:.0f} kWh generados hoy. Puede ser por nubes o suciedad en paneles."
    action = "Considera sacudir el polvo de los paneles" if es_hogar else "Considera limpiar los paneles"
    return _pkg("⚠️", NIVEL_AMARILLO, "Producción solar baja", msg, action)


# ---------------------------------------------------------------------------
# Riesgo de apagón
# ---------------------------------------------------------------------------
def traducir_riesgo_apagon(riesgo_pct: Optional[float], tipo_empresa: str = "pyme") -> Dict:
    es_hogar = (tipo_empresa == "hogar")
    
    if riesgo_pct is None:
        if es_hogar:
            return _pkg(
                "🛡️", NIVEL_VERDE,
                "Estabilidad de Red",
                "El servicio eléctrico en tu zona residencial se reporta estable hoy. Sin reportes de cortes.",
                None
            )
        return _pkg("❓", NIVEL_AMARILLO, "Sin predicción de apagón", "Genera predicciones para evaluar el riesgo.", "Generar predicción")
        
    if riesgo_pct >= 40:
        msg = f"Riesgo de corte de luz estimado en {riesgo_pct:.0f}%. Asegúrate de mantener cargados tus teléfonos y desconectar equipos delicados." if es_hogar else f"Probabilidad estimada {riesgo_pct:.0f}%. Carga baterías y prepara plan de contingencia."
        action = "Desconecta electrodomésticos delicados" if es_hogar else "Reduce cargas no críticas en la noche"
        return _pkg("🔴", NIVEL_ROJO, "Riesgo de apagón alto", msg, action)
        
    if riesgo_pct >= 20:
        msg = f"Riesgo medio de cortes de luz hoy ({riesgo_pct:.0f}%). Se detecta inestabilidad en la red del circuito local." if es_hogar else f"Probabilidad estimada {riesgo_pct:.0f}%. Mantén equipos críticos respaldados."
        action = None if es_hogar else "Verifica nivel de batería"
        return _pkg("🟡", NIVEL_AMARILLO, "Riesgo medio de apagón", msg, action)
        
    msg = "La red eléctrica residencial se reporta con alta estabilidad hoy. ¡Día tranquilo!" if es_hogar else f"Probabilidad estimada {riesgo_pct:.0f}%. Operación normal."
    return _pkg("🟢", NIVEL_VERDE, "Riesgo bajo de apagón", msg, None)


# ---------------------------------------------------------------------------
# Calidad del aire / polvo en paneles
# ---------------------------------------------------------------------------
def traducir_polvo(
    pm10: Optional[float], 
    polvo: Optional[float] = None, 
    tipo_empresa: str = "pyme", 
    capacidad_paneles_kw: float = 0.0
) -> Dict:
    es_hogar = (tipo_empresa == "hogar")
    valor = polvo if polvo is not None else pm10
    
    if capacidad_paneles_kw == 0.0:
        if valor is None:
            return _pkg("🍃", NIVEL_VERDE, "Calidad del Aire", f"El aire de {get_settings().LOCATION_CITY} está agradable y limpio hoy.", None)
        if valor >= 80:
            return _pkg(
                "💨", NIVEL_AMARILLO,
                f"Polvo moderado en {get_settings().LOCATION_CITY}",
                f"PM10/polvo en {valor:.0f} µg/m³. Se siente algo de brisa seca en tu sector residencial.",
                None
            )
        return _pkg(
            "🍃", NIVEL_VERDE,
            "Aire agradable",
            f"Buena calidad del aire hoy en {get_settings().LOCATION_CITY} ({valor:.0f} µg/m³). Un ambiente fresco para tu familia.",
            None
        )
        
    if valor is None:
        return _pkg("❓", NIVEL_AMARILLO, "Sin datos de aire", "Calidad del aire no disponible.", None)
        
    if valor >= 80:
        msg = f"PM10/polvo en {valor:.0f} µg/m³. La acumulación de arena en tus paneles puede reducir su producción familiar hasta 15%." if es_hogar else f"PM10/polvo en {valor:.0f} µg/m³. Tus paneles pueden perder hasta 15% de eficiencia."
        action = "Limpia tus paneles esta semana" if es_hogar else "Limpia los paneles esta semana"
        return _pkg("🟤", NIVEL_ROJO, "Polvo alto en el aire", msg, action)
        
    if valor >= 40:
        msg = f"Polvo moderado ({valor:.0f} µg/m³). Recuerda programar una limpieza rápida de los paneles pronto." if es_hogar else f"Aire con polvo ({valor:.0f} µg/m³). Considera limpieza pronto."
        action = "Programa limpieza rápida" if es_hogar else "Programa limpieza próxima"
        return _pkg("💨", NIVEL_AMARILLO, "Polvo moderado", msg, action)
        
    msg = f"Aire sumamente limpio ({valor:.0f} µg/m³). Tus paneles solares captan energía al 100% de su capacidad." if es_hogar else f"Buena calidad del aire ({valor:.0f} µg/m³). Paneles operando con eficiencia plena."
    return _pkg("🌬️", NIVEL_VERDE, "Aire limpio", msg, None)


# ---------------------------------------------------------------------------
# Batería
# ---------------------------------------------------------------------------
def traducir_bateria(
    nivel_pct: Optional[float], 
    tipo_empresa: str = "pyme", 
    capacidad_bateria_kwh: float = 0.0
) -> Dict:
    es_hogar = (tipo_empresa == "hogar")
    
    if capacidad_bateria_kwh == 0.0:
        return _pkg(
            "🔌", NIVEL_VERDE,
            "Respaldo de Red",
            "Tu hogar cuenta con respaldo directo de la red eléctrica general. No requieres acumuladores.",
            None
        )
        
    if nivel_pct is None:
        return _pkg("🔋", NIVEL_AMARILLO, "Sin lectura de batería", "No hay datos del banco de baterías.", None)
        
    if nivel_pct >= 70:
        return _pkg("🔋", NIVEL_VERDE, "Batería cargada", f"Nivel {nivel_pct:.0f}%. Listo para soportar cortes.", None)
        
    if nivel_pct >= 30:
        return _pkg("🔋", NIVEL_AMARILLO, "Batería media", f"Nivel {nivel_pct:.0f}%. Recarga si prevés cortes de servicio.", "Optimiza consumo en tu casa" if es_hogar else "Reduce consumo nocturno")
        
    msg = f"Batería en nivel crítico ({nivel_pct:.0f}%). Apaga luces o artefactos que no estés usando de inmediato." if es_hogar else f"Solo {nivel_pct:.0f}% de carga. Apaga equipos no esenciales."
    action = "Desconecta equipos a batería" if es_hogar else "Conecta cargas a red mientras se carga"
    return _pkg("🪫", NIVEL_ROJO, "Batería baja", msg, action)


# ---------------------------------------------------------------------------
# Resumen completo del día (todas las capas)
# ---------------------------------------------------------------------------
def construir_resumen_dia(
    ghi: Optional[float] = None,
    consumo_hoy_kwh: Optional[float] = None,
    consumo_ayer_kwh: Optional[float] = None,
    produccion_kwh: Optional[float] = None,
    riesgo_apagon_pct: Optional[float] = None,
    polvo_pm10: Optional[float] = None,
    nivel_bateria_pct: Optional[float] = None,
    tarifa_kwh: float = 943.0,
    tipo_empresa: str = "pyme",
    capacidad_paneles_kw: float = 0.0,
    capacidad_bateria_kwh: float = 0.0,
    sistema_sugerido: Optional[Dict] = None,
) -> Dict:
    """Devuelve el paquete completo de tarjetas para la vista 'simple'."""
    tarjetas = [
        ("dia_solar", traducir_radiacion(ghi, tipo_empresa)),
        ("consumo", traducir_consumo(consumo_hoy_kwh, consumo_ayer_kwh, tarifa_kwh, tipo_empresa)),
        ("produccion", traducir_produccion_solar(produccion_kwh, consumo_hoy_kwh, tarifa_kwh, tipo_empresa, capacidad_paneles_kw, sistema_sugerido)),
        ("riesgo_apagon", traducir_riesgo_apagon(riesgo_apagon_pct, tipo_empresa)),
        ("aire", traducir_polvo(polvo_pm10, tipo_empresa=tipo_empresa, capacidad_paneles_kw=capacidad_paneles_kw)),
        ("bateria", traducir_bateria(nivel_bateria_pct, tipo_empresa, capacidad_bateria_kwh)),
    ]
    score_global = _score_global([t for _, t in tarjetas])
    return {
        "score_global": score_global,
        "tarjetas": {k: v for k, v in tarjetas},
    }


def _score_global(tarjetas: list) -> Dict:
    """Calcula un nivel global agregando los semáforos."""
    rojos = sum(1 for t in tarjetas if t.get("nivel") == NIVEL_ROJO)
    amarillos = sum(1 for t in tarjetas if t.get("nivel") == NIVEL_AMARILLO)
    if rojos >= 2:
        return {"emoji": "🔴", "nivel": NIVEL_ROJO, "titulo": "Día crítico — atención requerida"}
    if rojos == 1 or amarillos >= 3:
        return {"emoji": "🟡", "nivel": NIVEL_AMARILLO, "titulo": "Día con avisos importantes"}
    return {"emoji": "🟢", "nivel": NIVEL_VERDE, "titulo": "Día energético tranquilo"}
