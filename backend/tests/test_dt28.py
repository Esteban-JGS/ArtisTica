"""DT28: reintentar una cancelacion o una resolucion con otro plan nunca mueve
dinero dos veces. Contra una base migrada y la pasarela falsa; cada prueba
termina en rollback.

"Un intento anterior" se simula moviendo el dinero directo en la falsa, sin
registrarlo, como si la llamada hubiera salido bien y el commit fallado.
"""

from decimal import Decimal

import pytest

from src.models import EstadoCobro, EstadoPedido, TipoCobro
from src.payments.contrato import EstadoOperacion
from src.payments.errores import PasarelaNoDisponible
from src.services import ledger
from tests.test_cobros_api import espiar
from tests.test_ledger import filas_ledger
from tests.test_moderacion_api import (
    admin,
    encargo_en_disputa,
    evento_en_disputa,
    resolver,
)
from tests.test_pedidos_api import cobros_db, pedido_db, ruta
from tests.test_vencimientos import evento

DE_DINERO = {"cobrar", "autorizar", "capturar", "liberar_autorizacion", "reembolsar"}


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


def de_dinero(llamadas) -> list[tuple[str, tuple, dict]]:
    return [llamada for llamada in llamadas if llamada[0] in DE_DINERO]


async def anticipo_en_disputa(http, autenticar_como, s, pasarela):
    """Evento disputado con los dos cobros capturados, y moderacion
    autenticada. Devuelve la escena y el anticipo."""
    escena = await evento_en_disputa(http, autenticar_como, s, pasarela)
    autenticar_como((await admin(s)).id)
    return escena, (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]


async def reembolsar_por_fuera(pasarela, referencia: str, monto: Decimal) -> None:
    await pasarela.reembolsar(
        referencia, monto=monto, clave_idempotencia=f"intento-anterior-{monto}"
    )


def cortar_despues_del_efecto(pasarela, operacion: str) -> None:
    """La proxima llamada mueve el dinero y despues falla por red, como un
    timeout de la respuesta."""
    original = getattr(pasarela, operacion)

    async def cortada(*args, **kwargs):
        setattr(pasarela, operacion, original)
        await original(*args, **kwargs)
        raise PasarelaNoDisponible("sin respuesta")

    setattr(pasarela, operacion, cortada)


# 17. Reembolso hecho por un intento anterior


