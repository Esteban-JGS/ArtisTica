"""Comentarios, respuestas y me gusta en comentarios contra una base migrada.

Cada prueba termina en rollback. Explorar es global: la prueba que lo lee filtra
por una categoria propia.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, func, select, text

from src.api.deps import get_current_user_payload
from src.core.config import settings
from src.domain.comentarios import destino_de_respuesta, puede_borrar
from src.main import app
from src.models import (
    Comentario,
    Follow,
    MeGustaComentario,
    Profile,
    Publicacion,
    RolPerfil,
)

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
    """Fechas de creacion estrictamente ascendentes, en el orden de llamada."""

    def __init__(self) -> None:
        self._actual = datetime.now(UTC) - timedelta(days=1)

    def __call__(self) -> datetime:
        self._actual += timedelta(seconds=1)
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


async def _publicacion(sesion_api, artista, *, borrada=False) -> Publicacion:
    publicacion = Publicacion(
        id=uuid.uuid4(),
        artista_id=artista.id,
        texto="Proceso",
        deleted_at=datetime.now(UTC) if borrada else None,
    )
    sesion_api.add(publicacion)
    await sesion_api.flush()
    return publicacion


async def _comentario(
    sesion_api, publicacion, autor, reloj, *, respuesta_a=None
) -> Comentario:
    comentario = Comentario(
        id=uuid.uuid4(),
        publicacion_id=publicacion.id,
        profile_id=autor.id,
        texto="Que lindo",
        respuesta_a_id=respuesta_a.id if respuesta_a else None,
        created_at=reloj(),
    )
    sesion_api.add(comentario)
    await sesion_api.flush()
    return comentario


async def _me_gusta(sesion_api, comentario, *perfiles) -> None:
    for perfil in perfiles:
        sesion_api.add(
            MeGustaComentario(comentario_id=comentario.id, profile_id=perfil.id)
        )
    await sesion_api.flush()


def _sin_token() -> None:
    app.dependency_overrides.pop(get_current_user_payload, None)


def _comentarios_ruta(publicacion) -> str:
    return f"{API}/publicaciones/{publicacion.id}/comentarios"


def _respuestas_ruta(comentario_id) -> str:
    return f"{API}/comentarios/{comentario_id}/respuestas"


def _me_gusta_ruta(comentario_id) -> str:
    return f"{API}/comentarios/{comentario_id}/me-gusta"


def _ids(items) -> list[str]:
    return [i["id"] for i in items]


async def _todos(cliente, ruta) -> list[dict]:
    items, cursor = [], None
    while True:
        params = {"tamano": 50, **({"cursor": cursor} if cursor else {})}
        pagina = (await cliente.get(ruta, params=params)).json()
        items += pagina["items"]
        cursor = pagina["siguiente_cursor"]
        if cursor is None:
            return items


# Reglas puras


def test_01_reglas_puras():
    primero, respuesta = uuid.uuid4(), uuid.uuid4()
    assert destino_de_respuesta(primero, None) == primero
    assert destino_de_respuesta(respuesta, primero) == primero

    autor, artista, tercero = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert puede_borrar(autor, artista, autor)
    assert puede_borrar(autor, artista, artista)
    assert not puede_borrar(autor, artista, tercero)


# Comentar y responder


async def test_02_comentar(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    yo = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista)
    borrada = await _publicacion(sesion_api, artista, borrada=True)

    r = await cliente.post(_comentarios_ruta(publicacion), json={"texto": "Hola"})
    assert r.status_code in (401, 403)

    autenticar_como(yo.id)
    r = await cliente.post(_comentarios_ruta(publicacion), json={"texto": " Hola "})
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["texto"] == "Hola"
    assert cuerpo["autor"]["handle"] == yo.handle
    assert cuerpo["autor"]["es_artista"] is False
    assert (cuerpo["me_gusta_total"], cuerpo["mi_me_gusta"]) == (0, False)
    assert (cuerpo["respuestas_total"], cuerpo["respuestas"]) == (0, [])

    r = await cliente.post(_comentarios_ruta(borrada), json={"texto": "Hola"})
    assert r.status_code == 404
    r = await cliente.post(
        f"{API}/publicaciones/{uuid.uuid4()}/comentarios", json={"texto": "Hola"}
    )
    assert r.status_code == 404
    for texto in ("Escribime al 8888-8888", "Por WhatsApp", "", "   ", "x" * 1001):
        r = await cliente.post(_comentarios_ruta(publicacion), json={"texto": texto})
        assert r.status_code == 422, texto
    r = await cliente.post(
        _comentarios_ruta(publicacion), json={"texto": "Hola", "extra": 1}
    )
    assert r.status_code == 422


async def test_03_responder(cliente, sesion_api, autenticar_como):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    yo = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista)
    otra = await _publicacion(sesion_api, artista)
    comentario = await _comentario(sesion_api, publicacion, artista, reloj)
    ajeno = await _comentario(sesion_api, otra, artista, reloj)
    autenticar_como(yo.id)

    async def _responder(objetivo_id) -> uuid.UUID:
        r = await cliente.post(
            _comentarios_ruta(publicacion),
            json={"texto": "Gracias", "respuesta_a": str(objetivo_id)},
        )
        assert r.status_code == 201
        return uuid.UUID(r.json()["id"])

    respuesta = await _responder(comentario.id)
    a_la_respuesta = await _responder(respuesta)
    for id_ in (respuesta, a_la_respuesta):
        guardada = await sesion_api.get(Comentario, id_)
        assert guardada.respuesta_a_id == comentario.id

    r = await cliente.post(
        _comentarios_ruta(publicacion),
        json={"texto": "Gracias", "respuesta_a": str(ajeno.id)},
    )
    assert r.status_code == 409
    r = await cliente.post(
        _comentarios_ruta(publicacion),
        json={"texto": "Gracias", "respuesta_a": str(uuid.uuid4())},
    )
    assert r.status_code == 409


# Listados


async def test_04_listado(cliente, sesion_api):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    otro = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista)
    comentarios = []
    for _ in range(25):
        comentario = await _comentario(sesion_api, publicacion, otro, reloj)
        comentarios.append(comentario)
    # Respuestas intercaladas en el tiempo: no son de primer nivel
    for comentario in comentarios[:3]:
        await _comentario(
            sesion_api, publicacion, artista, reloj, respuesta_a=comentario
        )
    esperados = [str(c.id) for c in comentarios]

    r = await cliente.get(_comentarios_ruta(publicacion), params={"tamano": 20})
    assert r.status_code == 200
    primera = r.json()
    assert len(primera["items"]) == 20
    assert primera["siguiente_cursor"] is not None
    r = await cliente.get(
        _comentarios_ruta(publicacion),
        params={"tamano": 20, "cursor": primera["siguiente_cursor"]},
    )
    segunda = r.json()
    assert len(segunda["items"]) == 5
    assert segunda["siguiente_cursor"] is None

    ids = _ids(primera["items"]) + _ids(segunda["items"])
    assert ids == esperados
    assert len(set(ids)) == 25

    r = await cliente.get(f"{API}/publicaciones/{uuid.uuid4()}/comentarios")
    assert r.status_code == 404


async def test_05_primeras_respuestas(cliente, sesion_api):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    otro = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista)
    comentario = await _comentario(sesion_api, publicacion, otro, reloj)
    sin_respuestas = await _comentario(sesion_api, publicacion, otro, reloj)
    respuestas = [
        await _comentario(
            sesion_api, publicacion, artista, reloj, respuesta_a=comentario
        )
        for _ in range(5)
    ]
    esperadas = [str(r.id) for r in respuestas]

    items = (await cliente.get(_comentarios_ruta(publicacion))).json()["items"]
    assert _ids(items) == [str(comentario.id), str(sin_respuestas.id)]
    assert items[0]["respuestas_total"] == 5
    assert _ids(items[0]["respuestas"]) == esperadas[:3]
    assert items[0]["respuestas"][0]["autor"]["handle"] == artista.handle
    assert (items[1]["respuestas_total"], items[1]["respuestas"]) == (0, [])

    r = await cliente.get(_respuestas_ruta(comentario.id))
    assert r.status_code == 200
    assert _ids(r.json()["items"]) == esperadas
    r = await cliente.get(_respuestas_ruta(comentario.id), params={"tamano": 2})
    assert _ids(r.json()["items"]) == esperadas[:2]
    assert _ids(await _todos(cliente, _respuestas_ruta(comentario.id))) == esperadas

    # Las respuestas de una respuesta no existen: hay un solo nivel
    assert (await cliente.get(_respuestas_ruta(respuestas[0].id))).status_code == 404
    assert (await cliente.get(_respuestas_ruta(uuid.uuid4()))).status_code == 404


# Borrar


async def test_06_borrar(cliente, sesion_api, autenticar_como):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    autor = await _publico(sesion_api)
    tercero = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista)
    propio, ajeno, con_respuestas = [
        await _comentario(sesion_api, publicacion, autor, reloj) for _ in range(3)
    ]
    respuesta = await _comentario(
        sesion_api, publicacion, tercero, reloj, respuesta_a=con_respuestas
    )

    autenticar_como(tercero.id)
    assert (await cliente.delete(f"{API}/comentarios/{propio.id}")).status_code == 403
    r = await cliente.delete(f"{API}/comentarios/{uuid.uuid4()}")
    assert r.status_code == 404

    autenticar_como(autor.id)
    assert (await cliente.delete(f"{API}/comentarios/{propio.id}")).status_code == 204
    assert (await cliente.delete(f"{API}/comentarios/{propio.id}")).status_code == 404

    autenticar_como(artista.id)
    assert (await cliente.delete(f"{API}/comentarios/{ajeno.id}")).status_code == 204
    r = await cliente.delete(f"{API}/comentarios/{con_respuestas.id}")
    assert r.status_code == 204

    _sin_token()
    assert (await cliente.get(_comentarios_ruta(publicacion))).json()["items"] == []
    r = await cliente.get(_respuestas_ruta(con_respuestas.id))
    assert r.status_code == 404
    # La respuesta desaparece con su comentario: ni me gusta acepta
    autenticar_como(tercero.id)
    assert (await cliente.put(_me_gusta_ruta(respuesta.id))).status_code == 404
    r = await cliente.get(f"{API}/publicaciones/{publicacion.id}")
    assert r.json()["comentarios_total"] == 0


# Me gusta


async def test_07_me_gusta(cliente, sesion_api, autenticar_como):
    reloj = Reloj()
    artista = await _perfil(sesion_api)
    yo = await _publico(sesion_api)
    otro = await _publico(sesion_api)
    publicacion = await _publicacion(sesion_api, artista)
    comentario = await _comentario(sesion_api, publicacion, artista, reloj)
    respuesta = await _comentario(
        sesion_api, publicacion, artista, reloj, respuesta_a=comentario
    )
    await _me_gusta(sesion_api, comentario, otro)

    autenticar_como(yo.id)
    for id_ in (comentario.id, comentario.id, respuesta.id):
        assert (await cliente.put(_me_gusta_ruta(id_))).status_code == 204
    filas = await sesion_api.execute(
        select(func.count(MeGustaComentario.id)).where(
            MeGustaComentario.comentario_id == comentario.id,
            MeGustaComentario.profile_id == yo.id,
        )
    )
    assert filas.scalar_one() == 1

    items = (await cliente.get(_comentarios_ruta(publicacion))).json()["items"]
    assert (items[0]["me_gusta_total"], items[0]["mi_me_gusta"]) == (2, True)
    primera = items[0]["respuestas"][0]
    assert (primera["me_gusta_total"], primera["mi_me_gusta"]) == (1, True)
    r = await cliente.get(_respuestas_ruta(comentario.id))
    assert r.json()["items"][0]["mi_me_gusta"] is True

    for _ in range(2):
        assert (await cliente.delete(_me_gusta_ruta(comentario.id))).status_code == 204
    items = (await cliente.get(_comentarios_ruta(publicacion))).json()["items"]
    assert (items[0]["me_gusta_total"], items[0]["mi_me_gusta"]) == (1, False)

    _sin_token()
    items = (await cliente.get(_comentarios_ruta(publicacion))).json()["items"]
    assert (items[0]["me_gusta_total"], items[0]["mi_me_gusta"]) == (1, None)
    assert items[0]["respuestas"][0]["mi_me_gusta"] is None
    r = await cliente.get(_respuestas_ruta(comentario.id))
    assert r.json()["items"][0]["mi_me_gusta"] is None
    assert (await cliente.put(_me_gusta_ruta(comentario.id))).status_code in (401, 403)

    autenticar_como(yo.id)
    assert (await cliente.put(_me_gusta_ruta(uuid.uuid4()))).status_code == 404
    assert (await cliente.delete(_me_gusta_ruta(uuid.uuid4()))).status_code == 404


# Total en el feed


async def test_08_total_en_el_feed(cliente, sesion_api, autenticar_como, categoria):
    reloj = Reloj()
    artista = await _perfil(sesion_api, categorias=[categoria])
    yo = await _publico(sesion_api)
    sesion_api.add(Follow(seguidor_id=yo.id, seguido_id=artista.id))
    publicacion = await _publicacion(sesion_api, artista)
    con_respuestas, *_ = [
        await _comentario(sesion_api, publicacion, yo, reloj) for _ in range(3)
    ]
    for _ in range(2):
        await _comentario(
            sesion_api, publicacion, artista, reloj, respuesta_a=con_respuestas
        )
    autenticar_como(yo.id)

    async def _totales() -> list[int]:
        seguidos = (await cliente.get(SEGUIDOS)).json()["items"]
        explorar = await cliente.get(EXPLORAR, params={"categorias": [categoria]})
        detalle = (await cliente.get(f"{API}/publicaciones/{publicacion.id}")).json()
        return [
            seguidos[0]["comentarios_total"],
            explorar.json()["items"][0]["comentarios_total"],
            detalle["comentarios_total"],
        ]

    assert await _totales() == [5, 5, 5]
    r = await cliente.delete(f"{API}/comentarios/{con_respuestas.id}")
    assert r.status_code == 204
    assert await _totales() == [2, 2, 2]


# Sin N+1


async def test_09_sin_n_mas_1(cliente, sesion_api, autenticar_como, test_db):
    lector = await _publico(sesion_api)

    async def _publicacion_con(cuantos: int) -> Publicacion:
        reloj = Reloj()
        artista = await _perfil(sesion_api)
        publicacion = await _publicacion(sesion_api, artista)
        for _ in range(cuantos):
            autor = await _publico(sesion_api)
            comentario = await _comentario(sesion_api, publicacion, autor, reloj)
            await _me_gusta(sesion_api, comentario, lector)
            for _ in range(4):
                otro = await _publico(sesion_api)
                respuesta = await _comentario(
                    sesion_api, publicacion, otro, reloj, respuesta_a=comentario
                )
                await _me_gusta(sesion_api, respuesta, lector)
        return publicacion

    async def _sentencias(publicacion: Publicacion, cuantos: int) -> int:
        contador = 0

        def _contar_sentencia(*_args) -> None:
            nonlocal contador
            contador += 1

        autenticar_como(lector.id)
        event.listen(test_db.sync_engine, "before_cursor_execute", _contar_sentencia)
        try:
            r = await cliente.get(_comentarios_ruta(publicacion))
        finally:
            event.remove(
                test_db.sync_engine, "before_cursor_execute", _contar_sentencia
            )
        items = r.json()["items"]
        assert len(items) == cuantos
        assert all(len(c["respuestas"]) == 3 for c in items)
        assert all(c["mi_me_gusta"] is True for c in items)
        return contador

    pocas = await _publicacion_con(3)
    muchas = await _publicacion_con(15)
    assert await _sentencias(pocas, 3) == await _sentencias(muchas, 15)


# RLS


async def test_10_rls(sesion_api):
    rls = await sesion_api.execute(
        text(
            "SELECT relrowsecurity FROM pg_class "
            "WHERE relname = 'me_gusta_comentarios' AND relkind = 'r'"
        )
    )
    assert rls.scalar_one() is True
    politicas = await sesion_api.execute(
        text(
            "SELECT count(*) FROM pg_policies WHERE tablename = 'me_gusta_comentarios'"
        )
    )
    assert politicas.scalar_one() == 0
