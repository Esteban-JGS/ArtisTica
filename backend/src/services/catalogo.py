"""Catalogo del artista: obras y servicios con los limites de su plan.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
Los limites, el monto minimo y el almacenamiento llegan como parametros: este
modulo no lee `settings`.

D11: bajar de plan no oculta ni borra nada. Con mas de lo permitido solo se
impide crear o activar otro hasta quedar por debajo del limite.
"""

import logging
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.paginacion import ParametrosPagina, traer_pagina
from src.core.exceptions import ReglaDeNegocioViolada, ResourceNotFound
from src.domain import catalogo as dominio
from src.domain.catalogo import LimitesPlan
from src.domain.pedidos import ESTADOS_TERMINALES
from src.models import (
    EstadoObra,
    MediaAsset,
    Obra,
    Pedido,
    PlanArtista,
    Profile,
    Servicio,
)
from src.services.perfiles import bloquear_perfil
from src.storage import Almacenamiento, ErrorAlmacenamiento

logger = logging.getLogger(__name__)

MOTIVO_MEDIO_INVALIDO = (
    "Algun medio no sirve: tiene que ser tuyo, confirmado, sin borrar y "
    "sin asociar a otra obra o publicacion"
)
MOTIVO_PEDIDO_ACTIVO = "La obra tiene un pedido en curso"
MOTIVO_VENDIDA = "La obra ya se vendio: solo se puede editar su ficha"

CAMPOS_DE_OBRA = ("titulo", "descripcion", "categorias", "precio", "estado")
CAMPOS_DE_SERVICIO = ("titulo", "descripcion", "precio_base", "tipo", "activo")


def _ahora() -> datetime:
    return datetime.now(UTC)


# Lo que necesitan los esquemas de respuesta, sin volver a la base


@dataclass(frozen=True)
class ObraDetalle:
    obra: Obra
    artista_handle: str
    medios: list[MediaAsset]


@dataclass(frozen=True)
class ServicioDetalle:
    servicio: Servicio
    artista_handle: str


@dataclass(frozen=True)
class LimitesArtista:
    plan: PlanArtista
    servicios_activos: int
    limite_servicios_activos: int | None
    obras_disponibles: int
    limite_obras_disponibles: int | None


# Carga, bloqueo y conteos


async def _artista_por_handle(session: AsyncSession, handle: str) -> Profile:
    stmt = select(Profile).where(Profile.handle == handle)
    perfil = (await session.execute(stmt)).scalar_one_or_none()
    if perfil is None:
        raise ResourceNotFound("Artista no encontrado")
    return perfil


async def _handle_de(session: AsyncSession, artista_id: uuid.UUID) -> str:
    stmt = select(Profile.handle).where(Profile.id == artista_id)
    handle = (await session.execute(stmt)).scalar_one_or_none()
    if handle is None:
        raise ResourceNotFound("Artista no encontrado")
    return handle


