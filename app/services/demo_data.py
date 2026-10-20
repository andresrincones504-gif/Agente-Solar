"""
Lectura de datasets demo en JSON (sin persistencia en BD).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "scripts" / "demo_data"
CONSUMO_FILE = DEMO_DIR / "consumo_demo.json"
RADIACION_FILE = DEMO_DIR / "radiacion_demo.json"
MANIFEST_FILE = DEMO_DIR / "manifest.json"
DEMO_EMPRESA_ID = 1


def _desfase() -> timedelta:
    """
    Días transcurridos desde que se generaron los JSON demo.

    Las fechas de los archivos son fijas; al leerlas se corren este número de días para que
    el último día generado como "hoy" siga siendo hoy y la demo no caduque. Los registros que
    se guardan se corren al revés, así que todo el archivo queda en la misma escala de tiempo.
    """
    try:
        generado = datetime.fromisoformat(json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))["generated_at"])
    except (OSError, ValueError, KeyError):
        return timedelta(0)
    return timedelta(days=(date.today() - generado.date()).days)


def _a_hoy(row: Dict[str, Any], desfase: timedelta) -> Dict[str, Any]:
    """Copia del registro con la fecha corrida al tiempo real."""
    copia = dict(row)
    try:
        copia["fecha"] = (datetime.fromisoformat(str(row.get("fecha"))) + desfase).isoformat()
    except ValueError:
        pass
    return copia


def _a_archivo(fecha: Any) -> Any:
    """Fecha real -> fecha en la escala del archivo (inversa de _a_hoy)."""
    if isinstance(fecha, str):
        try:
            fecha = datetime.fromisoformat(fecha)
        except ValueError:
            return fecha
    if isinstance(fecha, datetime):
        return (fecha - _desfase()).isoformat()
    return fecha


def _write(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_ids(rows: List[Dict[str, Any]], path: Path) -> List[Dict[str, Any]]:
    max_id = max((r.get("id") for r in rows if isinstance(r.get("id"), int)), default=99999)
    next_id = max(max_id + 1, 100000)
    updated = False
    for row in rows:
        if row.get("id") is None:
            row["id"] = next_id
            next_id += 1
            updated = True
        if path == CONSUMO_FILE and row.get("empresa_id") is None:
            row["empresa_id"] = DEMO_EMPRESA_ID
            updated = True
    if updated:
        _write(path, rows)
    return rows


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(row.get("fecha"), datetime):
        row["fecha"] = row["fecha"].isoformat()
    return row


def _within_days(fecha_iso: str, days: int) -> bool:
    """Últimos `days` días hasta hoy. Los días futuros de los JSON no cuentan."""
    try:
        fecha = datetime.fromisoformat(fecha_iso).replace(tzinfo=None)
    except ValueError:
        return False
    return datetime.now() - timedelta(days=days) <= fecha and fecha.date() <= date.today()


def _find_record(rows: List[Dict[str, Any]], record_id: int) -> Optional[Dict[str, Any]]:
    return next((r for r in rows if int(r.get("id", -1)) == record_id), None)


def get_consumo_demo(days: int = 30) -> List[Dict[str, Any]]:
    desfase = _desfase()
    rows = [_a_hoy(r, desfase) for r in _ensure_ids(_load(CONSUMO_FILE), CONSUMO_FILE)]
    rows = [r for r in rows if _within_days(str(r.get("fecha", "")), days)]
    rows.sort(key=lambda x: x.get("fecha", ""), reverse=True)
    return rows


def get_radiacion_demo(days: int = 30) -> List[Dict[str, Any]]:
    desfase = _desfase()
    rows = [_a_hoy(r, desfase) for r in _ensure_ids(_load(RADIACION_FILE), RADIACION_FILE)]
    rows = [r for r in rows if _within_days(str(r.get("fecha", "")), days)]
    rows.sort(key=lambda x: x.get("fecha", ""), reverse=True)
    return rows


def save_consumo_demo(data: Dict[str, Any]) -> Dict[str, Any]:
    rows = _ensure_ids(_load(CONSUMO_FILE), CONSUMO_FILE)
    record = {**data}
    record["empresa_id"] = DEMO_EMPRESA_ID
    record["escenario"] = "demo"
    record["origen_dato"] = "json_demo"
    record["confiabilidad"] = record.get("confiabilidad", 50.0)
    record = _serialize_row(record)
    record["fecha"] = _a_archivo(record.get("fecha"))
    max_id = max((r.get("id") for r in rows if isinstance(r.get("id"), int)), default=99999)
    record["id"] = max(max_id + 1, 100000)
    rows.insert(0, record)
    _write(CONSUMO_FILE, rows)
    return _a_hoy(record, _desfase())


def update_consumo_demo(consumo_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = _ensure_ids(_load(CONSUMO_FILE), CONSUMO_FILE)
    record = _find_record(rows, consumo_id)
    if record is None:
        return None
    for key, value in updates.items():
        if value is None:
            continue
        if key == "fecha":
            record[key] = _a_archivo(value)
        else:
            record[key] = value
    _write(CONSUMO_FILE, rows)
    return _a_hoy(record, _desfase())


def delete_consumo_demo(consumo_id: int) -> bool:
    rows = _ensure_ids(_load(CONSUMO_FILE), CONSUMO_FILE)
    remaining = [r for r in rows if int(r.get("id", -1)) != consumo_id]
    if len(remaining) == len(rows):
        return False
    _write(CONSUMO_FILE, remaining)
    return True


def save_radiacion_demo(data: Dict[str, Any]) -> Dict[str, Any]:
    rows = _ensure_ids(_load(RADIACION_FILE), RADIACION_FILE)
    record = {**data}
    record["escenario"] = "demo"
    record["origen_dato"] = record.get("origen_dato", "json_demo")
    record["confiabilidad"] = record.get("confiabilidad", 35.0)
    record = _serialize_row(record)
    record["fecha"] = _a_archivo(record.get("fecha"))
    max_id = max((r.get("id") for r in rows if isinstance(r.get("id"), int)), default=99999)
    record["id"] = max(max_id + 1, 100000)
    rows.insert(0, record)
    _write(RADIACION_FILE, rows)
    return _a_hoy(record, _desfase())


def update_radiacion_demo(radiacion_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = _ensure_ids(_load(RADIACION_FILE), RADIACION_FILE)
    record = _find_record(rows, radiacion_id)
    if record is None:
        return None
    for key, value in updates.items():
        if value is None:
            continue
        if key == "fecha":
            record[key] = _a_archivo(value)
        else:
            record[key] = value
    _write(RADIACION_FILE, rows)
    return _a_hoy(record, _desfase())


def delete_radiacion_demo(radiacion_id: int) -> bool:
    rows = _ensure_ids(_load(RADIACION_FILE), RADIACION_FILE)
    remaining = [r for r in rows if int(r.get("id", -1)) != radiacion_id]
    if len(remaining) == len(rows):
        return False
    _write(RADIACION_FILE, remaining)
    return True


def get_demo_empresa() -> Dict[str, Any]:
    return {
        "id": DEMO_EMPRESA_ID,
        "nombre": "Hotel Solar Fonseca (Demo)",
        "tipo": "hotel",
        "tipo_entidad": "empresa",
        "direccion": "Calle 13 #18-40, Fonseca",
        "ciudad": "Fonseca",
        "departamento": "La Guajira",
        "tarifa_kwh": 943.0,
        "capacidad_paneles_kw": 15.0,
        "capacidad_bateria_kwh": 30.0,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }
