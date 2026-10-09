"""Comentarios de publicaciones, con un solo nivel de respuestas, y sus me gusta.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
Comenta cualquier usuario con sesion, tambien el rol Publico. Dar y quitar me
gusta son idempotentes con `ON CONFLICT DO NOTHING`, sin leer antes.

Un comentario borrado desaparece junto con sus respuestas: una respuesta solo se
ve si su comentario de primer nivel tampoco esta borrado. Lo mismo vale si se
borra la publicacion.

Los contadores salen de la consulta, nunca de una columna, y no ordenan nada:
comentarios y respuestas van siempre del mas viejo al mas nuevo.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, Select, and_, delete, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.core.exceptions import (
    ActorNoAutorizado,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.domain.comentarios import destino_de_respuesta, puede_borrar
from src.models import Comentario, MeGustaComentario, Profile, Publicacion
from src.services.paginacion import ParametrosPagina, traer_pagina

# Cuantas respuestas trae cada comentario en el listado
PRIMERAS_RESPUESTAS = 3

MOTIVO_RESPUESTA_INVALIDA = "Solo se responde a un comentario de la misma publicacion"
MOTIVO_NO_PUEDE_BORRAR = "Solo borra el autor o el artista de la publicacion"


def _ahora() -> datetime:
    return datetime.now(UTC)


# Lo que necesitan los esquemas de respuesta, sin volver a la base


@dataclass(frozen=True)
class RespuestaDetalle:
    comentario: Comentario
    autor: Profile
    me_gusta_total: int = 0
    # Nulo si nadie mira
    mi_me_gusta: bool | None = None


@dataclass(frozen=True)
class ComentarioDetalle(RespuestaDetalle):
    respuestas_total: int = 0
    # Las primeras, en orden cronologico
    respuestas: list[RespuestaDetalle] = field(default_factory=list)


# Visibilidad


def _visible() -> ColumnElement[bool]:
    """Sin borrar, y si es respuesta, con su comentario de primer nivel sin borrar."""
    padre = aliased(Comentario)
    padre_vivo = exists().where(
        padre.id == Comentario.respuesta_a_id, padre.deleted_at.is_(None)
    )
    return and_(
        Comentario.deleted_at.is_(None),
        or_(Comentario.respuesta_a_id.is_(None), padre_vivo),
    )


def _visibles() -> Select[tuple[Comentario]]:
    """Comentarios visibles de publicaciones sin borrar."""
    return (
        select(Comentario)
        .join(Publicacion, Publicacion.id == Comentario.publicacion_id)
        .where(_visible(), Publicacion.deleted_at.is_(None))
    )


async def _comentario(session: AsyncSession, comentario_id: uuid.UUID) -> Comentario:
    stmt = _visibles().where(Comentario.id == comentario_id)
    comentario = (await session.execute(stmt)).scalar_one_or_none()
    if comentario is None:
        raise ResourceNotFound("Comentario no encontrado")
    return comentario


async def _exigir_publicacion(session: AsyncSession, publicacion_id: uuid.UUID) -> None:
    stmt = select(Publicacion.id).where(
        Publicacion.id == publicacion_id, Publicacion.deleted_at.is_(None)
    )
    if (await session.execute(stmt)).first() is None:
        raise ResourceNotFound("Publicacion no encontrada")


async def totales_por_publicacion(
    session: AsyncSession, publicacion_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Comentarios mas respuestas visibles de cada publicacion, en una consulta."""
    if not publicacion_ids:
        return {}
    filas = await session.execute(
        select(Comentario.publicacion_id, func.count(Comentario.id))
        .where(Comentario.publicacion_id.in_(publicacion_ids), _visible())
        .group_by(Comentario.publicacion_id)
    )
    return dict(filas.tuples().all())


# Detalle de una pagina, con un numero fijo de consultas


async def _autores(
    session: AsyncSession, comentarios: Sequence[Comentario]
) -> dict[uuid.UUID, Profile]:
    ids = {c.profile_id for c in comentarios}
    filas = await session.execute(select(Profile).where(Profile.id.in_(ids)))
    return {p.id: p for p in filas.scalars()}


