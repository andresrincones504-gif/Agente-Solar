"""Lógica pura de la tabla editable de Mis aparatos (sin Streamlit), para poder probarla."""
from __future__ import annotations

import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd


def normalizar(texto: Optional[str]) -> str:
    """Minúsculas y sin tildes: 'portatil' encuentra 'Portátil'."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def coincide(aparato: Dict, busqueda: Optional[str]) -> bool:
    """Todas las palabras buscadas aparecen en el nombre, la descripción o los sinónimos."""
    palabras = normalizar(busqueda).split()
    if not palabras:
        return True
    texto = normalizar(" ".join(filter(None, [aparato.get("nombre"), aparato.get("descripcion"), aparato.get("palabras_clave")])))
    return all(p in texto for p in palabras)

CAMPOS_EDITABLES = (("Potencia (W)", "potencia_w"), ("Horas al día", "horas_uso_dia"))


def _num(valor) -> Optional[float]:
    return None if valor is None or pd.isna(valor) else float(valor)


def calcular_cambios(
    original: pd.DataFrame,
    editado: pd.DataFrame,
    aparatos: List[Dict],
) -> Tuple[List[Tuple[int, str, Dict]], List[Tuple[int, str]]]:
    """
    Compara la tabla mostrada con la editada y devuelve (cambios, borrar).

    La tabla muestra los valores efectivos (los del usuario o, si no indicó, los típicos):
    - una celda vaciada envía null para volver al valor típico, solo si el usuario tenía un valor propio;
    - una celda con un valor distinto al mostrado envía ese valor;
    - una fila marcada en "Eliminar" se borra y no se edita.
    """
    por_aparato = {a["id"]: a for a in aparatos}
    cambios: List[Tuple[int, str, Dict]] = []
    borrar: List[Tuple[int, str]] = []
    for (_, antes), (_, despues) in zip(original.iterrows(), editado.iterrows()):
        aparato_id = int(antes["id"])
        if bool(despues["Eliminar"]):
            borrar.append((aparato_id, antes["Aparato"]))
            continue
        payload: Dict = {}
        if int(despues["Cantidad"]) != int(antes["Cantidad"]):
            payload["cantidad"] = int(despues["Cantidad"])
        aparato = por_aparato[aparato_id]
        for col, campo in CAMPOS_EDITABLES:
            nuevo, mostrado = _num(despues[col]), _num(antes[col])
            if nuevo is None:
                if aparato.get(campo) is not None:
                    payload[campo] = None
            elif nuevo != mostrado:
                payload[campo] = nuevo
        if payload:
            cambios.append((aparato_id, antes["Aparato"], payload))
    return cambios, borrar


def payload_edicion(
    aparato: Dict,
    cantidad: int,
    potencia: Optional[float],
    horas: Optional[float],
) -> Dict:
    """
    Campos a enviar cuando se edita un aparato desde la ventana de edición.

    - la cantidad se envía si cambió;
    - potencia u horas vacías vuelven al valor típico (null), solo si el usuario tenía un valor propio;
    - un valor distinto al que se usa hoy en los cálculos se envía tal cual.
    """
    payload: Dict = {}
    if int(cantidad) != int(aparato["cantidad"]):
        payload["cantidad"] = int(cantidad)
    for campo, efectivo, nuevo in (
        ("potencia_w", aparato["potencia_efectiva_w"], potencia),
        ("horas_uso_dia", aparato["horas_efectivas_dia"], horas),
    ):
        if nuevo is None:
            if aparato.get(campo) is not None:
                payload[campo] = None
        elif float(nuevo) != float(efectivo):
            payload[campo] = float(nuevo)
    return payload
