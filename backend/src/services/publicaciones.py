"""Publicaciones del artista: lo que aparece en el feed.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
El maximo de imagenes y el almacenamiento llegan como parametros: este modulo
no lee `settings`.

Una publicacion puede mostrar una obra de la galeria, pero no la vende: la
respuesta solo dice si la obra esta disponible.

Orden de los bloqueos: la publicacion antes que sus medios. Ninguna operacion
de este modulo bloquea el perfil.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ReglaDeNegocioViolada, ResourceNotFound
from src.domain.enums import TipoReaccion
from src.models import MediaAsset, Obra, Profile, Publicacion, Reaccion
from src.services.comentarios import totales_por_publicacion
from src.services.medios import (
    asignar_medios,
    borrar_objetos_de,
    medios_de_publicaciones,
    tomar_medios_sueltos,
)
from src.services.paginacion import ParametrosPagina, traer_pagina
from src.storage import Almacenamiento

MOTIVO_OBRA_INVALIDA = "La obra no existe o no es tuya"


def _ahora() -> datetime:
    return datetime.now(UTC)


# Lo que necesitan los esquemas de respuesta, sin volver a la base


@dataclass(frozen=True)
class PublicacionDetalle:
    publicacion: Publicacion
    artista: Profile
    medios: list[MediaAsset]
    # Nula si no muestra ninguna o si la obra se borro despues
    obra: Obra | None
    # Solo en Explorar: verdadero o falso. Nulo en los demas listados
    nuevo_talento: bool | None = None
    me_gusta_total: int = 0
    # Nulo si nadie mira
    mi_me_gusta: bool | None = None
    # Comentarios mas respuestas visibles: el "Comentarios · N" de la app
    comentarios_total: int = 0


async def _me_gusta(
    session: AsyncSession, ids: list[uuid.UUID], usuario: Profile | None
) -> tuple[dict[uuid.UUID, int], set[uuid.UUID] | None]:
    """El total de cada publicacion y las que marco quien mira: dos consultas."""
    es_me_gusta = Reaccion.tipo == TipoReaccion.ME_GUSTA.value
    filas = await session.execute(
        select(Reaccion.publicacion_id, func.count(Reaccion.id))
        .where(Reaccion.publicacion_id.in_(ids), es_me_gusta)
        .group_by(Reaccion.publicacion_id)
    )
    totales: dict[uuid.UUID, int] = dict(filas.all())
    if usuario is None:
        return totales, None
    mias = await session.execute(
        select(Reaccion.publicacion_id).where(
            Reaccion.publicacion_id.in_(ids),
            Reaccion.profile_id == usuario.id,
            es_me_gusta,
        )
    )
    return totales, set(mias.scalars())


async def detallar(
    session: AsyncSession,
    publicaciones: Sequence[Publicacion],
    usuario: Profile | None,
    nuevo_talento: Mapping[uuid.UUID, bool] | None = None,
) -> list[PublicacionDetalle]:
    """Medios, obras, artistas, me gusta y comentarios de una pagina entera.

    Una consulta por cada uno, sin importar el tamano de la pagina. `usuario`
    es quien mira: sin el, `mi_me_gusta` queda nulo. Nada de esto cambia el
    orden de la pagina.
    """
    if not publicaciones:
        return []
    marcas = nuevo_talento or {}
    ids = [p.id for p in publicaciones]
    medios = await medios_de_publicaciones(session, ids)
    obra_ids = {p.obra_id for p in publicaciones if p.obra_id is not None}
    obras: dict[uuid.UUID, Obra] = {}
    if obra_ids:
        filas = await session.execute(
            select(Obra).where(Obra.id.in_(obra_ids), Obra.deleted_at.is_(None))
        )
        obras = {o.id: o for o in filas.scalars()}
    artista_ids = {p.artista_id for p in publicaciones}
    filas = await session.execute(select(Profile).where(Profile.id.in_(artista_ids)))
    artistas = {a.id: a for a in filas.scalars()}
    totales, mias = await _me_gusta(session, ids, usuario)
    comentarios = await totales_por_publicacion(session, ids)
    return [
        PublicacionDetalle(
            publicacion=p,
            artista=artistas[p.artista_id],
            medios=medios.get(p.id, []),
            obra=obras.get(p.obra_id) if p.obra_id is not None else None,
            nuevo_talento=marcas.get(p.id),
            me_gusta_total=totales.get(p.id, 0),
            mi_me_gusta=None if mias is None else p.id in mias,
            comentarios_total=comentarios.get(p.id, 0),
        )
        for p in publicaciones
    ]


async def _uno(
    session: AsyncSession, publicacion: Publicacion, usuario: Profile | None
) -> PublicacionDetalle:
    return (await detallar(session, [publicacion], usuario))[0]


async def _bloquear_publicacion(
    session: AsyncSession, artista_id: uuid.UUID, publicacion_id: uuid.UUID
) -> Publicacion:
    """La publicacion del artista. Ajena o borrada da 404, para no revelar que existe."""
    stmt = (
        select(Publicacion)
        .where(
            Publicacion.id == publicacion_id,
            Publicacion.artista_id == artista_id,
            Publicacion.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    publicacion = (await session.execute(stmt)).scalar_one_or_none()
    if publicacion is None:
        raise ResourceNotFound("Publicacion no encontrada")
    return publicacion


async def _exigir_obra_propia(
    session: AsyncSession, artista_id: uuid.UUID, obra_id: uuid.UUID
) -> None:
    stmt = select(Obra.id).where(
        Obra.id == obra_id, Obra.artista_id == artista_id, Obra.deleted_at.is_(None)
    )
    if (await session.execute(stmt)).first() is None:
        raise ReglaDeNegocioViolada(MOTIVO_OBRA_INVALIDA)


async def crear(
    session: AsyncSession,
    artista: Profile,
    datos: Mapping,
    *,
    medios_maximo: int,
) -> PublicacionDetalle:
    obra_id = datos.get("obra_id")
    # Nada se escribe hasta que todo lo que puede fallar ya paso
    if obra_id is not None:
        await _exigir_obra_propia(session, artista.id, obra_id)
    elegidos = await tomar_medios_sueltos(
        session,
        artista.id,
        list(datos.get("medios") or []),
        maximo=medios_maximo,
        minimo=0,
        pertenece_a=None,
    )

    publicacion = Publicacion(
        id=uuid.uuid4(),
        artista_id=artista.id,
        texto=datos["texto"],
        obra_id=obra_id,
    )
    session.add(publicacion)
    await session.flush()
    await asignar_medios(session, elegidos, publicacion_id=publicacion.id)
    return await _uno(session, publicacion, artista)


async def obtener(
    session: AsyncSession, publicacion_id: uuid.UUID, usuario: Profile | None
) -> PublicacionDetalle:
    """Vista publica: nunca una publicacion borrada."""
    stmt = select(Publicacion).where(
        Publicacion.id == publicacion_id, Publicacion.deleted_at.is_(None)
    )
    publicacion = (await session.execute(stmt)).scalar_one_or_none()
    if publicacion is None:
        raise ResourceNotFound("Publicacion no encontrada")
    return await _uno(session, publicacion, usuario)


async def editar(
    session: AsyncSession,
    artista: Profile,
    publicacion_id: uuid.UUID,
    texto: str,
) -> PublicacionDetalle:
    publicacion = await _bloquear_publicacion(session, artista.id, publicacion_id)
    publicacion.texto = texto
    await session.flush()
    return await _uno(session, publicacion, artista)


async def eliminar(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    artista: Profile,
    publicacion_id: uuid.UUID,
) -> None:
    publicacion = await _bloquear_publicacion(session, artista.id, publicacion_id)
    ahora = _ahora()
    publicacion.deleted_at = ahora
    filas = await session.execute(
        select(MediaAsset)
        .where(
            MediaAsset.publicacion_id == publicacion.id,
            MediaAsset.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    medios = list(filas.scalars())
    for medio in medios:
        medio.deleted_at = ahora
    await session.flush()
    if medios:
        await borrar_objetos_de(almacenamiento, medios)


async def listar_de(
    session: AsyncSession,
    handle: str,
    parametros: ParametrosPagina,
    usuario: Profile | None,
) -> tuple[list[PublicacionDetalle], str | None]:
    """Las publicaciones de un artista, sin las borradas."""
    stmt = select(Profile.id).where(Profile.handle == handle)
    artista_id = (await session.execute(stmt)).scalar_one_or_none()
    if artista_id is None:
        raise ResourceNotFound("Artista no encontrado")
    consulta: Select[tuple[Publicacion]] = select(Publicacion).where(
        Publicacion.artista_id == artista_id, Publicacion.deleted_at.is_(None)
    )
    publicaciones, siguiente = await traer_pagina(
        session, consulta, Publicacion, parametros
    )
    return await detallar(session, publicaciones, usuario), siguiente
