"""Ledger: una fila por cada captura y cada reembolso, contra una base migrada
y la pasarela falsa. Cada prueba termina en rollback."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.domain.pedidos import porcentaje_de
from src.models import EstadoCobro, LedgerEntry, TipoCobro
from src.services import ledger
from src.tareas.barrido import barrer
from tests.test_moderacion_api import admin, encargo_en_disputa, resolver
from tests.test_pedidos_api import (
    POLITICAS,
    TARJETA,
    artista,
    cobros_db,
    encargo,
    obra,
    pedido_db,
    perfil,
    ruta,
    ruta_la_quiero,
)
from tests.test_vencimientos import evento


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


async def filas_ledger(s, pedido_id) -> list[LedgerEntry]:
    filas = await s.execute(
        select(LedgerEntry)
        .where(LedgerEntry.pedido_id == uuid.UUID(str(pedido_id)))
        .order_by(LedgerEntry.created_at, LedgerEntry.id)
        .execution_options(populate_existing=True)
    )
    return list(filas.scalars())


async def total_ledger(s) -> int:
    return (await s.execute(select(func.count()).select_from(LedgerEntry))).scalar()


def de_tipo(filas, tipo: str) -> list[LedgerEntry]:
    return [f for f in filas if f.tipo_evento == tipo]


# 12. Encargo completo


async def test_9b_12_encargo_completo_asienta_dos_capturas(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    pedido = await pedido_db(s, escena.pedido_id)
    cobros = await cobros_db(s, escena.pedido_id)

    filas = await filas_ledger(s, escena.pedido_id)
    assert [f.tipo_evento for f in filas] == [ledger.CAPTURA, ledger.CAPTURA]
    por_cobro = {f.cobro_id: f for f in filas}
    for tipo in (TipoCobro.ANTICIPO, TipoCobro.SALDO):
        cobro = cobros[tipo]
        fila = por_cobro[cobro.id]
        assert fila.clave == f"captura-{cobro.id}"
        assert fila.monto_bruto == cobro.monto
        assert fila.tarifa_artistica == porcentaje_de(
            cobro.monto, pedido.tarifa_porcentaje
        )
        assert fila.costo_procesamiento is None
        assert fila.monto_neto_artista is None
        assert fila.profile_id == escena.artista.id
        assert fila.referencia_pasarela == cobro.referencia_pasarela
    assert sum(f.monto_bruto for f in filas) == pedido.monto_total


# 13. Evento cancelado por el cliente con el 50 %


async def test_9b_13_evento_cancelado_con_la_mitad_asienta_un_reembolso(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    comprador, pedido_id, _ = await evento(
        http, autenticar_como, s, pasarela_falsa, dias=10
    )
    assert POLITICAS.cancelacion_evento_porcentaje_parcial == Decimal("50")
    autenticar_como(comprador.id)

    r = await http.post(ruta(pedido_id, "/cancelar"))
    assert r.status_code == 200, r.text
    anticipo = (await cobros_db(s, pedido_id))[TipoCobro.ANTICIPO]
    filas = await filas_ledger(s, pedido_id)
    [reembolso] = de_tipo(filas, ledger.REEMBOLSO)
    mitad = anticipo.monto / 2
    assert reembolso.monto_bruto == mitad
    assert reembolso.cobro_id == anticipo.id
    assert reembolso.clave == f"reembolso-{anticipo.id}-{mitad}"
    assert reembolso.tarifa_artistica is None
    assert reembolso.costo_procesamiento is None
    assert reembolso.monto_neto_artista is None
    assert len(de_tipo(filas, ledger.CAPTURA)) == 1


# 14. Obra despachada y disputa resuelta


async def test_9b_14_obra_despachada_asienta_una_captura(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    artista_ = await artista(s, pasarela_falsa)
    pieza = await obra(s, artista_)
    autenticar_como((await perfil(s)).id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    pid = r.json()["pedido"]["id"]
    assert await filas_ledger(s, pid) == []

    autenticar_como(artista_.id)
    r = await http.post(ruta(pid, "/despacho"), json={"guia_envio": "CR1"})
    assert r.status_code == 200, r.text
    total = (await cobros_db(s, pid))[TipoCobro.TOTAL]
    [fila] = await filas_ledger(s, pid)
    assert fila.tipo_evento == ledger.CAPTURA
    assert fila.cobro_id == total.id
    assert fila.monto_bruto == pieza.precio


async def test_9b_14_disputa_con_captura_y_reembolso_parcial_asienta_las_dos(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    cobros = await cobros_db(s, escena.pedido_id)
    anticipo, saldo = cobros[TipoCobro.ANTICIPO], cobros[TipoCobro.SALDO]
    antes = await filas_ledger(s, escena.pedido_id)
    autenticar_como((await admin(s)).id)

    parcial = Decimal("3000.00")
    r = await resolver(http, escena.pedido_id, reembolsos=[(anticipo.id, parcial)])
    assert r.status_code == 200, r.text
    nuevas = (await filas_ledger(s, escena.pedido_id))[len(antes) :]
    assert {(f.tipo_evento, f.cobro_id) for f in nuevas} == {
        (ledger.CAPTURA, saldo.id),
        (ledger.REEMBOLSO, anticipo.id),
    }
    [reembolso] = de_tipo(nuevas, ledger.REEMBOLSO)
    assert reembolso.monto_bruto == parcial
    assert reembolso.clave == f"reembolso-{anticipo.id}-{parcial}"
    [captura] = de_tipo(nuevas, ledger.CAPTURA)
    assert captura.monto_bruto == saldo.monto


# 15. Ningun hecho sin dinero se asienta


async def test_9b_15_autorizar_liberar_y_vencer_no_asientan(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela_falsa
):
    s, http = sesion_api, cliente
    # Autorizacion del saldo: solo queda la captura del anticipo
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="vista_previa_entregada"
    )
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.AUTORIZADO
    assert [f.tipo_evento for f in await filas_ledger(s, escena.pedido_id)] == [
        ledger.CAPTURA
    ]

    # Vencimiento de la autorizacion por el barrido
    total = await total_ledger(s)
    await barrer(
        sesiones_prueba,
        pasarela_falsa,
        ahora=saldo.autorizado_hasta + timedelta(seconds=1),
        politicas=POLITICAS,
    )
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.VENCIDO
    assert await total_ledger(s) == total

    # Autorizacion y liberacion de La quiero
    artista_ = await artista(s, pasarela_falsa)
    pieza = await obra(s, artista_)
    autenticar_como((await perfil(s)).id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    pid = r.json()["pedido"]["id"]
    r = await http.post(ruta(pid, "/cancelar"))
    assert r.status_code == 200, r.text
    assert (await cobros_db(s, pid))[TipoCobro.TOTAL].estado is EstadoCobro.CANCELADO
    assert await filas_ledger(s, pid) == []
    assert await total_ledger(s) == total


# 16. La clave es unica


async def test_9b_16_dos_filas_con_la_misma_clave_violan_la_restriccion(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="anticipo_pagado"
    )
    pedido = await pedido_db(s, escena.pedido_id)
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]

    with pytest.raises(IntegrityError) as error:
        async with s.begin_nested():
            await ledger.asentar_captura(
                s, pedido=pedido, cobro=anticipo, ahora=datetime.now(UTC)
            )
    diag = error.value.orig.diag
    assert diag.constraint_name == "uq_ledger_entries_clave"
    assert len(await filas_ledger(s, escena.pedido_id)) == 1
