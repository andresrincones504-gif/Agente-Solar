"""API de catálogo, registro con aparatos, inventario y estadísticas."""
from datetime import datetime, timedelta

import pytest

from app.models import models as m
from tests.conftest import CLAVE

B = "/api/v1"


@pytest.fixture
def base(crear_empresa, crear_usuario):
    hotel = crear_empresa("Hotel", tipo="hotel", tipo_entidad="empresa")
    crear_usuario("admin@t.co", rol=m.UserRole.ADMIN)
    crear_usuario("hotel@t.co", empresa=hotel)
    return hotel


def registrar(cliente, email, **campos):
    datos = {"email": email, "password": CLAVE, "full_name": "Ana", "escenario_usuario": "real", **campos}
    return cliente.post(B + "/auth/register", json=datos)


def codigos(respuesta):
    return {a["codigo"] for a in respuesta.json()}


def test_catalogo_filtra_por_categoria_y_texto_sin_tildes(cliente):
    assert codigos(cliente.get(B + "/catalogo/aparatos", params={"categoria": "finca", "q": "bomba"})) == {"bomba_agua", "bomba_riego", "ordenadora"}
    assert codigos(cliente.get(B + "/catalogo/aparatos", params={"q": "ordeno"})) == {"ordenadora", "tanque_leche"}
    assert codigos(cliente.get(B + "/catalogo/aparatos", params={"categoria": "hogar", "q": "refrigerador"})) == {"nevera", "nevera_antigua"}
    assert cliente.get(B + "/catalogo/aparatos", params={"categoria": "marciano"}).status_code == 422


def test_registro_publico_no_permite_admin_ni_empresa_ajena(cliente, base, token):
    assert registrar(cliente, "x1@t.co", role="admin").status_code == 403
    assert registrar(cliente, "x2@t.co", empresa_id=base.id).status_code == 403
    r = cliente.post(B + "/auth/register", headers=token("admin@t.co"),
                     json={"email": "analista@t.co", "password": CLAVE, "full_name": "A", "role": "analista"})
    assert r.status_code == 201


def test_registro_con_aparatos_es_una_sola_transaccion(cliente, base, catalogo, Sesion):
    aparatos = [{"catalogo_id": catalogo["nevera"].id},
                {"catalogo_id": catalogo["aire_12000"].id, "potencia_w": 1100},
                {"nombre": "Acuario", "potencia_w": 30, "horas_uso_dia": 24}]
    r = registrar(cliente, "ana@t.co", nombre_empresa="Casa Ana", tipo_entidad="hogar", aparatos=aparatos)
    assert r.status_code == 201, r.text

    def conteo():
        s = Sesion()
        try:
            return (s.query(m.Empresa).count(), s.query(m.ConfiguracionAlerta).count(),
                    s.query(m.AparatoUsuario).count(), s.query(m.User).count())
        finally:
            s.close()

    antes = conteo()
    r = registrar(cliente, "malo@t.co", tipo_entidad="negocio",
                  aparatos=[{"catalogo_id": catalogo["nevera"].id}, {"catalogo_id": 99999}])
    assert r.status_code == 400 and "99999" in r.text
    assert conteo() == antes, "un registro fallido no deja usuario, empresa, configuración ni aparatos"

    assert registrar(cliente, "malo2@t.co", aparatos=[{"nombre": "Algo"}]).status_code == 422

    registrar(cliente, "viejo@t.co", tipo_empresa="hotel", nombre_empresa="Hotel Viejo")
    s = Sesion()
    assert s.query(m.Empresa).filter_by(nombre="Hotel Viejo").one().tipo_entidad == "empresa"
    s.close()


@pytest.fixture
def ana(cliente, base, catalogo, token):
    aparatos = [{"catalogo_id": catalogo["nevera"].id},
                {"catalogo_id": catalogo["aire_12000"].id, "potencia_w": 1100},
                {"nombre": "Acuario", "potencia_w": 30, "horas_uso_dia": 24}]
    r = registrar(cliente, "ana@t.co", nombre_empresa="Casa Ana", tipo_entidad="hogar", aparatos=aparatos)
    return r.json()["empresa_id"], token("ana@t.co")


