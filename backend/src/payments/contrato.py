"""Contrato de la pasarela de pagos.

Nada fuera de `src.payments` conoce al proveedor: todo pasa por este contrato.
La capa no conoce los pedidos; quien llama pone sus ids en `metadatos`.

Las incognitas del proveedor se declaran en `Capacidades`, nunca como
constantes sueltas. `None` en una capacidad significa "no se sabe": quien llama
tiene que tratarlo como el caso mas desfavorable.
"""

import enum
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from src.payments.errores import OperacionNoSoportada, SolicitudInvalida

CENTIMO = Decimal("0.01")
CIEN = Decimal("100")
# Default inmutable para los metadatos opcionales
SIN_METADATOS: Mapping[str, str] = MappingProxyType({})
# Esquema segun RFC 3986, "://" y algo despues, sin espacios
_URL_CON_ESQUEMA = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://\S+")


class MetodoPago(enum.StrEnum):
    TARJETA = "tarjeta"
    SINPE_MOVIL = "sinpe_movil"


class EstadoCuenta(enum.StrEnum):
    PENDIENTE = "pendiente"
    COMPLETADA = "completada"
    RECHAZADA = "rechazada"


class EstadoOperacion(enum.StrEnum):
    """Resultado de una operacion, no la foto de un cobro."""

    AUTORIZADO = "autorizado"
    CAPTURADO = "capturado"
    LIBERADO = "liberado"
    # El cliente tiene que autenticarse (3DS). Todavia no se movio dinero
    REQUIERE_ACCION = "requiere_accion"


class EstadoCobroPasarela(enum.StrEnum):
    """Foto de un cobro segun la pasarela. La da `consultar_cobro`."""

    PENDIENTE = "pendiente"  # creado o en proceso, sin resultado
    REQUIERE_ACCION = "requiere_accion"  # 3DS u otra accion del cliente
    AUTORIZADO = "autorizado"  # capturable
    CAPTURADO = "capturado"
    LIBERADO = "liberado"  # cancelado, o autorizacion vencida
    FALLIDO = "fallido"


class ResponsableContracargos(enum.StrEnum):
    PLATAFORMA = "plataforma"
    CUENTA_CONECTADA = "cuenta_conectada"


class TipoEvento(enum.StrEnum):
    COBRO_AUTORIZADO = "cobro_autorizado"
    COBRO_CAPTURADO = "cobro_capturado"
    COBRO_FALLIDO = "cobro_fallido"
    AUTORIZACION_VENCIDA = "autorizacion_vencida"
    REEMBOLSO_CONFIRMADO = "reembolso_confirmado"
    CUENTA_ACTUALIZADA = "cuenta_actualizada"
    DESCONOCIDO = "desconocido"


@dataclass(frozen=True, kw_only=True)
class Capacidades:
    """Lo que el adaptador puede hacer. Cada incognita del proveedor vive aca."""

    metodos: frozenset[MetodoPago]
    # Metodos que admiten autorizar ahora y capturar despues
    autorizacion_diferida: frozenset[MetodoPago]
    # Incognita 1. None: no se sabe cuanto dura una autorizacion
    dias_vigencia_autorizacion: int | None
    # Incognita 4. False: la comision solo se fija por cuenta conectada
    comision_por_cobro: bool
    # Incognita 5, parte comision. None: no se sabe si se revierte
    revierte_comision_en_reembolso: bool | None
    soporta_idempotencia: bool
    # Incognita 2. None: no se sabe si se puede retener la liquidacion por cobro
    retencion_liquidacion_por_cobro: bool | None = None
    # Incognita 5, parte contracargos. None: no se sabe quien los absorbe
    responsable_contracargos: ResponsableContracargos | None = None
    # Incognita 6. None: no se sabe si una persona fisica sin actividad
    # inscrita en Hacienda puede completar el onboarding
    onboarding_persona_fisica: bool | None = None
    # La incognita 3 (SINPE en marketplace) es `SINPE_MOVIL in metodos`.


