# [Lote 5] Almacenamiento y medios con subida firmada

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-05-almacenamiento-medios
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas. Los artistas muestran su obra con imagenes. La app movil redimensiona cada imagen en el telefono y la sube **directo a Supabase Storage con una URL firmada que emite esta API**: el archivo nunca pasa por FastAPI. El ancho de banda de Storage es el primer limite real de la plataforma.

Este lote construye la capa de almacenamiento y el ciclo de vida de un medio: pedir la subida, confirmarla y borrarla. Las obras y servicios que usan esos medios son el lote siguiente; las miniaturas las genera el worker en un lote posterior. Aca solo se encola el trabajo de miniatura.

Igual que la pasarela de pagos, el proveedor de almacenamiento vive detras de un contrato: un adaptador real de Supabase y uno falso en memoria para pruebas y demo. Nada fuera de `src/storage/` sabe que Supabase Storage existe.

### Decisiones que este lote implementa

1. **En el MVP solo hay imagenes:** JPEG, PNG y WebP, hasta 5 MB. El video queda fuera del MVP.
2. **El bucket `medios` es publico para lectura**, para que la CDN de Supabase sirva la galeria sin URLs firmadas de lectura. Nadie escribe en el sin una URL firmada emitida por la API. Las rutas llevan un uuid, asi que no se adivinan.
3. **La ruta la arma siempre el servidor:** `{propietario_id}/{medio_id}.{extension}`. Nunca se acepta una ruta del cliente.
4. **Un medio no existe hasta que se confirma.** La API firma la subida, el cliente sube, y la API confirma consultando el objeto en Storage: existe, pesa lo permitido y tiene el tipo declarado. Solo un medio confirmado se puede asociar despues a una obra.
5. **`media_assets` gana una columna `bucket`.** Los entregables de un pedido (archivo final) usan la misma tabla y van a ir a un bucket privado en el lote 8. Hoy todo va a `medios`.
6. **Desde este lote las migraciones se encadenan.** La migracion inicial ya esta aplicada en bases de prueba y no se vuelve a reescribir.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno obligatorias estan en `backend/AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/models/medios.py` | `MediaAsset`: `propietario_id`, `obra_id`, `publicacion_id`, `tipo` (texto), `storage_path`, `thumbnail_path`, `estado` (`pendiente`, `procesado`, `fallido`, que es el estado del **procesamiento**), mas timestamps y `deleted_at`. `propietario_id` **no tiene indice** |
| `alembic/versions/1a2b3c4d5e6f_initial_migration.py` | Unica migracion. No se toca |
| `src/models/operacion.py` | `Job`: `type`, `payload` (JSONB), `status` (texto, `pending` por defecto), `attempts`, `max_attempts`, `run_after` (obligatorio) |
| `src/workers/handlers/thumbnails.py` | Handler de relleno para `generate_thumbnail`: no lee el payload. Se reescribe en un lote posterior. No se toca |
| `src/services/pedidos.py:354` | Usa `MediaAsset` para la vista previa de un pedido. No se toca |
| `src/core/config.py` | Ya tiene `SUPABASE_URL` y `SUPABASE_SERVICE_KEY: str | None`. `PASARELA` es el modelo a seguir para elegir adaptador |
| `src/payments/` | **Modelo a seguir** para el contrato, el adaptador falso, la fabrica, el bloque de mapeo del proveedor con fuentes, y las pruebas con `httpx.MockTransport` |
| `src/api/deps.py` | `get_current_user`, `get_current_artista`, `get_pasarela`. Las pruebas sobrescriben dependencias con `app.dependency_overrides` |
| `src/main.py` | Manejadores de error: `ResourceNotFound` 404, `ActorNoAutorizado` 403, `ReglaDeNegocioViolada` 409, errores de pasarela 502 y 503 |
| `tests/conftest.py` | Fixtures `sesion_api`, `pasarela_falsa` y `autenticar_como` |

Base de pruebas local: el contenedor `artistica-db-pruebas` (pgvector) en el puerto 5433, usuario y clave `postgres`, base `artistica`. Si no esta corriendo: `docker start artistica-db-pruebas`.

## Objetivo

Que un artista pueda pedir una URL firmada, subir una imagen directo a Storage, confirmarla y borrarla, con el proveedor detras de un contrato y la migracion de `media_assets` encadenada.

