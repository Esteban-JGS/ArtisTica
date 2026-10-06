"""Adaptador de Supabase Storage.

Todo lo que depende de la API de Storage vive en el bloque de mapeo de abajo.
Cada entrada lleva su fuente o POR_CONFIRMAR. Si Supabase cambia algo, se
corrige ese bloque y nada mas.

Preparar el bucket de medios (crea o actualiza, es idempotente):

    python -m src.storage.supabase
"""

import asyncio
import json
from collections.abc import Callable, Generator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from pydantic import SecretStr

from src.storage.contrato import (
    AlmacenamientoNoDisponible,
    CredencialesAlmacenamiento,
    ErrorAlmacenamiento,
    InfoObjeto,
    SubidaFirmada,
)

# ======================================================================
# MAPEO DE SUPABASE STORAGE
# Documentacion y codigo fuente consultados el 2026-10-04.
# Fuentes:
#   [api]  https://github.com/supabase/storage (src/http/routes)
#   [js]   https://github.com/supabase/storage-js (src/packages/StorageFileApi.ts,
#          src/packages/StorageBucketApi.ts)
#   [docs] https://supabase.com/docs/reference/javascript/storage-from-createsigneduploadurl
# ======================================================================

# Conexion y autenticacion
# [js] StorageClient se construye con `${SUPABASE_URL}/storage/v1`
PREFIJO_API = "/storage/v1"
# [docs] https://supabase.com/docs/guides/api/api-keys: la clave va en
# `apikey` y como Bearer en `Authorization`
ENCABEZADO_APIKEY = "apikey"
ENCABEZADO_AUTORIZACION = "Authorization"
PREFIJO_AUTORIZACION = "Bearer "

# Firmar subida
# [api] src/http/routes/object/getSignedUploadURL.ts: POST /upload/sign/:bucket/*
# bajo el prefijo /object
RUTA_FIRMAR_SUBIDA = "/object/upload/sign/{bucket}/{ruta}"
# [api] getSignedUploadURL.ts responde { url, token }
# [js] createSignedUploadUrl toma el token del query de `url`. Se usa el campo
# `token` si viene y el query si no, para versiones viejas que solo dan `url`.
CAMPO_URL_FIRMADA = "url"
CAMPO_TOKEN_FIRMADO = "token"  # noqa: S105  nombre de campo, no un secreto
PARAMETRO_TOKEN = "token"  # noqa: S105  nombre de parametro, no un secreto
# [js] uploadToSignedUrl sube con PUT a `${url}/object/upload/sign/...?token=`.
# Es lo que hace el cliente movil con `url_subida`; este adaptador no lo usa.
METODO_SUBIDA_CLIENTE = "PUT"
# [docs] "Signed upload URLs ... are valid for 2 hours".
# POR_CONFIRMAR: el servidor la toma de UPLOAD_SIGNED_URL_EXPIRATION_TIME
# ([api] src/config.ts, 60 s por defecto en una instalacion propia) y la
# respuesta no informa el vencimiento. Se asume el valor de la plataforma.
VIGENCIA_SUBIDA_FIRMADA = timedelta(hours=2)

# Informacion del objeto
# [api] src/http/routes/object/getObjectInfo.ts: GET /info/:bucket/*
# autenticado. Se elige sobre HEAD porque trae tamano y tipo en JSON.
# [js] info() usa la misma ruta
RUTA_INFO = "/object/info/{bucket}/{ruta}"
# [api] src/storage/renderer/info.ts: size, content_type, metadata
CAMPO_TAMANO = "size"
CAMPO_CONTENT_TYPE = "content_type"
# POR_CONFIRMAR: respaldo para versiones que solo informan dentro de metadata
# (metadata.size, metadata.mimetype, como en la tabla storage.objects)
CAMPO_METADATOS = "metadata"
CAMPO_METADATOS_TAMANO = "size"
CAMPO_METADATOS_TIPO = "mimetype"

