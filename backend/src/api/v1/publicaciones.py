"""Endpoints de publicaciones.

Cada handler que escribe cierra la transaccion con commit despues de llamar al
servicio. Ver una publicacion y el listado de un artista son publicos.
"""

import uuid

from fastapi import APIRouter, Response, status

from src.api.deps import AlmacenamientoDeMedios, Artista, Sesion
from src.api.paginacion import Pagina, Paginacion
from src.core.config import settings
from src.schemas.publicaciones import (
    EdicionPublicacion,
    NuevaPublicacion,
    PublicacionRespuesta,
)
from src.services import publicaciones as servicio
from src.services.publicaciones import PublicacionDetalle
from src.storage import Almacenamiento

router = APIRouter(tags=["publicaciones"])


def _pagina(
    detalles: list[PublicacionDetalle],
    siguiente: str | None,
    almacenamiento: Almacenamiento,
) -> Pagina[PublicacionRespuesta]:
    return Pagina(
        items=[PublicacionRespuesta.desde(d, almacenamiento) for d in detalles],
        siguiente_cursor=siguiente,
    )


# Publicaciones


@router.post("/publicaciones", status_code=status.HTTP_201_CREATED)
async def crear_publicacion(
    datos: NuevaPublicacion,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PublicacionRespuesta:
    detalle = await servicio.crear(
        session,
        artista,
        datos.model_dump(),
        medios_maximo=settings.MEDIOS_POR_PUBLICACION_MAXIMO,
    )
    await session.commit()
    return PublicacionRespuesta.desde(detalle, almacenamiento)


@router.get("/publicaciones/{publicacion_id}")
async def obtener_publicacion(
    publicacion_id: uuid.UUID,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PublicacionRespuesta:
    detalle = await servicio.obtener(session, publicacion_id)
    return PublicacionRespuesta.desde(detalle, almacenamiento)


@router.patch("/publicaciones/{publicacion_id}")
async def editar_publicacion(
    publicacion_id: uuid.UUID,
    datos: EdicionPublicacion,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> PublicacionRespuesta:
    detalle = await servicio.editar(session, artista, publicacion_id, datos.texto)
    await session.commit()
    return PublicacionRespuesta.desde(detalle, almacenamiento)


@router.delete(
    "/publicaciones/{publicacion_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def eliminar_publicacion(
    publicacion_id: uuid.UUID,
    artista: Artista,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> Response:
    await servicio.eliminar(session, almacenamiento, artista, publicacion_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/artistas/{handle}/publicaciones")
async def listar_publicaciones_del_artista(
    handle: str,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
    paginacion: Paginacion,
) -> Pagina[PublicacionRespuesta]:
    detalles, siguiente = await servicio.listar_de(session, handle, paginacion)
    return _pagina(detalles, siguiente, almacenamiento)
