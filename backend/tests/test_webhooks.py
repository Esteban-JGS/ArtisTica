"""Webhooks de la pasarela por la API, contra una base migrada, la pasarela
falsa y el adaptador de ONVO con su transporte simulado. Cada prueba termina en
rollback.

Todo webhook se manda con `enviar`, que verifica la prueba 28: al procesarlo,
la pasarela solo recibe `consultar_cobro`.
"""

import asyncio
import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.api.deps import get_pasarela
from src.api.v1 import pagos as api_pagos
from src.main import app
from src.models import (
    Cobro,
    EstadoCobro,
    EstadoObra,
    EstadoPedido,
    EventoPasarela,
    Obra,
    RolPerfil,
    TipoCobro,
)
from src.payments import onvo
from src.payments.contrato import MetodoPago, SolicitudCobro, TipoEvento
from src.payments.errores import PasarelaNoDisponible
from src.payments.falsa import MEDIO_PAGO_3DS
from src.services import contratacion
from src.services.contratacion import ResultadoConciliacion
from src.tareas.barrido import Conteo, barrer
from tests.test_ledger import filas_ledger
from tests.test_pasarela_onvo import (
    ACTUALIZADO,
    SECRETO_WEBHOOK,
    Simulador,
    configuracion,
    responder,
)
from tests.test_pedidos_api import (
    API,
    POLITICAS,
    TARJETA,
    cobros_db,
    encargo,
    pagar,
    pedido_db,
    perfil,
)
from tests.test_vencimientos import la_quiero, otro_pide

RUTA_WEBHOOK = f"{API}/pagos/webhook"
RUTA_EVENTOS = f"{API}/moderacion/pagos/eventos"
OPERACIONES = (
    "cobrar",
    "autorizar",
    "capturar",
    "liberar_autorizacion",
    "reembolsar",
    "configurar_tarifa",
    "consultar_cobro",
)
CAMPOS_EVENTO = {
    "id",
    "proveedor",
    "tipo",
    "intentos",
    "error",
    "procesado_en",
    "created_at",
}


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


@contextmanager
def anotar(pasarela) -> Iterator[list[str]]:
    """Anota cada operacion de dinero o consulta, y al salir la deja como
    estaba."""
    llamadas: list[str] = []
    originales = {nombre: getattr(pasarela, nombre) for nombre in OPERACIONES}
    for nombre, original in originales.items():

        async def envuelta(*args, _nombre=nombre, _original=original, **kwargs):
            llamadas.append(_nombre)
            return await _original(*args, **kwargs)

        setattr(pasarela, nombre, envuelta)
    try:
        yield llamadas
    finally:
        for nombre, original in originales.items():
            setattr(pasarela, nombre, original)


async def enviar(http, pasarela, cuerpo: bytes, encabezados: dict[str, str]):
    """Manda el webhook. Prueba 28: procesarlo solo consulta la pasarela."""
    with anotar(pasarela) as llamadas:
        r = await http.post(RUTA_WEBHOOK, content=cuerpo, headers=encabezados)
    assert set(llamadas) <= {"consultar_cobro"}, llamadas
    return r, llamadas


def evento_falso(pasarela, tipo: str, referencia: str | None):
    """Cuerpo, encabezados firmados e id externo de un evento de la falsa."""
    cuerpo, encabezados = pasarela.construir_evento(tipo, referencia=referencia)
    return cuerpo, encabezados, json.loads(cuerpo)["id"]


async def evento_db(
    s, evento_externo_id: str, proveedor: str = "falsa"
) -> EventoPasarela | None:
    filas = await s.execute(
        select(EventoPasarela)
        .where(
            EventoPasarela.proveedor == proveedor,
            EventoPasarela.evento_externo_id == evento_externo_id,
        )
        .execution_options(populate_existing=True)
    )
    return filas.scalar_one_or_none()


async def anticipo_con_3ds(http, autenticar_como, s, pasarela):
    """Encargo cotizado con el anticipo esperando el 3DS. Devuelve la escena y
    el anticipo."""
    escena = await encargo(http, autenticar_como, s, pasarela)
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "anticipo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "requiere_accion", r.text
    return escena, (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]


