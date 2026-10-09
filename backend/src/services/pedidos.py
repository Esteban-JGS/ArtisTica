"""Aplica las reglas del dominio de pedidos sobre la base.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
Bloquea el pedido con SELECT ... FOR UPDATE antes de cambiarlo, en el orden
de todo el backend (D18, D21): perfil del artista, pedido, consulta, obra.
No llama a la pasarela: recibe los hechos que la pasarela ya confirmo.
Cada captura y cada reembolso que registra se asientan en el ledger, en la
misma transaccion.
"""

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, Select, and_, not_, or_, select, union
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    ActorNoAutorizado,
    CotizacionInvalida,
    HechosInconsistentes,
    InvalidStateTransition,
    ObraNoDisponible,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.domain import pedidos as dominio
from src.domain.pedidos import HechosPasarela, PlanCobros, Rol
from src.domain.politicas import PoliticasPedido
from src.models import (
    Base,
    Cobro,
    Consulta,
    Disputa,
    Entregable,
    EstadoCobro,
    EstadoConsulta,
    EstadoDisputa,
    EstadoObra,
    EstadoPedido,
    MediaAsset,
    Obra,
    Pedido,
    Profile,
    RolPerfil,
    TipoCobro,
    TipoEntregable,
    TipoPedido,
)
from src.services import ledger
from src.services.paginacion import ParametrosPagina, traer_pagina
from src.services.perfiles import bloquear_perfil

INDICE_OBRA_ACTIVA = "ux_pedidos_obra_activa"
NO_ENCONTRADO = "Pedido no encontrado"


# Lo que necesitan los esquemas de respuesta, sin volver a la base


@dataclass(frozen=True)
class VistaPrevia:
    entregable: Entregable
    medio: MediaAsset


@dataclass(frozen=True)
class EntregableFinal:
    """Vive en el bucket privado: se descarga con una URL firmada, nunca publica."""

    entregable: Entregable
    medio: MediaAsset


@dataclass(frozen=True)
class PedidoDetalle:
    pedido: Pedido
    cliente: Profile
    artista: Profile
    # Quien mira. Nulo cuando mira moderacion
    soy: Rol | None
    cobros: list[Cobro]
    vistas_previas: list[VistaPrevia]
    finales: list[EntregableFinal]
    disputa: Disputa | None


# Carga y bloqueo


async def _bloquear[M: Base](
    session: AsyncSession, modelo: type[M], id_: uuid.UUID
) -> M:
    stmt = (
        select(modelo)
        .where(modelo.id == id_)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    fila = (await session.execute(stmt)).scalar_one_or_none()
    if fila is None:
        raise ResourceNotFound(f"{modelo.__tablename__} {id_} no existe")
    return fila


async def _obtener[M: Base](
    session: AsyncSession, modelo: type[M], id_: uuid.UUID
) -> M:
    fila = await session.get(modelo, id_, populate_existing=True)
    if fila is None:
        raise ResourceNotFound(f"{modelo.__tablename__} {id_} no existe")
    return fila


async def _cobros(session: AsyncSession, pedido_id: uuid.UUID) -> list[Cobro]:
    stmt = (
        select(Cobro)
        .where(Cobro.pedido_id == pedido_id)
        .order_by(Cobro.tipo)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(stmt)).scalars())


def _cobro(cobros: Sequence[Cobro], tipo: TipoCobro) -> Cobro:
    for cobro in cobros:
        if cobro.tipo is tipo:
            return cobro
    raise ResourceNotFound(f"El pedido no tiene cobro de {tipo}")


async def bloquear_pedido(session: AsyncSession, pedido_id: uuid.UUID) -> Pedido:
    return await _bloquear(session, Pedido, pedido_id)


async def cobros_del_pedido(session: AsyncSession, pedido_id: uuid.UUID) -> list[Cobro]:
    """Releidos de la base. Se cambian solo con el pedido bloqueado."""
    return await _cobros(session, pedido_id)


def cobro_de_tipo(cobros: Sequence[Cobro], tipo: TipoCobro) -> Cobro:
    return _cobro(cobros, tipo)


