"""Ciclo de vida de un medio: pedir la subida, confirmarla y borrarla.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
El archivo nunca pasa por la API: el cliente sube directo con la URL firmada y
aca solo se firma, se verifica y se borra.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ReglaDeNegocioViolada, ResourceNotFound
from src.domain import medios as dominio
from src.models import Entregable, EstadoMedia, Job, MediaAsset, Profile
from src.storage import Almacenamiento, ErrorAlmacenamiento, SubidaFirmada

logger = logging.getLogger(__name__)

TRABAJO_MINIATURA = "generate_thumbnail"


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
