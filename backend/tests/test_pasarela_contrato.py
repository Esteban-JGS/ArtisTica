"""Contrato de la pasarela contra PasarelaFalsa, y la fabrica."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.core.config import Settings, settings
from src.payments import fabrica
from src.payments.config import ConfigOnvo
from src.payments.contrato import (
    EstadoOperacion,
    MetodoPago,
    PasarelaDePagos,
    SolicitudCobro,
    TipoEvento,
)
from src.payments.errores import (
    AutorizacionVencida,
    CredencialesInvalidas,
    FirmaInvalida,
    OperacionNoSoportada,
    PagoRechazado,
    PasarelaNoDisponible,
    SolicitudInvalida,
)
from src.payments.falsa import (
    CAPACIDADES_POR_DEFECTO,
    ENCABEZADO_FIRMA,
    MEDIO_PAGO_RECHAZADO,
    PasarelaFalsa,
)

INICIO = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
MONTO = Decimal("10000.00")


class Reloj:
    def __init__(self) -> None:
        self.ahora = INICIO

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, **delta: float) -> None:
        self.ahora += timedelta(**delta)


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def pasarela(reloj: Reloj) -> PasarelaFalsa:
    return PasarelaFalsa(reloj=reloj)


@pytest.fixture
async def cuenta(pasarela: PasarelaFalsa) -> str:
    creada = await pasarela.crear_cuenta_conectada(
        nombre="Taller de Ana", tarifa_porcentaje=Decimal("8")
    )
    pasarela.completar_onboarding(creada.id)
    return creada.id


def solicitud(cuenta_id: str, clave: str = "clave-1", **cambios) -> SolicitudCobro:
    base = SolicitudCobro(
        monto=MONTO,
        metodo=MetodoPago.TARJETA,
        cuenta_conectada_id=cuenta_id,
        clave_idempotencia=clave,
        descripcion="Anticipo",
        metadatos={"pedido_id": "p-1", "cobro_id": "c-1"},
    )
    return replace(base, **cambios)


async def test_01_cobrar_deja_el_cobro_capturado(pasarela, cuenta):
    resultado = await pasarela.cobrar(solicitud(cuenta))

    assert resultado.estado is EstadoOperacion.CAPTURADO
    assert resultado.monto == MONTO
    assert resultado.capturado_en == INICIO
    assert resultado.autorizado_hasta is None
    estado = pasarela.inspeccionar_cobro(resultado.referencia)
    assert estado.monto_capturado == MONTO
    assert estado.estado is EstadoOperacion.CAPTURADO


async def test_02_autorizar_fija_autorizado_hasta_segun_capacidades(reloj):
    for dias in (7, 3):
        pasarela = PasarelaFalsa(
            reloj=reloj,
            capacidades=replace(
                CAPACIDADES_POR_DEFECTO, dias_vigencia_autorizacion=dias
            ),
        )
        creada = await pasarela.crear_cuenta_conectada(
            nombre="Ana", tarifa_porcentaje=Decimal("8")
        )
        pasarela.completar_onboarding(creada.id)

        resultado = await pasarela.autorizar(solicitud(creada.id))

        assert resultado.estado is EstadoOperacion.AUTORIZADO
        assert resultado.autorizado_hasta == INICIO + timedelta(days=dias)
        assert resultado.capturado_en is None


async def test_03_capturar_total_parcial_y_mas_de_lo_autorizado(pasarela, cuenta):
    parcial = await pasarela.autorizar(solicitud(cuenta, "a-1"))
    capturado = await pasarela.capturar(
        parcial.referencia, clave_idempotencia="c-1", monto=Decimal("4000.00")
    )
    assert capturado.estado is EstadoOperacion.CAPTURADO
    assert capturado.monto == Decimal("4000.00")
    assert capturado.referencia == parcial.referencia

    total = await pasarela.autorizar(solicitud(cuenta, "a-2"))
    capturado = await pasarela.capturar(total.referencia, clave_idempotencia="c-2")
    assert capturado.monto == MONTO

    exceso = await pasarela.autorizar(solicitud(cuenta, "a-3"))
    with pytest.raises(SolicitudInvalida):
        await pasarela.capturar(
            exceso.referencia, clave_idempotencia="c-3", monto=Decimal("10000.01")
        )
    assert (
        pasarela.inspeccionar_cobro(exceso.referencia).estado
        is EstadoOperacion.AUTORIZADO
    )


async def test_04_capturar_despues_de_autorizado_hasta_levanta_vencida(
    pasarela, cuenta, reloj
):
    a_tiempo = await pasarela.autorizar(solicitud(cuenta, "a-1"))
    vencida = await pasarela.autorizar(solicitud(cuenta, "a-2"))

    reloj.avanzar(days=7, seconds=-1)
    await pasarela.capturar(a_tiempo.referencia, clave_idempotencia="c-1")

    reloj.avanzar(seconds=1)
    assert reloj.ahora == vencida.autorizado_hasta
    with pytest.raises(AutorizacionVencida):
        await pasarela.capturar(vencida.referencia, clave_idempotencia="c-2")


async def test_05_despues_de_liberar_capturar_falla(pasarela, cuenta):
    autorizado = await pasarela.autorizar(solicitud(cuenta))

    liberado = await pasarela.liberar_autorizacion(
        autorizado.referencia, clave_idempotencia="l-1"
    )

    assert liberado.estado is EstadoOperacion.LIBERADO
    assert liberado.monto == MONTO
    with pytest.raises(SolicitudInvalida):
        await pasarela.capturar(autorizado.referencia, clave_idempotencia="c-1")


async def test_06_reembolso_parcial_total_y_exceso(pasarela, cuenta):
    cobro = await pasarela.cobrar(solicitud(cuenta))

    primero = await pasarela.reembolsar(
        cobro.referencia, monto=Decimal("3000.00"), clave_idempotencia="r-1"
    )
    assert primero.referencia_cobro == cobro.referencia
    assert primero.monto == Decimal("3000.00")
    assert primero.total_reembolsado == Decimal("3000.00")

    segundo = await pasarela.reembolsar(
        cobro.referencia, monto=Decimal("7000.00"), clave_idempotencia="r-2"
    )
    assert segundo.total_reembolsado == MONTO
    assert segundo.referencia_reembolso != primero.referencia_reembolso

    with pytest.raises(SolicitudInvalida):
        await pasarela.reembolsar(
            cobro.referencia, monto=Decimal("0.01"), clave_idempotencia="r-3"
        )
    assert pasarela.inspeccionar_cobro(cobro.referencia).monto_reembolsado == MONTO


async def test_07_idempotencia_mismo_efecto_y_datos_distintos(pasarela, cuenta):
    primero = await pasarela.cobrar(solicitud(cuenta, "k-1"))
    segundo = await pasarela.cobrar(solicitud(cuenta, "k-1"))

    assert segundo == primero
    assert pasarela.total_cobros == 1

    with pytest.raises(SolicitudInvalida):
        await pasarela.cobrar(solicitud(cuenta, "k-1", monto=Decimal("9999.00")))
    assert pasarela.total_cobros == 1

    reembolso = await pasarela.reembolsar(
        primero.referencia, monto=Decimal("100.00"), clave_idempotencia="k-2"
    )
    repetido = await pasarela.reembolsar(
        primero.referencia, monto=Decimal("100.00"), clave_idempotencia="k-2"
    )
    assert repetido == reembolso
    assert pasarela.inspeccionar_cobro(primero.referencia).monto_reembolsado == (
        Decimal("100.00")
    )


async def test_08_autorizar_con_metodo_sin_autorizacion_diferida(pasarela, cuenta):
    sinpe = solicitud(cuenta, metodo=MetodoPago.SINPE_MOVIL)

    with pytest.raises(OperacionNoSoportada):
        await pasarela.autorizar(sinpe)
    assert pasarela.total_cobros == 0

    # El mismo metodo si sirve para cobrar en un paso
    cobro = await pasarela.cobrar(sinpe)
    assert cobro.estado is EstadoOperacion.CAPTURADO


async def test_09_webhook_firmado_alterado_y_tipo_desconocido(pasarela):
    cuerpo, encabezados = pasarela.construir_evento(
        TipoEvento.COBRO_CAPTURADO, referencia="cobro_1", evento_id="evt-1"
    )

    evento = await pasarela.parsear_webhook(cuerpo, encabezados)
    assert evento.proveedor == "falsa"
    assert evento.evento_externo_id == "evt-1"
    assert evento.tipo is TipoEvento.COBRO_CAPTURADO
    assert evento.referencia == "cobro_1"
    assert evento.payload["id"] == "evt-1"

    # Los encabezados HTTP no distinguen mayusculas
    minusculas = {ENCABEZADO_FIRMA.lower(): encabezados[ENCABEZADO_FIRMA]}
    assert (await pasarela.parsear_webhook(cuerpo, minusculas)).tipo is (
        TipoEvento.COBRO_CAPTURADO
    )

    alterado = cuerpo.replace(b"cobro_1", b"cobro_2")
    with pytest.raises(FirmaInvalida):
        await pasarela.parsear_webhook(alterado, encabezados)
    with pytest.raises(FirmaInvalida):
        await pasarela.parsear_webhook(cuerpo, {})

    cuerpo, encabezados = pasarela.construir_evento("tipo_que_no_existe")
    evento = await pasarela.parsear_webhook(cuerpo, encabezados)
    assert evento.tipo is TipoEvento.DESCONOCIDO


async def test_10_fallas_programadas_y_reintentable(pasarela, cuenta):
    pasarela.programar_falla("cobrar", PagoRechazado("sin fondos"))
    with pytest.raises(PagoRechazado) as rechazo:
        await pasarela.cobrar(solicitud(cuenta, "f-1"))
    assert rechazo.value.reintentable is False
    assert pasarela.total_cobros == 0

    # La falla es solo para la proxima llamada
    autorizado = await pasarela.autorizar(solicitud(cuenta, "f-2"))

    pasarela.programar_falla("capturar", PasarelaNoDisponible("timeout"))
    with pytest.raises(PasarelaNoDisponible) as caida:
        await pasarela.capturar(autorizado.referencia, clave_idempotencia="f-3")
    assert caida.value.reintentable is True
    await pasarela.capturar(autorizado.referencia, clave_idempotencia="f-3")

    with pytest.raises(PagoRechazado):
        await pasarela.cobrar(
            solicitud(cuenta, "f-4", medio_pago_id=MEDIO_PAGO_RECHAZADO)
        )


async def test_11_montos_float_cero_y_negativos(pasarela, cuenta):
    with pytest.raises(TypeError):
        await pasarela.cobrar(solicitud(cuenta, monto=10000.0))
    for invalido in (Decimal("0"), Decimal("-1.00"), Decimal("0.001")):
        with pytest.raises(SolicitudInvalida):
            await pasarela.cobrar(solicitud(cuenta, monto=invalido))

    cobro = await pasarela.cobrar(solicitud(cuenta))
    with pytest.raises(TypeError):
        await pasarela.reembolsar(cobro.referencia, monto=1.5, clave_idempotencia="r")
    with pytest.raises(SolicitudInvalida):
        await pasarela.reembolsar(
            cobro.referencia, monto=Decimal("0"), clave_idempotencia="r"
        )
    with pytest.raises(SolicitudInvalida):
        await pasarela.cobrar(solicitud(cuenta, clave=""))


async def test_16_fabrica_por_defecto_sin_clave_y_desconocida(monkeypatch):
    monkeypatch.setattr(settings, "PASARELA", Settings.model_fields["PASARELA"].default)
    monkeypatch.delenv("ONVO_API_KEY", raising=False)
    fabrica.obtener_pasarela.cache_clear()
    try:
        pasarela = fabrica.obtener_pasarela()
        assert isinstance(pasarela, PasarelaFalsa)
        assert isinstance(pasarela, PasarelaDePagos)
        assert fabrica.obtener_pasarela() is pasarela
    finally:
        fabrica.obtener_pasarela.cache_clear()

    with pytest.raises(CredencialesInvalidas, match="ONVO_API_KEY"):
        fabrica.construir_pasarela("onvo", config_onvo=ConfigOnvo(_env_file=None))

    with pytest.raises(ValueError, match="PASARELA desconocida"):
        fabrica.construir_pasarela("pasarela_inventada")