async def cobro_por_referencia(session: AsyncSession, referencia: str) -> Cobro | None:
    """Sin bloquear: quien lo cambia vuelve a leerlo con el pedido bloqueado."""
    stmt = (
        select(Cobro)
        .where(Cobro.referencia_pasarela == referencia)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def esperando_autenticacion(cobro: Cobro) -> bool:
    """Un intento del cobro espera que el cliente se autentique en el banco."""
    return (
        cobro.estado is EstadoCobro.PENDIENTE and cobro.referencia_pasarela is not None
    )


# Intentos de un cobro. Quien llama ya bloqueo el pedido.


async def registrar_intento_en_espera(
    session: AsyncSession, *, cobro: Cobro, referencia_pasarela: str
) -> Cobro:
    """El banco pidio 3DS: el cobro guarda la referencia y sigue pendiente."""
    if cobro.estado is not EstadoCobro.PENDIENTE:
        raise InvalidStateTransition("Solo un cobro pendiente espera la autenticacion")
    _fijar_referencia(cobro, referencia_pasarela)
    await session.flush()
    return cobro


async def descartar_intento(session: AsyncSession, *, cobro: Cobro) -> Cobro:
    """El intento termino sin mover dinero. El siguiente usa otra clave."""
    if cobro.estado is not EstadoCobro.PENDIENTE:
        raise InvalidStateTransition(
            "Solo se descarta el intento de un cobro pendiente"
        )
    cobro.referencia_pasarela = None
    cobro.intentos += 1
    await session.flush()
    return cobro


async def posponer_intento(
    session: AsyncSession, *, cobro: Cobro, ahora: datetime
) -> Cobro:
    """El intento sigue esperando el 3DS: el barrido vuelve a consultarlo
    recien `abandono_3ds` despues de `ahora`, y no en cada vuelta."""
    if not esperando_autenticacion(cobro):
        raise InvalidStateTransition("Solo se pospone un intento que espera el 3DS")
    # Explicito: asignarlo evita que onupdate ponga la hora del reloj
    cobro.updated_at = ahora
    await session.flush()
    return cobro


async def reabrir_saldo_vencido(session: AsyncSession, *, cobro: Cobro) -> Cobro:
    """El saldo vencido vuelve a pendiente para autorizarlo otra vez. Conserva
    `autorizado_hasta`: de ahi sale el plazo de reautorizacion."""
    dominio.validar_transicion_cobro(cobro.estado, EstadoCobro.PENDIENTE)
    cobro.estado = EstadoCobro.PENDIENTE
    cobro.referencia_pasarela = None
    cobro.intentos += 1
    await session.flush()
    return cobro


def _fijar_referencia(cobro: Cobro, referencia: str | None) -> None:
    if referencia is None:
        if cobro.referencia_pasarela is None:
            raise ReglaDeNegocioViolada("Falta la referencia de la pasarela")
        return
    if cobro.referencia_pasarela not in (None, referencia):
        raise HechosInconsistentes("El cobro ya tiene otra referencia de pasarela")
    cobro.referencia_pasarela = referencia


def _nuevos_cobros(
    pedido_id: uuid.UUID, cotizacion: dominio.Cotizacion, pasarela: str
) -> list[Cobro]:
    return [
        Cobro(
            pedido_id=pedido_id,
            tipo=tipo,
            estado=EstadoCobro.PENDIENTE,
            monto=monto,
            monto_reembolsado=Decimal("0"),
            pasarela=pasarela,
        )
        for tipo, monto in cotizacion.cobros
    ]


async def _aplicar_plan(
    session: AsyncSession,
    pedido: Pedido,
    plan: PlanCobros,
    cobros: Sequence[Cobro],
    ahora: datetime,
) -> None:
    """Cada captura y cada reembolso se asientan en el ledger."""
    cambios: list[tuple[Cobro, dominio.AccionCobro, EstadoCobro]] = []
    for cobro in cobros:
        accion = plan.de(cobro.id)
        hacia = dominio.ESTADO_TRAS_ACCION[accion.accion] if accion else None
        if hacia is None:
            continue
        dominio.validar_transicion_cobro(cobro.estado, hacia)
        cambios.append((cobro, accion, hacia))

    for cobro, accion, hacia in cambios:
        cobro.estado = hacia
        if hacia is EstadoCobro.CAPTURADO:
            cobro.capturado_en = ahora
            await ledger.asentar_captura(
                session, pedido=pedido, cobro=cobro, ahora=ahora
            )
        if accion.accion is dominio.Accion.REEMBOLSAR:
            cobro.monto_reembolsado += accion.monto
            await ledger.asentar_reembolso(
                session, pedido=pedido, cobro=cobro, monto=accion.monto, ahora=ahora
            )


# Cotizacion


async def crear_pedido_desde_cotizacion(
    session: AsyncSession,
    *,
    consulta_id: uuid.UUID,
    tipo: TipoPedido,
    descripcion: str,
    monto_total: Decimal,
    pasarela: str,
    ahora: datetime,
    politicas: PoliticasPedido,
    anticipo_porcentaje: Decimal | None = None,
    fecha_evento: datetime | None = None,
    lugar_evento: str | None = None,
    fecha_entrega_estimada: datetime | None = None,
) -> Pedido:
    if tipo is TipoPedido.OBRA_DISPONIBLE:
        raise CotizacionInvalida("La obra disponible no se cotiza")
    # El perfil antes que la consulta: un cambio de plan no se cruza con la
    # tarifa que se congela en el pedido (D8)
    sin_bloqueo = await _obtener(session, Consulta, consulta_id)
    artista = await bloquear_perfil(session, sin_bloqueo.artista_id)
    consulta = await _bloquear(session, Consulta, consulta_id)
    dominio.validar_transicion_consulta(consulta.estado, EstadoConsulta.COTIZADA)
    dominio.validar_fecha_evento(tipo, fecha_evento, ahora)
    cotizacion = dominio.cotizar(tipo, monto_total, anticipo_porcentaje, politicas)

    pedido = Pedido(
        id=uuid.uuid4(),
        consulta_id=consulta.id,
        cliente_id=consulta.cliente_id,
        artista_id=consulta.artista_id,
        tipo=tipo,
        estado=EstadoPedido.COTIZADO,
        descripcion=descripcion,
        monto_total=cotizacion.monto_total,
        tarifa_porcentaje=dominio.tarifa_para_plan(artista.plan, politicas),
        anticipo_porcentaje=cotizacion.anticipo_porcentaje,
        fecha_evento=fecha_evento,
        lugar_evento=lugar_evento,
        fecha_entrega_estimada=fecha_entrega_estimada,
    )
    session.add(pedido)
    await session.flush()
    session.add_all(_nuevos_cobros(pedido.id, cotizacion, pasarela))
    consulta.estado = EstadoConsulta.COTIZADA
    await session.flush()
    return pedido


async def actualizar_cotizacion(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    descripcion: str,
    monto_total: Decimal,
    ahora: datetime,
    politicas: PoliticasPedido,
    anticipo_porcentaje: Decimal | None = None,
    fecha_evento: datetime | None = None,
    lugar_evento: str | None = None,
    fecha_entrega_estimada: datetime | None = None,
) -> Pedido:
    """Contraoferta: reemplaza la cotizacion del mismo pedido."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    if pedido.estado is not EstadoPedido.COTIZADO:
        raise InvalidStateTransition("Solo se actualiza una cotizacion vigente")
    if pedido.tipo is TipoPedido.OBRA_DISPONIBLE:
        raise CotizacionInvalida("El precio de una obra no se negocia aqui")
    dominio.validar_fecha_evento(pedido.tipo, fecha_evento, ahora)
    cotizacion = dominio.cotizar(
        pedido.tipo, monto_total, anticipo_porcentaje, politicas
    )
    cobros = await _cobros(session, pedido.id)
    if any(c.estado is not EstadoCobro.PENDIENTE for c in cobros):
        raise InvalidStateTransition("Hay cobros que ya no estan pendientes")
    # Un pago esperando el 3DS se hizo por el monto anterior
    if any(c.referencia_pasarela is not None for c in cobros):
        raise InvalidStateTransition("Hay un pago en curso: esperá a que termine")

    montos = dict(cotizacion.cobros)
    for cobro in cobros:
        cobro.monto = montos[cobro.tipo]
    pedido.descripcion = descripcion
    pedido.monto_total = cotizacion.monto_total
    pedido.anticipo_porcentaje = cotizacion.anticipo_porcentaje
    pedido.fecha_evento = fecha_evento
    pedido.lugar_evento = lugar_evento
    pedido.fecha_entrega_estimada = fecha_entrega_estimada
    await session.flush()
    return pedido


async def crear_pedido_obra_disponible(
    session: AsyncSession,
    *,
    obra_id: uuid.UUID,
    cliente_id: uuid.UUID,
    pasarela: str,
    politicas: PoliticasPedido,
) -> Pedido:
    """La quiero: consulta ya convertida, pedido cotizado y cobro total pendiente."""
    obra = await _obtener(session, Obra, obra_id)
    if obra.deleted_at is not None:
        raise ObraNoDisponible("La obra no esta disponible")
    dominio.validar_obra_pedible(obra.estado, obra.precio, obra.artista_id, cliente_id)
    cotizacion = dominio.cotizar(
        TipoPedido.OBRA_DISPONIBLE, obra.precio, None, politicas
    )
    artista = await _obtener(session, Profile, obra.artista_id)

    consulta = Consulta(
        id=uuid.uuid4(),
        cliente_id=cliente_id,
        artista_id=obra.artista_id,
        obra_id=obra.id,
        estado=EstadoConsulta.CONVERTIDA,
    )
    pedido = Pedido(
        id=uuid.uuid4(),
        consulta_id=consulta.id,
        cliente_id=cliente_id,
        artista_id=obra.artista_id,
        tipo=TipoPedido.OBRA_DISPONIBLE,
        estado=EstadoPedido.COTIZADO,
        descripcion=obra.titulo,
        monto_total=cotizacion.monto_total,
        tarifa_porcentaje=dominio.tarifa_para_plan(artista.plan, politicas),
        anticipo_porcentaje=None,
        obra_id=obra.id,
    )
    # El savepoint aisla el choque del indice parcial sin romper la transaccion
    try:
        async with session.begin_nested():
            session.add(consulta)
            await session.flush()
            session.add(pedido)
            await session.flush()
            session.add_all(_nuevos_cobros(pedido.id, cotizacion, pasarela))
            await session.flush()
    except IntegrityError as exc:
        diag = getattr(exc.orig, "diag", None)
        if getattr(diag, "constraint_name", None) == INDICE_OBRA_ACTIVA:
            raise ObraNoDisponible("La obra ya tiene un pedido en curso") from exc
        raise
    return pedido


async def rechazar_pedido(session: AsyncSession, *, pedido_id: uuid.UUID) -> Pedido:
    """El cliente rechaza o el artista retira la cotizacion."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.RECHAZADO)
    consulta = await _bloquear(session, Consulta, pedido.consulta_id)
    dominio.validar_transicion_consulta(consulta.estado, EstadoConsulta.DESCARTADA)
    cobros = await _cobros(session, pedido.id)
    for cobro in cobros:
        dominio.validar_transicion_cobro(cobro.estado, EstadoCobro.CANCELADO)

    for cobro in cobros:
        cobro.estado = EstadoCobro.CANCELADO
    consulta.estado = EstadoConsulta.DESCARTADA
    pedido.estado = EstadoPedido.RECHAZADO
    await session.flush()
    return pedido


# Encargo y evento


async def registrar_anticipo_capturado(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    referencia_pasarela: str,
    ahora: datetime,
) -> Pedido:
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.ANTICIPO_PAGADO)
    consulta = await _bloquear(session, Consulta, pedido.consulta_id)
    dominio.validar_transicion_consulta(consulta.estado, EstadoConsulta.CONVERTIDA)
    anticipo = _cobro(await _cobros(session, pedido.id), TipoCobro.ANTICIPO)
    dominio.validar_transicion_cobro(anticipo.estado, EstadoCobro.CAPTURADO)

    _fijar_referencia(anticipo, referencia_pasarela)
    anticipo.estado = EstadoCobro.CAPTURADO
    anticipo.capturado_en = ahora
    consulta.estado = EstadoConsulta.CONVERTIDA
    pedido.estado = EstadoPedido.ANTICIPO_PAGADO
    await ledger.asentar_captura(session, pedido=pedido, cobro=anticipo, ahora=ahora)
    return pedido