# 1. 3DS completado sin volver a la app


async def test_9b_01_3ds_completado_sin_volver_a_la_app(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    pasarela_falsa.completar_autenticacion(anticipo.referencia_pasarela, aprobada=True)
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", anticipo.referencia_pasarela
    )

    r, llamadas = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 200, r.text
    assert r.json() == {"estado": "recibido"}
    assert llamadas == ["consultar_cobro"]
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.CAPTURADO
    pedido = await pedido_db(s, escena.pedido_id)
    assert pedido.estado is EstadoPedido.ANTICIPO_PAGADO
    assert len(await filas_ledger(s, escena.pedido_id)) == 1
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is not None
    assert evento.error is None
    assert evento.tipo == TipoEvento.COBRO_CAPTURADO


# 2. El mismo evento dos veces


async def test_9b_02_evento_repetido_se_procesa_una_vez(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    _, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    pasarela_falsa.completar_autenticacion(anticipo.referencia_pasarela, aprobada=True)
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", anticipo.referencia_pasarela
    )

    primero, consultas_1 = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    segundo, consultas_2 = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert primero.json() == {"estado": "recibido"}
    assert segundo.status_code == 200, segundo.text
    assert segundo.json() == {"estado": "repetido"}
    assert consultas_1 + consultas_2 == ["consultar_cobro"]
    cuantos = await s.execute(
        select(func.count())
        .select_from(EventoPasarela)
        .where(EventoPasarela.evento_externo_id == evento_id)
    )
    assert cuantos.scalar() == 1


# 3. Firma invalida


async def test_9b_03_firma_invalida_da_401_y_no_guarda(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    _, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", anticipo.referencia_pasarela
    )
    encabezados = dict.fromkeys(encabezados, "0" * 64)

    r, llamadas = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 401, r.text
    assert llamadas == []
    assert await evento_db(s, evento_id) is None

    r, _ = await enviar(http, pasarela_falsa, cuerpo, {})
    assert r.status_code == 401, r.text


# 4. El webhook dice capturado y la pasarela sigue esperando el 3DS


async def test_9b_04_webhook_no_se_cree_sin_la_pasarela(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    referencia = anticipo.referencia_pasarela
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", referencia
    )

    r, llamadas = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.json() == {"estado": "recibido"}
    assert llamadas == ["consultar_cobro"]
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.PENDIENTE
    assert anticipo.referencia_pasarela == referencia
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.COTIZADO
    assert await filas_ledger(s, escena.pedido_id) == []
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is not None
    assert evento.error is None

    conciliacion = await contratacion.conciliar_cobro(
        s, pasarela_falsa, referencia, ahora=datetime.now(UTC), politicas=POLITICAS
    )
    assert conciliacion.resultado is ResultadoConciliacion.SIN_CAMBIOS


# 5. La quiero con el 3DS rechazado


async def test_9b_05_la_quiero_con_3ds_rechazado_suelta_la_obra(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    pieza, pedido_id, _ = await la_quiero(
        http, autenticar_como, s, pasarela_falsa, MEDIO_PAGO_3DS
    )
    referencia = (await cobros_db(s, pedido_id))[TipoCobro.TOTAL].referencia_pasarela
    pasarela_falsa.completar_autenticacion(referencia, aprobada=False)
    cuerpo, encabezados, _ = evento_falso(pasarela_falsa, "cobro_fallido", referencia)

    r, _ = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 200, r.text
    assert (await pedido_db(s, pedido_id)).estado is EstadoPedido.RECHAZADO
    obra = await s.get(Obra, pieza.id, populate_existing=True)
    assert obra.estado is EstadoObra.DISPONIBLE
    r = await otro_pide(http, autenticar_como, s, pieza.id)
    assert r.status_code == 201, r.text


# 6. Referencia desconocida


async def test_9b_06_referencia_desconocida_sin_dinero_queda_sin_cobro(
    cliente, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", "cobro_que_no_existe"
    )

    r, _ = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.json() == {"estado": "recibido"}
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is not None
    assert evento.intentos == 0
    assert "no conoce" in evento.error


async def test_9b_06_referencia_desconocida_con_dinero_es_discrepancia(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    # Un cobro de la pasarela con nuestro cobro en los metadatos y sin registro
    huerfano = await pasarela_falsa.cobrar(
        SolicitudCobro(
            monto=anticipo.monto,
            metodo=MetodoPago.TARJETA,
            cuenta_conectada_id=escena.artista.pasarela_cuenta_id,
            clave_idempotencia="sin-registro",
            metadatos={
                "pedido_id": str(escena.pedido_id),
                "cobro_id": str(anticipo.id),
            },
            medio_pago_id=TARJETA,
        )
    )
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", huerfano.referencia
    )

    r, _ = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 200, r.text
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is not None
    assert str(anticipo.id) in evento.error
    assert "no esta registrado" in evento.error
    assert huerfano.referencia not in evento.error
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.PENDIENTE
    assert anticipo.referencia_pasarela is None


# 7. Discrepancia


async def test_9b_07_reembolso_por_fuera_es_discrepancia_sin_cambios(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="anticipo_pagado"
    )
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    referencia = anticipo.referencia_pasarela
    await pasarela_falsa.reembolsar(
        referencia, monto=Decimal("1000.00"), clave_idempotencia="por-fuera"
    )
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "reembolso_confirmado", referencia
    )

    r, llamadas = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 200, r.text
    assert llamadas == ["consultar_cobro"]
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is not None
    assert str(anticipo.id) in evento.error
    assert referencia not in evento.error
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.CAPTURADO
    assert anticipo.monto_reembolsado == 0
    assert len(await filas_ledger(s, escena.pedido_id)) == 1


# 8. Falla al procesar


async def test_9b_08_falla_al_procesar_responde_200_y_el_barrido_reintenta(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    pasarela_falsa.completar_autenticacion(anticipo.referencia_pasarela, aprobada=True)
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", anticipo.referencia_pasarela
    )
    pasarela_falsa.programar_falla("consultar_cobro", PasarelaNoDisponible("caida"))

    r, _ = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 200, r.text
    assert r.json() == {"estado": "recibido"}
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is None
    assert evento.intentos == 1
    assert evento.error == "PasarelaNoDisponible"
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.COTIZADO

    with anotar(pasarela_falsa) as llamadas:
        resumen = await barrer(
            sesiones_prueba,
            pasarela_falsa,
            ahora=evento.created_at + timedelta(minutes=1),
            politicas=POLITICAS,
        )
    assert llamadas == ["consultar_cobro"]
    assert resumen.eventos_pendientes == Conteo(1, 0)
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is not None
    assert evento.error is None
    assert evento.intentos == 1
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.ANTICIPO_PAGADO


# 9 y 10. Intentos agotados y moderacion


async def test_9b_09_intentos_agotados_quedan_para_moderacion(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela_falsa
):
    s, http = sesion_api, cliente
    _, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", anticipo.referencia_pasarela
    )
    pasarela_falsa.programar_falla("consultar_cobro", PasarelaNoDisponible("caida"))
    await enviar(http, pasarela_falsa, cuerpo, encabezados)
    evento = await evento_db(s, evento_id)
    evento.intentos = 5
    await s.flush()

    with anotar(pasarela_falsa) as llamadas:
        resumen = await barrer(
            sesiones_prueba,
            pasarela_falsa,
            ahora=evento.created_at + timedelta(minutes=5),
            politicas=POLITICAS,
        )
    assert resumen.eventos_pendientes == Conteo()
    assert llamadas == []
    assert (await evento_db(s, evento_id)).procesado_en is None

    autenticar_como((await perfil(s, RolPerfil.ADMIN)).id)
    r = await http.get(RUTA_EVENTOS)
    assert r.status_code == 200, r.text
    [item] = [i for i in r.json()["items"] if i["id"] == str(evento.id)]
    assert item["intentos"] == 5
    assert item["error"] == "PasarelaNoDisponible"
    assert item["procesado_en"] is None


