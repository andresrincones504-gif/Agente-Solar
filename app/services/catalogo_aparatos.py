"""
Catálogo de aparatos eléctricos comunes con su consumo aproximado.

La fuente de verdad es app/data/catalogo_aparatos.json. Al arrancar la API se
sincroniza con la tabla catalogo_aparatos por `codigo`: se crean los nuevos, se
actualizan los existentes y se desactivan (sin borrar) los que ya no están en el
JSON, porque puede haber aparatos de usuarios que los referencian.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.models import CatalogoAparato, TipoEntidad

logger = logging.getLogger("app.services.catalogo_aparatos")

CATALOGO_FILE = Path(__file__).resolve().parents[1] / "data" / "catalogo_aparatos.json"
CAMPOS = (
    "nombre",
    "descripcion",
    "tipo_aparato",
    "categorias_entidad",
    "potencia_w",
    "horas_uso_dia",
    "palabras_clave",
    "fuente",
)
CATEGORIAS_VALIDAS = {t.value for t in TipoEntidad}


def cargar_catalogo_json(path: Path = CATALOGO_FILE) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    aparatos = data.get("aparatos", [])
    validos = []
    for item in aparatos:
        cats = item.get("categorias_entidad") or []
        invalidas = [c for c in cats if c not in CATEGORIAS_VALIDAS]
        if not item.get("codigo") or not cats or invalidas:
            logger.warning("Aparato ignorado en el catálogo: %s (categorías inválidas: %s)", item.get("codigo"), invalidas)
            continue
        validos.append(item)
    return validos


def sincronizar_catalogo(db: Session) -> Dict[str, int]:
    """Sincroniza la tabla con el JSON. Devuelve cuántos se crearon, actualizaron y desactivaron."""
    items = cargar_catalogo_json()
    existentes = {a.codigo: a for a in db.query(CatalogoAparato).all()}
    creados = actualizados = 0

    for item in items:
        valores = {campo: item.get(campo) for campo in CAMPOS}
        actual = existentes.get(item["codigo"])
        if actual is None:
            db.add(CatalogoAparato(codigo=item["codigo"], activo=True, **valores))
            creados += 1
            continue
        cambio = not actual.activo or any(getattr(actual, k) != v for k, v in valores.items())
        if cambio:
            for k, v in valores.items():
                setattr(actual, k, v)
            actual.activo = True
            actualizados += 1

    codigos_json = {i["codigo"] for i in items}
    desactivados = 0
    for codigo, aparato in existentes.items():
        if codigo not in codigos_json and aparato.activo:
            aparato.activo = False
            desactivados += 1

    db.commit()
    return {"total": len(items), "creados": creados, "actualizados": actualizados, "desactivados": desactivados}
