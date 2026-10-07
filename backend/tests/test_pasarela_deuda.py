"""Deudas DT11, DT12 y DT17 del contrato de pagos.

Las de ONVO usan httpx.MockTransport: nunca hay red.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from src.core.config import Settings
from src.domain.politicas import PoliticasPedido
from src.models import Profile
from src.payments import onvo
from src.payments.config import ConfigOnvo
from src.payments.contrato import (
    EstadoCobroPasarela,
    MetodoPago,
    SolicitudCobro,
)
from src.payments.errores import (
    ErrorPasarela,
    PasarelaNoDisponible,
    SolicitudInvalida,
)
from src.payments.falsa import PasarelaFalsa
from src.payments.onvo import PasarelaOnvo
from src.services import perfiles as servicio

INICIO = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
MONTO = Decimal("12500.50")
CENTIMOS = 1250050
METADATOS = {"pedido_id": "p-1", "cobro_id": "c-1"}


# Ayudas de la pasarela falsa


class Reloj:
    """Reloj inyectable: la prueba decide cuanto tiempo paso."""

    def __init__(self, ahora: datetime = INICIO) -> None:
        self.ahora = ahora

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, delta: timedelta) -> None:
        self.ahora += delta


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def pasarela(reloj: Reloj) -> PasarelaFalsa:
    return PasarelaFalsa(reloj=reloj)


@pytest.fixture
async def cuenta(pasarela: PasarelaFalsa) -> str:
    creada = await pasarela.crear_cuenta_conectada(
        nombre="Taller de Ana",
        tarifa_porcentaje=Decimal("8"),
        clave_idempotencia="cuenta-base",
    )
    pasarela.completar_onboarding(creada.id)
    return creada.id


def solicitud(cuenta_id: str, clave: str = "clave-1") -> SolicitudCobro:
    return SolicitudCobro(
        monto=MONTO,
        metodo=MetodoPago.TARJETA,
        cuenta_conectada_id=cuenta_id,
        clave_idempotencia=clave,
        descripcion="Anticipo",
        metadatos=METADATOS,
    )


# Ayudas de ONVO. Copia minima del helper de test_pasarela_onvo.py

CLAVE = "onvo_test_secret_key_NO_DEBE_FILTRARSE"


def configuracion() -> ConfigOnvo:
    return ConfigOnvo(_env_file=None, API_KEY=SecretStr(CLAVE))


class Simulador:
    """Responde por (metodo, ruta) y guarda cada solicitud recibida."""

    def __init__(self, rutas) -> None:
        self.rutas = rutas
        self.solicitudes: list[httpx.Request] = []

    def __call__(self, solicitud: httpx.Request) -> httpx.Response:
        self.solicitudes.append(solicitud)
        assert solicitud.headers[onvo.ENCABEZADO_AUTORIZACION] == f"Bearer {CLAVE}"
        return self.rutas[(solicitud.method, solicitud.url.path)](solicitud)

    def pasarela(self) -> PasarelaOnvo:
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(self))
        return PasarelaOnvo(configuracion(), cliente=cliente, reloj=lambda: INICIO)


def responder(estado: int, datos: object):
    return lambda _: httpx.Response(estado, json=datos)


RUTA_CONSULTA = onvo.RUTA_INTENCION.format(id="pi_1")


def simulador_consulta(estado: int, datos: object) -> Simulador:
    return Simulador({("GET", RUTA_CONSULTA): responder(estado, datos)})


def intencion(estado: str, **extra) -> dict:
    return {
        "id": "pi_1",
        "status": estado,
        "amount": CENTIMOS,
        "currency": "CRC",
        **extra,
    }


# 1 a 3. Consulta de cobro en la pasarela falsa (DT11)


async def test_01_consulta_de_una_autorizacion(pasarela, cuenta):
    autorizado = await pasarela.autorizar(solicitud(cuenta))

    consulta = await pasarela.consultar_cobro(autorizado.referencia)

    assert consulta.referencia == autorizado.referencia
    assert consulta.estado is EstadoCobroPasarela.AUTORIZADO
    assert consulta.monto == MONTO
    assert consulta.monto_capturado == Decimal("0")
    assert consulta.autorizado_hasta == autorizado.autorizado_hasta
    assert consulta.metadatos == METADATOS


async def test_02_consulta_a_lo_largo_del_ciclo(pasarela, cuenta):
    autorizado = await pasarela.autorizar(solicitud(cuenta, "a-1"))
    await pasarela.capturar(autorizado.referencia, clave_idempotencia="cap-1")

    capturada = await pasarela.consultar_cobro(autorizado.referencia)
    assert capturada.estado is EstadoCobroPasarela.CAPTURADO
    assert capturada.monto_capturado == MONTO
    assert capturada.monto_reembolsado == Decimal("0")

    await pasarela.reembolsar(
        autorizado.referencia, monto=Decimal("500.00"), clave_idempotencia="re-1"
    )
    reembolsada = await pasarela.consultar_cobro(autorizado.referencia)
    assert reembolsada.estado is EstadoCobroPasarela.CAPTURADO
    assert reembolsada.monto_reembolsado == Decimal("500.00")

    otra = await pasarela.autorizar(solicitud(cuenta, "a-2"))
    await pasarela.liberar_autorizacion(otra.referencia, clave_idempotencia="li-1")
    liberada = await pasarela.consultar_cobro(otra.referencia)
    assert liberada.estado is EstadoCobroPasarela.LIBERADO


async def test_03_una_autorizacion_vencida_se_informa_liberada(pasarela, cuenta, reloj):
    autorizado = await pasarela.autorizar(solicitud(cuenta))
    assert autorizado.autorizado_hasta is not None

    reloj.ahora = autorizado.autorizado_hasta + timedelta(seconds=1)

    consulta = await pasarela.consultar_cobro(autorizado.referencia)
    assert consulta.estado is EstadoCobroPasarela.LIBERADO


# 4 a 6. Consulta de cobro en ONVO (DT11)


async def test_04_la_consulta_a_onvo_es_un_get_reintentable():
    simulador = simulador_consulta(200, intencion(onvo.INTENCION_REQUIERE_CAPTURA))

    consulta = await simulador.pasarela().consultar_cobro("pi_1")

    assert consulta.referencia == "pi_1"
    pedido = simulador.solicitudes[0]
    assert pedido.method == "GET"
    assert pedido.url.path == RUTA_CONSULTA
    assert pedido.headers[onvo.ENCABEZADO_AUTORIZACION] == f"Bearer {CLAVE}"

    caido = simulador_consulta(503, {"message": "upstream"})
    with pytest.raises(PasarelaNoDisponible) as exc:
        await caido.pasarela().consultar_cobro("pi_1")
    assert exc.value.reintentable is True


ESTADOS_ESPERADOS = [
    ("requires_confirmation", {}, EstadoCobroPasarela.PENDIENTE),
    ("processing", {}, EstadoCobroPasarela.PENDIENTE),
    ("deferred", {}, EstadoCobroPasarela.PENDIENTE),
    (onvo.INTENCION_SIN_MEDIO_PAGO, {}, EstadoCobroPasarela.PENDIENTE),
    (
        onvo.INTENCION_SIN_MEDIO_PAGO,
        {onvo.CAMPO_ULTIMO_ERROR: {"code": "card_declined"}},
        EstadoCobroPasarela.FALLIDO,
    ),
    (onvo.INTENCION_FALLIDA, {}, EstadoCobroPasarela.FALLIDO),
    (onvo.INTENCION_REQUIERE_ACCION, {}, EstadoCobroPasarela.REQUIERE_ACCION),
    (onvo.INTENCION_REQUIERE_CAPTURA, {}, EstadoCobroPasarela.AUTORIZADO),
    (onvo.INTENCION_EXITOSA, {}, EstadoCobroPasarela.CAPTURADO),
    (onvo.INTENCION_CANCELADA, {}, EstadoCobroPasarela.LIBERADO),
    (onvo.INTENCION_REEMBOLSADA, {}, EstadoCobroPasarela.CAPTURADO),
    (onvo.INTENCION_REEMBOLSADA_PARCIAL, {}, EstadoCobroPasarela.CAPTURADO),
]


@pytest.mark.parametrize(("estado", "extra", "esperado"), ESTADOS_ESPERADOS)
async def test_05_estados_de_onvo_segun_el_mapeo(estado, extra, esperado):
    simulador = simulador_consulta(
        200, intencion(estado, receivedAmount=CENTIMOS, **extra)
    )

    consulta = await simulador.pasarela().consultar_cobro("pi_1")

    assert consulta.estado is esperado
    # Con un reembolso de por medio receivedAmount es el neto, no lo capturado
    if estado in onvo.INTENCIONES_CON_REEMBOLSO:
        assert consulta.monto_capturado is None
    else:
        assert consulta.monto_capturado == MONTO


async def test_05b_un_estado_fuera_del_mapeo_no_se_adivina():
    simulador = simulador_consulta(200, intencion("inventado"))

    with pytest.raises(ErrorPasarela):
        await simulador.pasarela().consultar_cobro("pi_1")


async def test_06_montos_y_metadatos_de_la_consulta():
    simulador = simulador_consulta(
        200,
        intencion(
            onvo.INTENCION_EXITOSA,
            receivedAmount=CENTIMOS - 50000,
            # En JSON las llaves son texto siempre: lo que puede no serlo es el valor
            metadata={"pedido_id": "p-1", "intentos": 3, "nulo": None},
        ),
    )

    consulta = await simulador.pasarela().consultar_cobro("pi_1")

    assert consulta.monto == MONTO
    assert consulta.monto_capturado == Decimal("12000.50")
    # ONVO no expone el acumulado reembolsado
    assert consulta.monto_reembolsado is None
    # Un metadato que no es texto se descarta
    assert consulta.metadatos == {"pedido_id": "p-1"}


# 7 y 8. Cuenta conectada idempotente (DT17)


async def test_07_la_falsa_no_duplica_la_cuenta_con_la_misma_clave(pasarela):
    primera = await pasarela.crear_cuenta_conectada(
        nombre="Ana",
        tarifa_porcentaje=Decimal("8"),
        clave_idempotencia="cuenta-1",
        metadatos={"perfil_id": "p-1"},
    )
    repetida = await pasarela.crear_cuenta_conectada(
        nombre="Ana",
        tarifa_porcentaje=Decimal("8"),
        clave_idempotencia="cuenta-1",
        metadatos={"perfil_id": "p-1"},
    )

    assert repetida == primera
    assert pasarela.total_cuentas == 1

    with pytest.raises(SolicitudInvalida):
        await pasarela.crear_cuenta_conectada(
            nombre="Otra",
            tarifa_porcentaje=Decimal("8"),
            clave_idempotencia="cuenta-1",
            metadatos={"perfil_id": "p-1"},
        )
    assert pasarela.total_cuentas == 1

    nueva = await pasarela.crear_cuenta_conectada(
        nombre="Ana",
        tarifa_porcentaje=Decimal("8"),
        clave_idempotencia="cuenta-2",
    )
    assert nueva.id != primera.id
    assert pasarela.total_cuentas == 2


async def test_08_onvo_valida_la_clave_y_no_manda_encabezado():
    simulador = Simulador(
        {
            ("POST", onvo.RUTA_CREAR_CUENTA): responder(
                201, {"id": "cuenta_1", "status": "pending_onboarding"}
            )
        }
    )

    with pytest.raises(SolicitudInvalida):
        await simulador.pasarela().crear_cuenta_conectada(
            nombre="Ana", tarifa_porcentaje=Decimal("8"), clave_idempotencia="  "
        )
    assert simulador.solicitudes == []

    await simulador.pasarela().crear_cuenta_conectada(
        nombre="Ana",
        tarifa_porcentaje=Decimal("8"),
        clave_idempotencia="cuenta-conectada-1",
        metadatos={"perfil_id": "p-1"},
    )
    enviada = simulador.solicitudes[0]
    assert onvo.ENCABEZADO_IDEMPOTENCIA is None
    assert not [c for c in enviada.headers if "idempot" in c.lower()]
    # La cuenta conectada no admite metadatos: no se envian
    assert json.loads(enviada.content) == {
        onvo.CAMPO_NOMBRE_NEGOCIO: "Ana",
        onvo.CAMPO_TARIFA_MARKETPLACE: 8,
    }


# 9. Vencimiento efectivo de una autorizacion (DT12)


def test_09_vencimiento_efectivo_de_la_autorizacion():
    politicas = PoliticasPedido.desde_config(
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/artistica",
            ALEMBIC_DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/artistica",
            SUPABASE_URL="http://supabase.local",
        )
    )
    informado = INICIO + timedelta(days=30)

    assert politicas.vencimiento_autorizacion(informado, INICIO) == informado
    assert politicas.vencimiento_autorizacion(None, INICIO) == INICIO + timedelta(
        days=5
    )

    with pytest.raises(ValueError, match="tiene que tener zona horaria"):
        politicas.vencimiento_autorizacion(None, INICIO.replace(tzinfo=None))

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/artistica",
            ALEMBIC_DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/artistica",
            SUPABASE_URL="http://supabase.local",
            DIAS_VIGENCIA_AUTORIZACION_SUPUESTA=0,
        )


# 10. Onboarding sin duplicar la cuenta (DT17)


async def test_10_un_commit_fallido_no_deja_dos_cuentas(sesion_api, pasarela_falsa):
    politicas = PoliticasPedido.desde_config(
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/artistica",
            ALEMBIC_DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/artistica",
            SUPABASE_URL="http://supabase.local",
        )
    )
    perfil_id = uuid.uuid4()
    perfil = await servicio.registrar(
        sesion_api, perfil_id, f"u{uuid.uuid4().hex[:12]}", "Ana"
    )
    await servicio.hacerse_artista(sesion_api, perfil)

    # Primer intento: la pasarela crea la cuenta y el commit falla
    savepoint = await sesion_api.begin_nested()
    primera = await servicio.iniciar_onboarding(
        sesion_api, pasarela_falsa, perfil_id, politicas
    )
    await savepoint.rollback()

    segunda = await servicio.iniciar_onboarding(
        sesion_api, pasarela_falsa, perfil_id, politicas
    )

    assert pasarela_falsa.total_cuentas == 1
    assert segunda.id == primera.id
    guardado = await sesion_api.get(Profile, perfil_id, populate_existing=True)
    assert guardado.pasarela_cuenta_id == primera.id
