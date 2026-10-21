"""
Agente de Alertas.

Genera las alertas generales del municipio (clima y riesgo para el servicio de energía) y las guarda
para cada empresa, de modo que cada usuario pueda marcarlas como revisadas. Las alertas no dependen
de los aparatos del usuario: los avisos sobre sus aparatos se muestran en Mis aparatos.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import Alerta, Empresa
from app.services.alertas_fonseca import TIPOS_GENERALES, obtener_alertas_generales


class AgenteAlertas:
    """Mantiene al día las alertas generales de cada empresa."""

    async def evaluar(self, db: Session, empresa: Empresa, refrescar: bool = False) -> List[Alerta]:
        hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Las alertas de hoy aún no leídas se recalculan con el pronóstico más reciente
        db.query(Alerta).filter(
            Alerta.empresa_id == empresa.id,
            Alerta.leida == False,  # noqa: E712
            Alerta.created_at >= hoy_inicio,
            Alerta.tipo.in_(TIPOS_GENERALES),
        ).delete(synchronize_session=False)
        db.commit()

        creadas = []
        for alerta in await obtener_alertas_generales(refrescar):
            a = self._crear_si_no_existe_hoy(db, empresa.id, **alerta)
            if a:
                creadas.append(a)
        return creadas

    def _crear_si_no_existe_hoy(
        self,
        db: Session,
        empresa_id: int,
        tipo: str,
        mensaje: str,
        severidad: str,
        desde: Optional[datetime] = None,
    ) -> Optional[Alerta]:
        """Una alerta por tipo y por día: si el usuario ya la revisó hoy, no se vuelve a crear."""
        hoy_inicio = desde or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        existente = (
            db.query(Alerta)
            .filter(
                Alerta.empresa_id == empresa_id,
                Alerta.tipo == tipo,
                Alerta.created_at >= hoy_inicio,
            )
            .first()
        )
        if existente:
            return None

        alerta = Alerta(empresa_id=empresa_id, tipo=tipo, mensaje=mensaje, severidad=severidad)
        db.add(alerta)
        db.commit()
        db.refresh(alerta)
        return alerta


agente_alertas = AgenteAlertas()
