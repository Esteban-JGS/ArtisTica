"""Esquemas de publicaciones y del feed. Las validaciones de forma dan 422.

El texto rechaza telefonos y WhatsApp igual que el perfil: el contacto va por la
plataforma. Una publicacion no vende: si muestra una obra, solo dice si esta
disponible, y lo demas vive en la ficha de la obra.
"""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from src.core.config import settings
from src.domain import perfiles as dominio_perfiles
from src.domain.enums import EstadoObra
from src.models import Obra, Profile
from src.schemas.catalogo import MedioDeObra
from src.services.publicaciones import PublicacionDetalle
from src.storage import Almacenamiento


def _sin_contacto(texto: str) -> str:
    """El mismo rechazo que en el perfil: el contacto va por la plataforma."""
    if dominio_perfiles.contiene_contacto_prohibido(texto):
        raise ValueError(
            "No se permiten telefonos ni WhatsApp: el contacto va por la plataforma"
        )
    return texto


def _dentro_del_maximo(medios: list[uuid.UUID]) -> list[uuid.UUID]:
    maximo = settings.MEDIOS_POR_PUBLICACION_MAXIMO
    if len(medios) > maximo:
        raise ValueError(f"Una publicacion admite {maximo} imagenes como maximo")
    if len(set(medios)) != len(medios):
        raise ValueError("Hay imagenes repetidas")
    return medios


Texto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    AfterValidator(_sin_contacto),
]
Medios = Annotated[list[uuid.UUID], AfterValidator(_dentro_del_maximo)]


# Entrada


class NuevaPublicacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: Texto
    medios: Medios = Field(default_factory=list)
    # Una obra propia de la galeria, si la publicacion la muestra
    obra_id: uuid.UUID | None = None


class EdicionPublicacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: Texto


# Salida


class ArtistaDePublicacion(BaseModel):
    handle: str
    nombre: str
    verificado: bool

    @classmethod
    def desde(cls, perfil: Profile) -> Self:
        return cls(
            handle=perfil.handle, nombre=perfil.nombre, verificado=perfil.is_verified
        )


class ObraDePublicacion(BaseModel):
    """Solo la etiqueta: lo demas de la obra vive en su ficha."""

    id: uuid.UUID
    titulo: str
    disponible: bool

    @classmethod
    def desde(cls, obra: Obra) -> Self:
        return cls(
            id=obra.id,
            titulo=obra.titulo,
            disponible=obra.estado == EstadoObra.DISPONIBLE,
        )


class PublicacionRespuesta(BaseModel):
    id: uuid.UUID
    artista: ArtistaDePublicacion
    texto: str
    medios: list[MedioDeObra]
    obra: ObraDePublicacion | None
    created_at: datetime
    # Verdadero o falso en Explorar; nulo en los demas listados
    nuevo_talento: bool | None

    @classmethod
    def desde(cls, detalle: PublicacionDetalle, almacenamiento: Almacenamiento) -> Self:
        publicacion = detalle.publicacion
        return cls(
            id=publicacion.id,
            artista=ArtistaDePublicacion.desde(detalle.artista),
            texto=publicacion.texto,
            medios=[MedioDeObra.desde(m, almacenamiento) for m in detalle.medios],
            obra=ObraDePublicacion.desde(detalle.obra) if detalle.obra else None,
            created_at=publicacion.created_at,
            nuevo_talento=detalle.nuevo_talento,
        )
