"""Adaptador de ONVO. Todas las pruebas usan httpx.MockTransport: nunca hay red."""

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from src.payments import onvo
from src.payments.config import ConfigOnvo
from src.payments.contrato import (
    EstadoCuenta,
    EstadoOperacion,
    MetodoPago,
    SolicitudCobro,
    TipoEvento,
)
from src.payments.errores import (
    CredencialesInvalidas,
    ErrorPasarela,
    FirmaInvalida,
    OperacionNoSoportada,
    PagoRechazado,
    PasarelaNoDisponible,
    SolicitudInvalida,
)
from src.payments.onvo import PasarelaOnvo, a_unidad_menor, desde_unidad_menor

CLAVE = "onvo_test_secret_key_NO_DEBE_FILTRARSE"
SECRETO_WEBHOOK = "webhook_secret_TAMPOCO_DEBE_FILTRARSE"
AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
ACTUALIZADO = "2026-10-01T12:00:05.000Z"
MONTO = Decimal("12500.50")
CENTIMOS = 1250050

Manejador = Callable[[httpx.Request], httpx.Response]


def configuracion(**cambios) -> ConfigOnvo:
    valores = {
        "API_KEY": SecretStr(CLAVE),
        "WEBHOOK_SECRET": SecretStr(SECRETO_WEBHOOK),
    }
    valores.update(cambios)
    return ConfigOnvo(_env_file=None, **valores)


class Simulador:
    """Responde por (metodo, ruta) y guarda cada solicitud recibida."""

    def __init__(self, rutas: dict[tuple[str, str], Manejador]) -> None:
        self.rutas = rutas
        self.solicitudes: list[httpx.Request] = []

    def __call__(self, solicitud: httpx.Request) -> httpx.Response:
        self.solicitudes.append(solicitud)
        # Toda solicitud va autenticada como dice el mapeo
        assert solicitud.headers[onvo.ENCABEZADO_AUTORIZACION] == f"Bearer {CLAVE}"
        return self.rutas[(solicitud.method, solicitud.url.path)](solicitud)

    def pasarela(self, config: ConfigOnvo | None = None) -> PasarelaOnvo:
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(self))
        return PasarelaOnvo(
            config or configuracion(), cliente=cliente, reloj=lambda: AHORA
        )


def responder(estado: int, datos: object) -> Manejador:
    return lambda _: httpx.Response(estado, json=datos)


def intencion(estado: str, **extra) -> dict:
    return {
        "id": "pi_1",
        "status": estado,
        "amount": CENTIMOS,
        "capturableAmount": CENTIMOS,
        "receivedAmount": CENTIMOS,
        "currency": "CRC",
        "updatedAt": ACTUALIZADO,
        **extra,
    }


def cuerpo(solicitud: httpx.Request) -> dict | None:
    if not solicitud.content:
        return None
    return json.loads(solicitud.content, parse_float=Decimal)


def cobro(metodo: MetodoPago = MetodoPago.TARJETA) -> SolicitudCobro:
    return SolicitudCobro(
        monto=MONTO,
        metodo=metodo,
        cuenta_conectada_id="cuenta_1",
        clave_idempotencia="clave-1",
        descripcion="Anticipo",
        metadatos={"pedido_id": "p-1"},
        medio_pago_id="pm_1",
    )


