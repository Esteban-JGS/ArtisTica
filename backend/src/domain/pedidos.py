"""Reglas de pedidos y cobros. Logica pura: recibe valores y devuelve valores.

No conoce la base, la pasarela ni el reloj. Toda fecha llega como parametro.
"""

import enum
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from src.core.exceptions import (
    ActorNoAutorizado,
    CotizacionInvalida,
    FueraDePlazo,
    HechosInconsistentes,
    InvalidStateTransition,
    ObraNoDisponible,
    ReglaDeNegocioViolada,
)
from src.domain.politicas import CERO, CIEN, PoliticasPedido
from src.models.catalogo import EstadoObra
from src.models.consultas import EstadoConsulta
from src.models.pedidos import EstadoCobro, EstadoPedido, TipoCobro, TipoPedido
from src.models.users import PlanArtista

E = EstadoPedido
T = TipoPedido
C = EstadoCobro

CENTIMO = Decimal("0.01")

# Transiciones

_TODOS = tuple(TipoPedido)

# (tipos, desde, hacia). Copia fiel de la tabla del lote 2.
_TABLA_PEDIDO: tuple[
    tuple[tuple[TipoPedido, ...], tuple[EstadoPedido, ...], tuple[EstadoPedido, ...]],
    ...,
] = (
    (_TODOS, (E.COTIZADO,), (E.RECHAZADO,)),
    ((T.ENCARGO, T.EVENTO), (E.COTIZADO,), (E.ANTICIPO_PAGADO,)),
    ((T.ENCARGO,), (E.ANTICIPO_PAGADO,), (E.EN_PROCESO,)),
    ((T.ENCARGO,), (E.EN_PROCESO,), (E.VISTA_PREVIA_ENTREGADA,)),
    ((T.ENCARGO,), (E.VISTA_PREVIA_ENTREGADA,), (E.SALDO_PAGADO,)),
    ((T.EVENTO,), (E.ANTICIPO_PAGADO,), (E.SALDO_PAGADO,)),
    ((T.OBRA_DISPONIBLE,), (E.COTIZADO,), (E.EN_PROCESO,)),
    ((T.OBRA_DISPONIBLE,), (E.EN_PROCESO,), (E.SALDO_PAGADO,)),
    (_TODOS, (E.SALDO_PAGADO,), (E.COMPLETADO,)),
    ((T.ENCARGO,), (E.VISTA_PREVIA_ENTREGADA,), (E.EN_DISPUTA,)),
    (_TODOS, (E.SALDO_PAGADO,), (E.EN_DISPUTA,)),
    (
        (T.ENCARGO,),
        (E.ANTICIPO_PAGADO, E.EN_PROCESO, E.VISTA_PREVIA_ENTREGADA),
        (E.CANCELADO,),
    ),
    ((T.EVENTO,), (E.ANTICIPO_PAGADO, E.SALDO_PAGADO), (E.CANCELADO,)),
    ((T.OBRA_DISPONIBLE,), (E.EN_PROCESO,), (E.CANCELADO,)),
    (_TODOS, (E.EN_DISPUTA,), (E.COMPLETADO, E.CANCELADO)),
)

TRANSICIONES_PEDIDO: frozenset[tuple[TipoPedido, EstadoPedido, EstadoPedido]] = (
    frozenset(
        (tipo, desde, hacia)
        for tipos, desdes, hacias in _TABLA_PEDIDO
        for tipo in tipos
        for desde in desdes
        for hacia in hacias
    )
)

ESTADOS_TERMINALES = frozenset({E.COMPLETADO, E.RECHAZADO, E.CANCELADO})

TRANSICIONES_COBRO: Mapping[EstadoCobro, frozenset[EstadoCobro]] = {
    C.PENDIENTE: frozenset({C.AUTORIZADO, C.CAPTURADO, C.CANCELADO}),
    C.AUTORIZADO: frozenset({C.CAPTURADO, C.CANCELADO, C.VENCIDO}),
    C.CAPTURADO: frozenset({C.REEMBOLSADO}),
}

# La consulta de La quiero nace ya convertida y no pasa por esta tabla
TRANSICIONES_CONSULTA: Mapping[EstadoConsulta, frozenset[EstadoConsulta]] = {
    EstadoConsulta.ABIERTA: frozenset(
        {EstadoConsulta.COTIZADA, EstadoConsulta.DESCARTADA}
    ),
    EstadoConsulta.COTIZADA: frozenset(
        {EstadoConsulta.CONVERTIDA, EstadoConsulta.DESCARTADA}
    ),
    EstadoConsulta.CONVERTIDA: frozenset({EstadoConsulta.DESCARTADA}),
}