## Diseno

### 1. Contrato (`src/storage/contrato.py`)

```python
@dataclass(frozen=True, kw_only=True)
class SubidaFirmada:
    bucket: str
    ruta: str
    token: str = field(repr=False)
    url_subida: str = field(repr=False)
    expira_en: datetime

@dataclass(frozen=True, kw_only=True)
class InfoObjeto:
    tamano_bytes: int
    content_type: str | None

class Almacenamiento(Protocol):
    async def firmar_subida(self, bucket: str, ruta: str) -> SubidaFirmada: ...
    async def info(self, bucket: str, ruta: str) -> InfoObjeto | None: ...  # None si no existe
    async def descargar(self, bucket: str, ruta: str) -> bytes: ...
    async def subir(self, bucket: str, ruta: str, contenido: bytes, content_type: str) -> None: ...
    async def borrar(self, bucket: str, rutas: Sequence[str]) -> None: ...
    def url_publica(self, bucket: str, ruta: str) -> str: ...
```

`descargar` y `subir` no los usa este lote: los necesita el worker de miniaturas. Se implementan y se prueban igual.

Errores en el mismo modulo: `ErrorAlmacenamiento` (base, con `reintentable`), `AlmacenamientoNoDisponible` (timeout, 5xx o red; reintentable) y `CredencialesAlmacenamiento` (401 o 403). Ningun mensaje lleva la clave.

### 2. Adaptador de Supabase (`src/storage/supabase.py`)

- `httpx.AsyncClient` con timeout configurable. Cada solicitud lleva la clave de servicio en `apikey` y en `Authorization: Bearer`.
- La clave es `SecretStr` y no aparece en `repr`, en logs ni en mensajes de error.
- **Bloque de mapeo del proveedor** al principio del archivo, igual que el de ONVO: cada endpoint, metodo, campo de respuesta y encabezado, con su fuente (URL de la documentacion oficial de Supabase o del OpenAPI de `supabase/storage`) o con la marca `POR_CONFIRMAR`. Puntos de partida, a verificar:

| Operacion | Punto de partida |
|---|---|
| Firmar subida | `POST {SUPABASE_URL}/storage/v1/object/upload/sign/{bucket}/{ruta}`, responde `{"url": "/object/upload/sign/...?token=..."}`. La URL vale 2 horas. `url_subida = {SUPABASE_URL}/storage/v1{url}`; el `token` sale del query |
| Info | El endpoint de informacion del objeto, o un `HEAD` sobre el objeto autenticado. Elegí el que la documentacion respalde y anotá la fuente. 404 da `None` |
| Descargar | `GET {SUPABASE_URL}/storage/v1/object/{bucket}/{ruta}` |
| Subir | `POST {SUPABASE_URL}/storage/v1/object/{bucket}/{ruta}` con `x-upsert: true` |
| Borrar | `DELETE {SUPABASE_URL}/storage/v1/object/{bucket}` con `{"prefixes": [...]}` |
| URL publica | `{SUPABASE_URL}/storage/v1/object/public/{bucket}/{ruta}` |
| Bucket | `GET`, `POST` y `PUT` sobre `{SUPABASE_URL}/storage/v1/bucket` |

- `preparar_bucket(...)`: crea el bucket `medios` si no existe o lo actualiza si existe, siempre con `public: true`, `file_size_limit` igual a `MEDIO_TAMANO_MAXIMO_BYTES` y `allowed_mime_types` igual a los tipos permitidos. Es idempotente. Se corre a mano con `python -m src.storage.supabase`, y ese es el unico uso de `if __name__ == "__main__"`. El limite y los tipos del bucket los **hace cumplir Supabase en la subida**, que es lo que impide que una URL firmada suba cualquier cosa.

### 3. Adaptador falso (`src/storage/falso.py`)

En memoria, una instancia por proceso. Implementa el contrato completo, mas controles para pruebas:

- `simular_subida(bucket, ruta, contenido, content_type)`: lo que haria el cliente con la URL firmada.
- `existe(bucket, ruta) -> bool`.
- `programar_falla(operacion, error)`: la proxima llamada a esa operacion levanta ese error, como en `PasarelaFalsa`.

`url_publica` devuelve `https://almacenamiento-falso.invalid/{bucket}/{ruta}`.

