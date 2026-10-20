"""Migración de tipo_entidad, sincronización del catálogo y consumo efectivo de cada aparato."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.migrations import ensure_schema_compatibility
from app.db.session import Base
from app.models import models as m
from app.services import catalogo_aparatos as cat


def test_migracion_agrega_tipo_entidad_y_rellena_las_empresas_existentes():
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("""CREATE TABLE empresas (id INTEGER PRIMARY KEY, nombre VARCHAR(255) NOT NULL, tipo VARCHAR(100),
            direccion VARCHAR(500), ciudad VARCHAR(100), departamento VARCHAR(100), tarifa_kwh FLOAT,
            capacidad_paneles_kw FLOAT, capacidad_bateria_kwh FLOAT, escenario_default VARCHAR(20) NOT NULL DEFAULT 'demo',
            is_active BOOLEAN, created_at DATETIME)"""))
        c.execute(text("INSERT INTO empresas (id, nombre, tipo) VALUES "
                       "(1,'Hotel Solar Fonseca','hotel'),(2,'Familia Pérez','hogar'),(3,'Junta comunal','comunidad'),(4,'Hielera X','hielera')"))
    Base.metadata.create_all(eng, tables=[m.CatalogoAparato.__table__, m.AparatoUsuario.__table__])

    ensure_schema_compatibility(eng)
    ensure_schema_compatibility(eng)  # idempotente

    assert "tipo_entidad" in {c["name"] for c in inspect(eng).get_columns("empresas")}
    with eng.connect() as c:
        tipos = dict(c.execute(text("SELECT nombre, tipo_entidad FROM empresas")).all())
    assert tipos == {"Hotel Solar Fonseca": "empresa", "Familia Pérez": "hogar",
                     "Junta comunal": "comunidad", "Hielera X": "empresa"}


def test_sincronizar_catalogo_crea_actualiza_y_desactiva(Sesion, monkeypatch):
    db = Sesion()
    r1 = cat.sincronizar_catalogo(db)
    assert r1["creados"] == r1["total"] == 54

    r2 = cat.sincronizar_catalogo(db)
    assert (r2["creados"], r2["actualizados"], r2["desactivados"]) == (0, 0, 0)

    original = cat.cargar_catalogo_json
    monkeypatch.setattr(cat, "cargar_catalogo_json", lambda: [a for a in original() if a["codigo"] != "consola"])
    assert cat.sincronizar_catalogo(db)["desactivados"] == 1
    assert db.query(m.CatalogoAparato).filter_by(codigo="consola").one().activo is False

    monkeypatch.setattr(cat, "cargar_catalogo_json", original)
    r4 = cat.sincronizar_catalogo(db)
    assert r4["actualizados"] == 1 and r4["desactivados"] == 0
    assert db.query(m.CatalogoAparato).count() == 54

    nevera = db.query(m.CatalogoAparato).filter_by(codigo="nevera").one()
    assert nevera.categorias_entidad[0] == "hogar"
    assert nevera.consumo_kwh_mes == 45.0  # 150 W × 10 h × 30 días


def test_consumo_efectivo_usa_el_dato_del_usuario_o_el_del_catalogo(db, catalogo, crear_empresa):
    casa = crear_empresa("Familia Pérez")
    nevera = catalogo["nevera"]
    db.add_all([
        m.AparatoUsuario(empresa_id=casa.id, catalogo_id=nevera.id, nombre=nevera.nombre, cantidad=2),
        m.AparatoUsuario(empresa_id=casa.id, catalogo_id=nevera.id, nombre="Nevera de la cocina", potencia_w=120),
        m.AparatoUsuario(empresa_id=casa.id, nombre="Acuario", potencia_w=30, horas_uso_dia=24),
    ])
    db.commit()
    a1, a2, a3 = db.query(m.AparatoUsuario).order_by(m.AparatoUsuario.id).all()

    assert (a1.origen_dato, a1.consumo_kwh_mes) == ("catalogo", 90.0)
    assert (a2.origen_dato, a2.potencia_efectiva_w, a2.horas_efectivas_dia, a2.consumo_kwh_mes) == ("usuario", 120, 10.0, 36.0)
    assert (a3.origen_dato, a3.tipo_aparato, a3.consumo_kwh_mes) == ("usuario", "otro", 21.6)

    casa.aparatos.remove(a3)
    db.commit()
    assert db.query(m.AparatoUsuario).count() == 2