async def test_9b_10_moderacion_de_eventos_solo_admin_y_sin_datos_de_pasarela(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="anticipo_pagado"
    )
    referencia = (await cobros_db(s, escena.pedido_id))[
        TipoCobro.ANTICIPO
    ].referencia_pasarela
    await pasarela_falsa.reembolsar(
        referencia, monto=Decimal("1000.00"), clave_idempotencia="por-fuera"
    )
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "reembolso_confirmado", referencia
    )
    await enviar(http, pasarela_falsa, cuerpo, encabezados)

    for rol in (RolPerfil.PUBLICO, RolPerfil.ARTISTA):
        autenticar_como((await perfil(s, rol)).id)
        assert (await http.get(RUTA_EVENTOS)).status_code == 403
    autenticar_como(escena.comprador.id)
    assert (await http.get(RUTA_EVENTOS)).status_code == 403

    autenticar_como((await perfil(s, RolPerfil.ADMIN)).id)
    r = await http.get(RUTA_EVENTOS, params={"tamano": 50})
    assert r.status_code == 200, r.text
    assert r.json()["items"]
    for item in r.json()["items"]:
        assert set(item) == CAMPOS_EVENTO
    assert referencia not in r.text
    assert evento_id not in r.text
    assert "payload" not in r.text
    evento = await evento_db(s, evento_id)
    assert str(evento.id) in {i["id"] for i in r.json()["items"]}


# 11. Tipo desconocido o sin referencia


