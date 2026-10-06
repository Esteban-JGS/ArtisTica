"""Endpoints de perfiles contra una base migrada. Cada prueba termina en rollback."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.api.deps import get_current_user_payload
from src.core.config import settings
from src.core.exceptions import CobroNoHabilitado
from src.domain.politicas import PoliticasPedido
from src.main import app
from src.models import Consulta, EstadoConsulta, Pedido, Profile, TipoPedido
from src.payments.errores import PasarelaNoDisponible
from src.services import pedidos as servicio_pedidos
from src.services.perfiles import exigir_cobro_habilitado

API = settings.API_V1_STR
POLITICAS = PoliticasPedido.desde_config(settings)


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa):  # noqa: ARG001  pedidas por su efecto; usefixtures no aplica a una fixture
    """Cliente HTTP con la base y la pasarela de prueba ya puestas."""
    return async_client


# Ayudas


def _handle() -> str:
    return f"u{uuid.uuid4().hex[:12]}"


async def _registrar(cliente, autenticar_como, handle=None) -> uuid.UUID:
    user_id = uuid.uuid4()
    autenticar_como(user_id)
    r = await cliente.post(
        f"{API}/perfiles", json={"handle": handle or _handle(), "nombre": "Ana"}
    )
    assert r.status_code == 201, r.text
    return user_id


async def _artista(cliente, autenticar_como) -> uuid.UUID:
    user_id = await _registrar(cliente, autenticar_como)
    r = await cliente.post(f"{API}/perfiles/yo/artista")
    assert r.status_code == 200, r.text
    return user_id


async def _con_cuenta(cliente, autenticar_como, sesion_api) -> tuple[uuid.UUID, str]:
    user_id = await _artista(cliente, autenticar_como)
    r = await cliente.post(f"{API}/perfiles/yo/onboarding")
    assert r.status_code == 200, r.text
    return user_id, await _cuenta_de(sesion_api, user_id)


async def _perfil(sesion_api, user_id) -> Profile:
    return await sesion_api.get(Profile, user_id, populate_existing=True)


async def _cuenta_de(sesion_api, user_id) -> str | None:
    return (await _perfil(sesion_api, user_id)).pasarela_cuenta_id


async def _plan(cliente, plan: str):
    return await cliente.put(f"{API}/perfiles/yo/plan", json={"plan": plan})


async def _pedido_abierto(sesion_api, artista_id) -> Pedido:
    comprador = Profile(id=uuid.uuid4(), handle=_handle(), nombre="Cliente")
    sesion_api.add(comprador)
    await sesion_api.flush()
    consulta = Consulta(
        cliente_id=comprador.id, artista_id=artista_id, estado=EstadoConsulta.ABIERTA
    )
    sesion_api.add(consulta)
    await sesion_api.flush()
    return await servicio_pedidos.crear_pedido_desde_cotizacion(
        sesion_api,
        consulta_id=consulta.id,
        tipo=TipoPedido.ENCARGO,
        descripcion="Retrato de mascota",
        monto_total=Decimal("10000.00"),
        anticipo_porcentaje=Decimal("50"),
        pasarela="falsa",
        ahora=datetime.now(UTC),
        politicas=POLITICAS,
    )


# Registro y perfil


async def test_09_registro(cliente, autenticar_como):
    user_id = uuid.uuid4()
    autenticar_como(user_id)
    handle = _handle()
    r = await cliente.post(f"{API}/perfiles", json={"handle": handle, "nombre": "Ana"})
    assert r.status_code == 201, r.text
    assert r.json()["rol"] == "publico"

    r = await cliente.post(
        f"{API}/perfiles", json={"handle": _handle(), "nombre": "Ana"}
    )
    assert r.status_code == 409

    autenticar_como(uuid.uuid4())
    r = await cliente.post(f"{API}/perfiles", json={"handle": handle, "nombre": "Bea"})
    assert r.status_code == 409
    assert "handle" in r.json()["detail"]


async def test_10_sin_token_y_sin_perfil(cliente, autenticar_como):
    r = await cliente.get(f"{API}/perfiles/yo")
    assert r.status_code in (401, 403)

    autenticar_como(uuid.uuid4())
    r = await cliente.get(f"{API}/perfiles/yo")
    assert r.status_code == 404
    assert r.json()["detail"] == "Perfil no registrado"


async def test_11_actualizar_perfil(cliente, autenticar_como):
    await _registrar(cliente, autenticar_como)

    r = await cliente.patch(f"{API}/perfiles/yo", json={"bio": "Pedidos al 8888-8888"})
    assert r.status_code == 422
    r = await cliente.patch(f"{API}/perfiles/yo", json={"provincia": "Narnia"})
    assert r.status_code == 422

    cambios = {
        "bio": "Acuarelas de fauna tica. instagram.com/ana",
        "provincia": "San José",
        "categorias": ["acuarela", "retrato"],
    }
    r = await cliente.patch(f"{API}/perfiles/yo", json=cambios)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert {k: cuerpo[k] for k in cambios} == cambios


async def test_12_perfil_publico_sin_token(cliente, autenticar_como):
    handle = _handle()
    await _registrar(cliente, autenticar_como, handle)
    app.dependency_overrides.pop(get_current_user_payload, None)

    r = await cliente.get(f"{API}/perfiles/{handle}")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["handle"] == handle
    for oculto in ("pasarela_cuenta_id", "rol", "onboarding"):
        assert oculto not in cuerpo
    assert "pasarela_cuenta_id" not in r.text

    r = await cliente.get(f"{API}/perfiles/{_handle()}")
    assert r.status_code == 404


async def test_13_hacerse_artista(cliente, autenticar_como):
    await _registrar(cliente, autenticar_como)
    r = await cliente.post(f"{API}/perfiles/yo/artista")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["rol"] == "artista"
    assert cuerpo["plan"] == "taller"
    assert Decimal(cuerpo["tarifa_porcentaje"]) == Decimal("8")


# Plan


async def test_14_publico_no_cambia_plan(cliente, autenticar_como):
    await _registrar(cliente, autenticar_como)
    r = await _plan(cliente, "estudio")
    assert r.status_code == 403


async def test_15_estudio_sin_cuenta(cliente, autenticar_como):
    await _artista(cliente, autenticar_como)
    r = await _plan(cliente, "estudio")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["plan"] == "estudio"
    assert Decimal(cuerpo["tarifa_porcentaje"]) == Decimal("5")
    assert cuerpo["tarifa_sincronizada"] is None


async def test_16_estudio_con_cuenta_sin_pedidos(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    _, cuenta = await _con_cuenta(cliente, autenticar_como, sesion_api)
    assert pasarela_falsa.tarifa_de(cuenta) == Decimal("8")

    r = await _plan(cliente, "estudio")
    assert r.status_code == 200, r.text
    assert r.json()["tarifa_sincronizada"] is True
    assert pasarela_falsa.tarifa_de(cuenta) == Decimal("5")


async def test_17_estudio_con_pedido_abierto(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    artista_id, cuenta = await _con_cuenta(cliente, autenticar_como, sesion_api)
    pedido = await _pedido_abierto(sesion_api, artista_id)
    assert pedido.tarifa_porcentaje == Decimal("8")

    r = await _plan(cliente, "estudio")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["plan"] == "estudio"
    assert cuerpo["tarifa_sincronizada"] is None
    assert pasarela_falsa.tarifa_de(cuenta) == Decimal("8")
    pedido = await sesion_api.get(Pedido, pedido.id, populate_existing=True)
    assert pedido.tarifa_porcentaje == Decimal("8")


async def test_18_falla_de_pasarela_conserva_el_plan(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    artista_id, cuenta = await _con_cuenta(cliente, autenticar_como, sesion_api)
    pasarela_falsa.programar_falla("configurar_tarifa", PasarelaNoDisponible("caida"))

    r = await _plan(cliente, "estudio")
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "estudio"
    assert r.json()["tarifa_sincronizada"] is False
    assert (await _perfil(sesion_api, artista_id)).plan == "estudio"
    assert pasarela_falsa.tarifa_de(cuenta) == Decimal("8")


async def test_07_sin_autoservicio_estudio_da_403(
    cliente, autenticar_como, sesion_api, pasarela_falsa, monkeypatch
):
    monkeypatch.setattr(settings, "ESTUDIO_AUTOSERVICIO", False)
    artista_id, cuenta = await _con_cuenta(cliente, autenticar_como, sesion_api)

    r = await _plan(cliente, "estudio")
    assert r.status_code == 403
    assert (await _perfil(sesion_api, artista_id)).plan == "taller"
    assert pasarela_falsa.tarifa_de(cuenta) == Decimal("8")


async def test_08_sin_autoservicio_se_baja_a_taller(
    cliente, autenticar_como, sesion_api, monkeypatch
):
    artista_id = await _artista(cliente, autenticar_como)
    r = await _plan(cliente, "estudio")
    assert r.status_code == 200, r.text

    monkeypatch.setattr(settings, "ESTUDIO_AUTOSERVICIO", False)
    r = await _plan(cliente, "taller")
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "taller"
    assert (await _perfil(sesion_api, artista_id)).plan == "taller"


# Onboarding


async def test_19_onboarding(cliente, autenticar_como, sesion_api, pasarela_falsa):
    artista_id = await _artista(cliente, autenticar_como)

    r = await cliente.post(f"{API}/perfiles/yo/onboarding")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "pendiente"
    assert r.json()["url_onboarding"]
    assert r.json()["puede_cobrar"] is False
    cuenta = await _cuenta_de(sesion_api, artista_id)
    assert cuenta is not None

    r = await cliente.post(f"{API}/perfiles/yo/onboarding")
    assert r.status_code == 200, r.text
    assert await _cuenta_de(sesion_api, artista_id) == cuenta

    pasarela_falsa.completar_onboarding(cuenta)
    r = await cliente.get(f"{API}/perfiles/yo/onboarding")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "completado"
    assert r.json()["puede_cobrar"] is True

    r = await cliente.get(f"{API}/perfiles/yo")
    assert r.json()["verificado"] is True
    assert r.json()["puede_cobrar"] is True


async def test_20_onboarding_con_pasarela_caida(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    artista_id = await _artista(cliente, autenticar_como)
    pasarela_falsa.programar_falla(
        "crear_cuenta_conectada", PasarelaNoDisponible("caida")
    )

    r = await cliente.post(f"{API}/perfiles/yo/onboarding")
    assert r.status_code == 503
    assert r.json()["detail"] == "La pasarela de pagos no esta disponible"
    perfil = await _perfil(sesion_api, artista_id)
    assert perfil.pasarela_cuenta_id is None

    with pytest.raises(CobroNoHabilitado):
        exigir_cobro_habilitado(perfil)


async def test_actualizar_handle_ocupado_deja_la_transaccion_usable(
    cliente, autenticar_como
):
    ocupado = _handle()
    await _registrar(cliente, autenticar_como, ocupado)
    await _registrar(cliente, autenticar_como)

    r = await cliente.patch(f"{API}/perfiles/yo", json={"handle": ocupado})
    assert r.status_code == 409
    r = await cliente.patch(f"{API}/perfiles/yo", json={"nombre": "Ana Mora"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Ana Mora"
