"""Endpoints de medios con subida firmada.

El archivo nunca pasa por aca: el cliente sube directo con la URL firmada.
Cada handler cierra la transaccion con commit despues de llamar al servicio.
"""

import uuid

from fastapi import APIRouter, Response, status

from src.api.deps import AlmacenamientoDeMedios, Artista, Sesion, Usuario
from src.core.config import settings
from src.schemas.medios import MedioRespuesta, SolicitudSubida, SubidaRespuesta
from src.services import medios as servicio

router = APIRouter(prefix="/medios", tags=["medios"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def solicitar_subida(
    datos: SolicitudSubida,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> SubidaRespuesta:
    medio, subida = await servicio.solicitar_subida(
        session,
        almacenamiento,
        artista,
        datos.content_type,
        datos.tamano_bytes,
        maximo_pendientes=settings.MEDIOS_PENDIENTES_MAXIMOS,
        bucket=settings.BUCKET_MEDIOS,
    )
    await session.commit()
    return SubidaRespuesta.desde(medio, subida)


@router.post("/{medio_id}/confirmar")
async def confirmar_subida(
    medio_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> MedioRespuesta:
    medio = await servicio.confirmar_subida(
        session,
        almacenamiento,
        usuario.id,
        medio_id,
        maximo_bytes=settings.MEDIO_TAMANO_MAXIMO_BYTES,
    )
    await session.commit()
    return MedioRespuesta.desde(medio, almacenamiento)


@router.get("/{medio_id}")
async def obtener_medio(
    medio_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> MedioRespuesta:
    medio = await servicio.obtener(session, usuario.id, medio_id)
    return MedioRespuesta.desde(medio, almacenamiento)


@router.delete("/{medio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_medio(
    medio_id: uuid.UUID,
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> Response:
    await servicio.eliminar(session, almacenamiento, usuario.id, medio_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