def timeout(solicitud: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("sin respuesta", request=solicitud)


# Prueba 12: cada operacion arma la solicitud del bloque de mapeo

CREAR = ("POST", onvo.RUTA_CREAR_INTENCION)
CONFIRMAR = ("POST", onvo.RUTA_CONFIRMAR.format(id="pi_1"))
CAPTURAR = ("POST", onvo.RUTA_CAPTURAR.format(id="pi_1"))


async def caso_crear_cuenta() -> None:
    simulador = Simulador(
        {
            ("POST", onvo.RUTA_CREAR_CUENTA): responder(
                201,
                {
                    "id": "cuenta_1",
                    "status": "pending_onboarding",
                    "onboardingUrl": "https://onvopay.com/setup/x",
                },
            )
        }
    )
    cuenta = await simulador.pasarela().crear_cuenta_conectada(
        nombre=" Taller de Ana ",
        tarifa_porcentaje=Decimal("6.25"),
        clave_idempotencia="cuenta-1",
    )
    assert cuenta.estado is EstadoCuenta.PENDIENTE
    assert cuenta.url_onboarding == "https://onvopay.com/setup/x"
    assert cuerpo(simulador.solicitudes[0]) == {
        onvo.CAMPO_NOMBRE_NEGOCIO: "Taller de Ana",
        onvo.CAMPO_TARIFA_MARKETPLACE: Decimal("6.25"),
    }


async def caso_consultar_cuenta() -> None:
    ruta = onvo.RUTA_CUENTA.format(id="cuenta_1")
    simulador = Simulador(
        {("GET", ruta): responder(200, {"id": "cuenta_1", "status": "active"})}
    )
    cuenta = await simulador.pasarela().consultar_cuenta("cuenta_1")
    assert cuenta.estado is EstadoCuenta.COMPLETADA
    assert cuerpo(simulador.solicitudes[0]) is None


async def caso_configurar_tarifa() -> None:
    ruta = onvo.RUTA_CUENTA.format(id="cuenta_1")
    simulador = Simulador({("POST", ruta): responder(200, {"id": "cuenta_1"})})
    await simulador.pasarela().configurar_tarifa("cuenta_1", Decimal("5"))
    assert cuerpo(simulador.solicitudes[0]) == {
        onvo.CAMPO_TARIFA_MARKETPLACE: Decimal("5")
    }


async def caso_cobrar() -> None:
    simulador = Simulador(
        {
            CREAR: responder(201, intencion("requires_payment_method")),
            CONFIRMAR: responder(201, intencion("succeeded")),
        }
    )
    resultado = await simulador.pasarela().cobrar(cobro())
    assert resultado.estado is EstadoOperacion.CAPTURADO
    assert resultado.referencia == "pi_1"
    assert resultado.monto == MONTO
    assert resultado.capturado_en == datetime(2026, 10, 1, 12, 0, 5, tzinfo=UTC)
    crear, confirmar = simulador.solicitudes
    assert cuerpo(crear) == {
        onvo.CAMPO_MONTO: CENTIMOS,
        onvo.CAMPO_MONEDA: "CRC",
        onvo.CAMPO_EN_NOMBRE_DE: "cuenta_1",
        onvo.CAMPO_METODO_CAPTURA: onvo.CAPTURA_AUTOMATICA,
        onvo.CAMPO_METADATOS: {
            "pedido_id": "p-1",
            onvo.LLAVE_METADATO_IDEMPOTENCIA: "clave-1",
        },
        onvo.CAMPO_DESCRIPCION: "Anticipo",
    }
    assert cuerpo(confirmar) == {onvo.CAMPO_MEDIO_PAGO: "pm_1"}


async def caso_autorizar() -> None:
    simulador = Simulador(
        {
            CREAR: responder(201, intencion("requires_payment_method")),
            CONFIRMAR: responder(201, intencion("requires_capture")),
        }
    )
    resultado = await simulador.pasarela().autorizar(cobro())
    assert resultado.estado is EstadoOperacion.AUTORIZADO
    assert resultado.monto == MONTO
    # La vigencia de ONVO no se conoce: no se inventa un vencimiento
    assert resultado.autorizado_hasta is None
    assert cuerpo(simulador.solicitudes[0])[onvo.CAMPO_METODO_CAPTURA] == (
        onvo.CAPTURA_MANUAL
    )


async def caso_capturar() -> None:
    simulador = Simulador(
        {CAPTURAR: responder(201, intencion("succeeded", receivedAmount=400000))}
    )
    resultado = await simulador.pasarela().capturar(
        "pi_1", clave_idempotencia="c-1", monto=Decimal("4000.00")
    )
    assert resultado.monto == Decimal("4000.00")
    assert resultado.estado is EstadoOperacion.CAPTURADO
    assert cuerpo(simulador.solicitudes[0]) == {onvo.CAMPO_MONTO_A_CAPTURAR: 400000}


async def caso_liberar() -> None:
    ruta = ("POST", onvo.RUTA_CANCELAR.format(id="pi_1"))
    simulador = Simulador({ruta: responder(201, intencion("canceled"))})
    resultado = await simulador.pasarela().liberar_autorizacion(
        "pi_1", clave_idempotencia="l-1"
    )
    assert resultado.estado is EstadoOperacion.LIBERADO
    assert resultado.monto == MONTO


async def caso_reembolsar() -> None:
    simulador = Simulador(
        {
            ("POST", onvo.RUTA_REEMBOLSOS): responder(
                201, {"id": "re_1", "amount": 300000, "status": "pending"}
            )
        }
    )
    resultado = await simulador.pasarela().reembolsar(
        "pi_1", monto=Decimal("3000.00"), clave_idempotencia="r-1"
    )
    assert resultado.referencia_reembolso == "re_1"
    assert resultado.monto == Decimal("3000.00")
    assert resultado.total_reembolsado is None
    assert cuerpo(simulador.solicitudes[0]) == {
        onvo.CAMPO_INTENCION_DEL_REEMBOLSO: "pi_1",
        onvo.CAMPO_MONTO: 300000,
    }


async def caso_webhook() -> None:
    pasarela = Simulador({}).pasarela()
    datos = json.dumps(
        {
            "type": "payment-intent.succeeded",
            "data": {"id": "pi_1", "updatedAt": ACTUALIZADO},
        }
    ).encode()
    evento = await pasarela.parsear_webhook(
        datos, {onvo.ENCABEZADO_WEBHOOK.lower(): SECRETO_WEBHOOK}
    )
    assert evento.proveedor == "onvo"
    assert evento.tipo is TipoEvento.COBRO_CAPTURADO
    assert evento.referencia == "pi_1"
    assert evento.evento_externo_id == f"payment-intent.succeeded:pi_1:{ACTUALIZADO}"

    with pytest.raises(FirmaInvalida):
        await pasarela.parsear_webhook(datos, {onvo.ENCABEZADO_WEBHOOK: "otro"})
    with pytest.raises(FirmaInvalida):
        await pasarela.parsear_webhook(datos, {})

    raro = json.dumps({"type": "algo.nuevo", "data": {}}).encode()
    evento = await pasarela.parsear_webhook(
        raro, {onvo.ENCABEZADO_WEBHOOK: SECRETO_WEBHOOK}
    )
    assert evento.tipo is TipoEvento.DESCONOCIDO
    assert evento.evento_externo_id.startswith("sha256:")

    sin_secreto = Simulador({}).pasarela(configuracion(WEBHOOK_SECRET=None))
    with pytest.raises(OperacionNoSoportada, match="ONVO_WEBHOOK_SECRET"):
        await sin_secreto.parsear_webhook(datos, {})


async def caso_autenticacion_y_url_base() -> None:
    simulador = Simulador({CAPTURAR: responder(201, intencion("succeeded"))})
    await simulador.pasarela(
        configuracion(BASE_URL="https://sandbox.ejemplo.test")
    ).capturar("pi_1", clave_idempotencia="c-1")
    solicitud = simulador.solicitudes[0]
    assert solicitud.headers[onvo.ENCABEZADO_AUTORIZACION] == f"Bearer {CLAVE}"
    assert solicitud.url.host == "sandbox.ejemplo.test"
    # Sin encabezado de idempotencia confirmado, no se inventa uno
    assert onvo.ENCABEZADO_IDEMPOTENCIA is None


CASOS_12: dict[str, Callable[[], Awaitable[None]]] = {
    "autenticacion_y_url_base": caso_autenticacion_y_url_base,
    "crear_cuenta": caso_crear_cuenta,
    "consultar_cuenta": caso_consultar_cuenta,
    "configurar_tarifa": caso_configurar_tarifa,
    "cobrar": caso_cobrar,
    "autorizar": caso_autorizar,
    "capturar": caso_capturar,
    "liberar": caso_liberar,
    "reembolsar": caso_reembolsar,
    "webhook": caso_webhook,
}


@pytest.mark.parametrize("caso", CASOS_12)
async def test_12_cada_operacion_arma_la_solicitud_del_mapeo(caso):
    await CASOS_12[caso]()


# Prueba 13: mapeo de errores

RECHAZO = intencion(
    "requires_payment_method",
    lastPaymentError={"code": "declined", "message": "Fondos insuficientes"},
)

CASOS_13 = {
    "rechazo_de_tarjeta": (
        "cobrar",
        {
            CREAR: responder(201, intencion("requires_payment_method")),
            CONFIRMAR: responder(201, RECHAZO),
        },
        PagoRechazado,
        False,
    ),
    "http_401": (
        "capturar",
        {CAPTURAR: responder(401, {})},
        CredencialesInvalidas,
        False,
    ),
    "http_403": (
        "capturar",
        {CAPTURAR: responder(403, {})},
        CredencialesInvalidas,
        False,
    ),
    "http_500": (
        "capturar",
        {CAPTURAR: responder(500, {})},
        PasarelaNoDisponible,
        True,
    ),
    "http_503": (
        "capturar",
        {CAPTURAR: responder(503, {})},
        PasarelaNoDisponible,
        True,
    ),
    "timeout": ("capturar", {CAPTURAR: timeout}, PasarelaNoDisponible, True),
    "http_400": (
        "capturar",
        {CAPTURAR: responder(400, {"statusCode": 400, "message": ["amountToCapture"]})},
        SolicitudInvalida,
        False,
    ),
    # Sin idempotencia, un timeout al confirmar deja el cobro incierto: un
    # reintento crearia otra intencion y podria cobrar dos veces
    "timeout_al_confirmar": (
        "cobrar",
        {
            CREAR: responder(201, intencion("requires_payment_method")),
            CONFIRMAR: timeout,
        },
        PasarelaNoDisponible,
        False,
    ),
    "timeout_al_crear_intencion": (
        "cobrar",
        {CREAR: timeout},
        PasarelaNoDisponible,
        True,
    ),
}


@pytest.mark.parametrize("caso", CASOS_13)
async def test_13_mapeo_de_errores(caso):
    operacion, rutas, error, reintentable = CASOS_13[caso]
    pasarela = Simulador(rutas).pasarela()

    async def ejecutar():
        if operacion == "cobrar":
            await pasarela.cobrar(cobro())
        else:
            await pasarela.capturar("pi_1", clave_idempotencia="c-1")

    with pytest.raises(error) as capturado:
        await ejecutar()

    assert capturado.value.reintentable is reintentable


# Prueba 14: la clave no se filtra


async def test_14_la_clave_no_aparece_en_repr_ni_en_errores():
    config = configuracion()
    eco = {"message": f"clave invalida {CLAVE}", "error": SECRETO_WEBHOOK}
    errores: list[ErrorPasarela] = []
    for estado in (401, 500, 400):
        pasarela = Simulador({CAPTURAR: responder(estado, eco)}).pasarela(config)
        with pytest.raises(ErrorPasarela) as capturado:
            await pasarela.capturar("pi_1", clave_idempotencia="c-1")
        errores.append(capturado.value)

    pasarela = Simulador({CAPTURAR: timeout}).pasarela(config)
    with pytest.raises(ErrorPasarela) as capturado:
        await pasarela.capturar("pi_1", clave_idempotencia="c-1")
    errores.append(capturado.value)

    with pytest.raises(ErrorPasarela) as capturado:
        await pasarela.parsear_webhook(b"{}", {onvo.ENCABEZADO_WEBHOOK: "otro"})
    errores.append(capturado.value)

    with pytest.raises(CredencialesInvalidas) as capturado:
        PasarelaOnvo(ConfigOnvo(_env_file=None))
    errores.append(capturado.value)

    textos = [repr(pasarela), str(pasarela), repr(config), str(config)]
    textos += [str(e) for e in errores] + [repr(e) for e in errores]
    for texto in textos:
        assert CLAVE not in texto
        assert SECRETO_WEBHOOK not in texto


# Prueba 15: conversion de montos


def test_15_la_conversion_de_montos_no_pierde_centimos():
    # Ejemplos de la documentacion de ONVO
    assert a_unidad_menor(Decimal("2100.89")) == 210089
    assert a_unidad_menor(Decimal("5000.00")) == 500000
    assert a_unidad_menor(Decimal("5000")) == 500000
    assert a_unidad_menor(Decimal("0.01")) == 1
    assert a_unidad_menor(Decimal("99999999999.99")) == 9999999999999

    for centimos in range(1, 100_001, 7):
        monto = Decimal(centimos).scaleb(-2)
        assert a_unidad_menor(monto) == centimos
        assert desde_unidad_menor(centimos) == monto
    assert str(desde_unidad_menor(210089)) == "2100.89"
    assert str(desde_unidad_menor(500000)) == "5000.00"

    # Nunca redondea: una fraccion de centimo es un error, no un redondeo
    with pytest.raises(SolicitudInvalida):
        a_unidad_menor(Decimal("1.005"))
    with pytest.raises(TypeError):
        a_unidad_menor(12.5)
    with pytest.raises(PasarelaNoDisponible):
        desde_unidad_menor(12.5)
