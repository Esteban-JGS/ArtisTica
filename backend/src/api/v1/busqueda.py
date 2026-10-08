"""Endpoints de busqueda. Publicos: el de publicaciones acepta token opcional.

El termino se recorta y tiene que quedar entre `TERMINO_MINIMO` y
`TERMINO_MAXIMO` caracteres; fuera de eso, 422.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import AlmacenamientoDeMedios, Sesion, UsuarioOpcional
from src.api.paginacion import Pagina, Paginacion
from src.schemas.publicaciones import PublicacionRespuesta
from src.schemas.social import PerfilResumido
from src.services import busqueda as servicio
from src.services.busqueda import TERMINO_MAXIMO, TERMINO_MINIMO

router = APIRouter(prefix="/buscar", tags=["busqueda"])


def termino_de_busqueda(q: Annotated[str, Query(max_length=512)]) -> str:
    """El termino recortado. Corto o largo da 422."""
    termino = q.strip()
    if not TERMINO_MINIMO <= len(termino) <= TERMINO_MAXIMO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"La busqueda va de {TERMINO_MINIMO} a {TERMINO_MAXIMO} caracteres"
            ),
        )
    return termino


Termino = Annotated[str, Depends(termino_de_busqueda)]


@router.get("/publicaciones")
async def buscar_publicaciones(
    termino: Termino,
    usuario: UsuarioOpcional,
    session: Sesion,
    almacenamiento: AlmacenamientoDeMedios,
    paginacion: Paginacion,
) -> Pagina[PublicacionRespuesta]:
    detalles, siguiente = await servicio.publicaciones(
        session, termino, paginacion, usuario
    )
    return Pagina(
        items=[PublicacionRespuesta.desde(d, almacenamiento) for d in detalles],
        siguiente_cursor=siguiente,
    )


@router.get("/artistas")
async def buscar_artistas(
    termino: Termino, session: Sesion, paginacion: Paginacion
) -> Pagina[PerfilResumido]:
    perfiles, siguiente = await servicio.artistas(session, termino, paginacion)
    return Pagina(
        items=[PerfilResumido.desde(p) for p in perfiles], siguiente_cursor=siguiente
    )
