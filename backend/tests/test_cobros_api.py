"""Cobros por la API: 3DS, intentos e idempotencia, contra una base migrada y
la pasarela falsa. Cada prueba termina en rollback."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from src.api.deps import get_pasarela
from src.main import app
from src.models import Cobro, Consulta, Obra, Pedido, TipoCobro
from src.payments.contrato import EstadoOperacion
from src.payments.falsa import MEDIO_PAGO_3DS, MEDIO_PAGO_RECHAZADO, PasarelaFalsa
from tests.test_pedidos_api import (
    API,
    OTRA_TARJETA,
    TARJETA,
    artista,
    cobros_db,
    encargo,
    obra,
    pagar,
    pedido_db,
    perfil,
    ruta,
    ruta_la_quiero,
    ruta_verificar,
)

OPERACIONES_DE_DINERO = (
    "cobrar",
    "autorizar",
    "capturar",
    "liberar_autorizacion",
    "reembolsar",
    "consultar_cobro",
)


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


def espiar(pasarela) -> list[tuple[str, tuple, dict]]:
    """Anota cada llamada de dinero a la pasarela, con sus argumentos."""
    llamadas: list[tuple[str, tuple, dict]] = []
    for nombre in OPERACIONES_DE_DINERO:
        original = getattr(pasarela, nombre)

        async def envuelta(*args, _nombre=nombre, _original=original, **kwargs):
            llamadas.append((_nombre, args, kwargs))
            return await _original(*args, **kwargs)

        setattr(pasarela, nombre, envuelta)
    return llamadas


async def cobro_db(sesion_api, cobro_id) -> Cobro:
    return await sesion_api.get(Cobro, uuid.UUID(str(cobro_id)), populate_existing=True)


# 14. Anticipo con 3DS aprobado


async def test_8b_14_anticipo_con_3ds_aprobado(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(escena.comprador.id)

    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["resultado"] == "requiere_accion"
    url = cuerpo["url_autenticacion"]
    assert url.startswith("https://")
    assert cuerpo["pedido"]["estado"] == "cotizado"
    assert cuerpo["cobro"]["estado"] == "pendiente"
    assert cuerpo["cobro"]["esperando_autenticacion"] is True
    cobro_id = cuerpo["cobro"]["id"]

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "requiere_accion"
    assert r.json()["url_autenticacion"] == url

    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    pasarela_falsa.completar_autenticacion(referencia, aprobada=True)
    r = await http.post(ruta_verificar(cobro_id))
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "completado"
    assert r.json()["url_autenticacion"] is None
    assert r.json()["pedido"]["estado"] == "anticipo_pagado"
    assert r.json()["cobro"]["estado"] == "capturado"
    assert r.json()["cobro"]["esperando_autenticacion"] is False

    llamadas = espiar(pasarela_falsa)
    total = pasarela_falsa.total_cobros
    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "completado"
    assert llamadas == []
    assert pasarela_falsa.total_cobros == total


# 15. 3DS rechazado y reintento con otra tarjeta


async def test_8b_15_3ds_rechazado_y_reintento(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    llamadas = espiar(pasarela_falsa)
    autenticar_como(escena.comprador.id)

    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    cobro_id = r.json()["cobro"]["id"]
    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    pasarela_falsa.completar_autenticacion(referencia, aprobada=False)

    r = await http.post(ruta_verificar(cobro_id))
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "rechazado"
    assert r.json()["mensaje"]
    assert r.json()["pedido"]["estado"] == "cotizado"
    cobro = await cobro_db(s, cobro_id)
    assert cobro.intentos == 1
    assert cobro.referencia_pasarela is None

    r = await pagar(http, escena.pedido_id, "anticipo", OTRA_TARJETA)
    assert r.json()["resultado"] == "completado", r.text
    assert r.json()["pedido"]["estado"] == "anticipo_pagado"
    claves = [a[0].clave_idempotencia for n, a, _ in llamadas if n == "cobrar"]
    assert claves == [f"cobrar-{cobro_id}-0", f"cobrar-{cobro_id}-1"]


# 16. Pago rechazado


async def test_8b_16_pago_rechazado(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(escena.comprador.id)

    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_RECHAZADO)
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "rechazado"
    assert r.json()["mensaje"]
    assert r.json()["pedido"]["estado"] == "cotizado"
    cobro_id = r.json()["cobro"]["id"]
    # Confirmado: el handler hizo commit del intento consumido
    assert (await cobro_db(s, cobro_id)).intentos == 1

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "rechazado"

    r = await pagar(http, escena.pedido_id, "anticipo", TARJETA)
    assert r.json()["resultado"] == "completado", r.text
    assert (await cobro_db(s, cobro_id)).intentos == 1


# 17. Repetir el mismo intento


async def test_8b_17_repetir_el_mismo_intento(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(escena.comprador.id)

    primera = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    cobro_id = primera.json()["cobro"]["id"]
    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    segunda = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)

    assert segunda.json()["resultado"] == "requiere_accion"
    assert segunda.json()["url_autenticacion"] == primera.json()["url_autenticacion"]
    assert (await cobro_db(s, cobro_id)).referencia_pasarela == referencia
    assert (await cobro_db(s, cobro_id)).intentos == 0
    assert pasarela_falsa.total_cobros == 1


# 18. Saldo de encargo y La quiero con 3DS


async def test_8b_18_saldo_de_encargo_con_3ds(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="con_vista_previa"
    )
    autenticar_como(escena.comprador.id)

    r = await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "requiere_accion", r.text
    assert r.json()["pedido"]["estado"] == "en_proceso"
    cobro_id = r.json()["cobro"]["id"]
    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    pasarela_falsa.completar_autenticacion(referencia, aprobada=True)

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "completado", r.text
    assert r.json()["pedido"]["estado"] == "vista_previa_entregada"
    assert r.json()["cobro"]["estado"] == "autorizado"
    assert r.json()["cobro"]["autorizado_hasta"] is not None


async def test_8b_18_la_quiero_con_3ds(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    pieza = await obra(s, await artista(s, pasarela_falsa))
    autenticar_como((await perfil(s)).id)

    r = await http.post(
        ruta_la_quiero(pieza.id), json={"metodo_pago_id": MEDIO_PAGO_3DS}
    )
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "requiere_accion"
    assert r.json()["pedido"]["estado"] == "cotizado"
    cobro_id = r.json()["cobro"]["id"]
    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    pasarela_falsa.completar_autenticacion(referencia, aprobada=True)

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "completado", r.text
    assert r.json()["pedido"]["estado"] == "en_proceso"
    assert r.json()["cobro"]["estado"] == "autorizado"
    assert r.json()["cobro"]["autorizado_hasta"] is not None


async def test_8b_18_la_quiero_con_3ds_fallido_libera_la_obra(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    pieza = await obra(s, await artista(s, pasarela_falsa))
    autenticar_como((await perfil(s)).id)

    r = await http.post(
        ruta_la_quiero(pieza.id), json={"metodo_pago_id": MEDIO_PAGO_3DS}
    )
    cobro_id = r.json()["cobro"]["id"]
    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    pasarela_falsa.completar_autenticacion(referencia, aprobada=False)

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "rechazado", r.text
    assert r.json()["pedido"]["estado"] == "rechazado"

    autenticar_como((await perfil(s)).id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "completado"


# 19. La quiero rechazado: no queda nada


async def test_8b_19_la_quiero_rechazado(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    pieza = await obra(s, await artista(s, pasarela_falsa))
    obra_id = pieza.id
    comprador_id, otro_id = (await perfil(s)).id, (await perfil(s)).id
    # El handler hace rollback: lo de la prueba tiene que estar confirmado antes
    await s.commit()

    autenticar_como(comprador_id)
    r = await http.post(
        ruta_la_quiero(obra_id), json={"metodo_pago_id": MEDIO_PAGO_RECHAZADO}
    )
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "rechazado"
    assert r.json()["mensaje"]
    assert r.json()["pedido"] is None
    assert r.json()["cobro"] is None
    pedidos = await s.scalar(
        select(func.count(Pedido.id)).where(Pedido.obra_id == obra_id)
    )
    consultas = await s.scalar(
        select(func.count(Consulta.id)).where(Consulta.obra_id == obra_id)
    )
    assert (pedidos, consultas) == (0, 0)

    autenticar_como(otro_id)
    r = await http.post(ruta_la_quiero(obra_id), json={"metodo_pago_id": TARJETA})
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "completado"
    assert (await s.get(Obra, obra_id, populate_existing=True)).estado.value == (
        "disponible"
    )


# 20. Rechazar con 3DS pendiente


async def test_8b_20_rechazar_con_3ds_pendiente(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    referencia = (await cobro_db(s, r.json()["cobro"]["id"])).referencia_pasarela

    autenticar_como(escena.artista.id)
    r = await http.post(ruta(escena.pedido_id, "/rechazar"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "rechazado"
    foto = pasarela_falsa.inspeccionar_cobro(referencia)
    assert foto.estado is EstadoOperacion.LIBERADO


async def test_8b_20_cancelar_con_3ds_pendiente_del_saldo(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="con_vista_previa"
    )
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_3DS)
    referencia = (await cobro_db(s, r.json()["cobro"]["id"])).referencia_pasarela

    r = await http.post(ruta(escena.pedido_id, "/cancelar"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"
    foto = pasarela_falsa.inspeccionar_cobro(referencia)
    assert foto.estado is EstadoOperacion.LIBERADO


# 21. Aprobar con la autorizacion vencida


async def test_8b_21_aprobar_con_la_autorizacion_vencida(
    cliente, autenticar_como, sesion_api
):
    s, http = sesion_api, cliente
    momento = [datetime.now(UTC)]
    propia = PasarelaFalsa(reloj=lambda: momento[0])
    app.dependency_overrides[get_pasarela] = lambda: propia
    escena = await encargo(
        http, autenticar_como, s, propia, hasta="vista_previa_entregada"
    )
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    momento[0] = saldo.autorizado_hasta + timedelta(seconds=1)

    autenticar_como(escena.comprador.id)
    r = await http.post(ruta(escena.pedido_id, "/aprobar"))
    assert r.status_code == 409, r.text
    assert "vencio" in r.json()["detail"]
    assert (await pedido_db(s, escena.pedido_id)).estado.value == (
        "vista_previa_entregada"
    )
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado.value == "autorizado"
    foto = propia.inspeccionar_cobro(saldo.referencia_pasarela)
    assert foto.estado is EstadoOperacion.AUTORIZADO


# 22. Ninguna respuesta lleva la referencia de la pasarela


async def test_8b_22_ninguna_respuesta_lleva_la_referencia(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    respuestas: list[dict] = []
    referencias: set[str] = set()

    async def _anotar(r, pedido_id) -> None:
        cuerpo = r.json()
        # La url del 3DS de la falsa lleva la referencia; la de ONVO es del banco
        cuerpo.pop("url_autenticacion", None)
        respuestas.append(cuerpo)
        for cobro in (await cobros_db(s, pedido_id)).values():
            if cobro.referencia_pasarela:
                referencias.add(cobro.referencia_pasarela)

    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="con_vista_previa"
    )
    pid = escena.pedido_id
    autenticar_como(escena.comprador.id)
    r = await pagar(http, pid, "saldo", MEDIO_PAGO_3DS)
    await _anotar(r, pid)
    cobro_id = r.json()["cobro"]["id"]
    await _anotar(await http.post(ruta_verificar(cobro_id)), pid)
    pasarela_falsa.completar_autenticacion(
        (await cobro_db(s, cobro_id)).referencia_pasarela, aprobada=True
    )
    await _anotar(await http.post(ruta_verificar(cobro_id)), pid)
    await _anotar(await http.post(ruta(pid, "/aprobar")), pid)
    await _anotar(await http.get(ruta(pid)), pid)
    await _anotar(await http.get(f"{API}/pedidos"), pid)

    pieza = await obra(s, escena.artista)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    obra_pid = r.json()["pedido"]["id"]
    await _anotar(r, obra_pid)
    autenticar_como(escena.artista.id)
    await _anotar(
        await http.post(ruta(obra_pid, "/despacho"), json={"guia_envio": "CR9"}),
        obra_pid,
    )

    for pedido_id in (pid, obra_pid):
        for cobro in (await cobros_db(s, pedido_id)).values():
            referencias.add(cobro.referencia_pasarela)
    # Anticipo, saldo y total
    assert len(referencias) == 3
    texto = json.dumps(respuestas)
    assert "referencia" not in texto
    for referencia in referencias:
        assert referencia not in texto


async def test_8b_20_rechazar_con_3ds_ya_cobrado_exige_verificar(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    cobro_id = r.json()["cobro"]["id"]
    referencia = (await cobro_db(s, cobro_id)).referencia_pasarela
    # El cliente se autentico pero no volvio a la app
    pasarela_falsa.completar_autenticacion(referencia, aprobada=True)

    r = await http.post(ruta(escena.pedido_id, "/rechazar"))
    assert r.status_code == 409, r.text
    assert (await pedido_db(s, escena.pedido_id)).estado.value == "cotizado"
    foto = pasarela_falsa.inspeccionar_cobro(referencia)
    assert foto.estado is EstadoOperacion.CAPTURADO

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "completado"
    assert r.json()["pedido"]["estado"] == "anticipo_pagado"


async def test_8b_20_contraoferta_con_3ds_pendiente(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    autenticar_como(escena.comprador.id)
    await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)

    autenticar_como(escena.artista.id)
    r = await http.put(
        ruta(escena.pedido_id, "/cotizacion"),
        json={"descripcion": "Otra", "monto_total": "30000.00"},
    )
    assert r.status_code == 409, r.text
    assert (await pedido_db(s, escena.pedido_id)).monto_total == 20000
