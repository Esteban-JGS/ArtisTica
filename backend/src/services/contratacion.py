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

Antes de ejecutar un plan de cierre consulta cada cobro que toca y toma como
hecho lo que ya este hecho (DT28): un reintento con otro plan nunca mueve
dinero dos veces. `conciliar_cobro` solo consulta: lo usan los webhooks y el
barrido.

Tambien controla quien sube y descarga el archivo final: recibe el
almacenamiento, los buckets y la vigencia de la descarga.
"""

import enum
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
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
from src.domain.pedidos import Accion, AccionCobro, HechosPasarela, Rol
from src.domain.politicas import PoliticasPedido
from src.models import (
    Cobro,
    Consulta,
    EstadoCobro,
    EstadoDisputa,
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
from src.payments.contrato import (
    ConsultaCobro,
    EstadoCobroPasarela,
    EstadoOperacion,
    MetodoPago,
    PasarelaDePagos,
    SolicitudCobro,
)
from src.payments.errores import (
    AutorizacionVencida,
    OperacionNoSoportada,
    PagoRechazado,
    SolicitudInvalida,
)
from src.services import medios, pedidos
from src.services.pedidos import PedidoDetalle
from src.services.perfiles import bloquear_perfil, exigir_cobro_habilitado
from src.storage.contrato import Almacenamiento, DescargaFirmada, SubidaFirmada

logger = logging.getLogger(__name__)

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
# El cliente todavia no termino el 3DS
_EN_ESPERA = frozenset(
    {EstadoCobroPasarela.REQUIERE_ACCION, EstadoCobroPasarela.PENDIENTE}
)


@dataclass(frozen=True)
class _Entorno:
    """Lo necesario para mover dinero y registrarlo. Lo usa tambien el barrido,
    que no actua por ningun usuario."""

    session: AsyncSession
    pasarela: PasarelaDePagos
    ahora: datetime
    politicas: PoliticasPedido


@dataclass(frozen=True)
class _Contexto(_Entorno):
    """Una operacion de la API: el usuario arma la respuesta que ve."""

    usuario: Profile


# Claves de idempotencia


def _clave_inicio(operacion: Operacion, cobro: Cobro) -> str:
    return f"{operacion}-{cobro.id}-{cobro.intentos}"


def _clave_captura(cobro: Cobro) -> str:
    return f"capturar-{cobro.id}"


def _clave_liberacion(cobro: Cobro) -> str:
    return f"liberar-{cobro.id}-{cobro.intentos}"


def _clave_reembolso(cobro: Cobro, hasta: Decimal) -> str:
    """`hasta` es el total reembolsado en la pasarela al terminar la llamada.
    Repetir la misma operacion da la misma clave; un plan distinto despues de
    un reembolso parcial da otra."""
    return f"reembolsar-{cobro.id}-{dominio.cuantizar(hasta)}"


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


async def _bloquear(ctx: _Entorno, pedido: Pedido) -> tuple[Profile, Pedido]:
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
    ctx: _Entorno,
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


async def _resolver_intento(
    ctx: _Entorno, pedido: Pedido, cobro: Cobro
) -> ConsultaCobro:
    """Consulta el intento que espera el 3DS y registra lo que la pasarela
    confirma. Devuelve la foto de la pasarela:

    - requiere_accion o pendiente: sigue en espera, no se toca nada;
    - fallido o liberado: termino sin dinero y el cobro queda listo para otro
      intento;
    - cualquier otro: se registro como lo habria hecho el pago directo.
    """
    operacion = _operacion(pedido, cobro)
    foto = await ctx.pasarela.consultar_cobro(cobro.referencia_pasarela)
    if foto.estado in _EN_ESPERA:
        return foto
    if foto.estado in _SIN_DINERO:
        await pedidos.descartar_intento(ctx.session, cobro=cobro)
        return foto
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
    return foto


async def _en_espera(
    ctx: _Contexto, pedido: Pedido, cobro: Cobro, url: str | None
) -> ResultadoPago:
    """Sin url no hay nada que abrir: la app solo puede volver a verificar."""
    if url is None:
        return await _resultado(ctx, pedido, cobro, Resultado.PENDIENTE)
    return await _resultado(ctx, pedido, cobro, Resultado.REQUIERE_ACCION, url=url)


async def _seguir_intento(
    ctx: _Contexto, pedido: Pedido, cobro: Cobro
) -> ResultadoPago | None:
    """El intento que espera el 3DS, segun `consultar_cobro`. None si termino
    sin dinero: el cobro queda listo para un intento nuevo."""
    foto = await _resolver_intento(ctx, pedido, cobro)
    if foto.estado in _SIN_DINERO:
        return None
    if foto.estado is EstadoCobroPasarela.REQUIERE_ACCION:
        return await _en_espera(ctx, pedido, cobro, foto.url_autenticacion)
    if foto.estado is EstadoCobroPasarela.PENDIENTE:
        return await _resultado(ctx, pedido, cobro, Resultado.PENDIENTE)
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
        return await _en_espera(ctx, pedido, cobro, resultado.url_autenticacion)
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
    ctx: _Entorno, artista: Profile, pedido: Pedido, cobro: Cobro, vencida: str
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
        # El barrido la marca vencida y el cliente puede volver a autorizarla
        raise FueraDePlazo(vencida) from exc
    _exigir_coherencia(
        cobro,
        resultado.monto,
        estado_esperado=resultado.estado is EstadoOperacion.CAPTURADO,
    )
    return referencia


async def _soltar_intentos_en_espera(ctx: _Entorno, cobros: list[Cobro]) -> None:
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


# Planes de cierre (DT28). Primero se consultan todos los cobros que el plan
# toca y recien despues se mueve dinero: un 409 de aca no deja nada a medias.

_DE_PASARELA = frozenset(
    {Accion.CAPTURAR, Accion.LIBERAR_AUTORIZACION, Accion.REEMBOLSAR}
)
_VENCIDA_EN_DISPUTA = (
    "La autorizacion vencio: no se puede completar capturando; resolver como "
    "cancelado o con reembolso"
)
_YA_CAPTURADO = (
    "El {tipo} ya se cobro en la pasarela: resolver como completado o con reembolso"
)


@dataclass(frozen=True)
class _Paso:
    """Una accion del plan segun la foto de la pasarela."""

    accion: AccionCobro
    cobro: Cobro
    # False: un intento anterior ya lo hizo y no se vuelve a llamar
    llamar: bool
    # Solo en un reembolso: lo que se devuelve ahora y el total al terminar
    monto: Decimal | None = None
    hasta: Decimal | None = None


def _otro_estado(cobro: Cobro) -> HechosInconsistentes:
    return HechosInconsistentes(f"La pasarela informa otro estado para el {cobro.tipo}")


def _paso_reembolso(accion: AccionCobro, cobro: Cobro, foto: ConsultaCobro) -> _Paso:
    """Lo devuelto en la pasarela y no registrado viene de un intento anterior:
    se descuenta de lo ordenado."""
    ordenado = accion.monto
    informado = foto.monto_reembolsado
    if informado is None:
        logger.warning(
            "No se pudo verificar lo ya reembolsado del cobro %s: la pasarela no "
            "informa el acumulado",
            cobro.id,
        )
        return _Paso(
            accion,
            cobro,
            llamar=True,
            monto=ordenado,
            hasta=cobro.monto_reembolsado + ordenado,
        )
    previo = informado - cobro.monto_reembolsado
    if previo == ordenado:
        return _Paso(accion, cobro, llamar=False)
    if previo > ordenado:
        raise HechosInconsistentes(
            f"La pasarela ya devolvio del {cobro.tipo} mas de lo ordenado"
        )
    if previo < 0:
        raise _otro_estado(cobro)
    falta = ordenado - previo
    return _Paso(accion, cobro, llamar=True, monto=falta, hasta=informado + falta)


def _paso(accion: AccionCobro, cobro: Cobro, foto: ConsultaCobro) -> _Paso:
    estado = foto.estado
    if accion.accion is Accion.CAPTURAR:
        if estado is EstadoCobroPasarela.AUTORIZADO:
            return _Paso(accion, cobro, llamar=True)
        if (
            estado is EstadoCobroPasarela.CAPTURADO
            and foto.monto == cobro.monto
            and foto.monto_capturado in (None, cobro.monto)
        ):
            return _Paso(accion, cobro, llamar=False)
        if estado in _SIN_DINERO:
            raise FueraDePlazo(_VENCIDA_EN_DISPUTA)
    elif accion.accion is Accion.LIBERAR_AUTORIZACION:
        if estado in _EN_CURSO:
            return _Paso(accion, cobro, llamar=True)
        if estado in _SIN_DINERO:
            return _Paso(accion, cobro, llamar=False)
        if estado is EstadoCobroPasarela.CAPTURADO:
            raise InvalidStateTransition(_YA_CAPTURADO.format(tipo=cobro.tipo))
    elif accion.monto is not None and estado is EstadoCobroPasarela.CAPTURADO:
        return _paso_reembolso(accion, cobro, foto)
    raise _otro_estado(cobro)


async def _consultar_plan(
    ctx: _Entorno, acciones: Sequence[AccionCobro], por_id: Mapping[uuid.UUID, Cobro]
) -> list[_Paso]:
    """Los pasos de pasarela del plan, en el orden recibido. Solo consulta."""
    pasos: list[_Paso] = []
    for accion in acciones:
        if accion.accion not in _DE_PASARELA:
            continue
        cobro = por_id[accion.cobro_id]
        if cobro.referencia_pasarela is None:
            raise HechosInconsistentes(f"El {cobro.tipo} no tiene referencia de pago")
        foto = await ctx.pasarela.consultar_cobro(cobro.referencia_pasarela)
        pasos.append(_paso(accion, cobro, foto))
    return pasos


async def _liberar_y_reembolsar(
    ctx: _Entorno, pasos: Sequence[_Paso]
) -> HechosPasarela:
    """Ejecuta las liberaciones y los reembolsos. Los hechos son los del plan
    completo: lo que ya estaba hecho cuenta como hecho."""
    liberados: set[uuid.UUID] = set()
    reembolsos: dict[uuid.UUID, Decimal] = {}
    for paso in pasos:
        cobro, accion = paso.cobro, paso.accion
        if accion.accion is Accion.LIBERAR_AUTORIZACION:
            if paso.llamar:
                await ctx.pasarela.liberar_autorizacion(
                    cobro.referencia_pasarela,
                    clave_idempotencia=_clave_liberacion(cobro),
                )
            liberados.add(cobro.id)
        elif accion.accion is Accion.REEMBOLSAR:
            if paso.llamar:
                await ctx.pasarela.reembolsar(
                    cobro.referencia_pasarela,
                    monto=paso.monto,
                    clave_idempotencia=_clave_reembolso(cobro, paso.hasta),
                )
            reembolsos[cobro.id] = accion.monto
    return HechosPasarela(liberados=frozenset(liberados), reembolsos=reembolsos)


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
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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
    *,
    bucket_publico: str,
) -> PedidoDetalle:
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.ARTISTA)
    await pedidos.entregar_vista_previa(
        session,
        pedido_id=pedido.id,
        media_asset_id=medio_id,
        nota=nota,
        bucket_publico=bucket_publico,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


# Archivo final del encargo, en el bucket privado (D12)


async def solicitar_subida_final(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    usuario: Profile,
    pedido_id: uuid.UUID,
    content_type: str,
    tamano_bytes: int,
    *,
    bucket_privado: str,
    maximo_pendientes: int,
) -> tuple[MediaAsset, SubidaFirmada]:
    """Firma la subida del archivo final. Se confirma como cualquier medio."""
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.ARTISTA)
    pedidos.exigir_final_admitido(pedido)
    return await medios.solicitar_subida(
        session,
        almacenamiento,
        usuario,
        content_type,
        tamano_bytes,
        maximo_pendientes=maximo_pendientes,
        bucket=bucket_privado,
    )


async def entregar_final(
    session: AsyncSession,
    usuario: Profile,
    pedido_id: uuid.UUID,
    medio_id: uuid.UUID,
    nota: str | None,
    *,
    bucket_privado: str,
) -> PedidoDetalle:
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.ARTISTA)
    await pedidos.entregar_final(
        session,
        pedido_id=pedido.id,
        media_asset_id=medio_id,
        nota=nota,
        bucket_privado=bucket_privado,
    )
    return await pedidos.detallar_uno(session, pedido, usuario)


async def descargar_entregable(
    session: AsyncSession,
    almacenamiento: Almacenamiento,
    usuario: Profile,
    pedido_id: uuid.UUID,
    entregable_id: uuid.UUID,
    *,
    segundos: int,
) -> DescargaFirmada:
    """URL firmada del archivo final, solo para el cliente o el artista."""
    pedido = await pedidos.pedido_visible(session, usuario, pedido_id)
    _exigir_rol(pedido, usuario, Rol.CLIENTE, Rol.ARTISTA)
    entregable, medio = await pedidos.entregable_del_pedido(
        session, pedido.id, entregable_id
    )
    if entregable.tipo is not TipoEntregable.FINAL:
        raise ReglaDeNegocioViolada(
            "Solo se descarga un archivo final: la vista previa ya viene en el pedido"
        )
    return await almacenamiento.firmar_descarga(
        medio.bucket, medio.storage_path, segundos=segundos
    )


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
    """Encargo: autoriza el saldo al ver la vista previa, o lo vuelve a
    autorizar si vencio. Evento: lo cobra antes de su fecha."""
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
    visto = await _visible(ctx, pedido_id, Rol.CLIENTE)
    artista, pedido = await _bloquear(ctx, visto)
    if pedido.tipo is TipoPedido.OBRA_DISPONIBLE:
        raise InvalidStateTransition("Una obra disponible no tiene saldo")
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    saldo = pedidos.cobro_de_tipo(cobros, TipoCobro.SALDO)
    if pedido.tipo is TipoPedido.EVENTO:
        dominio.validar_transicion(
            pedido.tipo, pedido.estado, EstadoPedido.SALDO_PAGADO
        )
        dominio.validar_saldo_evento_a_tiempo(pedido.fecha_evento, ahora)
        hacia = EstadoCobro.CAPTURADO
    elif pedido.estado is EstadoPedido.VISTA_PREVIA_ENTREGADA:
        dominio.validar_reautorizacion(
            pedido.estado, saldo.estado, saldo.autorizado_hasta, ahora, politicas
        )
        if saldo.estado is EstadoCobro.VENCIDO:
            await pedidos.reabrir_saldo_vencido(session, cobro=saldo)
        hacia = EstadoCobro.AUTORIZADO
    else:
        dominio.validar_transicion(
            pedido.tipo, pedido.estado, EstadoPedido.VISTA_PREVIA_ENTREGADA
        )
        await pedidos.exigir_vista_previa(session, pedido.id)
        hacia = EstadoCobro.AUTORIZADO
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
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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
    nada. El reintento consulta antes cada cobro (DT28): no libera ni
    reembolsa dos veces.
    """
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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

    pasos = await _consultar_plan(ctx, plan.acciones, por_id)
    # Fuera del plan, que trata al pendiente como CANCELAR sin pasarela
    await _soltar_intentos_en_espera(ctx, cobros)
    hechos = await _liberar_y_reembolsar(ctx, pasos)
    await pedidos.cancelar_pedido(
        session,
        pedido_id=pedido.id,
        actor_id=usuario.id,
        hechos=hechos,
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


# Primero lo que puede fallar por una regla del negocio, como una autorizacion
# vencida: asi no se reembolsa ni se libera nada de un plan que no se completa
_ORDEN_RESOLUCION = (
    Accion.CAPTURAR,
    Accion.LIBERAR_AUTORIZACION,
    Accion.REEMBOLSAR,
)


async def resolver_disputa(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    admin: Profile,
    pedido_id: uuid.UUID,
    *,
    destino: EstadoPedido,
    resolucion: str,
    reembolsos: Mapping[uuid.UUID, Decimal],
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PedidoDetalle:
    """Moderacion cierra la disputa: ejecuta el plan en la pasarela y despues
    lo registra.

    Si una llamada falla a mitad de camino, la excepcion sube y no se registra
    nada. El reintento consulta antes cada cobro (DT28): no captura, libera ni
    reembolsa dos veces, aunque moderacion cambie el plan.
    """
    if destino not in (EstadoPedido.COMPLETADO, EstadoPedido.CANCELADO):
        raise ReglaDeNegocioViolada("Una disputa se resuelve completada o cancelada")
    if admin.rol is not RolPerfil.ADMIN:
        raise ActorNoAutorizado("Solo moderacion resuelve una disputa")
    ctx = _Contexto(session, pasarela, ahora, politicas, admin)
    visto = await pedidos.pedido_existente(session, pedido_id)
    artista, pedido = await _bloquear(ctx, visto)
    disputa = await pedidos.disputa_del_pedido(session, pedido.id)
    if disputa is None or disputa.estado is not EstadoDisputa.ABIERTA:
        raise InvalidStateTransition("El pedido no tiene una disputa abierta")
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    plan = dominio.planear_resolucion(
        pedido.tipo, pedido.estado, destino, cobros, reembolsos
    )
    por_id = {c.id: c for c in cobros}
    for accion in plan.acciones:
        hacia = dominio.ESTADO_TRAS_ACCION[accion.accion]
        if hacia is not None:
            dominio.validar_transicion_cobro(por_id[accion.cobro_id].estado, hacia)

    acciones = sorted(
        (a for a in plan.acciones if a.accion in _ORDEN_RESOLUCION),
        key=lambda a: _ORDEN_RESOLUCION.index(a.accion),
    )
    pasos = await _consultar_plan(ctx, acciones, por_id)
    # Fuera del plan, que trata al pendiente como CANCELAR sin pasarela
    await _soltar_intentos_en_espera(ctx, cobros)
    capturados: set[uuid.UUID] = set()
    for paso in pasos:
        if paso.accion.accion is not Accion.CAPTURAR:
            continue
        if paso.llamar:
            await _capturar(ctx, artista, pedido, paso.cobro, _VENCIDA_EN_DISPUTA)
        capturados.add(paso.cobro.id)
    hechos = await _liberar_y_reembolsar(ctx, pasos)

    await pedidos.resolver_disputa(
        session,
        pedido_id=pedido.id,
        destino=destino,
        resolucion=resolucion,
        admin_id=admin.id,
        hechos=replace(hechos, capturados=frozenset(capturados)),
        ahora=ahora,
    )
    return await pedidos.detalle_para_moderacion(session, pedido.id)


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
    ctx = _Contexto(session, pasarela, ahora, politicas, usuario)
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


# Conciliacion. La llaman los webhooks y el barrido. Solo consulta la pasarela:
# un webhook nunca mueve dinero ni registra nada por si solo. Lo que no cuadra
# no se corrige, se marca como discrepancia para moderacion. Quien llama
# confirma.


class ResultadoConciliacion(enum.StrEnum):
    REGISTRADO = "registrado"
    SIN_CAMBIOS = "sin_cambios"
    SIN_COBRO = "sin_cobro"
    DISCREPANCIA = "discrepancia"


@dataclass(frozen=True)
class Conciliacion:
    resultado: ResultadoConciliacion
    # Para moderacion: ids internos, nunca la referencia de la pasarela
    detalle: str | None = None


# Pares de estado en la base y en la pasarela que cuadran
_CUADRAN: Mapping[EstadoCobro, frozenset[EstadoCobroPasarela]] = {
    EstadoCobro.AUTORIZADO: frozenset({EstadoCobroPasarela.AUTORIZADO}),
    EstadoCobro.CAPTURADO: frozenset({EstadoCobroPasarela.CAPTURADO}),
    EstadoCobro.REEMBOLSADO: frozenset({EstadoCobroPasarela.CAPTURADO}),
    EstadoCobro.CANCELADO: _SIN_DINERO,
    EstadoCobro.VENCIDO: _SIN_DINERO,
}


def _cuadra(cobro: Cobro, foto: ConsultaCobro, ahora: datetime) -> bool:
    if foto.estado in _CUADRAN.get(cobro.estado, frozenset()):
        return foto.estado is not EstadoCobroPasarela.CAPTURADO or (
            foto.monto_reembolsado in (None, cobro.monto_reembolsado)
        )
    # La autorizacion vencida que la pasarela ya solto la resuelve el barrido
    return (
        cobro.estado is EstadoCobro.AUTORIZADO
        and foto.estado is EstadoCobroPasarela.LIBERADO
        and cobro.autorizado_hasta is not None
        and cobro.autorizado_hasta <= ahora
    )


def _uuid(valor: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(valor) if valor else None
    except ValueError:
        return None


async def _conciliar_sin_cobro(ctx: _Entorno, referencia: str) -> Conciliacion:
    """Ningun cobro tiene la referencia. Si la pasarela retiene dinero de un
    cobro nuestro segun sus metadatos, es dinero sin registro."""
    try:
        foto = await ctx.pasarela.consultar_cobro(referencia)
    except SolicitudInvalida:
        return Conciliacion(
            ResultadoConciliacion.SIN_COBRO, "La pasarela no conoce la referencia"
        )
    if foto.estado in (EstadoCobroPasarela.AUTORIZADO, EstadoCobroPasarela.CAPTURADO):
        cobro_id = _uuid(foto.metadatos.get("cobro_id"))
        if cobro_id is not None and await ctx.session.get(Cobro, cobro_id) is not None:
            return Conciliacion(
                ResultadoConciliacion.DISCREPANCIA,
                f"La pasarela tiene {foto.estado} un pago del cobro {cobro_id} "
                "que no esta registrado",
            )
    return Conciliacion(
        ResultadoConciliacion.SIN_COBRO, "Ningun cobro tiene esta referencia"
    )


async def _conciliar_intento(
    ctx: _Entorno, pedido: Pedido, cobro: Cobro
) -> Conciliacion:
    """El cobro espera el 3DS: se registra lo que la pasarela confirma, como en
    `verificar_cobro`. Un monto o un estado que no cuadra no se registra. Si
    sigue en espera, la proxima consulta del barrido se pospone `abandono_3ds`."""
    try:
        async with ctx.session.begin_nested():
            foto = await _resolver_intento(ctx, pedido, cobro)
    except HechosInconsistentes:
        return Conciliacion(
            ResultadoConciliacion.DISCREPANCIA,
            f"El cobro {cobro.id} espera el 3DS y la pasarela informa otro monto o "
            "estado",
        )
    if foto.estado in _EN_ESPERA:
        await pedidos.posponer_intento(ctx.session, cobro=cobro, ahora=ctx.ahora)
        return Conciliacion(ResultadoConciliacion.SIN_CAMBIOS)
    if (
        foto.estado in _SIN_DINERO
        and pedido.tipo is TipoPedido.OBRA_DISPONIBLE
        and pedido.estado is EstadoPedido.COTIZADO
    ):
        # Como en verificar_cobro: la obra no queda tomada por un pago fallido
        await pedidos.rechazar_pedido(ctx.session, pedido_id=pedido.id)
    return Conciliacion(ResultadoConciliacion.REGISTRADO)


async def conciliar_cobro(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    referencia: str,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> Conciliacion:
    """Compara el cobro de la referencia con lo que dice la pasarela. Solo
    llama a `consultar_cobro`."""
    ctx = _Entorno(session, pasarela, ahora, politicas)
    visto = await pedidos.cobro_por_referencia(session, referencia)
    if visto is None:
        return await _conciliar_sin_cobro(ctx, referencia)
    _, pedido = await _bloquear(
        ctx, await pedidos.pedido_existente(session, visto.pedido_id)
    )
    cobros = await pedidos.cobros_del_pedido(session, pedido.id)
    cobro = next((c for c in cobros if c.id == visto.id), None)
    # Cambio mientras se bloqueaba
    if cobro is None or cobro.referencia_pasarela != referencia:
        return await _conciliar_sin_cobro(ctx, referencia)

    if pedidos.esperando_autenticacion(cobro):
        return await _conciliar_intento(ctx, pedido, cobro)
    foto = await pasarela.consultar_cobro(referencia)
    if _cuadra(cobro, foto, ahora):
        return Conciliacion(ResultadoConciliacion.SIN_CAMBIOS)
    return Conciliacion(
        ResultadoConciliacion.DISCREPANCIA,
        f"El cobro {cobro.id} esta {cobro.estado} en la base y {foto.estado} en la "
        "pasarela",
    )


# Vencimientos. Las llama el barrido, que no actua por ningun usuario. Cada una
# bloquea perfil y pedido y vuelve a comprobar su condicion: si ya no aplica,
# devuelve False sin tocar nada. Asi dos barridos a la vez no hacen nada dos
# veces. Quien llama confirma.

# Donde un cobro autorizado espera captura
_CON_AUTORIZACION = frozenset(
    {
        (TipoPedido.ENCARGO, EstadoPedido.VISTA_PREVIA_ENTREGADA),
        (TipoPedido.OBRA_DISPONIBLE, EstadoPedido.EN_PROCESO),
    }
)


async def _bloquear_para_vencer(
    ctx: _Entorno, pedido_id: uuid.UUID
) -> tuple[Pedido, list[Cobro]]:
    visto = await pedidos.pedido_existente(ctx.session, pedido_id)
    _, pedido = await _bloquear(ctx, visto)
    return pedido, await pedidos.cobros_del_pedido(ctx.session, pedido.id)


async def _anular_intento(ctx: _Entorno, cobro: Cobro) -> None:
    """Anula en la pasarela un 3DS que nadie termino. Si no lo permite
    (pregunta 20 a ONVO), sigue: una autorizacion que nadie captura vence sola."""
    try:
        await ctx.pasarela.liberar_autorizacion(
            cobro.referencia_pasarela, clave_idempotencia=_clave_liberacion(cobro)
        )
    except OperacionNoSoportada:
        logger.warning("La pasarela no anula el 3DS del cobro %s", cobro.id)
    await pedidos.descartar_intento(ctx.session, cobro=cobro)


async def _cerrar_intento(ctx: _Entorno, pedido: Pedido, cobro: Cobro) -> bool:
    """Antes de vencer o cancelar, el intento que espera el 3DS. True si ya
    movio dinero: se registro y el pedido no se cancela. Si sigue en curso, se
    anula."""
    if not pedidos.esperando_autenticacion(cobro):
        return False
    foto = await _resolver_intento(ctx, pedido, cobro)
    if foto.estado in _EN_ESPERA:
        await _anular_intento(ctx, cobro)
        return False
    return foto.estado not in _SIN_DINERO


async def _cancelar_vencido(ctx: _Entorno, pedido: Pedido) -> None:
    cobros = await pedidos.cobros_del_pedido(ctx.session, pedido.id)
    plan = dominio.planear_vencimiento(pedido.tipo, pedido.estado, cobros)
    pasos = await _consultar_plan(ctx, plan.acciones, {c.id: c for c in cobros})
    hechos = await _liberar_y_reembolsar(ctx, pasos)
    await pedidos.cancelar_por_vencimiento(
        ctx.session, pedido_id=pedido.id, hechos=hechos, ahora=ctx.ahora
    )


async def soltar_la_quiero_abandonado(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> bool:
    """DT25: el 3DS de La quiero quedo sin terminar y la obra sigue tomada."""
    ctx = _Entorno(session, pasarela, ahora, politicas)
    pedido, cobros = await _bloquear_para_vencer(ctx, pedido_id)
    if (
        pedido.tipo is not TipoPedido.OBRA_DISPONIBLE
        or pedido.estado is not EstadoPedido.COTIZADO
        or pedido.created_at > ahora - politicas.abandono_3ds
    ):
        return False
    total = pedidos.cobro_de_tipo(cobros, TipoCobro.TOTAL)
    if not pedidos.esperando_autenticacion(total):
        return False
    if await _cerrar_intento(ctx, pedido, total):
        return True
    await pedidos.rechazar_pedido(session, pedido_id=pedido.id)
    return True


async def vencer_autorizacion(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> bool:
    """La autorizacion vencida se libera si la pasarela todavia la retiene, asi
    el cliente no queda con dos retenciones al volver a autorizar. La obra
    disponible se cancela: no hay nada capturado que devolver."""
    ctx = _Entorno(session, pasarela, ahora, politicas)
    pedido, cobros = await _bloquear_para_vencer(ctx, pedido_id)
    if (pedido.tipo, pedido.estado) not in _CON_AUTORIZACION:
        return False
    vencidos = [
        c
        for c in cobros
        if c.estado is EstadoCobro.AUTORIZADO
        and c.autorizado_hasta is not None
        and c.autorizado_hasta <= ahora
    ]
    if not vencidos:
        return False
    fotos = [
        (c, await pasarela.consultar_cobro(c.referencia_pasarela)) for c in vencidos
    ]
    if any(f.estado is EstadoCobroPasarela.CAPTURADO for _, f in fotos):
        raise HechosInconsistentes("La pasarela capturo una autorizacion vencida")
    for cobro, foto in fotos:
        if foto.estado in _EN_CURSO:
            await pasarela.liberar_autorizacion(
                cobro.referencia_pasarela, clave_idempotencia=_clave_liberacion(cobro)
            )
    for cobro in vencidos:
        await pedidos.registrar_autorizacion_vencida(
            session, pedido_id=pedido.id, cobro_id=cobro.id, ahora=ahora
        )
    if pedido.tipo is TipoPedido.OBRA_DISPONIBLE:
        await _cancelar_vencido(ctx, pedido)
    return True


async def cerrar_reautorizacion_vencida(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> bool:
    """Paso el plazo para volver a autorizar el saldo: se cancela como una
    cancelacion del cliente despues del anticipo, que queda para el artista."""
    ctx = _Entorno(session, pasarela, ahora, politicas)
    pedido, cobros = await _bloquear_para_vencer(ctx, pedido_id)
    if (
        pedido.tipo is not TipoPedido.ENCARGO
        or pedido.estado is not EstadoPedido.VISTA_PREVIA_ENTREGADA
    ):
        return False
    saldo = pedidos.cobro_de_tipo(cobros, TipoCobro.SALDO)
    if (
        saldo.estado not in (EstadoCobro.VENCIDO, EstadoCobro.PENDIENTE)
        or saldo.autorizado_hasta is None
        or ahora < dominio.limite_reautorizacion(saldo.autorizado_hasta, politicas)
    ):
        return False
    if await _cerrar_intento(ctx, pedido, saldo):
        return True
    await _cancelar_vencido(ctx, pedido)
    return True


async def cancelar_evento_impago(
    session: AsyncSession,
    pasarela: PasarelaDePagos,
    pedido_id: uuid.UUID,
    *,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> bool:
    """Llego la fecha del evento sin el saldo. El anticipo no se devuelve."""
    ctx = _Entorno(session, pasarela, ahora, politicas)
    pedido, cobros = await _bloquear_para_vencer(ctx, pedido_id)
    if (
        pedido.tipo is not TipoPedido.EVENTO
        or pedido.estado is not EstadoPedido.ANTICIPO_PAGADO
        or pedido.fecha_evento is None
        or pedido.fecha_evento > ahora
    ):
        return False
    saldo = pedidos.cobro_de_tipo(cobros, TipoCobro.SALDO)
    if await _cerrar_intento(ctx, pedido, saldo):
        return True
    await _cancelar_vencido(ctx, pedido)
    return True
