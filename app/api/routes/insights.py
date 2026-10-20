"""
Endpoints de insights orientados al usuario común (vista 'simple').
Combinan:
- Datos crudos de BD y APIs externas.
- Capa de traducción (insights_translator).
- LLM (Gemini) para resumen narrativo opcional.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import (
    Empresa,
    User,
    UserRole,
    ConsumoEnergetico,
    RadiacionSolar,
    Prediccion,
)
from app.api.deps.auth import get_current_user
from app.services.demo_data import get_consumo_demo, get_demo_empresa, get_radiacion_demo
from app.services.insights_translator import construir_resumen_dia
from app.services.openmeteo import openmeteo_service
from app.services.gemini_client import obtener_respuesta_gemini
from app.services.contexto_energetico import (
    consejo_del_dia,
    dimensionar_sistema,
    obtener_franja_solar,
    resumen_inventario,
    texto_inventario_para_prompt,
)

router = APIRouter(prefix="/insights", tags=["Insights (Vista Simple)"])


def _check_acceso(current_user: User, empresa_id: int):
    if (
        current_user.role == UserRole.EMPRESA
        and current_user.empresa_id != empresa_id
    ):
        raise HTTPException(status_code=403, detail="Sin permisos")


async def _consejo_aparatos(db: Session, empresa: Optional[Empresa]):
    """Consejo del día sobre los aparatos del usuario. Devuelve (consejo, resumen) o (None, None)."""
    if empresa is None:
        return None, None
    try:
        resumen_ap = resumen_inventario(db, empresa)
        franja = await obtener_franja_solar() if resumen_ap["tiene_aparatos"] else None
        return consejo_del_dia(resumen_ap, franja), resumen_ap
    except Exception as e:
        print(f"[INSIGHTS] No se pudo calcular el consejo de aparatos: {e}")
        return None, None


def _generar_narrativa_fallback(resumen: dict, empresa_nombre: str, empresa_tipo: str) -> str:
    """Genera un resumen narrativo de fallback rico y bien redactado a partir de las tarjetas."""
    tarjetas = resumen.get("tarjetas", {})
    
    dia_solar = tarjetas.get("dia_solar", {}).get("mensaje", "")
    consumo = tarjetas.get("consumo", {}).get("mensaje", "")
    produccion = tarjetas.get("produccion", {}).get("mensaje", "")
    riesgo = tarjetas.get("riesgo_apagon", {}).get("mensaje", "")
    bateria = tarjetas.get("bateria", {}).get("mensaje", "")
    
    es_hogar = (empresa_tipo == "hogar")
    
    if es_hogar:
        narrativa = (
            f"¡Hola! Analizamos los datos de tu hogar para el día de hoy. En cuanto a las condiciones climáticas de {get_settings().LOCATION_CITY}, {dia_solar} "
            f"Con respecto al comportamiento de tu casa, {consumo} Adicionalmente, sobre la autogeneración solar, {produccion}\n\n"
            f"Para mantener tu hogar seguro hoy, {riesgo} En cuanto al almacenamiento de energía en tu casa, {bateria} "
            f"¡Que tengas un gran día con tu familia en {empresa_nombre}!"
        )
    else:
        narrativa = (
            f"Informe de análisis operativo diario para {empresa_nombre}. Respecto a las condiciones de radiación solar en {get_settings().LOCATION_CITY}, {dia_solar} "
            f"En términos de demanda y costos energéticos, {consumo} Sobre la capacidad de generación propia distribuida, {produccion}\n\n"
            f"En la dimensión de resiliencia operativa y riesgos de red, {riesgo} Los sistemas de almacenamiento local reportan que {bateria} "
            f"Se sugiere mantener el seguimiento de estas métricas operativas para optimizar la eficiencia y rentabilidad hoy."
        )
    return narrativa


@router.get("/diario/{empresa_id}")
async def insights_diario(
    empresa_id: int,
    incluir_resumen_llm: bool = Query(True),
    escenario: str = Query("real", pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Devuelve el panel humano-amigable del día para la empresa:
    - score global (verde/amarillo/rojo)
    - tarjetas de día solar, consumo, producción, riesgo, aire y batería
    - resumen narrativo opcional generado por Gemini o fallback por plantilla
    """
    _check_acceso(current_user, empresa_id)
    if escenario == "demo":
        demo = get_demo_empresa()
        if empresa_id != demo["id"]:
            raise HTTPException(status_code=404, detail="Empresa demo no encontrada")
        ahora = datetime.now()
        consumos = get_consumo_demo(days=2)
        hoy = ahora.date()
        ayer = (ahora - timedelta(days=1)).date()
        consumos_hoy = [c for c in consumos if datetime.fromisoformat(c["fecha"]).date() == hoy]
        consumos_ayer = [c for c in consumos if datetime.fromisoformat(c["fecha"]).date() == ayer]
        consumo_hoy_kwh = sum(c.get("consumo_kwh", 0) for c in consumos_hoy) if consumos_hoy else None
        consumo_ayer_kwh = sum(c.get("consumo_kwh", 0) for c in consumos_ayer) if consumos_ayer else None
        produccion_kwh = sum(c.get("produccion_solar_kwh", 0) for c in consumos_hoy) if consumos_hoy else None
        nivel_bateria_pct = consumos_hoy[0].get("nivel_bateria_pct") if consumos_hoy else None
        rad = get_radiacion_demo(days=3)
        ghi_actual = rad[0].get("ghi") if rad else None
        riesgo_pct = 18.0
        polvo_pm10: Optional[float] = 36.0
        resumen = construir_resumen_dia(
            ghi=ghi_actual,
            consumo_hoy_kwh=consumo_hoy_kwh,
            consumo_ayer_kwh=consumo_ayer_kwh,
            produccion_kwh=produccion_kwh,
            riesgo_apagon_pct=riesgo_pct,
            polvo_pm10=polvo_pm10,
            nivel_bateria_pct=nivel_bateria_pct,
            tarifa_kwh=demo["tarifa_kwh"],
            tipo_empresa=demo.get("tipo", "pyme"),
            capacidad_paneles_kw=demo.get("capacidad_paneles_kw", 0.0),
            capacidad_bateria_kwh=demo.get("capacidad_bateria_kwh", 0.0),
        )
        resumen_narrativo = _generar_narrativa_fallback(resumen, demo["nombre"], demo.get("tipo", "pyme"))
        # La empresa demo también existe en la BD: si tiene aparatos registrados se usan para el consejo
        consejo, _ = await _consejo_aparatos(db, db.query(Empresa).filter(Empresa.id == empresa_id).first())
        return {
            "empresa": {"id": demo["id"], "nombre": demo["nombre"], "tipo": demo["tipo"]},
            "fecha": ahora.isoformat(),
            "score_global": resumen["score_global"],
            "tarjetas": resumen["tarjetas"],
            "consejo_aparatos": consejo,
            "resumen_narrativo": resumen_narrativo,
            "fuente_narrativa": "plantilla",
        }

    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    ahora = datetime.now()
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_ayer = inicio_hoy - timedelta(days=1)

    # ---- Consumo hoy / ayer ----
    consumos_hoy = (
        db.query(ConsumoEnergetico)
        .filter(
            ConsumoEnergetico.empresa_id == empresa_id,
            ConsumoEnergetico.fecha >= inicio_hoy,
            ConsumoEnergetico.fecha < inicio_hoy + timedelta(days=1),
        )
        .all()
    )
    consumos_ayer = (
        db.query(ConsumoEnergetico)
        .filter(
            ConsumoEnergetico.empresa_id == empresa_id,
            ConsumoEnergetico.fecha >= inicio_ayer,
            ConsumoEnergetico.fecha < inicio_hoy,
        )
        .all()
    )
    consumo_hoy_kwh = sum(c.consumo_kwh for c in consumos_hoy) if consumos_hoy else None
    consumo_ayer_kwh = sum(c.consumo_kwh for c in consumos_ayer) if consumos_ayer else None
    produccion_kwh = (
        sum(c.produccion_solar_kwh or 0 for c in consumos_hoy) if consumos_hoy else None
    )
    nivel_bateria_pct = (
        consumos_hoy[-1].nivel_bateria_pct if consumos_hoy else None
    )

    # ---- Radiación más reciente (BD) ----
    radiacion = (
        db.query(RadiacionSolar)
        .order_by(desc(RadiacionSolar.fecha))
        .first()
    )
    ghi_actual = radiacion.ghi if radiacion else None
    latest_date = radiacion.fecha.date() if radiacion and radiacion.fecha else None
    if latest_date != ahora.date():
        try:
            forecast = await openmeteo_service.get_forecast_diario(days=1, allow_synthetic=False)
        except Exception:
            forecast = []
        if forecast and forecast[0].get("ghi") is not None:
            ghi_actual = forecast[0]["ghi"]

    # ---- Riesgo de apagón (última predicción) ----
    pred_apagon = (
        db.query(Prediccion)
        .filter(
            Prediccion.empresa_id == empresa_id,
            Prediccion.tipo == "riesgo_apagon",
        )
        .order_by(desc(Prediccion.fecha_prediccion))
        .first()
    )
    riesgo_pct = pred_apagon.valor if pred_apagon else None

    # ---- Calidad del aire (Open-Meteo, no requiere BD) ----
    polvo_pm10: Optional[float] = None
    try:
        aire = await openmeteo_service.get_calidad_aire()
        if aire.get("disponible") and aire.get("datos"):
            primer = aire["datos"][0]
            polvo_pm10 = primer.get("polvo") or primer.get("pm10")
    except Exception:
        polvo_pm10 = None

    # ---- Aparatos del usuario y sistema solar sugerido ----
    consejo, resumen_ap = await _consejo_aparatos(db, empresa)
    sistema_sugerido = None
    if not empresa.capacidad_paneles_kw:
        try:
            sistema_sugerido = dimensionar_sistema(db, empresa, resumen_ap)
        except Exception as e:
            print(f"[INSIGHTS] No se pudo dimensionar el sistema solar: {e}")

    # ---- Construir tarjetas (capa de traducción) ----
    resumen = construir_resumen_dia(
        ghi=ghi_actual,
        consumo_hoy_kwh=consumo_hoy_kwh,
        consumo_ayer_kwh=consumo_ayer_kwh,
        produccion_kwh=produccion_kwh,
        riesgo_apagon_pct=riesgo_pct,
        polvo_pm10=polvo_pm10,
        nivel_bateria_pct=nivel_bateria_pct,
        tarifa_kwh=empresa.tarifa_kwh,
        tipo_empresa=empresa.tipo,
        capacidad_paneles_kw=empresa.capacidad_paneles_kw,
        capacidad_bateria_kwh=empresa.capacidad_bateria_kwh,
        sistema_sugerido=sistema_sugerido,
    )

    # ---- Resumen narrativo (LLM) ----
    resumen_llm = None
    fuente = "plantilla"
    if incluir_resumen_llm:
        bloque_aparatos = ""
        if resumen_ap and resumen_ap["tiene_aparatos"]:
            bloque_aparatos = (
                f"\nAparatos del usuario:\n{texto_inventario_para_prompt(resumen_ap, maximo=8)}\n"
                f"Consejo del día sobre sus aparatos: {consejo['titulo']}. {consejo['mensaje']}\n"
                "Menciona al menos uno de sus aparatos por su nombre en el consejo de cierre.\n"
            )
        prompt = f"""Genera un resumen diario (de 2 a 3 párrafos cortos) para el hogar "{empresa.nombre}" (Sector: Residencial) en base a los siguientes datos operativos y climáticos de hoy:
Datos del día: {resumen}
{bloque_aparatos}
Da un consejo corto de cierre familiar.""" if empresa.tipo == "hogar" else f"""Genera un resumen diario (de 2 a 3 párrafos cortos) para la empresa "{empresa.nombre}" (Sector: {empresa.tipo or 'PYME'}) en base a los siguientes datos operativos y climáticos de hoy:
Datos del día: {resumen}
{bloque_aparatos}
Da un consejo corto de cierre."""
        
        lugar = get_settings().LOCATION_NAME
        system_instruction = f"Eres un asistente virtual de análisis energético de {lugar}. Hablas de forma familiar, concisa y optimista hoy." if empresa.tipo == "hogar" else f"Eres un asistente virtual de análisis energético de {lugar}. Hablas de forma ejecutiva, concisa y optimista."
        
        try:
            resumen_llm = await obtener_respuesta_gemini(
                prompt=prompt,
                system_instruction=system_instruction,
            )
            if resumen_llm:
                fuente = "gemini"
        except Exception as e:
            print(f"Excepción capturada al obtener respuesta de Gemini: {e}")
            resumen_llm = None

    if not resumen_llm:
        resumen_llm = _generar_narrativa_fallback(resumen, empresa.nombre, empresa.tipo)
        fuente = "plantilla"

    return {
        "empresa": {
            "id": empresa.id,
            "nombre": empresa.nombre,
            "tipo": empresa.tipo,
        },
        "fecha": ahora.isoformat(),
        "score_global": resumen["score_global"],
        "tarjetas": resumen["tarjetas"],
        "consejo_aparatos": consejo,
        "resumen_narrativo": resumen_llm,
        "fuente_narrativa": fuente,
    }

