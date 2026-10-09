"""Consultas y chat contra una base migrada.

Cada prueba termina en rollback. Los perfiles nacen con 30 dias salvo que la
prueba pida una cuenta reciente: el limite de consultas solo rige para esas.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select, text

from src.api.deps import get_current_user_payload
from src.core.config import settings
from src.domain.consultas import AVISO_PAGO_FUERA
from src.main import app
from src.models import (
    Consulta,
    EstadoConsulta,
    EstadoObra,
    Mensaje,
    Obra,
    Profile,
    RolPerfil,
    Servicio,
    TipoServicio,
)
from src.services import consultas as servicio

API = settings.API_V1_STR
CONSULTAS = f"{API}/consultas"
NO_LEIDOS = f"{CONSULTAS}/no-leidos"


@pytest.fixture
def cliente(async_client, sesion_api, almacenamiento_falso):  # noqa: ARG001  por su efecto
    """Cliente HTTP con la base y el almacenamiento de prueba ya puestos."""
    return async_client


class Reloj:
    """Fechas estrictamente ascendentes en el pasado, en el orden de llamada."""

    def __init__(self) -> None:
        self._actual = datetime.now(UTC) - timedelta(days=1)

    def __call__(self) -> datetime:
        self._actual += timedelta(seconds=1)
        return self._actual


# Fabricas


async def _perfil(sesion_api, rol=RolPerfil.ARTISTA, *, dias=30) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(),
        handle=f"u{uuid.uuid4().hex[:12]}",
        nombre="Ana",
        rol=rol,
        categorias=[],
        created_at=datetime.now(UTC) - timedelta(days=dias),
    )
    sesion_api.add(perfil)
    await sesion_api.flush()
    return perfil


async def _publico(sesion_api, *, dias=30) -> Profile:
    return await _perfil(sesion_api, rol=RolPerfil.PUBLICO, dias=dias)


async def _servicio(sesion_api, artista, *, activo=True) -> Servicio:
    servicio_ = Servicio(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo="Retrato",
        precio_base=Decimal("25000.00"),
        tipo=TipoServicio.ENCARGO,
        activo=activo,
    )
    sesion_api.add(servicio_)
    await sesion_api.flush()
    return servicio_


async def _obra(sesion_api, artista, estado=EstadoObra.DISPONIBLE) -> Obra:
    obra = Obra(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo="Paisaje",
        estado=estado,
        precio=Decimal("40000.00"),
    )
    sesion_api.add(obra)
    await sesion_api.flush()
    return obra


async def _consulta(
    sesion_api,
    cliente_,
    artista,
    *,
    estado=EstadoConsulta.ABIERTA,
    creada=None,
) -> Consulta:
    """Una consulta puesta en la base, sin mensajes."""
    creada = creada or datetime.now(UTC) - timedelta(days=2)
    consulta = Consulta(
        id=uuid.uuid4(),
        cliente_id=cliente_.id,
        artista_id=artista.id,
        estado=estado,
        created_at=creada,
        ultimo_mensaje_at=creada,
    )
    sesion_api.add(consulta)
    await sesion_api.flush()
    return consulta


async def _mensaje(sesion_api, consulta, remitente, marca, texto="Hola") -> Mensaje:
    mensaje = Mensaje(
        id=uuid.uuid4(),
        consulta_id=consulta.id,
        remitente_id=remitente.id,
        texto=texto,
        created_at=marca,
    )
    consulta.ultimo_mensaje_at = marca
    sesion_api.add(mensaje)
    await sesion_api.flush()
    return mensaje


def _sin_token() -> None:
    app.dependency_overrides.pop(get_current_user_payload, None)


async def _abrir(cliente_http, artista, **datos):
    cuerpo = {"artista_id": str(artista.id), "texto": "Hola, me interesa", **datos}
    return await cliente_http.post(CONSULTAS, json=cuerpo)


def _ruta(consulta_id, sufijo="") -> str:
    return f"{CONSULTAS}/{consulta_id}{sufijo}"


async def _todos(cliente_http, ruta, tamano, **params) -> list[dict]:
    items, cursor = [], None
    while True:
        consulta = {
            "tamano": tamano,
            **params,
            **({"cursor": cursor} if cursor else {}),
        }
        pagina = (await cliente_http.get(ruta, params=consulta)).json()
        items += pagina["items"]
        cursor = pagina["siguiente_cursor"]
        if cursor is None:
            return items


def _ids(items) -> list[str]:
    return [i["id"] for i in items]


# Abrir


async def test_7_05_abrir_sobre_un_servicio(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    servicio_ = await _servicio(sesion_api, artista)
    comprador = await _publico(sesion_api)

    autenticar_como(comprador.id)
    r = await _abrir(
        cliente,
        artista,
        servicio_id=str(servicio_.id),
        presupuesto="50000.00",
        fecha_deseada="2026-12-15",
    )
    assert r.status_code == 201, r.text
    consulta = r.json()
    assert consulta["estado"] == "abierta"
    assert consulta["soy"] == "cliente"
    assert consulta["servicio_id"] == str(servicio_.id)
    assert Decimal(consulta["presupuesto"]) == Decimal("50000.00")
    assert consulta["fecha_deseada"] == "2026-12-15"
    assert consulta["ultimo_mensaje"]["es_mio"] is True
    assert consulta["ultimo_mensaje"]["texto"] == "Hola, me interesa"
    assert consulta["no_leidos"] == 0

    autenticar_como(artista.id)
    bandeja = (await cliente.get(CONSULTAS)).json()["items"]
    assert _ids(bandeja) == [consulta["id"]]
    assert bandeja[0]["soy"] == "artista"
    assert bandeja[0]["no_leidos"] == 1
    assert bandeja[0]["ultimo_mensaje"]["es_mio"] is False
    assert bandeja[0]["cliente"]["handle"] == comprador.handle


async def test_7_06_validaciones_al_abrir(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    otro_artista = await _perfil(sesion_api)
    publico = await _publico(sesion_api)
    comprador = await _publico(sesion_api)
    ajeno = await _servicio(sesion_api, otro_artista)
    inactivo = await _servicio(sesion_api, artista, activo=False)
    vendida = await _obra(sesion_api, artista, EstadoObra.VENDIDA)
    propio = await _servicio(sesion_api, artista)
    obra = await _obra(sesion_api, artista)

    autenticar_como(comprador.id)
    inexistente = await cliente.post(
        CONSULTAS, json={"artista_id": str(uuid.uuid4()), "texto": "Hola"}
    )
    assert inexistente.status_code == 404
    assert (await _abrir(cliente, publico)).status_code == 404
    r = await _abrir(cliente, artista, servicio_id=str(ajeno.id))
    assert r.status_code == 404
    r = await _abrir(cliente, artista, servicio_id=str(inactivo.id))
    assert r.status_code == 409
    assert (await _abrir(cliente, artista, obra_id=str(vendida.id))).status_code == 409
    r = await _abrir(cliente, artista, servicio_id=str(propio.id), obra_id=str(obra.id))
    assert r.status_code == 422
    assert (await _abrir(cliente, artista, presupuesto="0")).status_code == 422
    assert (await _abrir(cliente, artista, texto="   ")).status_code == 422

    autenticar_como(artista.id)
    assert (await _abrir(cliente, artista)).status_code == 409

    _sin_token()
    assert (await _abrir(cliente, artista)).status_code == 401

    filas = await sesion_api.execute(
        select(Consulta.id).where(Consulta.artista_id == artista.id)
    )
    assert filas.first() is None


async def test_7_07_consulta_repetida(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    servicio_ = await _servicio(sesion_api, artista)
    comprador = await _publico(sesion_api)
    autenticar_como(comprador.id)

    primera = await _abrir(
        cliente, artista, servicio_id=str(servicio_.id), presupuesto="50000"
    )
    assert primera.status_code == 201
    repetida = await _abrir(
        cliente,
        artista,
        servicio_id=str(servicio_.id),
        texto="Otra cosa",
        presupuesto="90000",
    )
    assert repetida.status_code == 200, repetida.text
    assert repetida.json()["id"] == primera.json()["id"]
    assert Decimal(repetida.json()["presupuesto"]) == Decimal("50000")
    assert repetida.json()["ultimo_mensaje"]["texto"] == "Otra cosa"
    historial = (await cliente.get(_ruta(primera.json()["id"], "/mensajes"))).json()
    assert len(historial["items"]) == 2

    # Sobre otra referencia es otra consulta
    general = await _abrir(cliente, artista)
    assert general.status_code == 201
    assert general.json()["id"] != primera.json()["id"]

    r = await cliente.post(_ruta(primera.json()["id"], "/descartar"))
    assert r.status_code == 200
    nueva = await _abrir(cliente, artista, servicio_id=str(servicio_.id))
    assert nueva.status_code == 201
    assert nueva.json()["id"] != primera.json()["id"]


async def test_7_08_limite_para_cuentas_nuevas(cliente, sesion_api, autenticar_como):
    artistas = [await _perfil(sesion_api) for _ in range(6)]

    reciente = await _publico(sesion_api, dias=2)
    autenticar_como(reciente.id)
    for artista in artistas[:5]:
        assert (await _abrir(cliente, artista)).status_code == 201
    # La repetida no cuenta: se agrega a la que ya existe
    assert (await _abrir(cliente, artistas[0])).status_code == 200
    sexta = await _abrir(cliente, artistas[5])
    assert sexta.status_code == 429, sexta.text
    assert "5 consultas cada 24 horas" in sexta.json()["detail"]

    vieja = await _publico(sesion_api, dias=8)
    autenticar_como(vieja.id)
    for artista in artistas:
        assert (await _abrir(cliente, artista)).status_code == 201

    # Las de hace 25 horas quedan fuera de la ventana
    otra_reciente = await _publico(sesion_api, dias=2)
    hace_25_horas = datetime.now(UTC) - timedelta(hours=25)
    for artista in artistas[:5]:
        await _consulta(sesion_api, otra_reciente, artista, creada=hace_25_horas)
    autenticar_como(otra_reciente.id)
    for artista in [await _perfil(sesion_api) for _ in range(5)]:
        assert (await _abrir(cliente, artista)).status_code == 201


async def test_7_09_aviso_suave(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    comprador = await _publico(sesion_api)
    autenticar_como(comprador.id)
    consulta = (await _abrir(cliente, artista)).json()
    assert consulta["ultimo_mensaje"]["aviso"] is None
    assert consulta["ultimo_mensaje"]["aviso_contacto"] is False

    texto = "Te pago por SINPE y listo"
    r = await cliente.post(_ruta(consulta["id"], "/mensajes"), json={"texto": texto})
    assert r.status_code == 201, r.text
    mensaje = r.json()
    assert mensaje["texto"] == texto
    assert mensaje["aviso_contacto"] is True
    assert mensaje["aviso"] == AVISO_PAGO_FUERA
    assert mensaje["es_mio"] is True

    autenticar_como(artista.id)
    historial = (await cliente.get(_ruta(consulta["id"], "/mensajes"))).json()["items"]
    assert historial[0]["id"] == mensaje["id"]
    assert historial[0]["aviso"] == AVISO_PAGO_FUERA
    assert historial[0]["es_mio"] is False
    assert historial[1]["aviso"] is None


async def test_7_10_acceso_y_estados(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    comprador = await _publico(sesion_api)
    tercero = await _publico(sesion_api)
    abierta = await _consulta(sesion_api, comprador, artista)

    autenticar_como(tercero.id)
    respuestas = [
        await cliente.get(_ruta(abierta.id)),
        await cliente.post(_ruta(abierta.id, "/descartar")),
        await cliente.put(_ruta(abierta.id, "/leido")),
        await cliente.get(_ruta(abierta.id, "/mensajes")),
        await cliente.get(_ruta(abierta.id, "/mensajes/nuevos")),
        await cliente.post(_ruta(abierta.id, "/mensajes"), json={"texto": "Hola"}),
    ]
    assert [r.status_code for r in respuestas] == [404] * 6
    assert all(r.json()["detail"] == "Consulta no encontrada" for r in respuestas)

    descartada = await _consulta(
        sesion_api, comprador, artista, estado=EstadoConsulta.DESCARTADA
    )
    convertida = await _consulta(
        sesion_api, comprador, artista, estado=EstadoConsulta.CONVERTIDA
    )
    autenticar_como(artista.id)
    r = await cliente.post(_ruta(descartada.id, "/mensajes"), json={"texto": "Hola"})
    assert r.status_code == 409
    r = await cliente.post(_ruta(convertida.id, "/mensajes"), json={"texto": "Hola"})
    assert r.status_code == 201


async def test_7_11_historial_y_nuevos(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    comprador = await _publico(sesion_api)
    consulta = await _consulta(sesion_api, comprador, artista)
    reloj = Reloj()
    mensajes = [
        await _mensaje(
            sesion_api, consulta, comprador if i % 2 else artista, reloj(), f"m{i}"
        )
        for i in range(1, 26)
    ]
    esperados = [str(m.id) for m in mensajes]

    autenticar_como(comprador.id)
    paginas, cursor = [], None
    while True:
        params = {"tamano": 10, **({"cursor": cursor} if cursor else {})}
        pagina = (
            await cliente.get(_ruta(consulta.id, "/mensajes"), params=params)
        ).json()
        paginas.append(pagina["items"])
        cursor = pagina["siguiente_cursor"]
        if cursor is None:
            break
    assert [len(p) for p in paginas] == [10, 10, 5]
    historial = [i for p in paginas for i in p]
    assert _ids(historial) == esperados[::-1]

    decimo = next(i for i in historial if i["texto"] == "m10")
    nuevos = (
        await cliente.get(
            _ruta(consulta.id, "/mensajes/nuevos"), params={"cursor": decimo["cursor"]}
        )
    ).json()
    assert _ids(nuevos["items"]) == esperados[10:]
    assert nuevos["siguiente_cursor"] is None

    ultimo = nuevos["items"][-1]
    vacio = (
        await cliente.get(
            _ruta(consulta.id, "/mensajes/nuevos"), params={"cursor": ultimo["cursor"]}
        )
    ).json()
    assert vacio == {"items": [], "siguiente_cursor": None}

    desde_el_inicio = await _todos(cliente, _ruta(consulta.id, "/mensajes/nuevos"), 7)
    assert _ids(desde_el_inicio) == esperados


async def test_7_12_marcas_estrictamente_crecientes(sesion_api):
    artista = await _perfil(sesion_api)
    comprador = await _publico(sesion_api)
    consulta = await _consulta(sesion_api, comprador, artista)
    ahora = datetime.now(UTC)

    primero = await servicio.enviar(sesion_api, comprador, consulta.id, "uno", ahora)
    segundo = await servicio.enviar(sesion_api, artista, consulta.id, "dos", ahora)

    assert primero.mensaje.created_at == ahora
    assert segundo.mensaje.created_at > primero.mensaje.created_at
    await sesion_api.refresh(consulta)
    assert consulta.ultimo_mensaje_at == segundo.mensaje.created_at


async def test_7_13_no_leidos(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    comprador = await _publico(sesion_api)

    autenticar_como(comprador.id)
    consulta = (await _abrir(cliente, artista)).json()
    for texto in ("dos", "tres"):
        r = await cliente.post(
            _ruta(consulta["id"], "/mensajes"), json={"texto": texto}
        )
        assert r.status_code == 201
    assert (await cliente.get(_ruta(consulta["id"]))).json()["no_leidos"] == 0
    assert (await cliente.get(NO_LEIDOS)).json() == {"consultas": 0, "mensajes": 0}

    autenticar_como(artista.id)
    assert (await cliente.get(_ruta(consulta["id"]))).json()["no_leidos"] == 3
    assert (await cliente.get(NO_LEIDOS)).json() == {"consultas": 1, "mensajes": 3}

    r = await cliente.put(_ruta(consulta["id"], "/leido"))
    assert r.status_code == 204
    assert (await cliente.get(_ruta(consulta["id"]))).json()["no_leidos"] == 0
    assert (await cliente.get(NO_LEIDOS)).json() == {"consultas": 0, "mensajes": 0}

    # La respuesta del artista solo cuenta para el cliente
    r = await cliente.post(_ruta(consulta["id"], "/mensajes"), json={"texto": "Dale"})
    assert r.status_code == 201
    assert (await cliente.get(NO_LEIDOS)).json() == {"consultas": 0, "mensajes": 0}
    autenticar_como(comprador.id)
    assert (await cliente.get(_ruta(consulta["id"]))).json()["no_leidos"] == 1
    assert (await cliente.get(NO_LEIDOS)).json() == {"consultas": 1, "mensajes": 1}


async def test_7_14_bandeja(cliente, sesion_api, autenticar_como):
    yo = await _perfil(sesion_api)
    reloj = Reloj()
    como_cliente = await _consulta(sesion_api, yo, await _perfil(sesion_api))
    await _mensaje(sesion_api, como_cliente, yo, reloj())
    otro = await _publico(sesion_api)
    vieja = await _consulta(sesion_api, otro, yo)
    await _mensaje(sesion_api, vieja, otro, reloj())
    tercero = await _publico(sesion_api)
    media = await _consulta(sesion_api, tercero, yo)
    await _mensaje(sesion_api, media, tercero, reloj())

    autenticar_como(yo.id)
    bandeja = (await cliente.get(CONSULTAS)).json()["items"]
    assert _ids(bandeja) == [str(media.id), str(vieja.id), str(como_cliente.id)]

    r = await cliente.post(_ruta(vieja.id, "/mensajes"), json={"texto": "Sigo aca"})
    assert r.status_code == 201
    bandeja = (await cliente.get(CONSULTAS)).json()["items"]
    assert _ids(bandeja) == [str(vieja.id), str(media.id), str(como_cliente.id)]
    assert bandeja[0]["ultimo_mensaje"]["texto"] == "Sigo aca"
    assert bandeja[0]["ultimo_mensaje"]["es_mio"] is True

    clientes = (await cliente.get(CONSULTAS, params={"como": "cliente"})).json()
    assert _ids(clientes["items"]) == [str(como_cliente.id)]
    assert clientes["items"][0]["soy"] == "cliente"
    artistas = (await cliente.get(CONSULTAS, params={"como": "artista"})).json()
    assert _ids(artistas["items"]) == [str(vieja.id), str(media.id)]

    assert (await cliente.post(_ruta(media.id, "/descartar"))).status_code == 200
    descartadas = (await cliente.get(CONSULTAS, params={"estado": "descartada"})).json()
    assert _ids(descartadas["items"]) == [str(media.id)]
    abiertas = (await cliente.get(CONSULTAS, params={"estado": "abierta"})).json()
    assert str(media.id) not in _ids(abiertas["items"])

    recorrido = await _todos(cliente, CONSULTAS, 2)
    assert _ids(recorrido) == [str(vieja.id), str(media.id), str(como_cliente.id)]


async def test_7_14_bandeja_sin_n_mas_1(cliente, sesion_api, autenticar_como, test_db):
    reloj = Reloj()

    async def _bandeja_con(cuantas: int) -> int:
        lector = await _perfil(sesion_api)
        for _ in range(cuantas):
            remitente = await _publico(sesion_api)
            consulta = await _consulta(sesion_api, remitente, lector)
            await _mensaje(sesion_api, consulta, remitente, reloj())
        contador = 0

        def _contar_sentencia(*_args) -> None:
            nonlocal contador
            contador += 1

        autenticar_como(lector.id)
        event.listen(test_db.sync_engine, "before_cursor_execute", _contar_sentencia)
        try:
            r = await cliente.get(CONSULTAS)
        finally:
            event.remove(
                test_db.sync_engine, "before_cursor_execute", _contar_sentencia
            )
        items = r.json()["items"]
        assert len(items) == cuantas
        assert all(i["no_leidos"] == 1 for i in items)
        return contador

    assert await _bandeja_con(2) == await _bandeja_con(8)


async def test_7_15_descartar(cliente, sesion_api, autenticar_como):
    artista = await _perfil(sesion_api)
    comprador = await _publico(sesion_api)
    abierta = await _consulta(sesion_api, comprador, artista)
    cotizada = await _consulta(
        sesion_api, comprador, artista, estado=EstadoConsulta.COTIZADA
    )

    autenticar_como(artista.id)
    r = await cliente.post(_ruta(abierta.id, "/descartar"))
    assert r.status_code == 200
    assert r.json()["estado"] == "descartada"
    assert (await cliente.post(_ruta(abierta.id, "/descartar"))).status_code == 409

    autenticar_como(comprador.id)
    assert (await cliente.post(_ruta(cotizada.id, "/descartar"))).status_code == 409


async def test_7_16_rutas(cliente, sesion_api, autenticar_como):
    rutas = app.openapi()["paths"]
    for sufijo in (
        "",
        "/no-leidos",
        "/{consulta_id}",
        "/{consulta_id}/descartar",
        "/{consulta_id}/leido",
        "/{consulta_id}/mensajes",
        "/{consulta_id}/mensajes/nuevos",
    ):
        assert f"{CONSULTAS}{sufijo}" in rutas

    autenticar_como((await _publico(sesion_api)).id)
    r = await cliente.get(NO_LEIDOS)
    assert r.status_code == 200
    assert r.json() == {"consultas": 0, "mensajes": 0}


# RLS


async def test_7_17_rls_sin_politicas(sesion_api):
    filas = await sesion_api.execute(
        text(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relname IN ('consultas', 'mensajes') AND relkind = 'r'"
        )
    )
    assert dict(filas.all()) == {"consultas": True, "mensajes": True}
    politicas = await sesion_api.execute(text("SELECT count(*) FROM pg_policies"))
    assert politicas.scalar_one() == 0
