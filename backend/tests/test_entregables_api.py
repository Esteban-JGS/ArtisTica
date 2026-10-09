"""Archivo final del encargo en el bucket privado, por la API, contra una base
migrada, el almacenamiento falso y la pasarela falsa. Cada prueba termina en
rollback."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.core.config import Settings, settings
from src.models import MediaAsset
from src.storage.contrato import ErrorAlmacenamiento
from src.storage.falso import AlmacenamientoFalso
from tests.test_pedidos_api import API, encargo, medio, perfil, ruta

PNG = "image/png"
CONTENIDO = b"\x89PNG final sin marca de agua"
CAMPOS_FINAL = {"id", "nota", "created_at", "content_type"}


@pytest.fixture
def cliente(async_client, sesion_api, pasarela_falsa, almacenamiento_falso):  # noqa: ARG001  por su efecto
    return async_client


# Ayudas


def ruta_descarga(pedido_id, entregable_id) -> str:
    return ruta(pedido_id, f"/entregables/{entregable_id}/descarga")


async def pedir_subida(http, pedido_id):
    return await http.post(
        ruta(pedido_id, "/entregables/subida"),
        json={"content_type": PNG, "tamano_bytes": len(CONTENIDO)},
    )


async def entregar_final(http, pedido_id, medio_id, nota=None):
    cuerpo = {"medio_id": str(medio_id)}
    if nota is not None:
        cuerpo["nota"] = nota
    return await http.post(ruta(pedido_id, "/entregables/final"), json=cuerpo)


async def subir_final(http, almacenamiento: AlmacenamientoFalso, pedido_id) -> str:
    """Lo que hace la app: pide la subida, sube con la URL firmada y confirma."""
    r = await pedir_subida(http, pedido_id)
    assert r.status_code == 201, r.text
    subida = r.json()
    almacenamiento.simular_subida(subida["bucket"], subida["ruta"], CONTENIDO, PNG)
    r = await http.post(f"{API}/medios/{subida['medio_id']}/confirmar")
    assert r.status_code == 200, r.text
    return subida["medio_id"]


async def medio_privado(sesion_api, propietario) -> MediaAsset:
    nuevo = await medio(sesion_api, propietario)
    nuevo.bucket = settings.BUCKET_ENTREGABLES
    await sesion_api.flush()
    return nuevo


async def medio_db(sesion_api, medio_id) -> MediaAsset:
    return await sesion_api.get(
        MediaAsset, uuid.UUID(str(medio_id)), populate_existing=True
    )


# 4. Camino feliz


async def test_8c_04_camino_feliz(
    cliente, autenticar_como, sesion_api, pasarela_falsa, almacenamiento_falso
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    autenticar_como(escena.artista.id)

    r = await pedir_subida(http, escena.pedido_id)
    assert r.status_code == 201, r.text
    assert r.json()["bucket"] == settings.BUCKET_ENTREGABLES
    medio_id = r.json()["medio_id"]
    assert (await medio_db(s, medio_id)).bucket == settings.BUCKET_ENTREGABLES
    subida = r.json()
    almacenamiento_falso.simular_subida(
        subida["bucket"], subida["ruta"], CONTENIDO, PNG
    )
    r = await http.post(f"{API}/medios/{medio_id}/confirmar")
    assert r.status_code == 200, r.text

    r = await entregar_final(http, escena.pedido_id, medio_id, nota="Version final")
    assert r.status_code == 201, r.text
    (final,) = r.json()["finales"]
    assert set(final) == CAMPOS_FINAL
    assert final["nota"] == "Version final"
    assert final["content_type"] == PNG
    # Puede haber varios
    otro = await subir_final(http, almacenamiento_falso, escena.pedido_id)
    r = await entregar_final(http, escena.pedido_id, otro)
    assert r.status_code == 201, r.text
    assert len(r.json()["finales"]) == 2

    vigencia = timedelta(seconds=settings.DESCARGA_FIRMADA_SEGUNDOS)
    for quien in (escena.comprador, escena.artista):
        autenticar_como(quien.id)
        antes = datetime.now(UTC)
        r = await http.get(ruta_descarga(escena.pedido_id, final["id"]))
        despues = datetime.now(UTC)
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "no-store"
        descarga = r.json()
        assert set(descarga) == {"url", "expira_en"}
        assert f"/firmada/{settings.BUCKET_ENTREGABLES}/" in descarga["url"]
        expira_en = datetime.fromisoformat(descarga["expira_en"])
        assert antes + vigencia <= expira_en <= despues + vigencia

    # El detalle trae los finales sin URL, ni publica ni firmada
    autenticar_como(escena.comprador.id)
    r = await http.get(ruta(escena.pedido_id))
    assert r.status_code == 200, r.text
    assert all(set(f) == CAMPOS_FINAL for f in r.json()["finales"])
    ruta_objeto = (await medio_db(s, medio_id)).storage_path
    assert ruta_objeto not in r.text


# 5. Antes de pagar


@pytest.mark.parametrize("hasta", ["en_proceso", "vista_previa_entregada"])
async def test_8c_05_antes_de_pagar(
    cliente, autenticar_como, sesion_api, pasarela_falsa, hasta
):
    s, http = sesion_api, cliente
    escena = await encargo(http, autenticar_como, s, pasarela_falsa, hasta=hasta)
    autenticar_como(escena.artista.id)

    r = await pedir_subida(http, escena.pedido_id)
    assert r.status_code == 409, r.text
    privado = await medio_privado(s, escena.artista)
    r = await entregar_final(http, escena.pedido_id, privado.id)
    assert r.status_code == 409, r.text


# 6. Permisos


async def test_8c_06_permisos(
    cliente, autenticar_como, sesion_api, pasarela_falsa, almacenamiento_falso
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    autenticar_como(escena.artista.id)
    medio_id = await subir_final(http, almacenamiento_falso, escena.pedido_id)
    r = await entregar_final(http, escena.pedido_id, medio_id)
    final_id = r.json()["finales"][0]["id"]
    otro_medio = await medio_privado(s, escena.artista)

    autenticar_como((await perfil(s)).id)
    assert (await pedir_subida(http, escena.pedido_id)).status_code == 404
    r = await entregar_final(http, escena.pedido_id, otro_medio.id)
    assert r.status_code == 404
    assert (
        await http.get(ruta_descarga(escena.pedido_id, final_id))
    ).status_code == 404

    autenticar_como(escena.comprador.id)
    assert (await pedir_subida(http, escena.pedido_id)).status_code == 403
    r = await entregar_final(http, escena.pedido_id, otro_medio.id)
    assert r.status_code == 403

    # Un entregable de otro pedido no se descarga por este
    ajena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    autenticar_como(ajena.comprador.id)
    r = await http.get(ruta_descarga(ajena.pedido_id, final_id))
    assert r.status_code == 404


# 7. Buckets cruzados


async def test_8c_07_buckets_cruzados(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    pagado = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    autenticar_como(pagado.artista.id)
    publico = await medio(s, pagado.artista)
    r = await entregar_final(http, pagado.pedido_id, publico.id)
    assert r.status_code == 409, r.text

    en_proceso = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="en_proceso"
    )
    autenticar_como(en_proceso.artista.id)
    privado = await medio_privado(s, en_proceso.artista)
    r = await http.post(
        ruta(en_proceso.pedido_id, "/vistas-previas"),
        json={"medio_id": str(privado.id)},
    )
    assert r.status_code == 409, r.text


# 8. Descargar una vista previa


async def test_8c_08_descargar_una_vista_previa(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    autenticar_como(escena.comprador.id)
    (vista,) = (await http.get(ruta(escena.pedido_id))).json()["vistas_previas"]

    r = await http.get(ruta_descarga(escena.pedido_id, vista["id"]))
    assert r.status_code == 409, r.text
    r = await http.get(ruta_descarga(escena.pedido_id, uuid.uuid4()))
    assert r.status_code == 404, r.text


# 9. DT24


async def test_8c_09_un_entregable_no_va_a_una_obra_ni_a_una_publicacion(
    cliente, autenticar_como, sesion_api, pasarela_falsa
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="con_vista_previa"
    )
    autenticar_como(escena.artista.id)
    (vista,) = (await http.get(ruta(escena.pedido_id))).json()["vistas_previas"]
    entregado = vista["imagen"]["id"]

    r = await http.post(
        f"{API}/obras", json={"titulo": "Colibri", "medios": [entregado]}
    )
    assert r.status_code == 409, r.text
    r = await http.post(
        f"{API}/publicaciones", json={"texto": "Proceso", "medios": [entregado]}
    )
    assert r.status_code == 409, r.text

    # Un medio suelto del mismo artista si sirve
    suelto = await medio(s, escena.artista)
    r = await http.post(
        f"{API}/obras", json={"titulo": "Colibri", "medios": [str(suelto.id)]}
    )
    assert r.status_code == 201, r.text


# DT26


async def test_8d_10_medio_privado_sin_url_publica(
    cliente, autenticar_como, sesion_api, pasarela_falsa, almacenamiento_falso
):
    s, http = sesion_api, cliente
    escena = await encargo(
        http, autenticar_como, s, pasarela_falsa, hasta="saldo_pagado"
    )
    autenticar_como(escena.artista.id)

    r = await pedir_subida(http, escena.pedido_id)
    privada = r.json()
    almacenamiento_falso.simular_subida(
        privada["bucket"], privada["ruta"], CONTENIDO, PNG
    )
    r = await http.post(f"{API}/medios/{privada['medio_id']}/confirmar")
    assert r.status_code == 200, r.text
    assert r.json()["subido"] is True
    assert r.json()["url"] is None
    assert r.json()["miniatura_url"] is None
    # Tampoco con miniatura
    privado = await medio_db(s, privada["medio_id"])
    privado.thumbnail_path = f"{privado.storage_path}.miniatura.jpg"
    await s.flush()
    r = await http.get(f"{API}/medios/{privada['medio_id']}")
    assert r.status_code == 200, r.text
    assert r.json()["url"] is None
    assert r.json()["miniatura_url"] is None

    r = await http.post(
        f"{API}/medios", json={"content_type": PNG, "tamano_bytes": len(CONTENIDO)}
    )
    assert r.status_code == 201, r.text
    publica = r.json()
    assert publica["bucket"] == settings.BUCKET_MEDIOS
    almacenamiento_falso.simular_subida(
        publica["bucket"], publica["ruta"], CONTENIDO, PNG
    )
    r = await http.post(f"{API}/medios/{publica['medio_id']}/confirmar")
    assert r.status_code == 200, r.text
    assert publica["ruta"] in r.json()["url"]


# 10. Configuracion


OBLIGATORIAS = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "ALEMBIC_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/artistica",
    "SUPABASE_URL": "http://supabase.local",
}


def test_8c_10_configuracion():
    def _settings(**valores) -> Settings:
        # _env_file=None: no lee el .env local
        return Settings(_env_file=None, **OBLIGATORIAS, **valores)

    with pytest.raises(ValidationError, match="BUCKET_ENTREGABLES"):
        _settings(BUCKET_MEDIOS="medios", BUCKET_ENTREGABLES="medios")
    with pytest.raises(ValidationError, match="DESCARGA_FIRMADA_SEGUNDOS"):
        _settings(DESCARGA_FIRMADA_SEGUNDOS=30)

    defecto = _settings()
    assert defecto.BUCKET_ENTREGABLES != defecto.BUCKET_MEDIOS
    assert defecto.DESCARGA_FIRMADA_SEGUNDOS == 600


# 11. Almacenamiento falso


async def test_8c_11_descarga_firmada_del_falso():
    ahora = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    almacenamiento = AlmacenamientoFalso(reloj=lambda: ahora)
    with pytest.raises(ErrorAlmacenamiento) as error:
        await almacenamiento.firmar_descarga("entregables", "a/b.png", segundos=60)
    assert not error.value.reintentable

    await almacenamiento.subir("entregables", "a/b.png", CONTENIDO, PNG)
    descarga = await almacenamiento.firmar_descarga(
        "entregables", "a/b.png", segundos=60
    )
    expira_en = ahora + timedelta(seconds=60)
    assert descarga.expira_en == expira_en
    assert descarga.url == (
        "https://almacenamiento-falso.invalid/firmada/entregables/a/b.png"
        f"?expira={int(expira_en.timestamp())}"
    )
    with pytest.raises(ValueError, match="positivos"):
        await almacenamiento.firmar_descarga("entregables", "a/b.png", segundos=-1)