def validar_transicion(
    tipo: TipoPedido, desde: EstadoPedido, hacia: EstadoPedido
) -> None:
    if (tipo, desde, hacia) not in TRANSICIONES_PEDIDO:
        raise InvalidStateTransition(f"Pedido {tipo}: {desde} a {hacia} no permitido")


def validar_transicion_cobro(desde: EstadoCobro, hacia: EstadoCobro) -> None:
    if hacia not in TRANSICIONES_COBRO.get(desde, frozenset()):
        raise InvalidStateTransition(f"Cobro: {desde} a {hacia} no permitido")


def validar_transicion_consulta(desde: EstadoConsulta, hacia: EstadoConsulta) -> None:
    if hacia not in TRANSICIONES_CONSULTA.get(desde, frozenset()):
        raise InvalidStateTransition(f"Consulta: {desde} a {hacia} no permitido")


# Dinero


def cuantizar(monto: Decimal) -> Decimal:
    return monto.quantize(CENTIMO, rounding=ROUND_HALF_UP)


def porcentaje_de(monto: Decimal, porcentaje: Decimal) -> Decimal:
    return cuantizar(monto * porcentaje / CIEN)


def dividir_monto(monto_total: Decimal, porcentaje: Decimal) -> tuple[Decimal, Decimal]:
    """Anticipo y saldo. El saldo sale por resta para que sumen el total exacto."""
    anticipo = porcentaje_de(monto_total, porcentaje)
    return anticipo, monto_total - anticipo


def _exigir_decimal(valor: object, nombre: str) -> None:
    if not isinstance(valor, Decimal):
        raise TypeError(f"{nombre} debe ser Decimal, no {type(valor).__name__}")


@dataclass(frozen=True)
class Cotizacion:
    monto_total: Decimal
    anticipo_porcentaje: Decimal | None
    cobros: tuple[tuple[TipoCobro, Decimal], ...]


def resolver_porcentaje_anticipo(
    tipo: TipoPedido, porcentaje: Decimal | None, politicas: PoliticasPedido
) -> Decimal | None:
    if tipo is T.OBRA_DISPONIBLE:
        if porcentaje is not None:
            raise CotizacionInvalida("Una obra disponible no lleva anticipo")
        return None
    if porcentaje is None:
        return politicas.anticipo_porcentaje_defecto
    _exigir_decimal(porcentaje, "anticipo_porcentaje")
    minimo = politicas.anticipo_porcentaje_minimo
    maximo = politicas.anticipo_porcentaje_maximo
    if not minimo <= porcentaje <= maximo:
        raise CotizacionInvalida(f"El anticipo debe estar entre {minimo} y {maximo}")
    if cuantizar(porcentaje) != porcentaje:
        raise CotizacionInvalida("El anticipo admite como mucho dos decimales")
    return porcentaje


def cotizar(
    tipo: TipoPedido,
    monto_total: Decimal,
    anticipo_porcentaje: Decimal | None,
    politicas: PoliticasPedido,
) -> Cotizacion:
    _exigir_decimal(monto_total, "monto_total")
    if cuantizar(monto_total) != monto_total:
        raise CotizacionInvalida("El monto admite como mucho dos decimales")
    if monto_total < politicas.monto_minimo_pedido:
        raise CotizacionInvalida(
            f"El monto minimo por pedido es {politicas.monto_minimo_pedido}"
        )
    porcentaje = resolver_porcentaje_anticipo(tipo, anticipo_porcentaje, politicas)
    if porcentaje is None:
        return Cotizacion(monto_total, None, ((TipoCobro.TOTAL, monto_total),))
    anticipo, saldo = dividir_monto(monto_total, porcentaje)
    return Cotizacion(
        monto_total,
        porcentaje,
        ((TipoCobro.ANTICIPO, anticipo), (TipoCobro.SALDO, saldo)),
    )


def validar_fecha_evento(
    tipo: TipoPedido, fecha_evento: datetime | None, ahora: datetime
) -> None:
    if tipo is not T.EVENTO:
        if fecha_evento is not None:
            raise CotizacionInvalida("Solo un evento lleva fecha de evento")
        return
    if fecha_evento is None:
        raise CotizacionInvalida("Un evento necesita fecha")
    if fecha_evento <= ahora:
        raise CotizacionInvalida("La fecha del evento ya paso")


