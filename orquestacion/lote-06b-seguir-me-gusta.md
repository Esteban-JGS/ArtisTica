# [Lote 6b] Seguir, contadores y me gusta, con la deuda DT21

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-06b-seguir-me-gusta
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas. La parte social alimenta el momento de contratacion. La app ya tiene publicaciones y los feeds Seguidos y Explorar (lote 6). Sus pantallas muestran:

- en el perfil, **seguidores** y **siguiendo**, y un boton Seguir;
- en cada publicacion, un **"Me gusta"** (una estrella) con su contador, y el de comentarios.

Este lote agrega seguir artistas, los contadores del perfil y el "me gusta" de las publicaciones, con su contador en el feed. Ademas **paga la deuda DT21** del lote 6. Los comentarios (con respuestas y su propio "me gusta") y la busqueda son del lote 6c.

Reglas que no se negocian:

- Solo se sigue a **artistas**: el rol Publico no publica, asi que no hay nada que seguir.
- El feed Seguidos sigue siendo cronologico puro: los "me gusta" y los seguidores **no cambian ningun orden**, ni en Seguidos ni en Explorar. Son datos que se muestran, no señales de ranking.
- Ningun contador se guarda en una columna: se calcula en la consulta.

### La deuda DT21

| Parte | Problema | Resultado esperado |
|---|---|---|
| Cuota en paginas chicas | Con `tamano` menor que `EXPLORAR_CADA_N` (5), la cuota de nuevos talentos da 0 y esos artistas recien aparecen cuando se agotan los generales. Rompe la regla de la cuota fija | Explorar responde 422 si `tamano` es menor que `EXPLORAR_CADA_N`, y la configuracion no carga si `EXPLORAR_CADA_N` es mayor que `PAGINA_TAMANO_DEFECTO` o que `PAGINA_TAMANO_MAXIMO` |
| Nombre del esquema | El esquema de imagen publica se llama `MedioDeObra` (en `src/schemas/catalogo.py`) y ya lo usan tambien las publicaciones | Pasa a `ImagenPublica` en `src/schemas/medios.py`, y obras y publicaciones lo usan desde ahi |

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno y la base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) estan en `AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/models/users.py` | `Follow(seguidor_id, seguido_id)`, unico `(seguidor_id, seguido_id)`, indice en `seguido_id`, y `CHECK` que impide seguirse a uno mismo |
| `src/models/social.py` | `Reaccion(publicacion_id, profile_id, tipo)`, `tipo` es texto, unico `(publicacion_id, profile_id, tipo)` |
| `src/domain/enums.py` | Todos los enums del dominio. No hay uno de reacciones |
| `src/schemas/catalogo.py:149` | `MedioDeObra` (`id`, `url`, `miniatura_url`, con `desde(medio, almacenamiento)`) |
| `src/schemas/medios.py` | `MedioRespuesta`, el del ciclo de subida. **Es otro esquema**: no lo confundas ni lo cambies |
| `src/schemas/publicaciones.py` | `PublicacionRespuesta`: `id`, `artista`, `texto`, `medios: list[MedioDeObra]`, `obra`, `created_at`, `nuevo_talento` |
| `src/services/publicaciones.py` | `detallar(session, publicaciones, nuevo_talento)`: medios, obras y artistas de una pagina con una consulta cada uno. La usan el listado, el detalle y los dos feeds |
| `src/services/feed.py` | `seguidos(session, usuario, paginacion)` y `explorar(...)` |
| `src/services/paginacion.py` | `traer_pagina(session, stmt, modelo, parametros)` sobre cualquier modelo con `created_at` e `id` |
| `src/api/deps.py` | `security = HTTPBearer()` (falla sin token). Alias `Sesion`, `Usuario`, `Artista`, `AlmacenamientoDeMedios`. No existe un usuario opcional |
| `src/api/v1/publicaciones.py` | `parametros_de_explorar` valida `tamano` con `Query(ge=1, ...)`. Explorar es publico |
| `src/api/v1/perfiles.py` | `GET /perfiles/{handle}` publico, declarado despues de las rutas `/perfiles/yo...` |
| `src/core/config.py` | `PAGINA_TAMANO_DEFECTO = 20`, `PAGINA_TAMANO_MAXIMO = 50`, `EXPLORAR_CADA_N = 5`, y el validador `_rechazar_combinaciones_inseguras` |

Reglas del repositorio: el dominio no importa SQLAlchemy ni FastAPI; los servicios no importan de `src/api/`; el perfil se bloquea antes que cualquier otra fila (D18); sin `OFFSET`; sin `= Depends(...)`; un `noqa` lleva codigo y motivo.

## Objetivo

Que un usuario pueda seguir artistas y dar "me gusta" a publicaciones, que el perfil y el feed muestren sus contadores, y que DT21 quede pagada.

## Diseno

### 1. Usuario opcional (`src/api/deps.py`)

