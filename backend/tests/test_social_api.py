"""Seguir, contadores y me gusta contra una base migrada. Cada prueba termina en rollback.

Explorar es global: las pruebas que lo leen filtran por una categoria propia.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select

from src.api.deps import get_current_user_payload
from src.core.config import Settings, settings
from src.domain.enums import TipoReaccion
from src.main import app
from src.models import (
    EstadoMedia,
    EstadoObra,
    Follow,
    MediaAsset,
    Obra,
    Profile,
    Publicacion,
    Reaccion,
    RolPerfil,
)

API = settings.API_V1_STR
EXPLORAR = f"{API}/feed/explorar"
SEGUIDOS = f"{API}/feed/seguidos"
WEBP = "image/webp"
BUCKET = settings.BUCKET_MEDIOS


@pytest.fixture
def cliente(async_client, sesion_api, almacenamiento_falso):  # noqa: ARG001  por su efecto
    """Cliente HTTP con la base y el almacenamiento de prueba ya puestos."""
    return async_client


@pytest.fixture
def categoria() -> str:
    return f"cat-{uuid.uuid4().hex[:12]}"


class Reloj:
    """Fechas de creacion estrictamente descendentes, en el orden de llamada."""

    def __init__(self) -> None:
        self._actual = datetime.now(UTC)

    def __call__(self) -> datetime:
        self._actual -= timedelta(seconds=1)
        return self._actual


# Fabricas


async def _perfil(sesion_api, rol=RolPerfil.ARTISTA, categorias=()) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(),
        handle=f"u{uuid.uuid4().hex[:12]}",
        nombre="Ana",
        rol=rol,
        categorias=list(categorias),
    )
    sesion_api.add(perfil)
    await sesion_api.flush()
    return perfil


async def _publico(sesion_api) -> Profile:
    return await _perfil(sesion_api, rol=RolPerfil.PUBLICO)


async def _seguir(sesion_api, seguidor, seguido, creado_en=None) -> None:
    follow = Follow(seguidor_id=seguidor.id, seguido_id=seguido.id)
    if creado_en is not None:
        follow.created_at = creado_en
    sesion_api.add(follow)
    await sesion_api.flush()


async def _publicacion(
    sesion_api, artista, reloj, *, obra=None, borrada=False
) -> Publicacion:
    publicacion = Publicacion(
        id=uuid.uuid4(),
        artista_id=artista.id,
        texto="Proceso",
        obra_id=obra.id if obra else None,
        created_at=reloj(),
        deleted_at=datetime.now(UTC) if borrada else None,
    )
    sesion_api.add(publicacion)
    await sesion_api.flush()
    return publicacion


async def _me_gusta(sesion_api, publicacion, *perfiles) -> None:
    for perfil in perfiles:
        sesion_api.add(
            Reaccion(
                publicacion_id=publicacion.id,
                profile_id=perfil.id,
                tipo=TipoReaccion.ME_GUSTA.value,
            )
        )
    await sesion_api.flush()


async def _medio(sesion_api, almacenamiento, propietario) -> MediaAsset:
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
        subido_en=datetime.now(UTC),
    )
    sesion_api.add(medio)
    await sesion_api.flush()
    await almacenamiento.subir(BUCKET, ruta, b"imagen", WEBP)
    await almacenamiento.subir(BUCKET, medio.thumbnail_path, b"mini", WEBP)
    return medio


async def _contar(sesion_api, modelo, *condiciones) -> int:
    stmt = select(func.count(modelo.id)).where(*condiciones)
    return (await sesion_api.execute(stmt)).scalar_one()


def _sin_token() -> None:
    app.dependency_overrides.pop(get_current_user_payload, None)


async def _recorrer(cliente, ruta, params) -> list[list[dict]]:
    """Todas las paginas, siguiendo el cursor hasta que venga nulo."""
    paginas: list[list[dict]] = []
    cursor = None
    while True:
        consulta = dict(params, **({"cursor": cursor} if cursor else {}))
        r = await cliente.get(ruta, params=consulta)
        assert r.status_code == 200, r.text
        paginas.append(r.json()["items"])
        cursor = r.json()["siguiente_cursor"]
        if cursor is None:
            return paginas
        assert len(paginas) < 50, "el cursor no avanza"


def _ids(items) -> list[str]:
    return [p["id"] for p in items]


def _seguir_ruta(handle: str) -> str:
    return f"{API}/artistas/{handle}/seguir"


def _me_gusta_ruta(publicacion_id) -> str:
    return f"{API}/publicaciones/{publicacion_id}/me-gusta"


# Seguir


async def test_01_seguir(cliente, sesion_api, autenticar_como):
    yo = await _perfil(sesion_api)
    artista = await _perfil(sesion_api)
    publico = await _publico(sesion_api)
    ruta = _seguir_ruta(artista.handle)

    assert (await cliente.post(ruta)).status_code in (401, 403)
    assert (await cliente.delete(ruta)).status_code in (401, 403)

    autenticar_como(yo.id)
    es_mio = (Follow.seguidor_id == yo.id, Follow.seguido_id == artista.id)
    assert (await cliente.post(ruta)).status_code == 204
    assert (await cliente.post(ruta)).status_code == 204
    assert await _contar(sesion_api, Follow, *es_mio) == 1
    # El handle se normaliza igual que en el perfil publico
    assert (await cliente.post(_seguir_ruta(artista.handle.upper()))).status_code == (
        204
    )
    assert await _contar(sesion_api, Follow, *es_mio) == 1

    assert (await cliente.delete(ruta)).status_code == 204
    assert (await cliente.delete(ruta)).status_code == 204
    assert await _contar(sesion_api, Follow, *es_mio) == 0

    r = await cliente.post(_seguir_ruta(yo.handle))
    assert r.status_code == 409
    r = await cliente.post(_seguir_ruta(publico.handle))
    assert r.status_code == 409
    assert r.json()["detail"] == "Solo se sigue a artistas"
    assert await _contar(sesion_api, Follow, Follow.seguidor_id == yo.id) == 0

    nadie = _seguir_ruta(f"nadie-{uuid.uuid4().hex}")
    assert (await cliente.post(nadie)).status_code == 404
    assert (await cliente.delete(nadie)).status_code == 404


async def test_02_resumen(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    otro_artista = await _perfil(sesion_api)
    fan = await _publico(sesion_api)
    ajeno = await _publico(sesion_api)
    await _seguir(sesion_api, fan, artista)
    await _seguir(sesion_api, otro_artista, artista)
    await _seguir(sesion_api, artista, otro_artista)
    ruta = f"{API}/perfiles/{artista.handle}/social"

    r = await cliente.get(ruta)
    assert r.status_code == 200, r.text
    assert r.json() == {"seguidores": 2, "siguiendo": 1, "lo_sigo": None}

    autenticar_como(fan.id)
    assert (await cliente.get(ruta)).json()["lo_sigo"] is True
    r = await cliente.get(f"{API}/perfiles/{fan.handle}/social")
    assert r.json() == {"seguidores": 0, "siguiendo": 1, "lo_sigo": False}
    autenticar_como(ajeno.id)
    assert (await cliente.get(ruta)).json()["lo_sigo"] is False
    autenticar_como(artista.id)
    assert (await cliente.get(ruta)).json() == {
        "seguidores": 2,
        "siguiendo": 1,
        "lo_sigo": False,
    }
    # Un token valido sin perfil mira como anonimo
    autenticar_como(uuid.uuid4())
    assert (await cliente.get(ruta)).json()["lo_sigo"] is None

    r = await cliente.get(f"{API}/perfiles/nadie-{uuid.uuid4().hex}/social")
    assert r.status_code == 404

    # Un token roto no se ignora en silencio
    _sin_token()
    r = await cliente.get(ruta, headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


@pytest.mark.parametrize("lista", ["seguidores", "siguiendo"])
async def test_03_listas_paginadas(cliente, sesion_api, lista):
    reloj = Reloj()
    centro = await _perfil(sesion_api)
    esperados: list[str] = []
    # Cada follow es mas viejo que el anterior: el orden esperado es el de creacion
    for i in range(25):
        otro = await _perfil(
            sesion_api, rol=RolPerfil.PUBLICO if i % 2 else RolPerfil.ARTISTA
        )
        if lista == "seguidores":
            await _seguir(sesion_api, otro, centro, reloj())
        else:
            await _seguir(sesion_api, centro, otro, reloj())
        esperados.append(otro.handle)

    paginas = await _recorrer(
        cliente, f"{API}/perfiles/{centro.handle}/{lista}", {"tamano": 20}
    )
    assert [len(p) for p in paginas] == [20, 5]
    todos = [p for pagina in paginas for p in pagina]
    handles = [p["handle"] for p in todos]
    assert handles == esperados
    assert len(set(handles)) == 25
    assert set(todos[0]) == {"handle", "nombre", "verificado", "es_artista"}
    assert todos[0]["es_artista"] is True
    assert todos[1]["es_artista"] is False

    r = await cliente.get(f"{API}/perfiles/nadie-{uuid.uuid4().hex}/{lista}")
    assert r.status_code == 404


# Me gusta


async def test_04_me_gusta(cliente, sesion_api, autenticar_como):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    publico = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista, reloj)
    borrada = await _publicacion(sesion_api, artista, reloj, borrada=True)
    ruta = _me_gusta_ruta(publicacion.id)

    assert (await cliente.put(ruta)).status_code in (401, 403)

    autenticar_como(publico.id)
    filas = (Reaccion.publicacion_id == publicacion.id,)
    assert (await cliente.put(ruta)).status_code == 204
    assert (await cliente.put(ruta)).status_code == 204
    assert await _contar(sesion_api, Reaccion, *filas) == 1
    assert (await cliente.delete(ruta)).status_code == 204
    assert (await cliente.delete(ruta)).status_code == 204
    assert await _contar(sesion_api, Reaccion, *filas) == 0

    # El autor tambien puede
    autenticar_como(artista.id)
    assert (await cliente.put(ruta)).status_code == 204
    assert await _contar(sesion_api, Reaccion, *filas) == 1

    for id_ in (borrada.id, uuid.uuid4()):
        assert (await cliente.put(_me_gusta_ruta(id_))).status_code == 404
        assert (await cliente.delete(_me_gusta_ruta(id_))).status_code == 404


async def test_05_contadores_en_el_feed(
    cliente, sesion_api, autenticar_como, categoria
):
    reloj = Reloj()
    artista = await _perfil(sesion_api, categorias=[categoria])
    yo = await _publico(sesion_api)
    otros = [await _publico(sesion_api) for _ in range(2)]
    await _seguir(sesion_api, yo, artista)
    tres, una, ninguna = [
        await _publicacion(sesion_api, artista, reloj) for _ in range(3)
    ]
    await _me_gusta(sesion_api, tres, yo, *otros)
    await _me_gusta(sesion_api, una, otros[0])
    totales = [3, 1, 0]
    ids = [str(p.id) for p in (tres, una, ninguna)]

    # Sin token: los totales, y nulo en mi_me_gusta
    r = await cliente.get(EXPLORAR, params={"categorias": [categoria]})
    items = r.json()["items"]
    assert _ids(items) == ids
    assert [p["me_gusta_total"] for p in items] == totales
    assert all(p["mi_me_gusta"] is None for p in items)
    r = await cliente.get(f"{API}/publicaciones/{tres.id}")
    assert (r.json()["me_gusta_total"], r.json()["mi_me_gusta"]) == (3, None)
    r = await cliente.get(f"{API}/artistas/{artista.handle}/publicaciones")
    assert [p["mi_me_gusta"] for p in r.json()["items"]] == [None] * 3

    autenticar_como(yo.id)
    mias = [True, False, False]
    for ruta, params in (
        (SEGUIDOS, {}),
        (EXPLORAR, {"categorias": [categoria]}),
        (f"{API}/artistas/{artista.handle}/publicaciones", {}),
    ):
        items = (await cliente.get(ruta, params=params)).json()["items"]
        assert _ids(items) == ids, ruta
        assert [p["me_gusta_total"] for p in items] == totales, ruta
        assert [p["mi_me_gusta"] for p in items] == mias, ruta
    for publicacion, total, mia in zip(
        (tres, una, ninguna), totales, mias, strict=True
    ):
        r = await cliente.get(f"{API}/publicaciones/{publicacion.id}")
        assert (r.json()["me_gusta_total"], r.json()["mi_me_gusta"]) == (total, mia)


async def test_06_el_orden_no_cambia(cliente, sesion_api, autenticar_como, categoria):
    reloj = Reloj()
    artista = await _perfil(sesion_api, categorias=[categoria])
    yo = await _publico(sesion_api)
    await _seguir(sesion_api, yo, artista)
    publicaciones = [await _publicacion(sesion_api, artista, reloj) for _ in range(4)]
    cronologico = [str(p.id) for p in publicaciones]
    autenticar_como(yo.id)
    explorar = {"categorias": [categoria]}

    async def _ordenes() -> tuple[list[str], list[str]]:
        seguidos = (await cliente.get(SEGUIDOS)).json()["items"]
        explorados = (await cliente.get(EXPLORAR, params=explorar)).json()["items"]
        return _ids(seguidos), _ids(explorados)

    antes = await _ordenes()
    assert antes == (cronologico, cronologico)

    # La mas vieja junta muchos me gusta, y su artista muchos seguidores
    fans = [await _publico(sesion_api) for _ in range(12)]
    await _me_gusta(sesion_api, publicaciones[-1], yo, *fans)
    for fan in fans:
        await _seguir(sesion_api, fan, artista)
    seguidos, explorados = await _ordenes()
    assert (seguidos, explorados) == antes
    ultima = (await cliente.get(SEGUIDOS)).json()["items"][-1]
    assert ultima["me_gusta_total"] == 13


async def test_07_sin_n_mas_1(cliente, sesion_api, autenticar_como, test_db):
    reloj = Reloj()

    async def _lector_con(cuantas: int) -> Profile:
        artista = await _perfil(sesion_api)
        lector = await _publico(sesion_api)
        await _seguir(sesion_api, lector, artista)
        obra = Obra(
            id=uuid.uuid4(),
            artista_id=artista.id,
            titulo="Colibri",
            estado=EstadoObra.EXHIBICION,
        )
        sesion_api.add(obra)
        await sesion_api.flush()
        for _ in range(cuantas):
            publicacion = await _publicacion(sesion_api, artista, reloj, obra=obra)
            await _me_gusta(sesion_api, publicacion, lector)
        return lector

    async def _sentencias(lector: Profile, cuantas: int) -> int:
        contador = 0

        def _contar_sentencia(*_args) -> None:
            nonlocal contador
            contador += 1

        autenticar_como(lector.id)
        event.listen(test_db.sync_engine, "before_cursor_execute", _contar_sentencia)
        try:
            r = await cliente.get(SEGUIDOS)
        finally:
            event.remove(
                test_db.sync_engine, "before_cursor_execute", _contar_sentencia
            )
        assert len(r.json()["items"]) == cuantas
        assert all(p["mi_me_gusta"] is True for p in r.json()["items"])
        return contador

    pocas = await _lector_con(3)
    muchas = await _lector_con(15)
    assert await _sentencias(pocas, 3) == await _sentencias(muchas, 15)


async def test_08_seguir_de_punta_a_punta(cliente, sesion_api, autenticar_como):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    yo = await _publico(sesion_api)
    publicaciones = [await _publicacion(sesion_api, artista, reloj) for _ in range(2)]
    autenticar_como(yo.id)

    assert (await cliente.get(SEGUIDOS)).json()["items"] == []
    assert (await cliente.post(_seguir_ruta(artista.handle))).status_code == 204
    items = (await cliente.get(SEGUIDOS)).json()["items"]
    assert _ids(items) == [str(p.id) for p in publicaciones]
    assert (await cliente.delete(_seguir_ruta(artista.handle))).status_code == 204
    assert (await cliente.get(SEGUIDOS)).json()["items"] == []


# DT21


OBLIGATORIAS = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "ALEMBIC_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "SUPABASE_URL": "http://supabase.local",
}


async def test_09_dt21_cuota_minima(cliente, monkeypatch, categoria):
    monkeypatch.setattr(settings, "EXPLORAR_CADA_N", 5)
    params = {"categorias": [categoria]}
    r = await cliente.get(EXPLORAR, params={**params, "tamano": 4})
    assert r.status_code == 422
    assert "al menos 5" in r.json()["detail"]
    assert (
        await cliente.get(EXPLORAR, params={**params, "tamano": 5})
    ).status_code == (200)
    # Se lee en cada solicitud
    monkeypatch.setattr(settings, "EXPLORAR_CADA_N", 7)
    r = await cliente.get(EXPLORAR, params={**params, "tamano": 6})
    assert r.status_code == 422
    assert "al menos 7" in r.json()["detail"]

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **OBLIGATORIAS, EXPLORAR_CADA_N=30)
    assert "EXPLORAR_CADA_N" in str(exc.value)
    assert "PAGINA_TAMANO_DEFECTO" in str(exc.value)
    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            **OBLIGATORIAS,
            EXPLORAR_CADA_N=8,
            PAGINA_TAMANO_DEFECTO=5,
            PAGINA_TAMANO_MAXIMO=6,
        )
    assert "PAGINA_TAMANO_MAXIMO" in str(exc.value)
    assert Settings(_env_file=None, **OBLIGATORIAS).EXPLORAR_CADA_N == 5


async def test_10_dt21_imagen_publica(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    # Un solo esquema con la forma de imagen publica, y se llama ImagenPublica:
    # el nombre viejo ya no existe con ningun alias
    esquemas = app.openapi()["components"]["schemas"]
    forma = {"id", "url", "miniatura_url"}
    con_la_forma = {
        n for n, e in esquemas.items() if set(e.get("properties", {})) == forma
    }
    assert con_la_forma == {"ImagenPublica"}

    artista = await _perfil(sesion_api)
    autenticar_como(artista.id)
    de_obra = await _medio(sesion_api, almacenamiento_falso, artista)
    de_publicacion = await _medio(sesion_api, almacenamiento_falso, artista)

    r = await cliente.post(
        f"{API}/obras", json={"titulo": "Colibri", "medios": [str(de_obra.id)]}
    )
    assert r.status_code == 201, r.text
    obra_id = r.json()["id"]
    r = await cliente.post(
        f"{API}/publicaciones",
        json={"texto": "Proceso", "medios": [str(de_publicacion.id)]},
    )
    assert r.status_code == 201, r.text
    publicacion_id = r.json()["id"]

    for ruta, medio in (
        (f"{API}/obras/{obra_id}", de_obra),
        (f"{API}/publicaciones/{publicacion_id}", de_publicacion),
    ):
        r = await cliente.get(ruta)
        assert r.status_code == 200, r.text
        (imagen,) = r.json()["medios"]
        assert set(imagen) == {"id", "url", "miniatura_url"}
        assert imagen["id"] == str(medio.id)
        assert imagen["url"]
        assert imagen["miniatura_url"]