@dataclass(frozen=True, kw_only=True)
class SolicitudCobro:
    monto: Decimal
    metodo: MetodoPago
    cuenta_conectada_id: str
    clave_idempotencia: str
    descripcion: str = ""
    moneda: str = "CRC"
    # Solo si `capacidades.comision_por_cobro`. Si no, la tarifa es la de la
    # cuenta conectada y se fija con `configurar_tarifa`.
    tarifa_porcentaje: Decimal | None = None
    # Ids de pedido y cobro de quien llama. La capa solo los transporta.
    metadatos: Mapping[str, str] = field(default_factory=dict)
    # Medio de pago tokenizado en el cliente. Nunca datos de tarjeta en claro.
    medio_pago_id: str | None = None
    # A donde vuelve el cliente despues de autenticarse (3DS)
    url_retorno: str | None = None


@dataclass(frozen=True, kw_only=True)
class ResultadoCobro:
    # Una referencia por cobro: la de `autorizar` sirve para capturar,
    # liberar y reembolsar. Es `cobros.referencia_pasarela`.
    referencia: str
    estado: EstadoOperacion
    monto: Decimal
    autorizado_hasta: datetime | None = None
    capturado_en: datetime | None = None
    # Solo con REQUIERE_ACCION, y en ese caso nunca nula. Sensible: se le da
    # solo al cliente que paga, nunca a logs
    url_autenticacion: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        requiere = self.estado is EstadoOperacion.REQUIERE_ACCION
        if requiere != (self.url_autenticacion is not None):
            raise ValueError("url_autenticacion va solo y siempre con REQUIERE_ACCION")


@dataclass(frozen=True, kw_only=True)
class ConsultaCobro:
    """Lo que la pasarela dice hoy del cobro. Nunca se mueve dinero por un
    webhook solo: antes se consulta el cobro y se cree esta foto."""

    referencia: str
    estado: EstadoCobroPasarela
    monto: Decimal
    monto_capturado: Decimal | None  # None si el proveedor no lo informa
    monto_reembolsado: Decimal | None  # None si el proveedor no lo informa
    autorizado_hasta: datetime | None
    metadatos: Mapping[str, str]
    # Con REQUIERE_ACCION, si el proveedor la informa. Sensible como la de
    # ResultadoCobro
    url_autenticacion: str | None = field(default=None, repr=False)


@dataclass(frozen=True, kw_only=True)
class ResultadoReembolso:
    referencia_cobro: str
    referencia_reembolso: str
    monto: Decimal
    # None si el proveedor no informa el acumulado
    total_reembolsado: Decimal | None


@dataclass(frozen=True, kw_only=True)
class CuentaConectada:
    id: str
    estado: EstadoCuenta
    # Sensible: se le da solo al artista dueno de la cuenta, nunca a logs
    url_onboarding: str | None = field(default=None, repr=False)


@dataclass(frozen=True, kw_only=True)
class EventoRecibido:
    """Coincide con las columnas de `eventos_pasarela`."""

    proveedor: str
    evento_externo_id: str
    tipo: TipoEvento
    referencia: str | None
    payload: Mapping[str, Any]


@runtime_checkable
class PasarelaDePagos(Protocol):
    @property
    def capacidades(self) -> Capacidades: ...

    async def crear_cuenta_conectada(
        self,
        *,
        nombre: str,
        tarifa_porcentaje: Decimal,
        clave_idempotencia: str,
        metadatos: Mapping[str, str] = SIN_METADATOS,
    ) -> CuentaConectada: ...

    async def consultar_cuenta(self, cuenta_id: str) -> CuentaConectada: ...

    async def configurar_tarifa(
        self, cuenta_id: str, tarifa_porcentaje: Decimal
    ) -> None: ...

    async def cobrar(self, solicitud: SolicitudCobro) -> ResultadoCobro:
        """Cobra en un paso.

        Devuelve `CAPTURADO`, o `REQUIERE_ACCION` con la referencia y
        `url_autenticacion` si el banco pide 3DS. En ese caso el cobro todavia
        no movio dinero: quien llama manda al cliente a la URL y sigue con
        `consultar_cobro(referencia)` hasta ver `CAPTURADO`, `FALLIDO` o
        `LIBERADO`. Que el cliente vuelva no prueba que se haya pagado.
        """
        ...

    async def autorizar(self, solicitud: SolicitudCobro) -> ResultadoCobro:
        """Autoriza para capturar despues.

        Devuelve `AUTORIZADO`, o `REQUIERE_ACCION` con la referencia y
        `url_autenticacion` si el banco pide 3DS. En ese caso el cobro todavia
        no movio dinero: quien llama sigue con `consultar_cobro(referencia)`
        hasta ver `AUTORIZADO`, `FALLIDO` o `LIBERADO`.
        """
        ...

    async def capturar(
        self,
        referencia: str,
        *,
        clave_idempotencia: str,
        monto: Decimal | None = None,
    ) -> ResultadoCobro: ...

    async def liberar_autorizacion(
        self, referencia: str, *, clave_idempotencia: str
    ) -> ResultadoCobro: ...

    async def reembolsar(
        self, referencia: str, *, monto: Decimal, clave_idempotencia: str
    ) -> ResultadoReembolso: ...

    # Solo lectura, asi que siempre es repetible
    async def consultar_cobro(self, referencia: str) -> ConsultaCobro: ...

    async def parsear_webhook(
        self, cuerpo: bytes, encabezados: Mapping[str, str]
    ) -> EventoRecibido: ...


