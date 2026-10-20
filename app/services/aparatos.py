"""
Inventario de aparatos: búsqueda en el catálogo y estadísticas de consumo por aparato.

No hay medidores por aparato, así que el consumo de cada uno es una estimación
(potencia x horas de uso). Cuando la empresa tiene consumo real registrado
(factura o carga de datos) se ajusta a ese total:
- si el inventario estima MÁS de lo real, se reduce cada aparato en la misma proporción;
- si estima MENOS, los aparatos conservan su estimación y la diferencia aparece como
  "Consumo no identificado" (aparatos que la persona no registró).
"""
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import AparatoUsuario, CatalogoAparato, ConsumoEnergetico, Empresa

DIAS_VENTANA = 30
DIAS_MINIMOS_FACTURA = 7  # con menos días registrados no se ajusta a lo real
NO_IDENTIFICADO = "no_identificado"


def normalizar(texto: Optional[str]) -> str:
    """Minúsculas y sin tildes, para que 'nevera' encuentre 'Nevera' y 'bombillo' encuentre 'Bombíllo'."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


def filtrar_catalogo(
    aparatos: Iterable[CatalogoAparato],
    categoria: Optional[str] = None,
    q: Optional[str] = None,
    tipo_aparato: Optional[str] = None,
) -> List[CatalogoAparato]:
    palabras = normalizar(q).split()
    resultado = []
    for a in aparatos:
        if not a.activo:
            continue
        if categoria and categoria not in (a.categorias_entidad or []):
            continue
        if tipo_aparato and a.tipo_aparato != tipo_aparato:
            continue
        if palabras:
            texto = normalizar(" ".join(filter(None, [a.nombre, a.descripcion, a.palabras_clave])))
            if not all(p in texto for p in palabras):
                continue
        resultado.append(a)
    return sorted(resultado, key=lambda a: (a.tipo_aparato, a.nombre))


def consumo_real_mensual(db: Session, empresa: Empresa) -> Dict[str, Optional[float]]:
    """Consumo real de los últimos 30 días llevado a 30 días, o None si hay muy pocos días con datos."""
    ahora = datetime.now()
    desde = ahora - timedelta(days=DIAS_VENTANA)
    escenario = empresa.escenario_default or "real"
    filas = (
        db.query(func.date(ConsumoEnergetico.fecha), func.sum(ConsumoEnergetico.consumo_kwh))
        .filter(
            ConsumoEnergetico.empresa_id == empresa.id,
            ConsumoEnergetico.fecha >= desde,
            ConsumoEnergetico.fecha <= ahora,  # la factura mensual genera registros de días futuros
            ConsumoEnergetico.escenario == escenario,
        )
        .group_by(func.date(ConsumoEnergetico.fecha))
        .all()
    )
    dias = len(filas)
    total = sum(float(kwh or 0) for _, kwh in filas)
    mensual = round(total / dias * DIAS_VENTANA, 2) if dias >= DIAS_MINIMOS_FACTURA else None
    return {"dias_con_datos": dias, "consumo_real_kwh_mes": mensual}


def calcular_estadisticas(db: Session, empresa: Empresa) -> Dict:
    tarifa = float(empresa.tarifa_kwh or 0)
    aparatos = (
        db.query(AparatoUsuario)
        .filter(AparatoUsuario.empresa_id == empresa.id)
        .all()
    )
    inventario = round(sum(a.consumo_kwh_mes for a in aparatos), 2)
    real = consumo_real_mensual(db, empresa)
    consumo_real = real["consumo_real_kwh_mes"]

    factor = None
    no_identificado = 0.0
    if consumo_real is None:
        base, total = "catalogo", inventario
    else:
        base, total = "factura", consumo_real
        if inventario > consumo_real and inventario > 0:
            factor = round(consumo_real / inventario, 4)
        else:
            factor = 1.0
            no_identificado = round(consumo_real - inventario, 2)

    def pct(kwh: float) -> float:
        return round(kwh / total * 100, 1) if total else 0.0

    filas = []
    for a in aparatos:
        estimado = a.consumo_kwh_mes
        ajustado = round(estimado * factor, 2) if factor is not None else estimado
        filas.append({
            "aparato_id": a.id,
            "nombre": a.nombre,
            "tipo_aparato": a.tipo_aparato,
            "cantidad": a.cantidad,
            "origen_dato": a.origen_dato,
            "consumo_estimado_kwh_mes": estimado,
            "consumo_kwh_mes": ajustado,
            "costo_cop_mes": round(ajustado * tarifa, 0),
            "porcentaje": pct(ajustado),
        })
    filas.sort(key=lambda f: f["consumo_kwh_mes"], reverse=True)
    if no_identificado > 0:
        filas.append({
            "aparato_id": None,
            "nombre": "Consumo no identificado",
            "tipo_aparato": NO_IDENTIFICADO,
            "cantidad": 1,
            "origen_dato": "factura",
            "consumo_estimado_kwh_mes": 0.0,
            "consumo_kwh_mes": no_identificado,
            "costo_cop_mes": round(no_identificado * tarifa, 0),
            "porcentaje": pct(no_identificado),
        })

    por_tipo: Dict[str, float] = {}
    for f in filas:
        por_tipo[f["tipo_aparato"]] = por_tipo.get(f["tipo_aparato"], 0.0) + f["consumo_kwh_mes"]
    por_tipo_lista = sorted(
        (
            {"tipo_aparato": t, "consumo_kwh_mes": round(k, 2), "costo_cop_mes": round(k * tarifa, 0), "porcentaje": pct(k)}
            for t, k in por_tipo.items()
        ),
        key=lambda x: x["consumo_kwh_mes"],
        reverse=True,
    )

    return {
        "empresa_id": empresa.id,
        "tarifa_kwh": tarifa,
        "base_calculo": base,
        "dias_con_datos": real["dias_con_datos"],
        "consumo_inventario_kwh_mes": inventario,
        "consumo_real_kwh_mes": consumo_real,
        "consumo_total_kwh_mes": round(total, 2),
        "costo_total_cop_mes": round(total * tarifa, 0),
        "factor_ajuste": factor,
        "aparatos": filas,
        "por_tipo": por_tipo_lista,
    }


def crear_aparatos(db: Session, empresa_id: int, items: list) -> List[AparatoUsuario]:
    """Valida los ids del catálogo y agrega los aparatos a la sesión (sin commit)."""
    ids = {i.catalogo_id for i in items if i.catalogo_id is not None}
    catalogo = {}
    if ids:
        catalogo = {
            c.id: c
            for c in db.query(CatalogoAparato).filter(CatalogoAparato.id.in_(ids), CatalogoAparato.activo == True).all()  # noqa: E712
        }
    invalidos = sorted(ids - set(catalogo))
    if invalidos:
        raise ValueError(f"Aparatos del catálogo no encontrados o inactivos: {invalidos}")
    creados = []
    for i in items:
        cat = catalogo.get(i.catalogo_id) if i.catalogo_id is not None else None
        aparato = AparatoUsuario(
            empresa_id=empresa_id,
            catalogo_id=cat.id if cat else None,
            catalogo=cat,
            nombre=i.nombre or cat.nombre,
            cantidad=i.cantidad,
            potencia_w=i.potencia_w,
            horas_uso_dia=i.horas_uso_dia,
        )
        db.add(aparato)
        creados.append(aparato)
    return creados
