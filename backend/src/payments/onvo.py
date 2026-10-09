"""Adaptador de ONVO Pay.

Todo lo que depende de la API de ONVO vive en el bloque de mapeo de abajo.
Cada entrada lleva su fuente o POR_CONFIRMAR. Cuando ONVO responda las
preguntas abiertas, se corrige ese bloque y nada mas.
"""

import hashlib
import hmac
import json
from collections.abc import Callable, Generator, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from src.payments.config import ConfigOnvo
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
    CredencialesInvalidas,
    ErrorPasarela,
    FirmaInvalida,
    OperacionNoSoportada,
    PagoRechazado,
    PasarelaNoDisponible,
    SolicitudInvalida,
)

# ======================================================================
# MAPEO DE ONVO
# Documentacion consultada el 2026-09-24. OpenAPI version "2.0".
# ======================================================================

PROVEEDOR = "onvo"

# Conexion y autenticacion
# https://docs.onvopay.com/openapi.yaml (servers)
URL_BASE = "https://api.onvopay.com"
# https://docs.onvopay.com/openapi.yaml (securitySchemes.SecretApiKey: http bearer)
# https://docs.onvopay.com/en/payments/marketplaces (Authorization: Bearer <KEY>)
ENCABEZADO_AUTORIZACION = "Authorization"
PREFIJO_AUTORIZACION = "Bearer "
# POR_CONFIRMAR: la documentacion no menciona ningun encabezado de
# idempotencia. Mientras sea None no se envia y la clave solo viaja en metadata.
ENCABEZADO_IDEMPOTENCIA: str | None = None

# Rutas
# https://docs.onvopay.com/en/api/crear-una-cuenta-conectada
RUTA_CREAR_CUENTA = "/v1/connected-accounts"
# https://docs.onvopay.com/en/api/obtener-una-cuenta-conectada (GET)
# https://docs.onvopay.com/en/api/actualizar-una-cuenta-conectada (POST)
RUTA_CUENTA = "/v1/connected-accounts/{id}"
# https://docs.onvopay.com/en/api/crear-una-intencion-de-pago
RUTA_CREAR_INTENCION = "/v1/payment-intents"
# https://docs.onvopay.com/openapi.yaml (paths./v1/payment-intents/{id}.get)
# https://docs.onvopay.com/en/api/obtener-una-intencion-de-pago
RUTA_INTENCION = "/v1/payment-intents/{id}"
# https://docs.onvopay.com/en/api/confirmar-una-intencion-de-pago
RUTA_CONFIRMAR = "/v1/payment-intents/{id}/confirm"
# https://docs.onvopay.com/en/api/capturar-una-intencion-de-pago
RUTA_CAPTURAR = "/v1/payment-intents/{id}/capture"
# https://docs.onvopay.com/en/api/cancelar-una-intencion-de-pago
RUTA_CANCELAR = "/v1/payment-intents/{id}/cancel"
# https://docs.onvopay.com/en/api/crear-un-reembolso
RUTA_REEMBOLSOS = "/v1/refunds"

# Campos de cuenta conectada
# https://docs.onvopay.com/openapi.yaml (requestBodies.CreateConnectedAccount,
# UpdateConnectedAccount, schemas.ConnectedAccountCreateResponse)
CAMPO_NOMBRE_NEGOCIO = "businessName"
LARGO_MAXIMO_NOMBRE_NEGOCIO = 50
CAMPO_TARIFA_MARKETPLACE = "marketplaceAppFee"
CAMPO_URL_ONBOARDING = "onboardingUrl"
# https://docs.onvopay.com/openapi.yaml (requestBodies.CreateConnectedAccount):
# declara additionalProperties: false y solo businessName y marketplaceAppFee.
# POR_CONFIRMAR: la cuenta conectada no admite metadatos, asi que no se
# envian y la clave de idempotencia no llega a ONVO por ninguna via.
CUENTA_CONECTADA_ADMITE_METADATOS = False

