"""Vencimientos por la API y el barrido, contra una base migrada y una pasarela
falsa con reloj propio. Cada prueba termina en rollback.

La API usa la hora real; el barrido recibe `ahora` explicito. El reloj de la
falsa se mueve aparte, para que una autorizacion este viva o vencida segun la
pasarela.
"""

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.api.deps import get_pasarela
from src.main import app
from src.models import (
    EstadoCobro,
    EstadoPedido,
    TipoCobro,
)
from src.payments.contrato import EstadoCobroPasarela, EstadoOperacion
from src.payments.errores import PasarelaNoDisponible
from src.payments.falsa import MEDIO_PAGO_3DS, MEDIO_PAGO_RECHAZADO, PasarelaFalsa
from src.tareas.barrido import Conteo, ResumenBarrido, barrer
from tests.test_cobros_api import espiar
from tests.test_pedidos_api import (
    OTRA_TARJETA,
    POLITICAS,
    TARJETA,
    artista,
    cobros_db,
    consulta,
    cotizar,
    encargo,
    obra,
    pagar,
    pedido_db,
    perfil,
    ruta,
    ruta_la_quiero,
    ruta_verificar,
)

UN_SEGUNDO = timedelta(seconds=1)
PLAZO = POLITICAS.plazo_reautorizacion_saldo
ABANDONO = POLITICAS.abandono_3ds
DE_DINERO = {"cobrar", "autorizar", "capturar", "liberar_autorizacion", "reembolsar"}
NADA = Conteo()


@pytest.fixture
def momento() -> list[datetime]:
    """El reloj de la falsa. Se mueve asignando momento[0]."""
    return [datetime.now(UTC)]


@pytest.fixture
def pasarela(momento):
    propia = PasarelaFalsa(reloj=lambda: momento[0])
    app.dependency_overrides[get_pasarela] = lambda: propia
    yield propia
    app.dependency_overrides.pop(get_pasarela, None)


