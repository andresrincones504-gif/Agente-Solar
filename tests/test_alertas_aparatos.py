"""Alertas que nombran los aparatos del usuario y alertas semanales por inventario."""
import asyncio
from datetime import datetime, timedelta

import pytest

from app.models import models as m
from app.services import openmeteo
from app.services.agents.agente_alertas import agente_alertas
from app.services.alertas_translator import humanizar_lote


@pytest.fixture(autouse=True)
def viento_fuerte(monkeypatch):
    async def pronostico(days=3, allow_synthetic=True):
        return [{"ghi": 5.5, "precipitacion_mm": 0.0, "viento_kmh_max": 55.0}, {"ghi": 5.5, "precipitacion_mm": 0.0}]
    monkeypatch.setattr(openmeteo.openmeteo_service, "get_forecast_diario", pronostico)


def alertas(db, empresa):
    return {a.tipo: a for a in db.query(m.Alerta).filter(m.Alerta.empresa_id == empresa.id).all()}


def contar(db, empresa, tipo):
    return db.query(m.Alerta).filter(m.Alerta.empresa_id == empresa.id, m.Alerta.tipo == tipo).count()


@pytest.fixture
def casa(db, crear_empresa, agregar_aparatos):
    """Casa con factura alta (≈550 kWh/mes) y un día de hoy de 80 kWh con pico de potencia."""
    casa = crear_empresa()
    agregar_aparatos(casa, ("aire_ventana", 1), ("nevera", 1), ("bombillo_led", 6), ("lavadora", 1), ("plancha", 1), ("router", 1))
    hoy = datetime.now().replace(minute=0, second=0, microsecond=0)
    for i in range(1, 29):
        db.add(m.ConsumoEnergetico(empresa_id=casa.id, fecha=hoy - timedelta(days=i), consumo_kwh=15 + (i % 3),
                                   demanda_pico_kw=2.0, periodo="diario", escenario="real"))
    db.add(m.ConsumoEnergetico(empresa_id=casa.id, fecha=hoy.replace(hour=0, minute=30), consumo_kwh=80,
                               demanda_pico_kw=4.5, periodo="diario", escenario="real"))
    db.commit()
    return casa


def test_sin_aparatos_solo_las_alertas_de_siempre(db, crear_empresa):
    vacia = crear_empresa("Vacía")
    asyncio.run(agente_alertas.evaluar(db, vacia))
    t = alertas(db, vacia)
    assert "riesgo_apagon" in t and "nevera" not in t["riesgo_apagon"].mensaje.lower()
    assert "aparato_dominante" not in t and "consumo_sobre_inventario" not in t


def test_las_alertas_nombran_los_aparatos(db, casa):
    asyncio.run(agente_alertas.evaluar(db, casa))
    t = alertas(db, casa)

    consumo_alto = t["consumo_alto"].mensaje
    assert "aire acondicionado de ventana" in consumo_alto
    assert "nevera" not in consumo_alto.split("Revisa primero")[1]  # no se sugiere apagar una carga crítica

    assert "plancha" in t["pico_demanda"].mensaje and "Air-E" not in t["pico_demanda"].mensaje
    assert "nevera" in t["riesgo_apagon"].mensaje
    assert t["consumo_sobre_inventario"].severidad == "baja"
    assert "aire acondicionado de ventana" in t["aparato_dominante"].mensaje


def test_plantillas_de_las_alertas_nuevas(db, casa):
    asyncio.run(agente_alertas.evaluar(db, casa))
    crudas = [{"id": a.id, "tipo": a.tipo, "mensaje": a.mensaje, "severidad": a.severidad} for a in alertas(db, casa).values()]
    h = {x["tipo_original"]: x for x in humanizar_lote(crudas, tiene_baterias=False, tiene_paneles=False)}
    assert h["consumo_sobre_inventario"]["titulo"] == "Tu factura no cuadra con tus aparatos"
    assert h["consumo_sobre_inventario"]["nivel"] == "verde"
    assert "Mis aparatos" in h["aparato_dominante"]["accion"]
    assert humanizar_lote([{"tipo": "recordatorio_pago", "severidad": "media"}])[0]["titulo"] == "Recordatorio de pago"


def test_alertas_por_aparato_se_repiten_como_maximo_una_vez_por_semana(db, casa):
    asyncio.run(agente_alertas.evaluar(db, casa))
    asyncio.run(agente_alertas.evaluar(db, casa))
    assert contar(db, casa, "aparato_dominante") == 1

    for a in db.query(m.Alerta).filter(m.Alerta.empresa_id == casa.id).all():
        a.leida = True
    db.commit()
    asyncio.run(agente_alertas.evaluar(db, casa))
    assert contar(db, casa, "aparato_dominante") == 1

    dominante = db.query(m.Alerta).filter(m.Alerta.empresa_id == casa.id, m.Alerta.tipo == "aparato_dominante").one()
    dominante.created_at = datetime.now() - timedelta(days=3)
    db.commit()
    asyncio.run(agente_alertas.evaluar(db, casa))
    assert contar(db, casa, "aparato_dominante") == 1

    dominante.created_at = datetime.now() - timedelta(days=8)
    db.commit()
    asyncio.run(agente_alertas.evaluar(db, casa))
    assert contar(db, casa, "aparato_dominante") == 2
    assert contar(db, casa, "consumo_alto") == 1


def test_recordatorio_de_pago_sobrevive_a_la_reevaluacion(db, casa):
    db.add(m.Alerta(empresa_id=casa.id, tipo="recordatorio_pago", mensaje="Paga antes del 30", severidad="media"))
    db.commit()
    asyncio.run(agente_alertas.evaluar(db, casa))
    assert contar(db, casa, "recordatorio_pago") == 1


def test_dias_futuros_de_una_factura_no_cuentan_como_hoy(db, crear_empresa):
    casa = crear_empresa()
    hoy = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    for i in range(-12, 20):  # 20 días pasados, hoy y 12 días futuros, 19 kWh cada uno
        db.add(m.ConsumoEnergetico(empresa_id=casa.id, fecha=hoy - timedelta(days=i), consumo_kwh=19, periodo="diario", escenario="real"))
    db.commit()
    asyncio.run(agente_alertas.evaluar(db, casa))
    assert "consumo_alto" not in alertas(db, casa)
