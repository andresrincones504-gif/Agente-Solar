"""Franja solar, dimensionamiento, consejo del día y texto del inventario para Gemini."""
from datetime import datetime, timedelta

from app.models import models as m
from app.services import contexto_energetico as ce


def pronostico_campana():
    """Dos días de pronóstico horario con el pico a mediodía."""
    return [
        {"fecha": datetime(2026, 10, 19 + d, h), "ghi_w_m2": max(0, 950 - abs(h - 12) * 190) if 6 <= h <= 18 else 0}
        for d in range(2) for h in range(24)
    ]


def test_franja_solar_de_hoy_o_de_manana():
    fc = pronostico_campana()
    f = ce.franja_solar(fc, ahora=datetime(2026, 10, 19, 7, 0))
    assert f["es_hoy"] and (f["inicio"], f["fin"]) == (11, 14)
    tarde = ce.franja_solar(fc, ahora=datetime(2026, 10, 19, 15, 0))
    assert not tarde["es_hoy"] and tarde["texto"].startswith("mañana")
    assert ce.franja_solar([], ahora=datetime(2026, 10, 19, 7, 0)) is None


def test_dimensionamiento_por_referencia_inventario_y_factura(db, crear_empresa, agregar_aparatos):
    casa = crear_empresa()
    d0 = ce.dimensionar_sistema(db, casa)
    assert (d0["base"], d0["kwp_sugerido"], d0["bateria_kwh_sugerida"]) == ("referencia", 2.5, 5.0)

    agregar_aparatos(casa, ("nevera", 1), ("aire_12000", 1), ("bombillo_led", 8), ("lavadora", 1), ("router", 1))
    r = ce.resumen_inventario(db, casa)
    assert [a["nombre"] for a in r["top"]] == ["Aire acondicionado 12.000 BTU", "Nevera", "Lavadora"]
    assert [a["nombre"] for a in r["desplazables"]] == ["Lavadora"]

    d1 = ce.dimensionar_sistema(db, casa, r)
    # 216 + 45 + 15 + 8.64 + 7.2 = 291.84 kWh/mes
    assert d1["base"] == "inventario" and d1["consumo_mes_kwh"] == 291.8
    # Cargas críticas: nevera + bombillos + router = 60.84 kWh/mes = 2.03 kWh/día -> mínimo 2.5 kWh
    assert d1["cargas_criticas_kwh_dia"] == 2.03 and d1["bateria_kwh_sugerida"] == 2.5

    ayer = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
    for i in range(10):
        db.add(m.ConsumoEnergetico(empresa_id=casa.id, fecha=ayer - timedelta(days=i), consumo_kwh=20, periodo="diario", escenario="real"))
    db.commit()
    d2 = ce.dimensionar_sistema(db, casa)
    assert d2["base"] == "factura" and d2["consumo_mes_kwh"] == 600
    assert d2["kwp_sugerido"] == round(600 / (30 * d2["hsp"] * 0.8) * 2) / 2


def test_consejo_del_dia(db, crear_empresa, agregar_aparatos):
    franja = ce.franja_solar(pronostico_campana(), ahora=datetime(2026, 10, 19, 7, 0))
    vacia = crear_empresa("Vacía", tipo="pyme", tipo_entidad="negocio")
    assert ce.consejo_del_dia(ce.resumen_inventario(db, vacia), franja)["tipo"] == "sin_aparatos"

    sola = crear_empresa("Una nevera")
    agregar_aparatos(sola, ("nevera", 1))
    c = ce.consejo_del_dia(ce.resumen_inventario(db, sola), franja)
    assert "100%" not in c["titulo"] and "45 kWh" in c["titulo"]

    casa = crear_empresa()
    agregar_aparatos(casa, ("aire_12000", 1), ("nevera", 1), ("lavadora", 1))
    c = ce.consejo_del_dia(ce.resumen_inventario(db, casa), franja)
    assert c["tipo"] == "aparato_mayor" and "aire" in c["titulo"].lower() and "24 °C" in c["mensaje"]

    casa.capacidad_paneles_kw = 3.0
    db.commit()
    c = ce.consejo_del_dia(ce.resumen_inventario(db, casa), franja)
    assert c["tipo"] == "franja_solar" and "lavadora" in c["mensaje"]


def test_texto_para_gemini_incluye_no_identificado_y_cargas_desplazables(db, crear_empresa, agregar_aparatos):
    casa = crear_empresa()
    agregar_aparatos(casa, ("aire_12000", 1), ("lavadora", 1))
    ayer = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
    for i in range(10):
        db.add(m.ConsumoEnergetico(empresa_id=casa.id, fecha=ayer - timedelta(days=i), consumo_kwh=20, periodo="diario", escenario="real"))
    db.commit()
    texto = ce.texto_inventario_para_prompt(ce.resumen_inventario(db, casa))
    assert "no identificado" in texto.lower()
    assert "[se puede mover de horario]" in texto