def tarifa_para_plan(plan: PlanArtista, politicas: PoliticasPedido) -> Decimal:
    tarifas = {
        PlanArtista.TALLER: politicas.tarifa_taller_porcentaje,
        PlanArtista.ESTUDIO: politicas.tarifa_estudio_porcentaje,
    }
    return tarifas[plan]


def validar_obra_pedible(
    estado: EstadoObra,
    precio: Decimal | None,
    artista_id: uuid.UUID,
    cliente_id: uuid.UUID,
) -> None:
    if estado is not EstadoObra.DISPONIBLE or precio is None:
        raise ObraNoDisponible("La obra no esta disponible")
    if artista_id == cliente_id:
        raise ActorNoAutorizado("Un artista no pide su propia obra")


# Actores y disputa


class Rol(enum.StrEnum):
    CLIENTE = "cliente"
    ARTISTA = "artista"


def rol_en_pedido(
    actor_id: uuid.UUID, cliente_id: uuid.UUID, artista_id: uuid.UUID
) -> Rol:
    if actor_id == cliente_id:
        return Rol.CLIENTE
    if actor_id == artista_id:
        return Rol.ARTISTA
    raise ActorNoAutorizado("Solo el cliente o el artista del pedido")


def calcular_disputable_hasta(
    tipo: TipoPedido,
    ahora: datetime,
    fecha_evento: datetime | None,
    politicas: PoliticasPedido,
) -> datetime:
    """Encargo desde la captura del saldo, obra desde el despacho, evento desde
    su fecha. Siempre mas la ventana de disputa."""
    if tipo is T.EVENTO:
        if fecha_evento is None:
            raise CotizacionInvalida("Un evento necesita fecha")
        return fecha_evento + politicas.ventana_disputa
    return ahora + politicas.ventana_disputa


def ventana_vencida(disputable_hasta: datetime, ahora: datetime) -> bool:
    return disputable_hasta < ahora


def validar_apertura_disputa(
    tipo: TipoPedido,
    estado: EstadoPedido,
    disputable_hasta: datetime | None,
    ahora: datetime,
) -> None:
    validar_transicion(tipo, estado, E.EN_DISPUTA)
    if estado is E.SALDO_PAGADO and (
        disputable_hasta is None or ventana_vencida(disputable_hasta, ahora)
    ):
        raise FueraDePlazo("La ventana de disputa ya vencio")


# Planes sobre los cobros: cancelacion y resolucion de disputa


class CobroVista(Protocol):
    id: uuid.UUID
    tipo: TipoCobro
    estado: EstadoCobro
    monto: Decimal
    monto_reembolsado: Decimal


class Accion(enum.StrEnum):
    # Cobro pendiente: nunca llego a la pasarela, se anula sin llamarla
    CANCELAR = "cancelar"
    LIBERAR_AUTORIZACION = "liberar_autorizacion"
    CAPTURAR = "capturar"
    REEMBOLSAR = "reembolsar"
    CONSERVAR = "conservar"


ESTADO_TRAS_ACCION: Mapping[Accion, EstadoCobro | None] = {
    Accion.CANCELAR: C.CANCELADO,
    Accion.LIBERAR_AUTORIZACION: C.CANCELADO,
    Accion.CAPTURAR: C.CAPTURADO,
    Accion.REEMBOLSAR: C.REEMBOLSADO,
    Accion.CONSERVAR: None,
}


@dataclass(frozen=True)
class AccionCobro:
    cobro_id: uuid.UUID
    accion: Accion
    monto: Decimal | None = None


@dataclass(frozen=True)
class PlanCobros:
    acciones: tuple[AccionCobro, ...]

    def de(self, cobro_id: uuid.UUID) -> AccionCobro | None:
        return next((a for a in self.acciones if a.cobro_id == cobro_id), None)

    def _ids(self, accion: Accion) -> frozenset[uuid.UUID]:
        return frozenset(a.cobro_id for a in self.acciones if a.accion is accion)

    @property
    def liberaciones(self) -> frozenset[uuid.UUID]:
        return self._ids(Accion.LIBERAR_AUTORIZACION)

    @property
    def capturas(self) -> frozenset[uuid.UUID]:
        return self._ids(Accion.CAPTURAR)

    @property
    def reembolsos(self) -> dict[uuid.UUID, Decimal]:
        return {
            a.cobro_id: a.monto
            for a in self.acciones
            if a.accion is Accion.REEMBOLSAR and a.monto is not None
        }


@dataclass(frozen=True)
class HechosPasarela:
    """Lo que la pasarela ya ejecuto. Quien llama lo trae despues de ejecutar."""

    liberados: frozenset[uuid.UUID] = frozenset()
    capturados: frozenset[uuid.UUID] = frozenset()
    reembolsos: Mapping[uuid.UUID, Decimal] = field(default_factory=dict)


