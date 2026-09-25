"""Aplica las reglas del dominio de pedidos sobre la base.

No cierra la transaccion: hace flush, y la abre y la cierra quien llama.
Bloquea el pedido con SELECT ... FOR UPDATE antes de cambiarlo.
No llama a la pasarela: recibe los hechos que la pasarela ya confirmo.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
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

INDICE_OBRA_ACTIVA = "ux_pedidos_obra_activa"


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


def _aplicar_plan(plan: PlanCobros, cobros: Sequence[Cobro], ahora: datetime) -> None:
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
        if accion.accion is dominio.Accion.REEMBOLSAR:
            cobro.monto_reembolsado += accion.monto


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
    consulta = await _bloquear(session, Consulta, consulta_id)
    dominio.validar_transicion_consulta(consulta.estado, EstadoConsulta.COTIZADA)
    dominio.validar_fecha_evento(tipo, fecha_evento, ahora)
    cotizacion = dominio.cotizar(tipo, monto_total, anticipo_porcentaje, politicas)
    artista = await _obtener(session, Profile, consulta.artista_id)

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
    await session.flush()
    return pedido


async def iniciar_trabajo(session: AsyncSession, *, pedido_id: uuid.UUID) -> Pedido:
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.EN_PROCESO)
    pedido.estado = EstadoPedido.EN_PROCESO
    await session.flush()
    return pedido


async def registrar_vista_previa(
    session: AsyncSession,
    *,
    pedido_id: uuid.UUID,
    media_asset_id: uuid.UUID,
    referencia_pasarela: str,
    autorizado_hasta: datetime,
    ahora: datetime,
    nota: str | None = None,
) -> Entregable:
    """Vista previa con marca de agua y saldo autorizado, en un solo paso."""
    pedido = await _bloquear(session, Pedido, pedido_id)
    dominio.validar_transicion(
        pedido.tipo, pedido.estado, EstadoPedido.VISTA_PREVIA_ENTREGADA
    )
    if autorizado_hasta <= ahora:
        raise ReglaDeNegocioViolada("La autorizacion del saldo ya vencio")
    media = await _obtener(session, MediaAsset, media_asset_id)
    if media.propietario_id != pedido.artista_id:
        raise ActorNoAutorizado("La vista previa no es del artista del pedido")
    saldo = _cobro(await _cobros(session, pedido.id), TipoCobro.SALDO)
    dominio.validar_transicion_cobro(saldo.estado, EstadoCobro.AUTORIZADO)

    entregable = Entregable(
        pedido_id=pedido.id,
        media_asset_id=media.id,
        tipo=TipoEntregable.VISTA_PREVIA,
        nota=nota,
    )
    session.add(entregable)
    _fijar_referencia(saldo, referencia_pasarela)
    saldo.estado = EstadoCobro.AUTORIZADO
    saldo.autorizado_hasta = autorizado_hasta
    pedido.estado = EstadoPedido.VISTA_PREVIA_ENTREGADA
    await session.flush()
    return entregable


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
    await session.flush()
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
    await session.flush()
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

    _aplicar_plan(plan, cobros, ahora)
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

    _aplicar_plan(plan, cobros, ahora)
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
