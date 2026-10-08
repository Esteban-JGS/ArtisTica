# [Lote 6c] Comentarios con respuestas y busqueda

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-06c-comentarios-busqueda
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas. La socializacion publica vive en los comentarios y en los "me gusta" de las publicaciones; el chat privado es otra cosa (consultas, lote 7).

La pantalla de comentarios de la app muestra:

- los comentarios de una publicacion **del mas viejo al mas nuevo**, cada uno con autor, texto, hora y su contador de "me gusta";
- **un solo nivel de respuestas** debajo de cada comentario ("Responder a ..."), sin "me gusta" propio en la interfaz;
- un total, "Comentarios · N", que **suma comentarios y respuestas**. Ese mismo numero aparece en la tarjeta de la publicacion en el feed.

Este lote construye eso y la busqueda de publicaciones y artistas. Con el cierra la parte social del MVP.

Reglas que aplican:

- **Comenta cualquier usuario con sesion**, tambien el rol Publico.
- Un comentario **no puede llevar telefonos ni WhatsApp**: es texto publico y la plataforma no puede ser vitrina para cerrar tratos afuera. Mismo validador que el perfil.
- Los contadores **no ordenan nada**: comentarios en orden cronologico, busqueda por recencia. Los resultados son organicos (no hay promocionados en el MVP).
- Ningun contador se guarda en una columna.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno y la base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) estan en `AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/models/social.py` | `Comentario(publicacion_id, profile_id, texto, deleted_at)`, con indice en `publicacion_id`. **No tiene respuesta a otro comentario.** `Publicacion` con `search_vector`, columna generada con `to_tsvector('spanish', texto)` e indice GIN. `Reaccion` para los "me gusta" de publicaciones |
| `src/models/__init__.py` | Reexporta los modelos |
| `src/services/paginacion.py` | `traer_pagina` y el cursor, **solo en orden descendente** (`created_at DESC, id DESC`) |
| `src/services/publicaciones.py` | `detallar(session, publicaciones, ..., usuario)`: medios, obras, artistas y "me gusta" de una pagina, una consulta agrupada por cada cosa |
| `src/services/social.py` | Seguir, resumen social y "me gusta" de publicaciones, idempotentes con `ON CONFLICT DO NOTHING` |
| `src/schemas/publicaciones.py` | `PublicacionRespuesta` con `me_gusta_total` y `mi_me_gusta` |
| `src/schemas/social.py` | `PerfilResumido` (`handle`, `nombre`, `verificado`, `es_artista`) |
| `src/schemas/perfiles.py` | Validador de contacto prohibido |
| `src/api/deps.py` | `Usuario`, `UsuarioOpcional`, `Sesion`, `AlmacenamientoDeMedios` |
| `src/api/paginacion.py` | `Pagina[T]` y la dependencia `Paginacion` |
| `alembic/versions/` | Cabeza `9e0f1a2b3c45`. La migracion inicial activa RLS con `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` |

Reglas del repositorio: el dominio no importa SQLAlchemy ni FastAPI; los servicios no importan de `src/api/`; el perfil se bloquea antes que cualquier otra fila (D18); sin `OFFSET`; sin `= Depends(...)`; un `noqa` lleva codigo y motivo; **toda tabla nueva tiene RLS activo y ninguna politica**.

## Objetivo

Que cualquier usuario pueda comentar, responder y dar "me gusta" a comentarios, que el feed muestre el total de comentarios, y que se puedan buscar publicaciones y artistas.

## Diseno

### 1. Modelo y migracion

- `Comentario.respuesta_a_id`: llave foranea nula a `comentarios.id`, `ondelete="CASCADE"`. Nulo es un comentario de primer nivel.
- Indices `comentarios (publicacion_id, created_at)` y `comentarios (respuesta_a_id, created_at)`.
- Tabla nueva `me_gusta_comentarios`: `comentario_id` (llave foranea, `CASCADE`), `profile_id` (llave foranea a `profiles`, `CASCADE`), unico `(comentario_id, profile_id)`, con `IdMixin` y `TimestampMixin`, **con RLS activo y sin politicas** en la misma migracion.
- Una migracion con `down_revision = "9e0f1a2b3c45"`, reversible, con `alembic check` limpio.

### 2. Orden ascendente en la paginacion (`src/services/paginacion.py`)

`traer_pagina` suma un parametro de solo palabra clave `ascendente: bool = False`. Con `True` ordena por `created_at ASC, id ASC` y la pagina siguiente filtra con `>`. El cursor no cambia de formato. Las llamadas existentes no se tocan.

### 3. Reglas puras (`src/domain/comentarios.py`, nuevo)

