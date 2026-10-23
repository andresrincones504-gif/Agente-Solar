from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.core.config import get_settings
from app.db.session import Base

_settings = get_settings()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPRESA = "empresa"
    ANALISTA = "analista"


class TipoEntidad(str, enum.Enum):
    """Tipo de entidad que se registra. Define qué aparatos del catálogo se le ofrecen."""
    HOGAR = "hogar"
    NEGOCIO = "negocio"            # tienda, restaurante, peluquería, panadería...
    EMPRESA = "empresa"            # empresa o industria (hotel, hielera, bodega...)
    INSTITUCION = "institucion"    # colegio, puesto de salud, oficina pública
    FINCA = "finca"                # finca o actividad agropecuaria
    COMUNIDAD = "comunidad"        # comunidad / espacio comunitario


class VistaPreferida(str, enum.Enum):
    """Modo de visualización elegido por el usuario."""
    SIMPLE = "simple"            # Lenguaje natural, semáforos, sin números técnicos
    DETALLADO = "detallado"      # Series, métricas crudas, exportables
    OPERACIONAL = "operacional"  # Salud del sistema (admin)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(
        SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.EMPRESA,
        nullable=False,
    )
    escenario_usuario = Column(String(20), default="real", nullable=False)  # demo | real
    vista_preferida = Column(
        SQLEnum(VistaPreferida, values_callable=lambda x: [e.value for e in x]),
        default=VistaPreferida.SIMPLE,
        nullable=False,
    )
    is_active = Column(Boolean, default=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="users")


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    tipo = Column(String(100))  # giro o subtipo: hogar, hotel, hielera, retail, pyme, comunidad...
    tipo_entidad = Column(String(30), nullable=True, index=True)  # ver TipoEntidad
    direccion = Column(String(500))
    ciudad = Column(String(100), default=lambda: _settings.LOCATION_CITY)
    departamento = Column(String(100), default="La Guajira")
    tarifa_kwh = Column(Float, default=943.0)  # COP/kWh
    capacidad_paneles_kw = Column(Float, default=0.0)
    capacidad_bateria_kwh = Column(Float, default=0.0)
    escenario_default = Column(String(20), default="demo")  # demo | real
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="empresa")
    consumos = relationship("ConsumoEnergetico", back_populates="empresa")
    alertas = relationship("Alerta", back_populates="empresa")
    recomendaciones = relationship("Recomendacion", back_populates="empresa")
    aparatos = relationship(
        "AparatoUsuario", back_populates="empresa", cascade="all, delete-orphan"
    )


class RadiacionSolar(Base):
    __tablename__ = "radiacion_solar"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=False, index=True)
    ghi = Column(Float)  # Global Horizontal Irradiance (kWh/m²/día)
    dni = Column(Float)  # Direct Normal Irradiance
    dhi = Column(Float)  # Diffuse Horizontal Irradiance
    temperatura = Column(Float)  # °C (promedio)
    temperatura_max = Column(Float)  # °C
    temperatura_min = Column(Float)  # °C
    nubosidad = Column(Float)  # %
    precipitacion_mm = Column(Float)
    viento_kmh_max = Column(Float)
    # fuente: open_meteo (núcleo), openweather (complemento), pvgis (baseline),
    #         nasa_power (legacy), synthetic
    fuente = Column(String(50))
    escenario = Column(String(20), default="demo")  # demo | real
    origen_dato = Column(String(40), default="seed_demo")  # real_api | seed_demo | synthetic_fallback
    confiabilidad = Column(Float, default=50.0)  # 0-100
    latitud = Column(Float, default=lambda: _settings.LOCATION_LAT)
    longitud = Column(Float, default=lambda: _settings.LOCATION_LON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ConsumoEnergetico(Base):
    __tablename__ = "consumo_energetico"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    fecha = Column(DateTime, nullable=False, index=True)
    consumo_kwh = Column(Float, nullable=False)
    costo_cop = Column(Float)
    demanda_pico_kw = Column(Float)
    produccion_solar_kwh = Column(Float, default=0.0)
    nivel_bateria_pct = Column(Float)
    periodo = Column(String(20))  # horario, diario, mensual
    escenario = Column(String(20), default="demo")  # demo | real
    origen_dato = Column(String(40), default="seed_demo")  # real_upload | seed_demo
    confiabilidad = Column(Float, default=50.0)  # 0-100
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="consumos")


class Alerta(Base):
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo = Column(String(50), nullable=False)  # consumo_alto, pico_demanda, bateria_baja, baja_radiacion, riesgo_apagon
    mensaje = Column(Text, nullable=False)
    severidad = Column(String(20), default="media")  # baja, media, alta, critica
    leida = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="alertas")


class Recomendacion(Base):
    __tablename__ = "recomendaciones"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    texto = Column(Text, nullable=False)
    tipo = Column(String(50))  # ahorro, redistribucion, contingencia, mantenimiento
    impacto_estimado_cop = Column(Float)
    confianza_pct = Column(Float)
    escenario = Column(String(20), default="demo")  # demo | real
    origen_dato = Column(String(40), default="reglas")  # llm | reglas
    confiabilidad_datos = Column(Float, default=50.0)  # 0-100
    aplicada = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="recomendaciones")


