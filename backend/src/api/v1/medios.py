"""Endpoints de medios con subida firmada.

El archivo nunca pasa por aca: el cliente sube directo con la URL firmada.
Cada handler cierra la transaccion con commit despues de llamar al servicio.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    get_almacenamiento,
    get_current_artista,
    get_current_user,
    get_db,
)
from src.core.config import settings
from src.models import Profile
from src.schemas.medios import MedioRespuesta, SolicitudSubida, SubidaRespuesta
from src.services import medios as servicio
from src.storage import Almacenamiento

router = APIRouter(prefix="/medios", tags=["medios"])


@router.post("", response_model=SubidaRespuesta, status_code=status.HTTP_201_CREATED)
async def solicitar_subida(
    datos: SolicitudSubida,
    artista: Profile = Depends(get_current_artista),
    session: AsyncSession = Depends(get_db),
    almacenamiento: Almacenamiento = Depends(get_almacenamiento),
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


@router.post("/{medio_id}/confirmar", response_model=MedioRespuesta)
async def confirmar_subida(
    medio_id: uuid.UUID,
    usuario: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    almacenamiento: Almacenamiento = Depends(get_almacenamiento),
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


@router.get("/{medio_id}", response_model=MedioRespuesta)
async def obtener_medio(
    medio_id: uuid.UUID,
    usuario: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    almacenamiento: Almacenamiento = Depends(get_almacenamiento),
) -> MedioRespuesta:
    medio = await servicio.obtener(session, usuario.id, medio_id)
    return MedioRespuesta.desde(medio, almacenamiento)


@router.delete("/{medio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_medio(
    medio_id: uuid.UUID,
    usuario: Profile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    almacenamiento: Almacenamiento = Depends(get_almacenamiento),
) -> Response:
    await servicio.eliminar(session, almacenamiento, usuario.id, medio_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
