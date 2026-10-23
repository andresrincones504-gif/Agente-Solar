"""Registro con la instalación solar ("Tengo paneles solares"): tabla instalaciones_solares."""
import pytest

from app.models import models as m
from tests.conftest import CLAVE

B = "/api/v1"

INSTALACION = {
    "potencia_panel_w": 500.0, "cantidad_paneles": 12, "orientacion": "sur", "azimut_grados": 180.0,
    "inclinacion_grados": 12, "tipo_panel": "Monocristalino PERC / TOPCon",
    "tiene_bateria": True, "quimica_bateria": "Litio LiFePO4", "voltaje_banco_v": 48.0, "capacidad_ah": 200.0,
    "soc_pct": 78, "dod_pct": 90.0, "eficiencia_ciclo_pct": 95.0, "potencia_descarga_w": 5000.0,
    "potencia_inversor_w": 5000.0, "eficiencia_inversor_pct": 97.5, "rendimiento_pr_pct": 82.0,
    "potencia_pv_max_w": 6500.0, "consumo_diario_kwh": 14.5, "demanda_diurna_kwh": 6.5,
    "demanda_nocturna_kwh": 8.0, "carga_base_w": 200.0,
}


@pytest.fixture
def admin(crear_usuario, token):
    crear_usuario("admin@t.co", rol=m.UserRole.ADMIN)
    return token("admin@t.co")


def registrar(cliente, admin, email, **campos):
    datos = {"email": email, "password": CLAVE, "full_name": "Ana", "escenario_usuario": "real",
             "nombre_empresa": "Casa Ana", "tipo_entidad": "hogar", **campos}
    return cliente.post(B + "/auth/register", json=datos, headers=admin)


def test_registro_guarda_la_instalacion_y_las_capacidades(cliente, admin, Sesion):
    r = registrar(cliente, admin, "ana@t.co", instalacion=INSTALACION)
    assert r.status_code == 201, r.text
    s = Sesion()
    try:
        empresa = s.query(m.Empresa).filter_by(nombre="Casa Ana").one()
        inst = s.query(m.InstalacionSolar).filter_by(empresa_id=empresa.id).one()
        assert inst.cantidad_paneles == 12 and inst.orientacion == "sur" and inst.soc_pct == 78
        # 500 W × 12 = 6 kWp; 48 V × 200 Ah = 9,6 kWh
        assert empresa.capacidad_paneles_kw == pytest.approx(6.0)
        assert empresa.capacidad_bateria_kwh == pytest.approx(9.6)
    finally:
        s.close()


def test_sin_bateria_la_capacidad_de_bateria_es_cero(cliente, admin, Sesion):
    sin_bateria = {k: v for k, v in INSTALACION.items() if k not in ("quimica_bateria", "voltaje_banco_v", "capacidad_ah")}
    r = registrar(cliente, admin, "luis@t.co", instalacion={**sin_bateria, "tiene_bateria": False})
    assert r.status_code == 201, r.text
    s = Sesion()
    try:
        empresa = s.query(m.Empresa).filter_by(nombre="Casa Ana").one()
        assert empresa.capacidad_paneles_kw == pytest.approx(6.0)
        assert empresa.capacidad_bateria_kwh == 0
    finally:
        s.close()


def test_registro_sin_instalacion_no_crea_fila(cliente, admin, Sesion):
    assert registrar(cliente, admin, "eva@t.co").status_code == 201
    s = Sesion()
    try:
        assert s.query(m.InstalacionSolar).count() == 0
    finally:
        s.close()


@pytest.mark.parametrize("cambio", [
    {"capacidad_ah": None},                 # batería sin capacidad
    {"orientacion": "norte"},               # orientación que no existe
    {"cantidad_paneles": 0},
    {"inclinacion_grados": 120},
])
def test_datos_invalidos_no_crean_la_cuenta(cliente, admin, Sesion, cambio):
    r = registrar(cliente, admin, "mal@t.co", instalacion={**INSTALACION, **cambio})
    assert r.status_code == 422
    s = Sesion()
    try:
        assert s.query(m.User).filter_by(email="mal@t.co").count() == 0
    finally:
        s.close()
