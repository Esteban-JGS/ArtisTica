"""Esquemas de medios. Ninguna respuesta lleva la clave de servicio.

Los limites se leen de `settings` en cada solicitud, no al importar.
"""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from src.core.config import settings
from src.domain.medios import TIPOS_PERMITIDOS
from src.models.medios import EstadoMedia, MediaAsset
from src.storage import Almacenamiento, SubidaFirmada


def _tipo_permitido(content_type: str) -> str:
    normalizado = content_type.strip().lower()
    if normalizado not in TIPOS_PERMITIDOS:
        raise ValueError(
            f"Tipo no permitido. Opciones: {', '.join(sorted(TIPOS_PERMITIDOS))}"
        )
    return normalizado


def _dentro_del_maximo(tamano: int) -> int:
    if tamano > settings.MEDIO_TAMANO_MAXIMO_BYTES:
        raise ValueError(
            f"El archivo supera el maximo de {settings.MEDIO_TAMANO_MAXIMO_BYTES} bytes"
        )
    return tamano


class SolicitudSubida(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: Annotated[str, AfterValidator(_tipo_permitido)]
    tamano_bytes: Annotated[
        int, Field(gt=0, strict=True), AfterValidator(_dentro_del_maximo)
    ]


class SubidaRespuesta(BaseModel):
    medio_id: uuid.UUID
    bucket: str
    ruta: str
    token: str
    url_subida: str
    expira_en: datetime

    @classmethod
    def desde(cls, medio: MediaAsset, subida: SubidaFirmada) -> Self:
        return cls(
            medio_id=medio.id,
            bucket=subida.bucket,
            ruta=subida.ruta,
            token=subida.token,
            url_subida=subida.url_subida,
            expira_en=subida.expira_en,
        )


class MedioRespuesta(BaseModel):
    id: uuid.UUID
    estado: EstadoMedia
    subido: bool
    url: str | None
    miniatura_url: str | None
    content_type: str | None
    tamano_bytes: int | None

    @classmethod
    def desde(cls, medio: MediaAsset, almacenamiento: Almacenamiento) -> Self:
        subido = medio.subido_en is not None
        return cls(
            id=medio.id,
            estado=medio.estado,
            subido=subido,
            url=(
                almacenamiento.url_publica(medio.bucket, medio.storage_path)
                if subido
                else None
            ),
            miniatura_url=(
                almacenamiento.url_publica(medio.bucket, medio.thumbnail_path)
                if medio.thumbnail_path
                else None
            ),
            content_type=medio.content_type,
            tamano_bytes=medio.tamano_bytes,
        )