### 4. Fabrica (`src/storage/__init__.py`)

`construir_almacenamiento(nombre)` y `obtener_almacenamiento()` (con `functools.cache`), igual que `src/payments/fabrica.py`:

- `falso` devuelve el falso. Es el valor por defecto.
- `supabase` exige `SUPABASE_SERVICE_KEY`; sin ella falla con un mensaje que nombra la variable.
- Con `ENVIRONMENT` igual a `production` o `prod`, `falso` **falla**: en produccion no se guardan imagenes en memoria.
- Un valor desconocido falla.

### 5. Configuracion (`src/core/config.py`)

```python
ALMACENAMIENTO: str = "falso"
ALMACENAMIENTO_TIMEOUT_SEGUNDOS: int = 15
BUCKET_MEDIOS: str = "medios"
MEDIO_TAMANO_MAXIMO_BYTES: int = 5 * 1024 * 1024
MEDIOS_PENDIENTES_MAXIMOS: int = 20
```

### 6. Modelo y migracion

En `src/models/medios.py`, sin cambiar lo existente:

| Columna | Tipo | Para que |
|---|---|---|
| `bucket` | `String`, no nula, `server_default="medios"` | Decision 5 |
| `content_type` | `String`, nula | El tipo declarado al pedir la subida |
| `tamano_bytes` | `BigInteger`, nula | El declarado, y despues el real al confirmar |
| `subido_en` | `DateTime(timezone=True)`, nula | Nula hasta confirmar. Es lo que distingue un medio confirmado |

Mas `index=True` en `propietario_id`.

Migracion nueva en `alembic/versions/`, con `down_revision = "1a2b3c4d5e6f"`, que agrega las cuatro columnas y el indice, con `downgrade` que los quita. El nombre del indice tiene que coincidir con la convencion de `NAMING_CONVENTION` de `src/models/base.py`. RLS no cambia: no hay tablas nuevas.

### 7. Dominio (`src/domain/medios.py`)

Puro: sin base ni almacenamiento.

- `TIPOS_PERMITIDOS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}`.
- `ruta_para(propietario_id, medio_id, content_type) -> str`. `ValueError` si el tipo no esta permitido.
- `problema_de_subida(content_type_declarado, info, maximo) -> str | None`: `None` si la subida es valida; si no, el motivo en texto ("El archivo no se subio", "El archivo supera el tamano permitido", "El tipo del archivo no coincide con el declarado").

### 8. Servicio (`src/services/medios.py`)

Hace `flush` y nunca `commit`. Recibe el almacenamiento y los limites como parametros.

| Funcion | Que hace |
|---|---|
| `solicitar_subida(session, almacenamiento, propietario, content_type, tamano_bytes, *, maximo_pendientes, bucket)` | Si el propietario ya tiene `maximo_pendientes` medios sin confirmar y sin borrar, `ReglaDeNegocioViolada`. Genera el `medio_id` en Python, arma la ruta, **firma primero** y recien despues agrega la fila y hace `flush`: si Storage falla, no queda fila. Devuelve `(medio, subida)` |
| `confirmar_subida(session, almacenamiento, propietario_id, medio_id, *, maximo_bytes)` | Bloquea la fila con `FOR UPDATE` (`populate_existing`). Si no es del propietario o esta borrado, `ResourceNotFound`, para no revelar que existe. Si ya esta confirmado, lo devuelve sin hacer nada. Consulta `info`; si hay problema, borra el objeto en Storage (si falla el borrado, solo loguea) y levanta `ReglaDeNegocioViolada` con el motivo. Si esta bien: `subido_en`, `tamano_bytes` real, y encola un `Job` con `type="generate_thumbnail"`, `payload={"medio_id": "<uuid>"}` y `run_after` igual al momento actual |
| `obtener(session, propietario_id, medio_id)` | El medio, con la misma regla de `ResourceNotFound` |
| `eliminar(session, almacenamiento, propietario_id, medio_id)` | Si esta asociado a una obra o una publicacion, `ReglaDeNegocioViolada`. Marca `deleted_at`, hace `flush` y borra el objeto en Storage; si el borrado falla, loguea y sigue |

Un medio confirmado queda en `estado = pendiente` hasta que el worker genere la miniatura. Eso es correcto: `estado` habla del procesamiento, `subido_en` de la subida.

