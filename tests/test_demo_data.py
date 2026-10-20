"""Datos demo en JSON: sin días futuros y con fechas que no caducan."""
import json
from datetime import date, datetime, timedelta

import pytest

from app.services import demo_data


@pytest.fixture
def archivos_demo(tmp_path, monkeypatch):
    """JSON generados hace 10 días: 5 días antes y 5 después de esa fecha."""
    generado = datetime.now() - timedelta(days=10)
    filas = [{"id": 100000 + i, "empresa_id": 1, "fecha": (generado + timedelta(days=i)).replace(hour=23, minute=59).isoformat(),
              "consumo_kwh": 100 + i} for i in range(-5, 6)]
    (tmp_path / "consumo.json").write_text(json.dumps(filas), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"generated_at": generado.isoformat()}), encoding="utf-8")
    monkeypatch.setattr(demo_data, "CONSUMO_FILE", tmp_path / "consumo.json")
    monkeypatch.setattr(demo_data, "MANIFEST_FILE", tmp_path / "manifest.json")
    return tmp_path


def test_las_fechas_se_corren_a_hoy_y_no_hay_dias_futuros(archivos_demo):
    filas = demo_data.get_consumo_demo(days=30)
    fechas = [datetime.fromisoformat(f["fecha"]).date() for f in filas]
    assert max(fechas) == date.today()  # el "hoy" del archivo es hoy
    assert len(filas) == 6  # 5 días previos + hoy; los 5 futuros no cuentan
    hoy = next(f for f in filas if datetime.fromisoformat(f["fecha"]).date() == date.today())
    assert hoy["consumo_kwh"] == 100


def test_un_registro_guardado_hoy_se_lee_con_la_fecha_de_hoy(archivos_demo):
    ahora = datetime.now().replace(microsecond=0)
    guardado = demo_data.save_consumo_demo({"fecha": ahora, "consumo_kwh": 42})
    assert guardado["fecha"] == ahora.isoformat()
    en_archivo = json.loads((archivos_demo / "consumo.json").read_text(encoding="utf-8"))[0]
    assert datetime.fromisoformat(en_archivo["fecha"]).date() == (ahora - timedelta(days=10)).date()
    assert any(f["consumo_kwh"] == 42 for f in demo_data.get_consumo_demo(days=2))

    nueva = ahora - timedelta(days=1)
    actualizado = demo_data.update_consumo_demo(guardado["id"], {"fecha": nueva})
    assert actualizado["fecha"] == nueva.isoformat()


def test_sin_manifest_no_se_corre_nada(archivos_demo, monkeypatch):
    monkeypatch.setattr(demo_data, "MANIFEST_FILE", archivos_demo / "no_existe.json")
    assert demo_data._desfase() == timedelta(0)