class Prediccion(Base):
    __tablename__ = "predicciones"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    fecha_prediccion = Column(DateTime, nullable=False)
    fecha_objetivo = Column(DateTime, nullable=False)
    tipo = Column(String(50))  # produccion_solar, consumo, costo, riesgo_apagon
    valor = Column(Float, nullable=False)
    unidad = Column(String(20))  # kWh, COP, %
    confianza_pct = Column(Float)
    escenario = Column(String(20), default="demo")  # demo | real
    origen_dato = Column(String(40), default="modelo_hibrido")  # modelo_hibrido
    confiabilidad_datos = Column(Float, default=50.0)  # 0-100
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ConfiguracionAlerta(Base):
    __tablename__ = "configuracion_alertas"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    umbral_consumo_diario_kwh = Column(Float, default=500.0)
    umbral_bateria_baja_pct = Column(Float, default=20.0)
    umbral_radiacion_baja = Column(Float, default=2.0)
    notificar_email = Column(Boolean, default=True)
    notificar_dashboard = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CatalogoAparato(Base):
    """Aparatos comunes con su consumo aproximado. Se carga desde app/data/catalogo_aparatos.json."""
    __tablename__ = "catalogo_aparatos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(60), unique=True, nullable=False, index=True)  # identificador estable del JSON
    nombre = Column(String(120), nullable=False)
    descripcion = Column(String(300))
    tipo_aparato = Column(String(40), nullable=False, index=True)  # refrigeracion, climatizacion, iluminacion...
    categorias_entidad = Column(JSON, nullable=False)  # lista de TipoEntidad a las que aplica
    potencia_w = Column(Float, nullable=False)  # potencia típica (W)
    # Horas equivalentes a plena potencia por día. Para equipos con ciclos (nevera, aire)
    # ya incluye el tiempo en que el compresor está apagado.
    horas_uso_dia = Column(Float, nullable=False)
    palabras_clave = Column(String(300))
    fuente = Column(String(300))
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def consumo_kwh_mes(self) -> float:
        return round((self.potencia_w or 0) * (self.horas_uso_dia or 0) * 30 / 1000, 2)


class AparatoUsuario(Base):
    """Inventario de aparatos de un hogar, negocio o empresa."""
    __tablename__ = "aparatos_usuario"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    catalogo_id = Column(Integer, ForeignKey("catalogo_aparatos.id"), nullable=True)  # None = aparato propio
    nombre = Column(String(120), nullable=False)
    cantidad = Column(Integer, default=1, nullable=False)
    potencia_w = Column(Float, nullable=True)  # indicado por el usuario (opcional)
    horas_uso_dia = Column(Float, nullable=True)  # indicado por el usuario (opcional)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="aparatos")
    catalogo = relationship("CatalogoAparato")

    @property
    def tipo_aparato(self) -> str:
        return self.catalogo.tipo_aparato if self.catalogo else "otro"

    @property
    def potencia_efectiva_w(self) -> float:
        if self.potencia_w is not None:
            return self.potencia_w
        return self.catalogo.potencia_w if self.catalogo else 0.0

    @property
    def horas_efectivas_dia(self) -> float:
        if self.horas_uso_dia is not None:
            return self.horas_uso_dia
        return self.catalogo.horas_uso_dia if self.catalogo else 0.0

    @property
    def origen_dato(self) -> str:
        """'usuario' si la persona indicó potencia u horas; 'catalogo' si todo viene del catálogo."""
        if self.potencia_w is not None or self.horas_uso_dia is not None or self.catalogo is None:
            return "usuario"
        return "catalogo"

    @property
    def consumo_kwh_mes(self) -> float:
        return round(self.potencia_efectiva_w * self.horas_efectivas_dia * (self.cantidad or 1) * 30 / 1000, 2)


class InstalacionSolar(Base):
    """Datos técnicos del sistema solar de un hogar o empresa (pantalla "Tengo paneles solares" del registro).

    De aquí salen capacidad_paneles_kw (W x cantidad) y capacidad_bateria_kwh (V x Ah) de la empresa,
    que son los valores que usan hoy los cálculos de producción y ahorro.
    """
    __tablename__ = "instalaciones_solares"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, unique=True, index=True)
    # Paneles
    potencia_panel_w = Column(Float, nullable=False)
    cantidad_paneles = Column(Integer, nullable=False)
    orientacion = Column(String(20), default="sur")  # sur, sureste, suroeste, este_oeste, personalizada
    azimut_grados = Column(Float, nullable=True)  # 180 = sur
    inclinacion_grados = Column(Float, nullable=True)
    tipo_panel = Column(String(60), nullable=True)
    # Batería
    tiene_bateria = Column(Boolean, default=False, nullable=False)
    quimica_bateria = Column(String(60), nullable=True)
    voltaje_banco_v = Column(Float, nullable=True)
    capacidad_ah = Column(Float, nullable=True)
    soc_pct = Column(Float, nullable=True)
    dod_pct = Column(Float, nullable=True)
    eficiencia_ciclo_pct = Column(Float, nullable=True)
    potencia_descarga_w = Column(Float, nullable=True)
    # Inversor
    potencia_inversor_w = Column(Float, nullable=True)
    eficiencia_inversor_pct = Column(Float, nullable=True)
    rendimiento_pr_pct = Column(Float, nullable=True)
    potencia_pv_max_w = Column(Float, nullable=True)
    # Perfil de consumo
    consumo_diario_kwh = Column(Float, nullable=True)
    demanda_diurna_kwh = Column(Float, nullable=True)
    demanda_nocturna_kwh = Column(Float, nullable=True)
    carga_base_w = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def potencia_pico_kw(self) -> float:
        return round((self.potencia_panel_w or 0) * (self.cantidad_paneles or 0) / 1000, 3)

    @property
    def bateria_kwh(self) -> float:
        if not self.tiene_bateria or not self.voltaje_banco_v or not self.capacidad_ah:
            return 0.0
        return round(self.voltaje_banco_v * self.capacidad_ah / 1000, 3)
