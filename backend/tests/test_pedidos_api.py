"""Pedidos de punta a punta por la API, contra una base migrada y la pasarela
falsa. Cada prueba termina en rollback.

Las ayudas sin prefijo `test_` las reusa `test_cobros_api.py`.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from src.core.config import settings
from src.domain.politicas import PoliticasPedido
from src.models import (
    Cobro,
    Consulta,
    EstadoConsulta,
    EstadoMedia,
    EstadoObra,
    EstadoOnboarding,
    MediaAsset,
    Obra,
    Pedido,
    PlanArtista,
    Profile,
    RolPerfil,
    TipoCobro,
    TipoPedido,
)
from src.payments.contrato import EstadoOperacion
from src.services import pedidos as servicio_pedidos

API = settings.API_V1_STR
POLITICAS = PoliticasPedido.desde_config(settings)
TARJETA = "tarjeta_de_prueba"
OTRA_TARJETA = "otra_tarjeta_de_prueba"
VENTANA = timedelta(days=settings.DIAS_VENTANA_DISPUTA)


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    """Cliente HTTP con la base, la pasarela y el almacenamiento de prueba."""
    return async_client


# Fabricas


async def perfil(sesion_api, rol=RolPerfil.PUBLICO) -> Profile:
    nuevo = Profile(
        id=uuid.uuid4(),
        handle=f"u{uuid.uuid4().hex[:12]}",
        nombre="Prueba",
        rol=rol,
        plan=PlanArtista.TALLER,
        categorias=[],
    )
    sesion_api.add(nuevo)
    await sesion_api.flush()
    return nuevo


async def artista(
    sesion_api, pasarela, *, habilitado=True, tarifa_cuenta=Decimal("8")
) -> Profile:
    """Artista con la cuenta conectada y el onboarding completado, salvo que no."""
    nuevo = await perfil(sesion_api, RolPerfil.ARTISTA)
    if habilitado:
        cuenta = await pasarela.crear_cuenta_conectada(
            nombre=nuevo.nombre,
            tarifa_porcentaje=tarifa_cuenta,
            clave_idempotencia=f"cuenta-{nuevo.id}",
        )
        pasarela.completar_onboarding(cuenta.id)
        nuevo.pasarela_cuenta_id = cuenta.id
        nuevo.pasarela_onboarding = EstadoOnboarding.COMPLETADO
        nuevo.is_verified = True
        await sesion_api.flush()
    return nuevo


async def consulta(sesion_api, comprador, artista_) -> Consulta:
    nueva = Consulta(
        id=uuid.uuid4(),
        cliente_id=comprador.id,
        artista_id=artista_.id,
        estado=EstadoConsulta.ABIERTA,
    )
    sesion_api.add(nueva)
    await sesion_api.flush()
    return nueva


async def medio(sesion_api, propietario) -> MediaAsset:
    nuevo = MediaAsset(
        id=uuid.uuid4(),
        propietario_id=propietario.id,
        tipo="imagen",
        storage_path=f"{propietario.id}/{uuid.uuid4()}.jpg",
        estado=EstadoMedia.PROCESADO,
        content_type="image/jpeg",
        subido_en=datetime.now(UTC),
    )
    sesion_api.add(nuevo)
    await sesion_api.flush()
    return nuevo


async def obra(sesion_api, artista_, precio=Decimal("15000.00")) -> Obra:
    nueva = Obra(
        id=uuid.uuid4(),
        artista_id=artista_.id,
        titulo="Colibri en acuarela",
        estado=EstadoObra.DISPONIBLE,
        precio=precio,
    )
    sesion_api.add(nueva)
    await sesion_api.flush()
    return nueva


async def pedido_db(sesion_api, pedido_id) -> Pedido:
    return await sesion_api.get(
        Pedido, uuid.UUID(str(pedido_id)), populate_existing=True
    )


async def cobros_db(sesion_api, pedido_id) -> dict[TipoCobro, Cobro]:
    filas = await sesion_api.execute(
        select(Cobro)
        .where(Cobro.pedido_id == uuid.UUID(str(pedido_id)))
        .execution_options(populate_existing=True)
    )
    return {c.tipo: c for c in filas.scalars()}


def cobro_de(cuerpo: dict, tipo: str) -> dict:
    return next(c for c in cuerpo["cobros"] if c["tipo"] == tipo)


# Rutas


def ruta(pedido_id, accion: str = "") -> str:
    return f"{API}/pedidos/{pedido_id}{accion}"


def ruta_verificar(cobro_id) -> str:
    return f"{API}/cobros/{cobro_id}/verificar"


def ruta_la_quiero(obra_id) -> str:
    return f"{API}/obras/{obra_id}/la-quiero"


async def cotizar(http, consulta_id, **cambios):
    datos = {
        "tipo": "encargo",
        "descripcion": "Retrato de mascota",
        "monto_total": "20000.00",
        "anticipo_porcentaje": "40",
    }
    datos.update(cambios)
    return await http.post(f"{API}/consultas/{consulta_id}/cotizacion", json=datos)


async def pagar(http, pedido_id, hito: str, metodo=TARJETA):
    return await http.post(ruta(pedido_id, f"/{hito}"), json={"metodo_pago_id": metodo})


# Escenas


@dataclass
class Escena:
    artista: Profile
    comprador: Profile
    consulta_id: uuid.UUID
    pedido_id: uuid.UUID


PASOS_ENCARGO = (
    "cotizado",
    "anticipo_pagado",
    "en_proceso",
    "con_vista_previa",
    "vista_previa_entregada",
    "saldo_pagado",
)


async def encargo(
    http,
    autenticar_como,
    sesion_api,
    pasarela,
    *,
    hasta="cotizado",
    artista_=None,
    comprador_=None,
) -> Escena:
    """Un encargo recorrido por la API hasta el paso pedido."""
    pasos = PASOS_ENCARGO[: PASOS_ENCARGO.index(hasta) + 1]
    artista_ = artista_ or await artista(sesion_api, pasarela)
    comprador = comprador_ or await perfil(sesion_api)
    consulta_ = await consulta(sesion_api, comprador, artista_)
    autenticar_como(artista_.id)
    r = await cotizar(http, consulta_.id)
    assert r.status_code == 201, r.text
    escena = Escena(artista_, comprador, consulta_.id, uuid.UUID(r.json()["id"]))

    if "anticipo_pagado" in pasos:
        autenticar_como(comprador.id)
        r = await pagar(http, escena.pedido_id, "anticipo")
        assert r.json()["resultado"] == "completado", r.text
    if "en_proceso" in pasos:
        autenticar_como(artista_.id)
        assert (await http.post(ruta(escena.pedido_id, "/iniciar"))).status_code == 200
    if "con_vista_previa" in pasos:
        imagen = await medio(sesion_api, artista_)
        r = await http.post(
            ruta(escena.pedido_id, "/vistas-previas"), json={"medio_id": str(imagen.id)}
        )
        assert r.status_code == 201, r.text
    if "vista_previa_entregada" in pasos:
        autenticar_como(comprador.id)
        r = await pagar(http, escena.pedido_id, "saldo")
        assert r.json()["resultado"] == "completado", r.text
    if "saldo_pagado" in pasos:
        autenticar_como(comprador.id)
        r = await http.post(ruta(escena.pedido_id, "/aprobar"))
        assert r.status_code == 200, r.text
    return escena


# 4. Encargo completo


async def test_8b_04_encargo_completo(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    artista_ = await artista(s, pasarela_falsa, tarifa_cuenta=Decimal("5"))
    comprador = await perfil(s)
    consulta_ = await consulta(s, comprador, artista_)

    autenticar_como(artista_.id)
    r = await cotizar(http, consulta_.id)
    assert r.status_code == 201, r.text
    pedido = r.json()
    pedido_id = pedido["id"]
    assert pedido["estado"] == "cotizado"
    assert pedido["soy"] == "artista"
    assert Decimal(cobro_de(pedido, "anticipo")["monto"]) == Decimal("8000.00")
    assert Decimal(cobro_de(pedido, "saldo")["monto"]) == Decimal("12000.00")

    autenticar_como(comprador.id)
    r = await pagar(http, pedido_id, "anticipo")
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "completado"
    assert r.json()["pedido"]["estado"] == "anticipo_pagado"
    assert r.json()["pedido"]["soy"] == "cliente"
    assert r.json()["cobro"]["estado"] == "capturado"

    autenticar_como(artista_.id)
    r = await http.post(ruta(pedido_id, "/iniciar"))
    assert r.json()["estado"] == "en_proceso"
    imagen = await medio(s, artista_)
    r = await http.post(
        ruta(pedido_id, "/vistas-previas"),
        json={"medio_id": str(imagen.id), "nota": "Primera version"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "en_proceso"
    [previa] = r.json()["vistas_previas"]
    assert previa["nota"] == "Primera version"
    assert previa["imagen"]["id"] == str(imagen.id)

    autenticar_como(comprador.id)
    r = await pagar(http, pedido_id, "saldo")
    assert r.json()["resultado"] == "completado", r.text
    assert r.json()["pedido"]["estado"] == "vista_previa_entregada"
    assert r.json()["cobro"]["estado"] == "autorizado"
    assert r.json()["cobro"]["autorizado_hasta"] is not None

    antes = datetime.now(UTC)
    r = await http.post(ruta(pedido_id, "/aprobar"))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "saldo_pagado"
    disputable = datetime.fromisoformat(cuerpo["disputable_hasta"])
    assert antes + VENTANA <= disputable <= datetime.now(UTC) + VENTANA

    cobros = await cobros_db(s, pedido_id)
    for tipo in (TipoCobro.ANTICIPO, TipoCobro.SALDO):
        foto = pasarela_falsa.inspeccionar_cobro(cobros[tipo].referencia_pasarela)
        assert foto.estado is EstadoOperacion.CAPTURADO
        assert foto.monto_capturado == cobros[tipo].monto
    # D8: la tarifa de la cuenta conectada es la congelada en el pedido
    assert pasarela_falsa.tarifa_de(artista_.pasarela_cuenta_id) == Decimal(
        cuerpo["tarifa_porcentaje"]
    )
    assert Decimal(cuerpo["tarifa_porcentaje"]) == POLITICAS.tarifa_taller_porcentaje


# 5. Evento


async def test_8b_05_evento(cliente, autenticar_como, sesion_api, pasarela_falsa):
    s, http = sesion_api, cliente
    artista_ = await artista(s, pasarela_falsa)
    comprador = await perfil(s)
    consulta_ = await consulta(s, comprador, artista_)
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
    pedido_id = r.json()["id"]
    assert r.json()["lugar_evento"] == "San Jose"

    autenticar_como(comprador.id)
    r = await pagar(http, pedido_id, "anticipo")
    assert r.json()["pedido"]["estado"] == "anticipo_pagado"
    r = await pagar(http, pedido_id, "saldo")
    assert r.json()["resultado"] == "completado", r.text
    cuerpo = r.json()["pedido"]
    assert cuerpo["estado"] == "saldo_pagado"
    assert r.json()["cobro"]["estado"] == "capturado"
    assert datetime.fromisoformat(cuerpo["disputable_hasta"]) == fecha + VENTANA

    saldo = (await cobros_db(s, pedido_id))[TipoCobro.SALDO]
    foto = pasarela_falsa.inspeccionar_cobro(saldo.referencia_pasarela)
    assert foto.estado is EstadoOperacion.CAPTURADO

    autenticar_como(artista_.id)
    r = await http.get(ruta(pedido_id))
    assert r.status_code == 200
    assert r.json()["estado"] == "saldo_pagado"
    assert r.json()["soy"] == "artista"


# 6. Obra disponible


async def test_8b_06_obra_disponible(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    artista_ = await artista(s, pasarela_falsa)
    pieza = await obra(s, artista_)
    comprador, otro = await perfil(s), await perfil(s)

    autenticar_como(comprador.id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "completado"
    pedido = r.json()["pedido"]
    assert pedido["estado"] == "en_proceso"
    assert pedido["tipo"] == "obra_disponible"
    assert r.json()["cobro"]["tipo"] == "total"
    assert r.json()["cobro"]["estado"] == "autorizado"
    assert Decimal(r.json()["cobro"]["monto"]) == pieza.precio

    autenticar_como(otro.id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    assert r.status_code == 409

    autenticar_como(artista_.id)
    r = await http.post(ruta(pedido["id"], "/despacho"), json={"guia_envio": "CR123"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "saldo_pagado"
    assert r.json()["guia_envio"] == "CR123"
    assert r.json()["disputable_hasta"] is not None
    vendida = await s.get(Obra, pieza.id, populate_existing=True)
    assert vendida.estado is EstadoObra.VENDIDA
    total = (await cobros_db(s, pedido["id"]))[TipoCobro.TOTAL]
    foto = pasarela_falsa.inspeccionar_cobro(total.referencia_pasarela)
    assert foto.estado is EstadoOperacion.CAPTURADO

    autenticar_como(otro.id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    assert r.status_code == 409


# 7. Permisos


async def test_8b_07_permisos(cliente, autenticar_como, sesion_api, pasarela_falsa):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="con_vista_previa"
    )
    pid = escena.pedido_id
    otra = await consulta(s, escena.comprador, escena.artista)
    imagen = await medio(s, escena.artista)

    autenticar_como(escena.comprador.id)
    assert (await cotizar(http, otra.id)).status_code == 403
    assert (await http.post(ruta(pid, "/iniciar"))).status_code == 403
    r = await http.post(ruta(pid, "/vistas-previas"), json={"medio_id": str(imagen.id)})
    assert r.status_code == 403
    r = await http.post(ruta(pid, "/despacho"), json={"guia_envio": "CR1"})
    assert r.status_code == 403
    r = await http.put(
        ruta(pid, "/cotizacion"),
        json={"descripcion": "Otra", "monto_total": "30000.00"},
    )
    assert r.status_code == 403

    autenticar_como(escena.artista.id)
    assert (await pagar(http, pid, "anticipo")).status_code == 403
    assert (await pagar(http, pid, "saldo")).status_code == 403
    assert (await http.post(ruta(pid, "/aprobar"))).status_code == 403

    tercero = await perfil(s)
    autenticar_como(tercero.id)
    cotizacion = {"descripcion": "Otra", "monto_total": "30000.00"}
    pago = {"metodo_pago_id": TARJETA}
    rutas = [
        ("put", "/cotizacion", cotizacion),
        ("post", "/rechazar", None),
        ("post", "/anticipo", pago),
        ("post", "/iniciar", None),
        ("post", "/vistas-previas", {"medio_id": str(imagen.id)}),
        ("post", "/saldo", pago),
        ("post", "/aprobar", None),
        ("post", "/despacho", {"guia_envio": "CR1"}),
        ("post", "/cancelar", None),
        ("post", "/disputa", {"motivo": "Metiche"}),
        ("get", "", None),
    ]
    for metodo, accion, cuerpo in rutas:
        r = await http.request(metodo, ruta(pid, accion), json=cuerpo)
        assert r.status_code == 404, (accion, r.text)
    cobro_id = (await cobros_db(s, pid))[TipoCobro.ANTICIPO].id
    assert (await http.post(ruta_verificar(cobro_id))).status_code == 404
    assert (await cotizar(http, escena.consulta_id)).status_code == 404

    propia = await obra(s, escena.artista)
    autenticar_como(escena.artista.id)
    r = await http.post(ruta_la_quiero(propia.id), json=pago)
    assert r.status_code == 403
    assert (await pedido_db(s, pid)).estado.value == "en_proceso"


# 8. Orden: nada llega a la pasarela si la transicion no corresponde


async def test_8b_08_orden(cliente, autenticar_como, sesion_api, pasarela_falsa):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa, hasta="en_proceso")
    pid = escena.pedido_id
    cobros_antes = pasarela_falsa.total_cobros

    autenticar_como(escena.comprador.id)
    r = await pagar(http, pid, "saldo")
    assert r.status_code == 409, r.text
    assert "vista previa" in r.json()["detail"]
    assert (await http.post(ruta(pid, "/aprobar"))).status_code == 409
    autenticar_como(escena.artista.id)
    r = await http.post(ruta(pid, "/despacho"), json={"guia_envio": "CR1"})
    assert r.status_code == 409

    assert pasarela_falsa.total_cobros == cobros_antes
    assert (await pedido_db(s, pid)).estado.value == "en_proceso"
    saldo = (await cobros_db(s, pid))[TipoCobro.SALDO]
    assert saldo.referencia_pasarela is None
    assert saldo.intentos == 0


# 9. Sin onboarding


async def test_8b_09_sin_onboarding(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    artista_ = await artista(s, pasarela_falsa, habilitado=False)
    comprador = await perfil(s)
    consulta_ = await consulta(s, comprador, artista_)

    autenticar_como(artista_.id)
    r = await cotizar(http, consulta_.id)
    assert r.status_code == 201, r.text

    autenticar_como(comprador.id)
    r = await pagar(http, r.json()["id"], "anticipo")
    assert r.status_code == 409
    assert "verificacion" in r.json()["detail"]
    assert pasarela_falsa.total_cobros == 0


# 10. Contraoferta y rechazo


async def test_8b_10_contraoferta_y_rechazo(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa)
    pid = escena.pedido_id

    autenticar_como(escena.artista.id)
    r = await http.put(
        ruta(pid, "/cotizacion"),
        json={
            "descripcion": "Retrato de dos mascotas",
            "monto_total": "30000.00",
            "anticipo_porcentaje": "50",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["descripcion"] == "Retrato de dos mascotas"
    assert Decimal(cobro_de(r.json(), "anticipo")["monto"]) == Decimal("15000.00")
    assert r.json()["id"] == str(pid)

    autenticar_como(escena.comprador.id)
    r = await http.post(ruta(pid, "/rechazar"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "rechazado"
    assert {c["estado"] for c in r.json()["cobros"]} == {"cancelado"}
    consulta_ = await s.get(Consulta, escena.consulta_id, populate_existing=True)
    assert consulta_.estado is EstadoConsulta.DESCARTADA
    assert (await http.post(ruta(pid, "/rechazar"))).status_code == 409


# 11. Cancelar


async def test_8b_11_cliente_cancela_y_conserva_el_anticipo(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="anticipo_pagado"
    )
    autenticar_como(escena.comprador.id)
    r = await http.post(ruta(escena.pedido_id, "/cancelar"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"
    anticipo = cobro_de(r.json(), "anticipo")
    assert anticipo["estado"] == "capturado"
    assert Decimal(anticipo["monto_reembolsado"]) == 0
    assert cobro_de(r.json(), "saldo")["estado"] == "cancelado"
    ref = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO].referencia_pasarela
    assert pasarela_falsa.inspeccionar_cobro(ref).monto_reembolsado == 0


async def test_8b_11_artista_cancela_y_reembolsa_todo(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="anticipo_pagado"
    )
    autenticar_como(escena.artista.id)
    r = await http.post(ruta(escena.pedido_id, "/cancelar"))
    assert r.status_code == 200, r.text
    anticipo = cobro_de(r.json(), "anticipo")
    assert anticipo["estado"] == "reembolsado"
    assert Decimal(anticipo["monto_reembolsado"]) == Decimal(anticipo["monto"])
    ref = (await cobros_db(s, escena.pedido_id))[TipoCobro.ANTICIPO].referencia_pasarela
    foto = pasarela_falsa.inspeccionar_cobro(ref)
    assert foto.monto_reembolsado == Decimal(anticipo["monto"])


async def test_8b_11_obra_confirmada_y_cancelada_libera(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    artista_ = await artista(s, pasarela_falsa)
    pieza = await obra(s, artista_)
    comprador = await perfil(s)
    autenticar_como(comprador.id)
    r = await http.post(ruta_la_quiero(pieza.id), json={"metodo_pago_id": TARJETA})
    pid = r.json()["pedido"]["id"]

    r = await http.post(ruta(pid, "/cancelar"))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"
    assert cobro_de(r.json(), "total")["estado"] == "cancelado"
    ref = (await cobros_db(s, pid))[TipoCobro.TOTAL].referencia_pasarela
    assert pasarela_falsa.inspeccionar_cobro(ref).estado is EstadoOperacion.LIBERADO
    disponible = await s.get(Obra, pieza.id, populate_existing=True)
    assert disponible.estado is EstadoObra.DISPONIBLE


# 12. Disputa


async def test_8b_12_disputa(cliente, autenticar_como, sesion_api, pasarela_falsa):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="vista_previa_entregada"
    )
    autenticar_como(escena.comprador.id)
    ruta_disputa = ruta(escena.pedido_id, "/disputa")
    assert (await http.post(ruta_disputa, json={})).status_code == 422
    assert (await http.post(ruta_disputa, json={"motivo": "   "})).status_code == 422
    r = await http.post(ruta_disputa, json={"motivo": "No se parece"})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "en_disputa"
    assert (await http.post(ruta_disputa, json={"motivo": "Otra"})).status_code == 409


# 13. Listados


async def test_8b_13_listados(cliente, autenticar_como, sesion_api, pasarela_falsa):
    s, http = sesion_api, cliente
    yo = await artista(s, pasarela_falsa)
    otro_artista = await artista(s, pasarela_falsa)
    como_cliente = [
        await encargo(
            http,
            autenticar_como,
            s,
            pasarela_falsa,
            artista_=otro_artista,
            comprador_=yo,
        )
        for _ in range(2)
    ]
    como_artista = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="anticipo_pagado", artista_=yo
    )
    ajeno = await encargo(http, autenticar_como, s, pasarela_falsa)

    autenticar_como(yo.id)

    async def _ids(consulta_params: dict) -> list[str]:
        r = await http.get(f"{API}/pedidos", params=consulta_params)
        assert r.status_code == 200, r.text
        return [p["id"] for p in r.json()["items"]]

    mios = {str(e.pedido_id) for e in [*como_cliente, como_artista]}
    assert set(await _ids({})) == mios
    assert str(ajeno.pedido_id) not in await _ids({})
    assert set(await _ids({"como": "cliente"})) == {
        str(e.pedido_id) for e in como_cliente
    }
    assert await _ids({"como": "artista"}) == [str(como_artista.pedido_id)]
    assert await _ids({"estado": "anticipo_pagado"}) == [str(como_artista.pedido_id)]
    assert await _ids({"consulta_id": str(como_cliente[0].consulta_id)}) == [
        str(como_cliente[0].pedido_id)
    ]
    assert await _ids({"consulta_id": str(ajeno.consulta_id)}) == []

    vistos: list[str] = []
    cursor = None
    while True:
        params = {"tamano": 2} | ({"cursor": cursor} if cursor else {})
        r = await http.get(f"{API}/pedidos", params=params)
        vistos += [p["id"] for p in r.json()["items"]]
        cursor = r.json()["siguiente_cursor"]
        if cursor is None:
            break
    assert len(vistos) == len(set(vistos)) == 3
    assert set(vistos) == mios


async def test_8b_13_listado_sin_n_mas_1(
    cliente, autenticar_como, sesion_api, pasarela_falsa, test_db
):
    s, http = sesion_api, cliente

    async def _listado_con(cuantos: int) -> int:
        lector = await perfil(s)
        artista_ = await artista(s, pasarela_falsa)
        for _ in range(cuantos):
            consulta_ = await consulta(s, lector, artista_)
            pedido = await servicio_pedidos.crear_pedido_desde_cotizacion(
                s,
                consulta_id=consulta_.id,
                tipo=TipoPedido.ENCARGO,
                descripcion="Retrato",
                monto_total=Decimal("10000.00"),
                pasarela="falsa",
                ahora=datetime.now(UTC),
                politicas=POLITICAS,
            )
            await servicio_pedidos.registrar_anticipo_capturado(
                s,
                pedido_id=pedido.id,
                referencia_pasarela=f"ref-{pedido.id}",
                ahora=datetime.now(UTC),
            )
            await servicio_pedidos.iniciar_trabajo(s, pedido_id=pedido.id)
            imagen = await medio(s, artista_)
            await servicio_pedidos.entregar_vista_previa(
                s,
                pedido_id=pedido.id,
                media_asset_id=imagen.id,
                bucket_publico=settings.BUCKET_MEDIOS,
            )
        await s.flush()
        contador = 0

        def _contar(*_args) -> None:
            nonlocal contador
            contador += 1

        autenticar_como(lector.id)
        event.listen(test_db.sync_engine, "before_cursor_execute", _contar)
        try:
            r = await http.get(f"{API}/pedidos")
        finally:
            event.remove(test_db.sync_engine, "before_cursor_execute", _contar)
        items = r.json()["items"]
        assert len(items) == cuantos
        assert all(len(i["vistas_previas"]) == 1 for i in items)
        assert all(len(i["cobros"]) == 2 for i in items)
        return contador

    assert await _listado_con(2) == await _listado_con(6)
