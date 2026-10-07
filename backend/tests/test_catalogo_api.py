"""Endpoints del catalogo contra una base migrada. Cada prueba termina en rollback."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.core.config import settings
from src.domain.politicas import PoliticasPedido
from src.models import (
    EstadoMedia,
    EstadoObra,
    MediaAsset,
    Obra,
    PlanArtista,
    Profile,
    RolPerfil,
    Servicio,
    TipoServicio,
)
from src.services import pedidos as servicio_pedidos

API = settings.API_V1_STR
WEBP = "image/webp"
BUCKET = settings.BUCKET_MEDIOS
POLITICAS = PoliticasPedido.desde_config(settings)
PRECIO = Decimal("15000.00")


@pytest.fixture
def cliente(async_client, sesion_api, almacenamiento_falso):  # noqa: ARG001  por su efecto
    """Cliente HTTP con la base y el almacenamiento de prueba ya puestos."""
    return async_client


# Fabricas


async def _perfil(
    sesion_api, rol=RolPerfil.ARTISTA, plan=PlanArtista.TALLER
) -> Profile:
    perfil = Profile(
        id=uuid.uuid4(),
        handle=f"u{uuid.uuid4().hex[:12]}",
        nombre="Ana",
        rol=rol,
        plan=plan,
    )
    sesion_api.add(perfil)
    await sesion_api.flush()
    return perfil


async def _artista(sesion_api, autenticar_como, plan=PlanArtista.TALLER) -> Profile:
    artista = await _perfil(sesion_api, plan=plan)
    autenticar_como(artista.id)
    return artista


async def _medio(
    sesion_api,
    almacenamiento,
    propietario,
    *,
    confirmado=True,
    obra_id=None,
    borrado=False,
) -> MediaAsset:
    """Un medio como lo deja el lote 5: confirmado tiene `subido_en` y su objeto."""
    medio_id = uuid.uuid4()
    ruta = f"{propietario.id}/{medio_id}.webp"
    ahora = datetime.now(UTC)
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
        subido_en=ahora if confirmado else None,
        obra_id=obra_id,
        deleted_at=ahora if borrado else None,
    )
    sesion_api.add(medio)
    await sesion_api.flush()
    await almacenamiento.subir(BUCKET, ruta, b"imagen", WEBP)
    await almacenamiento.subir(BUCKET, medio.thumbnail_path, b"mini", WEBP)
    return medio


async def _obra_en_base(
    sesion_api,
    artista,
    *,
    estado=EstadoObra.DISPONIBLE,
    precio=PRECIO,
    titulo="Colibri",
) -> Obra:
    obra = Obra(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo=titulo,
        estado=estado,
        precio=precio if estado != EstadoObra.EXHIBICION else None,
    )
    sesion_api.add(obra)
    await sesion_api.flush()
    return obra


async def _servicio_en_base(sesion_api, artista, *, activo=True) -> Servicio:
    servicio = Servicio(
        id=uuid.uuid4(),
        artista_id=artista.id,
        titulo="Retrato A4",
        precio_base=PRECIO,
        tipo=TipoServicio.ENCARGO,
        activo=activo,
    )
    sesion_api.add(servicio)
    await sesion_api.flush()
    return servicio


def _cuerpo_obra(medios, **extra) -> dict:
    cuerpo = {"titulo": "Colibri en acuarela", "medios": [str(m.id) for m in medios]}
    cuerpo.update(extra)
    return cuerpo


async def _crear_obra(cliente, medios, **extra):
    return await cliente.post(f"{API}/obras", json=_cuerpo_obra(medios, **extra))


async def _recargar(sesion_api, modelo, id_):
    return await sesion_api.get(modelo, id_, populate_existing=True)


# Obras


async def test_04_crear_obra_en_exhibicion(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    publico = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
    autenticar_como(publico.id)
    medio_ajeno = await _medio(sesion_api, almacenamiento_falso, publico)
    assert (await _crear_obra(cliente, [medio_ajeno])).status_code == 403

    artista = await _artista(sesion_api, autenticar_como)
    primero = await _medio(sesion_api, almacenamiento_falso, artista)
    segundo = await _medio(sesion_api, almacenamiento_falso, artista)
    r = await _crear_obra(cliente, [primero, segundo])
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == EstadoObra.EXHIBICION
    assert cuerpo["precio"] is None
    assert cuerpo["artista_handle"] == artista.handle
    assert [m["id"] for m in cuerpo["medios"]] == [str(primero.id), str(segundo.id)]
    assert all(m["miniatura_url"] for m in cuerpo["medios"])

    obra_id = uuid.UUID(cuerpo["id"])
    for posicion, medio in enumerate((primero, segundo)):
        fila = await _recargar(sesion_api, MediaAsset, medio.id)
        assert fila.obra_id == obra_id
        assert fila.orden == posicion


async def test_05_medios_invalidos(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    otro = await _perfil(sesion_api)
    obra_previa = await _obra_en_base(sesion_api, artista)

    ajeno = await _medio(sesion_api, almacenamiento_falso, otro)
    sin_confirmar = await _medio(
        sesion_api, almacenamiento_falso, artista, confirmado=False
    )
    asociado = await _medio(
        sesion_api, almacenamiento_falso, artista, obra_id=obra_previa.id
    )
    borrado = await _medio(sesion_api, almacenamiento_falso, artista, borrado=True)
    bueno = await _medio(sesion_api, almacenamiento_falso, artista)

    for medios in ([ajeno], [sin_confirmar], [asociado], [borrado], [bueno, bueno]):
        r = await _crear_obra(cliente, medios)
        assert r.status_code in (409, 422), (medios, r.status_code, r.text)

    assert (
        await cliente.post(
            f"{API}/obras", json={"titulo": "Sin imagenes", "medios": []}
        )
    ).status_code == 422

    once = [await _medio(sesion_api, almacenamiento_falso, artista) for _ in range(11)]
    assert (await _crear_obra(cliente, once)).status_code == 422

    # Ningun medio quedo asociado a una obra nueva
    for medio in (ajeno, sin_confirmar, borrado, bueno, *once):
        fila = await _recargar(sesion_api, MediaAsset, medio.id)
        assert fila.obra_id is None
        assert fila.orden is None
    assert (await _recargar(sesion_api, MediaAsset, asociado.id)).obra_id == (
        obra_previa.id
    )


async def test_06_limite_de_obras_disponibles(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    for numero in range(5):
        medio = await _medio(sesion_api, almacenamiento_falso, artista)
        r = await _crear_obra(
            cliente, [medio], estado=EstadoObra.DISPONIBLE, precio=str(PRECIO)
        )
        assert r.status_code == 201, (numero, r.text)

    sexto = await _medio(sesion_api, almacenamiento_falso, artista)
    r = await _crear_obra(
        cliente, [sexto], estado=EstadoObra.DISPONIBLE, precio=str(PRECIO)
    )
    assert r.status_code == 409, r.text
    assert (await _recargar(sesion_api, MediaAsset, sexto.id)).obra_id is None

    # La galeria en exhibicion nunca se limita
    assert (await _crear_obra(cliente, [sexto])).status_code == 201

    estudio = await _artista(sesion_api, autenticar_como, plan=PlanArtista.ESTUDIO)
    for _ in range(5):
        await _obra_en_base(sesion_api, estudio)
    medio = await _medio(sesion_api, almacenamiento_falso, estudio)
    r = await _crear_obra(
        cliente, [medio], estado=EstadoObra.DISPONIBLE, precio=str(PRECIO)
    )
    assert r.status_code == 201, r.text


async def test_07_bajar_de_plan_no_oculta_nada(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como, plan=PlanArtista.ESTUDIO)
    obras = [await _obra_en_base(sesion_api, artista) for _ in range(6)]
    artista.plan = PlanArtista.TALLER
    await sesion_api.flush()

    r = await cliente.get(f"{API}/artistas/{artista.handle}/obras")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 6

    medio = await _medio(sesion_api, almacenamiento_falso, artista)
    r = await _crear_obra(
        cliente, [medio], estado=EstadoObra.DISPONIBLE, precio=str(PRECIO)
    )
    assert r.status_code == 409, r.text

    for obra in obras[:2]:
        r = await cliente.patch(
            f"{API}/obras/{obra.id}", json={"estado": EstadoObra.EXHIBICION}
        )
        assert r.status_code == 200, r.text
        assert r.json()["precio"] is None

    r = await _crear_obra(
        cliente, [medio], estado=EstadoObra.DISPONIBLE, precio=str(PRECIO)
    )
    assert r.status_code == 201, r.text


async def test_08_precio_y_contacto(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    medio = await _medio(sesion_api, almacenamiento_falso, artista)

    bajo = settings.MONTO_MINIMO_PEDIDO - Decimal("0.01")
    r = await _crear_obra(
        cliente, [medio], estado=EstadoObra.DISPONIBLE, precio=str(bajo)
    )
    assert r.status_code == 422, r.text

    r = await _crear_obra(cliente, [medio], descripcion="Escribime al 8888-8888")
    assert r.status_code == 422, r.text

    # Sin precio no se puede nacer disponible
    r = await _crear_obra(cliente, [medio], estado=EstadoObra.DISPONIBLE)
    assert r.status_code == 409, r.text


async def test_09_obra_con_pedido_activo(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    medio = await _medio(sesion_api, almacenamiento_falso, artista)
    r = await _crear_obra(
        cliente, [medio], estado=EstadoObra.DISPONIBLE, precio=str(PRECIO)
    )
    assert r.status_code == 201, r.text
    obra_id = uuid.UUID(r.json()["id"])

    comprador = await _perfil(sesion_api, rol=RolPerfil.PUBLICO)
    await servicio_pedidos.crear_pedido_obra_disponible(
        sesion_api,
        obra_id=obra_id,
        cliente_id=comprador.id,
        pasarela="falsa",
        politicas=POLITICAS,
    )
    await sesion_api.flush()

    ruta = f"{API}/obras/{obra_id}"
    assert (await cliente.patch(ruta, json={"precio": "20000.00"})).status_code == 409
    assert (
        await cliente.patch(ruta, json={"estado": EstadoObra.EXHIBICION})
    ).status_code == 409
    otro = await _medio(sesion_api, almacenamiento_falso, artista)
    assert (
        await cliente.patch(ruta, json={"medios": [str(otro.id)]})
    ).status_code == 409
    assert (await cliente.delete(ruta)).status_code == 409

    r = await cliente.patch(ruta, json={"titulo": "Colibri al amanecer"})
    assert r.status_code == 200, r.text
    assert r.json()["titulo"] == "Colibri al amanecer"


async def test_10_obra_vendida_es_de_solo_lectura(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    obra = await _obra_en_base(sesion_api, artista)
    await _medio(sesion_api, almacenamiento_falso, artista, obra_id=obra.id)
    obra.estado = EstadoObra.VENDIDA
    await sesion_api.flush()

    ruta = f"{API}/obras/{obra.id}"
    assert (
        await cliente.patch(ruta, json={"estado": EstadoObra.DISPONIBLE})
    ).status_code == 409
    assert (await cliente.patch(ruta, json={"precio": "99000.00"})).status_code == 409

    r = await cliente.patch(ruta, json={"titulo": "Vendida a buen precio"})
    assert r.status_code == 200, r.text
    # Una obra vendida no muestra precio: ya no se vende
    assert r.json()["precio"] is None


async def test_11_borrar_obra_sin_pedidos(
    cliente, sesion_api, autenticar_como, almacenamiento_falso
):
    artista = await _artista(sesion_api, autenticar_como)
    medio = await _medio(sesion_api, almacenamiento_falso, artista)
    r = await _crear_obra(cliente, [medio])
    assert r.status_code == 201, r.text
    obra_id = uuid.UUID(r.json()["id"])

    assert almacenamiento_falso.existe(BUCKET, medio.storage_path)
    assert (await cliente.delete(f"{API}/obras/{obra_id}")).status_code == 204

    fila = await _recargar(sesion_api, MediaAsset, medio.id)
    assert fila.deleted_at is not None
    assert not almacenamiento_falso.existe(BUCKET, medio.storage_path)
    assert not almacenamiento_falso.existe(BUCKET, medio.thumbnail_path)
    assert (await cliente.get(f"{API}/obras/{obra_id}")).status_code == 404
    r = await cliente.get(f"{API}/artistas/{artista.handle}/obras")
    assert r.json()["items"] == []


async def test_12_listado_publico_paginado(cliente, sesion_api, autenticar_como):
    artista = await _artista(sesion_api, autenticar_como)
    for numero in range(25):
        estado = EstadoObra.DISPONIBLE if numero % 5 == 0 else EstadoObra.EXHIBICION
        await _obra_en_base(
            sesion_api, artista, estado=estado, titulo=f"Obra {numero:02d}"
        )

    ruta = f"{API}/artistas/{artista.handle}/obras"
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
    ids = [o["id"] for o in todos]
    assert len(set(ids)) == 25
    fechas = [o["created_at"] for o in todos]
    assert fechas == sorted(fechas, reverse=True)
    for obra in todos:
        esta_disponible = obra["estado"] == EstadoObra.DISPONIBLE
        assert (obra["precio"] is not None) is esta_disponible

    assert (await cliente.get(ruta, params={"cursor": "no-sirve"})).status_code == 422
    assert (await cliente.get(f"{API}/artistas/nadie/obras")).status_code == 404


# Servicios


async def test_13_limite_de_servicios_activos(cliente, sesion_api, autenticar_como):
    await _artista(sesion_api, autenticar_como)
    cuerpo = {
        "titulo": "Retrato A4",
        "precio_base": str(PRECIO),
        "tipo": TipoServicio.ENCARGO,
    }
    for _ in range(2):
        r = await cliente.post(f"{API}/servicios", json=cuerpo)
        assert r.status_code == 201, r.text
        assert r.json()["activo"] is True

    assert (await cliente.post(f"{API}/servicios", json=cuerpo)).status_code == 409

    r = await cliente.post(f"{API}/servicios", json={**cuerpo, "activo": False})
    assert r.status_code == 201, r.text
    inactivo_id = r.json()["id"]
    r = await cliente.patch(f"{API}/servicios/{inactivo_id}", json={"activo": True})
    assert r.status_code == 409, r.text

    await _artista(sesion_api, autenticar_como, plan=PlanArtista.ESTUDIO)
    for _ in range(3):
        assert (await cliente.post(f"{API}/servicios", json=cuerpo)).status_code == 201


async def test_14_vitrina_y_servicios_propios(cliente, sesion_api, autenticar_como):
    artista = await _artista(sesion_api, autenticar_como)
    activo = await _servicio_en_base(sesion_api, artista)
    inactivo = await _servicio_en_base(sesion_api, artista, activo=False)

    publicos = (await cliente.get(f"{API}/artistas/{artista.handle}/servicios")).json()[
        "items"
    ]
    assert [s["id"] for s in publicos] == [str(activo.id)]

    mios = (await cliente.get(f"{API}/servicios/mios")).json()["items"]
    assert {s["id"] for s in mios} == {str(activo.id), str(inactivo.id)}

    assert (await cliente.get(f"{API}/servicios/{activo.id}")).status_code == 200
    assert (await cliente.get(f"{API}/servicios/{inactivo.id}")).status_code == 404

    ajeno = await _servicio_en_base(sesion_api, await _perfil(sesion_api))
    r = await cliente.patch(f"{API}/servicios/{ajeno.id}", json={"titulo": "Mio ahora"})
    assert r.status_code == 404, r.text

    assert (await cliente.delete(f"{API}/servicios/{inactivo.id}")).status_code == 204
    mios = (await cliente.get(f"{API}/servicios/mios")).json()["items"]
    assert [s["id"] for s in mios] == [str(activo.id)]


async def test_15_limites_del_plan(cliente, sesion_api, autenticar_como):
    artista = await _artista(sesion_api, autenticar_como)
    await _servicio_en_base(sesion_api, artista)
    await _servicio_en_base(sesion_api, artista, activo=False)
    await _obra_en_base(sesion_api, artista)
    await _obra_en_base(sesion_api, artista, estado=EstadoObra.EXHIBICION)

    cuerpo = (await cliente.get(f"{API}/catalogo/limites")).json()
    assert cuerpo == {
        "plan": PlanArtista.TALLER,
        "servicios_activos": 1,
        "limite_servicios_activos": 2,
        "obras_disponibles": 1,
        "limite_obras_disponibles": 5,
    }

    estudio = await _artista(sesion_api, autenticar_como, plan=PlanArtista.ESTUDIO)
    await _obra_en_base(sesion_api, estudio)
    cuerpo = (await cliente.get(f"{API}/catalogo/limites")).json()
    assert cuerpo == {
        "plan": PlanArtista.ESTUDIO,
        "servicios_activos": 0,
        "limite_servicios_activos": None,
        "obras_disponibles": 1,
        "limite_obras_disponibles": None,
    }