def test_inventario_listar_agregar_editar_eliminar_y_permisos(cliente, base, ana, catalogo, token):
    emp_id, H = ana
    lista = cliente.get(B + f"/empresas/{emp_id}/aparatos", headers=H).json()
    assert [(a["nombre"], a["consumo_kwh_mes"], a["origen_dato"]) for a in lista] == [
        ("Aire acondicionado 12.000 BTU", 198.0, "usuario"), ("Nevera", 45.0, "catalogo"), ("Acuario", 21.6, "usuario")]
    acuario = next(a["id"] for a in lista if a["nombre"] == "Acuario")

    r = cliente.post(B + f"/empresas/{emp_id}/aparatos", headers=H, json=[{"catalogo_id": catalogo["bombillo_led"].id, "cantidad": 6}])
    assert r.status_code == 201
    led = r.json()[0]["id"]

    r = cliente.patch(B + f"/empresas/{emp_id}/aparatos/{led}", headers=H, json={"cantidad": 8})
    assert r.status_code == 200 and r.json()["consumo_kwh_mes"] == 8.64
    assert cliente.patch(B + f"/empresas/{emp_id}/aparatos/{acuario}", headers=H, json={"potencia_w": None}).status_code == 400

    assert cliente.delete(B + f"/empresas/{emp_id}/aparatos/{acuario}", headers=H).status_code == 204
    assert len(cliente.get(B + f"/empresas/{emp_id}/aparatos", headers=H).json()) == 3

    assert cliente.get(B + f"/empresas/{emp_id}/aparatos", headers=token("hotel@t.co")).status_code == 403
    assert cliente.delete(B + f"/empresas/{base.id}/aparatos/{led}", headers=token("admin@t.co")).status_code == 404


def test_estadisticas_se_ajustan_a_la_factura(cliente, ana, Sesion):
    emp_id, H = ana
    url = B + f"/empresas/{emp_id}/aparatos/estadisticas"

    e = cliente.get(url, headers=H).json()
    assert e["base_calculo"] == "catalogo"
    assert e["consumo_total_kwh_mes"] == 264.6  # 198 + 45 + 21.6
    assert e["costo_total_cop_mes"] == round(264.6 * 943)

    def cargar(kwh_dia, dias=10):
        s = Sesion()
        s.query(m.ConsumoEnergetico).filter_by(empresa_id=emp_id).delete()
        ayer = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
        for d in range(dias):
            s.add(m.ConsumoEnergetico(empresa_id=emp_id, fecha=ayer - timedelta(days=d), consumo_kwh=kwh_dia, periodo="diario", escenario="real"))
        s.add(m.ConsumoEnergetico(empresa_id=emp_id, fecha=ayer + timedelta(days=5), consumo_kwh=999, periodo="diario", escenario="real"))
        s.commit()
        s.close()

    cargar(5)  # 150 kWh/mes: menos que el inventario
    e = cliente.get(url, headers=H).json()
    suma = round(sum(a["consumo_kwh_mes"] for a in e["aparatos"]), 1)
    assert e["base_calculo"] == "factura" and e["consumo_real_kwh_mes"] == 150.0
    assert e["factor_ajuste"] < 1 and abs(suma - 150) < 0.1

    cargar(20)  # 600 kWh/mes: más que el inventario
    e = cliente.get(url, headers=H).json()
    no_ident = next(a for a in e["aparatos"] if a["aparato_id"] is None)
    assert e["consumo_total_kwh_mes"] == 600.0
    assert no_ident["consumo_kwh_mes"] == round(600 - 264.6, 2)
    assert abs(sum(a["porcentaje"] for a in e["aparatos"]) - 100) < 0.5
    assert [t["tipo_aparato"] for t in e["por_tipo"]][:2] == ["no_identificado", "climatizacion"]

    cargar(5, dias=3)  # muy pocos días: no se ajusta
    e = cliente.get(url, headers=H).json()
    assert e["base_calculo"] == "catalogo" and e["dias_con_datos"] == 3


def test_dimensionamiento_usa_la_factura_o_los_aparatos(cliente, ana):
    emp_id, H = ana
    d = cliente.get(B + f"/empresas/{emp_id}/aparatos/dimensionamiento", headers=H).json()
    assert d["base"] == "inventario" and d["consumo_mes_kwh"] == 264.6
    assert d["kwp_sugerido"] >= 1 and d["bateria_kwh_sugerida"] >= 2.5
