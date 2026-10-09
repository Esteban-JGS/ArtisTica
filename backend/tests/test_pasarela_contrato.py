"""Contrato de la pasarela contra PasarelaFalsa, y la fabrica."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.core.config import Settings, settings
from src.payments import fabrica
from src.payments.config import ConfigOnvo
from src.payments.contrato import (
    EstadoCobroPasarela,
    EstadoOperacion,
    MetodoPago,
    PasarelaDePagos,
    ResultadoCobro,
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
    MEDIO_PAGO_3DS,
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
        nombre="Taller de Ana",
        tarifa_porcentaje=Decimal("8"),
        clave_idempotencia="cuenta-1",
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
            nombre="Ana",
            tarifa_porcentaje=Decimal("8"),
            clave_idempotencia=f"cuenta-{dias}",
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


# Lote 8: autenticacion 3DS


def url_3ds(referencia: str) -> str:
    return f"https://pasarela-falsa.invalid/3ds/{referencia}"


def con_3ds(cuenta_id: str, clave: str = "clave-3ds", **cambios) -> SolicitudCobro:
    return solicitud(cuenta_id, clave, medio_pago_id=MEDIO_PAGO_3DS, **cambios)


async def test_8_01_cobrar_con_3ds_y_autenticacion_aprobada(pasarela, cuenta):
    resultado = await pasarela.cobrar(con_3ds(cuenta))

    assert resultado.estado is EstadoOperacion.REQUIERE_ACCION
    assert resultado.monto == MONTO
    assert resultado.url_autenticacion == url_3ds(resultado.referencia)
    consulta = await pasarela.consultar_cobro(resultado.referencia)
    assert consulta.estado is EstadoCobroPasarela.REQUIERE_ACCION
    assert consulta.url_autenticacion == resultado.url_autenticacion
    assert consulta.monto_capturado == Decimal("0")

    pasarela.completar_autenticacion(resultado.referencia, aprobada=True)

    consulta = await pasarela.consultar_cobro(resultado.referencia)
    assert consulta.estado is EstadoCobroPasarela.CAPTURADO
    assert consulta.monto_capturado == MONTO
    assert consulta.url_autenticacion is None


async def test_8_02_autorizar_con_3ds_aprobada_vence_desde_la_aprobacion(
    pasarela, cuenta, reloj
):
    resultado = await pasarela.autorizar(con_3ds(cuenta))
    assert resultado.estado is EstadoOperacion.REQUIERE_ACCION
    assert resultado.autorizado_hasta is None

    reloj.avanzar(minutes=10)
    pasarela.completar_autenticacion(resultado.referencia, aprobada=True)

    consulta = await pasarela.consultar_cobro(resultado.referencia)
    assert consulta.estado is EstadoCobroPasarela.AUTORIZADO
    dias = CAPACIDADES_POR_DEFECTO.dias_vigencia_autorizacion
    assert consulta.autorizado_hasta == reloj.ahora + timedelta(days=dias)
    capturado = await pasarela.capturar(resultado.referencia, clave_idempotencia="c")
    assert capturado.estado is EstadoOperacion.CAPTURADO
    assert capturado.monto == MONTO


async def test_8_03_autenticacion_rechazada_deja_el_cobro_fallido(pasarela, cuenta):
    diferido = await pasarela.autorizar(con_3ds(cuenta, "a-1"))
    directo = await pasarela.cobrar(con_3ds(cuenta, "a-2"))

    for referencia in (diferido.referencia, directo.referencia):
        pasarela.completar_autenticacion(referencia, aprobada=False)
        consulta = await pasarela.consultar_cobro(referencia)
        assert consulta.estado is EstadoCobroPasarela.FALLIDO
        assert consulta.url_autenticacion is None
        assert pasarela.inspeccionar_cobro(referencia).fallido is True

    with pytest.raises(SolicitudInvalida):
        await pasarela.capturar(diferido.referencia, clave_idempotencia="c-1")
    with pytest.raises(SolicitudInvalida):
        await pasarela.reembolsar(
            directo.referencia, monto=MONTO, clave_idempotencia="r-1"
        )
    with pytest.raises(SolicitudInvalida):
        pasarela.completar_autenticacion(directo.referencia, aprobada=True)


async def test_8_04_liberar_un_cobro_que_espera_el_3ds(pasarela, cuenta):
    resultado = await pasarela.autorizar(con_3ds(cuenta))

    liberado = await pasarela.liberar_autorizacion(
        resultado.referencia, clave_idempotencia="l-1"
    )

    assert liberado.estado is EstadoOperacion.LIBERADO
    consulta = await pasarela.consultar_cobro(resultado.referencia)
    assert consulta.estado is EstadoCobroPasarela.LIBERADO
    assert consulta.url_autenticacion is None
    with pytest.raises(SolicitudInvalida):
        pasarela.completar_autenticacion(resultado.referencia, aprobada=True)


async def test_8_05_capturar_o_reembolsar_antes_de_autenticar(pasarela, cuenta):
    diferido = await pasarela.autorizar(con_3ds(cuenta, "a-1"))
    directo = await pasarela.cobrar(con_3ds(cuenta, "a-2"))

    with pytest.raises(SolicitudInvalida):
        await pasarela.capturar(diferido.referencia, clave_idempotencia="c-1")
    with pytest.raises(SolicitudInvalida):
        await pasarela.reembolsar(
            directo.referencia, monto=MONTO, clave_idempotencia="r-1"
        )
    assert pasarela.inspeccionar_cobro(diferido.referencia).estado is (
        EstadoOperacion.REQUIERE_ACCION
    )


async def test_8_06_idempotencia_antes_y_despues_de_autenticar(pasarela, cuenta):
    primero = await pasarela.autorizar(con_3ds(cuenta, "k-1"))
    assert await pasarela.autorizar(con_3ds(cuenta, "k-1")) == primero

    pasarela.completar_autenticacion(primero.referencia, aprobada=True)

    # El resultado guardado no cambia: el estado vigente sale de consultar_cobro
    despues = await pasarela.autorizar(con_3ds(cuenta, "k-1"))
    assert despues == primero
    assert despues.estado is EstadoOperacion.REQUIERE_ACCION
    assert despues.url_autenticacion == primero.url_autenticacion
    assert pasarela.total_cobros == 1
    consulta = await pasarela.consultar_cobro(primero.referencia)
    assert consulta.estado is EstadoCobroPasarela.AUTORIZADO

    cobro = await pasarela.cobrar(con_3ds(cuenta, "k-2"))
    pasarela.completar_autenticacion(cobro.referencia, aprobada=True)
    assert await pasarela.cobrar(con_3ds(cuenta, "k-2")) == cobro
    assert pasarela.total_cobros == 2


async def test_8_07_validacion_de_url_retorno(pasarela, cuenta):
    invalidas = ("", "   ", "https://pago listo", "pago", "/3ds/vuelta", "://x")
    for numero, invalida in enumerate(invalidas):
        with pytest.raises(SolicitudInvalida):
            await pasarela.cobrar(con_3ds(cuenta, f"u-{numero}", url_retorno=invalida))
    assert pasarela.total_cobros == 0

    for valida in ("https://artistica.cr/pago/vuelta", "artistica://pago"):
        resultado = await pasarela.cobrar(
            con_3ds(cuenta, f"v-{valida}", url_retorno=valida)
        )
        assert resultado.estado is EstadoOperacion.REQUIERE_ACCION


async def test_8_08_el_repr_no_muestra_la_url_de_autenticacion(pasarela, cuenta):
    resultado = await pasarela.cobrar(con_3ds(cuenta))
    consulta = await pasarela.consultar_cobro(resultado.referencia)
    url = url_3ds(resultado.referencia)

    assert resultado.url_autenticacion == consulta.url_autenticacion == url
    for objeto in (resultado, consulta, pasarela):
        assert url not in repr(objeto)
        assert "pasarela-falsa.invalid" not in repr(objeto)

    # El contrato no admite una URL fuera de REQUIERE_ACCION, ni lo contrario
    with pytest.raises(ValueError, match="REQUIERE_ACCION"):
        ResultadoCobro(
            referencia="r",
            estado=EstadoOperacion.CAPTURADO,
            monto=MONTO,
            url_autenticacion=url,
        )
    with pytest.raises(ValueError, match="REQUIERE_ACCION"):
        ResultadoCobro(
            referencia="r", estado=EstadoOperacion.REQUIERE_ACCION, monto=MONTO
        )


async def test_8_09_sin_3ds_nada_cambia(pasarela, cuenta):
    cobro = await pasarela.cobrar(solicitud(cuenta, "s-1"))
    autorizado = await pasarela.autorizar(solicitud(cuenta, "s-2"))

    assert cobro.estado is EstadoOperacion.CAPTURADO
    assert autorizado.estado is EstadoOperacion.AUTORIZADO
    assert cobro.url_autenticacion is None
    assert autorizado.url_autenticacion is None
    for referencia in (cobro.referencia, autorizado.referencia):
        assert (await pasarela.consultar_cobro(referencia)).url_autenticacion is None
        with pytest.raises(SolicitudInvalida):
            pasarela.completar_autenticacion(referencia, aprobada=True)
