"""
Ka’i — API FastAPI
Dashboard Solar con IA para Ahorro Energético en La Guajira (ubicación configurable con LOCATION_*).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.db.session import engine, Base
from app.db.migrations import ensure_schema_compatibility
from app.models import models  # noqa: F401  importar para registrar modelos

from app.api.routes import (
    auth,
    users,
    empresas,
    solar,
    consumo,
    ia,
    predicciones,
    alertas,
    reportes,
    insights,
    aparatos,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(engine)

    # Catálogo de aparatos (app/data/catalogo_aparatos.json -> tabla catalogo_aparatos)
    from app.db.session import SessionLocal as _SessionLocal
    from app.services.catalogo_aparatos import sincronizar_catalogo
    with _SessionLocal() as db_catalogo:
        try:
            resumen = sincronizar_catalogo(db_catalogo)
            print(f"[STARTUP] Catálogo de aparatos sincronizado: {resumen}")
        except Exception as e:
            print(f"[STARTUP ERROR] No se pudo sincronizar el catálogo de aparatos: {e}")
    
    # Sincronización automática de Fuentes de Verdad en segundo plano (no bloqueante)
    import asyncio
    from app.db.session import SessionLocal
    from app.services.startup_sync import ejecutar_sincronizacion_inicial
    
    db = SessionLocal()
    try:
        asyncio.create_task(ejecutar_sincronizacion_inicial(db))
    except Exception as e:
        print(f"[STARTUP ERROR] No se pudo lanzar la sincronización inicial: {e}")
        
    yield
    # Shutdown


app = FastAPI(
    title="Ka’i API",
    description=(
        f"API REST para el Dashboard Solar con IA para Ahorro Energético en {settings.LOCATION_NAME}. "
        "Diseñada para ser consumida desde el frontend Streamlit y aplicaciones móviles."
    ),
    version="1.1.0",
    lifespan=lifespan,
    contact={
        "name": "Equipo Hackatón La Guajira",
        "url": "https://github.com",
    },
    license_info={"name": "MIT"},
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios concretos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(empresas.router, prefix=API_PREFIX)
app.include_router(solar.router, prefix=API_PREFIX)
app.include_router(consumo.router, prefix=API_PREFIX)
app.include_router(ia.router, prefix=API_PREFIX)
app.include_router(predicciones.router, prefix=API_PREFIX)
app.include_router(alertas.router, prefix=API_PREFIX)
app.include_router(reportes.router, prefix=API_PREFIX)
app.include_router(insights.router, prefix=API_PREFIX)
app.include_router(aparatos.router, prefix=API_PREFIX)


@app.get("/", tags=["Root"])
def root():
    return {
        "app": "Ka’i API",
        "version": "1.1.0",
        "ubicacion": f"{settings.LOCATION_NAME}, Colombia",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Root"])
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