@pytest.fixture
def cliente(async_client, sesion_api, pasarela, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


async def barrido(sesiones, pasarela, ahora: datetime) -> ResumenBarrido:
    return await barrer(sesiones, pasarela, ahora=ahora, politicas=POLITICAS)


def nombres(llamadas) -> list[str]:
    return [n for n, _, _ in llamadas]


def de_dinero(llamadas) -> list[str]:
    return [n for n in nombres(llamadas) if n in DE_DINERO]


async def estado(s, pedido_id) -> EstadoPedido:
    return (await pedido_db(s, pedido_id)).estado


async def saldo_de(s, pedido_id):
    return (await cobros_db(s, pedido_id))[TipoCobro.SALDO]


async def encargo_con_saldo_vencido(http, autenticar_como, s, pasarela, sesiones):
    """Encargo con la vista previa entregada y el saldo ya vencido por el
    barrido. Devuelve la escena y el `autorizado_hasta` original."""
    escena = await encargo(
        http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
    )
    vence = (await saldo_de(s, escena.pedido_id)).autorizado_hasta
    await barrido(sesiones, pasarela, vence + UN_SEGUNDO)
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.VENCIDO
    autenticar_como(escena.comprador.id)
    return escena, vence


async def evento(http, autenticar_como, s, pasarela, *, dias=10):
    """Evento con el anticipo pagado. Devuelve el comprador, el id y la fecha."""
    artista_ = await artista(s, pasarela)
    comprador = await perfil(s)
    consulta_ = await consulta(s, comprador, artista_)
    fecha = (datetime.now(UTC) + timedelta(days=dias)).replace(microsecond=0)
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
    pedido_id = uuid.UUID(r.json()["id"])
    autenticar_como(comprador.id)
    r = await pagar(http, pedido_id, "anticipo")
    assert r.json()["pedido"]["estado"] == "anticipo_pagado", r.text
    return comprador, pedido_id, fecha


async def la_quiero(http, autenticar_como, s, pasarela, metodo=TARJETA):
    """Obra pedida con La quiero. Devuelve la obra, el id del pedido y el
    cuerpo de la respuesta."""
    pieza = await obra(s, await artista(s, pasarela))
    comprador = await perfil(s)
    # Un La quiero rechazado hace rollback: lo de la prueba va confirmado
    await s.commit()
    autenticar_como(comprador.id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": metodo})
    assert r.status_code == 201, r.text
    return pieza, uuid.UUID(r.json()["pedido"]["id"]), r.json()


async def otro_pide(http, autenticar_como, s, obra_id):
    autenticar_como((await perfil(s)).id)
    await s.commit()
    return await http.post(ruta_la_quiero(obra_id), json={"metodo_pago_id": TARJETA})


# 1. Autorizacion del saldo vencida


async def test_9_01_autorizacion_vencida_viva_en_la_pasarela_se_libera(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
    )
    saldo = await saldo_de(s, escena.pedido_id)
    referencia, intentos = saldo.referencia_pasarela, saldo.intentos
    llamadas = espiar(pasarela)

    resumen = await barrido(
        sesiones_prueba, pasarela, saldo.autorizado_hasta - UN_SEGUNDO
    )
    assert resumen.autorizaciones_vencidas == NADA
    assert llamadas == []

    # La falsa todavia la tiene viva segun su reloj
    resumen = await barrido(sesiones_prueba, pasarela, saldo.autorizado_hasta)
    assert resumen.autorizaciones_vencidas == Conteo(1, 0)
    assert nombres(llamadas) == ["consultar_cobro", "liberar_autorizacion"]
    _, args, kwargs = llamadas[1]
    assert args == (referencia,)
    assert kwargs == {"clave_idempotencia": f"liberar-{saldo.id}-{intentos}"}
    saldo = await saldo_de(s, escena.pedido_id)
    assert saldo.estado is EstadoCobro.VENCIDO
    assert await estado(s, escena.pedido_id) is EstadoPedido.VISTA_PREVIA_ENTREGADA
    assert pasarela.inspeccionar_cobro(referencia).estado is EstadoOperacion.LIBERADO


async def test_9_01_autorizacion_ya_liberada_no_se_libera_otra_vez(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela, momento
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
    )
    vence = (await saldo_de(s, escena.pedido_id)).autorizado_hasta
    momento[0] = vence + UN_SEGUNDO
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, vence + UN_SEGUNDO)
    assert resumen.autorizaciones_vencidas == Conteo(1, 0)
    assert nombres(llamadas) == ["consultar_cobro"]
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.VENCIDO
    assert await estado(s, escena.pedido_id) is EstadoPedido.VISTA_PREVIA_ENTREGADA


# 2. Reautorizacion


async def test_9_02_reautorizacion_y_aprobacion(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela, momento
):
    s, http = sesion_api, cliente
    escena, vence = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )
    vencido = await saldo_de(s, escena.pedido_id)
    referencia, intentos = vencido.referencia_pasarela, vencido.intentos
    momento[0] += timedelta(hours=1)

    r = await pagar(http, escena.pedido_id, "saldo")
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "completado"
    assert r.json()["pedido"]["estado"] == "vista_previa_entregada"
    saldo = await saldo_de(s, escena.pedido_id)
    assert saldo.estado is EstadoCobro.AUTORIZADO
    assert saldo.referencia_pasarela not in (None, referencia)
    assert saldo.intentos == intentos + 1
    assert saldo.autorizado_hasta > vence

    r = await http.post(ruta(escena.pedido_id, "/aprobar"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "saldo_pagado"
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.CAPTURADO


# 3. Reautorizacion con 3DS


async def test_9_03_reautorizacion_con_3ds(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena, _ = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )

    r = await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "requiere_accion", r.text
    cobro_id = r.json()["cobro"]["id"]
    saldo = await saldo_de(s, escena.pedido_id)
    assert saldo.estado is EstadoCobro.PENDIENTE
    pasarela.completar_autenticacion(saldo.referencia_pasarela, aprobada=True)

    r = await http.post(ruta_verificar(cobro_id))
    assert r.json()["resultado"] == "completado", r.text
    assert r.json()["pedido"]["estado"] == "vista_previa_entregada"
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.AUTORIZADO


# 4. Reautorizacion rechazada


async def test_9_04_reautorizacion_rechazada_y_reintento(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena, vence = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )

    r = await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_RECHAZADO)
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "rechazado"
    saldo = await saldo_de(s, escena.pedido_id)
    assert saldo.estado is EstadoCobro.PENDIENTE
    assert saldo.referencia_pasarela is None
    # El plazo sigue contando desde el vencimiento original
    assert saldo.autorizado_hasta == vence

    r = await pagar(http, escena.pedido_id, "saldo", OTRA_TARJETA)
    assert r.json()["resultado"] == "completado", r.text
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.AUTORIZADO


# 5. Reautorizacion fuera de plazo


async def test_9_05_reautorizacion_fuera_de_plazo(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena, _ = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )
    # La API usa la hora real: el vencimiento se corre al pasado
    saldo = await saldo_de(s, escena.pedido_id)
    saldo.autorizado_hasta = datetime.now(UTC) - PLAZO - UN_SEGUNDO
    await s.commit()
    llamadas = espiar(pasarela)

    r = await pagar(http, escena.pedido_id, "saldo")
    assert r.status_code == 409, r.text
    assert llamadas == []
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.VENCIDO


async def test_9_05_saldo_autorizado_no_se_vuelve_a_autorizar(
    cliente, autenticar_como, sesion_api, pasarela
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
    )
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "saldo")
    assert r.status_code == 409, r.text