async def iniciar_trabajo(session: AsyncSession, *, pedido_id: uuid.UUID) -> Pedido:
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.EN_PROCESO)
    pedido.estado = EstadoPedido.EN_PROCESO
    await session.flush()
    return pedido


async def _medio_para_entregar(
    session: AsyncSession, pedido: Pedido, media_asset_id: uuid.UUID, bucket: str
) -> MediaAsset:
    """El medio del artista, subido, suelto, sin entregar y en `bucket`."""
    # Bloqueado: no se cruza con su borrado ni con otra entrega del mismo medio
    stmt = (
        select(MediaAsset)
        .where(
            MediaAsset.id == media_asset_id,
            MediaAsset.propietario_id == pedido.artista_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    medio = (await session.execute(stmt)).scalar_one_or_none()
    if medio is None:
        raise ResourceNotFound("Medio no encontrado")
    if medio.deleted_at is not None or medio.subido_en is None:
        raise ReglaDeNegocioViolada("El medio tiene que estar subido y sin borrar")
    if medio.obra_id is not None or medio.publicacion_id is not None:
        raise ReglaDeNegocioViolada(
            "El medio esta asociado a una obra o una publicacion"
        )
    if medio.bucket != bucket:
        raise ReglaDeNegocioViolada("El medio no esta en el bucket que corresponde")
    usado = await session.execute(
        select(Entregable.id).where(Entregable.media_asset_id == medio.id).limit(1)
    )
    if usado.first() is not None:
        raise ReglaDeNegocioViolada("El medio ya es un entregable")
    return medio


async def _crear_entregable(
    session: AsyncSession,
    pedido: Pedido,
    medio: MediaAsset,
    tipo: TipoEntregable,
    nota: str | None,
) -> Entregable:
    entregable = Entregable(
        pedido_id=pedido.id, media_asset_id=medio.id, tipo=tipo, nota=nota
    )
    session.add(entregable)
    await session.flush()
    return entregable


async def entregar_vista_previa(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    media_asset_id: uuid.UUID,
    bucket_publico: str,
    nota: str | None = None,
) -> Entregable:
    """Primer paso (D24): el artista sube la vista previa y el pedido sigue en
    en_proceso. Puede entregar varias, una por revision.

    El medio tiene que estar en `bucket_publico`: en el privado no se veria."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    # Solo un encargo en proceso puede pasar a vista_previa_entregada
    dominio.validar_transicion(
        pedido.tipo, pedido.estado, EstadoPedido.VISTA_PREVIA_ENTREGADA
    )
    medio = await _medio_para_entregar(session, pedido, media_asset_id, bucket_publico)
    return await _crear_entregable(
        session, pedido, medio, TipoEntregable.VISTA_PREVIA, nota
    )


ESTADOS_CON_FINAL = frozenset({EstadoPedido.SALDO_PAGADO, EstadoPedido.COMPLETADO})


def exigir_final_admitido(pedido: Pedido) -> None:
    """El archivo final es de un encargo con el saldo ya cobrado."""
    if pedido.tipo is not TipoPedido.ENCARGO or pedido.estado not in ESTADOS_CON_FINAL:
        raise InvalidStateTransition(
            "El archivo final se entrega en un encargo con el saldo pagado"
        )


async def entregar_final(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    media_asset_id: uuid.UUID,
    nota: str | None,
    bucket_privado: str,
) -> Entregable:
    """El archivo sin marca de agua, en el bucket privado. Puede haber varios."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    exigir_final_admitido(pedido)
    medio = await _medio_para_entregar(session, pedido, media_asset_id, bucket_privado)
    return await _crear_entregable(session, pedido, medio, TipoEntregable.FINAL, nota)


async def entregable_del_pedido(
    session: AsyncSession, pedido_id: uuid.UUID, entregable_id: uuid.UUID
) -> tuple[Entregable, MediaAsset]:
    stmt = (
        select(Entregable, MediaAsset)
        .join(MediaAsset, MediaAsset.id == Entregable.media_asset_id)
        .where(Entregable.id == entregable_id, Entregable.pedido_id == pedido_id)
    )
    fila = (await session.execute(stmt)).one_or_none()
    if fila is None:
        raise ResourceNotFound("Entregable no encontrado")
    entregable, medio = fila
    return entregable, medio


async def exigir_vista_previa(session: AsyncSession, pedido_id: uuid.UUID) -> None:
    stmt = (
        select(Entregable.id)
        .where(
            Entregable.pedido_id == pedido_id,
            Entregable.tipo == TipoEntregable.VISTA_PREVIA,
        )
        .limit(1)
    )
    if (await session.execute(stmt)).first() is None:
        raise ReglaDeNegocioViolada("El artista todavia no entrego una vista previa")


async def registrar_saldo_autorizado(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    referencia_pasarela: str,
    autorizado_hasta: datetime,
    ahora: datetime,
) -> Pedido:
    """Segundo paso (D24): el cliente vio la vista previa y autorizo el saldo.
    Si el pedido ya esta ahi, es la reautorizacion de un saldo vencido."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    if pedido.estado is not EstadoPedido.VISTA_PREVIA_ENTREGADA:
        dominio.validar_transicion(
            pedido.tipo, pedido.estado, EstadoPedido.VISTA_PREVIA_ENTREGADA
        )
    if autorizado_hasta <= ahora:
        raise ReglaDeNegocioViolada("La autorizacion del saldo ya vencio")
    await exigir_vista_previa(session, pedido.id)
    saldo = _cobro(await _cobros(session, pedido.id), TipoCobro.SALDO)
    dominio.validar_transicion_cobro(saldo.estado, EstadoCobro.AUTORIZADO)

    _fijar_referencia(saldo, referencia_pasarela)
    saldo.estado = EstadoCobro.AUTORIZADO
    saldo.autorizado_hasta = autorizado_hasta
    pedido.estado = EstadoPedido.VISTA_PREVIA_ENTREGADA
    await session.flush()
    return pedido


async def registrar_saldo_capturado(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    ahora: datetime,
    politicas: PoliticasPedido,
    referencia_pasarela: str | None = None,
) -> Pedido:
    """Encargo: captura lo autorizado en la vista previa. Evento: cobra directo."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.SALDO_PAGADO)
    if pedido.tipo is TipoPedido.OBRA_DISPONIBLE:
        raise InvalidStateTransition("La obra disponible se cobra en el despacho")
    saldo = _cobro(await _cobros(session, pedido.id), TipoCobro.SALDO)
    dominio.validar_transicion_cobro(saldo.estado, EstadoCobro.CAPTURADO)
    disputable_hasta = dominio.calcular_disputable_hasta(
        pedido.tipo, ahora, pedido.fecha_evento, politicas
    )

    _fijar_referencia(saldo, referencia_pasarela)
    saldo.estado = EstadoCobro.CAPTURADO
    saldo.capturado_en = ahora
    pedido.estado = EstadoPedido.SALDO_PAGADO
    pedido.disputable_hasta = disputable_hasta
    await ledger.asentar_captura(session, pedido=pedido, cobro=saldo, ahora=ahora)
    return pedido


# Obra disponible


async def confirmar_obra(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    referencia_pasarela: str,
    autorizado_hasta: datetime,
    ahora: datetime,
) -> Pedido:
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.EN_PROCESO)
    if autorizado_hasta <= ahora:
        raise ReglaDeNegocioViolada("La autorizacion ya vencio")
    consulta = await _bloquear(session, Consulta, pedido.consulta_id)
    total = _cobro(await _cobros(session, pedido.id), TipoCobro.TOTAL)
    dominio.validar_transicion_cobro(total.estado, EstadoCobro.AUTORIZADO)

    _fijar_referencia(total, referencia_pasarela)
    total.estado = EstadoCobro.AUTORIZADO
    total.autorizado_hasta = autorizado_hasta
    # La consulta nace convertida en La quiero; esto solo la sostiene ahi
    if consulta.estado is not EstadoConsulta.CONVERTIDA:
        dominio.validar_transicion_consulta(consulta.estado, EstadoConsulta.CONVERTIDA)
        consulta.estado = EstadoConsulta.CONVERTIDA
    pedido.estado = EstadoPedido.EN_PROCESO
    await session.flush()
    return pedido


async def registrar_despacho(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    guia_envio: str,
    ahora: datetime,
    politicas: PoliticasPedido,
    referencia_pasarela: str | None = None,
) -> Pedido:
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.SALDO_PAGADO)
    if pedido.tipo is not TipoPedido.OBRA_DISPONIBLE or pedido.obra_id is None:
        raise InvalidStateTransition("Solo una obra disponible se despacha")
    if not guia_envio.strip():
        raise ReglaDeNegocioViolada("El despacho necesita numero de guia")
    total = _cobro(await _cobros(session, pedido.id), TipoCobro.TOTAL)
    dominio.validar_transicion_cobro(total.estado, EstadoCobro.CAPTURADO)
    obra = await _bloquear(session, Obra, pedido.obra_id)
    disputable_hasta = dominio.calcular_disputable_hasta(
        pedido.tipo, ahora, pedido.fecha_evento, politicas
    )

    _fijar_referencia(total, referencia_pasarela)
    total.estado = EstadoCobro.CAPTURADO
    total.capturado_en = ahora
    obra.estado = EstadoObra.VENDIDA
    pedido.guia_envio = guia_envio
    pedido.estado = EstadoPedido.SALDO_PAGADO
    pedido.disputable_hasta = disputable_hasta
    await ledger.asentar_captura(session, pedido=pedido, cobro=total, ahora=ahora)
    return pedido


