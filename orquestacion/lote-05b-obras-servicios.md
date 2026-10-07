# [Lote 5b] Obras y servicios con limites de plan

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-05b-obras-servicios
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Funciona con **comisiones abiertas, no como tienda**: el artista muestra lo que hace y vende su habilidad.

- Una **obra** es una pieza de la galeria del artista. Puede estar en `exhibicion` (solo se muestra), `disponible` (terminada, con precio fijo; un cliente toca "La quiero" y se crea un pedido) o `vendida`. A `vendida` solo la lleva el servicio de pedidos al despachar; nadie la pone a mano.
- Un **servicio** es un paquete con precio base que el artista ofrece ("Retrato A4", "Serenata 30 min"), de tipo `encargo` o `evento`. Los clientes lo consultan; la cotizacion final se negocia en otro lote.

| Plan | Servicios activos | Obras disponibles a la vez | Obras en exhibicion |
|---|---|---|---|
| Taller (gratis) | 2 | 5 | Sin limite |
| Estudio | Sin limite | Sin limite | Sin limite |

**Nunca se limita publicar ni recibir pedidos**: el limite de Taller es sobre servicios activos y obras **disponibles**, no sobre la galeria.

Decision D11, que este lote aplica: si un artista baja de Estudio a Taller con mas servicios u obras disponibles que el limite, **no se oculta ni se borra nada**. Solo se le impide crear o activar otro hasta quedar por debajo.

Este lote construye el catalogo del artista sobre los medios del lote 5 (imagenes ya subidas y confirmadas) y deja la paginacion por cursor que van a reusar el feed y los listados siguientes.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno y la base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) estan en `AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/models/catalogo.py` | `Obra`: `artista_id`, `titulo`, `descripcion`, `estado`, `precio` (`Numeric(12,2)`, nulo), `categorias`, `style_embedding`, `hash_imagen`, `deleted_at`. Restriccion: fuera de `exhibicion` el precio es obligatorio y positivo. Indice solo en `artista_id`. `Servicio`: `artista_id`, `titulo`, `descripcion`, `precio_base`, `tipo`, `activo`, `deleted_at` |
| `src/models/medios.py` | `MediaAsset` con `obra_id`, `publicacion_id`, `bucket`, `storage_path`, `thumbnail_path`, `subido_en` (nulo hasta confirmar), `deleted_at`. No tiene orden |
| `src/models/pedidos.py` | Indice unico parcial `ux_pedidos_obra_activa`: una obra tiene como maximo un pedido no terminado |
| `src/domain/enums.py` | Todos los enums, entre ellos `EstadoObra`, `TipoServicio`, `PlanArtista` |
| `src/domain/pedidos.py` | `ESTADOS_TERMINALES` |
| `src/services/pedidos.py` | `crear_pedido_obra_disponible` exige obra no borrada, `disponible` y con precio; `confirmar_obra` la pasa a `vendida`. No se toca |
| `src/services/perfiles.py` | `bloquear_perfil(session, perfil_id)`: `SELECT ... FOR UPDATE` sobre `profiles`, el bloqueo por artista |
| `src/services/medios.py` | Ciclo del medio. Un medio confirmado tiene `subido_en`; uno suelto no tiene `obra_id` ni `publicacion_id` |
| `src/storage/` | Contrato `Almacenamiento` con `url_publica(bucket, ruta)` y `borrar(bucket, rutas)` |
| `src/schemas/perfiles.py` | Tipos anotados `Categorias` (hasta 5, de 1 a 40 caracteres, sin repetidas) y el validador que rechaza telefonos y WhatsApp (`dominio.contiene_contacto_prohibido`) |
| `src/api/deps.py` | Alias `Sesion`, `Usuario`, `Artista`, `AlmacenamientoDeMedios`, entre otros. **Todo endpoint usa estos alias con `Annotated`**: el lint (`FAST002`) rechaza `= Depends(...)` |
| `src/core/config.py` | `MONTO_MINIMO_PEDIDO = 2500.00` |
| `alembic/versions/` | Cabeza `7c8d9e0f1a23`. `alembic/env.py` compara tambien los `server_default` |
| `tests/conftest.py` | `sesion_api`, `pasarela_falsa`, `almacenamiento_falso`, `autenticar_como` |

## Objetivo

Que un artista pueda crear, editar y borrar sus obras y servicios con los limites de su plan, y que cualquiera pueda ver su catalogo publico paginado por cursor.