# 6. Pasado el plazo sin reautorizar


async def test_9_06_pasado_el_plazo_se_cancela_y_el_anticipo_queda(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena, vence = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, vence + PLAZO - UN_SEGUNDO)
    assert resumen.reautorizaciones_vencidas == NADA
    assert await estado(s, escena.pedido_id) is EstadoPedido.VISTA_PREVIA_ENTREGADA

    resumen = await barrido(sesiones_prueba, pasarela, vence + PLAZO)
    assert resumen.reautorizaciones_vencidas == Conteo(1, 0)
    assert await estado(s, escena.pedido_id) is EstadoPedido.CANCELADO
    cobros = await cobros_db(s, escena.pedido_id)
    anticipo = cobros[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.CAPTURADO
    assert anticipo.monto_reembolsado == Decimal("0")
    assert cobros[TipoCobro.SALDO].estado is EstadoCobro.VENCIDO
    assert de_dinero(llamadas) == []
    foto = pasarela.inspeccionar_cobro(anticipo.referencia_pasarela)
    assert foto.monto_reembolsado == Decimal("0")


async def test_9_06_en_una_sola_vuelta_vence_y_cancela(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
    )
    vence = (await saldo_de(s, escena.pedido_id)).autorizado_hasta
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, vence + PLAZO)
    assert resumen.autorizaciones_vencidas == Conteo(1, 0)
    assert resumen.reautorizaciones_vencidas == Conteo(1, 0)
    assert await estado(s, escena.pedido_id) is EstadoPedido.CANCELADO
    assert "reembolsar" not in nombres(llamadas)


# 7. Pasado el plazo con un 3DS que el cliente si completo


async def test_9_07_3ds_completado_pasado_el_plazo_no_se_cancela(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela, momento
):
    s, http = sesion_api, cliente
    escena, vence = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )
    r = await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "requiere_accion", r.text
    referencia = (await saldo_de(s, escena.pedido_id)).referencia_pasarela
    limite = vence + PLAZO
    # El cliente vuelve del banco justo al vencer el plazo, sin abrir la app
    momento[0] = limite
    pasarela.completar_autenticacion(referencia, aprobada=True)
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, limite + UN_SEGUNDO)
    assert resumen.reautorizaciones_vencidas == Conteo(1, 0)
    assert await estado(s, escena.pedido_id) is EstadoPedido.VISTA_PREVIA_ENTREGADA
    saldo = await saldo_de(s, escena.pedido_id)
    assert saldo.estado is EstadoCobro.AUTORIZADO
    assert saldo.referencia_pasarela == referencia
    assert de_dinero(llamadas) == []


