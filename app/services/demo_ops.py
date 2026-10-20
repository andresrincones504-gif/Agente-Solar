"""
Estado operativo de modo demo persistido en JSON (sin BD).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "scripts" / "demo_data"
RECS_FILE = DEMO_DIR / "recomendaciones_demo.json"
PREDS_FILE = DEMO_DIR / "predicciones_demo.json"
ALERTS_FILE = DEMO_DIR / "alertas_demo.json"
CONFIG_FILE = DEMO_DIR / "config_alertas_demo.json"


def _ensure() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for path, default in (
        (RECS_FILE, []),
        (PREDS_FILE, []),
        (ALERTS_FILE, []),
        (CONFIG_FILE, {"umbral_consumo_diario_kwh": 400.0, "umbral_bateria_baja_pct": 20.0, "umbral_radiacion_baja": 2.5, "notificar_email": False, "notificar_dashboard": True}),
    ):
        if not path.exists():
            path.write_text(json.dumps(default, ensure_ascii=True, indent=2), encoding="utf-8")


def _read(path: Path, default: Any):
    _ensure()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, value: Any) -> None:
    _ensure()
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding="utf-8")


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def list_demo_recs(empresa_id: int) -> List[Dict[str, Any]]:
    return [r for r in _read(RECS_FILE, []) if r.get("empresa_id") == empresa_id]


def save_demo_recs(empresa_id: int, recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing = _read(RECS_FILE, [])
    existing = [r for r in existing if r.get("empresa_id") != empresa_id]
    base_id = int(datetime.now().timestamp())
    out = []
    for i, r in enumerate(recs):
        out.append(
            {
                "id": base_id + i,
                "empresa_id": empresa_id,
                "texto": r.get("texto", ""),
                "tipo": r.get("tipo", "ahorro"),
                "impacto_estimado_cop": float(r.get("impacto_cop", r.get("impacto_estimado_cop", 0)) or 0),
                "confianza_pct": float(r.get("confianza", r.get("confianza_pct", 75)) or 75),
                "escenario": "demo",
                "origen_dato": "json_demo",
                "confiabilidad_datos": 55.0,
                "aplicada": False,
                "created_at": now_iso(),
            }
        )
    existing.extend(out)
    _write(RECS_FILE, existing)
    return out


def mark_demo_rec_applied(rec_id: int) -> Dict[str, Any] | None:
    rows = _read(RECS_FILE, [])
    found = None
    for r in rows:
        if r.get("id") == rec_id:
            r["aplicada"] = True
            found = r
            break
    if found:
        _write(RECS_FILE, rows)
    return found


def list_demo_preds(empresa_id: int, tipo: str | None = None) -> List[Dict[str, Any]]:
    rows = [p for p in _read(PREDS_FILE, []) if p.get("empresa_id") == empresa_id]
    if tipo:
        rows = [p for p in rows if p.get("tipo") == tipo]
    return rows


def save_demo_preds(empresa_id: int, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing = _read(PREDS_FILE, [])
    existing = [p for p in existing if p.get("empresa_id") != empresa_id]
    existing.extend(rows)
    _write(PREDS_FILE, existing)
    return rows


def list_demo_alerts(empresa_id: int) -> List[Dict[str, Any]]:
    return [a for a in _read(ALERTS_FILE, []) if a.get("empresa_id") == empresa_id]


def save_demo_alerts(empresa_id: int, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing = _read(ALERTS_FILE, [])
    existing = [a for a in existing if a.get("empresa_id") != empresa_id]
    existing.extend(rows)
    _write(ALERTS_FILE, existing)
    return rows


def mark_demo_alert_read(alert_id: int) -> Dict[str, Any] | None:
    rows = _read(ALERTS_FILE, [])
    found = None
    for a in rows:
        if a.get("id") == alert_id:
            a["leida"] = True
            found = a
            break
    if found:
        _write(ALERTS_FILE, rows)
    return found


def get_demo_alert_config() -> Dict[str, Any]:
    return _read(CONFIG_FILE, {})


def set_demo_alert_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = get_demo_alert_config()
    current.update(payload)
    _write(CONFIG_FILE, current)
    return current