## Diseno

### 1. Limites (`src/domain/catalogo.py`, nuevo, puro)

```python
@dataclass(frozen=True)
class LimitesPlan:
    servicios_activos_taller: int
    obras_disponibles_taller: int
    medios_por_obra: int

    @classmethod
    def desde_config(cls, config) -> "LimitesPlan": ...

    def servicios_activos(self, plan: PlanArtista) -> int | None: ...   # None: sin limite
    def obras_disponibles(self, plan: PlanArtista) -> int | None: ...
```

Mas funciones puras para: si se puede sumar uno mas (`actuales < limite`, o sin limite), y si un precio es valido para una obra disponible o un servicio (positivo, con dos decimales como maximo, y no menor que `MONTO_MINIMO_PEDIDO`).

Configuracion nueva en `src/core/config.py`: `LIMITE_SERVICIOS_TALLER = 2`, `LIMITE_OBRAS_DISPONIBLES_TALLER = 5`, `MEDIOS_POR_OBRA_MAXIMO = 10`, `PAGINA_TAMANO_DEFECTO = 20`, `PAGINA_TAMANO_MAXIMO = 50`, todos con `Field(ge=1)`.

### 2. Paginacion por cursor (`src/api/paginacion.py`, nuevo)

- Orden `created_at DESC, id DESC`. El cursor es opaco: base64 url-safe de `{"t": "<created_at ISO con zona>", "id": "<uuid>"}`.
- La pagina siguiente filtra con `tuple_(created_at, id) < tuple_(t, id)`. Nunca `OFFSET`.
- Se piden `tamano + 1` filas para saber si hay pagina siguiente. `siguiente_cursor` es nulo en la ultima.
- Un cursor mal formado da 422.
- Un esquema generico `Pagina[T]` con `items` y `siguiente_cursor`.

### 3. Modelo y migracion

- `MediaAsset.orden`: `SmallInteger`, nulo. El orden de las imagenes dentro de la obra; la de orden 0 es la portada.
- Indice `ix_obras_artista_id_created_at` sobre `obras (artista_id, created_at DESC)`, para el listado del artista.
- Una migracion con `down_revision = "7c8d9e0f1a23"`, reversible. `alembic check` tiene que quedar limpio.

### 4. Servicio (`src/services/catalogo.py`, nuevo)

Hace `flush` y nunca `commit`. Recibe `LimitesPlan`, el monto minimo y el almacenamiento como parametros.

**Obras**

| Operacion | Reglas |
|---|---|
| Crear | Rol artista. Entre 1 y `medios_por_obra` medios, todos **del artista, confirmados (`subido_en`), sin borrar y sueltos** (sin `obra_id` ni `publicacion_id`), sin repetidos. Si alguno falla, 409 y no se asocia ninguno. Los medios toman `obra_id` y `orden` segun la posicion en la lista. Estado `exhibicion` (precio opcional) o `disponible` (precio valido obligatorio). Si es `disponible`, se bloquea el perfil con `bloquear_perfil` y se verifica el limite de obras disponibles **con el bloqueo tomado** |
| Editar | Solo el dueño; ajena o borrada da 404. Se bloquea la obra con `FOR UPDATE`. Campos: `titulo`, `descripcion`, `categorias`, `precio`, `estado` (solo `exhibicion` o `disponible`), `medios` (reemplaza la lista completa con las mismas reglas de crear; los que salen quedan sueltos, con `obra_id` y `orden` nulos). Pasar a `disponible` verifica el limite con el perfil bloqueado y exige precio valido |
| Obra con pedido activo | Si tiene un pedido cuyo estado no esta en `ESTADOS_TERMINALES`, no se puede cambiar `precio`, `estado` ni `medios`, ni borrar: 409. `titulo`, `descripcion` y `categorias` si |
| Obra `vendida` | Solo `titulo`, `descripcion` y `categorias`. Lo demas da 409 |
| Borrar | Soft delete. Si la obra **nunca** tuvo pedidos, sus medios tambien se marcan borrados y sus objetos se borran del almacenamiento (si el borrado falla, se loguea y se sigue). Si tuvo alguno, sus medios se conservan como historial del pedido |

**Servicios**

