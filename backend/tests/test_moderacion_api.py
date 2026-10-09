"""Moderacion de disputas por la API, contra una base migrada y la pasarela
falsa. Cada prueba termina en rollback."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from src.api.deps import get_pasarela
from src.main import app
from src.models import Disputa, EstadoDisputa, RolPerfil, TipoCobro
from src.payments.contrato import EstadoOperacion
from src.payments.errores import PasarelaNoDisponible
from src.payments.falsa import PasarelaFalsa
from tests.test_pedidos_api import (
    API,
    Escena,
    artista,
    cobros_db,
    consulta,
    cotizar,
    encargo,
    pagar,
    pedido_db,
    perfil,
    ruta,
)


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


# Ayudas


def ruta_moderacion(pedido_id=None, accion: str = "") -> str:
    if pedido_id is None:
        return f"{API}/moderacion/disputas"
    return f"{API}/moderacion/pedidos/{pedido_id}{accion}"


def ruta_resolver(pedido_id) -> str:
    return ruta_moderacion(pedido_id, "/disputa/resolver")


async def admin(sesion_api):
    return await perfil(sesion_api, RolPerfil.ADMIN)


async def disputar(http, autenticar_como, escena: Escena, motivo="No se parece"):
    autenticar_como(escena.comprador.id)
    r = await http.post(ruta(escena.pedido_id, "/disputa"), json={"motivo": motivo})
    assert r.status_code == 201, r.text


async def encargo_en_disputa(http, autenticar_como, sesion_api, pasarela, **kw):
    """Encargo disputado con el saldo autorizado, desde vista_previa_entregada."""
    escena = await encargo(
        http,
        autenticar_como,
        sesion_api,
        pasarela,
        hasta="vista_previa_entregada",
        **kw,
    )
    await disputar(http, autenticar_como, escena)
    return escena


async def evento_en_disputa(http, autenticar_como, sesion_api, pasarela) -> Escena:
    """Evento disputado desde saldo_pagado: anticipo y saldo capturados."""
    artista_ = await artista(sesion_api, pasarela)
    comprador = await perfil(sesion_api)
    consulta_ = await consulta(sesion_api, comprador, artista_)
    fecha = (datetime.now(UTC) + timedelta(days=40)).replace(microsecond=0)
    autenticar_como(artista_.id)
    r = await cotizar(
        http,
        consulta_.id,
        tipo="evento",
        descripcion="Mural en vivo",
        fecha_evento=fecha.isoformat(),
        lugar_evento="San Jose",
    )
    assert r.status_code == 201, r.text
    escena = Escena(artista_, comprador, consulta_.id, uuid.UUID(r.json()["id"]))
    autenticar_como(comprador.id)
    for hito in ("anticipo", "saldo"):
        r = await pagar(http, escena.pedido_id, hito)
        assert r.json()["resultado"] == "completado", r.text
    await disputar(http, autenticar_como, escena)
    return escena


async def resolver(http, pedido_id, destino="completado", reembolsos=(), **cambios):
    datos = {
        "destino": destino,
        "resolucion": "Revisado el chat y las vistas previas",
        "reembolsos": [
            {"cobro_id": str(cobro_id), "monto": str(monto)}
            for cobro_id, monto in reembolsos
        ],
    }
    datos.update(cambios)
    return await http.post(ruta_resolver(pedido_id), json=datos)


async def disputa_db(sesion_api, pedido_id) -> Disputa:
    filas = await sesion_api.execute(
        select(Disputa)
        .where(Disputa.pedido_id == pedido_id)
        .execution_options(populate_existing=True)
    )
    return filas.scalar_one()


def fotos(pasarela: PasarelaFalsa, cobros) -> dict:
    return {
        c.id: pasarela.inspeccionar_cobro(c.referencia_pasarela)
        for c in cobros
        if c.referencia_pasarela is not None
    }


def sin_referencias(texto: str, cobros) -> bool:
    return all(
        c.referencia_pasarela is None or c.referencia_pasarela not in texto
        for c in cobros
    )


# 1. Completar con captura


async def test_8d_01_completar_con_captura(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    moderador = await admin(s)

    autenticar_como(moderador.id)
    r = await resolver(http, escena.pedido_id)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "completado"
    assert cuerpo["soy"] is None
    assert cuerpo["disputa"]["estado"] == "resuelta"
    assert cuerpo["disputa"]["resolucion"] == "Revisado el chat y las vistas previas"
    assert cuerpo["disputa"]["resuelta_en"] is not None

    cobros = await cobros_db(s, escena.pedido_id)
    saldo = cobros[TipoCobro.SALDO]
    foto = pasarela_falsa.inspeccionar_cobro(saldo.referencia_pasarela)
    assert foto.estado is EstadoOperacion.CAPTURADO
    assert foto.monto_capturado == saldo.monto
    assert saldo.estado == "capturado"
    assert saldo.capturado_en is not None
    assert (await pedido_db(s, escena.pedido_id)).estado == "completado"
    disputa = await disputa_db(s, escena.pedido_id)
    assert disputa.estado is EstadoDisputa.RESUELTA
    assert disputa.resuelta_por_id == moderador.id
    assert disputa.resolucion == "Revisado el chat y las vistas previas"
    assert sin_referencias(r.text, cobros.values())


# 2. Cancelar con liberacion y reembolso del anticipo


async def test_8d_02_cancelar_libera_y_reembolsa_el_anticipo(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]

    autenticar_como((await admin(s)).id)
    r = await resolver(
        http,
        escena.pedido_id,
        "cancelado",
        reembolsos=[(anticipo.id, anticipo.monto)],
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"

    cobros = await cobros_db(s, escena.pedido_id)
    saldo, anticipo = cobros[TipoCobro.SALDO], cobros[TipoCobro.ANTICIPO]
    liberado = pasarela_falsa.inspeccionar_cobro(saldo.referencia_pasarela)
    assert liberado.estado is EstadoOperacion.LIBERADO
    assert liberado.monto_capturado == Decimal("0")
    reembolsado = pasarela_falsa.inspeccionar_cobro(anticipo.referencia_pasarela)
    assert reembolsado.monto_reembolsado == anticipo.monto
    assert saldo.estado == "cancelado"
    assert anticipo.estado == "reembolsado"
    assert anticipo.monto_reembolsado == anticipo.monto
    assert (await pedido_db(s, escena.pedido_id)).estado == "cancelado"


# 3. Reembolso parcial al completar


async def test_8d_03_reembolso_parcial_al_completar(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await evento_en_disputa(http, autenticar_como, s, pasarela_falsa)
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    parcial = Decimal("1500.50")

    autenticar_como((await admin(s)).id)
    r = await resolver(http, escena.pedido_id, reembolsos=[(saldo.id, parcial)])
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "completado"

    cobros = await cobros_db(s, escena.pedido_id)
    for tipo, esperado in ((TipoCobro.SALDO, parcial), (TipoCobro.ANTICIPO, 0)):
        cobro = cobros[tipo]
        foto = pasarela_falsa.inspeccionar_cobro(cobro.referencia_pasarela)
        assert foto.monto_reembolsado == esperado
        assert cobro.monto_reembolsado == esperado
    assert cobros[TipoCobro.ANTICIPO].estado == "capturado"


# 4. Validaciones antes de la pasarela


async def test_8d_04_validaciones_antes_de_la_pasarela(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    sin_disputa = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="vista_previa_entregada"
    )
    cobros = await cobros_db(s, escena.pedido_id)
    ajenos = await cobros_db(s, sin_disputa.pedido_id)
    anticipo = cobros[TipoCobro.ANTICIPO]
    todos = [*cobros.values(), *ajenos.values()]
    antes = fotos(pasarela_falsa, todos)
    total = pasarela_falsa.total_cobros

    autenticar_como((await admin(s)).id)
    casos = [
        (sin_disputa.pedido_id, {}, 409),
        (
            escena.pedido_id,
            {"reembolsos": [(ajenos[TipoCobro.ANTICIPO].id, "10.00")]},
            409,
        ),
        (
            escena.pedido_id,
            {"reembolsos": [(anticipo.id, anticipo.monto + Decimal("0.01"))]},
            409,
        ),
        # El saldo esta autorizado, no capturado
        (
            escena.pedido_id,
            {"reembolsos": [(cobros[TipoCobro.SALDO].id, "10.00")]},
            409,
        ),
        (escena.pedido_id, {"destino": "rechazado"}, 422),
        (escena.pedido_id, {"destino": "en_disputa"}, 422),
        (
            escena.pedido_id,
            {"reembolsos": [(anticipo.id, "10.00"), (anticipo.id, "5.00")]},
            422,
        ),
        (escena.pedido_id, {"reembolsos": [(anticipo.id, "10.001")]}, 422),
        (escena.pedido_id, {"reembolsos": [(anticipo.id, "0")]}, 422),
        (escena.pedido_id, {"resolucion": "   "}, 422),
    ]
    for pedido_id, cambios, codigo in casos:
        r = await resolver(http, pedido_id, **cambios)
        assert r.status_code == codigo, (cambios, r.text)
    r = await http.post(
        ruta_resolver(escena.pedido_id),
        json={"destino": "completado", "resolucion": "Ok", "extra": 1},
    )
    assert r.status_code == 422
    r = await resolver(http, uuid.uuid4())
    assert r.status_code == 404

    assert fotos(pasarela_falsa, todos) == antes
    assert pasarela_falsa.total_cobros == total
    assert (await pedido_db(s, escena.pedido_id)).estado == "en_disputa"
    assert (await disputa_db(s, escena.pedido_id)).estado is EstadoDisputa.ABIERTA


# 5. Autorizacion vencida


async def test_8d_05_autorizacion_vencida(cliente, autenticar_como, sesion_api):
    s, http = sesion_api, cliente
    reloj = [datetime.now(UTC)]
    propia = PasarelaFalsa(reloj=lambda: reloj[0])
    # `cliente` usa el fixture `pasarela_falsa`, que quita esto al terminar
    app.dependency_overrides[get_pasarela] = lambda: propia
    escena = await encargo_en_disputa(http, autenticar_como, s, propia)
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    reloj[0] += timedelta(days=propia.capacidades.dias_vigencia_autorizacion + 1)

    autenticar_como((await admin(s)).id)
    r = await resolver(http, escena.pedido_id)
    assert r.status_code == 409, r.text
    assert "autorizacion vencio" in r.json()["detail"]
    # La captura va primero: el reembolso ordenado no llega a la pasarela
    r = await resolver(http, escena.pedido_id, reembolsos=[(anticipo.id, "100.00")])
    assert r.status_code == 409, r.text
    foto = propia.inspeccionar_cobro(anticipo.referencia_pasarela)
    assert foto.monto_reembolsado == Decimal("0")
    assert (await pedido_db(s, escena.pedido_id)).estado == "en_disputa"
    assert (await disputa_db(s, escena.pedido_id)).estado is EstadoDisputa.ABIERTA


# 6. Idempotencia


async def test_8d_06_reintento_sin_doble_movimiento(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    cobros = await cobros_db(s, escena.pedido_id)
    anticipo, saldo = cobros[TipoCobro.ANTICIPO], cobros[TipoCobro.SALDO]
    parcial = Decimal("2000.00")
    # Plan: primero la captura del saldo, despues el reembolso del anticipo
    pasarela_falsa.programar_falla("reembolsar", PasarelaNoDisponible("caida"))

    autenticar_como((await admin(s)).id)
    r = await resolver(http, escena.pedido_id, reembolsos=[(anticipo.id, parcial)])
    assert r.status_code == 503, r.text
    cobros = await cobros_db(s, escena.pedido_id)
    assert cobros[TipoCobro.SALDO].estado == "autorizado"
    assert cobros[TipoCobro.ANTICIPO].monto_reembolsado == Decimal("0")
    assert (await pedido_db(s, escena.pedido_id)).estado == "en_disputa"
    assert (await disputa_db(s, escena.pedido_id)).estado is EstadoDisputa.ABIERTA
    capturado = pasarela_falsa.inspeccionar_cobro(saldo.referencia_pasarela)
    assert capturado.estado is EstadoOperacion.CAPTURADO

    r = await resolver(http, escena.pedido_id, reembolsos=[(anticipo.id, parcial)])
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "completado"
    capturado = pasarela_falsa.inspeccionar_cobro(saldo.referencia_pasarela)
    assert capturado.monto_capturado == saldo.monto
    reembolsado = pasarela_falsa.inspeccionar_cobro(anticipo.referencia_pasarela)
    assert reembolsado.monto_reembolsado == parcial
    cobros = await cobros_db(s, escena.pedido_id)
    assert cobros[TipoCobro.SALDO].estado == "capturado"
    assert cobros[TipoCobro.ANTICIPO].monto_reembolsado == parcial


# 7. Permisos


async def test_8d_07_solo_moderacion(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    tercero = await perfil(s)
    pedido_id = escena.pedido_id

    for quien in (escena.comprador, escena.artista, tercero):
        autenticar_como(quien.id)
        respuestas = [
            await http.get(ruta_moderacion()),
            await http.get(ruta_moderacion(pedido_id)),
            await http.get(ruta_moderacion(pedido_id, "/mensajes")),
            await resolver(http, pedido_id),
        ]
        assert [r.status_code for r in respuestas] == [403] * 4
    assert (await pedido_db(s, pedido_id)).estado == "en_disputa"


# 8. Lecturas


async def test_8d_08_disputas_abiertas_sin_n_mas_1(
    cliente, autenticar_como, sesion_api, pasarela_falsa, test_db
):
    s, http = sesion_api, cliente
    moderador = await admin(s)
    abiertas: list[str] = []
    resuelta = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(moderador.id)
    assert (await resolver(http, resuelta.pedido_id)).status_code == 200

    async def _contar_listado(cuantas: int) -> int:
        while len(abiertas) < cuantas:
            escena = await encargo_en_disputa(http, autenticar_como, s, pasarela_falsa)
            abiertas.append(str(escena.pedido_id))
        contador = 0

        def _contar(*_args) -> None:
            nonlocal contador
            contador += 1

        autenticar_como(moderador.id)
        event.listen(test_db.sync_engine, "before_cursor_execute", _contar)
        try:
            r = await http.get(ruta_moderacion())
        finally:
            event.remove(test_db.sync_engine, "before_cursor_execute", _contar)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert [i["id"] for i in items] == abiertas
        assert all(i["soy"] is None for i in items)
        assert all(i["disputa"]["estado"] == "abierta" for i in items)
        assert all(len(i["vistas_previas"]) == 1 for i in items)
        assert all(len(i["cobros"]) == 2 for i in items)
        return contador

    assert await _contar_listado(2) == await _contar_listado(6)

    vistos: list[str] = []
    cursor = None
    while True:
        params = {"tamano": 4} | ({"cursor": cursor} if cursor else {})
        r = await http.get(ruta_moderacion(), params=params)
        assert r.status_code == 200, r.text
        vistos += [p["id"] for p in r.json()["items"]]
        cursor = r.json()["siguiente_cursor"]
        if cursor is None:
            break
    assert vistos == abiertas
    assert str(resuelta.pedido_id) not in vistos


async def test_8d_08_detalle_y_mensajes(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="vista_previa_entregada"
    )
    chat = [
        (escena.comprador, "Hola, quiero un retrato"),
        (escena.artista, "Con gusto, te cotizo"),
        (escena.comprador, "Mi numero es 8888 8888"),
    ]
    for quien, texto in chat:
        autenticar_como(quien.id)
        r = await http.post(
            f"{API}/consultas/{escena.consulta_id}/mensajes", json={"texto": texto}
        )
        assert r.status_code == 201, r.text
    await disputar(http, autenticar_como, escena, motivo="La vista previa no cumple")
    cobros = (await cobros_db(s, escena.pedido_id)).values()

    autenticar_como((await admin(s)).id)
    r = await http.get(ruta_moderacion(escena.pedido_id))
    assert r.status_code == 200, r.text
    detalle = r.json()
    assert detalle["soy"] is None
    assert detalle["estado"] == "en_disputa"
    disputa = detalle["disputa"]
    assert disputa["estado"] == "abierta"
    assert disputa["motivo"] == "La vista previa no cumple"
    assert disputa["abierta_por"]["handle"] == escena.comprador.handle
    assert disputa["resolucion"] is None
    assert disputa["resuelta_en"] is None
    assert len(detalle["vistas_previas"]) == 1
    assert sin_referencias(r.text, cobros)

    r = await http.get(ruta_moderacion(escena.pedido_id, "/mensajes"))
    assert r.status_code == 200, r.text
    mensajes = r.json()["items"]
    assert [(m["remitente"]["handle"], m["texto"]) for m in mensajes] == [
        (quien.handle, texto) for quien, texto in chat
    ]
    assert [m["aviso_contacto"] for m in mensajes] == [False, False, True]
    assert set(mensajes[0]) == {"remitente", "texto", "aviso_contacto", "created_at"}

    r = await http.get(
        ruta_moderacion(escena.pedido_id, "/mensajes"), params={"tamano": 2}
    )
    primera = r.json()
    assert len(primera["items"]) == 2
    r = await http.get(
        ruta_moderacion(escena.pedido_id, "/mensajes"),
        params={"tamano": 2, "cursor": primera["siguiente_cursor"]},
    )
    assert [m["texto"] for m in r.json()["items"]] == [chat[2][1]]
    assert r.json()["siguiente_cursor"] is None

    for accion in ("", "/mensajes"):
        r = await http.get(ruta_moderacion(uuid.uuid4(), accion))
        assert r.status_code == 404, r.text

    r = await resolver(http, escena.pedido_id)
    assert r.status_code == 200, r.text
    assert sin_referencias(r.text, cobros)
    assert "url_autenticacion" not in r.text


# 9. La parte ve la disputa


async def test_8d_09_la_parte_ve_la_disputa(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="vista_previa_entregada"
    )
    autenticar_como(escena.comprador.id)
    r = await http.get(ruta(escena.pedido_id))
    assert r.json()["disputa"] is None
    await disputar(http, autenticar_como, escena)

    r = await http.get(ruta(escena.pedido_id))
    assert r.status_code == 200, r.text
    assert r.json()["soy"] == "cliente"
    assert r.json()["disputa"]["estado"] == "abierta"
    assert r.json()["disputa"]["abierta_por"]["handle"] == escena.comprador.handle

    autenticar_como((await admin(s)).id)
    assert (await resolver(http, escena.pedido_id)).status_code == 200

    autenticar_como(escena.comprador.id)
    r = await http.get(ruta(escena.pedido_id))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "completado"
    disputa = r.json()["disputa"]
    assert disputa["estado"] == "resuelta"
    assert disputa["resolucion"] == "Revisado el chat y las vistas previas"
    assert disputa["resuelta_en"] is not None
