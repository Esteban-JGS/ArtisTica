"""Dominio y endpoints de medios contra una base migrada. Cada prueba termina en rollback."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.core.config import settings
from src.domain import medios as dominio
from src.models import EstadoObra, Job, MediaAsset, Obra, Profile, RolPerfil
from src.storage import AlmacenamientoNoDisponible, InfoObjeto

API = settings.API_V1_STR
WEBP = "image/webp"


@pytest.fixture
def cliente(async_client, sesion_api, almacenamiento_falso):
    """Cliente HTTP con la base y el almacenamiento de prueba ya puestos."""
    return async_client


# Ayudas


async def _perfil(sesion_api, rol=RolPerfil.ARTISTA) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(), handle=f"u{uuid.uuid4().hex[:12]}", nombre="Ana", rol=rol
    )
    sesion_api.add(perfil)
    await sesion_api.flush()
    return perfil


async def _artista(sesion_api, autenticar_como) -> Profile:
    artista = await _perfil(sesion_api)
    autenticar_como(artista.id)
    return artista


async def _solicitar(cliente, content_type=WEBP, tamano=1000):
    return await cliente.post(
        f"{API}/medios", json={"content_type": content_type, "tamano_bytes": tamano}
    )


async def _pedir(cliente, content_type=WEBP, tamano=1000) -> dict:
    r = await _solicitar(cliente, content_type, tamano)
    assert r.status_code == 201, r.text
    return r.json()


async def _medio(sesion_api, medio_id) -> MediaAsset:
    return await sesion_api.get(
        MediaAsset, uuid.UUID(str(medio_id)), populate_existing=True
    )


async def _jobs_de(sesion_api, medio_id) -> int:
    stmt = select(func.count(Job.id)).where(
        Job.type == "generate_thumbnail",
        Job.payload["medio_id"].astext == str(medio_id),
    )
    return (await sesion_api.execute(stmt)).scalar_one()


def _confirmar(cliente, medio_id):
    return cliente.post(f"{API}/medios/{medio_id}/confirmar")


# Dominio


def test_08_ruta_para():
    propietario, medio = uuid.uuid4(), uuid.uuid4()
    assert dominio.ruta_para(propietario, medio, WEBP) == f"{propietario}/{medio}.webp"
    with pytest.raises(ValueError):
        dominio.ruta_para(propietario, medio, "image/gif")


def test_09_problema_de_subida():
    maximo = 100
    valido = InfoObjeto(tamano_bytes=50, content_type=WEBP)
    assert dominio.problema_de_subida(WEBP, valido, maximo) is None
    assert dominio.problema_de_subida(WEBP, None, maximo) == dominio.MOTIVO_NO_SUBIDO
    grande = InfoObjeto(tamano_bytes=101, content_type=WEBP)
    assert (
        dominio.problema_de_subida(WEBP, grande, maximo)
        == dominio.MOTIVO_DEMASIADO_GRANDE
    )
    otro = InfoObjeto(tamano_bytes=50, content_type="image/png")
    assert dominio.problema_de_subida(WEBP, otro, maximo) == (
        dominio.MOTIVO_TIPO_DISTINTO
    )


# API


async def test_10_solicitud_invalida(cliente, sesion_api, autenticar_como):
    publico = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
    autenticar_como(publico.id)
    assert (await _solicitar(cliente)).status_code == 403

    await _artista(sesion_api, autenticar_como)
    assert (await _solicitar(cliente, content_type="image/gif")).status_code == 422
    excedido = settings.MEDIO_TAMANO_MAXIMO_BYTES + 1
    assert (await _solicitar(cliente, tamano=excedido)).status_code == 422
    r = await cliente.post(
        f"{API}/medios",
        json={"content_type": WEBP, "tamano_bytes": 10, "ruta": "otro/x.webp"},
    )
    assert r.status_code == 422


async def test_11_solicitud_valida(cliente, sesion_api, autenticar_como):
    artista = await _artista(sesion_api, autenticar_como)
    datos = await _pedir(cliente)

    assert datos["ruta"].startswith(f"{artista.id}/")
    assert datos["ruta"].endswith(".webp")
    assert datos["bucket"] == settings.BUCKET_MEDIOS
    assert datos["token"] and datos["url_subida"]
    medio = await _medio(sesion_api, datos["medio_id"])
    assert medio.propietario_id == artista.id
    assert medio.storage_path == datos["ruta"]
    assert medio.subido_en is None
    assert medio.content_type == WEBP


async def test_12_maximo_de_pendientes(
    cliente, sesion_api, autenticar_como, monkeypatch
):
    monkeypatch.setattr(settings, "MEDIOS_PENDIENTES_MAXIMOS", 2)
    await _artista(sesion_api, autenticar_como)
    await _pedir(cliente)
    await _pedir(cliente)
    assert (await _solicitar(cliente)).status_code == 409


async def test_13_falla_al_firmar_no_deja_fila(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    almacenamiento_falso.programar_falla(
        "firmar_subida", AlmacenamientoNoDisponible("caido")
    )
    r = await _solicitar(cliente)
    assert r.status_code == 503
    assert r.json()["detail"] == "El almacenamiento no esta disponible"
    stmt = select(func.count(MediaAsset.id)).where(
        MediaAsset.propietario_id == artista.id
    )
    assert (await sesion_api.execute(stmt)).scalar_one() == 0


async def test_14_confirmar_sin_subir(cliente, sesion_api, autenticar_como):
    await _artista(sesion_api, autenticar_como)
    datos = await _pedir(cliente)
    r = await _confirmar(cliente, datos["medio_id"])
    assert r.status_code == 409
    assert r.json()["detail"] == dominio.MOTIVO_NO_SUBIDO
    assert (await _medio(sesion_api, datos["medio_id"])).subido_en is None


async def test_15_confirmar_encola_una_miniatura(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    await _artista(sesion_api, autenticar_como)
    datos = await _pedir(cliente)
    almacenamiento_falso.simular_subida(
        datos["bucket"], datos["ruta"], b"x" * 700, WEBP
    )

    r = await _confirmar(cliente, datos["medio_id"])
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["subido"] is True
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["tamano_bytes"] == 700
    assert cuerpo["url"] == almacenamiento_falso.url_publica(
        datos["bucket"], datos["ruta"]
    )
    assert cuerpo["miniatura_url"] is None
    assert await _jobs_de(sesion_api, datos["medio_id"]) == 1
    assert (await _medio(sesion_api, datos["medio_id"])).subido_en is not None

    r = await _confirmar(cliente, datos["medio_id"])
    assert r.status_code == 200
    assert await _jobs_de(sesion_api, datos["medio_id"]) == 1

    r = await cliente.get(f"{API}/medios/{datos['medio_id']}")
    assert r.status_code == 200
    assert r.json()["subido"] is True


async def test_16_confirmar_rechaza_y_borra_el_objeto(
    cliente, sesion_api, autenticar_como, almacenamiento_falso, monkeypatch
):
    monkeypatch.setattr(settings, "MEDIO_TAMANO_MAXIMO_BYTES", 100)
    await _artista(sesion_api, autenticar_como)

    grande = await _pedir(cliente, tamano=50)
    almacenamiento_falso.simular_subida(
        grande["bucket"], grande["ruta"], b"x" * 101, WEBP
    )
    r = await _confirmar(cliente, grande["medio_id"])
    assert r.status_code == 409
    assert r.json()["detail"] == dominio.MOTIVO_DEMASIADO_GRANDE
    assert not almacenamiento_falso.existe(grande["bucket"], grande["ruta"])

    otro_tipo = await _pedir(cliente, tamano=50)
    almacenamiento_falso.simular_subida(
        otro_tipo["bucket"], otro_tipo["ruta"], b"x" * 50, "image/png"
    )
    r = await _confirmar(cliente, otro_tipo["medio_id"])
    assert r.status_code == 409
    assert r.json()["detail"] == dominio.MOTIVO_TIPO_DISTINTO
    assert not almacenamiento_falso.existe(otro_tipo["bucket"], otro_tipo["ruta"])
    assert (await _medio(sesion_api, otro_tipo["medio_id"])).subido_en is None


async def test_17_medio_ajeno_da_404(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    await _artista(sesion_api, autenticar_como)
    datos = await _pedir(cliente)
    almacenamiento_falso.simular_subida(datos["bucket"], datos["ruta"], b"x", WEBP)

    otro = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
    autenticar_como(otro.id)
    medio_url = f"{API}/medios/{datos['medio_id']}"
    assert (await cliente.get(medio_url)).status_code == 404
    assert (await _confirmar(cliente, datos["medio_id"])).status_code == 404
    assert (await cliente.delete(medio_url)).status_code == 404

    assert (await _medio(sesion_api, datos["medio_id"])).subido_en is None
    assert almacenamiento_falso.existe(datos["bucket"], datos["ruta"])


async def test_18_eliminar(cliente, sesion_api, autenticar_como, almacenamiento_falso):
    artista = await _artista(sesion_api, autenticar_como)

    suelto = await _pedir(cliente)
    almacenamiento_falso.simular_subida(suelto["bucket"], suelto["ruta"], b"x", WEBP)
    assert (await _confirmar(cliente, suelto["medio_id"])).status_code == 200
    r = await cliente.delete(f"{API}/medios/{suelto['medio_id']}")
    assert r.status_code == 204
    assert (await _medio(sesion_api, suelto["medio_id"])).deleted_at is not None
    assert not almacenamiento_falso.existe(suelto["bucket"], suelto["ruta"])
    # Borrado ya no existe para su dueno
    assert (await cliente.get(f"{API}/medios/{suelto['medio_id']}")).status_code == 404

    obra = Obra(
        artista_id=artista.id,
        titulo="Colibri en acuarela",
        estado=EstadoObra.DISPONIBLE,
        precio=Decimal("15000.00"),
    )
    sesion_api.add(obra)
    await sesion_api.flush()
    asociado = await _pedir(cliente)
    almacenamiento_falso.simular_subida(
        asociado["bucket"], asociado["ruta"], b"x", WEBP
    )
    assert (await _confirmar(cliente, asociado["medio_id"])).status_code == 200
    medio = await _medio(sesion_api, asociado["medio_id"])
    medio.obra_id = obra.id
    await sesion_api.flush()

    r = await cliente.delete(f"{API}/medios/{asociado['medio_id']}")
    assert r.status_code == 409
    assert (await _medio(sesion_api, asociado["medio_id"])).deleted_at is None
    assert almacenamiento_falso.existe(asociado["bucket"], asociado["ruta"])
