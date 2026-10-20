from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.models import Prediccion, Empresa, User, UserRole
from app.schemas.schemas import PrediccionResponse
from app.api.deps.auth import get_current_user
from app.services.agents.agente_prediccion import agente_prediccion
from app.services.demo_data import get_consumo_demo, get_demo_empresa
from app.services.demo_ops import list_demo_preds, save_demo_preds

router = APIRouter(prefix="/predicciones", tags=["Predicciones"])


def _check_acceso(current_user: User, empresa_id: int):
    if (
        current_user.role == UserRole.EMPRESA
        and current_user.empresa_id != empresa_id
    ):
        raise HTTPException(status_code=403, detail="Sin permisos")


@router.post("/generar/{empresa_id}")
async def generar_predicciones(
    empresa_id: int,
    horas_horizonte: int = Query(72, ge=24, le=168),
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera predicciones a 24-168h para la empresa."""
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        consumos = get_consumo_demo(days=30)
        prom = (sum((c.get("consumo_kwh") or 0) for c in consumos) / len(consumos)) if consumos else 380.0
        tarifa = float(get_demo_empresa().get("tarifa_kwh", 943.0))
        pasos_dias = max(1, min(7, horas_horizonte // 24))
        base_id = int(now.timestamp())
        rows = []
        resumen = []
        for i in range(1, pasos_dias + 1):
            fecha_obj = now + timedelta(days=i)
            prod = round(max(25.0, 72.0 - (i - 1) * 3.5), 2)
            cons = round(prom * (1 + (0.01 * ((i % 3) - 1))), 2)
            costo = round(max(0, cons - prod) * tarifa, 0)
            rows.extend(
                [
                    {"id": base_id + i * 10 + 1, "empresa_id": empresa_id, "fecha_prediccion": now.isoformat(), "fecha_objetivo": fecha_obj.isoformat(), "tipo": "produccion_solar", "valor": prod, "unidad": "kWh", "confianza_pct": 76.0, "escenario": "demo", "origen_dato": "json_demo", "confiabilidad_datos": 55.0, "created_at": now.isoformat()},
                    {"id": base_id + i * 10 + 2, "empresa_id": empresa_id, "fecha_prediccion": now.isoformat(), "fecha_objetivo": fecha_obj.isoformat(), "tipo": "consumo", "valor": cons, "unidad": "kWh", "confianza_pct": 70.0, "escenario": "demo", "origen_dato": "json_demo", "confiabilidad_datos": 55.0, "created_at": now.isoformat()},
                    {"id": base_id + i * 10 + 3, "empresa_id": empresa_id, "fecha_prediccion": now.isoformat(), "fecha_objetivo": fecha_obj.isoformat(), "tipo": "costo", "valor": costo, "unidad": "COP", "confianza_pct": 70.0, "escenario": "demo", "origen_dato": "json_demo", "confiabilidad_datos": 55.0, "created_at": now.isoformat()},
                ]
            )
            resumen.append({"fecha": fecha_obj.isoformat(), "produccion_solar_kwh": prod, "consumo_kwh": cons, "costo_cop": costo, "ghi_diario_kwh_m2": round(prod / (15.0 * 0.8), 2)})
        rows.append(
            {"id": base_id + 999, "empresa_id": empresa_id, "fecha_prediccion": now.isoformat(), "fecha_objetivo": (now + timedelta(hours=24)).isoformat(), "tipo": "riesgo_apagon", "valor": 18.0, "unidad": "%", "confianza_pct": 60.0, "escenario": "demo", "origen_dato": "json_demo", "confiabilidad_datos": 55.0, "created_at": now.isoformat()}
        )
        save_demo_preds(empresa_id, rows)
        return {
            "predicciones_diarias": resumen,
            "riesgo_apagon_24h_pct": 18.0,
            "promedio_consumo_diario_kwh": round(prom, 2),
            "total_predicciones_guardadas": len(rows),
            "fuente_principal": "json_demo",
            "fuente_complemento": "json_demo",
        }
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if escenario:
        empresa.escenario_default = escenario
    try:
        resultado = await agente_prediccion.predecir(db, empresa, horas_horizonte)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return resultado


@router.get("/{empresa_id}", response_model=List[PrediccionResponse])
async def list_predicciones(
    empresa_id: int,
    tipo: Optional[str] = None,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista predicciones recientes para la empresa."""
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        rows = list_demo_preds(empresa_id, tipo=tipo)
        if not rows:
            try:
                await generar_predicciones(empresa_id, horas_horizonte=72, escenario="demo", db=db, current_user=current_user)
                rows = list_demo_preds(empresa_id, tipo=tipo)
            except Exception as e:
                print(f"[AUTO-PRED DEMO ERROR] {e}")
        return rows
    _check_acceso(current_user, empresa_id)
    desde = datetime.now() - timedelta(hours=12)
    q = db.query(Prediccion).filter(
        Prediccion.empresa_id == empresa_id,
        Prediccion.fecha_prediccion >= desde,
        Prediccion.fecha_objetivo >= datetime.now(),
        Prediccion.escenario == escenario,
    )
    if tipo:
        q = q.filter(Prediccion.tipo == tipo)
    rows = q.order_by(Prediccion.fecha_objetivo).all()
    if not rows:
        try:
            await generar_predicciones(empresa_id, horas_horizonte=72, escenario=escenario, db=db, current_user=current_user)
            q = db.query(Prediccion).filter(
                Prediccion.empresa_id == empresa_id,
                Prediccion.fecha_prediccion >= desde,
                Prediccion.fecha_objetivo >= datetime.now(),
                Prediccion.escenario == escenario,
            )
            if tipo:
                q = q.filter(Prediccion.tipo == tipo)
            rows = q.order_by(Prediccion.fecha_objetivo).all()
        except Exception as e:
            print(f"[AUTO-PRED REAL ERROR] {e}")
    return rows
