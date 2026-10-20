from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserResponse, UserPreferenciasUpdate
from app.api.deps.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/users", tags=["Usuarios"])


@router.get("/", response_model=List[UserResponse])
def list_users(
    escenario_usuario: str | None = Query(None, pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Listar todos los usuarios (solo admin)."""
    q = db.query(User)
    if escenario_usuario:
        q = q.filter(User.escenario_usuario == escenario_usuario)
    return q.all()


@router.patch("/me/preferencias", response_model=UserResponse)
def update_preferencias(
    payload: UserPreferenciasUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar la vista preferida del usuario autenticado."""
    current_user.vista_preferida = payload.vista_preferida
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener usuario por ID."""
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Sin permisos")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Deshabilitar cuenta (solo admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Activar cuenta (solo admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user
