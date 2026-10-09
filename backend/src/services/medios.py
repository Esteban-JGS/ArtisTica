"""Ciclo de vida de un medio: pedir la subida, confirmarla y borrarla.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
El archivo nunca pasa por la API: el cliente sube directo con la URL firmada y
aca solo se firma, se verifica y se borra.

Tambien la asignacion de medios a una obra o una publicacion, que comparten el
catalogo y el feed. Quien asigna bloquea antes su obra o su publicacion, y
despues los medios.
"""

import logging
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from src.core.exceptions import ReglaDeNegocioViolada, ResourceNotFound
from src.domain import medios as dominio
from src.models import Entregable, EstadoMedia, Job, MediaAsset, Profile
from src.storage import Almacenamiento, ErrorAlmacenamiento, SubidaFirmada

logger = logging.getLogger(__name__)

TRABAJO_MINIATURA = "generate_thumbnail"

MOTIVO_MEDIO_INVALIDO = (
    "Algun medio no sirve: tiene que ser tuyo, confirmado, sin borrar, "
    "sin asociar a otra obra o publicacion y sin entregar en un pedido"
)


@dataclass(frozen=True)
class Destino:
    """La obra o la publicacion duena de unos medios. Solo una de las dos."""

    obra_id: uuid.UUID | None = None
    publicacion_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (self.obra_id is None) == (self.publicacion_id is None):
            raise ValueError("Un destino es una obra o una publicacion, no ambas")


def _ahora() -> datetime:
    return datetime.now(UTC)


async def _cargar(
    session: AsyncSession,
    propietario_id: uuid.UUID,
    medio_id: uuid.UUID,
    *,
    bloquear: bool = False,
) -> MediaAsset:
    """El medio del propietario. Ajeno o borrado da 404, para no revelar que existe."""
    stmt = select(MediaAsset).where(
        MediaAsset.id == medio_id,
        MediaAsset.propietario_id == propietario_id,
        MediaAsset.deleted_at.is_(None),
    )
    if bloquear:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    medio = (await session.execute(stmt)).scalar_one_or_none()
    if medio is None:
        raise ResourceNotFound("Medio no encontrado")
    return medio


async def _borrar_objetos(
    almacenamiento: Almacenamiento, medio: MediaAsset, rutas: list[str]
) -> None:
    """Borra en Storage. Si falla, solo se loguea: queda un objeto huerfano."""
    try:
        await almacenamiento.borrar(medio.bucket, rutas)
    except ErrorAlmacenamiento as exc:
        logger.warning(
            "No se pudo borrar el objeto del medio %s: %s", medio.id, type(exc).__name__
        )


async def solicitar_subida(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    propietario: Profile,
    content_type: str,
    tamano_bytes: int,
    *,
    maximo_pendientes: int,
    bucket: str,
) -> tuple[MediaAsset, SubidaFirmada]:
    stmt = select(func.count(MediaAsset.id)).where(
        MediaAsset.propietario_id == propietario.id,
        MediaAsset.subido_en.is_(None),
        MediaAsset.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).scalar_one() >= maximo_pendientes:
        raise ReglaDeNegocioViolada(
            "Hay demasiadas subidas sin confirmar: confirmalas o borralas"
        )

    medio_id = uuid.uuid4()
    ruta = dominio.ruta_para(propietario.id, medio_id, content_type)
    # Primero se firma: si Storage falla, no queda ninguna fila
    subida = await almacenamiento.firmar_subida(bucket, ruta)
    medio = MediaAsset(
        id=medio_id,
        propietario_id=propietario.id,
        tipo=dominio.TIPO_IMAGEN,
        storage_path=ruta,
        bucket=bucket,
        content_type=content_type,
        tamano_bytes=tamano_bytes,
        estado=EstadoMedia.PENDIENTE,
    )
    session.add(medio)
    await session.flush()
    return medio, subida


async def confirmar_subida(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    propietario_id: uuid.UUID,
    medio_id: uuid.UUID,
    *,
    maximo_bytes: int,
) -> MediaAsset:
    medio = await _cargar(session, propietario_id, medio_id, bloquear=True)
    if medio.subido_en is not None:
        return medio

    info = await almacenamiento.info(medio.bucket, medio.storage_path)
    problema = dominio.problema_de_subida(medio.content_type, info, maximo_bytes)
    if problema is not None:
        if info is not None:
            await _borrar_objetos(almacenamiento, medio, [medio.storage_path])
        raise ReglaDeNegocioViolada(problema)

    ahora = _ahora()
    medio.subido_en = ahora
    medio.tamano_bytes = info.tamano_bytes
    # estado sigue en pendiente: habla del procesamiento, no de la subida
    session.add(
        Job(
            type=TRABAJO_MINIATURA,
            payload={"medio_id": str(medio.id)},
            run_after=ahora,
        )
    )
    await session.flush()
    return medio


async def obtener(
    session: AsyncSession, propietario_id: uuid.UUID, medio_id: uuid.UUID
) -> MediaAsset:
    return await _cargar(session, propietario_id, medio_id)


async def eliminar(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    propietario_id: uuid.UUID,
    medio_id: uuid.UUID,
) -> None:
    medio = await _cargar(session, propietario_id, medio_id, bloquear=True)
    if medio.obra_id is not None or medio.publicacion_id is not None:
        raise ReglaDeNegocioViolada(
            "El medio esta asociado a una obra o una publicacion"
        )
    entregable = await session.execute(
        select(Entregable.id).where(Entregable.media_asset_id == medio.id).limit(1)
    )
    if entregable.first() is not None:
        raise ReglaDeNegocioViolada("El medio es un entregable de un pedido")

    medio.deleted_at = _ahora()
    await session.flush()
    rutas = [medio.storage_path]
    if medio.thumbnail_path:
        rutas.append(medio.thumbnail_path)
    await _borrar_objetos(almacenamiento, medio, rutas)


