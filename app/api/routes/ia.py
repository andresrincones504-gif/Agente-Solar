import os
import time
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models.models import Empresa, Recomendacion, User, UserRole
from app.schemas.schemas import RecomendacionResponse
from app.services.agents.agente_consumo import agente_consumo
from app.services.agents.agente_recomendaciones import agente_recomendaciones
from app.services.agents.agente_solar import agente_solar
from app.services.demo_data import get_consumo_demo, get_demo_empresa, get_radiacion_demo
from app.services.demo_ops import list_demo_recs, mark_demo_rec_applied, save_demo_recs

router = APIRouter(prefix="/ia", tags=["Motor IA"])


def _check_acceso(current_user: User, empresa_id: int):
    if current_user.role == UserRole.EMPRESA and current_user.empresa_id != empresa_id:
        raise HTTPException(status_code=403, detail="Sin permisos")


def _demo_recs(empresa_id: int) -> list[dict]:
    rows = list_demo_recs(empresa_id)
    if rows:
        return rows
    return save_demo_recs(
        empresa_id,
        [
            {"texto": "Concentre cargas altas entre 10:00 y 14:00 para aprovechar el pico solar.", "tipo": "redistribucion", "impacto_cop": 82000, "confianza": 82.0},
            {"texto": "Programe limpieza de paneles cada 2 semanas por carga de polvo local.", "tipo": "mantenimiento", "impacto_cop": 45000, "confianza": 78.0},
        ],
    )


GEMINI_HOST = "https://generativelanguage.googleapis.com/"
SEGUNDOS_CACHE_CONEXION = 60  # para no consultar a Google en cada carga de página
_conexion_cache = {"ok": None, "revisado": 0.0}


async def _hay_conexion_gemini(refrescar: bool = False) -> bool:
    """True si el servidor llega a Gemini. Cualquier respuesta HTTP (incluso un 404) cuenta como conexión."""
    ahora = time.monotonic()
    if (
        not refrescar
        and _conexion_cache["ok"] is not None
        and ahora - _conexion_cache["revisado"] < SEGUNDOS_CACHE_CONEXION
    ):
        return _conexion_cache["ok"]
    try:
        async with httpx.AsyncClient(timeout=3.0) as cliente:
            await cliente.get(GEMINI_HOST)
        ok = True
    except httpx.HTTPError:
        ok = False
    _conexion_cache.update(ok=ok, revisado=ahora)
    return ok