# Campos de intencion de pago
# https://docs.onvopay.com/openapi.yaml (schemas.PaymentIntent)
CAMPO_ID = "id"
CAMPO_ESTADO = "status"
CAMPO_MONTO = "amount"
CAMPO_MONEDA = "currency"
CAMPO_DESCRIPCION = "description"
CAMPO_METADATOS = "metadata"
CAMPO_MONTO_CAPTURABLE = "capturableAmount"
CAMPO_MONTO_RECIBIDO = "receivedAmount"
CAMPO_ACTUALIZADO_EN = "updatedAt"
CAMPO_ULTIMO_ERROR = "lastPaymentError"
CAMPO_ERROR_CODIGO = "code"
CAMPO_ERROR_MENSAJE = "message"
# https://docs.onvopay.com/en/payments/marketplaces (Payment intents)
CAMPO_EN_NOMBRE_DE = "onBehalfOf"
# https://docs.onvopay.com/en/payments/manual-capture
CAMPO_METODO_CAPTURA = "captureMethod"
CAPTURA_MANUAL = "manual"
CAPTURA_AUTOMATICA = "automatic"
# https://docs.onvopay.com/openapi.yaml (schemas.ConfirmPaymentIntent)
CAMPO_MEDIO_PAGO = "paymentMethodId"
# 3D Secure. https://docs.onvopay.com/payments/three-ds (consultada el
# 2026-10-08): la confirmacion lleva returnUrl y, si el banco pide
# autenticacion, responde requires_action con
# nextAction {"type": "redirect_to_url", "redirectToUrl": {"url", "returnUrl"}}.
# Al volver, ONVO agrega payment_intent_id al returnUrl; que la autenticacion
# salga bien no garantiza el pago, asi que el estado sale de consultar_cobro.
# POR_CONFIRMAR (preguntas-onvo.md, 19): si acepta un returnUrl con esquema
# propio como artistica://pago.
# POR_CONFIRMAR (preguntas-onvo.md, 20): si una intencion en requires_action
# se puede cancelar, o cuanto tarda en vencer si se abandona.
CAMPO_URL_RETORNO = "returnUrl"
CAMPO_ACCION_SIGUIENTE = "nextAction"
CAMPO_TIPO_ACCION = "type"
CAMPO_REDIRIGIR = "redirectToUrl"
CAMPO_URL = "url"
ACCION_REDIRIGIR = "redirect_to_url"
# https://docs.onvopay.com/openapi.yaml (schemas.CapturePaymentIntent)
CAMPO_MONTO_A_CAPTURAR = "amountToCapture"
# https://docs.onvopay.com/openapi.yaml (schemas.PaymentIntent.metadata):
# hasta 50 pares texto a texto, llave de 40 y valor de 500 caracteres
MAXIMO_METADATOS = 50
LARGO_MAXIMO_LLAVE_METADATO = 40
LARGO_MAXIMO_VALOR_METADATO = 500
# Llave propia, no de ONVO: la metadata es libre
LLAVE_METADATO_IDEMPOTENCIA = "clave_idempotencia"

# Campos de reembolso
# https://docs.onvopay.com/openapi.yaml (schemas.Refund)
# https://docs.onvopay.com/en/payments/refunds
CAMPO_INTENCION_DEL_REEMBOLSO = "paymentIntentId"
CAMPO_MOTIVO_FALLA_REEMBOLSO = "failureReason"
REEMBOLSO_FALLIDO = "failed"

# Estados de intencion de pago
# https://docs.onvopay.com/openapi.yaml (schemas.PaymentIntent.status)
# https://docs.onvopay.com/en/payments/manual-capture
INTENCION_EXITOSA = "succeeded"
INTENCION_REQUIERE_CAPTURA = "requires_capture"
INTENCION_CANCELADA = "canceled"
INTENCION_REQUIERE_ACCION = "requires_action"
INTENCION_SIN_MEDIO_PAGO = "requires_payment_method"
INTENCION_FALLIDA = "failed"
INTENCION_REEMBOLSADA = "refunded"
INTENCION_REEMBOLSADA_PARCIAL = "partially_refunded"
# Una confirmacion declinada vuelve a requires_payment_method
INTENCIONES_RECHAZADAS = frozenset({INTENCION_SIN_MEDIO_PAGO, INTENCION_FALLIDA})

# Foto del cobro para consultar_cobro (DT11).
# https://docs.onvopay.com/openapi.yaml (schemas.PaymentIntent.status)
# requires_payment_method no esta aca: es ambiguo y lo resuelve
# `_estado_cobro` segun lastPaymentError.
# POR_CONFIRMAR: requires_confirmation y deferred no aparecen en el enum
# documentado; deferred solo existe como evento payment-intent.deferred.
# refunded y partially_refunded: el dinero se capturo y despues se
# reembolso desde el dashboard de ONVO. El reembolso es otro dato, no
# un estado distinto del cobro.
ESTADOS_COBRO: Mapping[str, EstadoCobroPasarela] = {
    "requires_confirmation": EstadoCobroPasarela.PENDIENTE,
    "processing": EstadoCobroPasarela.PENDIENTE,
    "deferred": EstadoCobroPasarela.PENDIENTE,
    INTENCION_REQUIERE_ACCION: EstadoCobroPasarela.REQUIERE_ACCION,
    INTENCION_REQUIERE_CAPTURA: EstadoCobroPasarela.AUTORIZADO,
    INTENCION_EXITOSA: EstadoCobroPasarela.CAPTURADO,
    INTENCION_CANCELADA: EstadoCobroPasarela.LIBERADO,
    INTENCION_FALLIDA: EstadoCobroPasarela.FALLIDO,
    INTENCION_REEMBOLSADA: EstadoCobroPasarela.CAPTURADO,
    INTENCION_REEMBOLSADA_PARCIAL: EstadoCobroPasarela.CAPTURADO,
}
# En estos dos receivedAmount ya bajo por el reembolso: informa el neto
# recibido y no lo capturado, asi que monto_capturado queda en None.
INTENCIONES_CON_REEMBOLSO = frozenset(
    {INTENCION_REEMBOLSADA, INTENCION_REEMBOLSADA_PARCIAL}
)

