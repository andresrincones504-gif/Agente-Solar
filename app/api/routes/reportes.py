from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import datetime

from app.db.session import get_db
from app.models.models import Empresa, User, UserRole
from app.api.deps.auth import get_current_user
from app.services.reportes import reporte_service

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _check_acceso(current_user: User, empresa_id: int):
    if (
        current_user.role == UserRole.EMPRESA
        and current_user.empresa_id != empresa_id
    ):
        raise HTTPException(status_code=403, detail="Sin permisos")


@router.get("/pdf/{empresa_id}")
def descargar_pdf(
    empresa_id: int,
    days: int = Query(30, ge=1, le=365),
    escenario: str = Query("real", pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera y descarga reporte PDF de la empresa."""
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    pdf_bytes = reporte_service.generar_pdf(db, empresa, days, escenario=escenario)
    filename = f"reporte_{empresa.nombre.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/excel/{empresa_id}")
def descargar_excel(
    empresa_id: int,
    days: int = Query(30, ge=1, le=365),
    escenario: str = Query("real", pattern="^(demo|real)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera y descarga reporte Excel de la empresa."""
    _check_acceso(current_user, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    xlsx_bytes = reporte_service.generar_excel(db, empresa, days, escenario=escenario)
    filename = f"reporte_{empresa.nombre.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