# Objetos
# [js] download(): GET /object/{bucket}/{ruta}
# [js] upload(): POST /object/{bucket}/{ruta}
RUTA_OBJETO = "/object/{bucket}/{ruta}"
# [js] uploadOrUpdate manda x-upsert y content-type con cuerpo crudo
ENCABEZADO_UPSERT = "x-upsert"
# [js] remove(): DELETE /object/{bucket} con { prefixes: [...] }
RUTA_BORRAR = "/object/{bucket}"
CAMPO_PREFIJOS = "prefixes"
# [js] getPublicUrl(): `${url}/object/public/{bucket}/{ruta}`, sin autenticar
RUTA_PUBLICA = "/object/public/{bucket}/{ruta}"

# Buckets
# [api] src/http/routes/bucket/getBucket.ts: GET /bucket/:bucketId
# [api] src/http/routes/bucket/updateBucket.ts: PUT /bucket/:bucketId
RUTA_BUCKET = "/bucket/{bucket}"
# [api] src/http/routes/bucket/createBucket.ts: POST /bucket
RUTA_BUCKETS = "/bucket"
# [api] createBucket.ts y updateBucket.ts (cuerpo)
CAMPO_BUCKET_ID = "id"
CAMPO_BUCKET_NOMBRE = "name"
CAMPO_BUCKET_PUBLICO = "public"
CAMPO_BUCKET_LIMITE = "file_size_limit"
CAMPO_BUCKET_TIPOS = "allowed_mime_types"

# Errores HTTP
# [api] src/http/error-handler.ts: salvo las rutas que respetan el codigo, un
# error del storage sale como HTTP 400 (o 500) y el codigo real va como texto
# en el campo `statusCode` del cuerpo. Se lee ese campo cuando llega un 400.
HTTP_ERROR_ENVUELTO = 400
CAMPO_ERROR_CODIGO = "statusCode"
# [api] src/internal/errors/codes.ts: NoSuchKey y NoSuchBucket son 404
HTTP_NO_ENCONTRADO = 404
HTTP_CREDENCIALES = frozenset({401, 403})
# POR_CONFIRMAR: 429 no esta documentado; se trata como no disponible
HTTP_NO_DISPONIBLE_EXTRA = frozenset({429})
# [api] error-handler.ts: cuerpo { statusCode, error, message }
CAMPOS_DETALLE_ERROR = ("error", "message")

# ======================================================================
# FIN DEL MAPEO
# ======================================================================


class _ClaveServicio(httpx.Auth):
    """Pone la clave en la solicitud sin dejarla en variables locales."""

    def __init__(self, clave: SecretStr) -> None:
        self._clave = clave

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        valor = self._clave.get_secret_value()
        request.headers[ENCABEZADO_APIKEY] = valor
        request.headers[ENCABEZADO_AUTORIZACION] = PREFIJO_AUTORIZACION + valor
        yield request

    def __repr__(self) -> str:
        return "_ClaveServicio(**********)"


def _reloj_utc() -> datetime:
    return datetime.now(UTC)


