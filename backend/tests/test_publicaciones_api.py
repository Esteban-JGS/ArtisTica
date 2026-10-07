"""Endpoints de publicaciones contra una base migrada. Cada prueba termina en rollback."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.core.config import settings
from src.models import (
    EstadoMedia,
    EstadoObra,
    MediaAsset,
    Obra,
    Profile,
    Publicacion,
    RolPerfil,
)

API = settings.API_V1_STR
WEBP = "image/webp"
BUCKET = settings.BUCKET_MEDIOS


@pytest.fixture
def cliente(async_client, sesion_api, almacenamiento_falso):  # noqa: ARG001  por su efecto
    """Cliente HTTP con la base y el almacenamiento de prueba ya puestos."""
    return async_client


# Fabricas


async def _perfil(sesion_api, rol=RolPerfil.ARTISTA) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(),
        handle=f"u{uuid.uuid4().hex[:12]}",
        nombre="Ana",
        rol=rol,
    )
    sesion_api.add(perfil)
    await sesion_api.flush()
    return perfil


async def _artista(sesion_api, autenticar_como) -> Profile:
    artista = await _perfil(sesion_api)
    autenticar_como(artista.id)
    return artista


async def _medio(
    sesion_api, almacenamiento, propietario, *, confirmado=True, obra_id=None
) -> MediaAsset:
    """Un medio como lo deja el lote 5: confirmado tiene `subido_en` y su objeto."""
    medio_id = uuid.uuid4()
    ruta = f"{propietario.id}/{medio_id}.webp"
    medio = MediaAsset(
        id=medio_id,
        propietario_id=propietario.id,
        tipo="imagen",
        storage_path=ruta,
        thumbnail_path=f"{ruta}.thumb.webp",
        bucket=BUCKET,
        content_type=WEBP,
        tamano_bytes=100,
        estado=EstadoMedia.PROCESADO,
        subido_en=datetime.now(UTC) if confirmado else None,
        obra_id=obra_id,
    )
    sesion_api.add(medio)
    await sesion_api.flush()
    await almacenamiento.subir(BUCKET, ruta, b"imagen", WEBP)
    await almacenamiento.subir(BUCKET, medio.thumbnail_path, b"mini", WEBP)
    return medio


async def _obra(
    sesion_api, artista, *, estado=EstadoObra.DISPONIBLE, borrada=False
) -> Obra:
    obra = Obra(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo="Colibri",
        estado=estado,
        precio=Decimal("15000.00") if estado != EstadoObra.EXHIBICION else None,
        deleted_at=datetime.now(UTC) if borrada else None,
    )
    sesion_api.add(obra)
    await sesion_api.flush()
    return obra


async def _publicar(cliente, texto="Proceso del colibri", medios=(), obra=None):
    cuerpo: dict = {"texto": texto, "medios": [str(m.id) for m in medios]}
    if obra is not None:
        cuerpo["obra_id"] = str(obra.id)
    return await cliente.post(f"{API}/publicaciones", json=cuerpo)


async def _recargar(sesion_api, modelo, id_):
    return await sesion_api.get(modelo, id_, populate_existing=True)


async def _contar_publicaciones(sesion_api, artista) -> int:
    stmt = select(func.count(Publicacion.id)).where(
        Publicacion.artista_id == artista.id
    )
    return (await sesion_api.execute(stmt)).scalar_one()


def _claves(valor) -> set[str]:
    """Todas las claves de un JSON, a cualquier profundidad."""
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


# Publicaciones


async def test_04_publicar_con_imagenes_y_obra(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    publico = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
    autenticar_como(publico.id)
    assert (await _publicar(cliente)).status_code == 403

    artista = await _artista(sesion_api, autenticar_como)
    obra = await _obra(sesion_api, artista)
    primero = await _medio(sesion_api, almacenamiento_falso, artista)
    segundo = await _medio(sesion_api, almacenamiento_falso, artista)
    r = await _publicar(cliente, medios=[segundo, primero], obra=obra)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert [m["id"] for m in cuerpo["medios"]] == [str(segundo.id), str(primero.id)]
    assert all(m["url"] and m["miniatura_url"] for m in cuerpo["medios"])
    assert cuerpo["obra"] == {
        "id": str(obra.id),
        "titulo": "Colibri",
        "disponible": True,
    }
    assert cuerpo["artista"] == {
        "handle": artista.handle,
        "nombre": "Ana",
        "verificado": False,
    }
    assert cuerpo["nuevo_talento"] is None
    assert "precio" not in _claves(cuerpo)

    publicacion_id = uuid.UUID(cuerpo["id"])
    for posicion, medio in enumerate((segundo, primero)):
        fila = await _recargar(sesion_api, MediaAsset, medio.id)
        assert fila.publicacion_id == publicacion_id
        assert fila.obra_id is None
        assert fila.orden == posicion

    r = await cliente.get(f"{API}/publicaciones/{publicacion_id}")
    assert r.status_code == 200
    assert r.json() == cuerpo


async def test_05_validaciones_al_publicar(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    r = await _publicar(cliente, texto="Agenda de octubre")
    assert r.status_code == 201, r.text
    assert r.json()["medios"] == []
    assert r.json()["obra"] is None

    for texto in ("Escribime al 8888-8888", "   ", ""):
        assert (await _publicar(cliente, texto=texto)).status_code == 422, texto
    r = await cliente.post(
        f"{API}/publicaciones", json={"texto": "Hola", "precio": "1000"}
    )
    assert r.status_code == 422

    otro = await _perfil(sesion_api)
    obra_ajena = await _obra(sesion_api, otro)
    obra_borrada = await _obra(sesion_api, artista, borrada=True)
    for obra in (obra_ajena, obra_borrada):
        assert (await _publicar(cliente, obra=obra)).status_code == 409

    obra_propia = await _obra(sesion_api, artista, estado=EstadoObra.EXHIBICION)
    ajeno = await _medio(sesion_api, almacenamiento_falso, otro)
    sin_confirmar = await _medio(
        sesion_api, almacenamiento_falso, artista, confirmado=False
    )
    de_obra = await _medio(
        sesion_api, almacenamiento_falso, artista, obra_id=obra_propia.id
    )
    bueno = await _medio(sesion_api, almacenamiento_falso, artista)
    antes = await _contar_publicaciones(sesion_api, artista)
    for malo in (ajeno, sin_confirmar, de_obra):
        r = await _publicar(cliente, medios=[bueno, malo])
        assert r.status_code == 409, (malo.id, r.text)
    assert await _contar_publicaciones(sesion_api, artista) == antes
    for medio in (ajeno, sin_confirmar, de_obra, bueno):
        fila = await _recargar(sesion_api, MediaAsset, medio.id)
        assert fila.publicacion_id is None
    assert (await _recargar(sesion_api, MediaAsset, de_obra.id)).obra_id == (
        obra_propia.id
    )

    once = [await _medio(sesion_api, almacenamiento_falso, artista) for _ in range(11)]
    assert (await _publicar(cliente, medios=once)).status_code == 422
    assert (await _publicar(cliente, medios=[bueno, bueno])).status_code == 422

    # Una publicacion en exhibicion muestra la obra como no disponible
    r = await _publicar(cliente, obra=obra_propia)
    assert r.status_code == 201
    assert r.json()["obra"]["disponible"] is False


async def test_06_editar_y_borrar(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    await _artista(sesion_api, autenticar_como)
    ajena = (await _publicar(cliente, texto="Ajena")).json()

    artista = await _artista(sesion_api, autenticar_como)
    medios = [await _medio(sesion_api, almacenamiento_falso, artista) for _ in range(2)]
    propia = (await _publicar(cliente, medios=medios)).json()
    ruta = f"{API}/publicaciones/{propia['id']}"

    r = await cliente.patch(ruta, json={"texto": "Texto nuevo"})
    assert r.status_code == 200, r.text
    assert r.json()["texto"] == "Texto nuevo"
    assert [m["id"] for m in r.json()["medios"]] == [str(m.id) for m in medios]
    assert (
        await cliente.patch(ruta, json={"texto": "Llama 8888-8888"})
    ).status_code == (422)
    assert (await cliente.patch(ruta, json={"medios": []})).status_code == 422

    r = await cliente.patch(f"{API}/publicaciones/{ajena['id']}", json={"texto": "x"})
    assert r.status_code == 404
    r = await cliente.delete(f"{API}/publicaciones/{ajena['id']}")
    assert r.status_code == 404
    assert (await cliente.get(f"{API}/publicaciones/{ajena['id']}")).status_code == 200

    assert (await cliente.delete(ruta)).status_code == 204
    for medio in medios:
        fila = await _recargar(sesion_api, MediaAsset, medio.id)
        assert fila.deleted_at is not None
        assert not almacenamiento_falso.existe(BUCKET, medio.storage_path)
        assert not almacenamiento_falso.existe(BUCKET, medio.thumbnail_path)
    assert (await cliente.get(ruta)).status_code == 404
    assert (await cliente.patch(ruta, json={"texto": "Otra vez"})).status_code == 404
    assert (await cliente.delete(ruta)).status_code == 404
    assert (await cliente.get(f"{API}/publicaciones/{uuid.uuid4()}")).status_code == 404


async def test_07_listado_del_artista_paginado(cliente, sesion_api, autenticar_como):
    artista = await _artista(sesion_api, autenticar_como)
    base = datetime.now(UTC)
    for numero in range(26):
        sesion_api.add(
            Publicacion(
                id=uuid.uuid4(),
                artista_id=artista.id,
                texto=f"Publicacion {numero:02d}",
                created_at=base - timedelta(minutes=numero),
                # La ultima esta borrada: no cuenta
                deleted_at=base if numero == 25 else None,
            )
        )
    otro = await _perfil(sesion_api)
    sesion_api.add(Publicacion(id=uuid.uuid4(), artista_id=otro.id, texto="Ajena"))
    await sesion_api.flush()

    ruta = f"{API}/artistas/{artista.handle}/publicaciones"
    primera = (await cliente.get(ruta, params={"tamano": 20})).json()
    assert len(primera["items"]) == 20
    assert primera["siguiente_cursor"]
    segunda = (
        await cliente.get(
            ruta, params={"tamano": 20, "cursor": primera["siguiente_cursor"]}
        )
    ).json()
    assert len(segunda["items"]) == 5
    assert segunda["siguiente_cursor"] is None

    todos = primera["items"] + segunda["items"]
    assert len({p["id"] for p in todos}) == 25
    assert [p["texto"] for p in todos] == [f"Publicacion {n:02d}" for n in range(25)]
    fechas = [p["created_at"] for p in todos]
    assert fechas == sorted(fechas, reverse=True)
    assert all(p["nuevo_talento"] is None for p in todos)

    assert (await cliente.get(ruta, params={"cursor": "no-sirve"})).status_code == 422
    r = await cliente.get(f"{API}/artistas/nadie-{uuid.uuid4().hex}/publicaciones")
    assert r.status_code == 404


async def test_08_regresion_de_medios_en_obras(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    a, b, c = [
        await _medio(sesion_api, almacenamiento_falso, artista) for _ in range(3)
    ]
    r = await cliente.post(
        f"{API}/obras", json={"titulo": "Colibri", "medios": [str(a.id), str(b.id)]}
    )
    assert r.status_code == 201, r.text
    obra_id = r.json()["id"]
    assert [m["id"] for m in r.json()["medios"]] == [str(a.id), str(b.id)]

    # Reordenar y cambiar: el que sale queda suelto, el que entra toma su lugar
    r = await cliente.patch(
        f"{API}/obras/{obra_id}", json={"medios": [str(c.id), str(a.id)]}
    )
    assert r.status_code == 200, r.text
    assert [m["id"] for m in r.json()["medios"]] == [str(c.id), str(a.id)]
    suelto = await _recargar(sesion_api, MediaAsset, b.id)
    assert suelto.obra_id is None
    assert suelto.orden is None
    assert (await _recargar(sesion_api, MediaAsset, c.id)).orden == 0

    # Un medio de una publicacion no sirve para una obra, ni al reves
    publicado = await _medio(sesion_api, almacenamiento_falso, artista)
    assert (await _publicar(cliente, medios=[publicado])).status_code == 201
    r = await cliente.patch(
        f"{API}/obras/{obra_id}", json={"medios": [str(publicado.id)]}
    )
    assert r.status_code == 409
    assert (await _publicar(cliente, medios=[a])).status_code == 409

    # El suelto que dejo la obra sirve para una publicacion
    assert (await _publicar(cliente, medios=[b])).status_code == 201
    r = await cliente.post(
        f"{API}/obras", json={"titulo": "Sin imagenes", "medios": []}
    )
    assert r.status_code == 422
