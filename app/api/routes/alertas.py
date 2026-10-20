from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models.models import Alerta, ConfiguracionAlerta, ConsumoEnergetico, Empresa, User, UserRole
from app.schemas.schemas import AlertaResponse, ConfigAlertaUpdate
from app.services.agents.agente_alertas import agente_alertas
from app.services.alertas_translator import humanizar_lote
from app.services.demo_data import get_consumo_demo, get_radiacion_demo
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


def _evaluar_demo_internamente(empresa_id: int) -> List[dict]:
    cfg = get_demo_alert_config()
    consumos = get_consumo_demo(days=2)
    radiacion = get_radiacion_demo(days=2)
    now = datetime.now().replace(microsecond=0).isoformat()
    rows = []
    hoy = datetime.now().date()
    c_hoy = [c for c in consumos if datetime.fromisoformat(c["fecha"]).date() == hoy]
    total_hoy = sum((c.get("consumo_kwh") or 0) for c in c_hoy)
    
    if total_hoy > float(cfg.get("umbral_consumo_diario_kwh", 400.0)):
        rows.append({
            "id": int(datetime.now().timestamp()) + 1,
            "empresa_id": empresa_id,
            "tipo": "consumo_alto",
            "mensaje": f"Consumo diario demo {total_hoy:.1f} kWh supera el umbral de {float(cfg.get('umbral_consumo_diario_kwh', 400.0)):.1f} kWh.",
            "severidad": "media",
            "leida": False,
            "created_at": now
        })
        
    bateria = c_hoy[0].get("nivel_bateria_pct") if c_hoy else None
    if bateria is not None and bateria < float(cfg.get("umbral_bateria_baja_pct", 20.0)):
        rows.append({
            "id": int(datetime.now().timestamp()) + 2,
            "empresa_id": empresa_id,
            "tipo": "bateria_baja",
            "mensaje": f"El almacenamiento de batería demo se encuentra críticamente en {bateria:.1f}% (umbral: {float(cfg.get('umbral_bateria_baja_pct', 20.0)):.0f}%).",
            "severidad": "alta",
            "leida": False,
            "created_at": now
        })
        
    ghi = radiacion[0].get("ghi") if radiacion else None
    if ghi is not None and ghi < float(cfg.get("umbral_radiacion_baja", 2.5)):
        rows.append({
            "id": int(datetime.now().timestamp()) + 3,
            "empresa_id": empresa_id,
            "tipo": "baja_radiacion",
            "mensaje": f"Radiación solar demo baja ({ghi:.2f} kWh/m²/día, umbral: {float(cfg.get('umbral_radiacion_baja', 2.5)):.1f}).",
            "severidad": "media",
            "leida": False,
            "created_at": now
        })
        
    # Alerta climática premium para el escenario demo
    rows.append({
        "id": int(datetime.now().timestamp()) + 4,
        "empresa_id": empresa_id,
        "tipo": "riesgo_apagon",
        "mensaje": f"Alerta climática de Red (Demo): Pronóstico de tormenta y vientos de 42 km/h en {get_settings().LOCATION_CITY}. Se sugiere activar Carga Máxima Preventiva en tus baterías.",
        "severidad": "critica",
        "leida": False,
        "created_at": now
    })
    
    return save_demo_alerts(empresa_id, rows)


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
        rows = list_demo_alerts(empresa_id)
        if not rows:
            rows = _evaluar_demo_internamente(empresa_id)
        if solo_no_leidas:
            rows = [a for a in rows if not a.get("leida")]
        return rows[:limit]
    
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if empresa:
        # Evaluación proactiva automática al listar las alertas
        try:
            await agente_alertas.evaluar(db, empresa)
        except Exception as e:
            print(f"[AUTO-EVALUATION ERROR] {e}")

    q = db.query(Alerta).filter(Alerta.empresa_id == empresa_id)
    if solo_no_leidas:
        q = q.filter(Alerta.leida == False)  # noqa: E712
    return q.order_by(desc(Alerta.created_at)).limit(limit).all()


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
        rows = list_demo_alerts(empresa_id)
        if not rows:
            rows = _evaluar_demo_internamente(empresa_id)
        if solo_no_leidas:
            rows = [a for a in rows if not a.get("leida")]
        return humanizar_lote(rows[:limit], tiene_baterias=True, tiene_paneles=True)
    
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    tiene_baterias = True
    tiene_paneles = True
    if empresa:
        # Identificar equipamiento dinámicamente para el humanizador de alertas
        tiene_telemetria_bateria = db.query(ConsumoEnergetico).filter(
            ConsumoEnergetico.empresa_id == empresa_id,
            ConsumoEnergetico.nivel_bateria_pct.isnot(None),
            ConsumoEnergetico.escenario == escenario
        ).first() is not None

        tiene_telemetria_solar = db.query(ConsumoEnergetico).filter(
            ConsumoEnergetico.empresa_id == empresa_id,
            ConsumoEnergetico.produccion_solar_kwh > 0.0,
            ConsumoEnergetico.escenario == escenario
        ).first() is not None

        tiene_baterias = ((empresa.capacidad_bateria_kwh or 0.0) > 0.0) or tiene_telemetria_bateria
        tiene_paneles = ((empresa.capacidad_paneles_kw or 0.0) > 0.0) or tiene_telemetria_solar
        
        # Evaluación proactiva automática al listar las alertas humanizadas
        try:
            await agente_alertas.evaluar(db, empresa)
        except Exception as e:
            print(f"[AUTO-EVALUATION ERROR] {e}")

    q = db.query(Alerta).filter(Alerta.empresa_id == empresa_id)
    if solo_no_leidas:
        q = q.filter(Alerta.leida == False)  # noqa: E712
    rows = q.order_by(desc(Alerta.created_at)).limit(limit).all()
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
        for a in rows
    ]
    return humanizar_lote(crudas, tiene_baterias=tiene_baterias, tiene_paneles=tiene_paneles)


@router.post("/evaluar/{empresa_id}", response_model=List[AlertaResponse])
async def evaluar_alertas(
    empresa_id: int,
    escenario: Optional[str] = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escenario = escenario or current_user.escenario_usuario
    if escenario == "demo":
        return _evaluar_demo_internamente(empresa_id)

    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    creadas = await agente_alertas.evaluar(db, empresa)
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

