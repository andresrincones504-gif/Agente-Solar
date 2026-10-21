from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from typing import Optional

from app.api.deps.auth import get_current_user, get_optional_user
from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.models import User, Empresa, ConfiguracionAlerta, TipoEntidad, UserRole
from app.schemas.schemas import MessageResponse, Token, UserCreate, UserLogin, UserResponse
from app.services.aparatos import crear_aparatos


router = APIRouter(prefix="/auth", tags=["Autenticacion"])
settings = get_settings()


def _tipo_entidad(user_data: UserCreate) -> str:
    """Tipo de entidad indicado, o deducido del giro para clientes que aún no lo envían."""
    if user_data.tipo_entidad is not None:
        return TipoEntidad(user_data.tipo_entidad).value
    giro = (user_data.tipo_empresa or "hogar").lower()
    if giro in ("hogar", "comunidad"):
        return giro
    return TipoEntidad.EMPRESA.value


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Registrar nuevo usuario. Solo un administrador autenticado puede hacerlo.

    Crea el usuario (empresa, analista o admin). Si no se indica una empresa existente,
    crea también su hogar o empresa, con el tipo de entidad y los aparatos elegidos.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inicia sesión como administrador para registrar usuarios",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede registrar usuarios",
        )

    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo ya esta registrado",
        )

    if user_data.escenario_usuario not in ("demo", "real"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="escenario_usuario debe ser 'demo' o 'real'",
        )

    empresa_id = user_data.empresa_id
    if empresa_id and user_data.aparatos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los aparatos se registran al crear un hogar o empresa nuevo; para uno existente usa /empresas/{id}/aparatos",
        )

    try:
        if not empresa_id:
            # Crear automáticamente el hogar / negocio / empresa del usuario
            tipo_entidad = _tipo_entidad(user_data)
            nombre_emp = user_data.nombre_empresa or f"Hogar de {user_data.full_name}"
            tipo_emp = user_data.tipo_empresa or tipo_entidad
            tarifa = user_data.tarifa_kwh if user_data.tarifa_kwh is not None else 943.0

            nueva_empresa = Empresa(
                nombre=nombre_emp,
                tipo=tipo_emp,
                tipo_entidad=tipo_entidad,
                tarifa_kwh=tarifa,
                escenario_default=user_data.escenario_usuario,
            )
            db.add(nueva_empresa)
            db.flush()  # obtiene el id sin cerrar la transacción
            empresa_id = nueva_empresa.id

            db.add(ConfiguracionAlerta(empresa_id=empresa_id))
            if user_data.aparatos:
                crear_aparatos(db, empresa_id, user_data.aparatos)

        user = User(
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            escenario_usuario=user_data.escenario_usuario,
            empresa_id=empresa_id,
        )
        db.add(user)
        db.commit()  # usuario, empresa, configuración y aparatos se guardan juntos o no se guarda nada
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login con email y password. Retorna JWT."""
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva",
        )

    access_token = create_access_token(
        data={
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value,
            "empresa_id": user.empresa_id,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Obtener informacion del usuario autenticado."""
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Cerrar sesion del usuario autenticado.

    La autenticacion actual usa JWT stateless, asi que esta ruta valida el token
    recibido y permite al cliente cerrar sesion de forma explicita limpiando su
    estado local.
    """
    return MessageResponse(message=f"Sesion cerrada correctamente para {current_user.email}")
