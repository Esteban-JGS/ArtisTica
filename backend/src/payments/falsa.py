"""Pasarela falsa, en memoria y determinista.

La usan las pruebas y la demo. Se comporta como una pasarela de verdad: lleva
el estado de cada cobro, vence autorizaciones segun el reloj inyectado, aplica
idempotencia real y puede fallar a pedido con `programar_falla`.
"""

import hashlib
import hmac
import json
from collections import defaultdict, deque
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import SecretStr

from src.payments.contrato import (
    SIN_METADATOS,
    Capacidades,
    ConsultaCobro,
    CuentaConectada,
    EstadoCobroPasarela,
    EstadoCuenta,
    EstadoOperacion,
    EventoRecibido,
    MetodoPago,
    ResponsableContracargos,
    ResultadoCobro,
    ResultadoReembolso,
    SolicitudCobro,
    TipoEvento,
    buscar_encabezado,
    validar_clave,
    validar_metadatos,
    validar_monto,
    validar_referencia,
    validar_solicitud,
    validar_tarifa,
)
from src.payments.errores import (
    AutorizacionVencida,
    ErrorPasarela,
    FirmaInvalida,
    PagoRechazado,
    SolicitudInvalida,
)

PROVEEDOR = "falsa"
ENCABEZADO_FIRMA = "X-Firma-Pasarela"
# Un cobro con este medio de pago lo rechaza la pasarela, como una tarjeta sin
# fondos. Sirve para la demo.
MEDIO_PAGO_RECHAZADO = "medio_falso_rechazado"

OPERACIONES = frozenset(
    {
        "crear_cuenta_conectada",
        "consultar_cuenta",
        "configurar_tarifa",
        "cobrar",
        "autorizar",
        "capturar",
        "liberar_autorizacion",
        "reembolsar",
        "consultar_cobro",
        "parsear_webhook",
    }
)

CAPACIDADES_POR_DEFECTO = Capacidades(
    metodos=frozenset(MetodoPago),
    autorizacion_diferida=frozenset({MetodoPago.TARJETA}),
    dias_vigencia_autorizacion=7,
    comision_por_cobro=False,
    revierte_comision_en_reembolso=True,
    soporta_idempotencia=True,
    retencion_liquidacion_por_cobro=False,
    responsable_contracargos=ResponsableContracargos.CUENTA_CONECTADA,
    onboarding_persona_fisica=True,
)


def _reloj_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class _Cuenta:
    nombre: str
    estado: EstadoCuenta
    tarifa: Decimal
    metadatos: Mapping[str, str] = field(default_factory=dict)


@dataclass
class _Cobro:
    cuenta_id: str
    autorizado: Decimal
    estado: EstadoOperacion
    autorizado_hasta: datetime | None
    capturado: Decimal = Decimal("0")
    reembolsado: Decimal = Decimal("0")
    capturado_en: datetime | None = None
    metadatos: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class EstadoCobroFalso:
    """Foto del estado interno de un cobro, para pruebas y demo."""

    estado: EstadoOperacion
    monto_autorizado: Decimal
    monto_capturado: Decimal
    monto_reembolsado: Decimal
    autorizado_hasta: datetime | None