def verificar_hechos(plan: PlanCobros, hechos: HechosPasarela) -> None:
    if (
        hechos.liberados != plan.liberaciones
        or hechos.capturados != plan.capturas
        or dict(hechos.reembolsos) != plan.reembolsos
    ):
        raise HechosInconsistentes("Los hechos de la pasarela no siguen el plan")


def reembolsable(cobro: CobroVista) -> Decimal:
    return cobro.monto - cobro.monto_reembolsado


def _accion_al_cerrar(
    cobro: CobroVista, porcentaje_reembolso: Decimal, capturar_autorizados: bool
) -> AccionCobro | None:
    if cobro.estado is C.PENDIENTE:
        return AccionCobro(cobro.id, Accion.CANCELAR)
    if cobro.estado is C.AUTORIZADO:
        accion = (
            Accion.CAPTURAR if capturar_autorizados else Accion.LIBERAR_AUTORIZACION
        )
        return AccionCobro(cobro.id, accion)
    if cobro.estado is C.CAPTURADO:
        monto = porcentaje_de(reembolsable(cobro), porcentaje_reembolso)
        if monto > CERO:
            return AccionCobro(cobro.id, Accion.REEMBOLSAR, monto)
        return AccionCobro(cobro.id, Accion.CONSERVAR)
    # Cancelado, vencido o reembolsado: ya no hay nada que hacer en la pasarela
    return None


def porcentaje_reembolso_evento(
    fecha_evento: datetime, ahora: datetime, politicas: PoliticasPedido
) -> Decimal:
    anticipacion = fecha_evento - ahora
    if anticipacion > politicas.cancelacion_evento_total:
        return CIEN
    if anticipacion >= politicas.cancelacion_evento_parcial:
        return politicas.cancelacion_evento_porcentaje_parcial
    return CERO


def planear_cancelacion(
    tipo: TipoPedido,
    estado: EstadoPedido,
    rol: Rol,
    cobros: Iterable[CobroVista],
    fecha_evento: datetime | None,
    ahora: datetime,
    politicas: PoliticasPedido,
) -> PlanCobros:
    validar_transicion(tipo, estado, E.CANCELADO)
    if tipo is T.EVENTO and (fecha_evento is None or ahora >= fecha_evento):
        raise FueraDePlazo("Un evento solo se cancela antes de su fecha")

    if rol is Rol.ARTISTA:
        porcentaje = CIEN
    elif tipo is T.ENCARGO:
        porcentaje = CERO
    elif tipo is T.EVENTO:
        porcentaje = porcentaje_reembolso_evento(fecha_evento, ahora, politicas)
    else:
        # Obra disponible antes del despacho: no hay nada capturado
        porcentaje = CIEN

    acciones = (_accion_al_cerrar(c, porcentaje, False) for c in cobros)
    return PlanCobros(tuple(a for a in acciones if a is not None))


def planear_resolucion(
    tipo: TipoPedido,
    estado: EstadoPedido,
    destino: EstadoPedido,
    cobros: Iterable[CobroVista],
    reembolsos_ordenados: Mapping[uuid.UUID, Decimal],
) -> PlanCobros:
    """Moderacion cierra la disputa. Puede devolver cualquier cobro capturado,
    anticipo incluido. Si completa, captura lo autorizado; si cancela, lo libera."""
    validar_transicion(tipo, estado, destino)
    cobros = list(cobros)
    desconocidos = set(reembolsos_ordenados) - {c.id for c in cobros}
    if desconocidos:
        raise ReglaDeNegocioViolada("Reembolso ordenado sobre un cobro ajeno")

    acciones: list[AccionCobro] = []
    for cobro in cobros:
        monto = reembolsos_ordenados.get(cobro.id)
        if monto is None:
            accion = _accion_al_cerrar(cobro, CERO, destino is E.COMPLETADO)
            if accion is not None:
                acciones.append(accion)
            continue
        _exigir_decimal(monto, "monto de reembolso")
        if cobro.estado is not C.CAPTURADO:
            raise ReglaDeNegocioViolada("Solo se reembolsa un cobro capturado")
        if not CERO < monto <= reembolsable(cobro) or cuantizar(monto) != monto:
            raise ReglaDeNegocioViolada("Monto de reembolso fuera de rango")
        acciones.append(AccionCobro(cobro.id, Accion.REEMBOLSAR, monto))
    return PlanCobros(tuple(acciones))