| Operacion | Reglas |
|---|---|
| Crear | Rol artista. `titulo`, `descripcion`, `precio_base` valido, `tipo` (`encargo` o `evento`), `activo` (por defecto verdadero). Si nace activo, verifica el limite de servicios activos con el perfil bloqueado |
| Editar | Solo el dueño; ajeno o borrado da 404. Activar verifica el limite con el perfil bloqueado. Desactivar siempre se puede |
| Borrar | Soft delete |

**Limites del artista:** una funcion que devuelve plan, servicios activos, limite de servicios, obras disponibles y limite de obras disponibles (`None` si no hay limite). Cuenta solo lo no borrado.

### 5. Esquemas (`src/schemas/catalogo.py`, nuevo)

- Entradas con `extra="forbid"`. `titulo` de 1 a 120 caracteres, `descripcion` hasta 2000. **`titulo` y `descripcion` rechazan telefonos y WhatsApp**, con el mismo validador de perfiles. `categorias` reusa el tipo `Categorias` de `src/schemas/perfiles.py`. Montos en `Decimal`.
- `ObraRespuesta`: `id`, `artista_handle`, `titulo`, `descripcion`, `estado`, `precio` (**solo si esta `disponible`**; nulo en exhibicion y vendida), `categorias`, `medios` (lista ordenada de `{id, url, miniatura_url}`), `created_at`.
- `ServicioRespuesta`: `id`, `artista_handle`, `titulo`, `descripcion`, `precio_base`, `tipo`, `activo`.
- `LimitesRespuesta`: lo de la seccion 4.
- Las URLs salen de `almacenamiento.url_publica`; `miniatura_url` es nula si no hay `thumbnail_path`.

### 6. Endpoints (`src/api/v1/catalogo.py`, nuevo)

