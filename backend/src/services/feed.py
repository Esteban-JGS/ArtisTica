"""Feed Seguidos y Explorar.

Seguidos es cronologico puro: las publicaciones del usuario y de quienes sigue,
sin nada promocionado ni reordenado.

Explorar lee dos flujos disjuntos, los dos cronologicos: el de los artistas con
`umbral` seguidores o mas y el de los nuevos talentos, con menos. El conteo de
seguidores sale de la consulta, nunca de una columna. Ninguna senal de
popularidad, interaccion ni tiempo en pantalla entra en el orden.

Solo lee: no bloquea ni escribe nada.
"""

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.feed import Origen, cuantos_de_cada, intercalar
from src.models import Follow, Obra, Profile, Publicacion
from src.services.paginacion import (
    ClaveCursor,
    EstadoFlujo,
    ParametrosPagina,
    PosicionFlujo,
    codificar_cursor_compuesto,
    decodificar_cursor_compuesto,
    traer_pagina,
)
from src.services.publicaciones import PublicacionDetalle, detallar

# Nombres de los flujos dentro del cursor compuesto
FLUJOS = frozenset(o.value for o in Origen)


# Seguidos


async def seguidos(
    session: AsyncSession, usuario: Profile, parametros: ParametrosPagina
) -> tuple[list[PublicacionDetalle], str | None]:
    siguiendo = select(Follow.seguido_id).where(Follow.seguidor_id == usuario.id)
    stmt: Select[tuple[Publicacion]] = select(Publicacion).where(
        Publicacion.deleted_at.is_(None),
        or_(
            Publicacion.artista_id == usuario.id,
            Publicacion.artista_id.in_(siguiendo),
        ),
    )
    publicaciones, siguiente = await traer_pagina(
        session, stmt, Publicacion, parametros
    )
    return await detallar(session, publicaciones, usuario), siguiente


# Explorar


def leer_cursor_explorar(valor: str | None) -> dict[str, PosicionFlujo]:
    """La posicion de cada flujo. Un cursor ajeno levanta `CursorInvalido`."""
    if valor is None:
        return dict.fromkeys(FLUJOS)
    return decodificar_cursor_compuesto(valor, FLUJOS)


def _consulta(
    origen: Origen, umbral: int, categorias: Sequence[str]
) -> Select[tuple[Publicacion]]:
    seguidores = (
        select(func.count(Follow.id))
        .where(Follow.seguido_id == Publicacion.artista_id)
        .scalar_subquery()
    )
    condicion: ColumnElement[bool] = (
        seguidores < umbral if origen == Origen.NUEVO_TALENTO else seguidores >= umbral
    )
    stmt = select(Publicacion).where(Publicacion.deleted_at.is_(None), condicion)
    if categorias:
        filtro = list(categorias)
        stmt = (
            stmt.join(Profile, Profile.id == Publicacion.artista_id)
            .outerjoin(
                Obra, (Obra.id == Publicacion.obra_id) & Obra.deleted_at.is_(None)
            )
            .where(
                or_(
                    Profile.categorias.overlap(filtro),
                    Obra.categorias.overlap(filtro),
                )
            )
        )
    return stmt


async def _tramo(
    session: AsyncSession,
    stmt: Select[tuple[Publicacion]],
    posicion: PosicionFlujo,
    cuantos: int,
) -> tuple[list[Publicacion], PosicionFlujo]:
    """Hasta `cuantos` filas del flujo desde `posicion`, y donde queda despues."""
    if posicion is EstadoFlujo.AGOTADO or cuantos == 0:
        return [], posicion
    filas, siguiente = await traer_pagina(
        session, stmt, Publicacion, ParametrosPagina(cuantos, posicion)
    )
    if siguiente is None:
        return filas, EstadoFlujo.AGOTADO
    return filas, ClaveCursor(filas[-1].created_at, filas[-1].id)


async def explorar(
    session: AsyncSession,
    posiciones: Mapping[str, PosicionFlujo],
    tamano: int,
    *,
    categorias: Sequence[str],
    umbral: int,
    cada_n: int,
    usuario: Profile | None,
) -> tuple[list[PublicacionDetalle], str | None]:
    """Una pagina con la cuota de nuevos talentos y el cursor de los dos flujos.

    Cada flujo da primero su cuota. Si uno se agota antes, el otro completa la
    pagina con una segunda consulta.
    """
    posiciones = dict(posiciones)
    consultas = {o: _consulta(o, umbral, categorias) for o in Origen}
    cuotas = dict(zip(Origen, cuantos_de_cada(tamano, cada_n), strict=True))
    filas: dict[Origen, list[Publicacion]] = {}
    for origen in Origen:
        filas[origen], posiciones[origen.value] = await _tramo(
            session, consultas[origen], posiciones[origen.value], cuotas[origen]
        )

    faltan = tamano - sum(len(f) for f in filas.values())
    if faltan:
        # El que no lleno su cuota esta agotado: completa el otro
        otro = (
            Origen.NUEVO_TALENTO
            if len(filas[Origen.GENERAL]) < cuotas[Origen.GENERAL]
            else Origen.GENERAL
        )
        extra, posiciones[otro.value] = await _tramo(
            session, consultas[otro], posiciones[otro.value], faltan
        )
        filas[otro] += extra

    pagina = intercalar(
        filas[Origen.GENERAL], filas[Origen.NUEVO_TALENTO], tamano, cada_n
    )
    marcas: dict[uuid.UUID, bool] = {
        i.elemento.id: i.origen == Origen.NUEVO_TALENTO for i in pagina
    }
    detalles = await detallar(session, [i.elemento for i in pagina], usuario, marcas)
    agotados = all(p is EstadoFlujo.AGOTADO for p in posiciones.values())
    siguiente = None if agotados else codificar_cursor_compuesto(posiciones)
    return detalles, siguiente
