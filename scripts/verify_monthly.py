"""
Script de verificación: valida el registro e interpolación diaria de facturas mensuales.
Ejecutar: docker compose exec api python scripts/verify_monthly.py
"""
import os
import sys
import calendar
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.models import ConsumoEnergetico, Empresa, Alerta


def verify():
    print("[INFO] Iniciando verificación del flujo de Factura Mensual...")
    db: Session = SessionLocal()

    try:
        # 1. Obtener una empresa de prueba (o crearla)
        empresa = db.query(Empresa).filter(Empresa.nombre.in_(["Hotel Solar Fonseca", "Hotel Solar Riohacha"])).first()
        if not empresa:
            print("[ERROR] No se encontró la empresa demo. Por favor corre el seed primero.")
            return

        empresa_id = empresa.id
        anio = 2026
        mes = 5  # Mayo (31 días)
        consumo_total = 310.0  # 310 kWh / 31 días = 10 kWh diarios
        costo_energia = 292330.0  # $292,330 COP / 31 días = $9,430 COP diarios

        print(f"[INFO] Insertando factura mensual ficticia para Mayo {anio}:")
        print(f"       Consumo total: {consumo_total} kWh")
        print(f"       Costo de energía: {costo_energia} COP")

        # 2. Simular la lógica del endpoint POST /monthly
        _, num_dias = calendar.monthrange(anio, mes)
        consumo_diario = consumo_total / num_dias
        costo_diario = costo_energia / num_dias

        # Eliminar cualquier registro real preexistente para evitar duplicación
        inicio_mes = datetime(anio, mes, 1, 0, 0, 0)
        fin_mes = datetime(anio, mes, num_dias, 23, 59, 59)
        
        deleted = db.query(ConsumoEnergetico).filter(
            ConsumoEnergetico.empresa_id == empresa_id,
            ConsumoEnergetico.fecha >= inicio_mes,
            ConsumoEnergetico.fecha <= fin_mes,
            ConsumoEnergetico.escenario == "real",
        ).delete(synchronize_session=False)
        print(f"[INFO] Registros reales previos eliminados de Mayo: {deleted}")

        # Insertar registros diarios
        for dia in range(1, num_dias + 1):
            fecha_registro = datetime(anio, mes, dia, 12, 0, 0)
            rec = ConsumoEnergetico(
                empresa_id=empresa_id,
                fecha=fecha_registro,
                consumo_kwh=consumo_diario,
                costo_cop=costo_diario,
                demanda_pico_kw=None,
                produccion_solar_kwh=0.0,
                nivel_bateria_pct=None,
                periodo="diario",
                escenario="real",
                origen_dato="real_monthly_bill",
                confiabilidad=90.0,
            )
            db.add(rec)

        # Simular alerta preventiva
        db.query(Alerta).filter(
            Alerta.empresa_id == empresa_id,
            Alerta.tipo == "recordatorio_pago",
            Alerta.mensaje.like(f"%{mes}/{anio}%")
        ).delete(synchronize_session=False)

        fecha_pago = datetime(2026, 5, 21)
        fecha_suspension = datetime(2026, 5, 22)
        fecha_pago_str = fecha_pago.strftime("%d/%m/%Y")
        fecha_susp_str = fecha_suspension.strftime("%d/%m/%Y")
        mensaje_alerta = (
            f"📌 Recordatorio de Pago: Tu recibo de energía de {mes}/{anio} tiene como fecha oportuna de "
            f"pago el {fecha_pago_str}. Evita la suspensión del servicio programada a partir del {fecha_susp_str}."
        )

        alerta_rec = Alerta(
            empresa_id=empresa_id,
            tipo="recordatorio_pago",
            mensaje=mensaje_alerta,
            severidad="alta",
            leida=False,
        )
        db.add(alerta_rec)

        db.commit()
        print(f"[OK] Se han insertado {num_dias} registros diarios interpolados.")
        print(f"[OK] Se ha insertado la alerta preventiva de pago.")

        # 3. Consultar los registros insertados para verificar
        registros = db.query(ConsumoEnergetico).filter(
            ConsumoEnergetico.empresa_id == empresa_id,
            ConsumoEnergetico.fecha >= inicio_mes,
            ConsumoEnergetico.fecha <= fin_mes,
            ConsumoEnergetico.escenario == "real",
        ).all()

        assert len(registros) == 31, f"Error: Se esperaban 31 registros, pero se encontraron {len(registros)}"
        
        # Verificar que el consumo y costo diario sean correctos
        for r in registros:
            assert abs(r.consumo_kwh - 10.0) < 1e-5, f"Error: Consumo incorrecto {r.consumo_kwh}"
            assert abs(r.costo_cop - 9430.0) < 1e-5, f"Error: Costo incorrecto {r.costo_cop}"
            assert r.escenario == "real", f"Error: Escenario incorrecto {r.escenario}"
            assert r.origen_dato == "real_monthly_bill", f"Error: Origen de datos incorrecto {r.origen_dato}"

        # Verificar alerta
        alerta_guardada = db.query(Alerta).filter(
            Alerta.empresa_id == empresa_id,
            Alerta.tipo == "recordatorio_pago",
            Alerta.mensaje.like(f"%{mes}/{anio}%")
        ).first()
        assert alerta_guardada is not None, "Error: No se creó la alerta preventiva"
        
        print("\n" + "=" * 60)
        print("✅ VERIFICACIÓN DE FACTURA MENSUAL EXITOSA")
        print("=" * 60)
        print(f"  Total días registrados: {len(registros)}")
        print(f"  Consumo diario calculado: {registros[0].consumo_kwh} kWh/día (Esperado: 10.0)")
        print(f"  Costo diario calculado: ${registros[0].costo_cop:,.0f} COP/día (Esperado: 9,430)")
        print(f"  Alerta preventiva: '{alerta_guardada.mensaje}'")
        print("=" * 60)

    except AssertionError as exc:
        print(f"[FAIL] Error en la aserción de datos: {exc}")
    except Exception as exc:
        print(f"[FAIL] Error inesperado en verificación: {exc}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    verify()