class AlmacenamientoSupabase:
    def __init__(
        self,
        *,
        url: str,
        clave: SecretStr,
        timeout_segundos: float = 15,
        cliente: httpx.AsyncClient | None = None,
        reloj: Callable[[], datetime] = _reloj_utc,
    ) -> None:
        if not clave.get_secret_value().strip():
            raise CredencialesAlmacenamiento("Falta SUPABASE_SERVICE_KEY")
        self._clave = clave
        self._auth = _ClaveServicio(clave)
        self._url_base = url.rstrip("/") + PREFIJO_API
        self._timeout = httpx.Timeout(timeout_segundos)
        self._cliente_propio = cliente is None
        self._cliente = cliente or httpx.AsyncClient(timeout=self._timeout)
        self._reloj = reloj

    def __repr__(self) -> str:
        return f"AlmacenamientoSupabase(url_base={self._url_base!r})"

    async def cerrar(self) -> None:
        if self._cliente_propio:
            await self._cliente.aclose()

    # Contrato

    async def firmar_subida(self, bucket: str, ruta: str) -> SubidaFirmada:
        expira_en = self._reloj() + VIGENCIA_SUBIDA_FIRMADA
        respuesta = await self._solicitar(
            "POST", _ruta(RUTA_FIRMAR_SUBIDA, bucket, ruta), json_cuerpo={}
        )
        datos = _json_o_nada(respuesta) or {}
        relativa = datos.get(CAMPO_URL_FIRMADA)
        if not isinstance(relativa, str) or not relativa.startswith("/"):
            raise ErrorAlmacenamiento("Storage respondio la firma sin url")
        token = datos.get(CAMPO_TOKEN_FIRMADO)
        if not isinstance(token, str) or not token:
            valores = parse_qs(urlsplit(relativa).query).get(PARAMETRO_TOKEN)
            token = valores[0] if valores else None
        if not token:
            raise ErrorAlmacenamiento("Storage respondio la firma sin token")
        return SubidaFirmada(
            bucket=bucket,
            ruta=ruta,
            token=token,
            url_subida=self._url_base + relativa,
            expira_en=expira_en,
        )

    async def info(self, bucket: str, ruta: str) -> InfoObjeto | None:
        respuesta = await self._solicitar(
            "GET", _ruta(RUTA_INFO, bucket, ruta), no_encontrado_es_none=True
        )
        if respuesta is None:
            return None
        datos = _json_o_nada(respuesta)
        if datos is None:
            raise ErrorAlmacenamiento("Storage respondio la informacion sin JSON")
        metadatos = datos.get(CAMPO_METADATOS)
        metadatos = metadatos if isinstance(metadatos, dict) else {}
        tamano = datos.get(CAMPO_TAMANO)
        if tamano is None:
            tamano = metadatos.get(CAMPO_METADATOS_TAMANO)
        if isinstance(tamano, bool) or not isinstance(tamano, int):
            raise ErrorAlmacenamiento("Storage respondio sin el tamano del objeto")
        tipo = datos.get(CAMPO_CONTENT_TYPE) or metadatos.get(CAMPO_METADATOS_TIPO)
        return InfoObjeto(
            tamano_bytes=tamano, content_type=tipo if isinstance(tipo, str) else None
        )

    async def descargar(self, bucket: str, ruta: str) -> bytes:
        respuesta = await self._solicitar("GET", _ruta(RUTA_OBJETO, bucket, ruta))
        return respuesta.content

    async def subir(
        self, bucket: str, ruta: str, contenido: bytes, content_type: str
    ) -> None:
        await self._solicitar(
            "POST",
            _ruta(RUTA_OBJETO, bucket, ruta),
            contenido=contenido,
            encabezados={"Content-Type": content_type, ENCABEZADO_UPSERT: "true"},
        )

    async def borrar(self, bucket: str, rutas: Sequence[str]) -> None:
        if not rutas:
            return
        await self._solicitar(
            "DELETE",
            RUTA_BORRAR.format(bucket=quote(bucket, safe="")),
            json_cuerpo={CAMPO_PREFIJOS: list(rutas)},
        )

    def url_publica(self, bucket: str, ruta: str) -> str:
        return self._url_base + _ruta(RUTA_PUBLICA, bucket, ruta)

    # Administracion

    async def preparar_bucket(
        self, bucket: str, *, tamano_maximo: int, tipos: Sequence[str]
    ) -> str:
        """Crea el bucket publico o lo actualiza. Devuelve "creado" o "actualizado".

        Supabase hace cumplir el limite y los tipos en cada subida, tambien en
        las firmadas.
        """
        reglas = {
            CAMPO_BUCKET_PUBLICO: True,
            CAMPO_BUCKET_LIMITE: tamano_maximo,
            CAMPO_BUCKET_TIPOS: list(tipos),
        }
        ruta_bucket = RUTA_BUCKET.format(bucket=quote(bucket, safe=""))
        existente = await self._solicitar(
            "GET", ruta_bucket, no_encontrado_es_none=True
        )
        if existente is None:
            await self._solicitar(
                "POST",
                RUTA_BUCKETS,
                json_cuerpo={
                    CAMPO_BUCKET_ID: bucket,
                    CAMPO_BUCKET_NOMBRE: bucket,
                    **reglas,
                },
            )
            return "creado"
        await self._solicitar("PUT", ruta_bucket, json_cuerpo=reglas)
        return "actualizado"

    # Internos

    async def _solicitar(
        self,
        metodo: str,
        ruta: str,
        *,
        json_cuerpo: Mapping[str, Any] | None = None,
        contenido: bytes | None = None,
        encabezados: Mapping[str, str] | None = None,
        no_encontrado_es_none: bool = False,
    ) -> httpx.Response | None:
        cabeceras = dict(encabezados or {})
        if json_cuerpo is not None:
            contenido = json.dumps(json_cuerpo).encode()
            cabeceras["Content-Type"] = "application/json"
        try:
            respuesta = await self._cliente.request(
                metodo,
                self._url_base + ruta,
                content=contenido,
                headers=cabeceras,
                auth=self._auth,
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            raise AlmacenamientoNoDisponible(
                f"Storage no respondio a tiempo: {metodo}"
            ) from None
        except httpx.TransportError:
            raise AlmacenamientoNoDisponible(
                f"Error de red con Storage: {metodo}"
            ) from None

        if 200 <= respuesta.status_code < 300:
            return respuesta
        codigo = _codigo_efectivo(respuesta)
        if codigo == HTTP_NO_ENCONTRADO and no_encontrado_es_none:
            return None
        detalle = self._limpiar(_detalle(respuesta))
        if codigo in HTTP_CREDENCIALES:
            raise CredencialesAlmacenamiento(
                f"Storage rechazo las credenciales (HTTP {codigo})"
            )
        if codigo >= 500 or codigo in HTTP_NO_DISPONIBLE_EXTRA:
            raise AlmacenamientoNoDisponible(
                f"Storage no disponible (HTTP {codigo}): {detalle}"
            )
        raise ErrorAlmacenamiento(
            f"Storage rechazo la solicitud (HTTP {codigo}): {detalle}"
        )

    def _limpiar(self, texto: str) -> str:
        """Ningun secreto sale en un mensaje, aunque el proveedor lo devuelva."""
        return texto[:300].replace(self._clave.get_secret_value(), "**********")


# Auxiliares sin estado


def _ruta(plantilla: str, bucket: str, ruta: str) -> str:
    return plantilla.format(bucket=quote(bucket, safe=""), ruta=quote(ruta, safe="/"))


def _json_o_nada(respuesta: httpx.Response) -> dict[str, Any] | None:
    try:
        datos = json.loads(respuesta.content)
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None


def _codigo_efectivo(respuesta: httpx.Response) -> int:
    codigo = respuesta.status_code
    if codigo != HTTP_ERROR_ENVUELTO:
        return codigo
    datos = _json_o_nada(respuesta) or {}
    try:
        return int(str(datos.get(CAMPO_ERROR_CODIGO)))
    except ValueError:
        return codigo


def _detalle(respuesta: httpx.Response) -> str:
    datos = _json_o_nada(respuesta)
    if not datos:
        return "sin detalle"
    partes = [str(datos[c]) for c in CAMPOS_DETALLE_ERROR if datos.get(c)]
    return " | ".join(partes) or "sin detalle"


def desde_config(config: Any) -> AlmacenamientoSupabase:
    """Construye el adaptador desde `Settings`. Exige la clave de servicio."""
    clave = config.SUPABASE_SERVICE_KEY
    if clave is None or not str(clave).strip():
        raise CredencialesAlmacenamiento(
            "ALMACENAMIENTO=supabase necesita SUPABASE_SERVICE_KEY"
        )
    return AlmacenamientoSupabase(
        url=str(config.SUPABASE_URL),
        clave=SecretStr(str(clave)),
        timeout_segundos=config.ALMACENAMIENTO_TIMEOUT_SEGUNDOS,
    )


async def _preparar_bucket_medios() -> None:
    # Imports diferidos: importarlos arriba haria circular el modulo de config
    from src.core.config import settings  # noqa: PLC0415
    from src.domain.medios import TIPOS_PERMITIDOS  # noqa: PLC0415

    almacenamiento = desde_config(settings)
    try:
        resultado = await almacenamiento.preparar_bucket(
            settings.BUCKET_MEDIOS,
            tamano_maximo=settings.MEDIO_TAMANO_MAXIMO_BYTES,
            tipos=sorted(TIPOS_PERMITIDOS),
        )
    finally:
        await almacenamiento.cerrar()
    print(  # noqa: T201  es la salida del comando de consola
        f"Bucket {settings.BUCKET_MEDIOS}: {resultado}"
    )


if __name__ == "__main__":
    asyncio.run(_preparar_bucket_medios())
