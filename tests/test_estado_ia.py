"""Estado del motor de recomendaciones (GET /ia/status): con IA, sin internet y sin clave."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import ia


@pytest.fixture
def cliente_ia():
    app = FastAPI()
    app.include_router(ia.router, prefix="/api/v1")
    ia._conexion_cache.update(ok=None, revisado=0.0)
    return TestClient(app)


def conexion(monkeypatch, hay_internet):
    llamadas = []

    async def falsa(refrescar=False):
        llamadas.append(refrescar)
        return hay_internet

    monkeypatch.setattr(ia, "_hay_conexion_gemini", falsa)
    return llamadas


def test_con_clave_e_internet_esta_en_linea(cliente_ia, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-real")
    conexion(monkeypatch, True)
    r = cliente_ia.get("/api/v1/ia/status").json()
    assert r["estado"] == "con_ia" and r["gemini_disponible"] is True


def test_con_clave_sin_internet_pasa_a_modo_basico(cliente_ia, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-real")
    llamadas = conexion(monkeypatch, False)
    r = cliente_ia.get("/api/v1/ia/status", params={"refrescar": True}).json()
    assert r["estado"] == "sin_conexion" and r["gemini_disponible"] is False
    assert llamadas == [True]  # "Revisar de nuevo" fuerza la revisión


@pytest.mark.parametrize("clave", ["", "tu_api_key_gemini"])
def test_sin_clave_no_revisa_internet(cliente_ia, monkeypatch, clave):
    monkeypatch.setenv("GEMINI_API_KEY", clave)
    llamadas = conexion(monkeypatch, True)
    assert cliente_ia.get("/api/v1/ia/status").json()["estado"] == "sin_clave"
    assert llamadas == []


def test_la_revision_de_conexion_se_guarda_un_minuto(monkeypatch):
    ia._conexion_cache.update(ok=None, revisado=0.0)
    intentos = []

    class ClienteSinRed:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            intentos.append(url)
            raise httpx.ConnectError("sin red")

    monkeypatch.setattr(ia.httpx, "AsyncClient", ClienteSinRed)
    assert asyncio.run(ia._hay_conexion_gemini()) is False
    assert asyncio.run(ia._hay_conexion_gemini()) is False
    assert len(intentos) == 1  # la segunda vez usa la caché
    asyncio.run(ia._hay_conexion_gemini(refrescar=True))
    assert len(intentos) == 2
