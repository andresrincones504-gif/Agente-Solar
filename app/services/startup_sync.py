"""
Servicio de sincronización inicial y precalentamiento para las Fuentes de Verdad.
Garantiza que la base de datos MySQL cuente con series reales de radiación y clima
de Open-Meteo, NASA Power, PVGIS y OpenWeather para la ubicación configurada al iniciar la app,
evitando que se requieran acciones manuales de los usuarios.
"""
import logging
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.config import get_settings
from app.models.models import RadiacionSolar
from app.services.openmeteo import openmeteo_service
from app.services.nasa_power import nasa_service
from app.services.pvgis import pvgis_service
from app.services.openweather import openweather_service

logger = logging.getLogger("app.services.startup_sync")
logging.basicConfig(level=logging.INFO)


def _upsert_radiacion_local(db: Session, items: list) -> int:
    """Inserta o actualiza registros reales de radiación en la base de datos."""
    count = 0
    valid_cols = {c.name for c in RadiacionSolar.__table__.columns}
    for item in items:
        fuente = str(item.get("fuente") or "").lower()
        origen = str(item.get("origen_dato") or "").lower()
        escenario = str(item.get("escenario") or "").lower()
        
        # En base de datos física solo guardamos datos reales, no simulaciones locales
        if fuente == "synthetic" or origen == "synthetic_fallback" or escenario == "demo":
            continue

        clean = {k: v for k, v in item.items() if k in valid_cols}
        existing = (
            db.query(RadiacionSolar)
            .filter(
                RadiacionSolar.fecha == clean["fecha"],
                RadiacionSolar.fuente == clean.get("fuente"),
            )
            .first()
        )
        if existing:
            for k, v in clean.items():
                setattr(existing, k, v)
        else:
            rec = RadiacionSolar(**clean)
            db.add(rec)
            count += 1
            
    db.commit()
    return count


async def ejecutar_sincronizacion_inicial(db: Session) -> None:
    """
    Ejecuta el precalentamiento y la sincronización de las APIs climáticas.
    Diseñado para correr en segundo plano (asíncrono) al iniciar la aplicación.
    """
    logger.info("🌤️ [STARTUP SYNC] Iniciando inicialización y precalentamiento de Fuentes de Verdad...")
    
    try:
        # 1. Sincronizar Open-Meteo (Últimos 30 días de radiación real)
        logger.info(f"🌤️ [STARTUP SYNC] Conectando con Open-Meteo Archive (ERA5) para {get_settings().LOCATION_CITY}...")
        try:
            om_data = await openmeteo_service.get_ultimos_dias(days=30)
            om_added = _upsert_radiacion_local(db, om_data)
            logger.info(f"🟢 [STARTUP SYNC] Open-Meteo sincronizado con éxito. Nuevos registros guardados: {om_added}")
        except Exception as e:
            logger.warning(f"⚠️ [STARTUP SYNC] No se pudo sincronizar Open-Meteo al iniciar: {e}. Fallback listo.")

        # 2. Sincronizar NASA POWER (Últimos 30 días de respaldo y validación)
        logger.info(f"🌤️ [STARTUP SYNC] Conectando con NASA POWER API para {get_settings().LOCATION_CITY}...")
        try:
            nasa_data = await nasa_service.get_last_days(days=30)
            nasa_added = _upsert_radiacion_local(db, nasa_data)
            logger.info(f"🟢 [STARTUP SYNC] NASA POWER sincronizado con éxito. Nuevos registros guardados: {nasa_added}")
        except Exception as e:
            logger.warning(f"⚠️ [STARTUP SYNC] No se pudo sincronizar NASA POWER al iniciar: {e}. Fallback listo.")

        # 3. Precalentar TMY (Año Meteorológico Típico) desde PVGIS
        logger.info("🌤️ [STARTUP SYNC] Precalentando año meteorológico de referencia desde PVGIS...")
        try:
            tmy_data = await pvgis_service.get_tmy()
            if tmy_data.get("disponible"):
                logger.info(
                    f"🟢 [STARTUP SYNC] PVGIS TMY precalentado correctamente. "
                    f"Radiación diaria típica: {tmy_data.get('ghi_promedio_diario_kwh_m2')} kWh/m²/día"
                )
            else:
                logger.info(f"🟡 [STARTUP SYNC] PVGIS está inactivo o reporta: {tmy_data.get('motivo')}")
        except Exception as e:
            logger.warning(f"⚠️ [STARTUP SYNC] No se pudo obtener TMY de PVGIS en inicio: {e}")

        # 4. Precalentar clima actual desde OpenWeather
        logger.info("🌤️ [STARTUP SYNC] Solicitando clima actual y calidad de aire en OpenWeather...")
        try:
            weather_data = await openweather_service.get_current_weather(allow_synthetic=False)
            if weather_data:
                logger.info(
                    f"🟢 [STARTUP SYNC] OpenWeather inicializado. Clima actual en {get_settings().LOCATION_CITY}: "
                    f"{weather_data.get('temperatura')}°C, {weather_data.get('descripcion')}"
                )
        except Exception as e:
            logger.warning(f"⚠️ [STARTUP SYNC] OpenWeather inactivo o sin API Key en .env: {e}")

        logger.info("🚀 [STARTUP SYNC] ¡Proceso de inicialización de Fuentes de Verdad completado con éxito!")

    except Exception as e:
        logger.error(f"❌ [STARTUP SYNC] Error crítico inesperado durante la sincronización inicial: {e}")
    finally:
        db.close()