async def test_9b_11_tipo_desconocido_o_sin_referencia_no_consulta(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    _, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    casos = (
        ("algo_nuevo", anticipo.referencia_pasarela),
        ("cuenta_actualizada", anticipo.referencia_pasarela),
        ("cobro_capturado", None),
    )
    for tipo, referencia in casos:
        cuerpo, encabezados, evento_id = evento_falso(pasarela_falsa, tipo, referencia)
        r, llamadas = await enviar(http, pasarela_falsa, cuerpo, encabezados)
        assert r.json() == {"estado": "recibido"}, tipo
        assert llamadas == [], tipo
        evento = await evento_db(s, evento_id)
        assert evento.procesado_en is not None, tipo
        assert evento.error is None, tipo
    assert (await evento_db(s, evento_id)).tipo == TipoEvento.COBRO_CAPTURADO


# 24 a 26. Adaptador de ONVO con su transporte simulado


def evento_onvo(referencia: str, tipo: str = "payment-intent.succeeded") -> bytes:
    return json.dumps(
        {"type": tipo, "data": {"id": referencia, "updatedAt": ACTUALIZADO}}
    ).encode()


def intencion_onvo(referencia: str, monto: Decimal, estado: str = "succeeded") -> dict:
    centimos = onvo.a_unidad_menor(monto)
    return {
        "id": referencia,
        "status": estado,
        "amount": centimos,
        "capturableAmount": 0,
        "receivedAmount": centimos,
        "currency": "CRC",
        "updatedAt": ACTUALIZADO,
    }


@pytest.fixture
def con_onvo():
    """Pone un adaptador de ONVO como pasarela de la API."""

    def _con(simulador: Simulador, config=None):
        pasarela = simulador.pasarela(config)
        app.dependency_overrides[get_pasarela] = lambda: pasarela
        return pasarela

    return _con


async def anticipo_con_referencia_onvo(http, autenticar_como, s, pasarela_falsa):
    """Encargo cotizado con el anticipo esperando el 3DS de una intencion de
    ONVO, puesta directo en la base."""
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    referencia = f"pi_{uuid.uuid4().hex[:16]}"
    anticipo.referencia_pasarela = referencia
    await s.flush()
    return escena, anticipo, referencia


async def test_9b_24_evento_de_onvo_de_punta_a_punta(
    cliente, autenticar_como, sesion_api, pasarela_falsa, con_onvo
):
    s, http = sesion_api, cliente
    escena, anticipo, referencia = await anticipo_con_referencia_onvo(
        http, autenticar_como, s, pasarela_falsa
    )
    ruta_intencion = onvo.RUTA_INTENCION.format(id=referencia)
    simulador = Simulador(
        {
            ("GET", ruta_intencion): responder(
                200, intencion_onvo(referencia, anticipo.monto)
            )
        }
    )
    pasarela = con_onvo(simulador)

    r, llamadas = await enviar(
        http,
        pasarela,
        evento_onvo(referencia),
        {onvo.ENCABEZADO_WEBHOOK: SECRETO_WEBHOOK},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"estado": "recibido"}
    assert llamadas == ["consultar_cobro"]
    assert [(q.method, q.url.path) for q in simulador.solicitudes] == [
        ("GET", ruta_intencion)
    ]
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.CAPTURADO
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.ANTICIPO_PAGADO
    evento = await evento_db(
        s, f"payment-intent.succeeded:{referencia}:{ACTUALIZADO}", "onvo"
    )
    assert evento.procesado_en is not None
    assert evento.error is None
    assert evento.referencia == referencia


async def test_9b_25_onvo_sin_secreto_o_con_otro_no_guarda(
    cliente, autenticar_como, sesion_api, pasarela_falsa, con_onvo
):
    s, http = sesion_api, cliente
    _, _, referencia = await anticipo_con_referencia_onvo(
        http, autenticar_como, s, pasarela_falsa
    )
    evento_id = f"payment-intent.succeeded:{referencia}:{ACTUALIZADO}"

    simulador = Simulador({})
    pasarela = con_onvo(simulador)
    r, _ = await enviar(
        http, pasarela, evento_onvo(referencia), {onvo.ENCABEZADO_WEBHOOK: "otro"}
    )
    assert r.status_code == 401, r.text

    pasarela = con_onvo(simulador, configuracion(WEBHOOK_SECRET=None))
    r, _ = await enviar(
        http,
        pasarela,
        evento_onvo(referencia),
        {onvo.ENCABEZADO_WEBHOOK: SECRETO_WEBHOOK},
    )
    assert r.status_code == 503, r.text
    assert simulador.solicitudes == []
    assert await evento_db(s, evento_id, "onvo") is None


async def test_9b_26_onvo_con_otro_monto_no_registra(
    cliente, autenticar_como, sesion_api, pasarela_falsa, con_onvo
):
    s, http = sesion_api, cliente
    escena, anticipo, referencia = await anticipo_con_referencia_onvo(
        http, autenticar_como, s, pasarela_falsa
    )
    otro_monto = anticipo.monto + Decimal("1.00")
    simulador = Simulador(
        {
            ("GET", onvo.RUTA_INTENCION.format(id=referencia)): responder(
                200, intencion_onvo(referencia, otro_monto)
            )
        }
    )
    pasarela = con_onvo(simulador)

    r, _ = await enviar(
        http,
        pasarela,
        evento_onvo(referencia),
        {onvo.ENCABEZADO_WEBHOOK: SECRETO_WEBHOOK},
    )
    assert r.status_code == 200, r.text
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.PENDIENTE
    assert anticipo.referencia_pasarela == referencia
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.COTIZADO
    assert await filas_ledger(s, escena.pedido_id) == []
    evento = await evento_db(
        s, f"payment-intent.succeeded:{referencia}:{ACTUALIZADO}", "onvo"
    )
    assert evento.error is not None
    assert str(anticipo.id) in evento.error
    assert referencia not in evento.error


# 27. Barrido como respaldo


async def test_9b_27_barrido_registra_el_3ds_sin_webhook(
    cliente, autenticar_como, sesion_api, sesiones_prueba, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="con_vista_previa"
    )
    autenticar_como(escena.comprador.id)
    r = await pagar(http, escena.pedido_id, "saldo", MEDIO_PAGO_3DS)
    assert r.json()["resultado"] == "requiere_accion", r.text
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    pasarela_falsa.completar_autenticacion(saldo.referencia_pasarela, aprobada=True)
    desde = saldo.updated_at

    with anotar(pasarela_falsa) as llamadas:
        resumen = await barrer(
            sesiones_prueba,
            pasarela_falsa,
            ahora=desde + timedelta(minutes=10),
            politicas=POLITICAS,
        )
    assert resumen.intentos_en_espera == Conteo()
    assert llamadas == []
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.PENDIENTE

    with anotar(pasarela_falsa) as llamadas:
        resumen = await barrer(
            sesiones_prueba,
            pasarela_falsa,
            ahora=desde + timedelta(minutes=31),
            politicas=POLITICAS,
        )
    assert resumen.intentos_en_espera == Conteo(1, 0)
    assert llamadas == ["consultar_cobro"]
    saldo = (await cobros_db(s, escena.pedido_id))[TipoCobro.SALDO]
    assert saldo.estado is EstadoCobro.AUTORIZADO
    assert (
        await pedido_db(s, escena.pedido_id)
    ).estado is EstadoPedido.VISTA_PREVIA_ENTREGADA


# 28. Procesar un webhook solo consulta


async def test_9b_28_procesar_solo_consulta_la_pasarela(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    _, aprobado = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    pasarela_falsa.completar_autenticacion(aprobado.referencia_pasarela, aprobada=True)
    _, rechazado = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    pasarela_falsa.completar_autenticacion(
        rechazado.referencia_pasarela, aprobada=False
    )
    _, en_espera = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    casos = (
        ("cobro_capturado", aprobado.referencia_pasarela),
        ("cobro_fallido", rechazado.referencia_pasarela),
        ("cobro_autorizado", en_espera.referencia_pasarela),
        ("autorizacion_vencida", en_espera.referencia_pasarela),
        ("reembolso_confirmado", "cobro_que_no_existe"),
    )
    for tipo, referencia in casos:
        cuerpo, encabezados, _ = evento_falso(pasarela_falsa, tipo, referencia)
        # `enviar` falla si la pasarela recibe otra cosa que consultar_cobro
        r, llamadas = await enviar(http, pasarela_falsa, cuerpo, encabezados)
        assert r.json() == {"estado": "recibido"}, tipo
        assert llamadas == ["consultar_cobro"], tipo
    rechazado = await s.get(Cobro, rechazado.id, populate_existing=True)
    assert rechazado.estado is EstadoCobro.PENDIENTE
    assert rechazado.intentos == 1
    assert rechazado.referencia_pasarela is None


# 29. Tiempo maximo


async def test_9b_29_procesar_que_se_pasa_del_tiempo_queda_para_el_barrido(
    cliente, autenticar_como, sesion_api, pasarela_falsa, monkeypatch
):
    s, http = sesion_api, cliente
    escena, anticipo = await anticipo_con_3ds(http, autenticar_como, s, pasarela_falsa)
    pasarela_falsa.completar_autenticacion(anticipo.referencia_pasarela, aprobada=True)
    cuerpo, encabezados, evento_id = evento_falso(
        pasarela_falsa, "cobro_capturado", anticipo.referencia_pasarela
    )
    monkeypatch.setattr(api_pagos, "TIEMPO_MAXIMO_PROCESO_SEGUNDOS", 0.05)
    original = pasarela_falsa.consultar_cobro

    async def lenta(referencia):
        await asyncio.sleep(1)
        return await original(referencia)

    pasarela_falsa.consultar_cobro = lenta

    r, _ = await enviar(http, pasarela_falsa, cuerpo, encabezados)
    assert r.status_code == 200, r.text
    assert r.json() == {"estado": "recibido"}
    evento = await evento_db(s, evento_id)
    assert evento.procesado_en is None
    assert evento.intentos == 1
    assert evento.error == "TimeoutError"
    anticipo = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO]
    assert anticipo.estado is EstadoCobro.PENDIENTE
    assert (await pedido_db(s, escena.pedido_id)).estado is EstadoPedido.COTIZADO
