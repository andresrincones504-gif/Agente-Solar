"""Mi Día con el consejo de aparatos y el sistema sugerido; facturas con días futuros."""
import calendar
from datetime import datetime, timedelta

import pytest

from app.api.routes import insights
from app.models import models as m
from app.services.insights_translator import traducir_produccion_solar

B = "/api/v1"


@pytest.fixture
def casa(crear_empresa, crear_usuario, token):
    casa = crear_empresa("Casa Pérez")
    crear_usuario("casa@t.co", empresa=casa)
    return casa, token("casa@t.co")


def mi_dia(cliente, casa):
    empresa, H = casa
    r = cliente.get(B + f"/insights/diario/{empresa.id}", headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_mi_dia_sin_aparatos_invita_a_registrarlos(cliente, casa):
    d = mi_dia(cliente, casa)
    assert d["consejo_aparatos"]["tipo"] == "sin_aparatos"
    assert d["fuente_narrativa"] == "plantilla"  # sin clave de Gemini
    assert "2.5 kWp" in d["tarjetas"]["produccion"]["mensaje"]


def test_mi_dia_con_aparatos_y_sin_paneles(cliente, casa, agregar_aparatos):
    agregar_aparatos(casa[0], ("aire_12000", 1), ("nevera", 1), ("bombillo_led", 8), ("lavadora", 1))
    d = mi_dia(cliente, casa)
    assert d["consejo_aparatos"]["tipo"] == "aparato_mayor"
    assert "aire acondicionado" in d["consejo_aparatos"]["titulo"].lower()
    produccion = d["tarjetas"]["produccion"]["mensaje"]
    assert "kWh al mes" in produccion and "% de tu consumo" in produccion


def test_mi_dia_con_paneles_usa_la_franja_y_gemini_recibe_el_inventario(cliente, casa, db, agregar_aparatos, franja_fija, monkeypatch):
    empresa, _ = casa
    agregar_aparatos(empresa, ("aire_12000", 1), ("lavadora", 1))
    empresa.capacidad_paneles_kw = 3.0
    db.commit()
    enviado = {}

    async def gemini(prompt, system_instruction=None, model_name=None):
        enviado.update(prompt=prompt, model_name=model_name)
        return "Resumen de prueba"

    monkeypatch.setattr(insights, "obtener_respuesta_gemini", gemini)
    d = mi_dia(cliente, casa)
    assert d["consejo_aparatos"]["tipo"] == "franja_solar" and "lavadora" in d["consejo_aparatos"]["mensaje"]
    assert d["fuente_narrativa"] == "gemini"
    assert "Aire acondicionado" in enviado["prompt"] and "Consejo del día" in enviado["prompt"]
    assert enviado["model_name"] is None


def test_tarjeta_de_paneles_con_y_sin_sistema_calculado():
    assert "2.5 kWp" in traducir_produccion_solar(None, 10, 943, "hogar", 0.0, None)["mensaje"]
    sistema = {"kwp_sugerido": 4.0, "consumo_mes_kwh": 480, "produccion_mes_kwh": 480, "cobertura_pct": 100, "ahorro_mes_cop": 452640}
    mensaje = traducir_produccion_solar(None, 10, 943, "pyme", 0.0, sistema)["mensaje"]
    assert "4.0 kWp" in mensaje and "100%" in mensaje and "452,640" in mensaje


def test_factura_del_mes_en_curso_no_suma_dias_futuros_a_hoy(cliente, casa):
    empresa, H = casa
    hoy = datetime.now()
    r = cliente.post(B + "/consumo/monthly", headers=H, json={
        "empresa_id": empresa.id, "anio": hoy.year, "mes": hoy.month,
        "consumo_total_kwh": 600, "costo_energia_cop": 600 * 943})
    assert r.status_code == 201, r.text

    kpis = cliente.get(B + f"/consumo/kpis/{empresa.id}", headers=H, params={"escenario": "real"}).json()
    diario = 600 / calendar.monthrange(hoy.year, hoy.month)[1]
    assert kpis["consumo_hoy_kwh"] == pytest.approx(diario)
    assert kpis["consumo_mes_kwh"] == pytest.approx(diario * hoy.day)
    mensaje = mi_dia(cliente, casa)["tarjetas"]["consumo"]["mensaje"]
    assert f"{diario:.1f} kWh hoy" in mensaje or f"{diario:.0f} kWh hoy" in mensaje


def test_no_se_acepta_una_factura_de_un_mes_futuro(cliente, casa):
    empresa, H = casa
    futuro = (datetime.now().replace(day=1) + timedelta(days=40))
    r = cliente.post(B + "/consumo/monthly", headers=H, json={
        "empresa_id": empresa.id, "anio": futuro.year, "mes": futuro.month,
        "consumo_total_kwh": 600, "costo_energia_cop": 600 * 943})
    assert r.status_code == 400


@pytest.mark.parametrize("ghi", [6.5, 5.0, 3.5, 2.0])
def test_mensajes_de_radiacion_para_hogares_muestran_el_valor(ghi):
    from app.services.insights_translator import traducir_radiacion
    mensaje = traducir_radiacion(ghi, "hogar")["mensaje"]
    assert "{" not in mensaje and f"{ghi:.1f} kWh/m²" in mensaje


def test_los_mensajes_usan_la_ubicacion_configurada(monkeypatch):
    from app.core.config import get_settings
    from app.services.insights_translator import traducir_polvo, traducir_radiacion
    monkeypatch.setattr(get_settings(), "LOCATION_NAME", "Maicao, La Guajira")
    assert get_settings().LOCATION_CITY == "Maicao"
    assert "Maicao" in traducir_radiacion(1.5, "hogar")["mensaje"]
    assert "Fonseca" not in traducir_polvo(20.0, tipo_empresa="hogar")["mensaje"]
