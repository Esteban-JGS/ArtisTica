"""Busqueda de publicaciones y artistas contra una base migrada.

Cada prueba termina en rollback. La busqueda es global: cada prueba usa un
termino propio, asi que no la afecta lo que haya en la base.
"""

import random
import string
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.core.config import settings
from src.models import Comentario, Profile, Publicacion, Reaccion, RolPerfil

API = settings.API_V1_STR
BUSCAR_PUBLICACIONES = f"{API}/buscar/publicaciones"
BUSCAR_ARTISTAS = f"{API}/buscar/artistas"


@pytest.fixture
def cliente(async_client, sesion_api, almacenamiento_falso):  # noqa: ARG001  por su efecto
    """Cliente HTTP con la base y el almacenamiento de prueba ya puestos."""
    return async_client


@pytest.fixture
def marca() -> str:
    """Una palabra que nadie mas usa, solo letras para que no la parta el parser."""
    return "zq" + "".join(random.choices(string.ascii_lowercase, k=10))  # noqa: S311  no es criptografico


class Reloj:
    """Fechas de creacion estrictamente descendentes, en el orden de llamada."""

    def __init__(self) -> None:
        self._actual = datetime.now(UTC)

    def __call__(self) -> datetime:
        self._actual -= timedelta(seconds=1)
        return self._actual


async def _perfil(
    sesion_api, reloj, *, rol=RolPerfil.ARTISTA, handle=None, nombre="Ana"
) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(),
        handle=handle or f"u{uuid.uuid4().hex[:12]}",
        nombre=nombre,
        rol=rol,
        created_at=reloj(),
    )
    sesion_api.add(perfil)
    await sesion_api.flush()
    return perfil


async def _publicacion(sesion_api, artista, reloj, texto, *, borrada=False):
    publicacion = Publicacion(
        id=uuid.uuid4(),
        artista_id=artista.id,
        texto=texto,
        created_at=reloj(),
        deleted_at=datetime.now(UTC) if borrada else None,
    )
    sesion_api.add(publicacion)
    await sesion_api.flush()
    return publicacion


def _ids(items) -> list[str]:
    return [i["id"] for i in items]


async def test_11_publicaciones(cliente, sesion_api, marca):
    reloj = Reloj()
    artista = await _perfil(sesion_api, reloj)
    fan = await _perfil(sesion_api, reloj, rol=RolPerfil.PUBLICO)
    nueva = await _publicacion(sesion_api, artista, reloj, f"Una acuarela {marca}")
    await _publicacion(
        sesion_api, artista, reloj, f"Acuarela borrada {marca}", borrada=True
    )
    media = await _publicacion(sesion_api, artista, reloj, f"Acuarelas del {marca}")
    await _publicacion(sesion_api, artista, reloj, f"Un oleo {marca}")
    vieja = await _publicacion(sesion_api, artista, reloj, f"{marca}: ACUARELA")
    sesion_api.add(
        Reaccion(publicacion_id=media.id, profile_id=fan.id, tipo="me_gusta")
    )
    sesion_api.add(Comentario(publicacion_id=media.id, profile_id=fan.id, texto="Wow"))
    await sesion_api.flush()

    r = await cliente.get(BUSCAR_PUBLICACIONES, params={"q": f"acuarelas {marca}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert _ids(items) == [str(nueva.id), str(media.id), str(vieja.id)]
    assert [(p["me_gusta_total"], p["comentarios_total"]) for p in items] == [
        (0, 0),
        (1, 1),
        (0, 0),
    ]
    assert all(p["mi_me_gusta"] is None for p in items)

    r = await cliente.get(
        BUSCAR_PUBLICACIONES, params={"q": f"acuarela {marca}", "tamano": 2}
    )
    primera = r.json()
    assert _ids(primera["items"]) == [str(nueva.id), str(media.id)]
    r = await cliente.get(
        BUSCAR_PUBLICACIONES,
        params={"q": f"acuarela {marca}", "cursor": primera["siguiente_cursor"]},
    )
    assert _ids(r.json()["items"]) == [str(vieja.id)]
    assert r.json()["siguiente_cursor"] is None

    # Recortado y con los limites de largo
    r = await cliente.get(BUSCAR_PUBLICACIONES, params={"q": f"  {marca}  "})
    assert len(r.json()["items"]) == 4
    for q in ("a", " a ", "", "x" * 101):
        r = await cliente.get(BUSCAR_PUBLICACIONES, params={"q": q})
        assert r.status_code == 422, q
    assert (await cliente.get(BUSCAR_PUBLICACIONES)).status_code == 422


async def test_12_artistas(cliente, sesion_api, marca):
    reloj = Reloj()
    por_nombre = await _perfil(sesion_api, reloj, nombre=f"Taller {marca.upper()}")
    por_handle = await _perfil(sesion_api, reloj, handle=f"ana{marca}x")
    await _perfil(sesion_api, reloj, rol=RolPerfil.PUBLICO, nombre=f"Fan {marca}")
    porcentaje = await _perfil(sesion_api, reloj, nombre=f"Estudio {marca}%A")
    guion_bajo = await _perfil(sesion_api, reloj, nombre=f"Estudio {marca}_B")

    async def _handles(q: str) -> list[str]:
        r = await cliente.get(BUSCAR_ARTISTAS, params={"q": q})
        assert r.status_code == 200, q
        assert all(p["es_artista"] for p in r.json()["items"])
        return [p["handle"] for p in r.json()["items"]]

    todos = [por_nombre, por_handle, porcentaje, guion_bajo]
    assert await _handles(marca.upper()) == [p.handle for p in todos]
    assert await _handles(f"ANA{marca[:4]}") == [por_handle.handle]
    assert await _handles(f"taller {marca}") == [por_nombre.handle]

    # Comodines como literales: sin escapar, los dos traerian a todos
    assert await _handles(f"{marca}%") == [porcentaje.handle]
    assert await _handles(f"{marca}_") == [guion_bajo.handle]
    assert await _handles(f"{marca}\\") == []
    for q in ("%%", "__"):
        r = await cliente.get(BUSCAR_ARTISTAS, params={"q": q})
        for perfil in r.json()["items"]:
            assert q in perfil["handle"] or q in perfil["nombre"], q

    r = await cliente.get(BUSCAR_ARTISTAS, params={"q": f"{marca}", "tamano": 3})
    primera = r.json()
    assert len(primera["items"]) == 3
    r = await cliente.get(
        BUSCAR_ARTISTAS, params={"q": marca, "cursor": primera["siguiente_cursor"]}
    )
    assert [p["handle"] for p in r.json()["items"]] == [guion_bajo.handle]
    assert (await cliente.get(BUSCAR_ARTISTAS, params={"q": "a"})).status_code == 422