async def test_9_07_3ds_sin_completar_pasado_el_plazo_se_anula_y_cancela(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena, vence = await encargo_con_saldo_vencido(
        http, autenticar_como, s, pasarela, sesiones_prueba
    )
    await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_3DS)
    referencia = (await saldo_de(s, escena.pedido_id)).referencia_pasarela

    await barrido(sesiones_prueba, pasarela, vence + PLAZO)
    assert await estado(s, escena.pedido_id) is EstadoPedido.CANCELADO
    assert pasarela.inspeccionar_cobro(referencia).estado is EstadoOperacion.LIBERADO
    assert (await saldo_de(s, escena.pedido_id)).estado is EstadoCobro.CANCELADO


# 8. Obra disponible con el total vencido


async def test_9_08_obra_con_el_total_vencido_se_cancela_y_queda_libre(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    pieza, pedido_id, cuerpo = await la_quiero(http, autenticar_como, s, pasarela)
    assert cuerpo["pedido"]["estado"] == "en_proceso"
    total = (await cobros_db(s, pedido_id))[TipoCobro.TOTAL]
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, total.autorizado_hasta)
    assert resumen.autorizaciones_vencidas == Conteo(1, 0)
    assert await estado(s, pedido_id) is EstadoPedido.CANCELADO
    total = (await cobros_db(s, pedido_id))[TipoCobro.TOTAL]
    assert total.estado is EstadoCobro.VENCIDO
    assert de_dinero(llamadas) == ["liberar_autorizacion"]

    r = await otro_pide(http, autenticar_como, s, pieza.id)
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "completado"


# 9. Evento cuya fecha llego


async def test_9_09_evento_impago_se_cancela_y_el_anticipo_queda(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    _, pedido_id, fecha = await evento(http, autenticar_como, s, pasarela)
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, fecha - UN_SEGUNDO)
    assert resumen.eventos_impagos == NADA

    resumen = await barrido(sesiones_prueba, pasarela, fecha)
    assert resumen.eventos_impagos == Conteo(1, 0)
    assert await estado(s, pedido_id) is EstadoPedido.CANCELADO
    cobros = await cobros_db(s, pedido_id)
    assert cobros[TipoCobro.ANTICIPO].estado is EstadoCobro.CAPTURADO
    assert cobros[TipoCobro.ANTICIPO].monto_reembolsado == Decimal("0")
    assert cobros[TipoCobro.SALDO].estado is EstadoCobro.CANCELADO
    assert llamadas == []


