"""Consultas entre cliente y artista y sus mensajes: el unico chat del sistema.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
Recibe `ahora` y los limites como parametros: no lee el reloj ni la configuracion.

No hay tiempo real: la app pide los mensajes posteriores a su ultimo cursor.
Para que ninguno quede detras de un cursor ya entregado, cada mensaje se crea
con la fila de la consulta bloqueada y una marca que nunca retrocede: el orden
de confirmacion es el orden de las marcas.

Bloqueos en el orden de todo el backend (D18): perfil, despues consulta.
Una consulta en la que no participa quien pide da 404, para no revelar que existe.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    InvalidStateTransition,
    LimiteExcedido,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.domain.consultas import (
    VENTANA_LIMITE,
    LimitesConsultas,
    RolEnConsulta,
    marca_siguiente,
    requiere_aviso,
    rol_en_consulta,
)
from src.models import (
    Consulta,
    EstadoConsulta,
    EstadoObra,
    Mensaje,
    Obra,
    Pedido,
    Profile,
    RolPerfil,
    Servicio,
)
from src.services.paginacion import ParametrosPagina, traer_pagina
from src.services.perfiles import bloquear_perfil

NO_ENCONTRADA = "Consulta no encontrada"

# Donde se puede seguir agregando a una consulta repetida
ESTADOS_EN_CURSO = (EstadoConsulta.ABIERTA, EstadoConsulta.COTIZADA)


# Lo que necesitan los esquemas de respuesta, sin volver a la base


@dataclass(frozen=True)
class MensajeDetalle:
    mensaje: Mensaje
    es_mio: bool


@dataclass(frozen=True)
class MensajeConRemitente:
    """Para moderacion, que no es parte de la consulta."""

    mensaje: Mensaje
    remitente: Profile


@dataclass(frozen=True)
class ConsultaDetalle:
    consulta: Consulta
    cliente: Profile
    artista: Profile
    # Quien mira
    soy: RolEnConsulta
    ultimo_mensaje: MensajeDetalle | None
    no_leidos: int


# Visibilidad y carga


def _participa(usuario_id: uuid.UUID) -> ColumnElement[bool]:
    return or_(Consulta.cliente_id == usuario_id, Consulta.artista_id == usuario_id)


async def _consulta(
    session: AsyncSession,
    usuario: Profile,
    consulta_id: uuid.UUID,
    *,
    bloquear: bool = False,
) -> Consulta:
    stmt = select(Consulta).where(Consulta.id == consulta_id, _participa(usuario.id))
    if bloquear:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    consulta = (await session.execute(stmt)).scalar_one_or_none()
    if consulta is None:
        raise ResourceNotFound(NO_ENCONTRADA)
    return consulta


def _soy(consulta: Consulta, usuario: Profile) -> RolEnConsulta:
    rol = rol_en_consulta(consulta.cliente_id, consulta.artista_id, usuario.id)
    if rol is None:
        # Solo se detallan consultas ya filtradas por participante
        raise ResourceNotFound(NO_ENCONTRADA)
    return rol


def _marca_de_lectura(usuario_id: uuid.UUID) -> ColumnElement[datetime | None]:
    """La marca de lectura de quien mira en cada fila de consultas."""
    return case(
        (Consulta.cliente_id == usuario_id, Consulta.leido_cliente_hasta),
        else_=Consulta.leido_artista_hasta,
    )


def _no_leido(usuario_id: uuid.UUID) -> ColumnElement[bool]:
    """Mensaje de la otra parte posterior a la marca de lectura de quien mira."""
    marca = _marca_de_lectura(usuario_id)
    return and_(
        Mensaje.remitente_id != usuario_id,
        or_(marca.is_(None), Mensaje.created_at > marca),
    )


# Detalle de una pagina, con un numero fijo de consultas


async def _perfiles(
    session: AsyncSession, consultas: Sequence[Consulta]
) -> dict[uuid.UUID, Profile]:
    ids = {c.cliente_id for c in consultas} | {c.artista_id for c in consultas}
    filas = await session.execute(select(Profile).where(Profile.id.in_(ids)))
    return {p.id: p for p in filas.scalars()}


async def _ultimos_mensajes(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, Mensaje]:
    stmt = (
        select(Mensaje)
        .where(Mensaje.consulta_id.in_(ids))
        .ext(distinct_on(Mensaje.consulta_id))
        .order_by(
            Mensaje.consulta_id.desc(), Mensaje.created_at.desc(), Mensaje.id.desc()
        )
    )
    return {m.consulta_id: m for m in (await session.execute(stmt)).scalars()}


async def _no_leidos(
    session: AsyncSession, ids: list[uuid.UUID], usuario: Profile
) -> dict[uuid.UUID, int]:
    stmt = (
        select(Mensaje.consulta_id, func.count(Mensaje.id))
        .join(Consulta, Consulta.id == Mensaje.consulta_id)
        .where(Mensaje.consulta_id.in_(ids), _no_leido(usuario.id))
        .group_by(Mensaje.consulta_id)
    )
    return dict((await session.execute(stmt)).all())


async def _detallar(
    session: AsyncSession, consultas: Sequence[Consulta], usuario: Profile
) -> list[ConsultaDetalle]:
    """Perfiles, ultimo mensaje y no leidos de una pagina entera, sin N+1."""
    if not consultas:
        return []
    ids = [c.id for c in consultas]
    perfiles = await _perfiles(session, consultas)
    ultimos = await _ultimos_mensajes(session, ids)
    no_leidos = await _no_leidos(session, ids, usuario)
    detalles = []
    for c in consultas:
        ultimo = ultimos.get(c.id)
        detalles.append(
            ConsultaDetalle(
                consulta=c,
                cliente=perfiles[c.cliente_id],
                artista=perfiles[c.artista_id],
                soy=_soy(c, usuario),
                ultimo_mensaje=None
                if ultimo is None
                else MensajeDetalle(ultimo, ultimo.remitente_id == usuario.id),
                no_leidos=no_leidos.get(c.id, 0),
            )
        )
    return detalles


async def _detalle_de(
    session: AsyncSession, consulta: Consulta, usuario: Profile
) -> ConsultaDetalle:
    return (await _detallar(session, [consulta], usuario))[0]


# Mensajes


async def _agregar_mensaje(
    session: AsyncSession,
    consulta: Consulta,
    remitente: Profile,
    texto: str,
    ahora: datetime,
) -> Mensaje:
    """Con la fila de la consulta ya bloqueada por quien llama."""
    marca = marca_siguiente(consulta.ultimo_mensaje_at, ahora)
    mensaje = Mensaje(
        id=uuid.uuid4(),
        consulta_id=consulta.id,
        remitente_id=remitente.id,
        texto=texto,
        aviso_contacto=requiere_aviso(texto),
        created_at=marca,
    )
    consulta.ultimo_mensaje_at = marca
    session.add(mensaje)
    await session.flush()
    return mensaje


# Abrir


async def _exigir_artista(
    session: AsyncSession, cliente: Profile, artista_id: uuid.UUID
) -> Profile:
    artista = await session.get(Profile, artista_id)
    if artista is None or artista.rol != RolPerfil.ARTISTA:
        raise ResourceNotFound("Artista no encontrado")
    if artista.id == cliente.id:
        raise ReglaDeNegocioViolada("No podes abrir una consulta con vos mismo")
    return artista


async def _exigir_referencia(
    session: AsyncSession,
    artista: Profile,
    servicio_id: uuid.UUID | None,
    obra_id: uuid.UUID | None,
) -> None:
    """Servicio u obra del artista, sin borrar. Se leen sin bloquear."""
    if servicio_id is not None:
        servicio = (
            await session.execute(
                select(Servicio).where(
                    Servicio.id == servicio_id,
                    Servicio.artista_id == artista.id,
                    Servicio.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if servicio is None:
            raise ResourceNotFound("Servicio no encontrado")
        if not servicio.activo:
            raise ReglaDeNegocioViolada("El servicio no esta activo")
    if obra_id is not None:
        obra = (
            await session.execute(
                select(Obra).where(
                    Obra.id == obra_id,
                    Obra.artista_id == artista.id,
                    Obra.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if obra is None:
            raise ResourceNotFound("Obra no encontrada")
        if obra.estado is EstadoObra.VENDIDA:
            raise ReglaDeNegocioViolada("La obra ya se vendio")


async def _en_curso(
    session: AsyncSession,
    cliente: Profile,
    artista: Profile,
    servicio_id: uuid.UUID | None,
    obra_id: uuid.UUID | None,
) -> Consulta | None:
    """La consulta en curso con la misma referencia, bloqueada, si existe."""
    stmt = (
        select(Consulta)
        .where(
            Consulta.cliente_id == cliente.id,
            Consulta.artista_id == artista.id,
            Consulta.servicio_id.is_not_distinct_from(servicio_id),
            Consulta.obra_id.is_not_distinct_from(obra_id),
            Consulta.estado.in_(ESTADOS_EN_CURSO),
        )
        .order_by(Consulta.created_at.desc(), Consulta.id.desc())
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _exigir_cupo(
    session: AsyncSession,
    cliente: Profile,
    ahora: datetime,
    limites: LimitesConsultas,
) -> None:
    if not limites.es_reciente(cliente.created_at, ahora):
        return
    abiertas = (
        await session.execute(
            select(func.count(Consulta.id)).where(
                Consulta.cliente_id == cliente.id,
                Consulta.created_at > ahora - VENTANA_LIMITE,
            )
        )
    ).scalar_one()
    if not limites.cabe_otra(abiertas):
        raise LimiteExcedido(
            f"Una cuenta con menos de {limites.dias_cuenta_reciente} dias abre "
            f"hasta {limites.consultas_por_ventana} consultas cada 24 horas"
        )


async def abrir(
    session: AsyncSession,
    cliente: Profile,
    *,
    artista_id: uuid.UUID,
    servicio_id: uuid.UUID | None,
    obra_id: uuid.UUID | None,
    texto: str,
    presupuesto: Decimal | None,
    fecha_deseada: date | None,
    ahora: datetime,
    limites: LimitesConsultas,
) -> tuple[ConsultaDetalle, bool]:
    """La consulta y si se creo. Con una en curso igual, se le agrega el mensaje."""
    # Antes que nada: serializa las consultas del cliente, y con ellas el limite
    cliente = await bloquear_perfil(session, cliente.id)
    artista = await _exigir_artista(session, cliente, artista_id)
    await _exigir_referencia(session, artista, servicio_id, obra_id)

    existente = await _en_curso(session, cliente, artista, servicio_id, obra_id)
    if existente is not None:
        await _agregar_mensaje(session, existente, cliente, texto, ahora)
        return await _detalle_de(session, existente, cliente), False

    await _exigir_cupo(session, cliente, ahora, limites)
    consulta = Consulta(
        id=uuid.uuid4(),
        cliente_id=cliente.id,
        artista_id=artista.id,
        servicio_id=servicio_id,
        obra_id=obra_id,
        estado=EstadoConsulta.ABIERTA,
        presupuesto=presupuesto,
        fecha_deseada=fecha_deseada,
        created_at=ahora,
        ultimo_mensaje_at=ahora,
    )
    session.add(consulta)
    await session.flush()
    session.add(
        Mensaje(
            id=uuid.uuid4(),
            consulta_id=consulta.id,
            remitente_id=cliente.id,
            texto=texto,
            aviso_contacto=requiere_aviso(texto),
            created_at=ahora,
        )
    )
    await session.flush()
    return await _detalle_de(session, consulta, cliente), True


# Conversacion


async def enviar(
    session: AsyncSession,
    usuario: Profile,
    consulta_id: uuid.UUID,
    texto: str,
    ahora: datetime,
) -> MensajeDetalle:
    # Unico bloqueo: el orden de confirmacion es el orden de las marcas
    consulta = await _consulta(session, usuario, consulta_id, bloquear=True)
    if consulta.estado is EstadoConsulta.DESCARTADA:
        raise ReglaDeNegocioViolada("La consulta esta descartada")
    mensaje = await _agregar_mensaje(session, consulta, usuario, texto, ahora)
    return MensajeDetalle(mensaje, es_mio=True)


async def _mensajes(
    session: AsyncSession,
    usuario: Profile,
    consulta_id: uuid.UUID,
    parametros: ParametrosPagina,
    *,
    ascendente: bool,
) -> tuple[list[MensajeDetalle], str | None]:
    consulta = await _consulta(session, usuario, consulta_id)
    stmt = select(Mensaje).where(Mensaje.consulta_id == consulta.id)
    mensajes, siguiente = await traer_pagina(
        session, stmt, Mensaje, parametros, ascendente=ascendente
    )
    detalles = [MensajeDetalle(m, m.remitente_id == usuario.id) for m in mensajes]
    return detalles, siguiente


async def listar_mensajes(
    session: AsyncSession,
    usuario: Profile,
    consulta_id: uuid.UUID,
    parametros: ParametrosPagina,
) -> tuple[list[MensajeDetalle], str | None]:
    """El historial, del mas nuevo al mas viejo."""
    return await _mensajes(session, usuario, consulta_id, parametros, ascendente=False)


async def mensajes_nuevos(
    session: AsyncSession,
    usuario: Profile,
    consulta_id: uuid.UUID,
    parametros: ParametrosPagina,
) -> tuple[list[MensajeDetalle], str | None]:
    """Los posteriores al cursor, del mas viejo al mas nuevo. Sin cursor, todos."""
    return await _mensajes(session, usuario, consulta_id, parametros, ascendente=True)


async def marcar_leido(
    session: AsyncSession, usuario: Profile, consulta_id: uuid.UUID
) -> None:
    """Un solo UPDATE: la marca de quien lee pasa al ultimo mensaje de la fila."""
    stmt = (
        update(Consulta)
        .where(Consulta.id == consulta_id, _participa(usuario.id))
        .values(
            leido_cliente_hasta=case(
                (Consulta.cliente_id == usuario.id, Consulta.ultimo_mensaje_at),
                else_=Consulta.leido_cliente_hasta,
            ),
            leido_artista_hasta=case(
                (Consulta.artista_id == usuario.id, Consulta.ultimo_mensaje_at),
                else_=Consulta.leido_artista_hasta,
            ),
        )
        .returning(Consulta.id)
        .execution_options(synchronize_session=False)
    )
    if (await session.execute(stmt)).first() is None:
        raise ResourceNotFound(NO_ENCONTRADA)


async def descartar(
    session: AsyncSession, usuario: Profile, consulta_id: uuid.UUID
) -> ConsultaDetalle:
    """Cualquiera de los dos, solo desde abierta. La cotizada se cierra en el lote 8."""
    consulta = await _consulta(session, usuario, consulta_id, bloquear=True)
    if consulta.estado is not EstadoConsulta.ABIERTA:
        raise InvalidStateTransition(
            f"Solo se descarta una consulta abierta, y esta {consulta.estado}"
        )
    consulta.estado = EstadoConsulta.DESCARTADA
    await session.flush()
    return await _detalle_de(session, consulta, usuario)


# Lectura


async def detalle(
    session: AsyncSession, usuario: Profile, consulta_id: uuid.UUID
) -> ConsultaDetalle:
    consulta = await _consulta(session, usuario, consulta_id)
    return await _detalle_de(session, consulta, usuario)


async def bandeja(
    session: AsyncSession,
    usuario: Profile,
    como: RolEnConsulta | None,
    estado: EstadoConsulta | None,
    parametros: ParametrosPagina,
) -> tuple[list[ConsultaDetalle], str | None]:
    """Las consultas de quien mira, por ultimo mensaje, de la mas reciente."""
    if como is RolEnConsulta.CLIENTE:
        filtro = Consulta.cliente_id == usuario.id
    elif como is RolEnConsulta.ARTISTA:
        filtro = Consulta.artista_id == usuario.id
    else:
        filtro = _participa(usuario.id)
    stmt = select(Consulta).where(filtro)
    if estado is not None:
        stmt = stmt.where(Consulta.estado == estado)
    consultas, siguiente = await traer_pagina(
        session, stmt, Consulta, parametros, columna=Consulta.ultimo_mensaje_at
    )
    return await _detallar(session, consultas, usuario), siguiente


async def resumen_no_leidos(session: AsyncSession, usuario: Profile) -> tuple[int, int]:
    """Cuantas consultas tienen algo sin leer y cuantos mensajes, en una consulta."""
    stmt = (
        select(func.count(func.distinct(Mensaje.consulta_id)), func.count(Mensaje.id))
        .join(Consulta, Consulta.id == Mensaje.consulta_id)
        .where(_participa(usuario.id), _no_leido(usuario.id))
    )
    consultas, mensajes = (await session.execute(stmt)).one()
    return consultas, mensajes


# Lectura para moderacion. Sin control de participante: la API exige un admin.


async def mensajes_para_moderacion(
    session: AsyncSession, pedido_id: uuid.UUID, parametros: ParametrosPagina
) -> tuple[list[MensajeConRemitente], str | None]:
    """El chat de la consulta del pedido, del mas viejo al mas nuevo."""
    consulta_id = (
        await session.execute(select(Pedido.consulta_id).where(Pedido.id == pedido_id))
    ).scalar_one_or_none()
    if consulta_id is None:
        raise ResourceNotFound("Pedido no encontrado")
    stmt = select(Mensaje).where(Mensaje.consulta_id == consulta_id)
    mensajes, siguiente = await traer_pagina(
        session, stmt, Mensaje, parametros, ascendente=True
    )
    if not mensajes:
        return [], siguiente
    ids = {m.remitente_id for m in mensajes}
    filas = await session.execute(select(Profile).where(Profile.id.in_(ids)))
    perfiles = {p.id: p for p in filas.scalars()}
    return [
        MensajeConRemitente(m, perfiles[m.remitente_id]) for m in mensajes
    ], siguiente