class PasarelaFalsa:
    def __init__(
        self,
        *,
        reloj: Callable[[], datetime] = _reloj_utc,
        capacidades: Capacidades = CAPACIDADES_POR_DEFECTO,
        secreto_webhook: str = "secreto_webhook_falso",
    ) -> None:
        self._reloj = reloj
        self._capacidades = capacidades
        self._secreto = SecretStr(secreto_webhook)
        self._cuentas: dict[str, _Cuenta] = {}
        self._cobros: dict[str, _Cobro] = {}
        self._idempotencia: dict[str, tuple[Hashable, Any]] = {}
        self._fallas: defaultdict[str, deque[ErrorPasarela]] = defaultdict(deque)
        self._secuencia = 0

    def __repr__(self) -> str:
        return (
            f"PasarelaFalsa(cuentas={len(self._cuentas)}, cobros={len(self._cobros)})"
        )

    @property
    def capacidades(self) -> Capacidades:
        return self._capacidades

    # Controles de la falsa

    def programar_falla(self, operacion: str, error: ErrorPasarela) -> None:
        """La proxima llamada a `operacion` levanta `error`."""
        if operacion not in OPERACIONES:
            raise ValueError(f"Operacion desconocida: {operacion}")
        if not isinstance(error, ErrorPasarela):
            raise TypeError("La falla tiene que ser un ErrorPasarela")
        self._fallas[operacion].append(error)

    def completar_onboarding(self, cuenta_id: str) -> None:
        self._cuenta(cuenta_id).estado = EstadoCuenta.COMPLETADA

    def rechazar_onboarding(self, cuenta_id: str) -> None:
        self._cuenta(cuenta_id).estado = EstadoCuenta.RECHAZADA

    def tarifa_de(self, cuenta_id: str) -> Decimal:
        return self._cuenta(cuenta_id).tarifa

    def inspeccionar_cobro(self, referencia: str) -> EstadoCobroFalso:
        cobro = self._cobro(referencia)
        return EstadoCobroFalso(
            estado=cobro.estado,
            monto_autorizado=cobro.autorizado,
            monto_capturado=cobro.capturado,
            monto_reembolsado=cobro.reembolsado,
            autorizado_hasta=cobro.autorizado_hasta,
        )

    @property
    def total_cobros(self) -> int:
        return len(self._cobros)

    def total_cuentas(self) -> int:
        return len(self._cuentas)

    def firmar(self, cuerpo: bytes) -> str:
        return hmac.new(
            self._secreto.get_secret_value().encode(), cuerpo, hashlib.sha256
        ).hexdigest()

    def construir_evento(
        self,
        tipo: str,
        *,
        referencia: str | None = None,
        evento_id: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """Arma un webhook firmado: cuerpo y encabezados."""
        cuerpo = json.dumps(
            {
                "id": evento_id or self._nuevo_id("evento"),
                "tipo": str(tipo),
                "referencia": referencia,
            },
            sort_keys=True,
        ).encode()
        return cuerpo, {ENCABEZADO_FIRMA: self.firmar(cuerpo)}

    # Cuentas conectadas

    async def crear_cuenta_conectada(
        self,
        *,
        nombre: str,
        tarifa_porcentaje: Decimal,
        clave_idempotencia: str,
        metadatos: Mapping[str, str] = SIN_METADATOS,
    ) -> CuentaConectada:
        if not isinstance(nombre, str) or not nombre.strip():
            raise SolicitudInvalida("Falta el nombre de la cuenta")
        validar_tarifa(tarifa_porcentaje)
        validar_clave(clave_idempotencia)
        validar_metadatos(metadatos)
        self._fallar_si_programado("crear_cuenta_conectada")
        nombre = nombre.strip()
        huella = (
            "crear_cuenta_conectada",
            nombre,
            tarifa_porcentaje,
            tuple(sorted(metadatos.items())),
        )
        # Reintentar despues de un commit fallido no crea una segunda cuenta
        if (previo := self._repetido(clave_idempotencia, huella)) is not None:
            return previo

        cuenta_id = self._nuevo_id("cuenta")
        self._cuentas[cuenta_id] = _Cuenta(
            nombre=nombre,
            estado=EstadoCuenta.PENDIENTE,
            tarifa=tarifa_porcentaje,
            metadatos=dict(metadatos),
        )
        cuenta = CuentaConectada(
            id=cuenta_id,
            estado=EstadoCuenta.PENDIENTE,
            url_onboarding=f"https://pasarela-falsa.invalid/onboarding/{cuenta_id}",
        )
        return self._recordar(clave_idempotencia, huella, cuenta)

    async def consultar_cuenta(self, cuenta_id: str) -> CuentaConectada:
        self._fallar_si_programado("consultar_cuenta")
        return CuentaConectada(id=cuenta_id, estado=self._cuenta(cuenta_id).estado)

    async def configurar_tarifa(
        self, cuenta_id: str, tarifa_porcentaje: Decimal
    ) -> None:
        validar_tarifa(tarifa_porcentaje)
        self._fallar_si_programado("configurar_tarifa")
        self._cuenta(cuenta_id).tarifa = tarifa_porcentaje

    # Cobros

    async def cobrar(self, solicitud: SolicitudCobro) -> ResultadoCobro:
        return self._cobrar_o_autorizar(solicitud, operacion="cobrar")

    async def autorizar(self, solicitud: SolicitudCobro) -> ResultadoCobro:
        return self._cobrar_o_autorizar(solicitud, operacion="autorizar")

    async def capturar(
        self,
        referencia: str,
        *,
        clave_idempotencia: str,
        monto: Decimal | None = None,
    ) -> ResultadoCobro:
        validar_referencia(referencia)
        validar_clave(clave_idempotencia)
        if monto is not None:
            validar_monto(monto)
        self._fallar_si_programado("capturar")
        huella = ("capturar", referencia, monto)
        if (previo := self._repetido(clave_idempotencia, huella)) is not None:
            return previo

        cobro = self._cobro(referencia)
        ahora = self._ahora()
        self._exigir_autorizado(cobro, ahora)
        a_capturar = cobro.autorizado if monto is None else monto
        if a_capturar > cobro.autorizado:
            raise SolicitudInvalida("No se puede capturar mas de lo autorizado")
        # Una captura cierra la autorizacion: el resto se libera
        cobro.capturado = a_capturar
        cobro.estado = EstadoOperacion.CAPTURADO
        cobro.capturado_en = ahora
        resultado = ResultadoCobro(
            referencia=referencia,
            estado=EstadoOperacion.CAPTURADO,
            monto=a_capturar,
            autorizado_hasta=cobro.autorizado_hasta,
            capturado_en=ahora,
        )
        return self._recordar(clave_idempotencia, huella, resultado)

    async def liberar_autorizacion(
        self, referencia: str, *, clave_idempotencia: str
    ) -> ResultadoCobro:
        validar_referencia(referencia)
        validar_clave(clave_idempotencia)
        self._fallar_si_programado("liberar_autorizacion")
        huella = ("liberar_autorizacion", referencia)
        if (previo := self._repetido(clave_idempotencia, huella)) is not None:
            return previo

        cobro = self._cobro(referencia)
        if cobro.estado is not EstadoOperacion.AUTORIZADO:
            raise SolicitudInvalida(f"El cobro esta {cobro.estado}, no autorizado")
        cobro.estado = EstadoOperacion.LIBERADO
        resultado = ResultadoCobro(
            referencia=referencia,
            estado=EstadoOperacion.LIBERADO,
            monto=cobro.autorizado,
            autorizado_hasta=cobro.autorizado_hasta,
        )
        return self._recordar(clave_idempotencia, huella, resultado)

    async def reembolsar(
        self, referencia: str, *, monto: Decimal, clave_idempotencia: str
    ) -> ResultadoReembolso:
        validar_referencia(referencia)
        validar_monto(monto)
        validar_clave(clave_idempotencia)
        self._fallar_si_programado("reembolsar")
        huella = ("reembolsar", referencia, monto)
        if (previo := self._repetido(clave_idempotencia, huella)) is not None:
            return previo

        cobro = self._cobro(referencia)
        if cobro.estado is not EstadoOperacion.CAPTURADO:
            raise SolicitudInvalida("Solo se reembolsa un cobro capturado")
        if monto > cobro.capturado - cobro.reembolsado:
            raise SolicitudInvalida("No se puede reembolsar mas de lo capturado")
        cobro.reembolsado += monto
        resultado = ResultadoReembolso(
            referencia_cobro=referencia,
            referencia_reembolso=self._nuevo_id("reembolso"),
            monto=monto,
            total_reembolsado=cobro.reembolsado,
        )
        return self._recordar(clave_idempotencia, huella, resultado)

    async def consultar_cobro(self, referencia: str) -> ConsultaCobro:
        validar_referencia(referencia)
        self._fallar_si_programado("consultar_cobro")
        cobro = self._cobro(referencia)
        return ConsultaCobro(
            referencia=referencia,
            estado=self._foto_de(cobro),
            monto=cobro.autorizado,
            monto_capturado=cobro.capturado,
            monto_reembolsado=cobro.reembolsado,
            autorizado_hasta=cobro.autorizado_hasta,
            metadatos=dict(cobro.metadatos),
        )

    # Webhooks

    async def parsear_webhook(
        self, cuerpo: bytes, encabezados: Mapping[str, str]
    ) -> EventoRecibido:
        self._fallar_si_programado("parsear_webhook")
        firma = buscar_encabezado(encabezados, ENCABEZADO_FIRMA)
        if firma is None or not hmac.compare_digest(
            firma.encode(), self.firmar(cuerpo).encode()
        ):
            raise FirmaInvalida("La firma del webhook no es valida")
        try:
            payload = json.loads(cuerpo)
        except ValueError:
            raise SolicitudInvalida("El webhook no es JSON") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise SolicitudInvalida("El webhook no trae id")
        referencia = payload.get("referencia")
        return EventoRecibido(
            proveedor=PROVEEDOR,
            evento_externo_id=payload["id"],
            tipo=_tipo_evento(payload.get("tipo")),
            referencia=referencia if isinstance(referencia, str) else None,
            payload=payload,
        )

    # Internos

    def _cobrar_o_autorizar(
        self, solicitud: SolicitudCobro, *, operacion: str
    ) -> ResultadoCobro:
        diferida = operacion == "autorizar"
        validar_solicitud(solicitud, self._capacidades, diferida=diferida)
        self._fallar_si_programado(operacion)
        huella = (operacion, _huella_solicitud(solicitud))
        if (previo := self._repetido(solicitud.clave_idempotencia, huella)) is not None:
            return previo

        cuenta = self._cuentas.get(solicitud.cuenta_conectada_id)
        if cuenta is None or cuenta.estado is not EstadoCuenta.COMPLETADA:
            raise SolicitudInvalida("La cuenta conectada no puede recibir cobros")
        if solicitud.medio_pago_id == MEDIO_PAGO_RECHAZADO:
            raise PagoRechazado("Pago rechazado por el emisor")

        ahora = self._ahora()
        referencia = self._nuevo_id("cobro")
        if diferida:
            dias = self._capacidades.dias_vigencia_autorizacion
            hasta = None if dias is None else ahora + timedelta(days=dias)
            self._cobros[referencia] = _Cobro(
                cuenta_id=solicitud.cuenta_conectada_id,
                autorizado=solicitud.monto,
                estado=EstadoOperacion.AUTORIZADO,
                autorizado_hasta=hasta,
                metadatos=dict(solicitud.metadatos),
            )
            resultado = ResultadoCobro(
                referencia=referencia,
                estado=EstadoOperacion.AUTORIZADO,
                monto=solicitud.monto,
                autorizado_hasta=hasta,
            )
        else:
            self._cobros[referencia] = _Cobro(
                cuenta_id=solicitud.cuenta_conectada_id,
                autorizado=solicitud.monto,
                estado=EstadoOperacion.CAPTURADO,
                autorizado_hasta=None,
                capturado=solicitud.monto,
                capturado_en=ahora,
                metadatos=dict(solicitud.metadatos),
            )
            resultado = ResultadoCobro(
                referencia=referencia,
                estado=EstadoOperacion.CAPTURADO,
                monto=solicitud.monto,
                capturado_en=ahora,
            )
        return self._recordar(solicitud.clave_idempotencia, huella, resultado)

    def _foto_de(self, cobro: _Cobro) -> EstadoCobroPasarela:
        if cobro.estado is EstadoOperacion.CAPTURADO:
            return EstadoCobroPasarela.CAPTURADO
        if cobro.estado is EstadoOperacion.LIBERADO:
            return EstadoCobroPasarela.LIBERADO
        # Una autorizacion vencida deja de ser capturable: la pasarela la libera
        if cobro.autorizado_hasta is not None and cobro.autorizado_hasta <= (
            self._ahora()
        ):
            return EstadoCobroPasarela.LIBERADO
        return EstadoCobroPasarela.AUTORIZADO

    def _exigir_autorizado(self, cobro: _Cobro, ahora: datetime) -> None:
        if cobro.estado is not EstadoOperacion.AUTORIZADO:
            raise SolicitudInvalida(f"El cobro esta {cobro.estado}, no autorizado")
        # Mismo borde que el lote 2: vencida cuando autorizado_hasta <= ahora
        if cobro.autorizado_hasta is not None and cobro.autorizado_hasta <= ahora:
            raise AutorizacionVencida("La autorizacion ya vencio")

    def _repetido(self, clave: str, huella: Hashable) -> Any:
        if not self._capacidades.soporta_idempotencia:
            return None
        previo = self._idempotencia.get(clave)
        if previo is None:
            return None
        huella_previa, resultado = previo
        if huella_previa != huella:
            raise SolicitudInvalida(
                "La clave de idempotencia ya se uso con datos distintos"
            )
        return resultado

    def _recordar(self, clave: str, huella: Hashable, resultado: Any) -> Any:
        if self._capacidades.soporta_idempotencia:
            self._idempotencia[clave] = (huella, resultado)
        return resultado

    def _fallar_si_programado(self, operacion: str) -> None:
        fallas = self._fallas[operacion]
        if fallas:
            raise fallas.popleft()

    def _cuenta(self, cuenta_id: str) -> _Cuenta:
        cuenta = self._cuentas.get(cuenta_id)
        if cuenta is None:
            raise SolicitudInvalida("Cuenta conectada inexistente")
        return cuenta

    def _cobro(self, referencia: str) -> _Cobro:
        cobro = self._cobros.get(referencia)
        if cobro is None:
            raise SolicitudInvalida("Referencia de cobro inexistente")
        return cobro

    def _ahora(self) -> datetime:
        ahora = self._reloj()
        if ahora.tzinfo is None:
            raise ValueError("El reloj tiene que devolver fechas con zona horaria")
        return ahora

    def _nuevo_id(self, prefijo: str) -> str:
        self._secuencia += 1
        return f"{prefijo}_falso_{self._secuencia:06d}"


def _huella_solicitud(solicitud: SolicitudCobro) -> Hashable:
    return (
        solicitud.monto,
        solicitud.moneda,
        solicitud.metodo,
        solicitud.cuenta_conectada_id,
        solicitud.tarifa_porcentaje,
        solicitud.descripcion,
        solicitud.medio_pago_id,
        tuple(sorted(solicitud.metadatos.items())),
    )


def _tipo_evento(valor: object) -> TipoEvento:
    try:
        return TipoEvento(valor)
    except ValueError:
        return TipoEvento.DESCONOCIDO
