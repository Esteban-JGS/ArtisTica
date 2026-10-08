"""Esquemas de consultas y mensajes. Las validaciones de forma dan 422.

A diferencia del perfil y los comentarios, el texto del chat no rechaza
telefonos, WhatsApp ni SINPE: el servicio lo guarda con un aviso.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from src.domain.consultas import AVISO_PAGO_FUERA, RolEnConsulta
from src.domain.enums import EstadoConsulta
from src.schemas.catalogo import Monto
from src.schemas.social import PerfilResumido
from src.services.consultas import ConsultaDetalle, MensajeDetalle
from src.services.paginacion import codificar_cursor

Texto = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


# Entrada


class NuevaConsulta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artista_id: uuid.UUID
    # Sobre un servicio, sobre una obra, o ninguno: en general
    servicio_id: uuid.UUID | None = None
    obra_id: uuid.UUID | None = None
    texto: Texto
    presupuesto: Monto | None = None
    fecha_deseada: date | None = None

    @model_validator(mode="after")
    def _una_referencia(self) -> Self:
        if self.servicio_id is not None and self.obra_id is not None:
            raise ValueError("La consulta es sobre un servicio o sobre una obra")
        return self


class NuevoMensaje(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: Texto


# Salida


class MensajeRespuesta(BaseModel):
    id: uuid.UUID
    # Para pedir los posteriores a este mensaje
    cursor: str
    es_mio: bool
    texto: str
    created_at: datetime
    aviso_contacto: bool
    # El texto para mostrar a los dos lados, o nulo
    aviso: str | None

    @classmethod
    def desde(cls, detalle: MensajeDetalle) -> Self:
        mensaje = detalle.mensaje
        return cls(
            id=mensaje.id,
            cursor=codificar_cursor(mensaje.created_at, mensaje.id),
            es_mio=detalle.es_mio,
            texto=mensaje.texto,
            created_at=mensaje.created_at,
            aviso_contacto=mensaje.aviso_contacto,
            aviso=AVISO_PAGO_FUERA if mensaje.aviso_contacto else None,
        )


class ConsultaRespuesta(BaseModel):
    id: uuid.UUID
    estado: EstadoConsulta
    soy: RolEnConsulta
    cliente: PerfilResumido
    artista: PerfilResumido
    servicio_id: uuid.UUID | None
    obra_id: uuid.UUID | None
    presupuesto: Decimal | None
    fecha_deseada: date | None
    created_at: datetime
    ultimo_mensaje_at: datetime
    ultimo_mensaje: MensajeRespuesta | None
    # Mensajes de la otra parte posteriores a la ultima lectura
    no_leidos: int

    @classmethod
    def desde(cls, detalle: ConsultaDetalle) -> Self:
        consulta = detalle.consulta
        return cls(
            id=consulta.id,
            estado=consulta.estado,
            soy=detalle.soy,
            cliente=PerfilResumido.desde(detalle.cliente),
            artista=PerfilResumido.desde(detalle.artista),
            servicio_id=consulta.servicio_id,
            obra_id=consulta.obra_id,
            presupuesto=consulta.presupuesto,
            fecha_deseada=consulta.fecha_deseada,
            created_at=consulta.created_at,
            ultimo_mensaje_at=consulta.ultimo_mensaje_at,
            ultimo_mensaje=None
            if detalle.ultimo_mensaje is None
            else MensajeRespuesta.desde(detalle.ultimo_mensaje),
            no_leidos=detalle.no_leidos,
        )


class ResumenNoLeidos(BaseModel):
    # Consultas con algo sin leer
    consultas: int
    mensajes: int
