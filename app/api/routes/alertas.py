from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models.models import Alerta, ConfiguracionAlerta, Empresa, User, UserRole
from app.schemas.schemas import AlertaResponse, ConfigAlertaUpdate
from app.services.agents.agente_alertas import agente_alertas
from app.services.alertas_fonseca import CRITERIOS, TIPOS_GENERALES, obtener_alertas_generales
from app.services.alertas_translator import humanizar_lote
from app.services.demo_ops import (
    get_demo_alert_config,
    list_demo_alerts,
    mark_demo_alert_read,
    save_demo_alerts,
    set_demo_alert_config,
)

router = APIRouter(prefix="/alertas", tags=["Alertas"])


def _check_acceso(current_user: User, empresa_id: int):
    if current_user.role == UserRole.EMPRESA and current_user.empresa_id != empresa_id:
        raise HTTPException(status_code=403, detail="Sin permisos")


async def _alertas_demo(empresa_id: int, refrescar: bool = False) -> List[dict]:
    """Alertas generales para la empresa demo, guardadas en JSON (una tanda por día)."""
    hoy = datetime.now().date().isoformat()
    rows = [
        a for a in list_demo_alerts(empresa_id)
        if a.get("tipo") in TIPOS_GENERALES and str(a.get("created_at", "")).startswith(hoy)
    ]
    if rows and not refrescar:
        return rows
    leidas = {a["tipo"] for a in rows if a.get("leida")}
    ahora = datetime.now().replace(microsecond=0)
    base = int(ahora.timestamp() * 1000)
    nuevas = [
        {
            "id": base + i,
            "empresa_id": empresa_id,
            **alerta,
            "leida": alerta["tipo"] in leidas,
            "created_at": ahora.isoformat(),
        }
        for i, alerta in enumerate(await obtener_alertas_generales(refrescar))
    ]
    return save_demo_alerts(empresa_id, nuevas)


def _consulta_visibles(db: Session, empresa_id: int, solo_no_leidas: bool, limit: int):
    """Solo las alertas generales del municipio (no las de consumo, aparatos ni pagos guardadas antes)."""
    q = db.query(Alerta).filter(Alerta.empresa_id == empresa_id, Alerta.tipo.in_(TIPOS_GENERALES))
    if solo_no_leidas:
        q = q.filter(Alerta.leida == False)  # noqa: E712
    return q.order_by(desc(Alerta.created_at)).limit(limit).all()


@router.get("/criterios")
def criterios_alertas(current_user: User = Depends(get_current_user)):
    """Cuándo se dispara cada alerta general (mismos umbrales para todos)."""
    return {"ubicacion": get_settings().LOCATION_NAME, "criterios": CRITERIOS}


@router.get("/{empresa_id}", response_model=List[AlertaResponse])
async def list_alertas(
    empresa_id: int,
    solo_no_leidas: bool = False,
    limit: int = Query(50, ge=1, le=200),
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        rows = await _alertas_demo(empresa_id)
        if solo_no_leidas:
            rows = [a for a in rows if not a.get("leida")]
        return rows[:limit]

    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if empresa:
        # Las alertas generales se actualizan al consultarlas
        try:
            await agente_alertas.evaluar(db, empresa)
        except Exception as e:
            print(f"[AUTO-EVALUATION ERROR] {e}")
    return _consulta_visibles(db, empresa_id, solo_no_leidas, limit)


@router.get("/{empresa_id}/humanizadas")
async def list_alertas_humanizadas(
    empresa_id: int,
    solo_no_leidas: bool = False,
    limit: int = Query(50, ge=1, le=200),
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        rows = await _alertas_demo(empresa_id)
        if solo_no_leidas:
            rows = [a for a in rows if not a.get("leida")]
        return humanizar_lote(rows[:limit])

    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if empresa:
        try:
            await agente_alertas.evaluar(db, empresa)
        except Exception as e:
            print(f"[AUTO-EVALUATION ERROR] {e}")

    crudas = [
        {
            "id": a.id,
            "tipo": a.tipo,
            "severidad": a.severidad,
            "mensaje": a.mensaje,
            "leida": a.leida,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "empresa_id": a.empresa_id,
        }
        for a in _consulta_visibles(db, empresa_id, solo_no_leidas, limit)
    ]
    return humanizar_lote(crudas)


@router.post("/evaluar/{empresa_id}", response_model=List[AlertaResponse])
async def evaluar_alertas(
    empresa_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        return await _alertas_demo(empresa_id, refrescar=True)

    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    creadas = await agente_alertas.evaluar(db, empresa, refrescar=True)
    return [c for c in creadas if c is not None]


@router.patch("/{alerta_id}/marcar-leida", response_model=AlertaResponse)
def marcar_leida(
    alerta_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        row = mark_demo_alert_read(alerta_id)
        if not row:
            raise HTTPException(status_code=404, detail="Alerta demo no encontrada")
        return row
    alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    _check_acceso(current_user, alerta.empresa_id)
    alerta.leida = True
    db.commit()
    db.refresh(alerta)
    return alerta


@router.get("/config/{empresa_id}")
def get_configuracion(
    empresa_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        return {"id": 0, "empresa_id": empresa_id, **get_demo_alert_config()}
    _check_acceso(current_user, empresa_id)
    config = db.query(ConfiguracionAlerta).filter(ConfiguracionAlerta.empresa_id == empresa_id).first()
    if not config:
        config = ConfiguracionAlerta(empresa_id=empresa_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return {
        "id": config.id,
        "empresa_id": config.empresa_id,
        "umbral_consumo_diario_kwh": config.umbral_consumo_diario_kwh,
        "umbral_bateria_baja_pct": config.umbral_bateria_baja_pct,
        "umbral_radiacion_baja": config.umbral_radiacion_baja,
        "notificar_email": config.notificar_email,
        "notificar_dashboard": config.notificar_dashboard,
    }


@router.patch("/config/{empresa_id}")
def update_configuracion(
    empresa_id: int,
    data: ConfigAlertaUpdate,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        cfg = set_demo_alert_config(data.model_dump(exclude_unset=True))
        return {"empresa_id": empresa_id, **cfg}
    _check_acceso(current_user, empresa_id)
    config = db.query(ConfiguracionAlerta).filter(ConfiguracionAlerta.empresa_id == empresa_id).first()
    if not config:
        config = ConfiguracionAlerta(empresa_id=empresa_id)
        db.add(config)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return {
        "empresa_id": config.empresa_id,
        "umbral_consumo_diario_kwh": config.umbral_consumo_diario_kwh,
        "umbral_bateria_baja_pct": config.umbral_bateria_baja_pct,
        "umbral_radiacion_baja": config.umbral_radiacion_baja,
        "notificar_email": config.notificar_email,
        "notificar_dashboard": config.notificar_dashboard,
    }

