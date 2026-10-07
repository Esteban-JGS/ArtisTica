# [Lote 6] Publicaciones, feed Seguidos y Explorar

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-06-publicaciones-feed
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas. No es una red social: la parte social alimenta el momento de contratacion. La app tiene dos pestañas de inicio, **Seguidos** y **Para ti** (Explorar).

- Una **publicacion** es lo que aparece en el feed. La crea un artista (el rol Publico no publica). Puede mostrar una obra de su galeria o ser independiente (proceso, agenda), con texto y de cero a diez imagenes.
- **Una publicacion nunca tiene precio ni boton de compra.** Si muestra una obra disponible, solo lleva la etiqueta "Disponible"; el precio vive en la ficha de la obra.

Reglas del feed, que no se negocian:

| Superficie | Regla |
|---|---|
| **Seguidos** | Cronologico puro, de los artistas que el usuario sigue y sus propias publicaciones. **Jamas** lleva contenido promocionado ni reordenado |
| **Explorar** | Publicaciones recientes, filtrables por categorias, con una **cuota fija de Nuevos talentos**: una de cada cinco posiciones es de un artista con pocos seguidores. Nunca se ordena por tiempo en pantalla ni por popularidad |

En el MVP Explorar no tiene similitud de estilo (los embeddings los calcula el worker en el lote 11) ni promocionados (los boosts estan fuera del MVP).

Seguir artistas, contadores de seguidores, comentarios, reacciones y busqueda son del lote 6b. Aca las pruebas crean los seguimientos directo en la tabla `follows`.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno y la base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) estan en `AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/models/social.py` | `Publicacion`: `artista_id`, `texto`, `obra_id` (nulo, `SET NULL`), `search_vector` (columna generada), `deleted_at`. Indices: `(artista_id, created_at DESC)` y GIN de `search_vector`. **No hay indice global por fecha** |
| `src/models/users.py` | `Profile.categorias` (`varchar[]`) sin indice. `Follow(seguidor_id, seguido_id)` con unico `(seguidor_id, seguido_id)` e indice en `seguido_id` |
| `src/models/medios.py` | `MediaAsset` con `obra_id`, `publicacion_id`, `orden`. **No hay indice en `obra_id` ni en `publicacion_id`**: hoy la galeria del lote 5b recorre la tabla para buscar las imagenes de una pagina |
| `src/models/catalogo.py` | `Obra.categorias`, `Obra.estado` |
| `src/services/catalogo.py` | `_validar_medios` (medios propios, confirmados, sin borrar, sueltos, sin repetidos, hasta un maximo; los bloquea con `FOR UPDATE`) y `_reemplazar_medios`, privadas y atadas a `Obra`. `medios_de(session, obra_ids)` trae las imagenes de varias obras en una consulta. Docstring con el orden de los bloqueos (D18) |
| `src/services/medios.py` | Ciclo de vida del medio |
| `src/services/paginacion.py` | `ClaveCursor`, `ParametrosPagina`, `codificar_cursor`, `decodificar_cursor`, `CursorInvalido`, `traer_pagina`. Orden `created_at DESC, id DESC`, sin `OFFSET` |
| `src/api/paginacion.py` | `Pagina[T]` y la dependencia `Paginacion` que lee `cursor` y `tamano` y traduce `CursorInvalido` a 422 |
| `src/api/deps.py` | Alias `Sesion`, `Usuario`, `Artista`, `AlmacenamientoDeMedios`. Todo endpoint usa `Annotated` |
| `src/schemas/perfiles.py` | Validador de contacto prohibido y tipo `Categorias` |
| `src/schemas/catalogo.py` | `MedioRespuesta` con `id`, `url`, `miniatura_url` |
| `alembic/versions/` | Cabeza `8d9e0f1a2b34` |

Reglas del repositorio que aplican: el dominio no importa SQLAlchemy ni FastAPI; los servicios no importan de `src/api/`; el perfil se bloquea antes que cualquier otra fila (D18); sin `OFFSET`; sin `= Depends(...)`; un `noqa` lleva codigo y motivo.

## Objetivo

Que un artista pueda publicar, editar y borrar publicaciones, y que la app tenga el feed Seguidos y Explorar por cursor, con la cuota de Nuevos talentos.

## Diseno

### 1. Configuracion (`src/core/config.py`)

```python
MEDIOS_POR_PUBLICACION_MAXIMO: int = Field(default=10, ge=1)
EXPLORAR_CADA_N: int = Field(default=5, ge=2)            # una de cada N es nuevo talento
NUEVO_TALENTO_MAX_SEGUIDORES: int = Field(default=50, ge=1)  # menos que esto es nuevo talento
```

### 2. Medios compartidos (`src/services/medios.py` y `src/services/catalogo.py`)

Sacá la validacion y la asignacion de medios de `catalogo.py` a `medios.py`, como funciones publicas que sirvan para una obra y para una publicacion:

- `tomar_medios_sueltos(session, propietario_id, ids, *, maximo, minimo, pertenece_a)`: las mismas reglas que hoy `_validar_medios`, con `minimo` (1 para obras, 0 para publicaciones) y `pertenece_a` para aceptar los medios que ya son de esa obra o publicacion al editar.
- `asignar_medios(session, elegidos, *, obra_id=None, publicacion_id=None)`: deja exactamente esos medios, en orden, y suelta los anteriores.
- `medios_de_obras` y `medios_de_publicaciones`: una consulta para varias filas.

`catalogo.py` pasa a usarlas sin cambiar su comportamiento: las 308 pruebas existentes lo verifican.

### 3. Modelo y migracion

- Indices nuevos: `media_assets (obra_id)`, `media_assets (publicacion_id)`, `publicaciones (created_at DESC, id DESC)` para Explorar, y GIN en `profiles (categorias)` para el filtro.
- Una migracion con `down_revision = "8d9e0f1a2b34"`, reversible, con `alembic check` limpio.

### 4. Dominio del feed (`src/domain/feed.py`, nuevo, puro)

- `cuantos_de_cada(tamano, cada_n) -> tuple[int, int]`: cuantos generales y cuantos nuevos talentos lleva una pagina. Con `tamano=20` y `cada_n=5`, 16 y 4.
- `intercalar(generales, nuevos, tamano, cada_n)`: arma la pagina poniendo un nuevo talento en cada posicion multiplo de `cada_n` (5, 10, 15...). Si una de las dos listas se queda corta, la otra completa los huecos. Devuelve cada elemento marcado con su origen.

### 5. Cursor compuesto (`src/services/paginacion.py`)

Explorar lee dos flujos disjuntos y necesita un cursor con la posicion de cada uno. Sumá `codificar_cursor_compuesto(claves: Mapping[str, ClaveCursor | None]) -> str` y su inverso, con el mismo formato opaco y el mismo `CursorInvalido`. Una clave en `None` significa que ese flujo no empezo; un flujo agotado se marca para no volver a consultarlo.

### 6. Servicios

**`src/services/publicaciones.py`** (nuevo):

| Operacion | Reglas |
|---|---|
| Crear | Rol artista. `texto` obligatorio. De 0 a `MEDIOS_POR_PUBLICACION_MAXIMO` medios con `tomar_medios_sueltos`. `obra_id` opcional: tiene que ser del mismo artista y no estar borrada |
| Editar | Solo el dueño; ajena o borrada da 404. Solo `texto` |
| Borrar | Soft delete. Sus medios se marcan borrados y sus objetos se borran del almacenamiento (si falla, se loguea y se sigue) |
| Listar del artista | Por handle, sin borradas, paginado con `traer_pagina`. Handle inexistente da 404 |

**`src/services/feed.py`** (nuevo):

- **Seguidos:** publicaciones sin borrar cuyo `artista_id` es el propio usuario o uno que sigue. Orden cronologico, paginado con `traer_pagina`.
- **Explorar:** dos flujos disjuntos, los dos ordenados por `created_at DESC, id DESC`:
  - **generales:** artistas con `NUEVO_TALENTO_MAX_SEGUIDORES` seguidores o mas;
  - **nuevos talentos:** artistas con menos.
  
  El conteo de seguidores se calcula en la consulta, no se guarda en una columna. Con categorias, una publicacion entra si se cruzan con las del artista o con las de la obra que muestra (operador `&&`). Cada pagina pide a cada flujo lo que dice `cuantos_de_cada`, mas uno para saber si sigue, intercala con `intercalar` y devuelve el cursor compuesto. `siguiente_cursor` es nulo cuando los dos flujos se agotaron.

Ningun listado hace una consulta por publicacion: los medios, las obras y los datos del artista de una pagina se traen en una consulta cada uno.

### 7. Esquemas (`src/schemas/publicaciones.py`, nuevo)

- `NuevaPublicacion`: `texto` (1 a 2000, sin telefonos ni WhatsApp), `medios` (lista de ids, por defecto vacia), `obra_id` opcional. `extra="forbid"`.
- `EdicionPublicacion`: `texto`.
- `PublicacionRespuesta`: `id`, `artista` (`handle`, `nombre`, `verificado`), `texto`, `medios` (ordenados, `{id, url, miniatura_url}`), `obra` (`{id, titulo, disponible: bool}` o nulo; **sin precio**), `created_at`, y `nuevo_talento: bool | None` (verdadero o falso en Explorar, nulo en los demas listados).