# Reglas comunes a todo adaptador


def validar_monto(monto: object) -> Decimal:
    if not isinstance(monto, Decimal):
        raise TypeError(f"El monto tiene que ser Decimal, no {type(monto).__name__}")
    if not monto.is_finite() or monto <= 0:
        raise SolicitudInvalida("El monto tiene que ser positivo")
    if monto != monto.quantize(CENTIMO):
        raise SolicitudInvalida("El monto tiene fracciones de centimo")
    return monto


def validar_tarifa(tarifa: object) -> Decimal:
    if not isinstance(tarifa, Decimal):
        raise TypeError(f"La tarifa tiene que ser Decimal, no {type(tarifa).__name__}")
    if not tarifa.is_finite() or not 0 <= tarifa <= CIEN:
        raise SolicitudInvalida("La tarifa tiene que estar entre 0 y 100")
    if tarifa != tarifa.quantize(CENTIMO):
        raise SolicitudInvalida("La tarifa admite como maximo dos decimales")
    return tarifa


def validar_clave(clave: object) -> str:
    if not isinstance(clave, str) or not clave.strip():
        raise SolicitudInvalida("Falta la clave de idempotencia")
    return clave


def validar_metadatos(metadatos: Mapping[str, str]) -> Mapping[str, str]:
    if any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in metadatos.items()
    ):
        raise SolicitudInvalida("Los metadatos son texto a texto")
    return metadatos


def validar_referencia(referencia: object) -> str:
    if not isinstance(referencia, str) or not referencia.strip():
        raise SolicitudInvalida("Falta la referencia del cobro")
    return referencia


def validar_url_retorno(url: object) -> str:
    """Con esquema (`https://` o uno propio como `artistica://`), sin espacios."""
    if not isinstance(url, str) or not _URL_CON_ESQUEMA.fullmatch(url):
        raise SolicitudInvalida(
            "La url de retorno necesita un esquema, no puede ser vacia ni tener "
            "espacios"
        )
    return url


def validar_solicitud(
    solicitud: SolicitudCobro, capacidades: Capacidades, *, diferida: bool
) -> None:
    """Valida antes de llamar al proveedor, incluidas las capacidades."""
    validar_monto(solicitud.monto)
    validar_clave(solicitud.clave_idempotencia)
    if not solicitud.cuenta_conectada_id or not solicitud.moneda:
        raise SolicitudInvalida("Faltan la cuenta conectada o la moneda")
    validar_metadatos(solicitud.metadatos)
    if solicitud.url_retorno is not None:
        validar_url_retorno(solicitud.url_retorno)
    if solicitud.metodo not in capacidades.metodos:
        raise OperacionNoSoportada(f"Metodo no soportado: {solicitud.metodo}")
    if diferida and solicitud.metodo not in capacidades.autorizacion_diferida:
        raise OperacionNoSoportada(
            f"El metodo {solicitud.metodo} no admite autorizacion diferida"
        )
    if solicitud.tarifa_porcentaje is not None:
        if not capacidades.comision_por_cobro:
            raise OperacionNoSoportada(
                "La comision solo se fija por cuenta conectada: "
                "usar configurar_tarifa y dejar tarifa_porcentaje en None"
            )
        validar_tarifa(solicitud.tarifa_porcentaje)


def buscar_encabezado(encabezados: Mapping[str, str], nombre: str) -> str | None:
    """Los encabezados HTTP no distinguen mayusculas."""
    nombre = nombre.lower()
    for clave, valor in encabezados.items():
        if clave.lower() == nombre:
            return valor
    return None