async def _me_gusta(
    session: AsyncSession, ids: list[uuid.UUID], usuario: Profile | None
) -> tuple[dict[uuid.UUID, int], set[uuid.UUID] | None]:
    """El total de cada comentario y los que marco quien mira: dos consultas."""
    filas = await session.execute(
        select(MeGustaComentario.comentario_id, func.count(MeGustaComentario.id))
        .where(MeGustaComentario.comentario_id.in_(ids))
        .group_by(MeGustaComentario.comentario_id)
    )
    totales: dict[uuid.UUID, int] = dict(filas.tuples().all())
    if usuario is None:
        return totales, None
    mias = await session.execute(
        select(MeGustaComentario.comentario_id).where(
            MeGustaComentario.comentario_id.in_(ids),
            MeGustaComentario.profile_id == usuario.id,
        )
    )
    return totales, set(mias.scalars())


async def _primeras_respuestas(
    session: AsyncSession, comentario_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, list[Comentario]]]:
    """El total de respuestas de cada comentario y las primeras: dos consultas."""
    filas = await session.execute(
        select(Comentario.respuesta_a_id, func.count(Comentario.id))
        .where(
            Comentario.respuesta_a_id.in_(comentario_ids),
            Comentario.deleted_at.is_(None),
        )
        .group_by(Comentario.respuesta_a_id)
    )
    totales: dict[uuid.UUID, int] = dict(filas.tuples().all())
    numeradas = (
        select(
            Comentario,
            func.row_number()
            .over(
                partition_by=Comentario.respuesta_a_id,
                order_by=(Comentario.created_at, Comentario.id),
            )
            .label("posicion"),
        )
        .where(
            Comentario.respuesta_a_id.in_(comentario_ids),
            Comentario.deleted_at.is_(None),
        )
        .subquery()
    )
    respuesta = aliased(Comentario, numeradas)
    filas = await session.execute(
        select(respuesta)
        .where(numeradas.c.posicion <= PRIMERAS_RESPUESTAS)
        .order_by(respuesta.created_at, respuesta.id)
    )
    primeras: dict[uuid.UUID, list[Comentario]] = {}
    for r in filas.scalars():
        primeras.setdefault(r.respuesta_a_id, []).append(r)
    return totales, primeras


def _respuesta(
    comentario: Comentario,
    autores: dict[uuid.UUID, Profile],
    totales: dict[uuid.UUID, int],
    mias: set[uuid.UUID] | None,
) -> RespuestaDetalle:
    return RespuestaDetalle(
        comentario=comentario,
        autor=autores[comentario.profile_id],
        me_gusta_total=totales.get(comentario.id, 0),
        mi_me_gusta=None if mias is None else comentario.id in mias,
    )


async def _detallar_respuestas(
    session: AsyncSession, respuestas: Sequence[Comentario], usuario: Profile | None
) -> list[RespuestaDetalle]:
    if not respuestas:
        return []
    autores = await _autores(session, respuestas)
    totales, mias = await _me_gusta(session, [r.id for r in respuestas], usuario)
    return [_respuesta(r, autores, totales, mias) for r in respuestas]


async def _detallar(
    session: AsyncSession, comentarios: Sequence[Comentario], usuario: Profile | None
) -> list[ComentarioDetalle]:
    """Respuestas, autores y me gusta de una pagina entera, sin N+1."""
    if not comentarios:
        return []
    ids = [c.id for c in comentarios]
    respuestas_totales, primeras = await _primeras_respuestas(session, ids)
    respuestas = [r for c in comentarios for r in primeras.get(c.id, [])]
    todos = [*comentarios, *respuestas]
    autores = await _autores(session, todos)
    totales, mias = await _me_gusta(session, [c.id for c in todos], usuario)
    return [
        ComentarioDetalle(
            comentario=c,
            autor=autores[c.profile_id],
            me_gusta_total=totales.get(c.id, 0),
            mi_me_gusta=None if mias is None else c.id in mias,
            respuestas_total=respuestas_totales.get(c.id, 0),
            respuestas=[
                _respuesta(r, autores, totales, mias) for r in primeras.get(c.id, [])
            ],
        )
        for c in comentarios
    ]


# Operaciones


