from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "solar_user"
    MYSQL_PASSWORD: str = "solar_pass_2026"
    MYSQL_DATABASE: str = "agente_solar_db"

    # JWT
    SECRET_KEY: str = "tu-clave-secreta-super-segura-cambiar-en-produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # APIs Externas
    # --- NÚCLEO PRINCIPAL: Open-Meteo (gratis, sin API key, GHI/DNI/DHI nativo) ---
    OPENMETEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPENMETEO_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    OPENMETEO_AIR_QUALITY_URL: str = "https://air-quality-api.open-meteo.com/v1/air-quality"

    # --- COMPLEMENTO: OpenWeather (alertas, validación cruzada) ---
    OPENWEATHER_API_KEY: str = ""
    OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"

    # --- OPCIONAL: PVGIS v6 (TMY baseline para infraestructura solar) ---
    PVGIS_BASE_URL: str = "https://re.jrc.ec.europa.eu/api/v5_3"
    PVGIS_VERSION: str = "v5_3"  # PVGIS API; v6 endpoint no público aún, v5_3 es el estable
    PVGIS_ENABLED: bool = True

    # --- LEGACY: NASA POWER (se mantiene como respaldo histórico) ---
    NASA_POWER_BASE_URL: str = "https://power.larc.nasa.gov/api/temporal/daily/point"

    # Ubicación de la instalación: coordenadas para los servicios de clima y nombre para los mensajes
    LOCATION_NAME: str = "Fonseca, La Guajira"
    LOCATION_LAT: float = 10.8858
    LOCATION_LON: float = -72.8481
    # Obsoletas: se conservan para no romper archivos .env antiguos, pero ya no se usan
    RIOHACHA_LAT: float = 10.8858
    RIOHACHA_LON: float = -72.8481

    # Gemini LLM
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_BASE_URL: str = "http://localhost:8000"

    @property
    def LOCATION_CITY(self) -> str:
        """Solo el municipio: 'Fonseca, La Guajira' -> 'Fonseca'."""
        return self.LOCATION_NAME.split(",")[0].strip() or self.LOCATION_NAME

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