- `destino_de_respuesta(objetivo_id, objetivo_respuesta_a_id) -> id`: responder a una respuesta cuelga la nueva del comentario de primer nivel. Hay un solo nivel.
- `puede_borrar(autor_id, artista_de_la_publicacion_id, usuario_id) -> bool`: el autor, o el artista dueño de la publicacion (moderar lo que se dice en su publicacion).

### 4. Servicio de comentarios (`src/services/comentarios.py`, nuevo)

| Operacion | Reglas |
|---|---|
| Comentar | Publicacion existente y sin borrar (404 si no). `respuesta_a` opcional: tiene que ser un comentario sin borrar **de la misma publicacion** (409 si no), y se aplica `destino_de_respuesta` |
| Listar de una publicacion | Solo los de primer nivel, sin borrar, del mas viejo al mas nuevo, paginados. Cada uno trae autor, `me_gusta_total`, `mi_me_gusta`, `respuestas_total` y las **primeras 3 respuestas** en orden cronologico |
| Listar respuestas | De un comentario de primer nivel sin borrar, del mas viejo al mas nuevo, paginadas |
| Borrar | Si `puede_borrar`, soft delete; si no, 403. Un comentario borrado desaparece de los listados **junto con sus respuestas** |
| Me gusta | Dar y quitar, idempotentes con `ON CONFLICT DO NOTHING`, sobre cualquier comentario sin borrar |

**Sin N+1.** Una pagina de comentarios hace un numero fijo de consultas: la pagina, los autores, los contadores de "me gusta" y el propio, el total de respuestas, y las primeras tres respuestas de todos con una sola consulta (por ejemplo con `row_number() OVER (PARTITION BY respuesta_a_id ORDER BY created_at, id)`), mas los autores de esas respuestas.

### 5. Total de comentarios en el feed (`src/services/publicaciones.py`)

`detallar` suma `comentarios_total`: los comentarios sin borrar de la publicacion **mas** las respuestas sin borrar cuyo comentario de primer nivel tampoco esta borrado. Es el mismo numero que muestra "Comentarios · N". Una consulta agrupada por pagina.

### 6. Busqueda (`src/services/busqueda.py`, nuevo)

- **Publicaciones:** `search_vector @@ websearch_to_tsquery('spanish', q)`, sin borradas, por recencia (`created_at DESC`) y paginadas con `traer_pagina`. Se detallan con `detallar`, asi que traen los mismos campos que el feed.
- **Artistas:** perfiles con rol artista cuyo `handle` o `nombre` contienen `q` sin distinguir mayusculas (`ILIKE`), paginados por recencia. **Escapá `%`, `_` y `\` de `q`** antes de armar el patron, con `escape`: una busqueda de `%` no puede devolver todo.
- `q` va de 2 a 100 caracteres, recortado; fuera de eso, 422.

### 7. Esquemas

- `src/schemas/comentarios.py` (nuevo): `NuevoComentario` (`texto` de 1 a 1000, sin telefonos ni WhatsApp; `respuesta_a` opcional; `extra="forbid"`), `RespuestaComentario` (`id`, `autor: PerfilResumido`, `texto`, `created_at`, `me_gusta_total`, `mi_me_gusta`) y `ComentarioRespuesta` (lo mismo mas `respuestas_total` y `respuestas: list[RespuestaComentario]` con las primeras tres).
- `src/schemas/publicaciones.py`: `PublicacionRespuesta` suma `comentarios_total: int`.

### 8. Endpoints

`src/api/v1/comentarios.py` (nuevo):

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /publicaciones/{publicacion_id}/comentarios` | Usuario | 201, `ComentarioRespuesta` |
| `GET /publicaciones/{publicacion_id}/comentarios?cursor=&tamano=` | Opcional | 200, `Pagina[ComentarioRespuesta]` |
| `GET /comentarios/{comentario_id}/respuestas?cursor=&tamano=` | Opcional | 200, `Pagina[RespuestaComentario]` |
| `DELETE /comentarios/{comentario_id}` | Usuario | 204; 403 si no es el autor ni el artista; 404 si no existe |
| `PUT /comentarios/{comentario_id}/me-gusta` | Usuario | 204 |
| `DELETE /comentarios/{comentario_id}/me-gusta` | Usuario | 204 |

