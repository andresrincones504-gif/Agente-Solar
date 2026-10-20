"""
Script de inicializacion: crea empresa y usuarios demo.
Opcionalmente puede persistir series sinteticas en BD para compatibilidad legacy.
Ejecutar: python scripts/seed.py
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.migrations import ensure_schema_compatibility
from app.db.session import Base, SessionLocal, engine
from app.models.models import (
    AparatoUsuario,
    CatalogoAparato,
    ConfiguracionAlerta,
    ConsumoEnergetico,
    Empresa,
    RadiacionSolar,
    User,
    UserRole,
)
from app.services.catalogo_aparatos import sincronizar_catalogo


def asegurar_config_alertas(db: Session, empresa: Empresa) -> None:
    """Una sola configuración de alertas por empresa: la crea si falta y quita duplicados de seeds anteriores."""
    configs = (
        db.query(ConfiguracionAlerta)
        .filter(ConfiguracionAlerta.empresa_id == empresa.id)
        .order_by(ConfiguracionAlerta.id)
        .all()
    )
    if not configs:
        db.add(ConfiguracionAlerta(
            empresa_id=empresa.id,
            umbral_consumo_diario_kwh=400.0,
            umbral_bateria_baja_pct=20.0,
            umbral_radiacion_baja=2.5,
        ))
        print("[OK] Configuración de alertas creada")
    for duplicada in configs[1:]:
        db.delete(duplicada)
    if len(configs) > 1:
        print(f"[OK] Configuraciones de alertas duplicadas eliminadas: {len(configs) - 1}")
    db.commit()


def cargar_aparatos_demo(db: Session, empresa: Empresa) -> None:
    """Inventario de ejemplo del hotel demo. Solo agrega los aparatos que la empresa aún no tiene."""
    archivo = Path(__file__).parent / "demo_data" / "aparatos_demo.json"
    if not archivo.exists():
        print(f"[WARN] Archivo no encontrado: {archivo}")
        return
    sincronizar_catalogo(db)
    catalogo = {c.codigo: c for c in db.query(CatalogoAparato).filter(CatalogoAparato.activo == True).all()}  # noqa: E712
    existentes = {a.catalogo_id for a in db.query(AparatoUsuario).filter(AparatoUsuario.empresa_id == empresa.id).all()}
    agregados = 0
    for item in json.loads(archivo.read_text(encoding="utf-8"))["aparatos"]:
        c = catalogo.get(item["codigo"])
        if c is None or c.id in existentes:
            continue
        db.add(AparatoUsuario(empresa_id=empresa.id, catalogo_id=c.id, nombre=c.nombre, cantidad=item.get("cantidad", 1)))
        agregados += 1
    db.commit()
    print(f"[OK] Aparatos demo agregados: {agregados}" if agregados else "[SKIP] El hotel demo ya tiene su inventario")


def seed() -> None:
    print("[INFO] Creando tablas...")
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(engine)

    db: Session = SessionLocal()
    persistir_sinteticos = os.getenv("SEED_PERSIST_SYNTHETIC", "0").strip().lower() in ("1", "true", "yes")

    try:
        empresa = db.query(Empresa).filter(Empresa.nombre.in_(["Hotel Solar Fonseca", "Hotel Solar Riohacha"])).first()
        if not empresa:
            empresa = Empresa(
                nombre="Hotel Solar Fonseca",
                tipo="hotel",
                tipo_entidad="empresa",
                direccion="Calle 13 #18-40, Fonseca",
                ciudad="Fonseca",
                departamento="La Guajira",
                tarifa_kwh=943.0,
                capacidad_paneles_kw=15.0,
                capacidad_bateria_kwh=30.0,
                escenario_default="demo",
            )
            db.add(empresa)
            db.commit()
            db.refresh(empresa)
            print(f"[OK] Empresa demo creada: {empresa.nombre} (ID {empresa.id})")
        else:
            if empresa.ciudad != "Fonseca" or empresa.nombre == "Hotel Solar Riohacha":
                empresa.nombre = "Hotel Solar Fonseca"
                empresa.ciudad = "Fonseca"
                empresa.direccion = "Calle 13 #18-40, Fonseca"
                db.commit()
                db.refresh(empresa)
                print(f"[OK] Empresa demo actualizada a: {empresa.nombre} (Ciudad: {empresa.ciudad})")

        asegurar_config_alertas(db, empresa)
        cargar_aparatos_demo(db, empresa)

        usuarios_demo = [
            {
                "email": "admin@agentesolar.co",
                "password": "admin123",
                "full_name": "Administrador del Sistema",
                "role": UserRole.ADMIN,
                "empresa_id": None,
                "escenario_usuario": "demo",
            },
            {
                "email": "hotel@agentesolar.co",
                "password": "hotel123",
                "full_name": "Gerente Hotel Solar",
                "role": UserRole.EMPRESA,
                "empresa_id": empresa.id,
                "escenario_usuario": "demo",
            },
            {
                "email": "analista@agentesolar.co",
                "password": "analista123",
                "full_name": "Analista Energetico",
                "role": UserRole.ANALISTA,
                "empresa_id": None,
                "escenario_usuario": "demo",
            },
        ]

        for u_data in usuarios_demo:
            existing = db.query(User).filter(User.email == u_data["email"]).first()
            if not existing:
                u = User(
                    email=u_data["email"],
                    hashed_password=get_password_hash(u_data["password"]),
                    full_name=u_data["full_name"],
                    role=u_data["role"],
                    escenario_usuario=u_data["escenario_usuario"],
                    empresa_id=u_data["empresa_id"],
                )
                db.add(u)
                db.commit()
                print(f"[OK] Usuario creado: {u.email} ({u.role.value}, {u.escenario_usuario})")
            else:
                print(f"[SKIP] Usuario ya existe: {u_data['email']}")

        if persistir_sinteticos:
            # Eliminar registros sinteticos previos para asegurar sincronizacion con fechas actuales
            eliminados_c = db.query(ConsumoEnergetico).filter(
                ConsumoEnergetico.empresa_id == empresa.id,
                ConsumoEnergetico.origen_dato == "json_demo"
            ).delete()
            db.commit()
            if eliminados_c > 0:
                print(f"[INFO] Registros anteriores de consumo sintético eliminados: {eliminados_c}")

            print("[INFO] Cargando datos sinteticos de consumo desde JSON...")
            consumo_file = Path(__file__).parent / "demo_data" / "consumo_demo.json"
            if consumo_file.exists():
                consumo_data = json.loads(consumo_file.read_text(encoding="utf-8"))
                for row in consumo_data:
                    consumo = ConsumoEnergetico(
                        empresa_id=empresa.id,
                        fecha=datetime.fromisoformat(row["fecha"]),
                        consumo_kwh=row["consumo_kwh"],
                        costo_cop=row["costo_cop"],
                        demanda_pico_kw=row["demanda_pico_kw"],
                        produccion_solar_kwh=row["produccion_solar_kwh"],
                        nivel_bateria_pct=row["nivel_bateria_pct"],
                        periodo=row.get("periodo", "diario"),
                        escenario=row.get("escenario", "demo"),
                        origen_dato="json_demo",
                        confiabilidad=row.get("confiabilidad", 35.0),
                    )
                    db.add(consumo)
                db.commit()
                print(f"[OK] {len(consumo_data)} registros de consumo cargados")
            else:
                print(f"[WARN] Archivo no encontrado: {consumo_file}")

            eliminados_r = db.query(RadiacionSolar).filter(
                RadiacionSolar.origen_dato == "json_demo"
            ).delete()
            db.commit()
            if eliminados_r > 0:
                print(f"[INFO] Registros anteriores de radiación sintética eliminados: {eliminados_r}")

            print("[INFO] Cargando datos sinteticos de radiacion solar desde JSON...")
            radiacion_file = Path(__file__).parent / "demo_data" / "radiacion_demo.json"
            if radiacion_file.exists():
                radiacion_data = json.loads(radiacion_file.read_text(encoding="utf-8"))
                for row in radiacion_data:
                    rad = RadiacionSolar(
                        fecha=datetime.fromisoformat(row["fecha"]),
                        ghi=row["ghi"],
                        dni=row["dni"],
                        dhi=row["dhi"],
                        temperatura=row["temperatura"],
                        nubosidad=row["nubosidad"],
                        fuente=row.get("fuente", "synthetic"),
                        escenario=row.get("escenario", "demo"),
                        origen_dato="json_demo",
                        confiabilidad=row.get("confiabilidad", 35.0),
                        latitud=row.get("latitud", 10.8858),
                        longitud=row.get("longitud", -72.8481),
                    )
                    db.add(rad)
                db.commit()
                print(f"[OK] {len(radiacion_data)} registros de radiacion cargados")
            else:
                print(f"[WARN] Archivo no encontrado: {radiacion_file}")
        else:
            print("[INFO] Seed sin series sinteticas en BD (SEED_PERSIST_SYNTHETIC=0).")

        print("\n" + "=" * 60)
        print("SEED COMPLETO")
        print("=" * 60)
        print("Credenciales demo:")
        print("  Admin:    admin@agentesolar.co    / admin123")
        print("  Empresa:  hotel@agentesolar.co    / hotel123")
        print("  Analista: analista@agentesolar.co / analista123")
        print("=" * 60)

    except Exception as exc:
        print(f"[ERROR] {exc}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