# Estados de cuenta conectada
# https://docs.onvopay.com/en/payments/marketplaces (Account statuses)
# POR_CONFIRMAR: agrupar inactive y las suspensiones como "rechazada" es
# interpretacion nuestra; el contrato solo tiene tres estados.
ESTADOS_CUENTA: Mapping[str, EstadoCuenta] = {
    "pending_onboarding": EstadoCuenta.PENDIENTE,
    "awaiting_approval": EstadoCuenta.PENDIENTE,
    "active": EstadoCuenta.COMPLETADA,
    "inactive": EstadoCuenta.RECHAZADA,
    "temporally_suspended": EstadoCuenta.RECHAZADA,
    "permanently_suspended": EstadoCuenta.RECHAZADA,
    "deleted": EstadoCuenta.RECHAZADA,
}

# Webhooks
# https://docs.onvopay.com/en/webhooks (Security): ONVO manda el secreto del
# webhook tal cual en este encabezado. No es una firma HMAC del cuerpo.
ENCABEZADO_WEBHOOK = "X-Webhook-Secret"
# https://docs.onvopay.com/en/webhooks (Payload format)
CAMPO_EVENTO_TIPO = "type"
CAMPO_EVENTO_DATOS = "data"
PREFIJO_EVENTO_INTENCION = "payment-intent."
# https://docs.onvopay.com/en/webhooks (Supported events)
# POR_CONFIRMAR: no hay eventos documentados para autorizacion aprobada
# (requires_capture), autorizacion vencida, reembolso ni cuenta conectada.
# payment-intent.deferred (SINPE en espera) no tiene equivalente y queda
# como desconocido.
EVENTOS: Mapping[str, TipoEvento] = {
    "payment-intent.succeeded": TipoEvento.COBRO_CAPTURADO,
    "payment-intent.failed": TipoEvento.COBRO_FALLIDO,
}
# POR_CONFIRMAR: el payload no trae id de evento. Se compone con type, data.id
# y data.updatedAt; si falta alguno, con el SHA256 del cuerpo.

# Montos
# https://docs.onvopay.com/openapi.yaml (schemas.PaymentIntent.amount): entero
# en la menor denominacion, centavos para USD y centimos para CRC
# (2100.89 CRC se envia como 210089).
# https://docs.onvopay.com/en/webhooks: 500000 representa 5000.00 CRC
DECIMALES_UNIDAD_MENOR = 2
MONEDAS = frozenset({"CRC", "USD"})

# Errores HTTP
# https://docs.onvopay.com/en/reference/errors
HTTP_CREDENCIALES = frozenset({401, 403})
# POR_CONFIRMAR: 429 no esta en la tabla de ONVO; se trata como no disponible
HTTP_NO_DISPONIBLE_EXTRA = frozenset({429})
# POR_CONFIRMAR: si algun rechazo de pago llega como codigo HTTP en vez de
# requires_payment_method con lastPaymentError. Vacio hasta confirmarlo.
HTTP_RECHAZO: frozenset[int] = frozenset()
# POR_CONFIRMAR: codigo de error de ONVO al capturar una autorizacion vencida.
# Vacio hasta confirmarlo: hoy llega como SolicitudInvalida.
CODIGOS_AUTORIZACION_VENCIDA: frozenset[str] = frozenset()
# https://docs.onvopay.com/en/payments/marketplaces (domain errors: code, message)
# https://docs.onvopay.com/openapi.yaml (schemas.ValidationError: message, error)
CAMPOS_DETALLE_ERROR = ("code", "message", "error")

# Capacidades. Las incognitas quedan en su valor mas conservador.
# https://docs.onvopay.com/en/payments/manual-capture: autorizacion diferida
# solo con tarjeta y en integraciones 100 % API
AUTORIZACION_DIFERIDA = frozenset({MetodoPago.TARJETA})
# POR_CONFIRMAR incognita 3: SINPE Movil en modo marketplace
METODOS = frozenset({MetodoPago.TARJETA})
# Incognita 1. https://docs.onvopay.com/openapi.yaml (descripcion de
# requestBodies.CreatePaymentIntent.captureMethod): si no se captura en
# "un maximo de 30 dias", los fondos vuelven al cliente. Es un maximo, no
# un minimo garantizado: el emisor de la tarjeta puede vencer la
# autorizacion antes. POR_CONFIRMAR cuanto dura de verdad, asi que queda
# en None y rige el plazo propio de 5 dias (D9).
DIAS_VIGENCIA_AUTORIZACION: int | None = None
# https://docs.onvopay.com/en/payments/marketplaces: marketplaceAppFee es por
# cuenta. POR_CONFIRMAR incognita 4: si existe tambien por cobro.
COMISION_POR_COBRO = False
# POR_CONFIRMAR incognita 5
REVIERTE_COMISION_EN_REEMBOLSO: bool | None = None
RESPONSABLE_CONTRACARGOS: ResponsableContracargos | None = None
# POR_CONFIRMAR incognita 2
RETENCION_LIQUIDACION_POR_COBRO: bool | None = None
# POR_CONFIRMAR incognita 6
ONBOARDING_PERSONA_FISICA: bool | None = None
# POR_CONFIRMAR: no hay idempotencia documentada
SOPORTA_IDEMPOTENCIA = False

# ======================================================================
# FIN DEL MAPEO
# ======================================================================