# Cancelacion


async def planear_cancelacion(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    actor_id: uuid.UUID,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PlanCobros:
    """Lo que quien llama debe ejecutar en la pasarela antes de cancelar_pedido."""
    pedido = await _obtener(session, Pedido, pedido_id)
    rol = dominio.rol_en_pedido(actor_id, pedido.cliente_id, pedido.artista_id)
    return dominio.planear_cancelacion(
        pedido.tipo,
        pedido.estado,
        rol,
        await _cobros(session, pedido.id),
        pedido.fecha_evento,
        ahora,
        politicas,
    )


async def cancelar_pedido(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    actor_id: uuid.UUID,
    hechos: HechosPasarela,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PlanCobros:
    """Recalcula el plan bajo bloqueo, exige que los hechos lo cumplan y lo aplica."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    rol: Rol = dominio.rol_en_pedido(actor_id, pedido.cliente_id, pedido.artista_id)
    cobros = await _cobros(session, pedido.id)
    plan = dominio.planear_cancelacion(
        pedido.tipo, pedido.estado, rol, cobros, pedido.fecha_evento, ahora, politicas
    )
    dominio.verificar_hechos(plan, hechos)

    await _aplicar_plan(session, pedido, plan, cobros, ahora)
    pedido.estado = EstadoPedido.CANCELADO
    await session.flush()
    return plan


# Disputa


async def abrir_disputa(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    actor_id: uuid.UUID,
    motivo: str,
    ahora: datetime,
) -> Disputa:
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.rol_en_pedido(actor_id, pedido.cliente_id, pedido.artista_id)
    dominio.validar_apertura_disputa(
        pedido.tipo, pedido.estado, pedido.disputable_hasta, ahora
    )
    if not motivo.strip():
        raise ReglaDeNegocioViolada("La disputa necesita un motivo")

    disputa = Disputa(
        pedido_id=pedido.id,
        abierta_por_id=actor_id,
        motivo=motivo,
        estado=EstadoDisputa.ABIERTA,
    )
    session.add(disputa)
    pedido.estado = EstadoPedido.EN_DISPUTA
    await session.flush()
    return disputa


async def planear_resolucion(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    destino: EstadoPedido,
    reembolsos: Mapping[uuid.UUID, Decimal],
) -> PlanCobros:
    """Lo que quien llama debe ejecutar en la pasarela antes de resolver_disputa."""
    pedido = await _obtener(session, Pedido, pedido_id)
    return dominio.planear_resolucion(
        pedido.tipo,
        pedido.estado,
        destino,
        await _cobros(session, pedido.id),
        reembolsos,
    )


async def resolver_disputa(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    destino: EstadoPedido,
    resolucion: str,
    admin_id: uuid.UUID,
    hechos: HechosPasarela,
    ahora: datetime,
) -> Disputa:
    """Moderacion cierra la disputa. Los reembolsos de los hechos son su orden."""
    admin = await _obtener(session, Profile, admin_id)
    if admin.rol is not RolPerfil.ADMIN:
        raise ActorNoAutorizado("Solo moderacion resuelve una disputa")
    pedido = await _bloquear(session, Pedido, pedido_id)
    stmt = (
        select(Disputa)
        .where(Disputa.pedido_id == pedido.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    disputa = (await session.execute(stmt)).scalar_one_or_none()
    if disputa is None or disputa.estado is EstadoDisputa.RESUELTA:
        raise InvalidStateTransition("El pedido no tiene una disputa abierta")
    cobros = await _cobros(session, pedido.id)
    plan = dominio.planear_resolucion(
        pedido.tipo, pedido.estado, destino, cobros, hechos.reembolsos
    )
    dominio.verificar_hechos(plan, hechos)

    await _aplicar_plan(session, pedido, plan, cobros, ahora)
    disputa.estado = EstadoDisputa.RESUELTA
    disputa.resolucion = resolucion
    disputa.resuelta_por_id = admin.id
    disputa.resuelta_en = ahora
    pedido.estado = destino
    await session.flush()
    return disputa


# Vencimientos


async def completar_vencidos(session: AsyncSession, *, ahora: datetime) -> int:
    """Completa los pedidos en saldo_pagado cuya ventana de disputa ya vencio."""
    stmt = (
        select(Pedido)
        .where(
            Pedido.estado == EstadoPedido.SALDO_PAGADO,
            Pedido.disputable_hasta < ahora,
        )
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    pedidos = list((await session.execute(stmt)).scalars())
    for pedido in pedidos:
        dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.COMPLETADO)
        pedido.estado = EstadoPedido.COMPLETADO
    await session.flush()
    return len(pedidos)


async def registrar_autorizacion_vencida(
    session: AsyncSession, *, pedido_id: uuid.UUID, cobro_id: uuid.UUID, ahora: datetime
) -> Cobro:
    """La pasarela ya no retiene la autorizacion: la libero o vencio sola."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    cobros = await _cobros(session, pedido.id)
    cobro = next((c for c in cobros if c.id == cobro_id), None)
    if cobro is None:
        raise ResourceNotFound("Cobro no encontrado")
    dominio.validar_transicion_cobro(cobro.estado, EstadoCobro.VENCIDO)
    if cobro.autorizado_hasta is None or cobro.autorizado_hasta > ahora:
        raise ReglaDeNegocioViolada("La autorizacion todavia no vencio")
    cobro.estado = EstadoCobro.VENCIDO
    await session.flush()
    return cobro


async def cancelar_por_vencimiento(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    hechos: HechosPasarela,
    ahora: datetime,
) -> PlanCobros:
    """Como cancelar_pedido, pero sin actor: lo cancela el barrido."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    cobros = await _cobros(session, pedido.id)
    plan = dominio.planear_vencimiento(pedido.tipo, pedido.estado, cobros)
    dominio.verificar_hechos(plan, hechos)

    await _aplicar_plan(session, pedido, plan, cobros, ahora)
    pedido.estado = EstadoPedido.CANCELADO
    await session.flush()
    return plan


TOPE_CANDIDATOS = 100


@dataclass(frozen=True)
class CandidatosVencimiento:
    """Ids de pedido por caso. Lectura sin bloqueo: cada operacion vuelve a
    comprobar la condicion con el pedido bloqueado."""

    la_quiero_abandonados: tuple[uuid.UUID, ...]
    autorizaciones_vencidas: tuple[uuid.UUID, ...]
    reautorizaciones_vencidas: tuple[uuid.UUID, ...]
    eventos_impagos: tuple[uuid.UUID, ...]
    # Referencias de cobro, no ids de pedido: intentos que esperan el 3DS hace
    # mas de `abandono_3ds`, con o sin webhook
    intentos_en_espera: tuple[str, ...]


async def _ids[T](session: AsyncSession, stmt: Select[tuple[T]]) -> tuple[T, ...]:
    filas = await session.execute(stmt.limit(TOPE_CANDIDATOS))
    # Sin repetidos y en el orden de la consulta
    return tuple(dict.fromkeys(filas.scalars()))


async def candidatos_vencimiento(
    session: AsyncSession, *, ahora: datetime, politicas: PoliticasPedido
) -> CandidatosVencimiento:
    con_cobro = select(Pedido.id).join(Cobro, Cobro.pedido_id == Pedido.id)
    la_quiero = (
        con_cobro.where(
            Pedido.tipo == TipoPedido.OBRA_DISPONIBLE,
            Pedido.estado == EstadoPedido.COTIZADO,
            Cobro.tipo == TipoCobro.TOTAL,
            Cobro.estado == EstadoCobro.PENDIENTE,
            Cobro.referencia_pasarela.is_not(None),
            Pedido.created_at <= ahora - politicas.abandono_3ds,
        )
    ).order_by(Pedido.created_at)
    autorizaciones = (
        con_cobro.where(
            Cobro.estado == EstadoCobro.AUTORIZADO,
            Cobro.autorizado_hasta <= ahora,
            or_(
                and_(
                    Pedido.tipo == TipoPedido.ENCARGO,
                    Pedido.estado == EstadoPedido.VISTA_PREVIA_ENTREGADA,
                ),
                and_(
                    Pedido.tipo == TipoPedido.OBRA_DISPONIBLE,
                    Pedido.estado == EstadoPedido.EN_PROCESO,
                ),
            ),
        )
    ).order_by(Cobro.autorizado_hasta)
    reautorizaciones = (
        con_cobro.where(
            Pedido.tipo == TipoPedido.ENCARGO,
            Pedido.estado == EstadoPedido.VISTA_PREVIA_ENTREGADA,
            Cobro.tipo == TipoCobro.SALDO,
            Cobro.estado.in_((EstadoCobro.VENCIDO, EstadoCobro.PENDIENTE)),
            Cobro.autorizado_hasta <= ahora - politicas.plazo_reautorizacion_saldo,
        )
    ).order_by(Cobro.autorizado_hasta)
    eventos = (
        select(Pedido.id)
        .where(
            Pedido.tipo == TipoPedido.EVENTO,
            Pedido.estado == EstadoPedido.ANTICIPO_PAGADO,
            Pedido.fecha_evento <= ahora,
        )
        .order_by(Pedido.fecha_evento)
    )
    # Fuera los que tienen su propio caso, que concilia el intento antes de
    # cerrar: La quiero cotizado, la reautorizacion vencida y el evento impago
    con_caso_propio = union(
        reautorizaciones.order_by(None), eventos.order_by(None)
    ).subquery()
    en_espera = (
        select(Cobro.referencia_pasarela)
        .join(Pedido, Pedido.id == Cobro.pedido_id)
        .where(
            Cobro.estado == EstadoCobro.PENDIENTE,
            Cobro.referencia_pasarela.is_not(None),
            Cobro.updated_at <= ahora - politicas.abandono_3ds,
            Pedido.estado.not_in(dominio.ESTADOS_TERMINALES),
            not_(
                and_(
                    Pedido.tipo == TipoPedido.OBRA_DISPONIBLE,
                    Pedido.estado == EstadoPedido.COTIZADO,
                )
            ),
            Pedido.id.not_in(select(con_caso_propio.c.id)),
        )
        .order_by(Cobro.updated_at)
    )
    return CandidatosVencimiento(
        la_quiero_abandonados=await _ids(session, la_quiero),
        autorizaciones_vencidas=await _ids(session, autorizaciones),
        reautorizaciones_vencidas=await _ids(session, reautorizaciones),
        eventos_impagos=await _ids(session, eventos),
        intentos_en_espera=await _ids(session, en_espera),
    )


# Lectura. Un pedido en el que no participa quien pide da 404.


def participa(usuario_id: uuid.UUID) -> ColumnElement[bool]:
    return or_(Pedido.cliente_id == usuario_id, Pedido.artista_id == usuario_id)


async def _perfiles(
    session: AsyncSession, pedidos: Sequence[Pedido]
) -> dict[uuid.UUID, Profile]:
    ids = {p.cliente_id for p in pedidos} | {p.artista_id for p in pedidos}
    filas = await session.execute(select(Profile).where(Profile.id.in_(ids)))
    return {p.id: p for p in filas.scalars()}


async def _cobros_de(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Cobro]]:
    stmt = select(Cobro).where(Cobro.pedido_id.in_(ids)).order_by(Cobro.tipo)
    por_pedido: dict[uuid.UUID, list[Cobro]] = defaultdict(list)
    for cobro in (await session.execute(stmt)).scalars():
        por_pedido[cobro.pedido_id].append(cobro)
    return por_pedido


async def _entregables_de(
    session: AsyncSession, ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, list[VistaPrevia]], dict[uuid.UUID, list[EntregableFinal]]]:
    """Vistas previas y finales en una sola consulta."""
    stmt = (
        select(Entregable, MediaAsset)
        .join(MediaAsset, MediaAsset.id == Entregable.media_asset_id)
        .where(Entregable.pedido_id.in_(ids))
        .order_by(Entregable.created_at, Entregable.id)
    )
    vistas: dict[uuid.UUID, list[VistaPrevia]] = defaultdict(list)
    finales: dict[uuid.UUID, list[EntregableFinal]] = defaultdict(list)
    for entregable, medio in await session.execute(stmt):
        if entregable.tipo is TipoEntregable.FINAL:
            finales[entregable.pedido_id].append(EntregableFinal(entregable, medio))
        else:
            vistas[entregable.pedido_id].append(VistaPrevia(entregable, medio))
    return vistas, finales


async def _disputas_de(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, Disputa]:
    stmt = select(Disputa).where(Disputa.pedido_id.in_(ids))
    return {d.pedido_id: d for d in (await session.execute(stmt)).scalars()}


async def _detallar(
    session: AsyncSession, pedidos: Sequence[Pedido], usuario: Profile | None
) -> list[PedidoDetalle]:
    """Perfiles, cobros, entregables y disputa de una pagina entera, sin N+1.
    Sin usuario mira moderacion: `soy` queda nulo."""
    if not pedidos:
        return []
    ids = [p.id for p in pedidos]
    perfiles = await _perfiles(session, pedidos)
    cobros = await _cobros_de(session, ids)
    vistas, finales = await _entregables_de(session, ids)
    disputas = await _disputas_de(session, ids)
    return [
        PedidoDetalle(
            pedido=p,
            cliente=perfiles[p.cliente_id],
            artista=perfiles[p.artista_id],
            soy=None
            if usuario is None
            else dominio.rol_en_pedido(usuario.id, p.cliente_id, p.artista_id),
            cobros=cobros.get(p.id, []),
            vistas_previas=vistas.get(p.id, []),
            finales=finales.get(p.id, []),
            disputa=disputas.get(p.id),
        )
        for p in pedidos
    ]


async def detallar(
    session: AsyncSession, pedidos: Sequence[Pedido], usuario: Profile
) -> list[PedidoDetalle]:
    return await _detallar(session, pedidos, usuario)


async def detallar_uno(
    session: AsyncSession, pedido: Pedido, usuario: Profile
) -> PedidoDetalle:
    return (await detallar(session, [pedido], usuario))[0]


async def pedido_existente(session: AsyncSession, pedido_id: uuid.UUID) -> Pedido:
    """Sin bloquear y sin control de participante: solo para moderacion."""
    pedido = (
        await session.execute(select(Pedido).where(Pedido.id == pedido_id))
    ).scalar_one_or_none()
    if pedido is None:
        raise ResourceNotFound(NO_ENCONTRADO)
    return pedido


async def disputa_del_pedido(
    session: AsyncSession, pedido_id: uuid.UUID
) -> Disputa | None:
    """Releida de la base. Quien la cambia ya bloqueo el pedido."""
    stmt = (
        select(Disputa)
        .where(Disputa.pedido_id == pedido_id)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def pedido_visible(
    session: AsyncSession, usuario: Profile, pedido_id: uuid.UUID
) -> Pedido:
    """Sin bloquear. Si quien pide no participa, 404 para no revelar que existe."""
    stmt = select(Pedido).where(Pedido.id == pedido_id, participa(usuario.id))
    pedido = (await session.execute(stmt)).scalar_one_or_none()
    if pedido is None:
        raise ResourceNotFound(NO_ENCONTRADO)
    return pedido


async def detalle(
    session: AsyncSession, usuario: Profile, pedido_id: uuid.UUID
) -> PedidoDetalle:
    pedido = await pedido_visible(session, usuario, pedido_id)
    return await detallar_uno(session, pedido, usuario)


async def listar(
    session: AsyncSession,
    usuario: Profile,
    como: Rol | None,
    estado: EstadoPedido | None,
    consulta_id: uuid.UUID | None,
    parametros: ParametrosPagina,
) -> tuple[list[PedidoDetalle], str | None]:
    """Los pedidos de quien mira, del mas nuevo al mas viejo."""
    if como is Rol.CLIENTE:
        filtro = Pedido.cliente_id == usuario.id
    elif como is Rol.ARTISTA:
        filtro = Pedido.artista_id == usuario.id
    else:
        filtro = participa(usuario.id)
    stmt = select(Pedido).where(filtro)
    if estado is not None:
        stmt = stmt.where(Pedido.estado == estado)
    if consulta_id is not None:
        stmt = stmt.where(Pedido.consulta_id == consulta_id)
    pedidos, siguiente = await traer_pagina(session, stmt, Pedido, parametros)
    return await detallar(session, pedidos, usuario), siguiente


# Lectura para moderacion. Sin control de participante: la API exige un admin.


async def detalle_para_moderacion(
    session: AsyncSession, pedido_id: uuid.UUID
) -> PedidoDetalle:
    pedido = await pedido_existente(session, pedido_id)
    return (await _detallar(session, [pedido], None))[0]


async def disputas_abiertas(
    session: AsyncSession, parametros: ParametrosPagina
) -> tuple[list[PedidoDetalle], str | None]:
    """Los pedidos en disputa, de la disputa mas vieja a la mas nueva. El cursor
    va sobre la fecha de la disputa."""
    stmt = (
        select(Disputa)
        .join(Pedido, Pedido.id == Disputa.pedido_id)
        .where(
            Disputa.estado == EstadoDisputa.ABIERTA,
            Pedido.estado == EstadoPedido.EN_DISPUTA,
        )
    )
    disputas, siguiente = await traer_pagina(
        session, stmt, Disputa, parametros, ascendente=True
    )
    if not disputas:
        return [], siguiente
    filas = await session.execute(
        select(Pedido).where(Pedido.id.in_([d.pedido_id for d in disputas]))
    )
    por_id = {p.id: p for p in filas.scalars()}
    pedidos = [por_id[d.pedido_id] for d in disputas]
    return await _detallar(session, pedidos, None), siguiente