### 9. Esquemas (`src/schemas/medios.py`)

| Esquema | Campos |
|---|---|
| `SolicitudSubida` | `content_type` (uno de `TIPOS_PERMITIDOS`), `tamano_bytes` (entero, mayor que 0 y hasta `MEDIO_TAMANO_MAXIMO_BYTES`). `extra="forbid"` |
| `SubidaRespuesta` | `medio_id`, `bucket`, `ruta`, `token`, `url_subida`, `expira_en` |
| `MedioRespuesta` | `id`, `estado`, `subido` (bool), `url` (publica, nula si no esta confirmado), `miniatura_url` (nula si no hay miniatura), `content_type`, `tamano_bytes` |

Ninguna respuesta lleva la clave de servicio. Los limites (`MEDIO_TAMANO_MAXIMO_BYTES`, `MEDIOS_PENDIENTES_MAXIMOS`) se leen de `settings` en cada solicitud, no al importar el modulo, para que las pruebas los cambien con `monkeypatch`.

### 10. Endpoints (`src/api/v1/medios.py`)

Bajo `/api/v1`. Cada handler hace `commit` despues del servicio. El almacenamiento llega por la dependencia `get_almacenamiento` de `deps.py`, nunca llamando a `obtener_almacenamiento()` desde el endpoint.

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /medios` | Artista | 201, `SubidaRespuesta` |
| `POST /medios/{medio_id}/confirmar` | Usuario dueño | 200, `MedioRespuesta` |
| `GET /medios/{medio_id}` | Usuario dueño | 200, `MedioRespuesta` |
| `DELETE /medios/{medio_id}` | Usuario dueño | 204 |

`main.py` suma dos manejadores: `AlmacenamientoNoDisponible` da 503 con "El almacenamiento no esta disponible", y cualquier otro `ErrorAlmacenamiento` da 502 con "El almacenamiento rechazo la operacion". Sin copiar el mensaje original.

### 11. Fixture (`tests/conftest.py`)

`almacenamiento_falso`: un `AlmacenamientoFalso()` nuevo, puesto en `get_almacenamiento`, que se limpia al terminar.

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`. Son 18, pero cinco son cambios de una o dos lineas:

- `src/core/config.py`
- `src/models/medios.py`
- `alembic/versions/<nueva>_medios_subida.py` (nuevo)
- `src/storage/__init__.py` (nuevo)
- `src/storage/contrato.py` (nuevo)
- `src/storage/supabase.py` (nuevo)
- `src/storage/falso.py` (nuevo)
- `src/domain/medios.py` (nuevo)
- `src/services/medios.py` (nuevo)
- `src/schemas/medios.py` (nuevo)
- `src/api/v1/medios.py` (nuevo)
- `src/api/v1/router.py`
- `src/api/deps.py` (solo agregar `get_almacenamiento`)
- `src/main.py` (solo los dos manejadores)
- `tests/conftest.py` (solo agregar `almacenamiento_falso`)
- `tests/test_almacenamiento_supabase.py` (nuevo)
- `tests/test_medios.py` (nuevo)
- `AGENTS.md` y `.env.example` de `backend/`: las variables nuevas, el comando `python -m src.storage.supabase` y la base de pruebas local en el 5433

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior. En particular `src/payments/`, `src/workers/`, `src/services/pedidos.py` y la migracion inicial.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias. `httpx` ya esta.
- Que el archivo pase por la API: nada de `UploadFile` ni de cuerpos binarios en un endpoint.
- Aceptar una ruta, un bucket o un nombre de archivo del cliente.
- Exponer o loguear `SUPABASE_SERVICE_KEY`, el token o la `url_subida`.
- Que algo fuera de `src/storage/` mencione Supabase Storage o sus URLs.
- Crear obras, servicios o publicaciones, o generar miniaturas. Son de otros lotes.
- Pruebas que usen red.

## Pruebas obligatorias

Nombralas con prefijo `test_01_` a `test_18_` para que se puedan contar.

**Adaptador de Supabase** (`tests/test_almacenamiento_supabase.py`), todas con `httpx.MockTransport`:

