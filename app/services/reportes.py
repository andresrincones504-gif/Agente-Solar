"""
Servicio de generación de reportes PDF y Excel.
"""
from io import BytesIO
from datetime import datetime, timedelta
from typing import List
from types import SimpleNamespace
from sqlalchemy.orm import Session
from sqlalchemy import desc

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

import xlsxwriter

from app.core.config import get_settings
from app.models.models import (
    ConsumoEnergetico,
    Recomendacion,
    Empresa,
    Alerta,
)
from app.services.demo_data import get_consumo_demo


class ReporteService:
    """Genera reportes PDF y Excel para una empresa."""

    @staticmethod
    def _get_data(
        db: Session,
        empresa: Empresa,
        days: int = 30,
        escenario: str = "real",
    ) -> dict:
        since = datetime.now() - timedelta(days=days)
        if escenario == "demo":
            demo_rows = get_consumo_demo(days=days)
            consumos = [
                SimpleNamespace(
                    fecha=datetime.fromisoformat(r["fecha"]),
                    consumo_kwh=r.get("consumo_kwh") or 0,
                    costo_cop=r.get("costo_cop"),
                    demanda_pico_kw=r.get("demanda_pico_kw"),
                    produccion_solar_kwh=r.get("produccion_solar_kwh") or 0,
                    nivel_bateria_pct=r.get("nivel_bateria_pct"),
                )
                for r in demo_rows
            ]
            recomendaciones = []
            alertas = []
            total_kwh = sum(c.consumo_kwh for c in consumos)
            produccion_total = sum(c.produccion_solar_kwh or 0 for c in consumos)
            costo_total = sum(c.costo_cop or (c.consumo_kwh * empresa.tarifa_kwh) for c in consumos)
            ahorro_solar = produccion_total * empresa.tarifa_kwh
            return {
                "consumos": consumos,
                "recomendaciones": recomendaciones,
                "alertas": alertas,
                "total_kwh": total_kwh,
                "produccion_total_kwh": produccion_total,
                "costo_total_cop": costo_total,
                "ahorro_solar_cop": ahorro_solar,
                "dias": days,
            }

        consumos = (
            db.query(ConsumoEnergetico)
            .filter(
                ConsumoEnergetico.empresa_id == empresa.id,
                ConsumoEnergetico.fecha >= since,
            )
            .order_by(ConsumoEnergetico.fecha)
            .all()
        )
        recomendaciones = (
            db.query(Recomendacion)
            .filter(Recomendacion.empresa_id == empresa.id)
            .order_by(desc(Recomendacion.created_at))
            .limit(10)
            .all()
        )
        alertas = (
            db.query(Alerta)
            .filter(
                Alerta.empresa_id == empresa.id,
                Alerta.created_at >= since,
            )
            .order_by(desc(Alerta.created_at))
            .all()
        )

        total_kwh = sum(c.consumo_kwh for c in consumos)
        produccion_total = sum(c.produccion_solar_kwh or 0 for c in consumos)
        costo_total = sum(c.costo_cop or (c.consumo_kwh * empresa.tarifa_kwh) for c in consumos)
        ahorro_solar = produccion_total * empresa.tarifa_kwh

        return {
            "consumos": consumos,
            "recomendaciones": recomendaciones,
            "alertas": alertas,
            "total_kwh": total_kwh,
            "produccion_total_kwh": produccion_total,
            "costo_total_cop": costo_total,
            "ahorro_solar_cop": ahorro_solar,
            "dias": days,
        }

    @classmethod
    def generar_pdf(
        cls,
        db: Session,
        empresa: Empresa,
        days: int = 30,
        escenario: str = "real",
    ) -> bytes:
        """Genera reporte PDF."""
        data = cls._get_data(db, empresa, days, escenario=escenario)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()

        # Estilos
        title_style = ParagraphStyle(
            "TitleCustom",
            parent=styles["Heading1"],
            fontSize=20,
            textColor=colors.HexColor("#1B4F72"),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#117A65"),
            alignment=TA_CENTER,
            spaceAfter=20,
        )
        h2 = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#1B4F72"),
            spaceBefore=12,
            spaceAfter=6,
        )

        story = []
        story.append(Paragraph("AGENTE SOLAR INTELIGENTE", title_style))
        story.append(Paragraph(f"Reporte Energético — {empresa.nombre}", subtitle_style))
        story.append(Paragraph(
            f"Período: últimos {days} días | "
            f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"{empresa.ciudad}, {empresa.departamento}" if empresa.ciudad and empresa.departamento else get_settings().LOCATION_NAME,
            styles["Normal"],
        ))
        story.append(Spacer(1, 0.5 * cm))

        # KPIs
        story.append(Paragraph("1. Resumen Ejecutivo", h2))
        kpi_data = [
            ["Indicador", "Valor"],
            ["Consumo total", f"{data['total_kwh']:.2f} kWh"],
            ["Producción solar", f"{data['produccion_total_kwh']:.2f} kWh"],
            ["Costo total energía", f"${data['costo_total_cop']:,.0f} COP"],
            ["Ahorro estimado solar", f"${data['ahorro_solar_cop']:,.0f} COP"],
            ["Tarifa actual", f"${empresa.tarifa_kwh:,.0f} COP/kWh"],
            ["Capacidad paneles", f"{empresa.capacidad_paneles_kw} kW"],
            ["Capacidad batería", f"{empresa.capacidad_bateria_kwh} kWh"],
        ]
        t = Table(kpi_data, colWidths=[8 * cm, 8 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4F72")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

        # Recomendaciones IA
        story.append(Paragraph("2. Recomendaciones del Agente IA", h2))
        if data["recomendaciones"]:
            for i, r in enumerate(data["recomendaciones"], 1):
                impacto = f"${r.impacto_estimado_cop:,.0f} COP" if r.impacto_estimado_cop else "N/A"
                p = Paragraph(
                    f"<b>{i}. [{r.tipo or 'ahorro'}]</b> {r.texto}<br/>"
                    f"<i>Impacto estimado: {impacto} | Confianza: {r.confianza_pct:.0f}%</i>",
                    styles["Normal"],
                )
                story.append(p)
                story.append(Spacer(1, 0.3 * cm))
        else:
            story.append(Paragraph("No hay recomendaciones generadas aún.", styles["Normal"]))

        story.append(Spacer(1, 0.5 * cm))

        # Alertas
        story.append(Paragraph("3. Alertas Recientes", h2))
        if data["alertas"]:
            alertas_data = [["Fecha", "Tipo", "Severidad", "Mensaje"]]
            for a in data["alertas"][:15]:
                alertas_data.append([
                    a.created_at.strftime("%Y-%m-%d %H:%M"),
                    a.tipo,
                    a.severidad,
                    a.mensaje[:80] + ("..." if len(a.mensaje) > 80 else ""),
                ])
            ta = Table(alertas_data, colWidths=[3.2 * cm, 3 * cm, 2.5 * cm, 7.3 * cm])
            ta.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#117A65")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E8F8F5")]),
            ]))
            story.append(ta)
        else:
            story.append(Paragraph("Sin alertas en el período.", styles["Normal"]))

        story.append(PageBreak())

        # Tabla detallada
        story.append(Paragraph("4. Detalle de Consumo", h2))
        if data["consumos"]:
            tabla = [["Fecha", "Consumo (kWh)", "Prod. Solar (kWh)", "Costo (COP)"]]
            for c in data["consumos"][:50]:
                tabla.append([
                    c.fecha.strftime("%Y-%m-%d %H:%M"),
                    f"{c.consumo_kwh:.2f}",
                    f"{c.produccion_solar_kwh or 0:.2f}",
                    f"${c.costo_cop or (c.consumo_kwh * empresa.tarifa_kwh):,.0f}",
                ])
            tc = Table(tabla, colWidths=[4 * cm, 4 * cm, 4 * cm, 4 * cm])
            tc.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4F72")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
            ]))
            story.append(tc)

        # Footer
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(
            "<i>Reporte generado automáticamente por Agente Solar Inteligente — "
            f"Dashboard Solar con IA para Ahorro Energético en {get_settings().LOCATION_NAME}</i>",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER),
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def generar_excel(
        cls,
        db: Session,
        empresa: Empresa,
        days: int = 30,
        escenario: str = "real",
    ) -> bytes:
        """Genera reporte Excel."""
        data = cls._get_data(db, empresa, days, escenario=escenario)
        buffer = BytesIO()
        wb = xlsxwriter.Workbook(buffer, {"in_memory": True})

        # Formatos
        title_fmt = wb.add_format({
            "bold": True, "font_size": 16, "font_color": "#1B4F72",
            "align": "center", "valign": "vcenter",
        })
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#1B4F72", "font_color": "white",
            "border": 1, "align": "center",
        })
        money_fmt = wb.add_format({"num_format": "$#,##0 COP"})
        num_fmt = wb.add_format({"num_format": "#,##0.00"})
        date_fmt = wb.add_format({"num_format": "yyyy-mm-dd hh:mm"})

        # Hoja 1: Resumen
        ws = wb.add_worksheet("Resumen")
        ws.set_column("A:A", 35)
        ws.set_column("B:B", 25)
        ws.merge_range("A1:B1", "AGENTE SOLAR INTELIGENTE", title_fmt)
        ws.merge_range("A2:B2", f"Reporte de {empresa.nombre}", title_fmt)
        ws.write("A4", "Período", header_fmt)
        ws.write("B4", f"Últimos {days} días")
        ws.write("A5", "Generado", header_fmt)
        ws.write("B5", datetime.now().strftime("%Y-%m-%d %H:%M"))

        ws.write("A7", "INDICADOR", header_fmt)
        ws.write("B7", "VALOR", header_fmt)
        kpis = [
            ("Consumo total (kWh)", data["total_kwh"], num_fmt),
            ("Producción solar (kWh)", data["produccion_total_kwh"], num_fmt),
            ("Costo total (COP)", data["costo_total_cop"], money_fmt),
            ("Ahorro estimado solar (COP)", data["ahorro_solar_cop"], money_fmt),
            ("Tarifa COP/kWh", empresa.tarifa_kwh, money_fmt),
            ("Capacidad paneles (kW)", empresa.capacidad_paneles_kw, num_fmt),
            ("Capacidad batería (kWh)", empresa.capacidad_bateria_kwh, num_fmt),
        ]
        for i, (k, v, f) in enumerate(kpis, start=8):
            ws.write(f"A{i}", k)
            ws.write(f"B{i}", v, f)

        # Hoja 2: Consumo
        ws2 = wb.add_worksheet("Consumo")
        ws2.set_column("A:A", 20)
        ws2.set_column("B:F", 18)
        headers = ["Fecha", "Consumo kWh", "Costo COP", "Demanda pico kW",
                   "Producción solar kWh", "Batería %"]
        for col, h in enumerate(headers):
            ws2.write(0, col, h, header_fmt)
        for row, c in enumerate(data["consumos"], start=1):
            ws2.write_datetime(row, 0, c.fecha, date_fmt)
            ws2.write(row, 1, c.consumo_kwh, num_fmt)
            ws2.write(row, 2, c.costo_cop or (c.consumo_kwh * empresa.tarifa_kwh), money_fmt)
            ws2.write(row, 3, c.demanda_pico_kw or 0, num_fmt)
            ws2.write(row, 4, c.produccion_solar_kwh or 0, num_fmt)
            ws2.write(row, 5, c.nivel_bateria_pct or 0, num_fmt)

        # Hoja 3: Recomendaciones IA
        ws3 = wb.add_worksheet("Recomendaciones IA")
        ws3.set_column("A:A", 18)
        ws3.set_column("B:B", 15)
        ws3.set_column("C:C", 60)
        ws3.set_column("D:E", 18)
        ws3_headers = ["Fecha", "Tipo", "Recomendación", "Impacto COP", "Confianza %"]
        for col, h in enumerate(ws3_headers):
            ws3.write(0, col, h, header_fmt)
        for row, r in enumerate(data["recomendaciones"], start=1):
            ws3.write_datetime(row, 0, r.created_at, date_fmt)
            ws3.write(row, 1, r.tipo or "ahorro")
            ws3.write(row, 2, r.texto)
            ws3.write(row, 3, r.impacto_estimado_cop or 0, money_fmt)
            ws3.write(row, 4, r.confianza_pct or 0, num_fmt)

        # Hoja 4: Alertas
        ws4 = wb.add_worksheet("Alertas")
        ws4.set_column("A:A", 20)
        ws4.set_column("B:C", 15)
        ws4.set_column("D:D", 70)
        ws4_headers = ["Fecha", "Tipo", "Severidad", "Mensaje"]
        for col, h in enumerate(ws4_headers):
            ws4.write(0, col, h, header_fmt)
        for row, a in enumerate(data["alertas"], start=1):
            ws4.write_datetime(row, 0, a.created_at, date_fmt)
            ws4.write(row, 1, a.tipo)
            ws4.write(row, 2, a.severidad)
            ws4.write(row, 3, a.mensaje)

        wb.close()
        buffer.seek(0)
        return buffer.getvalue()


reporte_service = ReporteService()
