"""Feed Seguidos y Explorar contra una base migrada. Cada prueba termina en rollback.

Explorar es global: cada prueba filtra por una categoria propia para no ver
publicaciones de otras.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.core.config import settings
from src.models import EstadoObra, Follow, Obra, Profile, Publicacion, RolPerfil

API = settings.API_V1_STR
EXPLORAR = f"{API}/feed/explorar"
SEGUIDOS = f"{API}/feed/seguidos"


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


async def _seguidores(sesion_api, artista, cuantos: int) -> None:
    for _ in range(cuantos):
        seguidor = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
        sesion_api.add(Follow(seguidor_id=seguidor.id, seguido_id=artista.id))
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


# Seguidos


async def test_09_seguidos(cliente, sesion_api, autenticar_como):
    assert (await cliente.get(SEGUIDOS)).status_code in (401, 403)

    reloj = Reloj()
    yo = await _perfil(sesion_api)
    seguido = await _perfil(sesion_api)
    no_seguido = await _perfil(sesion_api)
    sesion_api.add(Follow(seguidor_id=yo.id, seguido_id=seguido.id))
    # Que alguien me siga a mi no mete sus publicaciones en mi feed
    sesion_api.add(Follow(seguidor_id=no_seguido.id, seguido_id=yo.id))
    await sesion_api.flush()

    esperadas = []
    for autor in (seguido, yo, no_seguido, seguido, yo, seguido):
        publicacion = await _publicacion(sesion_api, autor, reloj)
        if autor is not no_seguido:
            esperadas.append(str(publicacion.id))
    await _publicacion(sesion_api, seguido, reloj, borrada=True)
    await _publicacion(sesion_api, yo, reloj, borrada=True)

    autenticar_como(yo.id)
    paginas = await _recorrer(cliente, SEGUIDOS, {"tamano": 2})
    assert [len(p) for p in paginas] == [2, 2, 1]
    todas = [p for pagina in paginas for p in pagina]
    assert _ids(todas) == esperadas
    fechas = [p["created_at"] for p in todas]
    assert fechas == sorted(fechas, reverse=True)
    assert all(p["nuevo_talento"] is None for p in todas)

    # Un usuario publico tambien tiene Seguidos
    publico = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
    sesion_api.add(Follow(seguidor_id=publico.id, seguido_id=no_seguido.id))
    await sesion_api.flush()
    autenticar_como(publico.id)
    r = await cliente.get(SEGUIDOS)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["artista"]["handle"] == no_seguido.handle


# Explorar


async def test_10_explorar_publico_y_filtrado(cliente, sesion_api, categoria):
    r = await cliente.get(EXPLORAR)
    assert r.status_code == 200, r.text

    reloj = Reloj()
    por_perfil = await _perfil(sesion_api, categorias=[categoria, "otra"])
    por_obra = await _perfil(sesion_api, categorias=["otra"])
    ninguno = await _perfil(sesion_api, categorias=["otra"])
    obra = Obra(
        id=uuid.uuid4(),
        artista_id=por_obra.id,
        titulo="Colibri",
        estado=EstadoObra.EXHIBICION,
        categorias=[categoria],
    )
    obra_borrada = Obra(
        id=uuid.uuid4(),
        artista_id=ninguno.id,
        titulo="Borrada",
        estado=EstadoObra.EXHIBICION,
        categorias=[categoria],
        deleted_at=datetime.now(UTC),
    )
    sesion_api.add_all([obra, obra_borrada])
    await sesion_api.flush()

    del_perfil = await _publicacion(sesion_api, por_perfil, reloj)
    de_la_obra = await _publicacion(sesion_api, por_obra, reloj, obra=obra)
    await _publicacion(sesion_api, por_obra, reloj)
    await _publicacion(sesion_api, ninguno, reloj)
    await _publicacion(sesion_api, ninguno, reloj, obra=obra_borrada)
    await _publicacion(sesion_api, por_perfil, reloj, borrada=True)

    r = await cliente.get(EXPLORAR, params={"categorias": [categoria]})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert _ids(items) == [str(del_perfil.id), str(de_la_obra.id)]
    assert items[1]["obra"]["id"] == str(obra.id)
    assert all(p["nuevo_talento"] is True for p in items)
    assert r.json()["siguiente_cursor"] is None

    # Dos categorias: alcanza con que se cruce una
    r = await cliente.get(EXPLORAR, params={"categorias": [categoria, "sin-uso-x"]})
    assert _ids(r.json()["items"]) == [str(del_perfil.id), str(de_la_obra.id)]

    seis = [f"c{i}" for i in range(6)]
    assert (await cliente.get(EXPLORAR, params={"categorias": seis})).status_code == (
        422
    )
    assert (await cliente.get(EXPLORAR, params={"cursor": "no-sirve"})).status_code == (
        422
    )
    # Un cursor de otro listado no sirve en Explorar
    otro = (
        await cliente.get(
            f"{API}/artistas/{por_obra.handle}/publicaciones", params={"tamano": 1}
        )
    ).json()["siguiente_cursor"]
    assert otro
    assert (await cliente.get(EXPLORAR, params={"cursor": otro})).status_code == 422


async def test_11_cuota_de_nuevos_talentos(cliente, sesion_api, monkeypatch, categoria):
    monkeypatch.setattr(settings, "NUEVO_TALENTO_MAX_SEGUIDORES", 2)
    reloj = Reloj()
    consolidados = [await _perfil(sesion_api, categorias=[categoria]) for _ in range(2)]
    await _seguidores(sesion_api, consolidados[0], 2)
    await _seguidores(sesion_api, consolidados[1], 3)
    nuevos = [await _perfil(sesion_api, categorias=[categoria]) for _ in range(2)]
    await _seguidores(sesion_api, nuevos[1], 1)

    generales: set[str] = set()
    de_nuevos: set[str] = set()
    # Intercaladas en el tiempo: el orden no favorece a ninguno de los dos
    for _ in range(5):
        for artista in (*consolidados, *nuevos):
            publicacion = await _publicacion(sesion_api, artista, reloj)
            destino = de_nuevos if artista in nuevos else generales
            destino.add(str(publicacion.id))
    assert len(generales) == len(de_nuevos) == 10

    params = {"categorias": [categoria], "tamano": 10}
    paginas = await _recorrer(cliente, EXPLORAR, params)
    primera = paginas[0]
    assert len(primera) == 10
    marcados = [i for i, p in enumerate(primera, 1) if p["nuevo_talento"]]
    assert marcados == [5, 10]
    for posicion, p in enumerate(primera, 1):
        assert p["nuevo_talento"] is (posicion in (5, 10))
        assert p["id"] in (de_nuevos if p["nuevo_talento"] else generales)
    # Dentro de cada flujo, cronologico
    for flujo in (True, False):
        fechas = [p["created_at"] for p in primera if p["nuevo_talento"] is flujo]
        assert fechas == sorted(fechas, reverse=True)

    todas = [p for pagina in paginas for p in pagina]
    assert len(todas) == 20
    assert set(_ids(todas)) == generales | de_nuevos
    for p in todas:
        assert p["nuevo_talento"] is (p["id"] in de_nuevos)


async def test_12_explorar_con_un_solo_flujo(
    cliente, sesion_api, monkeypatch, categoria
):
    monkeypatch.setattr(settings, "NUEVO_TALENTO_MAX_SEGUIDORES", 2)
    reloj = Reloj()

    # Sin nuevos talentos: la pagina se llena con generales
    consolidado = await _perfil(sesion_api, categorias=[categoria])
    await _seguidores(sesion_api, consolidado, 2)
    generales = [await _publicacion(sesion_api, consolidado, reloj) for _ in range(7)]
    params = {"categorias": [categoria], "tamano": 5}
    paginas = await _recorrer(cliente, EXPLORAR, params)
    assert [len(p) for p in paginas] == [5, 2]
    todas = [p for pagina in paginas for p in pagina]
    assert _ids(todas) == [str(p.id) for p in generales]
    assert all(p["nuevo_talento"] is False for p in todas)

    # Sin generales: la pagina se llena con nuevos talentos
    otra = f"{categoria}-n"
    nuevo = await _perfil(sesion_api, categorias=[otra])
    await _seguidores(sesion_api, nuevo, 1)
    de_nuevos = [await _publicacion(sesion_api, nuevo, reloj) for _ in range(7)]
    paginas = await _recorrer(cliente, EXPLORAR, {"categorias": [otra], "tamano": 5})
    assert [len(p) for p in paginas] == [5, 2]
    todas = [p for pagina in paginas for p in pagina]
    assert _ids(todas) == [str(p.id) for p in de_nuevos]
    assert all(p["nuevo_talento"] is True for p in todas)