async def comentar(
    session: AsyncSession,
    usuario: Profile,
    publicacion_id: uuid.UUID,
    texto: str,
    respuesta_a: uuid.UUID | None,
) -> ComentarioDetalle:
    await _exigir_publicacion(session, publicacion_id)
    destino = None
    if respuesta_a is not None:
        stmt = _visibles().where(
            Comentario.id == respuesta_a, Comentario.publicacion_id == publicacion_id
        )
        objetivo = (await session.execute(stmt)).scalar_one_or_none()
        if objetivo is None:
            raise ReglaDeNegocioViolada(MOTIVO_RESPUESTA_INVALIDA)
        destino = destino_de_respuesta(objetivo.id, objetivo.respuesta_a_id)
    comentario = Comentario(
        id=uuid.uuid4(),
        publicacion_id=publicacion_id,
        profile_id=usuario.id,
        texto=texto,
        respuesta_a_id=destino,
    )
    session.add(comentario)
    await session.flush()
    return ComentarioDetalle(comentario=comentario, autor=usuario, mi_me_gusta=False)


async def listar(
    session: AsyncSession,
    publicacion_id: uuid.UUID,
    parametros: ParametrosPagina,
    usuario: Profile | None,
) -> tuple[list[ComentarioDetalle], str | None]:
    """Los de primer nivel, del mas viejo al mas nuevo."""
    await _exigir_publicacion(session, publicacion_id)
    stmt = select(Comentario).where(
        Comentario.publicacion_id == publicacion_id,
        Comentario.respuesta_a_id.is_(None),
        Comentario.deleted_at.is_(None),
    )
    comentarios, siguiente = await traer_pagina(
        session, stmt, Comentario, parametros, ascendente=True
    )
    return await _detallar(session, comentarios, usuario), siguiente


async def listar_respuestas(
    session: AsyncSession,
    comentario_id: uuid.UUID,
    parametros: ParametrosPagina,
    usuario: Profile | None,
) -> tuple[list[RespuestaDetalle], str | None]:
    """Las respuestas de un comentario de primer nivel, del mas viejo al mas nuevo."""
    comentario = await _comentario(session, comentario_id)
    if comentario.respuesta_a_id is not None:
        raise ResourceNotFound("Comentario no encontrado")
    stmt = select(Comentario).where(
        Comentario.respuesta_a_id == comentario_id, Comentario.deleted_at.is_(None)
    )
    respuestas, siguiente = await traer_pagina(
        session, stmt, Comentario, parametros, ascendente=True
    )
    return await _detallar_respuestas(session, respuestas, usuario), siguiente


async def borrar(
    session: AsyncSession, usuario: Profile, comentario_id: uuid.UUID
) -> None:
    """Soft delete. Las respuestas desaparecen con el, sin tocarlas."""
    stmt = (
        _visibles()
        .add_columns(Publicacion.artista_id)
        .where(Comentario.id == comentario_id)
        .with_for_update(of=Comentario)
        .execution_options(populate_existing=True)
    )
    fila = (await session.execute(stmt)).one_or_none()
    if fila is None:
        raise ResourceNotFound("Comentario no encontrado")
    comentario, artista_id = fila
    if not puede_borrar(comentario.profile_id, artista_id, usuario.id):
        raise ActorNoAutorizado(MOTIVO_NO_PUEDE_BORRAR)
    comentario.deleted_at = _ahora()
    await session.flush()


async def dar_me_gusta(
    session: AsyncSession, usuario: Profile, comentario_id: uuid.UUID
) -> None:
    await _comentario(session, comentario_id)
    stmt = (
        insert(MeGustaComentario)
        .values(comentario_id=comentario_id, profile_id=usuario.id)
        .on_conflict_do_nothing(index_elements=["comentario_id", "profile_id"])
    )
    await session.execute(stmt)


async def quitar_me_gusta(
    session: AsyncSession, usuario: Profile, comentario_id: uuid.UUID
) -> None:
    await _comentario(session, comentario_id)
    await session.execute(
        delete(MeGustaComentario).where(
            MeGustaComentario.comentario_id == comentario_id,
            MeGustaComentario.profile_id == usuario.id,
        )
    )
