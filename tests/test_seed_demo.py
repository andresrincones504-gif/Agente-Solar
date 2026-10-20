"""Seed: configuración de alertas única e inventario del hotel demo."""
from app.models import models as m
from app.services import contexto_energetico as ce
from scripts import seed


def test_config_alertas_se_crea_una_vez_y_se_quitan_duplicados(db, crear_empresa):
    hotel = crear_empresa("Hotel Solar Fonseca", tipo="hotel", tipo_entidad="empresa")
    seed.asegurar_config_alertas(db, hotel)
    seed.asegurar_config_alertas(db, hotel)
    assert db.query(m.ConfiguracionAlerta).filter_by(empresa_id=hotel.id).count() == 1

    db.add(m.ConfiguracionAlerta(empresa_id=hotel.id))
    db.commit()
    seed.asegurar_config_alertas(db, hotel)
    assert db.query(m.ConfiguracionAlerta).filter_by(empresa_id=hotel.id).count() == 1


def test_inventario_demo_del_hotel_sin_duplicar(db, crear_empresa, catalogo, franja_fija):
    hotel = crear_empresa("Hotel Solar Fonseca", tipo="hotel", tipo_entidad="empresa", capacidad_paneles_kw=15.0)
    db.add(m.AparatoUsuario(empresa_id=hotel.id, catalogo_id=catalogo["nevera"].id, nombre="Nevera", cantidad=1))
    db.commit()

    seed.cargar_aparatos_demo(db, hotel)
    n = db.query(m.AparatoUsuario).filter_by(empresa_id=hotel.id).count()
    assert n == 23  # la nevera que ya tenía no se duplica
    seed.cargar_aparatos_demo(db, hotel)
    assert db.query(m.AparatoUsuario).filter_by(empresa_id=hotel.id).count() == n

    resumen = ce.resumen_inventario(db, hotel)
    assert 9000 < resumen["inventario_kwh_mes"] < 11750  # menos que el consumo demo (~11.750 kWh/mes)
    assert resumen["top"][0]["nombre"] == "Aire acondicionado 12.000 BTU"
    assert ce.consejo_del_dia(resumen, franja_fija)["tipo"] == "franja_solar"
