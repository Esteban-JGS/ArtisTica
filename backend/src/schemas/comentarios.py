"""Esquemas de comentarios. Las validaciones de forma dan 422.

Un comentario es texto publico: rechaza telefonos y WhatsApp igual que el
perfil, porque el contacto va por la plataforma.
"""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from src.domain import perfiles as dominio_perfiles
from src.schemas.social import PerfilResumido
from src.services.comentarios import ComentarioDetalle, RespuestaDetalle


def _sin_contacto(texto: str) -> str:
    """El mismo rechazo que en el perfil: el contacto va por la plataforma."""
    if dominio_perfiles.contiene_contacto_prohibido(texto):
        raise ValueError(
            "No se permiten telefonos ni WhatsApp: el contacto va por la plataforma"
        )
    return texto


Texto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    AfterValidator(_sin_contacto),
]


# Entrada


class NuevoComentario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: Texto
    # Si responde a otro comentario. Responder a una respuesta cuelga del primer nivel
    respuesta_a: uuid.UUID | None = None


# Salida


def _campos(detalle: RespuestaDetalle) -> dict:
    comentario = detalle.comentario
    return {
        "id": comentario.id,
        "autor": PerfilResumido.desde(detalle.autor),
        "texto": comentario.texto,
        "created_at": comentario.created_at,
        "me_gusta_total": detalle.me_gusta_total,
        "mi_me_gusta": detalle.mi_me_gusta,
    }


class RespuestaComentario(BaseModel):
    id: uuid.UUID
    autor: PerfilResumido
    texto: str
    created_at: datetime
    # Se muestran, no ordenan
    me_gusta_total: int
    # Nulo sin token
    mi_me_gusta: bool | None

    @classmethod
    def desde(cls, detalle: RespuestaDetalle) -> Self:
        return cls(**_campos(detalle))


class ComentarioRespuesta(RespuestaComentario):
    respuestas_total: int
    # Las primeras, del mas viejo al mas nuevo; el resto se pagina aparte
    respuestas: list[RespuestaComentario]

    @classmethod
    def desde(cls, detalle: ComentarioDetalle) -> Self:
        return cls(
            **_campos(detalle),
            respuestas_total=detalle.respuestas_total,
            respuestas=[RespuestaComentario.desde(r) for r in detalle.respuestas],
        )