async def _bloquear_obra(
    session: AsyncSession, artista_id: uuid.UUID, obra_id: uuid.UUID
) -> Obra:
    """La obra del artista. Ajena o borrada da 404, para no revelar que existe."""
    stmt = (
        select(Obra)
        .where(
            Obra.id == obra_id,
            Obra.artista_id == artista_id,
            Obra.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    obra = (await session.execute(stmt)).scalar_one_or_none()
    if obra is None:
        raise ResourceNotFound("Obra no encontrada")
    return obra


async def _bloquear_servicio(
    session: AsyncSession, artista_id: uuid.UUID, servicio_id: uuid.UUID
) -> Servicio:
    stmt = (
        select(Servicio)
        .where(
            Servicio.id == servicio_id,
            Servicio.artista_id == artista_id,
            Servicio.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    servicio = (await session.execute(stmt)).scalar_one_or_none()
    if servicio is None:
        raise ResourceNotFound("Servicio no encontrado")
    return servicio


async def _contar_obras_disponibles(
    session: AsyncSession, artista_id: uuid.UUID, *, excepto: uuid.UUID | None = None
) -> int:
    stmt = select(func.count(Obra.id)).where(
        Obra.artista_id == artista_id,
        Obra.estado == EstadoObra.DISPONIBLE,
        Obra.deleted_at.is_(None),
    )
    if excepto is not None:
        stmt = stmt.where(Obra.id != excepto)
    return (await session.execute(stmt)).scalar_one()


async def _contar_servicios_activos(
    session: AsyncSession, artista_id: uuid.UUID, *, excepto: uuid.UUID | None = None
) -> int:
    stmt = select(func.count(Servicio.id)).where(
        Servicio.artista_id == artista_id,
        Servicio.activo.is_(True),
        Servicio.deleted_at.is_(None),
    )
    if excepto is not None:
        stmt = stmt.where(Servicio.id != excepto)
    return (await session.execute(stmt)).scalar_one()


async def _exigir_cupo_de_obra(
    session: AsyncSession,
    artista_id: uuid.UUID,
    plan: PlanArtista,
    limites: LimitesPlan,
    *,
    excepto: uuid.UUID | None = None,
) -> None:
    """Se llama con el perfil ya bloqueado: el conteo no cambia hasta el commit."""
    limite = limites.obras_disponibles(plan)
    actuales = await _contar_obras_disponibles(session, artista_id, excepto=excepto)
    if not dominio.cabe_uno_mas(actuales, limite):
        raise ReglaDeNegocioViolada(
            f"Tu plan permite {limite} obras disponibles a la vez. "
            "Pasa alguna a exhibicion o cambia de plan"
        )


async def _exigir_cupo_de_servicio(
    session: AsyncSession,
    artista_id: uuid.UUID,
    plan: PlanArtista,
    limites: LimitesPlan,
    *,
    excepto: uuid.UUID | None = None,
) -> None:
    limite = limites.servicios_activos(plan)
    actuales = await _contar_servicios_activos(session, artista_id, excepto=excepto)
    if not dominio.cabe_uno_mas(actuales, limite):
        raise ReglaDeNegocioViolada(
            f"Tu plan permite {limite} servicios activos. "
            "Desactiva alguno o cambia de plan"
        )


# Pedidos de una obra


async def _tiene_pedido_activo(session: AsyncSession, obra_id: uuid.UUID) -> bool:
    stmt = (
        select(Pedido.id)
        .where(Pedido.obra_id == obra_id, Pedido.estado.not_in(ESTADOS_TERMINALES))
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def _tuvo_pedidos(session: AsyncSession, obra_id: uuid.UUID) -> bool:
    stmt = select(Pedido.id).where(Pedido.obra_id == obra_id).limit(1)
    return (await session.execute(stmt)).first() is not None


# Medios de una obra


async def medios_de(
    session: AsyncSession, obra_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[MediaAsset]]:
    """Los medios de varias obras en una sola consulta, ya ordenados."""
    if not obra_ids:
        return {}
    stmt = (
        select(MediaAsset)
        .where(MediaAsset.obra_id.in_(obra_ids), MediaAsset.deleted_at.is_(None))
        .order_by(MediaAsset.orden, MediaAsset.id)
    )
    por_obra: dict[uuid.UUID, list[MediaAsset]] = defaultdict(list)
    for medio in (await session.execute(stmt)).scalars():
        por_obra[medio.obra_id].append(medio)
    return por_obra


async def _validar_medios(
    session: AsyncSession,
    artista_id: uuid.UUID,
    ids: Sequence[uuid.UUID],
    *,
    obra_id: uuid.UUID | None,
    maximo: int,
) -> list[MediaAsset]:
    """Los medios en el orden pedido. Si alguno no sirve, falla antes de escribir."""
    if not ids:
        raise ReglaDeNegocioViolada("La obra necesita al menos una imagen")
    if len(ids) > maximo:
        raise ReglaDeNegocioViolada(f"Una obra admite {maximo} imagenes como maximo")
    if len(set(ids)) != len(ids):
        raise ReglaDeNegocioViolada("Hay imagenes repetidas")

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
        if (
            medio is None
            or medio.propietario_id != artista_id
            or medio.deleted_at is not None
            or medio.subido_en is None
            or medio.publicacion_id is not None
            or (medio.obra_id is not None and medio.obra_id != obra_id)
        ):
            raise ReglaDeNegocioViolada(MOTIVO_MEDIO_INVALIDO)
        elegidos.append(medio)
    return elegidos


async def _reemplazar_medios(
    session: AsyncSession, obra: Obra, elegidos: list[MediaAsset]
) -> list[MediaAsset]:
    """Deja exactamente estos medios en la obra. Los que salen quedan sueltos."""
    quedan = {m.id for m in elegidos}
    anteriores = await session.execute(
        select(MediaAsset)
        .where(MediaAsset.obra_id == obra.id, MediaAsset.id.not_in(quedan))
        .execution_options(populate_existing=True)
    )
    for medio in anteriores.scalars():
        medio.obra_id = None
        medio.orden = None
    for posicion, medio in enumerate(elegidos):
        medio.obra_id = obra.id
        medio.orden = posicion
    await session.flush()
    return elegidos


async def _borrar_objetos(
    almacenamiento: Almacenamiento, medios: Sequence[MediaAsset]
) -> None:
    """Borra en Storage. Si falla, solo se loguea: queda un objeto huerfano."""
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


# Obras


async def crear_obra(
    session: AsyncSession,
    artista: Profile,
    datos: Mapping,
    *,
    limites: LimitesPlan,
    monto_minimo: Decimal,
) -> ObraDetalle:
    estado = datos.get("estado", EstadoObra.EXHIBICION)
    precio = datos.get("precio")
    # Nada se escribe hasta que todo lo que puede fallar ya paso
    elegidos = await _validar_medios(
        session,
        artista.id,
        list(datos["medios"]),
        obra_id=None,
        maximo=limites.medios_por_obra,
    )
    if estado == EstadoObra.DISPONIBLE:
        problema = dominio.problema_de_precio(precio, monto_minimo)
        if problema is not None:
            raise ReglaDeNegocioViolada(problema)
        perfil = await bloquear_perfil(session, artista.id)
        await _exigir_cupo_de_obra(session, artista.id, perfil.plan, limites)

    obra = Obra(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo=datos["titulo"],
        descripcion=datos.get("descripcion"),
        categorias=list(datos.get("categorias") or []),
        estado=estado,
        precio=precio,
    )
    session.add(obra)
    await session.flush()
    medios = await _reemplazar_medios(session, obra, elegidos)
    return ObraDetalle(obra=obra, artista_handle=artista.handle, medios=medios)


async def obtener_obra(session: AsyncSession, obra_id: uuid.UUID) -> ObraDetalle:
    """Vista publica: cualquier estado, pero nunca una obra borrada."""
    stmt = select(Obra).where(Obra.id == obra_id, Obra.deleted_at.is_(None))
    obra = (await session.execute(stmt)).scalar_one_or_none()
    if obra is None:
        raise ResourceNotFound("Obra no encontrada")
    medios = (await medios_de(session, [obra.id])).get(obra.id, [])
    return ObraDetalle(
        obra=obra,
        artista_handle=await _handle_de(session, obra.artista_id),
        medios=medios,
    )


def _aplicar(fila: object, cambios: Mapping, campos: Sequence[str]) -> None:
    """Solo los campos presentes en el cuerpo."""
    for campo in campos:
        if campo in cambios:
            setattr(fila, campo, cambios[campo])


async def _exigir_obra_editable(
    session: AsyncSession, obra: Obra, cambios: Mapping
) -> None:
    """La ficha se edita siempre. El precio, el estado y las imagenes no cuando
    la obra se vendio o tiene un pedido en curso."""
    if not dominio.campos_restringidos(cambios):
        return
    if not dominio.es_estado_editable(obra.estado):
        raise ReglaDeNegocioViolada(MOTIVO_VENDIDA)
    if await _tiene_pedido_activo(session, obra.id):
        raise ReglaDeNegocioViolada(MOTIVO_PEDIDO_ACTIVO)


async def _exigir_disponible_posible(
    session: AsyncSession,
    obra: Obra,
    artista: Profile,
    precio: Decimal | None,
    *,
    limites: LimitesPlan,
    monto_minimo: Decimal,
) -> None:
    problema = dominio.problema_de_precio(precio, monto_minimo)
    if problema is not None:
        raise ReglaDeNegocioViolada(problema)
    if obra.estado == EstadoObra.DISPONIBLE:
        return
    perfil = await bloquear_perfil(session, artista.id)
    await _exigir_cupo_de_obra(
        session, artista.id, perfil.plan, limites, excepto=obra.id
    )


async def editar_obra(
    session: AsyncSession,
    artista: Profile,
    obra_id: uuid.UUID,
    cambios: Mapping,
    *,
    limites: LimitesPlan,
    monto_minimo: Decimal,
) -> ObraDetalle:
    obra = await _bloquear_obra(session, artista.id, obra_id)
    await _exigir_obra_editable(session, obra, cambios)

    estado = cambios.get("estado", obra.estado)
    precio = cambios.get("precio", obra.precio)
    elegidos = None
    if "medios" in cambios:
        elegidos = await _validar_medios(
            session,
            artista.id,
            list(cambios["medios"]),
            obra_id=obra.id,
            maximo=limites.medios_por_obra,
        )
    if estado == EstadoObra.DISPONIBLE:
        await _exigir_disponible_posible(
            session, obra, artista, precio, limites=limites, monto_minimo=monto_minimo
        )

    _aplicar(obra, cambios, CAMPOS_DE_OBRA)
    await session.flush()

    if elegidos is not None:
        medios = await _reemplazar_medios(session, obra, elegidos)
    else:
        medios = (await medios_de(session, [obra.id])).get(obra.id, [])
    return ObraDetalle(obra=obra, artista_handle=artista.handle, medios=medios)


async def eliminar_obra(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    artista: Profile,
    obra_id: uuid.UUID,
) -> None:
    obra = await _bloquear_obra(session, artista.id, obra_id)
    if await _tiene_pedido_activo(session, obra.id):
        raise ReglaDeNegocioViolada(MOTIVO_PEDIDO_ACTIVO)
    ahora = _ahora()
    obra.deleted_at = ahora
    # Si tuvo pedidos, sus imagenes son historial del pedido y se conservan
    huerfanos: list[MediaAsset] = []
    if not await _tuvo_pedidos(session, obra.id):
        filas = await session.execute(
            select(MediaAsset)
            .where(MediaAsset.obra_id == obra.id, MediaAsset.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        huerfanos = list(filas.scalars())
        for medio in huerfanos:
            medio.deleted_at = ahora
    await session.flush()
    if huerfanos:
        await _borrar_objetos(almacenamiento, huerfanos)


async def listar_obras_de(
    session: AsyncSession, handle: str, parametros: ParametrosPagina
) -> tuple[list[ObraDetalle], str | None]:
    """Galeria publica del artista: todos los estados, sin las borradas."""
    artista = await _artista_por_handle(session, handle)
    stmt: Select[tuple[Obra]] = select(Obra).where(
        Obra.artista_id == artista.id, Obra.deleted_at.is_(None)
    )
    obras, siguiente = await traer_pagina(session, stmt, Obra, parametros)
    por_obra = await medios_de(session, [o.id for o in obras])
    detalles = [
        ObraDetalle(
            obra=obra, artista_handle=artista.handle, medios=por_obra.get(obra.id, [])
        )
        for obra in obras
    ]
    return detalles, siguiente


# Servicios


async def crear_servicio(
    session: AsyncSession,
    artista: Profile,
    datos: Mapping,
    *,
    limites: LimitesPlan,
    monto_minimo: Decimal,
) -> ServicioDetalle:
    problema = dominio.problema_de_precio(datos.get("precio_base"), monto_minimo)
    if problema is not None:
        raise ReglaDeNegocioViolada(problema)
    activo = datos.get("activo", True)
    if activo:
        perfil = await bloquear_perfil(session, artista.id)
        await _exigir_cupo_de_servicio(session, artista.id, perfil.plan, limites)

    servicio = Servicio(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo=datos["titulo"],
        descripcion=datos.get("descripcion"),
        precio_base=datos["precio_base"],
        tipo=datos["tipo"],
        activo=activo,
    )
    session.add(servicio)
    await session.flush()
    return ServicioDetalle(servicio=servicio, artista_handle=artista.handle)


async def obtener_servicio(
    session: AsyncSession, servicio_id: uuid.UUID
) -> ServicioDetalle:
    """Vista publica: solo un servicio activo y sin borrar."""
    stmt = select(Servicio).where(
        Servicio.id == servicio_id,
        Servicio.activo.is_(True),
        Servicio.deleted_at.is_(None),
    )
    servicio = (await session.execute(stmt)).scalar_one_or_none()
    if servicio is None:
        raise ResourceNotFound("Servicio no encontrado")
    return ServicioDetalle(
        servicio=servicio,
        artista_handle=await _handle_de(session, servicio.artista_id),
    )


async def editar_servicio(
    session: AsyncSession,
    artista: Profile,
    servicio_id: uuid.UUID,
    cambios: Mapping,
    *,
    limites: LimitesPlan,
    monto_minimo: Decimal,
) -> ServicioDetalle:
    servicio = await _bloquear_servicio(session, artista.id, servicio_id)
    if "precio_base" in cambios:
        problema = dominio.problema_de_precio(cambios["precio_base"], monto_minimo)
        if problema is not None:
            raise ReglaDeNegocioViolada(problema)
    # Desactivar siempre se puede
    if cambios.get("activo") and not servicio.activo:
        perfil = await bloquear_perfil(session, artista.id)
        await _exigir_cupo_de_servicio(
            session, artista.id, perfil.plan, limites, excepto=servicio.id
        )

    _aplicar(servicio, cambios, CAMPOS_DE_SERVICIO)
    await session.flush()
    return ServicioDetalle(servicio=servicio, artista_handle=artista.handle)


async def eliminar_servicio(
    session: AsyncSession, artista: Profile, servicio_id: uuid.UUID
) -> None:
    servicio = await _bloquear_servicio(session, artista.id, servicio_id)
    servicio.deleted_at = _ahora()
    await session.flush()


async def listar_servicios_de(
    session: AsyncSession, handle: str, parametros: ParametrosPagina
) -> tuple[list[ServicioDetalle], str | None]:
    """Vitrina publica del artista: solo los activos."""
    artista = await _artista_por_handle(session, handle)
    stmt: Select[tuple[Servicio]] = select(Servicio).where(
        Servicio.artista_id == artista.id,
        Servicio.activo.is_(True),
        Servicio.deleted_at.is_(None),
    )
    servicios, siguiente = await traer_pagina(session, stmt, Servicio, parametros)
    detalles = [ServicioDetalle(s, artista.handle) for s in servicios]
    return detalles, siguiente


async def listar_servicios_propios(
    session: AsyncSession, artista: Profile, parametros: ParametrosPagina
) -> tuple[list[ServicioDetalle], str | None]:
    """Los del artista, activos e inactivos."""
    stmt: Select[tuple[Servicio]] = select(Servicio).where(
        Servicio.artista_id == artista.id, Servicio.deleted_at.is_(None)
    )
    servicios, siguiente = await traer_pagina(session, stmt, Servicio, parametros)
    detalles = [ServicioDetalle(s, artista.handle) for s in servicios]
    return detalles, siguiente


# Limites


async def limites_de(
    session: AsyncSession, artista: Profile, limites: LimitesPlan
) -> LimitesArtista:
    """Lo que el artista tiene activo y lo que su plan permite. Cuenta lo no borrado."""
    return LimitesArtista(
        plan=artista.plan,
        servicios_activos=await _contar_servicios_activos(session, artista.id),
        limite_servicios_activos=limites.servicios_activos(artista.plan),
        obras_disponibles=await _contar_obras_disponibles(session, artista.id),
        limite_obras_disponibles=limites.obras_disponibles(artista.plan),
    )
