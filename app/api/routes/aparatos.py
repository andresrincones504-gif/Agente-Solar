"""Catálogo de aparatos e inventario de aparatos por hogar o empresa."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models.models import AparatoUsuario, CatalogoAparato, Empresa, TipoEntidad, User, UserRole
from app.schemas.schemas import (
    AparatoUsuarioCreate,
    AparatoUsuarioResponse,
    AparatoUsuarioUpdate,
    CatalogoAparatoResponse,
    EstadisticasAparatosResponse,
)
from app.services.aparatos import calcular_estadisticas, crear_aparatos, filtrar_catalogo
from app.services.contexto_energetico import avisos_aparatos, dimensionar_sistema, resumen_inventario

router = APIRouter(tags=["Aparatos"])


def _empresa_con_acceso(db: Session, current_user: User, empresa_id: int) -> Empresa:
    if current_user.role == UserRole.EMPRESA and current_user.empresa_id != empresa_id:
        raise HTTPException(status_code=403, detail="Sin permisos sobre esta empresa")
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


def _aparato_de_empresa(db: Session, empresa_id: int, aparato_id: int) -> AparatoUsuario:
    aparato = (
        db.query(AparatoUsuario)
        .filter(AparatoUsuario.id == aparato_id, AparatoUsuario.empresa_id == empresa_id)
        .first()
    )
    if not aparato:
        raise HTTPException(status_code=404, detail="Aparato no encontrado en esta empresa")
    return aparato


@router.get("/catalogo/aparatos", response_model=List[CatalogoAparatoResponse])
def listar_catalogo(
    categoria: Optional[TipoEntidad] = Query(None, description="Solo aparatos que aplican a este tipo de entidad"),
    q: Optional[str] = Query(None, max_length=100, description="Palabras a buscar en nombre, descripción y sinónimos"),
    tipo_aparato: Optional[str] = Query(None, max_length=40),
    db: Session = Depends(get_db),
):
    """Catálogo público (lo usa el formulario de registro antes de iniciar sesión)."""
    todos = db.query(CatalogoAparato).filter(CatalogoAparato.activo == True).all()  # noqa: E712
    return filtrar_catalogo(todos, categoria=categoria.value if categoria else None, q=q, tipo_aparato=tipo_aparato)


@router.get("/empresas/{empresa_id}/aparatos", response_model=List[AparatoUsuarioResponse])
def listar_aparatos(
    empresa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _empresa_con_acceso(db, current_user, empresa_id)
    aparatos = db.query(AparatoUsuario).filter(AparatoUsuario.empresa_id == empresa_id).all()
    return sorted(aparatos, key=lambda a: a.consumo_kwh_mes, reverse=True)


@router.post("/empresas/{empresa_id}/aparatos", response_model=List[AparatoUsuarioResponse], status_code=status.HTTP_201_CREATED)
def agregar_aparatos(
    empresa_id: int,
    items: List[AparatoUsuarioCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agrega uno o varios aparatos al inventario."""
    _empresa_con_acceso(db, current_user, empresa_id)
    if not items:
        raise HTTPException(status_code=400, detail="Envía al menos un aparato")
    try:
        creados = crear_aparatos(db, empresa_id, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    for a in creados:
        db.refresh(a)
    return creados


@router.patch("/empresas/{empresa_id}/aparatos/{aparato_id}", response_model=AparatoUsuarioResponse)
def editar_aparato(
    empresa_id: int,
    aparato_id: int,
    data: AparatoUsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _empresa_con_acceso(db, current_user, empresa_id)
    aparato = _aparato_de_empresa(db, empresa_id, aparato_id)
    cambios = data.model_dump(exclude_unset=True)
    if aparato.catalogo_id is None and any(cambios.get(k, 1) is None for k in ("potencia_w", "horas_uso_dia")):
        raise HTTPException(status_code=400, detail="Un aparato propio necesita potencia y horas de uso")
    if "nombre" in cambios and not cambios["nombre"]:
        raise HTTPException(status_code=400, detail="El nombre no puede quedar vacío")
    if "cantidad" in cambios and cambios["cantidad"] is None:
        raise HTTPException(status_code=400, detail="La cantidad no puede quedar vacía")
    for campo, valor in cambios.items():
        setattr(aparato, campo, valor)
    db.commit()
    db.refresh(aparato)
    return aparato


@router.delete("/empresas/{empresa_id}/aparatos/{aparato_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_aparato(
    empresa_id: int,
    aparato_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _empresa_con_acceso(db, current_user, empresa_id)
    aparato = _aparato_de_empresa(db, empresa_id, aparato_id)
    db.delete(aparato)
    db.commit()


@router.get("/empresas/{empresa_id}/aparatos/estadisticas", response_model=EstadisticasAparatosResponse)
def estadisticas_aparatos(
    empresa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Consumo y costo mensual estimado por aparato, ajustado al consumo real cuando existe."""
    empresa = _empresa_con_acceso(db, current_user, empresa_id)
    return calcular_estadisticas(db, empresa)


@router.get("/empresas/{empresa_id}/aparatos/dimensionamiento")
def dimensionamiento_solar(
    empresa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paneles (kWp) y batería (kWh) sugeridos según el consumo real o el inventario de aparatos."""
    empresa = _empresa_con_acceso(db, current_user, empresa_id)
    return dimensionar_sistema(db, empresa)


@router.get("/empresas/{empresa_id}/aparatos/avisos")
def avisos_de_aparatos(
    empresa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Avisos sobre el inventario: la factura no cuadra con los aparatos o uno concentra el consumo."""
    empresa = _empresa_con_acceso(db, current_user, empresa_id)
    return avisos_aparatos(resumen_inventario(db, empresa))
