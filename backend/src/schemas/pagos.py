import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel

from src.models import EventoPasarela


class WebhookRespuesta(BaseModel):
    estado: Literal["recibido", "repetido"]


class EventoPasarelaRespuesta(BaseModel):
    """Para moderacion. Sin el payload, sin el id externo y sin la referencia
    de la pasarela."""

    id: uuid.UUID
    proveedor: str
    tipo: str
    intentos: int
    error: str | None
    procesado_en: datetime | None
    created_at: datetime

    @classmethod
    def desde(cls, evento: EventoPasarela) -> Self:
        return cls(
            id=evento.id,
            proveedor=evento.proveedor,
            tipo=evento.tipo,
            intentos=evento.intentos,
            error=evento.error,
            procesado_en=evento.procesado_en,
            created_at=evento.created_at,
        )