`UsuarioOpcional = Annotated[Profile | None, Depends(get_usuario_opcional)]`, con un `HTTPBearer(auto_error=False)` propio:

- sin token, `None`;
- con un token **invalido o vencido**, 401, igual que hoy (un token roto no se ignora en silencio);
- con un token valido cuyo perfil no existe, `None`.

Las pruebas lo cubren sobrescribiendo `get_current_user_payload`, como hoy.

### 2. Seguir (`src/services/social.py`, nuevo)

- `seguir(session, usuario, handle)`: el seguido tiene que existir (404) y ser **artista** (409, "Solo se sigue a artistas"); seguirse a uno mismo da 409. Idempotente: `INSERT ... ON CONFLICT DO NOTHING` sobre el unico, sin leer antes.
- `dejar_de_seguir(session, usuario, handle)`: idempotente. Handle inexistente da 404.
- `resumen(session, handle, usuario)`: `seguidores`, `siguiendo` y `lo_sigo` (`None` si no hay usuario; `False` si es el propio perfil). Contado en la consulta.
- `seguidores_de(session, handle, paginacion)` y `seguidos_por(session, handle, paginacion)`: perfiles paginados con `traer_pagina` sobre `Follow` (orden de cuando se siguio, mas reciente primero).

### 3. Me gusta

- `TipoReaccion` en `src/domain/enums.py` con un solo valor, `ME_GUSTA = "me_gusta"`. La columna `reacciones.tipo` sigue siendo texto: **sin migracion**.
- En `src/services/social.py`: `dar_me_gusta(session, usuario, publicacion_id)` y `quitar_me_gusta(...)`, idempotentes (el primero con `ON CONFLICT DO NOTHING`). Una publicacion inexistente o borrada da 404. Cualquier usuario puede, tambien el rol Publico y tambien el autor.

### 4. Contadores en las publicaciones (`src/services/publicaciones.py`)

`detallar` recibe ademas el usuario que mira (`Profile | None`) y suma a cada `PublicacionDetalle`:

- `me_gusta_total`: con **una consulta agrupada** para toda la pagina;
- `mi_me_gusta`: `None` sin usuario; si hay, con **una consulta** para toda la pagina.

`seguidos`, `explorar`, el listado del artista y el detalle pasan el usuario. Ningun orden cambia.

### 5. DT21

- `src/core/config.py`: el validador rechaza `EXPLORAR_CADA_N` mayor que `PAGINA_TAMANO_DEFECTO` o que `PAGINA_TAMANO_MAXIMO`, nombrando las variables.
- `src/api/v1/publicaciones.py`: `parametros_de_explorar` responde 422 si `tamano` es menor que `settings.EXPLORAR_CADA_N`, leido en cada solicitud (las pruebas lo cambian con `monkeypatch`). El mensaje dice el minimo.
- `ImagenPublica` en `src/schemas/medios.py`, con los mismos campos y el mismo `desde` que `MedioDeObra`. `src/schemas/catalogo.py` y `src/schemas/publicaciones.py` lo importan de ahi, y `MedioDeObra` deja de existir.

### 6. Esquemas

- `src/schemas/publicaciones.py`: `PublicacionRespuesta` suma `me_gusta_total: int` y `mi_me_gusta: bool | None`.
- `src/schemas/social.py` (nuevo): `ResumenSocial` (`seguidores`, `siguiendo`, `lo_sigo`) y `PerfilResumido` (`handle`, `nombre`, `verificado`, `es_artista`).

