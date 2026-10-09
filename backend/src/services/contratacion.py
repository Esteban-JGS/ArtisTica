"""Contratacion: la unica capa que llama a la pasarela por un pedido.

Primero valida, despues llama a la pasarela y recien despues registra con
`src.services.pedidos`. Hace flush y nunca commit: confirma quien llama. No lee
la configuracion ni el reloj: recibe la pasarela, `ahora`, las politicas, la
url de retorno y el nombre de la pasarela.

Bloqueos en el orden de todo el backend (D18, D21): perfil del artista,
pedido, consulta, obra. Las claves de idempotencia son deterministas: si la
pasarela movio el dinero y el commit falla, el reintento repite la clave y la
pasarela devuelve el mismo resultado. Nunca se cobra dos veces.

Un pago con 3DS (D23) se registra solo cuando `consultar_cobro` lo confirma.
Que el cliente vuelva del banco no prueba nada.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    ActorNoAutorizado,
    CobroNoHabilitado,
    FueraDePlazo,
    HechosInconsistentes,
    InvalidStateTransition,
    ReglaDeNegocioViolada,
    ResourceNotFound,
)
from src.domain import pedidos as dominio
from src.domain.pedidos import Accion, HechosPasarela, Rol
from src.domain.politicas import PoliticasPedido
from src.models import (
    Cobro,
    Consulta,
    EstadoCobro,
    EstadoPedido,
    Obra,
    Pedido,
    Profile,
    TipoCobro,
    TipoPedido,
)
from src.payments.contrato import (
    ConsultaCobro,
    EstadoCobroPasarela,
    EstadoOperacion,
    MetodoPago,
    PasarelaDePagos,
    SolicitudCobro,
)
from src.payments.errores import AutorizacionVencida, PagoRechazado
from src.services import pedidos
from src.services.pedidos import PedidoDetalle
from src.services.perfiles import bloquear_perfil, exigir_cobro_habilitado

MENSAJE_RECHAZO = "La pasarela rechazo el pago. Proba con otra tarjeta"
MENSAJE_AUTENTICACION = (
    "El banco no aprobo la autenticacion. Proba de nuevo o con otra tarjeta"
)
MENSAJE_NO_VIGENTE = "El cobro ya no esta vigente"


class Resultado(enum.StrEnum):
    COMPLETADO = "completado"
    # El cliente tiene que autenticarse en el banco (3DS) y despues verificar
    REQUIERE_ACCION = "requiere_accion"
    PENDIENTE = "pendiente"
    # Un resultado normal: el cliente reintenta con otra tarjeta
    RECHAZADO = "rechazado"


@dataclass(frozen=True)
class ResultadoPago:
    resultado: Resultado
    # Nulos solo en La quiero rechazado: no queda pedido
    pedido: PedidoDetalle | None
    cobro: Cobro | None
    # Solo con REQUIERE_ACCION. Sensible: va solo al cliente que paga
    url_autenticacion: str | None = field(default=None, repr=False)
    mensaje: str | None = None


class Operacion(enum.StrEnum):
    COBRAR = "cobrar"
    AUTORIZAR = "autorizar"


# Que operacion inicia cada cobro, y que estado espera de la pasarela
_OPERACIONES: dict[tuple[TipoPedido, TipoCobro], Operacion] = {
    (TipoPedido.ENCARGO, TipoCobro.ANTICIPO): Operacion.COBRAR,
    (TipoPedido.EVENTO, TipoCobro.ANTICIPO): Operacion.COBRAR,
    (TipoPedido.ENCARGO, TipoCobro.SALDO): Operacion.AUTORIZAR,
    (TipoPedido.EVENTO, TipoCobro.SALDO): Operacion.COBRAR,
    (TipoPedido.OBRA_DISPONIBLE, TipoCobro.TOTAL): Operacion.AUTORIZAR,
}
_ESPERADO_OPERACION = {
    Operacion.COBRAR: EstadoOperacion.CAPTURADO,
    Operacion.AUTORIZAR: EstadoOperacion.AUTORIZADO,
}
_ESPERADO_CONSULTA = {
    Operacion.COBRAR: EstadoCobroPasarela.CAPTURADO,
    Operacion.AUTORIZAR: EstadoCobroPasarela.AUTORIZADO,
}
# El intento sigue vivo en la pasarela: se puede liberar
_EN_CURSO = frozenset(
    {
        EstadoCobroPasarela.REQUIERE_ACCION,
        EstadoCobroPasarela.PENDIENTE,
        EstadoCobroPasarela.AUTORIZADO,
    }
)
_SIN_DINERO = frozenset({EstadoCobroPasarela.FALLIDO, EstadoCobroPasarela.LIBERADO})


@dataclass(frozen=True)
class _Contexto:
    session: AsyncSession
    pasarela: PasarelaDePagos
    usuario: Profile
    ahora: datetime
    politicas: PoliticasPedido


# Claves de idempotencia


def _clave_inicio(operacion: Operacion, cobro: Cobro) -> str:
    return f"{operacion}-{cobro.id}-{cobro.intentos}"


def _clave_captura(cobro: Cobro) -> str:
    return f"capturar-{cobro.id}"


def _clave_liberacion(cobro: Cobro) -> str:
    return f"liberar-{cobro.id}-{cobro.intentos}"


def _clave_reembolso(cobro: Cobro, monto: Decimal) -> str:
    return f"reembolsar-{cobro.id}-{monto}"


# Permisos y bloqueos


def _exigir_rol(pedido: Pedido, usuario: Profile, *roles: Rol) -> Rol:
    rol = dominio.rol_en_pedido(usuario.id, pedido.cliente_id, pedido.artista_id)
    if rol not in roles:
        raise ActorNoAutorizado(f"Esta operacion no le corresponde al {rol}")
    return rol


async def _visible(ctx: _Contexto, pedido_id: uuid.UUID, *roles: Rol) -> Pedido:
    """Sin bloquear: un tercero recibe 404 y una parte sin permiso, 403."""
    pedido = await pedidos.pedido_visible(ctx.session, ctx.usuario, pedido_id)
    _exigir_rol(pedido, ctx.usuario, *roles)
    return pedido


async def _bloquear(ctx: _Contexto, pedido: Pedido) -> tuple[Profile, Pedido]:
    artista = await bloquear_perfil(ctx.session, pedido.artista_id)
    return artista, await pedidos.bloquear_pedido(ctx.session, pedido.id)


def _cuenta(artista: Profile) -> str:
    if artista.pasarela_cuenta_id is None:
        raise CobroNoHabilitado("El artista no tiene una cuenta de cobro")
    return artista.pasarela_cuenta_id


async def _tarifa(
    pasarela: PasarelaDePagos, artista: Profile, pedido: Pedido
) -> Decimal | None:
    """D8: la tarifa congelada en el pedido. Por cobro si la pasarela lo admite;
    si no, en la cuenta conectada, justo antes de mover el dinero."""
    if pasarela.capacidades.comision_por_cobro:
        return pedido.tarifa_porcentaje
    await pasarela.configurar_tarifa(_cuenta(artista), pedido.tarifa_porcentaje)
    return None


# Resultados


async def _resultado(
    ctx: _Contexto,
    pedido: Pedido,
    cobro: Cobro,
    resultado: Resultado,
    *,
    url: str | None = None,
    mensaje: str | None = None,
) -> ResultadoPago:
    detalle = await pedidos.detallar_uno(ctx.session, pedido, ctx.usuario)
    return ResultadoPago(resultado, detalle, cobro, url, mensaje)


async def _estado_actual(ctx: _Contexto, pedido: Pedido, cobro: Cobro) -> ResultadoPago:
    """Lo que dice la base de un cobro sin intento en curso."""
    if cobro.estado in (
        EstadoCobro.AUTORIZADO,
        EstadoCobro.CAPTURADO,
        EstadoCobro.REEMBOLSADO,
    ):
        return await _resultado(ctx, pedido, cobro, Resultado.COMPLETADO)
    if cobro.estado is EstadoCobro.PENDIENTE:
        if cobro.intentos == 0:
            return await _resultado(ctx, pedido, cobro, Resultado.PENDIENTE)
        return await _resultado(
            ctx, pedido, cobro, Resultado.RECHAZADO, mensaje=MENSAJE_RECHAZO
        )
    return await _resultado(
        ctx, pedido, cobro, Resultado.RECHAZADO, mensaje=MENSAJE_NO_VIGENTE
    )


# Registro de lo que la pasarela confirmo


def _operacion(pedido: Pedido, cobro: Cobro) -> Operacion:
    operacion = _OPERACIONES.get((pedido.tipo, cobro.tipo))
    if operacion is None:
        raise InvalidStateTransition(f"Un {pedido.tipo} no tiene cobro de {cobro.tipo}")
    return operacion


async def _registrar(
    ctx: _Contexto,
    pedido: Pedido,
    cobro: Cobro,
    *,
    referencia: str,
    autorizado_hasta: datetime | None,
) -> None:
    session, ahora, politicas = ctx.session, ctx.ahora, ctx.politicas
    if cobro.tipo is TipoCobro.ANTICIPO:
        await pedidos.registrar_anticipo_capturado(
            session, pedido_id=pedido.id, referencia_pasarela=referencia, ahora=ahora
        )
    elif pedido.tipo is TipoPedido.ENCARGO:
        await pedidos.registrar_saldo_autorizado(
            session,
            pedido_id=pedido.id,
            referencia_pasarela=referencia,
            autorizado_hasta=politicas.vencimiento_autorizacion(
                autorizado_hasta, ahora
            ),
            ahora=ahora,
        )
    elif pedido.tipo is TipoPedido.EVENTO:
        await pedidos.registrar_saldo_capturado(
            session,
            pedido_id=pedido.id,
            ahora=ahora,
            politicas=politicas,
            referencia_pasarela=referencia,
        )
    else:
        await pedidos.confirmar_obra(
            session,
            pedido_id=pedido.id,
            referencia_pasarela=referencia,
            autorizado_hasta=politicas.vencimiento_autorizacion(
                autorizado_hasta, ahora
            ),
            ahora=ahora,
        )


def _exigir_coherencia(cobro: Cobro, monto: Decimal, *, estado_esperado: bool) -> None:
    if not estado_esperado or monto != cobro.monto:
        raise HechosInconsistentes("La pasarela informa otro resultado para este cobro")


# Intentos de cobro


async def _seguir_intento(
    ctx: _Contexto, pedido: Pedido, cobro: Cobro
) -> ResultadoPago | None:
    """El intento que espera el 3DS, segun `consultar_cobro`. None si termino
    sin dinero: el cobro queda listo para un intento nuevo."""
    operacion = _operacion(pedido, cobro)
    foto = await ctx.pasarela.consultar_cobro(cobro.referencia_pasarela)
    if foto.estado is EstadoCobroPasarela.REQUIERE_ACCION:
        return await _resultado(
            ctx, pedido, cobro, Resultado.REQUIERE_ACCION, url=foto.url_autenticacion
        )
    if foto.estado is EstadoCobroPasarela.PENDIENTE:
        return await _resultado(ctx, pedido, cobro, Resultado.PENDIENTE)
    if foto.estado in _SIN_DINERO:
        await pedidos.descartar_intento(ctx.session, cobro=cobro)
        return None
    _exigir_coherencia(
        cobro,
        foto.monto,
        estado_esperado=foto.estado is _ESPERADO_CONSULTA[operacion],
    )
    await _registrar(
        ctx,
        pedido,
        cobro,
        referencia=foto.referencia,
        autorizado_hasta=foto.autorizado_hasta,
    )
    return await _resultado(ctx, pedido, cobro, Resultado.COMPLETADO)


async def _iniciar_cobro(
    ctx: _Contexto,
    artista: Profile,
    pedido: Pedido,
    cobro: Cobro,
    metodo_pago_id: str,
    url_retorno: str,
) -> ResultadoPago:
    """Con el perfil y el pedido bloqueados y la transicion ya validada."""
    exigir_cobro_habilitado(artista)
    # Un intento anterior espera el 3DS: no se abre otro hasta saber como termino
    if cobro.referencia_pasarela is not None:
        previo = await _seguir_intento(ctx, pedido, cobro)
        if previo is not None:
            return previo

    operacion = _operacion(pedido, cobro)
    tarifa = await _tarifa(ctx.pasarela, artista, pedido)
    solicitud = SolicitudCobro(
        monto=cobro.monto,
        moneda=pedido.moneda,
        metodo=MetodoPago.TARJETA,
        cuenta_conectada_id=_cuenta(artista),
        clave_idempotencia=_clave_inicio(operacion, cobro),
        descripcion=f"{cobro.tipo} del pedido {pedido.id}",
        tarifa_porcentaje=tarifa,
        metadatos={"pedido_id": str(pedido.id), "cobro_id": str(cobro.id)},
        medio_pago_id=metodo_pago_id,
        url_retorno=url_retorno,
    )
    iniciar = (
        ctx.pasarela.cobrar if operacion is Operacion.COBRAR else ctx.pasarela.autorizar
    )
    try:
        resultado = await iniciar(solicitud)
    except PagoRechazado:
        # No se levanta: la API confirma el intento consumido
        await pedidos.descartar_intento(ctx.session, cobro=cobro)
        return await _resultado(
            ctx, pedido, cobro, Resultado.RECHAZADO, mensaje=MENSAJE_RECHAZO
        )

    if resultado.estado is EstadoOperacion.REQUIERE_ACCION:
        await pedidos.registrar_intento_en_espera(
            ctx.session, cobro=cobro, referencia_pasarela=resultado.referencia
        )
        return await _resultado(
            ctx,
            pedido,
            cobro,
            Resultado.REQUIERE_ACCION,
            url=resultado.url_autenticacion,
        )
    _exigir_coherencia(
        cobro,
        resultado.monto,
        estado_esperado=resultado.estado is _ESPERADO_OPERACION[operacion],
    )
    await _registrar(
        ctx,
        pedido,
        cobro,
        referencia=resultado.referencia,
        autorizado_hasta=resultado.autorizado_hasta,
    )
    return await _resultado(ctx, pedido, cobro, Resultado.COMPLETADO)


async def _capturar(
    ctx: _Contexto, artista: Profile, pedido: Pedido, cobro: Cobro, vencida: str
) -> str:
    """Captura lo autorizado. Devuelve la referencia para registrar."""
    referencia = cobro.referencia_pasarela
    if cobro.estado is not EstadoCobro.AUTORIZADO or referencia is None:
        raise InvalidStateTransition(f"El {cobro.tipo} no esta autorizado")
    await _tarifa(ctx.pasarela, artista, pedido)
    try:
        resultado = await ctx.pasarela.capturar(
            referencia, clave_idempotencia=_clave_captura(cobro)
        )
    except AutorizacionVencida as exc:
        # Reautorizar es el lote 9
        raise FueraDePlazo(vencida) from exc
    _exigir_coherencia(
        cobro,
        resultado.monto,
        estado_esperado=resultado.estado is EstadoOperacion.CAPTURADO,
    )
    return referencia


async def _soltar_intentos_en_espera(ctx: _Contexto, cobros: list[Cobro]) -> None:
    """Libera en la pasarela los intentos pendientes de 3DS de un pedido que se
    cierra. Si alguno ya cobro, falla antes de liberar nada."""
    en_espera = [
        c
        for c in cobros
        if c.estado is EstadoCobro.PENDIENTE and c.referencia_pasarela is not None
    ]
    fotos: list[tuple[Cobro, ConsultaCobro]] = [
        (c, await ctx.pasarela.consultar_cobro(c.referencia_pasarela))
        for c in en_espera
    ]
    if any(f.estado is EstadoCobroPasarela.CAPTURADO for _, f in fotos):
        raise InvalidStateTransition(
            "Un pago de este pedido ya se completo: verificalo antes de cerrarlo"
        )
    for cobro, foto in fotos:
        if foto.estado in _EN_CURSO:
            await ctx.pasarela.liberar_autorizacion(
                cobro.referencia_pasarela, clave_idempotencia=_clave_liberacion(cobro)
            )


# Cotizacion


async def cotizar(
    session: AsyncSession,
    usuario: Profile,
    consulta_id: uuid.UUID,
    *,
    tipo: TipoPedido,
    descripcion: str,
    monto_total: Decimal,
    anticipo_porcentaje: Decimal | None,
    fecha_evento: datetime | None,
    lugar_evento: str | None,
    fecha_entrega_estimada: datetime | None,
    ahora: datetime,
    politicas: PoliticasPedido,
    nombre_pasarela: str,
) -> PedidoDetalle:
    consulta = await session.get(Consulta, consulta_id)
    if consulta is None or usuario.id not in (consulta.cliente_id, consulta.artista_id):
        raise ResourceNotFound("Consulta no encontrada")
    if usuario.id != consulta.artista_id:
        raise ActorNoAutorizado("Solo el artista de la consulta cotiza")
    pedido = await pedidos.crear_pedido_desde_cotizacion(
        session,
        consulta_id=consulta.id,
        tipo=tipo,
        descripcion=descripcion,
        monto_total=monto_total,
        pasarela=nombre_pasarela,
        ahora=ahora,
        politicas=politicas,
        anticipo_porcentaje=anticipo_porcentaje,
        fecha_evento=fecha_evento,
        lugar_evento=lugar_evento,
        fecha_entrega_estimada=fecha_entrega_estimada,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


async def actualizar_cotizacion(
    session: AsyncSession,
    usuario: Profile,
    pedido_id: uuid.UUID,
    *,
    descripcion: str,
    monto_total: Decimal,
    anticipo_porcentaje: Decimal | None,
    fecha_evento: datetime | None,
    lugar_evento: str | None,
    fecha_entrega_estimada: datetime | None,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PedidoDetalle:
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.ARTISTA)
    await pedidos.actualizar_cotizacion(
        session,
        pedido_id=pedido.id,
        descripcion=descripcion,
        monto_total=monto_total,
        ahora=ahora,
        politicas=politicas,
        anticipo_porcentaje=anticipo_porcentaje,
        fecha_evento=fecha_evento,
        lugar_evento=lugar_evento,
        fecha_entrega_estimada=fecha_entrega_estimada,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


async def rechazar(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PedidoDetalle:
    """El cliente rechaza o el artista retira la cotizacion."""
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    visto = await _visible(ctx, pedido_id, Rol.CLIENTE, Rol.ARTISTA)
    _, pedido = await _bloquear(ctx, visto)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.RECHAZADO)
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    for cobro in cobros:
        dominio.validar_transicion_cobro(cobro.estado, EstadoCobro.CANCELADO)

    await _soltar_intentos_en_espera(ctx, cobros)
    await pedidos.rechazar_pedido(session, pedido_id=pedido.id)
    return await pedidos.detallar_uno(session, pedido, usuario)


# Encargo y evento


async def pagar_anticipo(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    pedido_id: uuid.UUID,
    metodo_pago_id: str,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
    url_retorno: str,
) -> ResultadoPago:
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    visto = await _visible(ctx, pedido_id, Rol.CLIENTE)
    artista, pedido = await _bloquear(ctx, visto)
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.ANTICIPO_PAGADO)
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    anticipo = pedidos.cobro_de_tipo(cobros, TipoCobro.ANTICIPO)
    dominio.validar_transicion_cobro(anticipo.estado, EstadoCobro.CAPTURADO)
    return await _iniciar_cobro(
        ctx, artista, pedido, anticipo, metodo_pago_id, url_retorno
    )


async def iniciar_trabajo(
    session: AsyncSession, usuario: Profile, pedido_id: uuid.UUID
) -> PedidoDetalle:
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.ARTISTA)
    await pedidos.iniciar_trabajo(session, pedido_id=pedido.id)
    return await pedidos.detallar_uno(session, pedido, usuario)


async def entregar_vista_previa(
    session: AsyncSession,
    usuario: Profile,
    pedido_id: uuid.UUID,
    medio_id: uuid.UUID,
    nota: str | None,
) -> PedidoDetalle:
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.ARTISTA)
    await pedidos.entregar_vista_previa(
        session, pedido_id=pedido.id, media_asset_id=medio_id, nota=nota
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


async def pagar_saldo(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    pedido_id: uuid.UUID,
    metodo_pago_id: str,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
    url_retorno: str,
) -> ResultadoPago:
    """Encargo: autoriza el saldo al ver la vista previa. Evento: lo cobra."""
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    visto = await _visible(ctx, pedido_id, Rol.CLIENTE)
    artista, pedido = await _bloquear(ctx, visto)
    if pedido.tipo is TipoPedido.ENCARGO:
        dominio.validar_transicion(
            pedido.tipo, pedido.estado, EstadoPedido.VISTA_PREVIA_ENTREGADA
        )
        await pedidos.exigir_vista_previa(session, pedido.id)
        hacia = EstadoCobro.AUTORIZADO
    elif pedido.tipo is TipoPedido.EVENTO:
        dominio.validar_transicion(
            pedido.tipo, pedido.estado, EstadoPedido.SALDO_PAGADO
        )
        hacia = EstadoCobro.CAPTURADO
    else:
        raise InvalidStateTransition("Una obra disponible no tiene saldo")
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    saldo = pedidos.cobro_de_tipo(cobros, TipoCobro.SALDO)
    dominio.validar_transicion_cobro(saldo.estado, hacia)
    return await _iniciar_cobro(
        ctx, artista, pedido, saldo, metodo_pago_id, url_retorno
    )


async def aprobar(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PedidoDetalle:
    """El cliente aprueba la vista previa: se captura el saldo autorizado."""
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    visto = await _visible(ctx, pedido_id, Rol.CLIENTE)
    artista, pedido = await _bloquear(ctx, visto)
    if pedido.tipo is not TipoPedido.ENCARGO:
        raise InvalidStateTransition("Solo se aprueba la vista previa de un encargo")
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.SALDO_PAGADO)
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    saldo = pedidos.cobro_de_tipo(cobros, TipoCobro.SALDO)

    referencia = await _capturar(
        ctx, artista, pedido, saldo, "La autorizacion del saldo vencio"
    )
    await pedidos.registrar_saldo_capturado(
        session,
        pedido_id=pedido.id,
        ahora=ahora,
        politicas=politicas,
        referencia_pasarela=referencia,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


# Obra disponible


async def la_quiero(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    obra_id: uuid.UUID,
    metodo_pago_id: str,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
    url_retorno: str,
    nombre_pasarela: str,
) -> ResultadoPago:
    """Crea el pedido y autoriza el total en la misma transaccion.

    Si la pasarela rechaza, el resultado no trae pedido y quien llama no
    confirma: no queda nada y la obra sigue libre.
    """
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    stmt = select(Obra).where(Obra.id == obra_id, Obra.deleted_at.is_(None))
    obra = (await session.execute(stmt)).scalar_one_or_none()
    if obra is None:
        raise ResourceNotFound("Obra no encontrada")
    artista = await bloquear_perfil(session, obra.artista_id)
    creado = await pedidos.crear_pedido_obra_disponible(
        session,
        obra_id=obra.id,
        cliente_id=usuario.id,
        pasarela=nombre_pasarela,
        politicas=politicas,
    )
    pedido = await pedidos.bloquear_pedido(session, creado.id)
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    total = pedidos.cobro_de_tipo(cobros, TipoCobro.TOTAL)

    resultado = await _iniciar_cobro(
        ctx, artista, pedido, total, metodo_pago_id, url_retorno
    )
    if resultado.resultado is Resultado.RECHAZADO:
        return ResultadoPago(Resultado.RECHAZADO, None, None, mensaje=resultado.mensaje)
    return resultado


async def despachar(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    pedido_id: uuid.UUID,
    guia_envio: str,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PedidoDetalle:
    """El artista despacha con numero de guia: se captura el total."""
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    visto = await _visible(ctx, pedido_id, Rol.ARTISTA)
    artista, pedido = await _bloquear(ctx, visto)
    if pedido.tipo is not TipoPedido.OBRA_DISPONIBLE:
        raise InvalidStateTransition("Solo una obra disponible se despacha")
    dominio.validar_transicion(pedido.tipo, pedido.estado, EstadoPedido.SALDO_PAGADO)
    if not guia_envio.strip():
        raise ReglaDeNegocioViolada("El despacho necesita numero de guia")
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    total = pedidos.cobro_de_tipo(cobros, TipoCobro.TOTAL)

    referencia = await _capturar(
        ctx, artista, pedido, total, "La autorizacion del total vencio"
    )
    await pedidos.registrar_despacho(
        session,
        pedido_id=pedido.id,
        guia_envio=guia_envio,
        ahora=ahora,
        politicas=politicas,
        referencia_pasarela=referencia,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


# Cierre


async def cancelar(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PedidoDetalle:
    """Ejecuta el plan de cancelacion en la pasarela y despues lo registra.

    Si una llamada falla a mitad de camino, la excepcion sube y no se registra
    nada. Las claves fijas hacen que el reintento no libere ni reembolse dos
    veces.
    """
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    visto = await _visible(ctx, pedido_id, Rol.CLIENTE, Rol.ARTISTA)
    _, pedido = await _bloquear(ctx, visto)
    rol = _exigir_rol(pedido, usuario, Rol.CLIENTE, Rol.ARTISTA)
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    plan = dominio.planear_cancelacion(
        pedido.tipo, pedido.estado, rol, cobros, pedido.fecha_evento, ahora, politicas
    )
    por_id = {c.id: c for c in cobros}
    for accion in plan.acciones:
        hacia = dominio.ESTADO_TRAS_ACCION[accion.accion]
        if hacia is not None:
            dominio.validar_transicion_cobro(por_id[accion.cobro_id].estado, hacia)

    # Fuera del plan, que trata al pendiente como CANCELAR sin pasarela
    await _soltar_intentos_en_espera(ctx, cobros)
    liberados: set[uuid.UUID] = set()
    reembolsos: dict[uuid.UUID, Decimal] = {}
    for accion in plan.acciones:
        cobro = por_id[accion.cobro_id]
        if accion.accion is Accion.LIBERAR_AUTORIZACION:
            await pasarela.liberar_autorizacion(
                cobro.referencia_pasarela, clave_idempotencia=_clave_liberacion(cobro)
            )
            liberados.add(cobro.id)
        elif accion.accion is Accion.REEMBOLSAR and accion.monto is not None:
            await pasarela.reembolsar(
                cobro.referencia_pasarela,
                monto=accion.monto,
                clave_idempotencia=_clave_reembolso(cobro, accion.monto),
            )
            reembolsos[cobro.id] = accion.monto

    await pedidos.cancelar_pedido(
        session,
        pedido_id=pedido.id,
        actor_id=usuario.id,
        hechos=HechosPasarela(liberados=frozenset(liberados), reembolsos=reembolsos),
        ahora=ahora,
        politicas=politicas,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


async def abrir_disputa(
    session: AsyncSession,
    usuario: Profile,
    pedido_id: uuid.UUID,
    motivo: str,
    *,
    ahora: datetime,
) -> PedidoDetalle:
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    await pedidos.abrir_disputa(
        session, pedido_id=pedido.id, actor_id=usuario.id, motivo=motivo, ahora=ahora
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


# Verificacion despues del 3DS


async def verificar_cobro(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    usuario: Profile,
    cobro_id: uuid.UUID,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> ResultadoPago:
    """Lo que la app llama al volver del banco. El estado sale de la pasarela."""
    ctx = _Contexto(session, pasarela, usuario, ahora, politicas)
    stmt = (
        select(Pedido)
        .join(Cobro, Cobro.pedido_id == Pedido.id)
        .where(Cobro.id == cobro_id, pedidos.participa(usuario.id))
    )
    visto = (await session.execute(stmt)).scalar_one_or_none()
    if visto is None:
        raise ResourceNotFound("Cobro no encontrado")
    # La url de autenticacion es solo para el cliente que paga
    _exigir_rol(visto, usuario, Rol.CLIENTE)
    _, pedido = await _bloquear(ctx, visto)
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    cobro = next(c for c in cobros if c.id == cobro_id)

    if cobro.estado is not EstadoCobro.PENDIENTE or cobro.referencia_pasarela is None:
        return await _estado_actual(ctx, pedido, cobro)
    seguido = await _seguir_intento(ctx, pedido, cobro)
    if seguido is not None:
        return seguido
    if pedido.tipo is TipoPedido.OBRA_DISPONIBLE:
        # Como en La quiero rechazado: la obra no queda tomada por un pago fallido
        await pedidos.rechazar_pedido(session, pedido_id=pedido.id)
    return await _resultado(
        ctx, pedido, cobro, Resultado.RECHAZADO, mensaje=MENSAJE_AUTENTICACION
    )