CAPACIDADES = Capacidades(
    metodos=METODOS,
    autorizacion_diferida=AUTORIZACION_DIFERIDA,
    dias_vigencia_autorizacion=DIAS_VIGENCIA_AUTORIZACION,
    comision_por_cobro=COMISION_POR_COBRO,
    revierte_comision_en_reembolso=REVIERTE_COMISION_EN_REEMBOLSO,
    soporta_idempotencia=SOPORTA_IDEMPOTENCIA,
    retencion_liquidacion_por_cobro=RETENCION_LIQUIDACION_POR_COBRO,
    responsable_contracargos=RESPONSABLE_CONTRACARGOS,
    onboarding_persona_fisica=ONBOARDING_PERSONA_FISICA,
)

_ESCALA = Decimal(10) ** DECIMALES_UNIDAD_MENOR


def a_unidad_menor(monto: Decimal) -> int:
    """Decimal en colones a entero en centimos. Nunca redondea."""
    validar_monto(monto)
    return int(monto * _ESCALA)


def desde_unidad_menor(valor: object) -> Decimal:
    """Entero en centimos a Decimal en colones con dos decimales."""
    if isinstance(valor, bool) or not isinstance(valor, int | Decimal):
        raise _respuesta_inesperada("Monto del proveedor con tipo inesperado")
    decimal = Decimal(valor)
    if decimal != decimal.to_integral_value():
        raise _respuesta_inesperada("Monto del proveedor con fracciones")
    return decimal.scaleb(-DECIMALES_UNIDAD_MENOR)


class _Bearer(httpx.Auth):
    """Pone la clave en la solicitud sin dejarla en variables locales."""

    def __init__(self, clave: SecretStr) -> None:
        self._clave = clave

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers[ENCABEZADO_AUTORIZACION] = (
            PREFIJO_AUTORIZACION + self._clave.get_secret_value()
        )
        yield request

    def __repr__(self) -> str:
        return "_Bearer(**********)"


def _reloj_utc() -> datetime:
    return datetime.now(UTC)