@router.get("/status")
async def get_ia_status(refrescar: bool = Query(False, description="Vuelve a revisar la conexión sin usar la caché")):
    """
    Estado del motor de recomendaciones:
    - con_ia: hay clave de Gemini y el servidor tiene conexión.
    - sin_conexion: hay clave pero no se llega a Gemini (sin internet); se usan las reglas.
    - sin_clave: Gemini no está configurado; se usan las reglas.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    tiene_clave = bool(api_key and not api_key.startswith("tu_api_key"))
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    conectado = await _hay_conexion_gemini(refrescar) if tiene_clave else False
    disponible = tiene_clave and conectado
    estado = "con_ia" if disponible else ("sin_conexion" if tiene_clave else "sin_clave")
    return {
        "gemini_disponible": disponible,
        "estado": estado,
        "modelo": model if disponible else "Heurístico Local (Reglas)",
        "api": "Google GenAI" if disponible else "Motor Local",
        "modo": f"LLM Gemini ({model})" if disponible else "Heurístico Local (Reglas)",
    }


@router.get("/analisis/solar/{empresa_id}")
def analisis_solar(
    empresa_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        if empresa_id != get_demo_empresa()["id"]:
            raise HTTPException(status_code=404, detail="Empresa demo no encontrada")
        rows = get_radiacion_demo(days=30)
        if not rows:
            return {"promedio_ghi": 0, "produccion_estimada_diaria_kwh": 0, "ahorro_estimado_mensual_cop": 0, "mensaje": "Sin datos demo"}
        ghi_vals = [r.get("ghi") or 0 for r in rows]
        promedio = sum(ghi_vals) / len(ghi_vals)
        prod = round(promedio * 15.0 * 0.80, 2)
        return {
            "promedio_ghi": round(promedio, 2),
            "max_ghi": round(max(ghi_vals), 2),
            "min_ghi": round(min(ghi_vals), 2),
            "produccion_estimada_diaria_kwh": prod,
            "produccion_estimada_mensual_kwh": round(prod * 30, 2),
            "ahorro_estimado_mensual_cop": round(prod * 30 * 943.0, 0),
            "dias_analizados": len(rows),
            "mensaje": "Analisis demo calculado desde JSON.",
        }
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return agente_solar.analizar(db, empresa)


@router.get("/analisis/consumo/{empresa_id}")
def analisis_consumo(
    empresa_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        if empresa_id != get_demo_empresa()["id"]:
            raise HTTPException(status_code=404, detail="Empresa demo no encontrada")
        rows = get_consumo_demo(days=30)
        if not rows:
            return {"total_kwh": 0, "promedio_diario_kwh": 0, "num_anomalias": 0, "mensaje": "Sin datos demo"}
        vals = [r.get("consumo_kwh") or 0 for r in rows]
        total = sum(vals)
        prom = total / len(vals)
        return {
            "total_kwh": round(total, 2),
            "promedio_diario_kwh": round(prom, 2),
            "std_kwh": 0,
            "costo_total_cop": round(sum((r.get("costo_cop") or 0) for r in rows), 0),
            "demanda_pico_kw": round(max((r.get("demanda_pico_kw") or 0) for r in rows), 2),
            "dia_mayor_consumo": {"fecha": rows[0]["fecha"], "consumo_kwh": max(vals)},
            "anomalias": [],
            "num_anomalias": 0,
            "tarifa_kwh": 943.0,
            "mensaje": "Analisis demo calculado desde JSON.",
        }
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return agente_consumo.analizar(db, empresa)


@router.post("/recomendaciones/{empresa_id}", response_model=List[RecomendacionResponse])
async def generar_recomendaciones(
    empresa_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        solar = analisis_solar(empresa_id=empresa_id, escenario="demo", db=db, current_user=current_user)
        consumo = analisis_consumo(empresa_id=empresa_id, escenario="demo", db=db, current_user=current_user)
        empresa_demo = Empresa(
            id=empresa_id,
            nombre=get_demo_empresa()["nombre"],
            tipo=get_demo_empresa()["tipo"],
            ciudad=get_demo_empresa()["ciudad"],
            departamento=get_demo_empresa()["departamento"],
            tarifa_kwh=get_demo_empresa()["tarifa_kwh"],
            capacidad_paneles_kw=get_demo_empresa()["capacidad_paneles_kw"],
            capacidad_bateria_kwh=get_demo_empresa()["capacidad_bateria_kwh"],
        )
        # La empresa demo también existe en la BD: si tiene aparatos, las recomendaciones los nombran
        ctx = None
        empresa_db = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if empresa_db:
            try:
                ctx = await agente_recomendaciones.contexto(db, empresa_db)
            except Exception as e:
                print(f"[RECOMENDACIONES] Sin contexto de aparatos para la demo: {e}")
        recs = await agente_recomendaciones._generar_con_llm(empresa_demo, solar, consumo, ctx)
        if not recs:
            recs = agente_recomendaciones._generar_con_reglas(empresa_demo, solar, consumo, ctx)
        return save_demo_recs(empresa_id, recs)
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if escenario:
        empresa.escenario_default = escenario
    solar = agente_solar.analizar(db, empresa)
    consumo = agente_consumo.analizar(db, empresa)
    return await agente_recomendaciones.generar(db, empresa, solar, consumo)


@router.get("/recomendaciones/{empresa_id}", response_model=List[RecomendacionResponse])
async def list_recomendaciones(
    empresa_id: int,
    limit: int = 20,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        rows = list_demo_recs(empresa_id)
        if not rows:
            # Generar recomendaciones de demostración iniciales de forma proactiva
            try:
                rows = await generar_recomendaciones(empresa_id, escenario="demo", db=db, current_user=current_user)
            except Exception as e:
                print(f"[AUTO-RECS DEMO ERROR] {e}")
                rows = _demo_recs(empresa_id)
        return rows[:limit]
    _check_acceso(current_user, empresa_id)
    q = db.query(Recomendacion).filter(
        Recomendacion.empresa_id == empresa_id,
        Recomendacion.escenario == escenario
    )
    rows = q.order_by(desc(Recomendacion.created_at)).limit(limit).all()
    if not rows:
        # Generar recomendaciones automáticas en tiempo real si la BD está vacía
        try:
            rows = await generar_recomendaciones(empresa_id, escenario=escenario, db=db, current_user=current_user)
        except Exception as e:
            print(f"[AUTO-RECS REAL ERROR] {e}")
            rows = []
    return rows[:limit]


@router.patch("/recomendaciones/{rec_id}/aplicar", response_model=RecomendacionResponse)
def marcar_aplicada(
    rec_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        rec = mark_demo_rec_applied(rec_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recomendacion demo no encontrada")
        return rec
    rec = db.query(Recomendacion).filter(Recomendacion.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recomendacion no encontrada")
    _check_acceso(current_user, rec.empresa_id)
    rec.aplicada = True
    db.commit()
    db.refresh(rec)
    return rec
