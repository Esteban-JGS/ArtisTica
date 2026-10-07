"""Endpoints de publicaciones y del feed.

Cada handler que escribe cierra la transaccion con commit despues de llamar al
servicio. Ver una publicacion, el listado de un artista y Explorar son publicos;
Seguidos pide token.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.api.deps import AlmacenamientoDeMedios, Artista, Sesion, Usuario
from src.api.paginacion import Pagina, Paginacion
from src.core.config import settings
from src.schemas.perfiles import Categoria
from src.schemas.publicaciones import (
    EdicionPublicacion,
    NuevaPublicacion,
    PublicacionRespuesta,
)
from src.services import feed
from src.services import publicaciones as servicio
from src.services.paginacion import CursorInvalido, PosicionFlujo
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


# Feed


@router.get("/feed/seguidos")
async def feed_seguidos(
    usuario: Usuario,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
    paginacion: Paginacion,
) -> Pagina[PublicacionRespuesta]:
    detalles, siguiente = await feed.seguidos(session, usuario, paginacion)
    return _pagina(detalles, siguiente, almacenamiento)


@dataclass(frozen=True)
class ParametrosExplorar:
    posiciones: dict[str, PosicionFlujo]
    tamano: int
    categorias: list[str]


def parametros_de_explorar(
    categorias: Annotated[list[Categoria] | None, Query(max_length=5)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    tamano: Annotated[
        int, Query(ge=1, le=settings.PAGINA_TAMANO_MAXIMO)
    ] = settings.PAGINA_TAMANO_DEFECTO,
) -> ParametrosExplorar:
    """Explorar lleva un cursor compuesto: uno mal formado da 422.

    DT21: una pagina mas chica que `EXPLORAR_CADA_N` dejaria la cuota de nuevos
    talentos en 0, asi que tambien da 422. Se lee en cada solicitud.
    """
    minimo = settings.EXPLORAR_CADA_N
    if tamano < minimo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Explorar pide un tamano de al menos {minimo}",
        )
    try:
        posiciones = feed.leer_cursor_explorar(cursor)
    except CursorInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return ParametrosExplorar(posiciones, tamano, list(categorias or []))


Explorar = Annotated[ParametrosExplorar, Depends(parametros_de_explorar)]


@router.get("/feed/explorar")
async def feed_explorar(
    parametros: Explorar,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
) -> Pagina[PublicacionRespuesta]:
    detalles, siguiente = await feed.explorar(
        session,
        parametros.posiciones,
        parametros.tamano,
        categorias=parametros.categorias,
        umbral=settings.NUEVO_TALENTO_MAX_SEGUIDORES,
        cada_n=settings.EXPLORAR_CADA_N,
    )
    return _pagina(detalles, siguiente, almacenamiento)