class PasarelaOnvo:
    def __init__(
        self,
        config: ConfigOnvo,
        *,
        cliente: httpx.AsyncClient | None = None,
        reloj: Callable[[], datetime] = _reloj_utc,
    ) -> None:
        if config.API_KEY is None or not config.API_KEY.get_secret_value().strip():
            raise CredencialesInvalidas("Falta ONVO_API_KEY")
        self._config = config
        self._auth = _Bearer(config.API_KEY)
        self._url_base = str(config.BASE_URL or URL_BASE).rstrip("/")
        self._timeout = httpx.Timeout(config.TIMEOUT_SEGUNDOS)
        self._cliente_propio = cliente is None
        self._cliente = cliente or httpx.AsyncClient(timeout=self._timeout)
        self._reloj = reloj

    def __repr__(self) -> str:
        return f"PasarelaOnvo(url_base={self._url_base!r})"

    @property
    def capacidades(self) -> Capacidades:
        return CAPACIDADES

    async def cerrar(self) -> None:
        if self._cliente_propio:
            await self._cliente.aclose()

    # Cuentas conectadas

    async def crear_cuenta_conectada(
        self,
        *,
        nombre: str,
        tarifa_porcentaje: Decimal,
        clave_idempotencia: str,
        metadatos: Mapping[str, str] = SIN_METADATOS,
    ) -> CuentaConectada:
        nombre = nombre.strip() if isinstance(nombre, str) else ""
        if not 1 <= len(nombre) <= LARGO_MAXIMO_NOMBRE_NEGOCIO:
            raise SolicitudInvalida(
                f"El nombre de la cuenta necesita de 1 a "
                f"{LARGO_MAXIMO_NOMBRE_NEGOCIO} caracteres"
            )
        validar_tarifa(tarifa_porcentaje)
        validar_clave(clave_idempotencia)
        validar_metadatos(metadatos)
        cuerpo: dict[str, Any] = {
            CAMPO_NOMBRE_NEGOCIO: nombre,
            CAMPO_TARIFA_MARKETPLACE: tarifa_porcentaje,
        }
        if metadatos and CUENTA_CONECTADA_ADMITE_METADATOS:
            cuerpo[CAMPO_METADATOS] = dict(metadatos)
        # Crear dos veces duplica la cuenta: un resultado incierto no se repite.
        # Sin idempotencia en ONVO la clave solo sirve del lado de quien llama.
        datos = await self._solicitar(
            "POST",
            RUTA_CREAR_CUENTA,
            cuerpo,
            repetible=False,
            clave_idempotencia=clave_idempotencia,
        )
        url = datos.get(CAMPO_URL_ONBOARDING)
        return CuentaConectada(
            id=_texto(datos, CAMPO_ID),
            estado=_estado_cuenta(datos),
            url_onboarding=url if isinstance(url, str) else None,
        )

    async def consultar_cuenta(self, cuenta_id: str) -> CuentaConectada:
        validar_referencia(cuenta_id)
        datos = await self._solicitar(
            "GET", _ruta(RUTA_CUENTA, cuenta_id), repetible=True
        )
        return CuentaConectada(id=_texto(datos, CAMPO_ID), estado=_estado_cuenta(datos))

    async def configurar_tarifa(
        self, cuenta_id: str, tarifa_porcentaje: Decimal
    ) -> None:
        validar_referencia(cuenta_id)
        validar_tarifa(tarifa_porcentaje)
        await self._solicitar(
            "POST",
            _ruta(RUTA_CUENTA, cuenta_id),
            {CAMPO_TARIFA_MARKETPLACE: tarifa_porcentaje},
            repetible=True,
        )

    # Cobros

    async def cobrar(self, solicitud: SolicitudCobro) -> ResultadoCobro:
        intencion = await self._crear_y_confirmar(solicitud, diferida=False)
        if intencion.get(CAMPO_ESTADO) == INTENCION_REQUIERE_ACCION:
            return _requiere_accion(intencion, solicitud)
        return ResultadoCobro(
            referencia=_texto(intencion, CAMPO_ID),
            estado=EstadoOperacion.CAPTURADO,
            monto=_monto(intencion, CAMPO_MONTO_RECIBIDO, CAMPO_MONTO),
            capturado_en=self._fecha(intencion),
        )

    async def autorizar(self, solicitud: SolicitudCobro) -> ResultadoCobro:
        intencion = await self._crear_y_confirmar(solicitud, diferida=True)
        if intencion.get(CAMPO_ESTADO) == INTENCION_REQUIERE_ACCION:
            return _requiere_accion(intencion, solicitud)
        dias = CAPACIDADES.dias_vigencia_autorizacion
        return ResultadoCobro(
            referencia=_texto(intencion, CAMPO_ID),
            estado=EstadoOperacion.AUTORIZADO,
            monto=_monto(intencion, CAMPO_MONTO_CAPTURABLE, CAMPO_MONTO),
            autorizado_hasta=(
                None if dias is None else self._reloj() + timedelta(days=dias)
            ),
        )

    async def capturar(
        self,
        referencia: str,
        *,
        clave_idempotencia: str,
        monto: Decimal | None = None,
    ) -> ResultadoCobro:
        validar_referencia(referencia)
        validar_clave(clave_idempotencia)
        cuerpo = (
            {} if monto is None else {CAMPO_MONTO_A_CAPTURAR: a_unidad_menor(monto)}
        )
        # Repetir una captura sobre la misma intencion no captura dos veces
        intencion = await self._solicitar(
            "POST",
            _ruta(RUTA_CAPTURAR, referencia),
            cuerpo,
            repetible=True,
            clave_idempotencia=clave_idempotencia,
        )
        _exigir_estado(intencion, INTENCION_EXITOSA)
        return ResultadoCobro(
            referencia=referencia,
            estado=EstadoOperacion.CAPTURADO,
            monto=_monto(intencion, CAMPO_MONTO_RECIBIDO, CAMPO_MONTO),
            capturado_en=self._fecha(intencion),
        )

    async def liberar_autorizacion(
        self, referencia: str, *, clave_idempotencia: str
    ) -> ResultadoCobro:
        validar_referencia(referencia)
        validar_clave(clave_idempotencia)
        intencion = await self._solicitar(
            "POST",
            _ruta(RUTA_CANCELAR, referencia),
            repetible=True,
            clave_idempotencia=clave_idempotencia,
        )
        _exigir_estado(intencion, INTENCION_CANCELADA)
        return ResultadoCobro(
            referencia=referencia,
            estado=EstadoOperacion.LIBERADO,
            monto=_monto(intencion, CAMPO_MONTO),
        )

    async def reembolsar(
        self, referencia: str, *, monto: Decimal, clave_idempotencia: str
    ) -> ResultadoReembolso:
        validar_referencia(referencia)
        validar_clave(clave_idempotencia)
        reembolso = await self._solicitar(
            "POST",
            RUTA_REEMBOLSOS,
            {
                CAMPO_INTENCION_DEL_REEMBOLSO: referencia,
                CAMPO_MONTO: a_unidad_menor(monto),
            },
            repetible=CAPACIDADES.soporta_idempotencia,
            clave_idempotencia=clave_idempotencia,
        )
        if reembolso.get(CAMPO_ESTADO) == REEMBOLSO_FALLIDO:
            motivo = reembolso.get(CAMPO_MOTIVO_FALLA_REEMBOLSO)
            raise PagoRechazado(f"ONVO rechazo el reembolso: {self._limpiar(motivo)}")
        return ResultadoReembolso(
            referencia_cobro=referencia,
            referencia_reembolso=_texto(reembolso, CAMPO_ID),
            monto=_monto(reembolso, CAMPO_MONTO),
            # ONVO no informa el acumulado en la respuesta del reembolso
            total_reembolsado=None,
        )

    async def consultar_cobro(self, referencia: str) -> ConsultaCobro:
        validar_referencia(referencia)
        intencion = await self._solicitar(
            "GET", _ruta(RUTA_INTENCION, referencia), repetible=True
        )
        estado = _estado_cobro(intencion)
        return ConsultaCobro(
            referencia=_texto(intencion, CAMPO_ID),
            estado=estado,
            monto=_monto(intencion, CAMPO_MONTO),
            monto_capturado=_monto_capturado(intencion),
            # POR_CONFIRMAR: ONVO no expone el acumulado reembolsado
            monto_reembolsado=None,
            # POR_CONFIRMAR: ONVO no informa cuando vence la autorizacion. Quien
            # llama aplica PoliticasPedido.vencimiento_autorizacion (D9).
            autorizado_hasta=None,
            metadatos=_metadatos_recibidos(intencion),
            url_autenticacion=(
                _url_autenticacion(intencion)
                if estado is EstadoCobroPasarela.REQUIERE_ACCION
                else None
            ),
        )

    # Webhooks

    async def parsear_webhook(
        self, cuerpo: bytes, encabezados: Mapping[str, str]
    ) -> EventoRecibido:
        secreto = self._config.WEBHOOK_SECRET
        if secreto is None or not secreto.get_secret_value():
            raise OperacionNoSoportada(
                "Falta ONVO_WEBHOOK_SECRET: no se puede verificar el origen del "
                "webhook y no se acepta ningun evento"
            )
        recibido = buscar_encabezado(encabezados, ENCABEZADO_WEBHOOK)
        if recibido is None or not hmac.compare_digest(
            recibido.encode(), secreto.get_secret_value().encode()
        ):
            raise FirmaInvalida("El webhook no trae el secreto esperado")
        try:
            payload = json.loads(cuerpo)
        except ValueError:
            raise SolicitudInvalida("El webhook no es JSON") from None
        if not isinstance(payload, dict):
            raise SolicitudInvalida("El webhook no es un objeto JSON")

        tipo_externo = payload.get(CAMPO_EVENTO_TIPO)
        datos = payload.get(CAMPO_EVENTO_DATOS)
        datos = datos if isinstance(datos, dict) else {}
        id_objeto = datos.get(CAMPO_ID)
        actualizado = datos.get(CAMPO_ACTUALIZADO_EN)
        if all(isinstance(v, str) for v in (tipo_externo, id_objeto, actualizado)):
            evento_id = f"{tipo_externo}:{id_objeto}:{actualizado}"
        else:
            evento_id = "sha256:" + hashlib.sha256(cuerpo).hexdigest()
        es_de_intencion = isinstance(tipo_externo, str) and tipo_externo.startswith(
            PREFIJO_EVENTO_INTENCION
        )
        return EventoRecibido(
            proveedor=PROVEEDOR,
            evento_externo_id=evento_id,
            tipo=EVENTOS.get(tipo_externo, TipoEvento.DESCONOCIDO)
            if isinstance(tipo_externo, str)
            else TipoEvento.DESCONOCIDO,
            referencia=(
                id_objeto if es_de_intencion and isinstance(id_objeto, str) else None
            ),
            payload=payload,
        )

    # Internos

    async def _crear_y_confirmar(
        self, solicitud: SolicitudCobro, *, diferida: bool
    ) -> dict[str, Any]:
        validar_solicitud(solicitud, CAPACIDADES, diferida=diferida)
        if solicitud.moneda not in MONEDAS:
            raise SolicitudInvalida(f"Moneda no soportada: {solicitud.moneda}")
        if not solicitud.medio_pago_id:
            raise SolicitudInvalida(
                "ONVO necesita medio_pago_id: el medio de pago se tokeniza en el "
                "cliente con la clave publicable"
            )
        metadatos = _metadatos(solicitud)
        cuerpo: dict[str, Any] = {
            CAMPO_MONTO: a_unidad_menor(solicitud.monto),
            CAMPO_MONEDA: solicitud.moneda,
            CAMPO_EN_NOMBRE_DE: solicitud.cuenta_conectada_id,
            CAMPO_METODO_CAPTURA: CAPTURA_MANUAL if diferida else CAPTURA_AUTOMATICA,
            CAMPO_METADATOS: metadatos,
        }
        if solicitud.descripcion:
            cuerpo[CAMPO_DESCRIPCION] = solicitud.descripcion
        # Crear la intencion no mueve dinero: repetirla deja a lo sumo una
        # intencion huerfana sin confirmar.
        intencion = await self._solicitar(
            "POST",
            RUTA_CREAR_INTENCION,
            cuerpo,
            repetible=True,
            clave_idempotencia=solicitud.clave_idempotencia,
        )
        confirmacion = {CAMPO_MEDIO_PAGO: solicitud.medio_pago_id}
        if solicitud.url_retorno is not None:
            confirmacion[CAMPO_URL_RETORNO] = solicitud.url_retorno
        # Confirmar si mueve dinero. Sin idempotencia, un resultado incierto no
        # se puede repetir: un reintento crearia otra intencion y cobraria dos
        # veces. Se reconcilia por webhook o metadata.
        confirmada = await self._solicitar(
            "POST",
            _ruta(RUTA_CONFIRMAR, _texto(intencion, CAMPO_ID)),
            confirmacion,
            repetible=CAPACIDADES.soporta_idempotencia,
            clave_idempotencia=solicitud.clave_idempotencia,
        )
        # 3DS: el cliente se autentica afuera y el resultado sale de
        # consultar_cobro. Lo resuelven cobrar y autorizar
        if confirmada.get(CAMPO_ESTADO) == INTENCION_REQUIERE_ACCION:
            return confirmada
        _exigir_estado(
            confirmada,
            INTENCION_REQUIERE_CAPTURA if diferida else INTENCION_EXITOSA,
        )
        return confirmada

    async def _solicitar(
        self,
        metodo: str,
        ruta: str,
        cuerpo: Mapping[str, Any] | None = None,
        *,
        repetible: bool,
        clave_idempotencia: str | None = None,
    ) -> dict[str, Any]:
        encabezados = {"Accept": "application/json"}
        contenido = None
        if cuerpo is not None:
            contenido = _a_json(cuerpo).encode()
            encabezados["Content-Type"] = "application/json"
        if ENCABEZADO_IDEMPOTENCIA and clave_idempotencia:
            encabezados[ENCABEZADO_IDEMPOTENCIA] = clave_idempotencia
        try:
            respuesta = await self._cliente.request(
                metodo,
                self._url_base + ruta,
                content=contenido,
                headers=encabezados,
                auth=self._auth,
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            raise PasarelaNoDisponible(
                f"ONVO no respondio a tiempo: {metodo} {ruta}", reintentable=repetible
            ) from None
        except httpx.TransportError:
            raise PasarelaNoDisponible(
                f"Error de red con ONVO: {metodo} {ruta}", reintentable=repetible
            ) from None
        return self._interpretar(respuesta, repetible=repetible)

    def _interpretar(
        self, respuesta: httpx.Response, *, repetible: bool
    ) -> dict[str, Any]:
        codigo = respuesta.status_code
        datos = _json_o_nada(respuesta)
        if 200 <= codigo < 300:
            if datos is None:
                raise _respuesta_inesperada("ONVO respondio sin un objeto JSON")
            return datos
        detalle = self._limpiar(_detalle(datos))
        if codigo in HTTP_CREDENCIALES:
            raise CredencialesInvalidas(
                f"ONVO rechazo las credenciales (HTTP {codigo})"
            )
        if codigo >= 500 or codigo in HTTP_NO_DISPONIBLE_EXTRA:
            raise PasarelaNoDisponible(
                f"ONVO no disponible (HTTP {codigo}): {detalle}", reintentable=repetible
            )
        if codigo in HTTP_RECHAZO:
            raise PagoRechazado(f"ONVO rechazo el pago (HTTP {codigo}): {detalle}")
        codigo_error = datos.get(CAMPO_ERROR_CODIGO) if datos else None
        if isinstance(codigo_error, str) and codigo_error in (
            CODIGOS_AUTORIZACION_VENCIDA
        ):
            raise AutorizacionVencida(f"La autorizacion vencio: {detalle}")
        raise SolicitudInvalida(f"ONVO rechazo la solicitud (HTTP {codigo}): {detalle}")

    def _limpiar(self, texto: object) -> str:
        """Ningun secreto sale en un mensaje, aunque el proveedor lo devuelva."""
        limpio = str(texto)[:300] if texto is not None else ""
        for secreto in (self._config.API_KEY, self._config.WEBHOOK_SECRET):
            if secreto is not None and secreto.get_secret_value():
                limpio = limpio.replace(secreto.get_secret_value(), "**********")
        return limpio

    def _fecha(self, datos: Mapping[str, Any]) -> datetime:
        valor = datos.get(CAMPO_ACTUALIZADO_EN)
        if isinstance(valor, str):
            try:
                fecha = datetime.fromisoformat(valor)
            except ValueError:
                fecha = None
            if fecha is not None and fecha.tzinfo is not None:
                return fecha
        return self._reloj()


# Auxiliares sin estado


def _ruta(plantilla: str, identificador: str) -> str:
    return plantilla.format(id=quote(identificador, safe=""))


def _a_json(valor: object) -> str:
    """JSON sin pasar por float: los Decimal salen como numero exacto."""
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if valor is None or isinstance(valor, bool | int | str):
        return json.dumps(valor)
    if isinstance(valor, Mapping):
        pares = (f"{json.dumps(str(k))}:{_a_json(v)}" for k, v in valor.items())
        return "{" + ",".join(pares) + "}"
    raise TypeError(f"No serializable: {type(valor).__name__}")


def _json_o_nada(respuesta: httpx.Response) -> dict[str, Any] | None:
    try:
        datos = json.loads(respuesta.content, parse_float=Decimal)
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None


def _detalle(datos: Mapping[str, Any] | None) -> str:
    if not datos:
        return "sin detalle"
    partes = []
    for campo in CAMPOS_DETALLE_ERROR:
        valor = datos.get(campo)
        if isinstance(valor, list):
            valor = "; ".join(str(v) for v in valor)
        if valor:
            partes.append(str(valor))
    return " | ".join(partes) or "sin detalle"


def _texto(datos: Mapping[str, Any], campo: str) -> str:
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor:
        raise _respuesta_inesperada(f"ONVO respondio sin {campo}")
    return valor


def _monto(datos: Mapping[str, Any], *campos: str) -> Decimal:
    for campo in campos:
        if datos.get(campo) is not None:
            return desde_unidad_menor(datos[campo])
    raise _respuesta_inesperada(f"ONVO respondio sin {campos[0]}")


def _monto_opcional(datos: Mapping[str, Any], campo: str) -> Decimal | None:
    valor = datos.get(campo)
    return None if valor is None else desde_unidad_menor(valor)


def _metadatos_recibidos(datos: Mapping[str, Any]) -> dict[str, str]:
    crudos = datos.get(CAMPO_METADATOS)
    if not isinstance(crudos, Mapping):
        return {}
    # Lo que no sea texto a texto se descarta: el contrato promete texto
    return {
        k: v for k, v in crudos.items() if isinstance(k, str) and isinstance(v, str)
    }


def _monto_capturado(intencion: Mapping[str, Any]) -> Decimal | None:
    # Con un reembolso de por medio receivedAmount es el neto recibido y no lo
    # capturado: antes que informar un monto equivocado, no se informa ninguno
    if intencion.get(CAMPO_ESTADO) in INTENCIONES_CON_REEMBOLSO:
        return None
    return _monto_opcional(intencion, CAMPO_MONTO_RECIBIDO)


def _estado_cobro(intencion: Mapping[str, Any]) -> EstadoCobroPasarela:
    estado = intencion.get(CAMPO_ESTADO)
    if estado == INTENCION_SIN_MEDIO_PAGO:
        # Sin lastPaymentError todavia no hubo intento; con el, fue declinado
        return (
            EstadoCobroPasarela.FALLIDO
            if intencion.get(CAMPO_ULTIMO_ERROR)
            else EstadoCobroPasarela.PENDIENTE
        )
    if isinstance(estado, str) and estado in ESTADOS_COBRO:
        return ESTADOS_COBRO[estado]
    # No se adivina: un estado fuera de la tabla no mueve dinero
    raise _respuesta_inesperada(f"Estado de cobro desconocido: {estado!r}")


def _estado_cuenta(datos: Mapping[str, Any]) -> EstadoCuenta:
    # Un estado desconocido no habilita cobros
    return ESTADOS_CUENTA.get(datos.get(CAMPO_ESTADO), EstadoCuenta.PENDIENTE)


def _exigir_estado(intencion: Mapping[str, Any], esperado: str) -> None:
    estado = intencion.get(CAMPO_ESTADO)
    if estado == esperado:
        return
    if estado in INTENCIONES_RECHAZADAS:
        error = intencion.get(CAMPO_ULTIMO_ERROR)
        error = error if isinstance(error, dict) else {}
        codigo = error.get(CAMPO_ERROR_CODIGO) or "sin codigo"
        mensaje = error.get(CAMPO_ERROR_MENSAJE) or "sin mensaje"
        raise PagoRechazado(f"ONVO rechazo el pago: {codigo}: {mensaje}"[:300])
    if estado == INTENCION_REQUIERE_ACCION:
        # cobrar y autorizar lo resuelven antes; aca solo llega una operacion
        # sobre un cobro que todavia espera la autenticacion del cliente
        raise SolicitudInvalida(
            f"El cobro espera la autenticacion del cliente, no esta {esperado!r}"
        )
    raise _respuesta_inesperada(
        f"Estado {estado!r} cuando se esperaba {esperado!r}: reconciliar"
    )


def _url_autenticacion(intencion: Mapping[str, Any]) -> str | None:
    """nextAction.redirectToUrl.url, o None si no viene como redirect_to_url."""
    accion = intencion.get(CAMPO_ACCION_SIGUIENTE)
    if not isinstance(accion, Mapping) or (
        accion.get(CAMPO_TIPO_ACCION) != ACCION_REDIRIGIR
    ):
        return None
    redirigir = accion.get(CAMPO_REDIRIGIR)
    url = redirigir.get(CAMPO_URL) if isinstance(redirigir, Mapping) else None
    return url if isinstance(url, str) and url else None


def _requiere_accion(
    intencion: Mapping[str, Any], solicitud: SolicitudCobro
) -> ResultadoCobro:
    url = _url_autenticacion(intencion)
    if url is None:
        # El cobro quedo a medias y sin forma de seguir: se reconcilia
        raise _respuesta_inesperada(
            "ONVO pidio una accion del cliente sin nextAction.redirectToUrl.url"
        )
    return ResultadoCobro(
        referencia=_texto(intencion, CAMPO_ID),
        estado=EstadoOperacion.REQUIERE_ACCION,
        monto=solicitud.monto,
        url_autenticacion=url,
    )


def _respuesta_inesperada(mensaje: str) -> ErrorPasarela:
    # El efecto pudo haber ocurrido: no se reintenta a ciegas
    return PasarelaNoDisponible(mensaje, reintentable=False)


def _metadatos(solicitud: SolicitudCobro) -> dict[str, str]:
    metadatos = dict(solicitud.metadatos)
    metadatos[LLAVE_METADATO_IDEMPOTENCIA] = solicitud.clave_idempotencia
    if len(metadatos) > MAXIMO_METADATOS or any(
        len(k) > LARGO_MAXIMO_LLAVE_METADATO or len(v) > LARGO_MAXIMO_VALOR_METADATO
        for k, v in metadatos.items()
    ):
        raise SolicitudInvalida("Los metadatos exceden los limites de ONVO")
    return metadatos