### 7. Endpoints (`src/api/v1/social.py`, nuevo, y los cambios en `publicaciones.py`)

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /artistas/{handle}/seguir` | Usuario | 204 |
| `DELETE /artistas/{handle}/seguir` | Usuario | 204 |
| `GET /perfiles/{handle}/social` | Opcional | 200, `ResumenSocial` |
| `GET /perfiles/{handle}/seguidores?cursor=&tamano=` | Sin autenticacion | 200, `Pagina[PerfilResumido]` |
| `GET /perfiles/{handle}/siguiendo?cursor=&tamano=` | Sin autenticacion | 200, `Pagina[PerfilResumido]` |
| `PUT /publicaciones/{publicacion_id}/me-gusta` | Usuario | 204 |
| `DELETE /publicaciones/{publicacion_id}/me-gusta` | Usuario | 204 |
| `GET /publicaciones/{id}`, `GET /artistas/{handle}/publicaciones`, `GET /feed/explorar` | Pasan a **opcional** | Igual que hoy, con `me_gusta_total` y `mi_me_gusta` |
| `GET /feed/seguidos` | Usuario, como hoy | Con `me_gusta_total` y `mi_me_gusta` |

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `src/core/config.py` (solo el validador de DT21)
- `src/api/deps.py` (solo el usuario opcional)
- `src/domain/enums.py` (solo `TipoReaccion`)
- `src/schemas/medios.py` (solo `ImagenPublica`)
- `src/schemas/catalogo.py` (solo el cambio de `MedioDeObra` a `ImagenPublica`)
- `src/schemas/publicaciones.py`
- `src/schemas/social.py` (nuevo)
- `src/services/social.py` (nuevo)
- `src/services/publicaciones.py` (solo `detallar` y quien lo llama)
- `src/services/feed.py` (solo pasar el usuario)
- `src/api/v1/social.py` (nuevo)
- `src/api/v1/publicaciones.py`
- `src/api/v1/router.py`
- `tests/test_social_api.py` (nuevo)
- Pruebas existentes **solo** si fallan por el cambio de nombre a `ImagenPublica` o porque una respuesta suma campos

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular crear una migracion.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias.
- Comentarios, me gusta en comentarios o busqueda: son del lote 6c.
- Que un "me gusta" o un seguidor cambie el orden de Seguidos o de Explorar.
- Una columna con un contador.
- Seguir a alguien que no es artista.
- `OFFSET`, `= Depends(...)` o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Pruebas obligatorias

En `tests/test_social_api.py`, con prefijo `test_01_` a `test_10_`. Usan `sesion_api`, `almacenamiento_falso` y `autenticar_como`.

1. **Seguir.** Seguir a un artista da 204; repetirlo da 204 y hay una sola fila. Dejar de seguir da 204, y repetirlo tambien. Seguirse a uno mismo da 409; seguir a un perfil `publico` da 409; un handle inexistente da 404; sin token da 401 o 403.
2. **Resumen.** `seguidores` y `siguiendo` correctos. `lo_sigo` es verdadero o falso con token, `None` sin token y falso en el propio perfil. Con un token invalido da 401: para esto, sin sobrescribir la dependencia, mandá un `Authorization: Bearer basura`.
3. **Listas.** Con 25 seguidores y `tamano=20`: 20 con cursor y 5 sin cursor, sin repetidos, el mas reciente primero. Lo mismo para `siguiendo`.
4. **Me gusta.** Dar "me gusta" dos veces deja una fila y da 204 las dos veces; quitarlo dos veces da 204. Un perfil `publico` puede. Una publicacion borrada da 404.
5. **Contadores en el feed.** En Seguidos, `me_gusta_total` es correcto y `mi_me_gusta` es verdadero en la que el usuario marco y falso en las otras. En Explorar sin token, `mi_me_gusta` es nulo; con token es booleano. El detalle de una publicacion trae los mismos campos.
6. **El orden no cambia.** Una publicacion vieja con muchos "me gusta" no sube en Seguidos ni en Explorar: el orden es el mismo que sin "me gusta".
7. **Sin N+1.** Contando las sentencias SQL con un listener `before_cursor_execute` sobre el engine de la sesion de prueba, una pagina de Seguidos de 3 publicaciones y una de 15, con token, ejecutan la misma cantidad de sentencias.
8. **Seguir de punta a punta.** Despues de `POST /artistas/{handle}/seguir`, las publicaciones de ese artista aparecen en Seguidos; despues del `DELETE`, desaparecen.
9. **DT21, cuota.** Con `EXPLORAR_CADA_N` en 5, Explorar con `tamano=4` da 422 y el mensaje dice el minimo; con `tamano=5` da 200. `Settings(...)` con `EXPLORAR_CADA_N=30` y los tamaños por defecto no carga y nombra las variables.
10. **DT21, nombre.** En `app.openapi()["components"]["schemas"]` existe `ImagenPublica` y no existe `MedioDeObra`. Una obra y una publicacion siguen devolviendo `medios` con `id`, `url` y `miniatura_url`.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `pytest -v` pasa, muestra las diez pruebas obligatorias, y las 320 anteriores siguen pasando.
- [ ] `alembic check` dice `No new upgrade operations detected.` y `git diff --stat develop...HEAD -- alembic` no devuelve nada: no hay migracion.
- [ ] `grep -rn "MedioDeObra" src tests` no devuelve nada.
- [ ] `grep -rn "from src.api\|import src.api" src/services src/domain` no devuelve nada.
- [ ] `grep -rniE "offset\(" src` no devuelve nada.
- [ ] `python -c "from src.main import app; print(sorted(p for p in app.openapi()['paths'] if any(x in p for x in ('seguir', 'social', 'seguidores', 'siguiendo', 'me-gusta'))))"` muestra las rutas de la seccion 7.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `feat/lote-06b-seguir-me-gusta` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `fix(backend): Explorar exige la cuota minima e ImagenPublica neutra`, `feat(backend): seguir artistas y contadores del perfil` y `feat(backend): me gusta en publicaciones con contadores en el feed`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados, y cuales pruebas existentes tocaste y por que.
3. La salida literal de cada criterio, en orden.
4. La tabla de endpoints tal como quedo.
5. Una tabla con las dos partes de DT21 y la evidencia de que quedaron pagadas.
6. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
