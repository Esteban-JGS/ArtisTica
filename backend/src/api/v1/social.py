"""Endpoints de seguir artistas.

Seguir pide token y es idempotente. El resumen del perfil
acepta token opcional; las listas de seguidores son publicas.
"""

from fastapi import APIRouter, Response, status

from src.api.deps import Sesion, Usuario, UsuarioOpcional
from src.api.paginacion import Pagina, Paginacion
from src.schemas.social import PerfilResumido, ResumenSocial
from src.services import social as servicio

router = APIRouter(tags=["social"])

SIN_CONTENIDO = status.HTTP_204_NO_CONTENT


# Seguir


@router.post("/artistas/{handle}/seguir", status_code=SIN_CONTENIDO)
async def seguir_artista(handle: str, usuario: Usuario, session: Sesion) -> Response:
    await servicio.seguir(session, usuario, handle)
    await session.commit()
    return Response(status_code=SIN_CONTENIDO)


@router.delete("/artistas/{handle}/seguir", status_code=SIN_CONTENIDO)
async def dejar_de_seguir_artista(
    handle: str, usuario: Usuario, session: Sesion
) -> Response:
    await servicio.dejar_de_seguir(session, usuario, handle)
    await session.commit()
    return Response(status_code=SIN_CONTENIDO)


@router.get("/perfiles/{handle}/social")
async def resumen_social(
    handle: str, usuario: UsuarioOpcional, session: Sesion
) -> ResumenSocial:
    return ResumenSocial.desde(await servicio.resumen(session, handle, usuario))


@router.get("/perfiles/{handle}/seguidores")
async def seguidores(
    handle: str, session: Sesion, paginacion: Paginacion
) -> Pagina[PerfilResumido]:
    perfiles, siguiente = await servicio.seguidores_de(session, handle, paginacion)
    return Pagina(
        items=[PerfilResumido.desde(p) for p in perfiles], siguiente_cursor=siguiente
    )


@router.get("/perfiles/{handle}/siguiendo")
async def siguiendo(
    handle: str, session: Sesion, paginacion: Paginacion
) -> Pagina[PerfilResumido]:
    perfiles, siguiente = await servicio.seguidos_por(session, handle, paginacion)
    return Pagina(
        items=[PerfilResumido.desde(p) for p in perfiles], siguiente_cursor=siguiente
    )
