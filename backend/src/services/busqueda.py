"""Busqueda de publicaciones y de artistas.

Los resultados son organicos y van por recencia: ningun contador ni senal de
popularidad entra en el orden. El texto de quien busca viaja siempre como
parametro, nunca dentro del SQL.

Solo lee: no bloquea ni escribe nada.
"""

from sqlalchemy import Select, cast, func, or_, select
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import RolPerfil
from src.models import Profile, Publicacion
from src.services.paginacion import ParametrosPagina, traer_pagina
from src.services.publicaciones import PublicacionDetalle, detallar

# Largo del termino, ya recortado. Lo valida la capa de API
TERMINO_MINIMO = 2
TERMINO_MAXIMO = 100

# El mismo diccionario de la columna generada `search_vector`
DICCIONARIO = "spanish"
ESCAPE = "\\"


def _patron_contiene(termino: str) -> str:
    """Patron de ILIKE que toma `%`, `_` y la barra del termino como literales."""
    escapado = (
        termino.replace(ESCAPE, ESCAPE * 2)
        .replace("%", ESCAPE + "%")
        .replace("_", ESCAPE + "_")
    )
    return "%" + escapado + "%"


async def publicaciones(
    session: AsyncSession,
    termino: str,
    parametros: ParametrosPagina,
    usuario: Profile | None,
) -> tuple[list[PublicacionDetalle], str | None]:
    """Busqueda de texto completo, con las formas de cada palabra."""
    consulta = func.websearch_to_tsquery(cast(DICCIONARIO, REGCONFIG), termino)
    stmt: Select[tuple[Publicacion]] = select(Publicacion).where(
        Publicacion.deleted_at.is_(None),
        Publicacion.search_vector.bool_op("@@")(consulta),
    )
    encontradas, siguiente = await traer_pagina(session, stmt, Publicacion, parametros)
    return await detallar(session, encontradas, usuario), siguiente


async def artistas(
    session: AsyncSession, termino: str, parametros: ParametrosPagina
) -> tuple[list[Profile], str | None]:
    """Artistas cuyo handle o nombre contienen el termino, sin distinguir mayusculas."""
    patron = _patron_contiene(termino)
    stmt: Select[tuple[Profile]] = select(Profile).where(
        Profile.rol == RolPerfil.ARTISTA,
        or_(
            Profile.handle.ilike(patron, escape=ESCAPE),
            Profile.nombre.ilike(patron, escape=ESCAPE),
        ),
    )
    return await traer_pagina(session, stmt, Profile, parametros)