1. `firmar_subida` llama al endpoint de firma con `apikey` y `Authorization`, y devuelve `token`, `url_subida` completa y `expira_en`.
2. `info` devuelve `InfoObjeto` con tamano y tipo cuando el objeto existe, y `None` con un 404.
3. Un 5xx o un timeout dan `AlmacenamientoNoDisponible`; un 401 da `CredencialesAlmacenamiento`.
4. `borrar` manda las rutas en `prefixes`; `subir` manda `x-upsert` y el `content-type`; `descargar` devuelve los bytes.
5. `preparar_bucket` crea el bucket cuando no existe y lo actualiza cuando existe, en los dos casos con `public`, el limite de tamano y los tipos permitidos.
6. La clave de servicio no aparece en `repr` del adaptador ni en el mensaje de ningun error, aunque la respuesta de error la incluya en el cuerpo.
7. Fabrica: sin configurar da el falso; `supabase` sin clave falla nombrando `SUPABASE_SERVICE_KEY`; `falso` con `ENVIRONMENT=production` falla; un valor desconocido falla.

**Dominio y API** (`tests/test_medios.py`), con `sesion_api`, `almacenamiento_falso` y `autenticar_como`:

8. `ruta_para` arma `{propietario}/{medio}.webp` para `image/webp` y rechaza `image/gif`.
9. `problema_de_subida` cubre: valido, sin subir, demasiado grande y tipo distinto.
10. `POST /medios` siendo `publico` da 403. Con `image/gif` da 422. Con un tamano mayor al maximo da 422.
11. `POST /medios` valido da 201; la ruta empieza con el id del artista y el medio queda en la base sin `subido_en`.
12. Con `MEDIOS_PENDIENTES_MAXIMOS` alcanzado, `POST /medios` da 409.
13. Si `firmar_subida` falla con `AlmacenamientoNoDisponible`, `POST /medios` da 503 y no queda ninguna fila de ese artista.
14. Confirmar sin subir da 409 y `subido_en` sigue nulo.
15. Confirmar despues de `simular_subida` da 200, `subido` verdadero y `url` publica, y hay exactamente un job `generate_thumbnail` con ese `medio_id`. Confirmar de nuevo da 200 y sigue habiendo un solo job.
16. Confirmar un objeto mas grande que el maximo, o con otro tipo, da 409 y el objeto ya no existe en el almacenamiento falso.
17. Otro usuario recibe 404 en `GET`, `confirmar` y `DELETE` del medio ajeno.
18. `DELETE` de un medio suelto da 204, marca `deleted_at` y borra el objeto. `DELETE` de un medio asociado a una obra da 409. Creá la obra con el modelo, como hace `tests/test_servicio_pedidos.py`.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] La migracion es reversible: `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head` corren sin error sobre la base de pruebas.
- [ ] `alembic heads` muestra una sola cabeza.
- [ ] `pytest -v` pasa, la salida muestra las dieciocho pruebas obligatorias, y las 237 anteriores siguen pasando.
- [ ] Nada fuera de `storage/` conoce a Supabase Storage: `grep -rniE "storage/v1|upload/sign" src --exclude-dir=storage` no devuelve nada.
- [ ] El archivo no pasa por la API: `grep -rnE "UploadFile|File\(" src/api` no devuelve nada.
- [ ] `grep -rn "obtener_almacenamiento" src/api/v1/` no devuelve nada.
- [ ] `grep -rniE "log.*(token|url_subida|service_key)" src/storage src/services/medios.py` no devuelve nada.
- [ ] `python -c "from src.main import app; print(sorted(p for p in app.openapi()['paths'] if '/medios' in p))"` muestra las rutas de la seccion 10.
- [ ] El bloque de mapeo de Supabase existe y cada entrada tiene fuente o `POR_CONFIRMAR`: pegalo completo en la entrega.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`, `src/payments/` ni `src/workers/`.

## Commit y entrega

Commiteá en `feat/lote-05-almacenamiento-medios` **solo los archivos del alcance**, con mensajes convencionales. Podés separar en dos commits, por ejemplo `feat(backend): capa de almacenamiento con adaptador de Supabase y falso` y `feat(backend): subida firmada y ciclo de vida de los medios`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. El bloque de mapeo de Supabase completo, y una tabla de lo que quedo `POR_CONFIRMAR`.
5. La tabla de endpoints tal como quedo.
6. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