### 8. Endpoints (`src/api/v1/publicaciones.py`, nuevo)

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /publicaciones` | Artista | 201 |
| `GET /publicaciones/{publicacion_id}` | Sin autenticacion | 200; 404 si no existe o esta borrada |
| `PATCH /publicaciones/{publicacion_id}` | Dueño | 200 |
| `DELETE /publicaciones/{publicacion_id}` | Dueño | 204 |
| `GET /artistas/{handle}/publicaciones?cursor=&tamano=` | Sin autenticacion | 200, `Pagina[PublicacionRespuesta]` |
| `GET /feed/seguidos?cursor=&tamano=` | Usuario | 200, `Pagina[PublicacionRespuesta]` |
| `GET /feed/explorar?categorias=&categorias=&cursor=&tamano=` | Sin autenticacion | 200, `Pagina[PublicacionRespuesta]`; hasta 5 categorias |

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `src/core/config.py` (solo las variables nuevas)
- `src/models/social.py`, `src/models/users.py`, `src/models/medios.py` (solo indices)
- `alembic/versions/<nueva>_feed.py` (nuevo)
- `src/domain/feed.py` (nuevo)
- `src/services/paginacion.py` (solo el cursor compuesto)
- `src/services/medios.py` y `src/services/catalogo.py` (solo la extraccion de la seccion 2)
- `src/services/publicaciones.py` y `src/services/feed.py` (nuevos)
- `src/schemas/publicaciones.py` (nuevo)
- `src/api/v1/publicaciones.py` (nuevo) y `src/api/v1/router.py`
- `tests/test_dominio_feed.py`, `tests/test_publicaciones_api.py`, `tests/test_feed_api.py` (nuevos)
- `.env.example`

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias.
- Endpoints de seguir, contadores, comentarios, reacciones o busqueda: son del lote 6b.
- Cualquier orden de Seguidos que no sea cronologico, o cualquier señal de popularidad, interaccion o tiempo en pantalla en Explorar.
- Un precio en una publicacion.
- Una columna con el conteo de seguidores.
- `OFFSET`, `= Depends(...)`, `float` para dinero, o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Pruebas obligatorias

Prefijo `test_01_` a `test_12_`. Las de API usan `sesion_api`, `almacenamiento_falso` y `autenticar_como`, y crean seguimientos con filas de `Follow`.

**Dominio** (`tests/test_dominio_feed.py`):

1. `cuantos_de_cada`: 20 y 5 dan 16 y 4; 3 y 5 dan 3 y 0; 5 y 5 dan 4 y 1.
2. `intercalar`: los nuevos talentos caen en las posiciones 5 y 10 de una pagina de 10; si faltan nuevos, los generales completan; si faltan generales, los nuevos completan; nunca se repite un elemento.
3. Cursor compuesto: ida y vuelta con una clave nula y otra no; uno mal formado levanta `CursorInvalido`.

**Publicaciones** (`tests/test_publicaciones_api.py`):

4. Siendo `publico`, `POST /publicaciones` da 403. Un artista publica con dos imagenes y una obra disponible propia: 201, imagenes en orden, `obra.disponible` verdadero y **ninguna clave `precio`** en toda la respuesta.
5. Una publicacion solo de texto da 201. Texto con telefono o vacio da 422. Obra ajena o borrada da 409. Un medio ajeno, sin confirmar o ya usado por una obra da 409, y no queda nada asociado.
6. Editar el texto propio da 200; el ajeno da 404. Borrar da 204, sus medios quedan borrados y sus objetos ya no estan en el almacenamiento falso, y `GET` da 404.
7. Listado de un artista con 25 publicaciones y `tamano=20`: 20 con cursor y despues 5 sin cursor, sin repetidos y en orden descendente.
8. **Regresion de la extraccion:** crear y editar una obra con medios sigue funcionando igual (las pruebas del catalogo pasan sin tocarlas).

**Feed** (`tests/test_feed_api.py`):

9. Seguidos sin token da 401 o 403. Con token muestra las publicaciones de los artistas seguidos y las propias, no las de un artista no seguido ni las borradas, en orden cronologico descendente, y paginando no repite.
10. Explorar sin token da 200. Con `categorias` filtra por las del artista o las de la obra que muestra la publicacion.
11. **Cuota de nuevos talentos:** con `NUEVO_TALENTO_MAX_SEGUIDORES` en 2 (`monkeypatch` sobre `settings`), 10 publicaciones de artistas con 2 o mas seguidores y 10 de artistas con menos: una pagina de 10 trae nuevos talentos en las posiciones 5 y 10, marcados con `nuevo_talento` verdadero y los demas falso, y recorrer todas las paginas trae las 20 sin repetidos.
12. Explorar sin ningun nuevo talento llena la pagina con generales, y sin ningun general la llena con nuevos talentos.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] La migracion es reversible: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`. `alembic heads` da una sola cabeza y `alembic check` dice `No new upgrade operations detected.`
- [ ] `pytest -v` pasa, muestra las doce pruebas obligatorias, y las 308 anteriores siguen pasando **sin modificarlas**.
- [ ] `grep -rniE "\.offset\(|offset\(" src` no devuelve nada.
- [ ] `grep -rn "precio" src/schemas/publicaciones.py src/services/feed.py src/services/publicaciones.py` no devuelve nada.
- [ ] `grep -rn "from src.api\|import src.api" src/services src/domain` no devuelve nada.
- [ ] `python -c "from src.main import app; print(sorted(p for p in app.openapi()['paths'] if 'publicaciones' in p or 'feed' in p))"` muestra las rutas de la seccion 8.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `feat/lote-06-publicaciones-feed` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `refactor(backend): medios compartidos entre obras y publicaciones`, `feat(backend): publicaciones del artista`, `feat(backend): feed Seguidos y Explorar con cuota de nuevos talentos`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. La tabla de endpoints tal como quedo.
5. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
