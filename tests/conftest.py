"""
Fixtures comunes de las pruebas.

- Base de datos SQLite en memoria, nueva en cada prueba, con el catálogo de aparatos cargado.
- Open-Meteo y Gemini simulados: las pruebas nunca salen a internet.
- Cliente HTTP de la API con los routers necesarios (sin MySQL ni el arranque de app.main).
"""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "streamlit_app"))
os.environ.pop("GEMINI_API_KEY", None)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import get_password_hash  # noqa: E402
from app.db.session import Base, get_db  # noqa: E402
from app.models import models as m  # noqa: E402
from app.services.catalogo_aparatos import sincronizar_catalogo  # noqa: E402

CLAVE = "clave-de-prueba"
FRANJA = {
    "fecha": "2026-10-20", "es_hoy": True, "inicio": 11, "fin": 14,
    "pico_w_m2": 950, "ghi_dia_kwh_m2": 6.1, "texto": "hoy de 11:00 a 14:00",
}


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def Sesion(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def db(Sesion):
    sesion = Sesion()
    sincronizar_catalogo(sesion)
    yield sesion
    sesion.close()


@pytest.fixture
def catalogo(db):
    """Aparatos del catálogo por código."""
    return {c.codigo: c for c in db.query(m.CatalogoAparato).all()}


@pytest.fixture
def agregar_aparatos(db, catalogo):
    """agregar_aparatos(empresa, ("nevera", 1), ("bombillo_led", 6), ...)"""
    def _agregar(empresa, *items):
        for codigo, cantidad in items:
            c = catalogo[codigo]
            db.add(m.AparatoUsuario(empresa_id=empresa.id, catalogo_id=c.id, catalogo=c, nombre=c.nombre, cantidad=cantidad))
        db.commit()
    return _agregar


@pytest.fixture
def crear_empresa(db):
    def _crear(nombre="Casa", tipo="hogar", tipo_entidad="hogar", **campos):
        e = m.Empresa(nombre=nombre, tipo=tipo, tipo_entidad=tipo_entidad, tarifa_kwh=943,
                      escenario_default="real", **campos)
        db.add(e)
        db.commit()
        return e
    return _crear


@pytest.fixture(autouse=True)
def sin_servicios_externos(monkeypatch):
    """Open-Meteo sin datos y Gemini sin clave, salvo que la prueba los reemplace."""
    from app.services import openmeteo

    async def vacio(*args, **kwargs):
        return []

    async def sin_aire(*args, **kwargs):
        return {"disponible": False}

    monkeypatch.setattr(openmeteo.openmeteo_service, "get_forecast_diario", vacio)
    monkeypatch.setattr(openmeteo.openmeteo_service, "get_forecast_horario", vacio)
    monkeypatch.setattr(openmeteo.openmeteo_service, "get_calidad_aire", sin_aire)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def franja_fija(monkeypatch):
    """Pronóstico con la franja de más sol de 11:00 a 14:00."""
    from app.api.routes import insights
    from app.services.agents import agente_recomendaciones

    async def franja():
        return FRANJA

    monkeypatch.setattr(insights, "obtener_franja_solar", franja)
    monkeypatch.setattr(agente_recomendaciones, "obtener_franja_solar", franja)
    return FRANJA


@pytest.fixture
def cliente(Sesion, db):
    """Cliente de la API con auth, empresas, aparatos, consumo e insights sobre la BD de prueba."""
    from app.api.routes import aparatos, auth, consumo, empresas, insights

    app = FastAPI()
    for r in (auth, aparatos, empresas, consumo, insights):
        app.include_router(r.router, prefix="/api/v1")

    def _db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


@pytest.fixture
def crear_usuario(db):
    def _crear(email, rol=m.UserRole.EMPRESA, empresa=None):
        db.add(m.User(email=email, hashed_password=get_password_hash(CLAVE), full_name=email.split("@")[0],
                      role=rol, empresa_id=empresa.id if empresa else None, escenario_usuario="real"))
        db.commit()
    return _crear


@pytest.fixture
def token(cliente):
    def _token(email):
        r = cliente.post("/api/v1/auth/login", json={"email": email, "password": CLAVE})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}
    return _token
