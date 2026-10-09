"""Endpoints de comentarios, respuestas y me gusta en comentarios.

Comentar, borrar y dar me gusta piden token; cualquier rol puede. Los listados
son publicos, con token opcional para saber si quien mira dio me gusta.
"""

import uuid

from fastapi import APIRouter, Response, status

from src.api.deps import Sesion, Usuario, UsuarioOpcional
from src.api.paginacion import Pagina, Paginacion
from src.schemas.comentarios import (
    ComentarioRespuesta,
    NuevoComentario,
    RespuestaComentario,
)
from src.services import comentarios as servicio

router = APIRouter(tags=["comentarios"])

SIN_CONTENIDO = status.HTTP_204_NO_CONTENT


@router.post(
    "/publicaciones/{publicacion_id}/comentarios",
    status_code=status.HTTP_201_CREATED,
)
async def comentar(
    publicacion_id: uuid.UUID,
    datos: NuevoComentario,
    usuario: Usuario,
    session: Sesion,
) -> ComentarioRespuesta:
    detalle = await servicio.comentar(
        session, usuario, publicacion_id, datos.texto, datos.respuesta_a
    )
    await session.commit()
    return ComentarioRespuesta.desde(detalle)


@router.get("/publicaciones/{publicacion_id}/comentarios")
async def listar_comentarios(
    publicacion_id: uuid.UUID,
    usuario: UsuarioOpcional,
    session: Sesion,
    paginacion: Paginacion,
) -> Pagina[ComentarioRespuesta]:
    detalles, siguiente = await servicio.listar(
        session, publicacion_id, paginacion, usuario
    )
    return Pagina(
        items=[ComentarioRespuesta.desde(d) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.get("/comentarios/{comentario_id}/respuestas")
async def listar_respuestas(
    comentario_id: uuid.UUID,
    usuario: UsuarioOpcional,
    session: Sesion,
    paginacion: Paginacion,
) -> Pagina[RespuestaComentario]:
    detalles, siguiente = await servicio.listar_respuestas(
        session, comentario_id, paginacion, usuario
    )
    return Pagina(
        items=[RespuestaComentario.desde(d) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.delete("/comentarios/{comentario_id}", status_code=SIN_CONTENIDO)
async def borrar_comentario(
    comentario_id: uuid.UUID, usuario: Usuario, session: Sesion
) -> Response:
    await servicio.borrar(session, usuario, comentario_id)
    await session.commit()
    return Response(status_code=SIN_CONTENIDO)


# Me gusta


@router.put("/comentarios/{comentario_id}/me-gusta", status_code=SIN_CONTENIDO)
async def dar_me_gusta(
    comentario_id: uuid.UUID, usuario: Usuario, session: Sesion
) -> Response:
    await servicio.dar_me_gusta(session, usuario, comentario_id)
    await session.commit()
    return Response(status_code=SIN_CONTENIDO)


@router.delete("/comentarios/{comentario_id}/me-gusta", status_code=SIN_CONTENIDO)
async def quitar_me_gusta(
    comentario_id: uuid.UUID, usuario: Usuario, session: Sesion
) -> Response:
    await servicio.quitar_me_gusta(session, usuario, comentario_id)
    await session.commit()
    return Response(status_code=SIN_CONTENIDO)
