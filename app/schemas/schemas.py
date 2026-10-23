from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.config import get_settings
from typing import Optional, List
from datetime import datetime
from app.models.models import UserRole, VistaPreferida, TipoEntidad


# --- Aparatos Schemas ---
class AparatoUsuarioCreate(BaseModel):
    """Un aparato del inventario. Del catálogo (catalogo_id) o propio (nombre + potencia + horas)."""
    catalogo_id: Optional[int] = None
    nombre: Optional[str] = Field(None, min_length=2, max_length=120)
    cantidad: int = Field(1, ge=1, le=500)
    potencia_w: Optional[float] = Field(None, gt=0, le=200000)
    horas_uso_dia: Optional[float] = Field(None, ge=0, le=24)

    @model_validator(mode="after")
    def _catalogo_o_propio(self):
        if self.catalogo_id is None:
            if not self.nombre:
                raise ValueError("Indica un aparato del catálogo (catalogo_id) o el nombre de tu aparato")
            if self.potencia_w is None or self.horas_uso_dia is None:
                raise ValueError("Para un aparato que no está en el catálogo indica su potencia (W) y horas de uso al día")
        return self


class AparatoUsuarioUpdate(BaseModel):
    """Campos a cambiar. potencia_w u horas_uso_dia en null vuelven al valor del catálogo."""
    nombre: Optional[str] = Field(None, min_length=2, max_length=120)
    cantidad: Optional[int] = Field(None, ge=1, le=500)
    potencia_w: Optional[float] = Field(None, gt=0, le=200000)
    horas_uso_dia: Optional[float] = Field(None, ge=0, le=24)


class AparatoUsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    catalogo_id: Optional[int] = None
    nombre: str
    cantidad: int
    tipo_aparato: str
    potencia_w: Optional[float] = None  # lo que indicó el usuario
    horas_uso_dia: Optional[float] = None  # lo que indicó el usuario
    potencia_efectiva_w: float  # la que se usa en los cálculos
    horas_efectivas_dia: float
    consumo_kwh_mes: float
    origen_dato: str  # usuario | catalogo
    created_at: datetime


class CatalogoAparatoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    tipo_aparato: str
    categorias_entidad: List[str]
    potencia_w: float
    horas_uso_dia: float
    consumo_kwh_mes: float
    palabras_clave: Optional[str] = None
    fuente: Optional[str] = None


class EstadisticaAparato(BaseModel):
    aparato_id: Optional[int] = None  # None = consumo no identificado
    nombre: str
    tipo_aparato: str
    cantidad: int
    origen_dato: str
    consumo_estimado_kwh_mes: float  # según potencia x horas
    consumo_kwh_mes: float  # ajustado a la factura cuando hay datos reales
    costo_cop_mes: float
    porcentaje: float


class EstadisticaTipoAparato(BaseModel):
    tipo_aparato: str
    consumo_kwh_mes: float
    costo_cop_mes: float
    porcentaje: float


class EstadisticasAparatosResponse(BaseModel):
    empresa_id: int
    tarifa_kwh: float
    base_calculo: str  # factura | catalogo
    dias_con_datos: int
    consumo_inventario_kwh_mes: float
    consumo_real_kwh_mes: Optional[float] = None
    consumo_total_kwh_mes: float
    costo_total_cop_mes: float
    factor_ajuste: Optional[float] = None
    aparatos: List[EstadisticaAparato]
    por_tipo: List[EstadisticaTipoAparato]


