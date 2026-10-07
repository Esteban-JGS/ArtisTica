"""Seguir artistas.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
Ninguna operacion bloquea filas: seguir es idempotente con
`ON CONFLICT DO NOTHING` sobre el unico, sin leer antes.

Los contadores salen de la consulta, nunca de una columna, y no entran en
ningun orden: ni Seguidos ni Explorar los miran.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ReglaDeNegocioViolada, ResourceNotFound
from src.domain.enums import RolPerfil
from src.models import Follow, Profile
from src.services.paginacion import ParametrosPagina, traer_pagina

MOTIVO_SOLO_ARTISTAS = "Solo se sigue a artistas"
MOTIVO_AUTOSEGUIMIENTO = "No te podes seguir a vos mismo"


@dataclass(frozen=True)
class Resumen:
    seguidores: int
    siguiendo: int
    # None si nadie mira; falso en el propio perfil
    lo_sigo: bool | None


def _normalizar(handle: str) -> str:
    return handle.strip().lower()


async def _perfil(session: AsyncSession, handle: str) -> Profile:
    stmt = select(Profile).where(Profile.handle == _normalizar(handle))
    perfil = (await session.execute(stmt)).scalar_one_or_none()
    if perfil is None:
        raise ResourceNotFound("Perfil no encontrado")
    return perfil


async def _id_de(session: AsyncSession, handle: str) -> uuid.UUID:
    stmt = select(Profile.id).where(Profile.handle == _normalizar(handle))
    perfil_id = (await session.execute(stmt)).scalar_one_or_none()
    if perfil_id is None:
        raise ResourceNotFound("Perfil no encontrado")
    return perfil_id


# Seguir


async def seguir(session: AsyncSession, usuario: Profile, handle: str) -> None:
    seguido = await _perfil(session, handle)
    if seguido.id == usuario.id:
        raise ReglaDeNegocioViolada(MOTIVO_AUTOSEGUIMIENTO)
    if seguido.rol != RolPerfil.ARTISTA:
        raise ReglaDeNegocioViolada(MOTIVO_SOLO_ARTISTAS)
    stmt = (
        insert(Follow)
        .values(seguidor_id=usuario.id, seguido_id=seguido.id)
        .on_conflict_do_nothing(index_elements=["seguidor_id", "seguido_id"])
    )
    await session.execute(stmt)


async def dejar_de_seguir(session: AsyncSession, usuario: Profile, handle: str) -> None:
    seguido_id = await _id_de(session, handle)
    await session.execute(
        delete(Follow).where(
            Follow.seguidor_id == usuario.id, Follow.seguido_id == seguido_id
        )
    )


async def resumen(
    session: AsyncSession, handle: str, usuario: Profile | None
) -> Resumen:
    """Los dos contadores y si quien mira lo sigue, en una sola consulta."""
    seguidores = (
        select(func.count(Follow.id))
        .where(Follow.seguido_id == Profile.id)
        .scalar_subquery()
    )
    siguiendo = (
        select(func.count(Follow.id))
        .where(Follow.seguidor_id == Profile.id)
        .scalar_subquery()
    )
    columnas = [seguidores, siguiendo]
    if usuario is not None:
        columnas.append(
            exists().where(
                Follow.seguidor_id == usuario.id, Follow.seguido_id == Profile.id
            )
        )
    stmt = select(*columnas).where(Profile.handle == _normalizar(handle))
    fila = (await session.execute(stmt)).one_or_none()
    if fila is None:
        raise ResourceNotFound("Perfil no encontrado")
    # El CHECK de `follows` impide seguirse a uno mismo: el propio perfil da falso
    lo_sigo = bool(fila[2]) if usuario is not None else None
    return Resumen(seguidores=fila[0], siguiendo=fila[1], lo_sigo=lo_sigo)


async def _perfiles_de(
    session: AsyncSession,
    stmt: Select[tuple[Follow]],
    parametros: ParametrosPagina,
    *,
    seguidores: bool,
) -> tuple[list[Profile], str | None]:
    """Una pagina de follows, de cuando se siguio el mas reciente primero."""
    follows, siguiente = await traer_pagina(session, stmt, Follow, parametros)
    if not follows:
        return [], siguiente
    ids = [f.seguidor_id if seguidores else f.seguido_id for f in follows]
    filas = await session.execute(select(Profile).where(Profile.id.in_(ids)))
    perfiles = {p.id: p for p in filas.scalars()}
    return [perfiles[i] for i in ids], siguiente


async def seguidores_de(
    session: AsyncSession, handle: str, parametros: ParametrosPagina
) -> tuple[list[Profile], str | None]:
    perfil_id = await _id_de(session, handle)
    stmt = select(Follow).where(Follow.seguido_id == perfil_id)
    return await _perfiles_de(session, stmt, parametros, seguidores=True)


async def seguidos_por(
    session: AsyncSession, handle: str, parametros: ParametrosPagina
) -> tuple[list[Profile], str | None]:
    perfil_id = await _id_de(session, handle)
    stmt = select(Follow).where(Follow.seguidor_id == perfil_id)
    return await _perfiles_de(session, stmt, parametros, seguidores=False)
