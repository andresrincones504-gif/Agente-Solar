from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.models import Empresa, User, UserRole, ConfiguracionAlerta
from app.schemas.schemas import EmpresaCreate, EmpresaUpdate, EmpresaResponse
from app.api.deps.auth import get_current_user, get_admin_user
from app.services.demo_data import get_demo_empresa

router = APIRouter(prefix="/empresas", tags=["Empresas"])


@router.post("/", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
def create_empresa(
    data: EmpresaCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Crear nueva empresa (solo admin)."""
    empresa = Empresa(**data.model_dump())
    db.add(empresa)
    db.commit()
    db.refresh(empresa)

    # Crear configuración de alertas por defecto
    config = ConfiguracionAlerta(empresa_id=empresa.id)
    db.add(config)
    db.commit()
    return empresa


@router.get("/", response_model=List[EmpresaResponse])
def list_empresas(
    escenario: str = Query("real", pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Listar empresas. Admin ve todas, empresa solo la suya."""
    if escenario == "demo":
        return [get_demo_empresa()]
    if current_user.role == UserRole.ADMIN or current_user.role == UserRole.ANALISTA:
        return db.query(Empresa).all()
    if current_user.empresa_id:
        return db.query(Empresa).filter(Empresa.id == current_user.empresa_id).all()
    return []


@router.get("/{empresa_id}", response_model=EmpresaResponse)
def get_empresa(
    empresa_id: int,
    escenario: str = Query("real", pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener empresa por ID."""
    if escenario == "demo":
        demo = get_demo_empresa()
        if empresa_id != demo["id"]:
            raise HTTPException(status_code=404, detail="Empresa demo no encontrada")
        return demo
    if (
        current_user.role == UserRole.EMPRESA
        and current_user.empresa_id != empresa_id
    ):
        raise HTTPException(status_code=403, detail="Sin permisos sobre esta empresa")
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


@router.patch("/{empresa_id}", response_model=EmpresaResponse)
def update_empresa(
    empresa_id: int,
    data: EmpresaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar empresa."""
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if (
        current_user.role == UserRole.EMPRESA
        and current_user.empresa_id != empresa_id
    ):
        raise HTTPException(status_code=403, detail="Sin permisos")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(empresa, key, value)
    db.commit()
    db.refresh(empresa)
    return empresa
