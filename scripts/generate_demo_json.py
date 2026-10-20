"""
Genera datos sintéticos demo en JSON (sin persistir en base de datos).
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "demo_data"


def build_consumo(days_past: int = 60, days_future: int = 20) -> list[dict]:
    random.seed(42)
    now = datetime.now()
    rows: list[dict] = []
    tarifa_kwh = 943.0
    
    # Registros históricos hacia atrás
    for i in range(days_past):
        fecha = (now - timedelta(days=i)).replace(hour=23, minute=59, second=0, microsecond=0)
        base_consumo = 380 + random.gauss(0, 30)
        if i in (15, 35):
            base_consumo *= 1.6
        base_produccion = max(0, 60 + random.gauss(0, 15))
        demanda = 20 + random.gauss(0, 3)
        bateria = max(20, min(100, 75 + random.gauss(0, 15)))
        consumo_kwh = round(max(0, base_consumo), 2)
        rows.append(
            {
                "fecha": fecha.isoformat(),
                "consumo_kwh": consumo_kwh,
                "costo_cop": round(consumo_kwh * tarifa_kwh, 0),
                "demanda_pico_kw": round(max(0, demanda), 2),
                "produccion_solar_kwh": round(base_produccion, 2),
                "nivel_bateria_pct": round(bateria, 1),
                "periodo": "diario",
                "escenario": "demo",
                "origen_dato": "json_demo",
                "confiabilidad": 35.0,
            }
        )
    
    # Registros futuros hacia adelante (20 días más)
    for i in range(1, days_future + 1):
        fecha = (now + timedelta(days=i)).replace(hour=23, minute=59, second=0, microsecond=0)
        base_consumo = 380 + random.gauss(0, 30)
        if i % 7 in (5, 6):  # Fin de semana usa más energía
            base_consumo *= 1.15
        base_produccion = max(0, 60 + random.gauss(0, 15))
        demanda = 20 + random.gauss(0, 3)
        bateria = max(20, min(100, 75 + random.gauss(0, 15)))
        consumo_kwh = round(max(0, base_consumo), 2)
        rows.append(
            {
                "fecha": fecha.isoformat(),
                "consumo_kwh": consumo_kwh,
                "costo_cop": round(consumo_kwh * tarifa_kwh, 0),
                "demanda_pico_kw": round(max(0, demanda), 2),
                "produccion_solar_kwh": round(base_produccion, 2),
                "nivel_bateria_pct": round(bateria, 1),
                "periodo": "diario",
                "escenario": "demo",
                "origen_dato": "json_demo",
                "confiabilidad": 35.0,
            }
        )
    return rows


def build_radiacion(days_past: int = 60, days_future: int = 20) -> list[dict]:
    random.seed(7)
    now = datetime.now()
    rows: list[dict] = []
    
    # Registros históricos hacia atrás
    for i in range(days_past):
        fecha = (now - timedelta(days=i)).replace(hour=12, minute=0, second=0, microsecond=0)
        ghi = max(2.0, min(7.5, 5.8 + random.gauss(0, 0.7)))
        rows.append(
            {
                "fecha": fecha.isoformat(),
                "ghi": round(ghi, 2),
                "dni": round(ghi * 1.3 + random.gauss(0, 0.3), 2),
                "dhi": round(ghi * 0.4 + random.gauss(0, 0.2), 2),
                "temperatura": round(28 + random.gauss(0, 2), 1),
                "nubosidad": round(max(0, min(100, 25 + random.gauss(0, 15))), 1),
                "fuente": "synthetic",
                "escenario": "demo",
                "origen_dato": "json_demo",
                "confiabilidad": 35.0,
                "latitud": 10.8858,
                "longitud": -72.8481,
            }
        )
    
    # Registros futuros hacia adelante (20 días más)
    for i in range(1, days_future + 1):
        fecha = (now + timedelta(days=i)).replace(hour=12, minute=0, second=0, microsecond=0)
        ghi = max(2.0, min(7.5, 5.8 + random.gauss(0, 0.7)))
        rows.append(
            {
                "fecha": fecha.isoformat(),
                "ghi": round(ghi, 2),
                "dni": round(ghi * 1.3 + random.gauss(0, 0.3), 2),
                "dhi": round(ghi * 0.4 + random.gauss(0, 0.2), 2),
                "temperatura": round(28 + random.gauss(0, 2), 1),
                "nubosidad": round(max(0, min(100, 25 + random.gauss(0, 15))), 1),
                "fuente": "synthetic",
                "escenario": "demo",
                "origen_dato": "json_demo",
                "confiabilidad": 35.0,
                "latitud": 10.8858,
                "longitud": -72.8481,
            }
        )
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    consumo = build_consumo(days_past=60, days_future=20)
    radiacion = build_radiacion(days_past=60, days_future=20)

    (OUT_DIR / "consumo_demo.json").write_text(
        json.dumps(consumo, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "radiacion_demo.json").write_text(
        json.dumps(radiacion, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "predicciones_demo.json").write_text("[]", encoding="utf-8")
    (OUT_DIR / "alertas_demo.json").write_text("[]", encoding="utf-8")
    (OUT_DIR / "recomendaciones_demo.json").write_text("[]", encoding="utf-8")
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "files": ["consumo_demo.json", "radiacion_demo.json", "predicciones_demo.json", "alertas_demo.json", "recomendaciones_demo.json"],
        "records": {
            "consumo_demo": len(consumo),
            "radiacion_demo": len(radiacion),
        },
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    print(f"[OK] JSON demo generado en: {OUT_DIR}")
    print(f"  - Consumo: {len(consumo)} registros (60 días pasados + 20 futuros)")
    print(f"  - Radiación: {len(radiacion)} registros (60 días pasados + 20 futuros)")
    print("  - Predicciones, alertas y recomendaciones reiniciadas para regeneración dinámica.")


if __name__ == "__main__":
    main()