Bajo `/api/v1`, con los alias de `deps.py`. Los handlers hacen `commit` despues del servicio.

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /obras` | Artista | 201, `ObraRespuesta` |
| `GET /obras/{obra_id}` | **Sin autenticacion** | 200; 404 si no existe o esta borrada |
| `PATCH /obras/{obra_id}` | Dueño | 200, `ObraRespuesta` |
| `DELETE /obras/{obra_id}` | Dueño | 204 |
| `GET /artistas/{handle}/obras?cursor=&tamano=` | **Sin autenticacion** | 200, `Pagina[ObraRespuesta]`, todos los estados, sin borradas |
| `POST /servicios` | Artista | 201, `ServicioRespuesta` |
| `GET /servicios/mios?cursor=&tamano=` | Artista | 200, `Pagina[ServicioRespuesta]`, incluidos los inactivos |
| `GET /servicios/{servicio_id}` | **Sin autenticacion** | 200 si esta activo y sin borrar; si no, 404 |
| `PATCH /servicios/{servicio_id}` | Dueño | 200, `ServicioRespuesta` |
| `DELETE /servicios/{servicio_id}` | Dueño | 204 |
| `GET /artistas/{handle}/servicios?cursor=&tamano=` | **Sin autenticacion** | 200, `Pagina[ServicioRespuesta]`, solo activos |
| `GET /catalogo/limites` | Artista | 200, `LimitesRespuesta` |

`tamano` va de 1 a `PAGINA_TAMANO_MAXIMO`, con `PAGINA_TAMANO_DEFECTO` si no viene. Un `handle` inexistente da 404. **Sin N+1:** un listado de obras hace una consulta para la pagina y una para los medios de esas obras, no una por obra. `/servicios/mios` se declara antes que `/servicios/{servicio_id}`.

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `src/core/config.py` (solo las variables nuevas)
- `src/models/medios.py` (solo `orden`)
- `src/models/catalogo.py` (solo el indice nuevo)
- `alembic/versions/<nueva>_catalogo.py` (nuevo)
- `src/domain/catalogo.py` (nuevo)
- `src/services/catalogo.py` (nuevo)
- `src/schemas/catalogo.py` (nuevo)
- `src/api/paginacion.py` (nuevo)
- `src/api/v1/catalogo.py` (nuevo)
- `src/api/v1/router.py`
- `tests/test_dominio_catalogo.py` (nuevo)
- `tests/test_catalogo_api.py` (nuevo)
- `.env.example` (las variables nuevas)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior. En particular `src/services/pedidos.py`, `src/services/medios.py`, `src/services/perfiles.py`, `src/payments/` y `src/storage/`.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias.
- Paginar con `OFFSET`.
- Poner una obra en `vendida` desde la API.
- Limitar la cantidad de obras en exhibicion, o cobrar o limitar algo que no sea servicios activos y obras disponibles en Taller.
- Ocultar o borrar contenido por haber bajado de plan.
- `= Depends(...)` en una firma, `float` para dinero, o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Pruebas obligatorias

Prefijo `test_01_` a `test_15_`. Las de API usan `sesion_api`, `almacenamiento_falso` y `autenticar_como`; para tener medios confirmados, usá el servicio de medios o creá las filas con `subido_en`.

**Dominio y paginacion** (`tests/test_dominio_catalogo.py`):

1. `LimitesPlan`: Taller da 2 y 5, Estudio da `None`; sumar uno mas con 4 de 5 se puede y con 5 de 5 no.
2. Precio: menor que el minimo, cero, negativo o con tres decimales se rechaza; el minimo exacto se acepta.
3. Cursor: ida y vuelta conserva fecha con zona e id; un cursor mal formado levanta el error que el endpoint traduce a 422.

**API** (`tests/test_catalogo_api.py`):

4. `POST /obras` siendo `publico` da 403. Un artista crea una obra en exhibicion con dos medios: 201, medios en orden 0 y 1 con `obra_id`, y la respuesta los trae ordenados.
5. Medios invalidos: ajeno, sin confirmar, ya asociado, borrado, repetido, lista vacia y mas de diez. Cada caso da 409 o 422, y ningun medio queda asociado.
6. Taller: cinco obras disponibles se crean; la sexta disponible da 409; una en exhibicion se sigue creando. En Estudio la sexta disponible se crea.
7. D11: un artista Estudio con seis disponibles baja a Taller. El listado publico sigue mostrando las seis. Crear otra disponible da 409. Pasar dos a exhibicion se puede, y con cuatro disponibles crear una mas se puede.
8. Precio de obra disponible menor que el minimo: 422. Un telefono en la `descripcion`: 422.
9. Obra con un pedido activo (creado con el servicio de pedidos, como en `tests/test_servicio_pedidos.py`): cambiar `precio` o `estado` da 409, borrar da 409, cambiar `titulo` da 200.
10. Obra `vendida` (ponela asi directo en la base): cambiar `estado` da 409, cambiar `titulo` da 200.
11. Borrar una obra sin pedidos: 204, sus medios quedan borrados y sus objetos ya no estan en el almacenamiento falso, `GET /obras/{id}` da 404 y no aparece en el listado publico.
12. Listado publico de 25 obras con `tamano=20`: primera pagina de 20 con cursor, segunda de 5 sin cursor, sin repetidos, en orden descendente. `precio` solo aparece en las disponibles. Un `handle` inexistente da 404.
13. Servicios en Taller: dos activos se crean, el tercero activo da 409, uno inactivo se crea, y activarlo da 409. En Estudio no hay limite.
14. Servicios: el listado publico trae solo los activos; `/servicios/mios` trae tambien los inactivos; `GET /servicios/{id}` de uno inactivo da 404; editar un servicio ajeno da 404.
15. `GET /catalogo/limites` da los contadores y limites correctos en Taller, y limites nulos en Estudio.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] La migracion es reversible: `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head` sin error. `alembic heads` da una sola cabeza y `alembic check` dice `No new upgrade operations detected.`
- [ ] `pytest -v` pasa, muestra las quince pruebas obligatorias, y las 292 anteriores siguen pasando.
- [ ] `grep -rniE "offset\(|\.offset" src` no devuelve nada.
- [ ] `grep -rn "= Depends(" src` no devuelve nada.
- [ ] `grep -rn "EstadoObra.VENDIDA" src --include=*.py` solo devuelve `src/services/pedidos.py` y, si lo usas para la regla de solo lectura, `src/domain/catalogo.py` o `src/services/catalogo.py`, nunca un endpoint.
- [ ] `python -c "from src.main import app; print(sorted(p for p in app.openapi()['paths'] if any(x in p for x in ('obras', 'servicios', 'catalogo'))))"` muestra las rutas de la seccion 6.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `feat/lote-05b-obras-servicios` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `feat(backend): paginacion por cursor y limites de plan`, `feat(backend): obras con medios ordenados` y `feat(backend): servicios del artista`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. La tabla de endpoints tal como quedo, con codigos de respuesta.
5. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
