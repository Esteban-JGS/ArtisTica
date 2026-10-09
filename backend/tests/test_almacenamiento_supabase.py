"""Adaptador de Supabase Storage y fabrica. Todas con httpx.MockTransport: nunca hay red."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

import src.storage as fabrica
from src.core.config import settings
from src.storage import supabase
from src.storage.contrato import (
    AlmacenamientoNoDisponible,
    CredencialesAlmacenamiento,
    DescargaFirmada,
    ErrorAlmacenamiento,
    InfoObjeto,
)
from src.storage.falso import AlmacenamientoFalso
from src.storage.supabase import AlmacenamientoSupabase

CLAVE = "service_role_clave_NO_DEBE_FILTRARSE"
URL = "https://proyecto.supabase.co"
BASE = "/storage/v1"
AHORA = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
RUTA = "propietario/medio.webp"
TIPOS = ["image/jpeg", "image/png", "image/webp"]

Manejador = Callable[[httpx.Request], httpx.Response]


class Simulador:
    """Responde por (metodo, ruta) y guarda cada solicitud recibida."""

    def __init__(self, rutas: dict[tuple[str, str], Manejador]) -> None:
        self.rutas = rutas
        self.solicitudes: list[httpx.Request] = []

    def __call__(self, solicitud: httpx.Request) -> httpx.Response:
        self.solicitudes.append(solicitud)
        # Toda solicitud va autenticada como dice el mapeo
        assert solicitud.headers[supabase.ENCABEZADO_APIKEY] == CLAVE
        assert solicitud.headers[supabase.ENCABEZADO_AUTORIZACION] == f"Bearer {CLAVE}"
        return self.rutas[(solicitud.method, solicitud.url.path)](solicitud)

    def almacenamiento(self) -> AlmacenamientoSupabase:
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(self))
        return AlmacenamientoSupabase(
            url=URL, clave=SecretStr(CLAVE), cliente=cliente, reloj=lambda: AHORA
        )


def responder(estado: int, datos: object) -> Manejador:
    return lambda _: httpx.Response(estado, json=datos)


def cuerpo(solicitud: httpx.Request) -> dict:
    return json.loads(solicitud.content)


def timeout(solicitud: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("sin respuesta", request=solicitud)


FIRMAR = ("POST", f"{BASE}/object/upload/sign/medios/{RUTA}")
INFO = ("GET", f"{BASE}/object/info/medios/{RUTA}")
OBJETO = f"{BASE}/object/medios/{RUTA}"


async def test_01_firmar_subida():
    relativa = f"/object/upload/sign/medios/{RUTA}?token=tok123"
    simulador = Simulador({FIRMAR: responder(200, {"url": relativa})})
    subida = await simulador.almacenamiento().firmar_subida("medios", RUTA)

    assert subida.bucket == "medios"
    assert subida.ruta == RUTA
    assert subida.token == "tok123"
    assert subida.url_subida == f"{URL}{BASE}{relativa}"
    assert subida.expira_en == AHORA + supabase.VIGENCIA_SUBIDA_FIRMADA
    # El token no sale en el repr
    assert "tok123" not in repr(subida)

    # Si el servidor manda el campo token, se usa ese
    simulador = Simulador(
        {FIRMAR: responder(200, {"url": relativa, "token": "tok_campo"})}
    )
    subida = await simulador.almacenamiento().firmar_subida("medios", RUTA)
    assert subida.token == "tok_campo"


async def test_02_info_existe_y_no_existe():
    simulador = Simulador(
        {INFO: responder(200, {"size": 2048, "content_type": "image/webp"})}
    )
    info = await simulador.almacenamiento().info("medios", RUTA)
    assert info == InfoObjeto(tamano_bytes=2048, content_type="image/webp")

    # Respaldo: tamano y tipo dentro de metadata
    simulador = Simulador(
        {INFO: responder(200, {"metadata": {"size": 10, "mimetype": "image/png"}})}
    )
    info = await simulador.almacenamiento().info("medios", RUTA)
    assert info == InfoObjeto(tamano_bytes=10, content_type="image/png")

    simulador = Simulador({INFO: responder(404, {"error": "not_found"})})
    assert await simulador.almacenamiento().info("medios", RUTA) is None

    # Storage envuelve el 404 en un 400 con statusCode en el cuerpo
    simulador = Simulador(
        {INFO: responder(400, {"statusCode": "404", "error": "not_found"})}
    )
    assert await simulador.almacenamiento().info("medios", RUTA) is None


async def test_03_errores_de_disponibilidad_y_credenciales():
    for manejador in (responder(503, {"message": "caido"}), timeout):
        almacenamiento = Simulador({INFO: manejador}).almacenamiento()
        with pytest.raises(AlmacenamientoNoDisponible) as error:
            await almacenamiento.info("medios", RUTA)
        assert error.value.reintentable

    for manejador in (
        responder(401, {"message": "Invalid JWT"}),
        responder(400, {"statusCode": "403", "error": "Unauthorized"}),
    ):
        almacenamiento = Simulador({FIRMAR: manejador}).almacenamiento()
        with pytest.raises(CredencialesAlmacenamiento) as error:
            await almacenamiento.firmar_subida("medios", RUTA)
        assert not error.value.reintentable


async def test_04_borrar_subir_y_descargar():
    simulador = Simulador(
        {
            ("DELETE", f"{BASE}/object/medios"): responder(200, []),
            ("POST", OBJETO): responder(200, {"Key": f"medios/{RUTA}"}),
            ("GET", OBJETO): lambda _: httpx.Response(200, content=b"\x89PNG"),
        }
    )
    almacenamiento = simulador.almacenamiento()

    await almacenamiento.borrar("medios", [RUTA, "propietario/mini.webp"])
    assert cuerpo(simulador.solicitudes[-1]) == {
        "prefixes": [RUTA, "propietario/mini.webp"]
    }

    await almacenamiento.subir("medios", RUTA, b"bytes", "image/webp")
    subida = simulador.solicitudes[-1]
    assert subida.headers["x-upsert"] == "true"
    assert subida.headers["content-type"] == "image/webp"
    assert subida.content == b"bytes"

    assert await almacenamiento.descargar("medios", RUTA) == b"\x89PNG"

    # Sin rutas no se llama a nadie
    total = len(simulador.solicitudes)
    await almacenamiento.borrar("medios", [])
    assert len(simulador.solicitudes) == total

    assert almacenamiento.url_publica("medios", RUTA) == (
        f"{URL}{BASE}/object/public/medios/{RUTA}"
    )


async def test_05_preparar_bucket_crea_o_actualiza():
    reglas = {"public": True, "file_size_limit": 5_000_000, "allowed_mime_types": TIPOS}
    bucket = ("GET", f"{BASE}/bucket/medios")

    simulador = Simulador(
        {
            bucket: responder(400, {"statusCode": "404", "error": "Bucket not found"}),
            ("POST", f"{BASE}/bucket"): responder(200, {"name": "medios"}),
        }
    )
    resultado = await simulador.almacenamiento().preparar_bucket(
        "medios", tamano_maximo=5_000_000, tipos=TIPOS
    )
    assert resultado == "creado"
    assert cuerpo(simulador.solicitudes[-1]) == {
        "id": "medios",
        "name": "medios",
        **reglas,
    }

    simulador = Simulador(
        {
            bucket: responder(200, {"id": "medios", "public": False}),
            ("PUT", f"{BASE}/bucket/medios"): responder(200, {"message": "ok"}),
        }
    )
    resultado = await simulador.almacenamiento().preparar_bucket(
        "medios", tamano_maximo=5_000_000, tipos=TIPOS
    )
    assert resultado == "actualizado"
    assert simulador.solicitudes[-1].method == "PUT"
    assert cuerpo(simulador.solicitudes[-1]) == reglas


async def test_06_la_clave_no_se_filtra():
    eco = {"message": f"clave recibida {CLAVE}", "error": CLAVE}
    for codigo in (400, 401, 500):
        almacenamiento = Simulador({FIRMAR: responder(codigo, eco)}).almacenamiento()
        assert CLAVE not in repr(almacenamiento)
        with pytest.raises(ErrorAlmacenamiento) as error:
            await almacenamiento.firmar_subida("medios", RUTA)
        assert CLAVE not in str(error.value)
        assert CLAVE not in repr(error.value)


async def test_07_fabrica(monkeypatch):
    monkeypatch.setattr(settings, "ALMACENAMIENTO", "falso")
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev")
    fabrica.obtener_almacenamiento.cache_clear()
    try:
        almacenamiento = fabrica.obtener_almacenamiento()
        assert isinstance(almacenamiento, AlmacenamientoFalso)
        assert fabrica.obtener_almacenamiento() is almacenamiento
    finally:
        fabrica.obtener_almacenamiento.cache_clear()

    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", None)
    with pytest.raises(CredencialesAlmacenamiento, match="SUPABASE_SERVICE_KEY"):
        fabrica.construir_almacenamiento("supabase")

    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", CLAVE)
    almacenamiento = fabrica.construir_almacenamiento("supabase")
    assert isinstance(almacenamiento, AlmacenamientoSupabase)
    await almacenamiento.cerrar()

    for entorno in ("production", "prod"):
        monkeypatch.setattr(settings, "ENVIRONMENT", entorno)
        with pytest.raises(ValueError, match="produccion"):
            fabrica.construir_almacenamiento("falso")

    with pytest.raises(ValueError, match="desconocido"):
        fabrica.construir_almacenamiento("disco_inventado")


# Lote 8c: descarga firmada y bucket privado

FIRMAR_DESCARGA = ("POST", f"{BASE}/object/sign/entregables/{RUTA}")


async def test_8c_01_firmar_descarga():
    relativa = f"/object/sign/entregables/{RUTA}?token=tok_descarga"
    simulador = Simulador({FIRMAR_DESCARGA: responder(200, {"signedURL": relativa})})
    descarga = await simulador.almacenamiento().firmar_descarga(
        "entregables", RUTA, segundos=600
    )

    assert cuerpo(simulador.solicitudes[-1]) == {"expiresIn": 600}
    assert descarga.url == f"{URL}{BASE}{relativa}"
    assert descarga.expira_en == AHORA + timedelta(seconds=600)

    for respuesta in ({}, {"signedURL": "https://otro.invalid/object/sign/x"}):
        almacenamiento = Simulador(
            {FIRMAR_DESCARGA: responder(200, respuesta)}
        ).almacenamiento()
        with pytest.raises(ErrorAlmacenamiento, match="sin url"):
            await almacenamiento.firmar_descarga("entregables", RUTA, segundos=600)

    with pytest.raises(ValueError, match="positivos"):
        await simulador.almacenamiento().firmar_descarga(
            "entregables", RUTA, segundos=0
        )


async def test_8c_02_preparar_bucket_privado():
    bucket = ("GET", f"{BASE}/bucket/entregables")
    rutas = {
        bucket: responder(400, {"statusCode": "404", "error": "Bucket not found"}),
        ("POST", f"{BASE}/bucket"): responder(200, {"name": "entregables"}),
    }

    simulador = Simulador(rutas)
    await simulador.almacenamiento().preparar_bucket(
        "entregables", tamano_maximo=5_000_000, tipos=TIPOS, publico=False
    )
    assert cuerpo(simulador.solicitudes[-1])["public"] is False

    simulador = Simulador(rutas)
    await simulador.almacenamiento().preparar_bucket(
        "entregables", tamano_maximo=5_000_000, tipos=TIPOS
    )
    assert cuerpo(simulador.solicitudes[-1])["public"] is True


def test_8c_03_repr_de_descarga_firmada_sin_url():
    url = "https://proyecto.supabase.co/storage/v1/object/sign/x?token=secreto"
    descarga = DescargaFirmada(url=url, expira_en=AHORA)
    assert "secreto" not in repr(descarga)
    assert url not in repr(descarga)
