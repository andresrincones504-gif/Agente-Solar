"""Cambios que envía la tabla editable de Mis aparatos (lógica sin Streamlit)."""
import pandas as pd
import pytest

# La carpeta streamlit_app no está dentro del contenedor de la API: ahí estas pruebas se omiten
inventario = pytest.importorskip("inventario")
calcular_cambios, coincide = inventario.calcular_cambios, inventario.coincide

APARATOS = [
    {"id": 1, "nombre": "Nevera exhibidora", "cantidad": 1, "potencia_w": None, "horas_uso_dia": None, "potencia_efectiva_w": 400, "horas_efectivas_dia": 14},
    {"id": 2, "nombre": "Vitrina", "cantidad": 1, "potencia_w": 800, "horas_uso_dia": 6, "potencia_efectiva_w": 800, "horas_efectivas_dia": 6},
    {"id": 3, "nombre": "Nevera", "cantidad": 1, "potencia_w": 120, "horas_uso_dia": None, "potencia_efectiva_w": 120, "horas_efectivas_dia": 10},
    {"id": 4, "nombre": "Bombillo LED", "cantidad": 10, "potencia_w": None, "horas_uso_dia": None, "potencia_efectiva_w": 9, "horas_efectivas_dia": 4},
]


def tabla():
    return pd.DataFrame({
        "id": [a["id"] for a in APARATOS],
        "Aparato": [a["nombre"] for a in APARATOS],
        "Cantidad": [a["cantidad"] for a in APARATOS],
        "Potencia (W)": pd.Series([a["potencia_efectiva_w"] for a in APARATOS], dtype="float64"),
        "Horas al día": pd.Series([a["horas_efectivas_dia"] for a in APARATOS], dtype="float64"),
        "Eliminar": [False] * len(APARATOS),
    })


def _cantidad_bombillos(e): e["Cantidad"] = [1, 1, 1, 12]
def _potencia_propia(e): e.loc[0, "Potencia (W)"] = 350
def _mismo_valor(e): e.loc[0, "Potencia (W)"] = 400
def _vaciar_propio(e): e.loc[2, "Potencia (W)"] = None
def _vaciar_tipico(e): e.loc[3, "Horas al día"] = None
def _varios(e): e.loc[2, "Horas al día"] = 12; e.loc[2, "Cantidad"] = 2
def _borrar(e): e.loc[1, "Eliminar"] = True; e.loc[1, "Cantidad"] = 5


@pytest.mark.parametrize("editar, cambios, borrados", [
    (lambda e: None, [], []),
    (_cantidad_bombillos, [(4, {"cantidad": 12})], []),
    (_potencia_propia, [(1, {"potencia_w": 350.0})], []),
    (_mismo_valor, [], []),  # escribir el valor típico no es un cambio
    (_vaciar_propio, [(3, {"potencia_w": None})], []),  # vuelve al valor del catálogo
    (_vaciar_tipico, [], []),
    (_varios, [(3, {"cantidad": 2, "horas_uso_dia": 12.0})], []),
    (_borrar, [], [2]),  # una fila para eliminar no se edita
], ids=["sin_cambios", "cantidad", "potencia_propia", "mismo_valor", "vaciar_propio", "vaciar_tipico", "varios", "eliminar"])
def test_calcular_cambios(editar, cambios, borrados):
    original = tabla()
    editada = original.copy()
    editar(editada)
    enviar, borrar = calcular_cambios(original, editada, APARATOS)
    assert [(i, p) for i, _, p in enviar] == cambios
    assert [i for i, _ in borrar] == borrados


def test_busqueda_sin_tildes_en_nombre_descripcion_y_palabras_clave():
    portatil = {"nombre": "Computador portátil", "descripcion": "Laptop de oficina", "palabras_clave": "pc"}
    assert coincide(portatil, "portatil")
    assert coincide(portatil, "LAPTOP")
    assert coincide(portatil, "")
    assert not coincide(portatil, "nevera")