async def test_9_09_evento_con_3ds_del_saldo_cobrado_queda_pagado(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    _, pedido_id, fecha = await evento(http, autenticar_como, s, pasarela)
    r = await pagar(http, pedido_id, "saldo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "requiere_accion", r.text
    referencia = (await saldo_de(s, pedido_id)).referencia_pasarela
    pasarela.completar_autenticacion(referencia, aprobada=True)

    resumen = await barrido(sesiones_prueba, pasarela, fecha)
    assert resumen.eventos_impagos == Conteo(1, 0)
    assert await estado(s, pedido_id) is EstadoPedido.SALDO_PAGADO
    assert (await saldo_de(s, pedido_id)).estado is EstadoCobro.CAPTURADO


async def test_9_09_evento_con_3ds_del_saldo_abandonado_se_anula(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    _, pedido_id, fecha = await evento(http, autenticar_como, s, pasarela)
    await pagar(http, pedido_id, "saldo", MEDIO_PAGO_3DS)
    referencia = (await saldo_de(s, pedido_id)).referencia_pasarela

    await barrido(sesiones_prueba, pasarela, fecha)
    assert await estado(s, pedido_id) is EstadoPedido.CANCELADO
    assert pasarela.inspeccionar_cobro(referencia).estado is EstadoOperacion.LIBERADO


# 10. Saldo de un evento en su fecha o despues


async def test_9_10_saldo_de_evento_en_su_fecha_da_409(
    cliente, autenticar_como, sesion_api, pasarela
):
    s, http = sesion_api, cliente
    _, pedido_id, _ = await evento(http, autenticar_como, s, pasarela)
    # La API usa la hora real: la fecha se corre al pasado
    (await pedido_db(s, pedido_id)).fecha_evento = datetime.now(UTC) - UN_SEGUNDO
    await s.commit()
    llamadas = espiar(pasarela)

    r = await pagar(http, pedido_id, "saldo")
    assert r.status_code == 409, r.text
    assert llamadas == []
    assert await estado(s, pedido_id) is EstadoPedido.ANTICIPO_PAGADO


# 11. DT25: La quiero con el 3DS abandonado


async def test_9_11_la_quiero_abandonado_suelta_la_obra(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    pieza, pedido_id, cuerpo = await la_quiero(
        http, autenticar_como, s, pasarela, MEDIO_PAGO_3DS
    )
    assert cuerpo["resultado"] == "requiere_accion"
    creado = (await pedido_db(s, pedido_id)).created_at
    referencia = (await cobros_db(s, pedido_id))[TipoCobro.TOTAL].referencia_pasarela
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, creado + ABANDONO - UN_SEGUNDO)
    assert resumen.la_quiero_abandonados == NADA
    assert llamadas == []
    assert await estado(s, pedido_id) is EstadoPedido.COTIZADO

    resumen = await barrido(sesiones_prueba, pasarela, creado + ABANDONO)
    assert resumen.la_quiero_abandonados == Conteo(1, 0)
    assert nombres(llamadas) == ["consultar_cobro", "liberar_autorizacion"]
    assert await estado(s, pedido_id) is EstadoPedido.RECHAZADO
    foto = await pasarela.consultar_cobro(referencia)
    assert foto.estado is EstadoCobroPasarela.LIBERADO

    r = await otro_pide(http, autenticar_como, s, pieza.id)
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "completado"


async def test_9_11_la_quiero_con_3ds_aprobado_antes_del_barrido_sigue(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    _, pedido_id, _ = await la_quiero(
        http, autenticar_como, s, pasarela, MEDIO_PAGO_3DS
    )
    creado = (await pedido_db(s, pedido_id)).created_at
    referencia = (await cobros_db(s, pedido_id))[TipoCobro.TOTAL].referencia_pasarela
    pasarela.completar_autenticacion(referencia, aprobada=True)
    llamadas = espiar(pasarela)

    resumen = await barrido(sesiones_prueba, pasarela, creado + ABANDONO)
    assert resumen.la_quiero_abandonados == Conteo(1, 0)
    assert await estado(s, pedido_id) is EstadoPedido.EN_PROCESO
    total = (await cobros_db(s, pedido_id))[TipoCobro.TOTAL]
    assert total.estado is EstadoCobro.AUTORIZADO
    assert de_dinero(llamadas) == []


# 12. requiere_accion sin URL


async def test_9_12_requiere_accion_sin_url_responde_pendiente(
    cliente, autenticar_como, sesion_api, pasarela
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela)
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    cobro_id = r.json()["cobro"]["id"]
    original = pasarela.consultar_cobro

    async def sin_url(referencia):
        foto = await original(referencia)
        return dataclasses.replace(foto, url_autenticacion=None)

    pasarela.consultar_cobro = sin_url

    r = await http.post(ruta_verificar(cobro_id))
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "pendiente"
    assert r.json()["url_autenticacion"] is None
    assert r.json()["cobro"]["esperando_autenticacion"] is True

    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "pendiente", r.text
    assert r.json()["url_autenticacion"] is None


# 13. Idempotencia


async def test_9_13_dos_barridos_seguidos_dan_lo_mismo(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    reautorizar = await encargo(
        http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
    )
    pagado = await encargo(http, autenticar_como, s, pasarela, hasta="saldo_pagado")
    _, obra_vencida, _ = await la_quiero(http, autenticar_como, s, pasarela)
    _, abandonada, _ = await la_quiero(
        http, autenticar_como, s, pasarela, MEDIO_PAGO_3DS
    )
    _, impago, _ = await evento(http, autenticar_como, s, pasarela)
    ids = [
        reautorizar.pedido_id,
        pagado.pedido_id,
        obra_vencida,
        abandonada,
        impago,
    ]
    ahora = datetime.now(UTC) + timedelta(days=30)

    async def foto():
        return [
            (
                await estado(s, i),
                sorted((c.tipo, c.estado) for c in (await cobros_db(s, i)).values()),
            )
            for i in ids
        ]

    primero = await barrido(sesiones_prueba, pasarela, ahora)
    despues_del_primero = await foto()
    assert [e for e, _ in despues_del_primero] == [
        EstadoPedido.CANCELADO,
        EstadoPedido.COMPLETADO,
        EstadoPedido.CANCELADO,
        EstadoPedido.RECHAZADO,
        EstadoPedido.CANCELADO,
    ]
    assert primero.la_quiero_abandonados == Conteo(1, 0)
    assert primero.autorizaciones_vencidas == Conteo(2, 0)
    assert primero.reautorizaciones_vencidas == Conteo(1, 0)
    assert primero.eventos_impagos == Conteo(1, 0)
    assert primero.completados == Conteo(1, 0)

    llamadas = espiar(pasarela)
    segundo = await barrido(sesiones_prueba, pasarela, ahora)
    assert await foto() == despues_del_primero
    assert segundo.vacio
    assert llamadas == []


# 14. Aislamiento


async def test_9_14_una_falla_no_frena_a_los_demas(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escenas = [
        await encargo(
            http, autenticar_como, s, pasarela, hasta="vista_previa_entregada"
        )
        for _ in range(2)
    ]
    ahora = max([(await saldo_de(s, e.pedido_id)).autorizado_hasta for e in escenas])
    pasarela.programar_falla("consultar_cobro", PasarelaNoDisponible("caida"))

    resumen = await barrido(sesiones_prueba, pasarela, ahora)
    assert resumen.autorizaciones_vencidas == Conteo(1, 1)
    saldos = [await saldo_de(s, e.pedido_id) for e in escenas]
    assert sorted(x.estado for x in saldos) == [
        EstadoCobro.AUTORIZADO,
        EstadoCobro.VENCIDO,
    ]
    fallido = next(x for x in saldos if x.estado is EstadoCobro.AUTORIZADO)
    foto = pasarela.inspeccionar_cobro(fallido.referencia_pasarela)
    assert foto.estado is EstadoOperacion.AUTORIZADO
    for e in escenas:
        assert await estado(s, e.pedido_id) is EstadoPedido.VISTA_PREVIA_ENTREGADA

    # La vuelta siguiente lo resuelve
    resumen = await barrido(sesiones_prueba, pasarela, ahora)
    assert resumen.autorizaciones_vencidas == Conteo(1, 0)


# 15. Completar los vencidos


async def test_9_15_barrer_completa_los_saldo_pagado_vencidos(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela, hasta="saldo_pagado")
    hasta = (await pedido_db(s, escena.pedido_id)).disputable_hasta

    resumen = await barrido(sesiones_prueba, pasarela, hasta)
    assert resumen.completados == NADA
    assert await estado(s, escena.pedido_id) is EstadoPedido.SALDO_PAGADO

    resumen = await barrido(sesiones_prueba, pasarela, hasta + UN_SEGUNDO)
    assert resumen.completados == Conteo(1, 0)
    assert await estado(s, escena.pedido_id) is EstadoPedido.COMPLETADO