`src/api/v1/busqueda.py` (nuevo):

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `GET /buscar/publicaciones?q=&cursor=&tamano=` | Opcional | 200, `Pagina[PublicacionRespuesta]` |
| `GET /buscar/artistas?q=&cursor=&tamano=` | Sin autenticacion | 200, `Pagina[PerfilResumido]` |

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `src/models/social.py` y `src/models/__init__.py`
- `alembic/versions/<nueva>_comentarios.py` (nuevo)
- `src/services/paginacion.py` (solo `ascendente`)
- `src/domain/comentarios.py` (nuevo)
- `src/services/comentarios.py` y `src/services/busqueda.py` (nuevos)
- `src/services/publicaciones.py` (solo `comentarios_total` en `detallar`)
- `src/schemas/comentarios.py` (nuevo) y `src/schemas/publicaciones.py` (solo `comentarios_total`)
- `src/api/v1/comentarios.py` y `src/api/v1/busqueda.py` (nuevos), y `src/api/v1/router.py`
- `tests/test_comentarios_api.py` y `tests/test_busqueda_api.py` (nuevos)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias, extensiones de Postgres (como `pg_trgm`) o columnas de contador.
- Mas de un nivel de respuestas.
- Ordenar comentarios o resultados de busqueda por "me gusta" o por cualquier señal de popularidad.
- Armar SQL con texto del usuario: todo va como parametro.
- Una tabla nueva sin RLS, o con alguna politica.
- `OFFSET`, `= Depends(...)` o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Pruebas obligatorias

Prefijo `test_01_` a `test_12_`. Usan `sesion_api`, `almacenamiento_falso` y `autenticar_como`.

**Comentarios** (`tests/test_comentarios_api.py`):

1. **Reglas puras.** `destino_de_respuesta` cuelga una respuesta a una respuesta del primer nivel. `puede_borrar` es verdadero para el autor y para el artista de la publicacion, y falso para un tercero.
2. **Comentar.** Un perfil `publico` comenta y recibe 201. Sin token da 401 o 403. En una publicacion borrada da 404. Con telefono o vacio da 422.
3. **Responder.** Una respuesta a un comentario cuelga de el; una respuesta a esa respuesta cuelga del mismo comentario de primer nivel. Responder a un comentario de otra publicacion da 409.
4. **Listado.** Con 25 comentarios y `tamano=20`: 20 con cursor y 5 sin cursor, **del mas viejo al mas nuevo**, sin repetidos. Las respuestas no aparecen como primer nivel.
5. **Primeras respuestas.** Un comentario con 5 respuestas trae `respuestas_total` 5 y las 3 primeras en orden; `GET /comentarios/{id}/respuestas` trae las 5 en orden.
6. **Borrar.** El autor borra (204). El artista de la publicacion borra un comentario ajeno (204). Un tercero recibe 403. Un comentario borrado desaparece del listado con sus respuestas.
7. **Me gusta en comentarios.** Dar dos veces deja una fila; quitar dos veces da 204. `me_gusta_total` y `mi_me_gusta` correctos con token, y `mi_me_gusta` nulo sin token.
8. **Total en el feed.** Con 3 comentarios y 2 respuestas, `comentarios_total` es 5 en Seguidos, en Explorar y en el detalle. Despues de borrar el comentario que tenia las 2 respuestas, baja a 2.
9. **Sin N+1.** Contando sentencias con un listener `before_cursor_execute`, una pagina de 3 comentarios y una de 15, cada uno con respuestas, ejecutan la misma cantidad.
10. **RLS.** `me_gusta_comentarios` tiene `relrowsecurity` verdadero y ninguna fila en `pg_policies`.

**Busqueda** (`tests/test_busqueda_api.py`):

11. **Publicaciones.** Buscar una palabra encuentra las publicaciones que la contienen, incluidas sus formas (por ejemplo "acuarelas" encuentra "acuarela", por el diccionario `spanish`), no trae borradas, ordena por recencia y trae `me_gusta_total` y `comentarios_total`. `q` de 1 caracter da 422.
12. **Artistas.** Buscar por parte del handle o del nombre, sin distinguir mayusculas, trae solo artistas (no perfiles `publico`). Buscar `%` o `_` no trae a todos: trae solo los que contienen ese caracter literal.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] La migracion es reversible: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`. `alembic heads` da una sola cabeza y `alembic check` dice `No new upgrade operations detected.`
- [ ] `pytest -v` pasa, muestra las doce pruebas obligatorias, y las 331 anteriores siguen pasando.
- [ ] `grep -rn "from src.api\|import src.api" src/services src/domain` no devuelve nada.
- [ ] `grep -rniE "offset\(" src` no devuelve nada.
- [ ] `grep -rnE "f\"[^\"]*(SELECT|WHERE|LIKE)|text\(f" src` no devuelve nada: ningun SQL armado con f-strings.
- [ ] `python -c "from src.main import app; print(sorted(p for p in app.openapi()['paths'] if 'comentarios' in p or 'buscar' in p))"` muestra las rutas de la seccion 8.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `feat/lote-06c-comentarios-busqueda` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `feat(backend): comentarios con un nivel de respuestas`, `feat(backend): me gusta en comentarios y total en el feed` y `feat(backend): busqueda de publicaciones y artistas`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

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