# --- Auth Schemas ---
class InstalacionSolarCreate(BaseModel):
    """Sistema solar que ya tiene el usuario: paneles, batería, inversor y perfil de consumo."""
    potencia_panel_w: float = Field(..., gt=0, le=2000)
    cantidad_paneles: int = Field(..., ge=1, le=10000)
    orientacion: str = Field("sur", pattern="^(sur|sureste|suroeste|este_oeste|personalizada)$")
    azimut_grados: Optional[float] = Field(None, ge=0, lt=360)
    inclinacion_grados: Optional[float] = Field(None, ge=0, le=90)
    tipo_panel: Optional[str] = Field(None, max_length=60)
    tiene_bateria: bool = False
    quimica_bateria: Optional[str] = Field(None, max_length=60)
    voltaje_banco_v: Optional[float] = Field(None, gt=0, le=1500)
    capacidad_ah: Optional[float] = Field(None, gt=0, le=100000)
    soc_pct: Optional[float] = Field(None, ge=0, le=100)
    dod_pct: Optional[float] = Field(None, gt=0, le=100)
    eficiencia_ciclo_pct: Optional[float] = Field(None, gt=0, le=100)
    potencia_descarga_w: Optional[float] = Field(None, gt=0, le=1000000)
    potencia_inversor_w: Optional[float] = Field(None, gt=0, le=1000000)
    eficiencia_inversor_pct: Optional[float] = Field(None, gt=0, le=100)
    rendimiento_pr_pct: Optional[float] = Field(None, gt=0, le=100)
    potencia_pv_max_w: Optional[float] = Field(None, gt=0, le=1000000)
    consumo_diario_kwh: Optional[float] = Field(None, ge=0, le=100000)
    demanda_diurna_kwh: Optional[float] = Field(None, ge=0, le=100000)
    demanda_nocturna_kwh: Optional[float] = Field(None, ge=0, le=100000)
    carga_base_w: Optional[float] = Field(None, ge=0, le=1000000)

    @model_validator(mode="after")
    def _bateria_completa(self):
        if self.tiene_bateria and (not self.voltaje_banco_v or not self.capacidad_ah):
            raise ValueError("Para la batería indica el voltaje del banco y su capacidad en Ah")
        return self


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.EMPRESA
    empresa_id: Optional[int] = None
    escenario_usuario: str = "real"
    nombre_empresa: Optional[str] = None
    tipo_empresa: Optional[str] = None
    tarifa_kwh: Optional[float] = None
    tipo_entidad: Optional[TipoEntidad] = None
    capacidad_paneles_kw: Optional[float] = Field(None, ge=0, le=5000)  # 'Tengo paneles solares' en el registro
    capacidad_bateria_kwh: Optional[float] = Field(None, ge=0, le=5000)
    instalacion: Optional[InstalacionSolarCreate] = None  # pantalla 'Tengo paneles solares'
    aparatos: List[AparatoUsuarioCreate] = Field(default_factory=list, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    escenario_usuario: str = "real"
    vista_preferida: VistaPreferida = VistaPreferida.SIMPLE
    is_active: bool
    empresa_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserPreferenciasUpdate(BaseModel):
    vista_preferida: VistaPreferida


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


# --- Empresa Schemas ---
class EmpresaCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    nombre: str
    tipo: Optional[str] = None
    tipo_entidad: Optional[TipoEntidad] = None
    direccion: Optional[str] = None
    ciudad: str = Field(default_factory=lambda: get_settings().LOCATION_CITY)
    departamento: str = "La Guajira"
    tarifa_kwh: float = 943.0
    capacidad_paneles_kw: float = 0.0
    capacidad_bateria_kwh: float = 0.0


class EmpresaUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    nombre: Optional[str] = None
    tipo: Optional[str] = None
    tipo_entidad: Optional[TipoEntidad] = None
    direccion: Optional[str] = None
    tarifa_kwh: Optional[float] = None
    capacidad_paneles_kw: Optional[float] = None
    capacidad_bateria_kwh: Optional[float] = None


class EmpresaResponse(BaseModel):
    id: int
    nombre: str
    tipo: Optional[str]
    tipo_entidad: Optional[str] = None
    direccion: Optional[str]
    ciudad: str
    departamento: str
    tarifa_kwh: float
    capacidad_paneles_kw: float
    capacidad_bateria_kwh: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Consumo Schemas ---
class ConsumoCreate(BaseModel):
    empresa_id: int
    fecha: datetime
    consumo_kwh: float
    costo_cop: Optional[float] = None
    demanda_pico_kw: Optional[float] = None
    produccion_solar_kwh: float = 0.0
    nivel_bateria_pct: Optional[float] = None
    periodo: str = "diario"


class ConsumoMensualCreate(BaseModel):
    empresa_id: int
    anio: int
    mes: int
    consumo_total_kwh: float
    costo_energia_cop: float
    costo_total_cop: Optional[float] = None
    fecha_emision: Optional[datetime] = None
    fecha_pago_oportuno: Optional[datetime] = None
    fecha_suspension: Optional[datetime] = None


class ConsumoUpdate(BaseModel):
    empresa_id: Optional[int] = None
    fecha: Optional[datetime] = None
    consumo_kwh: Optional[float] = None
    costo_cop: Optional[float] = None
    demanda_pico_kw: Optional[float] = None
    produccion_solar_kwh: Optional[float] = None
    nivel_bateria_pct: Optional[float] = None
    periodo: Optional[str] = None


class ConsumoResponse(BaseModel):
    id: int
    empresa_id: int
    fecha: datetime
    consumo_kwh: float
    costo_cop: Optional[float]
    demanda_pico_kw: Optional[float]
    produccion_solar_kwh: float
    nivel_bateria_pct: Optional[float]
    periodo: str
    escenario: str = "demo"
    origen_dato: Optional[str] = None
    confiabilidad: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Radiación Solar Schemas ---
class RadiacionCreate(BaseModel):
    fecha: datetime
    ghi: Optional[float] = None
    dni: Optional[float] = None
    dhi: Optional[float] = None
    temperatura: Optional[float] = None
    temperatura_max: Optional[float] = None
    temperatura_min: Optional[float] = None
    nubosidad: Optional[float] = None
    precipitacion_mm: Optional[float] = None
    viento_kmh_max: Optional[float] = None
    fuente: Optional[str] = "synthetic"
    origen_dato: Optional[str] = None
    confiabilidad: Optional[float] = 35.0


class RadiacionUpdate(BaseModel):
    fecha: Optional[datetime] = None
    ghi: Optional[float] = None
    dni: Optional[float] = None
    dhi: Optional[float] = None
    temperatura: Optional[float] = None
    temperatura_max: Optional[float] = None
    temperatura_min: Optional[float] = None
    nubosidad: Optional[float] = None
    precipitacion_mm: Optional[float] = None
    viento_kmh_max: Optional[float] = None
    fuente: Optional[str] = None
    origen_dato: Optional[str] = None
    confiabilidad: Optional[float] = None


class RadiacionResponse(BaseModel):
    id: int
    fecha: datetime
    ghi: Optional[float]
    dni: Optional[float]
    dhi: Optional[float]
    temperatura: Optional[float]
    temperatura_max: Optional[float] = None
    temperatura_min: Optional[float] = None
    nubosidad: Optional[float]
    precipitacion_mm: Optional[float] = None
    viento_kmh_max: Optional[float] = None
    fuente: Optional[str]
    escenario: Optional[str] = None
    origen_dato: Optional[str] = None
    confiabilidad: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Alertas Schemas ---
class AlertaResponse(BaseModel):
    id: int
    empresa_id: int
    tipo: str
    mensaje: str
    severidad: str
    leida: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertaUpdate(BaseModel):
    leida: bool = True


# --- Recomendaciones Schemas ---
class RecomendacionResponse(BaseModel):
    id: int
    empresa_id: int
    texto: str
    tipo: Optional[str]
    impacto_estimado_cop: Optional[float]
    confianza_pct: Optional[float]
    escenario: Optional[str] = None
    origen_dato: Optional[str] = None
    confiabilidad_datos: Optional[float] = None
    aplicada: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Predicción Schemas ---
class PrediccionResponse(BaseModel):
    id: int
    empresa_id: Optional[int]
    fecha_prediccion: datetime
    fecha_objetivo: datetime
    tipo: str
    valor: float
    unidad: Optional[str]
    confianza_pct: Optional[float]
    escenario: Optional[str] = None
    origen_dato: Optional[str] = None
    confiabilidad_datos: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Configuración Alertas ---
class ConfigAlertaUpdate(BaseModel):
    umbral_consumo_diario_kwh: Optional[float] = None
    umbral_bateria_baja_pct: Optional[float] = None
    umbral_radiacion_baja: Optional[float] = None
    notificar_email: Optional[bool] = None
    notificar_dashboard: Optional[bool] = None


# --- Dashboard KPIs ---
class DashboardKPIs(BaseModel):
    radiacion_actual_kwh: Optional[float] = None
    consumo_hoy_kwh: Optional[float] = None
    costo_hoy_cop: Optional[float] = None
    produccion_solar_hoy_kwh: Optional[float] = None
    ahorro_estimado_cop: Optional[float] = None
    nivel_bateria_pct: Optional[float] = None
    consumo_mes_kwh: Optional[float] = None
    costo_mes_cop: Optional[float] = None