async def test_9b_17_reembolso_ya_hecho_no_se_repite(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_en_disputa(
        http, autenticar_como, s, pasarela_falsa
    )
    m = Decimal("5000.00")
    await reembolsar_por_fuera(pasarela_falsa, anticipo.referencia_pasarela, m)
    llamadas = espiar(pasarela_falsa)

    r = await resolver(http, escena.pedido_id, reembolsos=[(anticipo.id, m)])
    assert r.status_code == 200, r.text
    assert de_dinero(llamadas) == []
    foto = pasarela_falsa.inspeccionar_cobro(anticipo.referencia_pasarela)
    assert foto.monto_reembolsado == m
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.REEMBOLSADO
    assert anticipo.monto_reembolsado == m


# 18. Reintento con un monto mayor


async def test_9b_18_reintento_con_monto_mayor_reembolsa_la_diferencia(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_en_disputa(
        http, autenticar_como, s, pasarela_falsa
    )
    referencia = anticipo.referencia_pasarela
    await reembolsar_por_fuera(pasarela_falsa, referencia, Decimal("3000.00"))
    llamadas = espiar(pasarela_falsa)

    r = await resolver(
        http, escena.pedido_id, reembolsos=[(anticipo.id, Decimal("5000.00"))]
    )
    assert r.status_code == 200, r.text
    [(nombre, args, kwargs)] = de_dinero(llamadas)
    assert nombre == "reembolsar"
    assert args == (referencia,)
    assert kwargs["monto"] == Decimal("2000.00")
    foto = pasarela_falsa.inspeccionar_cobro(referencia)
    assert foto.monto_reembolsado == Decimal("5000.00")
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.monto_reembolsado == Decimal("5000.00")


# 19. Reintento con un monto menor que lo ya devuelto


async def test_9b_19_ya_se_devolvio_mas_de_lo_ordenado_da_409(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_en_disputa(
        http, autenticar_como, s, pasarela_falsa
    )
    await reembolsar_por_fuera(
        pasarela_falsa, anticipo.referencia_pasarela, Decimal("6000.00")
    )
    antes = await filas_ledger(s, escena.pedido_id)
    llamadas = espiar(pasarela_falsa)

    r = await resolver(
        http, escena.pedido_id, reembolsos=[(anticipo.id, Decimal("5000.00"))]
    )
    assert r.status_code == 409, r.text
    assert "mas de lo ordenado" in r.json()["detail"]
    assert de_dinero(llamadas) == []
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.EN_DISPUTA
    cobros = await cobros_db(s, escena.pedido_id)
    assert cobros[TipoCobro.ANTICIPO].estado is EstadoCobro.CAPTURADO
    assert cobros[TipoCobro.ANTICIPO].monto_reembolsado == 0
    assert await filas_ledger(s, escena.pedido_id) == antes


# 20. Cancelar un saldo que la pasarela ya capturo


async def test_9b_20_liberar_un_saldo_ya_capturado_da_409(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    await pasarela_falsa.capturar(
        saldo.referencia_pasarela, clave_idempotencia="intento-anterior"
    )
    autenticar_como((await admin(s)).id)
    llamadas = espiar(pasarela_falsa)

    r = await resolver(http, escena.pedido_id, destino="cancelado")
    assert r.status_code == 409, r.text
    assert "ya se cobro" in r.json()["detail"]
    assert de_dinero(llamadas) == []
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.EN_DISPUTA
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.AUTORIZADO


# 21. Captura ya hecha


async def test_9b_21_captura_ya_hecha_no_se_repite(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    await pasarela_falsa.capturar(
        saldo.referencia_pasarela, clave_idempotencia="intento-anterior"
    )
    autenticar_como((await admin(s)).id)
    llamadas = espiar(pasarela_falsa)

    r = await resolver(http, escena.pedido_id, destino="completado")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "completado"
    assert de_dinero(llamadas) == []
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.CAPTURADO
    capturas = [
        f
        for f in await filas_ledger(s, escena.pedido_id)
        if f.tipo_evento == ledger.CAPTURA and f.cobro_id == saldo.id
    ]
    assert len(capturas) == 1


# 22. Cancelacion del cliente con un reembolso ya hecho


async def test_9b_22_cancelacion_con_reembolso_ya_hecho_no_reembolsa_dos_veces(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    # Con mas de 30 dias se devuelve todo el anticipo
    comprador, pedido_id, _ = await evento(
        http, autenticar_como, s, pasarela_falsa, dias=40
    )
    anticipo = (await cobros_db(s, pedido_id))[TipoCobro.ANTICIPO]
    await reembolsar_por_fuera(
        pasarela_falsa, anticipo.referencia_pasarela, anticipo.monto
    )
    autenticar_como(comprador.id)
    llamadas = espiar(pasarela_falsa)

    r = await http.post(ruta(pedido_id, "/cancelar"))
    assert r.status_code == 200, r.text
    assert de_dinero(llamadas) == []
    foto = pasarela_falsa.inspeccionar_cobro(anticipo.referencia_pasarela)
    assert foto.monto_reembolsado == anticipo.monto
    anticipo = (await cobros_db(s, pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.REEMBOLSADO
    assert anticipo.monto_reembolsado == anticipo.monto


# 23. La clave de reembolso


async def test_9b_23_clave_de_reembolso_lleva_el_total_al_terminar(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_en_disputa(
        http, autenticar_como, s, pasarela_falsa
    )
    referencia = anticipo.referencia_pasarela
    llamadas = espiar(pasarela_falsa)

    def claves() -> list[str]:
        return [k["clave_idempotencia"] for n, _, k in llamadas if n == "reembolsar"]

    # Falla antes de mover el dinero: la misma operacion repite la clave
    pasarela_falsa.programar_falla("reembolsar", PasarelaNoDisponible("caida"))
    tres_mil = [(anticipo.id, Decimal("3000.00"))]
    r = await resolver(http, escena.pedido_id, reembolsos=tres_mil)
    assert r.status_code == 503, r.text
    # Falla despues de moverlo: el reintento ve el reembolso en la pasarela
    cortar_despues_del_efecto(pasarela_falsa, "reembolsar")
    r = await resolver(http, escena.pedido_id, reembolsos=tres_mil)
    assert r.status_code == 503, r.text
    assert claves() == [f"reembolsar-{anticipo.id}-3000.00"] * 2
    assert pasarela_falsa.inspeccionar_cobro(referencia).monto_reembolsado == Decimal(
        "3000.00"
    )

    # Otra orden despues del reembolso parcial da otra clave
    r = await resolver(
        http, escena.pedido_id, reembolsos=[(anticipo.id, Decimal("5000.00"))]
    )
    assert r.status_code == 200, r.text
    assert claves()[2:] == [f"reembolsar-{anticipo.id}-5000.00"]
    assert llamadas[-1][2]["monto"] == Decimal("2000.00")
    foto = pasarela_falsa.inspeccionar_cobro(referencia)
    assert foto.estado is EstadoOperacion.CAPTURADO
    assert foto.monto_reembolsado == Decimal("5000.00")
    [fila] = [
        f
        for f in await filas_ledger(s, escena.pedido_id)
        if f.tipo_evento == ledger.REEMBOLSO
    ]
    assert fila.clave == f"reembolso-{anticipo.id}-5000.00"
