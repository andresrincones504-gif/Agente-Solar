"""Recomendaciones: Gemini con el inventario y reglas por aparato como respaldo."""
import asyncio

import pytest

from app.services.agents import agente_recomendaciones as modulo

ag = modulo.agente_recomendaciones
SOLAR = {"promedio_ghi": 5.2}
CONSUMO = {"promedio_diario_kwh": 10, "total_kwh": 300, "num_anomalias": 0}


def test_sin_aparatos_y_sin_gemini_usa_reglas_e_invita_a_registrarlos(db, crear_empresa):
    casa = crear_empresa("Casa vacía")
    recs = asyncio.run(ag.generar(db, casa, SOLAR, CONSUMO))
    assert recs and all(r.origen_dato == "reglas" for r in recs)
    assert "Mis aparatos" in recs[0].texto
    assert len(recs) <= 5


@pytest.fixture
def casa_ineficiente(crear_empresa, agregar_aparatos):
    casa = crear_empresa()
    agregar_aparatos(casa, ("aire_ventana", 1), ("nevera_antigua", 1), ("bombillo_incandescente", 6),
                     ("lavadora", 1), ("decodificador", 1))
    return casa


def test_reglas_por_aparato_sin_paneles(db, casa_ineficiente, franja_fija):
    ctx = asyncio.run(ag.contexto(db, casa_ineficiente))
    recs = ag._generar_con_reglas(casa_ineficiente, SOLAR, CONSUMO, ctx)
    textos = [r["texto"] for r in recs]
    assert len(recs) == 5
    assert textos[0].startswith("Tu aire acondicionado de ventana es el")
    assert any("nevera antigua" in t for t in textos)
    # 6 × (60 − 9) W × 4 h × 30 días = 36.72 kWh/mes
    incandescentes = next(r for r in recs if "incandescente" in r["texto"])
    assert incandescentes["impacto_cop"] == round(36.72 * 943)
    # Sin paneles la tarifa es la misma a toda hora: no se sugiere mover consumo al sol
    assert not any(r["tipo"] == "redistribucion" and "sol" in r["texto"] for r in recs)


def test_con_paneles_sugiere_la_franja_una_sola_vez(db, casa_ineficiente, franja_fija):
    casa_ineficiente.capacidad_paneles_kw = 3.0
    db.commit()
    ctx = asyncio.run(ag.contexto(db, casa_ineficiente))
    recs = ag._generar_con_reglas(casa_ineficiente, SOLAR, CONSUMO, ctx)
    redistribucion = [r for r in recs if r["tipo"] == "redistribucion"]
    assert len(redistribucion) == 1
    assert "lavadora" in redistribucion[0]["texto"] and "11:00 a 14:00" in redistribucion[0]["texto"]


def test_gemini_recibe_aparatos_paneles_franja_y_sistema(db, casa_ineficiente, franja_fija, monkeypatch):
    casa_ineficiente.capacidad_paneles_kw = 3.0
    db.commit()
    enviado = {}

    async def gemini(prompt, system_instruction=None, model_name=None):
        enviado.update(prompt=prompt, model_name=model_name)
        return '```json\n{"recomendaciones": [{"texto": "Usa la lavadora a mediodía", "tipo": "redistribucion", "impacto_cop": 9000, "confianza": 80}]}\n```'

    monkeypatch.setattr(modulo, "obtener_respuesta_gemini", gemini)
    recs = asyncio.run(ag.generar(db, casa_ineficiente, SOLAR, CONSUMO))
    assert len(recs) == 1 and recs[0].origen_dato == "llm"
    for fragmento in ("Aire acondicionado de ventana", "SÍ tiene paneles", "11:00 a 14:00", "kWp"):
        assert fragmento in enviado["prompt"]
    assert enviado["model_name"] is None  # el modelo sale de GEMINI_MODEL


@pytest.mark.parametrize("respuesta", ["no sé", None, ValueError("GEMINI_API_KEY no está configurada")])
def test_gemini_caido_o_respuesta_invalida_vuelve_a_reglas(db, casa_ineficiente, monkeypatch, respuesta):
    async def gemini(**kwargs):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(modulo, "obtener_respuesta_gemini", gemini)
    recs = asyncio.run(ag.generar(db, casa_ineficiente, SOLAR, CONSUMO))
    assert recs and recs[0].origen_dato == "reglas"


def test_modo_demo_sin_contexto_sigue_funcionando(casa_ineficiente):
    assert asyncio.run(ag._generar_con_llm(casa_ineficiente, SOLAR, CONSUMO)) == []
    assert ag._generar_con_reglas(casa_ineficiente, SOLAR, CONSUMO)