async def borrar_objetos_de(
    almacenamiento: Almacenamiento, medios: Sequence[MediaAsset]
) -> None:
    """Borra en Storage los objetos y miniaturas de varios medios. Si falla,
    solo se loguea: quedan objetos huerfanos."""
    por_bucket: dict[str, list[str]] = defaultdict(list)
    for medio in medios:
        por_bucket[medio.bucket].append(medio.storage_path)
        if medio.thumbnail_path:
            por_bucket[medio.bucket].append(medio.thumbnail_path)
    for bucket, rutas in por_bucket.items():
        try:
            await almacenamiento.borrar(bucket, rutas)
        except ErrorAlmacenamiento as exc:
            logger.warning(
                "No se pudieron borrar los objetos de %s: %s",
                bucket,
                type(exc).__name__,
            )


# Medios de una obra o una publicacion


def _campo_de(destino: Destino) -> str:
    return "obra_id" if destino.obra_id is not None else "publicacion_id"


def _sirve(
    medio: MediaAsset | None, propietario_id: uuid.UUID, pertenece_a: Destino | None
) -> bool:
    if (
        medio is None
        or medio.propietario_id != propietario_id
        or medio.deleted_at is not None
        or medio.subido_en is None
    ):
        return False
    if medio.obra_id is None and medio.publicacion_id is None:
        return True
    return (
        pertenece_a is not None
        and medio.obra_id == pertenece_a.obra_id
        and medio.publicacion_id == pertenece_a.publicacion_id
    )


async def tomar_medios_sueltos(
    session: AsyncSession,
    propietario_id: uuid.UUID,
    ids: Sequence[uuid.UUID],
    *,
    maximo: int,
    minimo: int,
    pertenece_a: Destino | None,
) -> list[MediaAsset]:
    """Los medios en el orden pedido, bloqueados. Si alguno no sirve, falla antes
    de escribir. Al editar, `pertenece_a` acepta los que ya son de ese destino."""
    if len(ids) < minimo:
        raise ReglaDeNegocioViolada(
            "Hace falta al menos una imagen"
            if minimo == 1
            else f"Hacen falta al menos {minimo} imagenes"
        )
    if len(ids) > maximo:
        raise ReglaDeNegocioViolada(f"Se admiten {maximo} imagenes como maximo")
    if len(set(ids)) != len(ids):
        raise ReglaDeNegocioViolada("Hay imagenes repetidas")
    if not ids:
        return []

    stmt = (
        select(MediaAsset)
        .where(MediaAsset.id.in_(ids))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    por_id = {m.id: m for m in (await session.execute(stmt)).scalars()}
    elegidos: list[MediaAsset] = []
    for medio_id in ids:
        medio = por_id.get(medio_id)
        if not _sirve(medio, propietario_id, pertenece_a):
            raise ReglaDeNegocioViolada(MOTIVO_MEDIO_INVALIDO)
        elegidos.append(medio)
    # DT24: un entregable de un pedido no pasa a una obra ni a una publicacion.
    # Con los medios ya bloqueados, no se cruza con una entrega en curso.
    entregado = await session.execute(
        select(Entregable.id).where(Entregable.media_asset_id.in_(ids)).limit(1)
    )
    if entregado.first() is not None:
        raise ReglaDeNegocioViolada(MOTIVO_MEDIO_INVALIDO)
    return elegidos


async def asignar_medios(
    session: AsyncSession,
    elegidos: Sequence[MediaAsset],
    *,
    obra_id: uuid.UUID | None = None,
    publicacion_id: uuid.UUID | None = None,
) -> list[MediaAsset]:
    """Deja exactamente estos medios, en este orden, en la obra o la publicacion.
    Los que tenia y salen quedan sueltos."""
    destino = Destino(obra_id=obra_id, publicacion_id=publicacion_id)
    campo = _campo_de(destino)
    dueno_id = getattr(destino, campo)
    columna: InstrumentedAttribute[uuid.UUID | None] = getattr(MediaAsset, campo)
    quedan = {m.id for m in elegidos}
    anteriores = await session.execute(
        select(MediaAsset)
        .where(columna == dueno_id, MediaAsset.id.not_in(quedan))
        .execution_options(populate_existing=True)
    )
    for medio in anteriores.scalars():
        setattr(medio, campo, None)
        medio.orden = None
    for posicion, medio in enumerate(elegidos):
        setattr(medio, campo, dueno_id)
        medio.orden = posicion
    await session.flush()
    return list(elegidos)


async def _medios_por(
    session: AsyncSession,
    columna: InstrumentedAttribute[uuid.UUID | None],
    ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, list[MediaAsset]]:
    if not ids:
        return {}
    stmt = (
        select(MediaAsset)
        .where(columna.in_(ids), MediaAsset.deleted_at.is_(None))
        .order_by(MediaAsset.orden, MediaAsset.id)
    )
    por_dueno: dict[uuid.UUID, list[MediaAsset]] = defaultdict(list)
    for medio in (await session.execute(stmt)).scalars():
        por_dueno[getattr(medio, columna.key)].append(medio)
    return por_dueno


async def medios_de_obras(
    session: AsyncSession, obra_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[MediaAsset]]:
    """Los medios de varias obras en una sola consulta, ya ordenados."""
    return await _medios_por(session, MediaAsset.obra_id, obra_ids)


async def medios_de_publicaciones(
    session: AsyncSession, publicacion_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[MediaAsset]]:
    """Los medios de varias publicaciones en una sola consulta, ya ordenados."""
    return await _medios_por(session, MediaAsset.publicacion_id, publicacion_ids)
