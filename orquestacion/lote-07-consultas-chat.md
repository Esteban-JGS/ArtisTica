# [Lote 7] Consultas y chat

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-07-consultas-chat
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

Verificá tambien que `develop` ya trae el lote 6d: `backend/alembic/versions/` tiene que tener `b1c2d3e4f5a6_indices.py` y `backend/src/core/sentry.py` tiene que existir. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. La contratacion empieza con una **consulta**: un cliente le escribe a un artista sobre un servicio, una obra o en general, y esa conversacion es el unico chat entre cliente y artista. Si avanza, el artista cotiza por ese mismo hilo (lote 8). No existe el mensaje directo suelto entre cliente y artista.

Este lote hace los endpoints de consultas y mensajes. Las decisiones ya tomadas:

| Tema | Decision |
|---|---|
| Tiempo real | No hay. La app consulta cada pocos segundos: pide los mensajes posteriores al ultimo que tiene, y la bandeja con el conteo de no leidos. Supabase Realtime exigiria politicas de RLS, y aca RLS esta activo sin politicas |
| Datos de contacto en el chat | Un telefono, "WhatsApp" o "SINPE" **no bloquea**: el mensaje se guarda igual y lleva un aviso suave que ven los dos lados: "Si pagás fuera de ArtísTica, no tenés protección ni reseña" |
| Spam | Una cuenta con menos de 7 dias puede abrir como maximo 5 consultas en 24 horas. Los dos numeros son configuracion |
| Consulta repetida | Si el cliente ya tiene una consulta `abierta` o `cotizada` con el mismo artista y la misma referencia, no se crea otra: el mensaje se agrega a esa |
| Fuera del lote | Mensajes libres entre artistas, adjuntos en el chat, notificaciones push, cotizar (lote 8) y "La quiero" (lote 8) |

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `backend/src/models/consultas.py` | `Consulta` con `cliente_id`, `artista_id`, `servicio_id` y `obra_id` opcionales, `estado` (`EstadoConsulta`) y el check `cliente_no_es_artista`. `Mensaje` con `consulta_id` (indice simple), `remitente_id` y `texto`. Las dos con `IdMixin` y `TimestampMixin` |
| `backend/src/domain/enums.py:43` | `EstadoConsulta`: `abierta`, `cotizada`, `convertida`, `descartada` |
| `backend/src/domain/pedidos.py:89` | `TRANSICIONES_CONSULTA` y `validar_transicion_consulta`. No se tocan |
| `backend/src/services/pedidos.py:146` | `crear_pedido_desde_cotizacion` bloquea la consulta y la pasa a `cotizada`. No se toca |
| `backend/src/domain/perfiles.py:29` | `contiene_contacto_prohibido(texto)`: telefonos de Costa Rica y WhatsApp. El perfil, el catalogo, las publicaciones y los comentarios lo usan para **rechazar**. El chat lo usa para **avisar** |
| `backend/src/services/perfiles.py:55` | `bloquear_perfil(session, perfil_id)`: `SELECT ... FOR UPDATE` del perfil |
| `backend/src/services/paginacion.py` | `traer_pagina(session, stmt, modelo, parametros, *, ascendente=False)`: keyset siempre sobre `(created_at, id)`. `codificar_cursor(fecha, id)` arma el cursor opaco |
| `backend/src/api/paginacion.py` | `Paginacion` (lee `cursor` y `tamano`) y `Pagina[T]` |
| `backend/src/api/deps.py` | `Sesion`, `Usuario` (perfil con token; sin perfil, 404) |
| `backend/src/core/exceptions.py` | `ResourceNotFound` (404), `ActorNoAutorizado` (403), `ReglaDeNegocioViolada` e `InvalidStateTransition` (409). Los mapea `backend/src/main.py:88` |
| `backend/src/domain/catalogo.py:33` | `LimitesPlan` con `desde_config(config)`: el patron para pasar limites de `Settings` al servicio sin que el servicio lea `settings` |
| `backend/src/schemas/catalogo.py:75` | `Monto`: el tipo de dinero validado de los precios |
| `backend/src/schemas/social.py` | `PerfilResumido.desde(perfil)` |
| `backend/tests/test_comentarios_api.py` | Patron de pruebas de API: fabricas `_perfil`, fixture `cliente`, `autenticar_como`, y el conteo de sentencias SQL con `event.listen(..., "before_cursor_execute", ...)` |
| `backend/alembic/versions/` | Cabeza `b1c2d3e4f5a6` |

La base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) y las variables estan en `backend/AGENTS.md`.

## Objetivo

Que un cliente abra consultas y converse con el artista por la API, con bandeja, no leidos, aviso suave por datos de contacto y limite de consultas para cuentas nuevas.

## Alcance

Archivos que podés crear o modificar:

- `backend/src/models/consultas.py`
- `backend/alembic/versions/c2d3e4f5a6b7_consultas_chat.py` (nuevo)
- `backend/src/domain/consultas.py` (nuevo)
- `backend/src/core/config.py` (solo las dos variables nuevas)
- `backend/src/core/exceptions.py` (solo `LimiteExcedido`)
- `backend/src/main.py` (solo el manejador de `LimiteExcedido`)
- `backend/src/services/paginacion.py` (solo el parametro `columna` de `traer_pagina`)
- `backend/src/services/consultas.py` (nuevo)
- `backend/src/schemas/consultas.py` (nuevo)
- `backend/src/api/v1/consultas.py` (nuevo)
- `backend/src/api/v1/router.py`
- `backend/.env.example` y `backend/AGENTS.md` (las dos variables nuevas)
- `backend/tests/test_dominio_consultas.py` (nuevo)
- `backend/tests/test_consultas_api.py` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular `mobile/`, `src/domain/pedidos.py` y `src/services/pedidos.py`.
- Agregar librerias, tablas nuevas o politicas de RLS.
- Cotizar, crear pedidos o implementar "La quiero": es el lote 8.
- Mensajes sin consulta, adjuntos, WebSockets, Supabase Realtime o notificaciones push.
- Rechazar un mensaje por tener un telefono, "WhatsApp" o "SINPE": en el chat solo se avisa.
- Bloquear cualquier fila antes que el perfil (D18). El orden en todo el backend es perfil, despues consulta, despues pedido.
- Leer `settings` desde `src/services/` o `src/domain/`: los limites llegan como parametro.
- Importar `src.api` desde `src/services/` o `src/domain/`; importar SQLAlchemy o FastAPI desde `src/domain/`.
- `OFFSET` en cualquier listado.
- `= Depends(...)`, `float` para dinero o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Trabajo a realizar

### 1. Modelo y migracion

En `Consulta`:

| Columna | Tipo | Regla |
|---|---|---|
| `presupuesto` | `Numeric(12, 2)`, nulo | Check `presupuesto_positivo`: nulo o mayor que 0 |
| `fecha_deseada` | `Date`, nulo | |
| `ultimo_mensaje_at` | `DateTime(timezone=True)`, no nulo | `default` y `server_default` igual que `created_at`. Ordena la bandeja |
| `leido_cliente_hasta` | `DateTime(timezone=True)`, nulo | Hasta donde leyo el cliente |
| `leido_artista_hasta` | `DateTime(timezone=True)`, nulo | Hasta donde leyo el artista |

Mas el check `una_referencia`: `num_nonnulls(servicio_id, obra_id) <= 1`.

En `Mensaje`: `aviso_contacto` booleano, no nulo, `default=False` y `server_default` falso.

Indices, todos en orden ascendente (Postgres los recorre al reves para el orden descendente, y `alembic check` no compara bien los `DESC`):

- `mensajes`: sale `ix_mensajes_consulta_id` y entra `ix_mensajes_consulta_id_created_at` sobre `(consulta_id, created_at, id)`.
- `consultas`: salen `ix_consultas_cliente_id` e `ix_consultas_artista_id`, y entran `ix_consultas_cliente_id_ultimo_mensaje_at` sobre `(cliente_id, ultimo_mensaje_at, id)` e `ix_consultas_artista_id_ultimo_mensaje_at` sobre `(artista_id, ultimo_mensaje_at, id)`.

La migracion `c2d3e4f5a6b7`, con `down_revision = "b1c2d3e4f5a6"`, agrega las columnas, llena `ultimo_mensaje_at` de las filas existentes con su `created_at`, y es reversible: el `downgrade` deja el esquema exactamente como estaba, con los indices viejos. `alembic check` limpio.

### 2. Dominio puro: `src/domain/consultas.py`

```python
AVISO_PAGO_FUERA = "Si pagás fuera de ArtísTica, no tenés protección ni reseña"
VENTANA_LIMITE = timedelta(hours=24)

def requiere_aviso(texto: str) -> bool
    # contiene_contacto_prohibido(texto), o "sinpe" sin distinguir mayusculas

@dataclass(frozen=True)
class LimitesConsultas:
    dias_cuenta_reciente: int
    consultas_por_ventana: int
    # __post_init__: los dos tienen que ser al menos 1, si no ValueError
    @classmethod
    def desde_config(cls, config: Settings) -> LimitesConsultas
    def es_reciente(self, perfil_creado: datetime, ahora: datetime) -> bool
        # ahora - perfil_creado < dias_cuenta_reciente dias. Exactamente 7 dias ya no es reciente
    def cabe_otra(self, abiertas_en_ventana: int) -> bool

def marca_siguiente(ultimo: datetime | None, ahora: datetime) -> datetime
    # max(ahora, ultimo + 1 microsegundo). La marca de un mensaje nunca retrocede

def rol_en_consulta(cliente_id, artista_id, usuario_id) -> RolEnConsulta | None
    # RolEnConsulta es un StrEnum de este modulo: CLIENTE, ARTISTA. None si no participa
```

### 3. Configuracion y excepcion

- `src/core/config.py`: `DIAS_CUENTA_RECIENTE: int = Field(default=7, ge=1)` y `CONSULTAS_POR_DIA_CUENTA_RECIENTE: int = Field(default=5, ge=1)`, con un comentario corto.
- `src/core/exceptions.py`: `class LimiteExcedido(ReglaDeNegocioViolada)`.
- `src/main.py`: `LimiteExcedido` responde 429 con el mismo formato `{"detail": ...}` que los demas. Registralo junto a los otros: Starlette elige el manejador por la clase mas especifica, como ya pasa con `ActorNoAutorizado`.

### 4. Paginacion

`traer_pagina` suma un parametro solo por nombre, `columna: InstrumentedAttribute[datetime] | None = None`. Si es `None`, todo sigue igual que hoy, sobre `created_at`. Si viene, el keyset, el orden y el cursor usan esa columna en lugar de `created_at`, con `id` de desempate. Ninguna llamada existente cambia.

### 5. Servicio: `src/services/consultas.py`

Hace `flush`, nunca `commit`. Recibe `ahora: datetime` y los limites como parametros; no lee el reloj ni `settings`. La consulta no visible para quien pide (no participa) da `ResourceNotFound("Consulta no encontrada")`, para no revelar que existe.

**`abrir(session, cliente, *, artista_id, servicio_id, obra_id, texto, presupuesto, fecha_deseada, ahora, limites) -> tuple[ConsultaDetalle, bool]`**. El booleano dice si se creo.

1. `bloquear_perfil(session, cliente.id)`, **antes que nada**. Serializa las consultas del mismo cliente, asi el limite no se pasa con dos solicitudes simultaneas.
2. El artista existe y tiene rol `artista`; si no, 404 `"Artista no encontrado"`. Si es el propio cliente, `ReglaDeNegocioViolada` (409).
3. Si hay `servicio_id`: del artista y sin borrar, si no 404; inactivo, 409. Si hay `obra_id`: del artista y sin borrar, si no 404; `vendida`, 409. Se leen sin bloquear.
4. Si existe una consulta del cliente con ese artista, `servicio_id` y `obra_id` iguales (`IS NOT DISTINCT FROM`) y estado `abierta` o `cotizada`: se le agrega el mensaje como en `enviar` y se devuelve con `False`. No cuenta para el limite y no cambia su presupuesto ni su fecha.
5. Si `limites.es_reciente(cliente.created_at, ahora)`: se cuentan las consultas del cliente con `created_at > ahora - VENTANA_LIMITE`, y si no `cabe_otra`, `LimiteExcedido` con un texto que diga el limite y la ventana.
6. Crea la consulta (`created_at` y `ultimo_mensaje_at` igual a `ahora`) y su primer mensaje con la misma marca y `aviso_contacto = requiere_aviso(texto)`. Devuelve con `True`.

**`enviar(session, usuario, consulta_id, texto, ahora) -> MensajeDetalle`**

1. Bloquea la fila de la consulta (`FOR UPDATE`, `populate_existing`). Es el unico bloqueo: no toca el perfil despues.
2. Si `usuario` no participa, 404. Si la consulta esta `descartada`, `ReglaDeNegocioViolada` (409). En `abierta`, `cotizada` y `convertida` se puede escribir.
3. `marca = marca_siguiente(consulta.ultimo_mensaje_at, ahora)`. El mensaje se crea con `created_at = marca` y la consulta queda con `ultimo_mensaje_at = marca`.

Por que el bloqueo y la marca: la app pide "los mensajes despues de mi ultimo cursor". Si dos mensajes de la misma consulta pudieran confirmarse en un orden distinto al de sus marcas, uno quedaria detras de un cursor ya entregado y la app no lo veria nunca. Con el bloqueo, el orden de confirmacion es el orden de las marcas.

**`listar_mensajes(session, usuario, consulta_id, parametros)`**: del mas nuevo al mas viejo, para el historial. `traer_pagina` descendente.

**`mensajes_nuevos(session, usuario, consulta_id, parametros)`**: del mas viejo al mas nuevo, los posteriores al cursor. `traer_pagina` ascendente. Sin cursor, desde el primero.

**`marcar_leido(session, usuario, consulta_id)`**: un solo `UPDATE` que pone la columna de quien lee (`leido_cliente_hasta` o `leido_artista_hasta`) igual a `ultimo_mensaje_at` de la misma fila. Sin `SELECT ... FOR UPDATE` previo.

**`descartar(session, usuario, consulta_id) -> ConsultaDetalle`**: bloquea la consulta, cualquiera de los dos participantes, solo desde `abierta`. Desde `cotizada` o `convertida`, 409: una cotizada se cierra rechazando la cotizacion, en el lote 8.

**`detalle(session, usuario, consulta_id)`** y **`bandeja(session, usuario, como, estado, parametros)`**: `como` es `RolEnConsulta | None` (sin valor, las dos) y `estado` es `EstadoConsulta | None`. La bandeja va por `ultimo_mensaje_at` descendente con `traer_pagina(..., columna=Consulta.ultimo_mensaje_at)`. Cada `ConsultaDetalle` lleva la consulta, el cliente y el artista (`Profile`), el rol de quien mira, el ultimo mensaje y `no_leidos`. **Sin N+1**: perfiles, ultimos mensajes (`DISTINCT ON (consulta_id)`) y no leidos de toda la pagina con un numero fijo de consultas SQL.

`no_leidos` son los mensajes **de la otra parte** con `created_at` mayor que la marca de lectura de quien mira (nula: todos). Los mensajes propios nunca cuentan.

**`resumen_no_leidos(session, usuario) -> tuple[int, int]`**: cuantas consultas tienen algo sin leer y cuantos mensajes sin leer hay en total, en una consulta SQL. Es lo que la app pide para el globito de la bandeja.

`MensajeDetalle` lleva el `Mensaje` y si es de quien mira. El cursor de cada mensaje sale de `codificar_cursor(mensaje.created_at, mensaje.id)`.

### 6. Esquemas: `src/schemas/consultas.py`

- `NuevaConsulta` (`extra="forbid"`): `artista_id`, `servicio_id` y `obra_id` opcionales (los dos a la vez, 422), `texto`, `presupuesto: Monto | None`, `fecha_deseada: date | None`.
- `NuevoMensaje` (`extra="forbid"`): `texto`.
- El texto en los dos: sin espacios a los lados, de 1 a 2000 caracteres, **sin** el validador de contacto.
- `MensajeRespuesta`: `id`, `cursor`, `es_mio`, `texto`, `created_at`, `aviso_contacto` y `aviso: str | None` (el texto de `AVISO_PAGO_FUERA` si `aviso_contacto`, si no nulo).
- `ConsultaRespuesta`: `id`, `estado`, `soy` (`cliente` o `artista`), `cliente` y `artista` (`PerfilResumido`), `servicio_id`, `obra_id`, `presupuesto`, `fecha_deseada`, `created_at`, `ultimo_mensaje_at`, `ultimo_mensaje: MensajeRespuesta | None` y `no_leidos`.
- `ResumenNoLeidos`: `consultas` y `mensajes`.

### 7. Endpoints: `src/api/v1/consultas.py`

Todos piden token, con `Usuario`; cualquier rol puede ser cliente. La API pasa `ahora=datetime.now(UTC)` y `LimitesConsultas.desde_config(settings)`, y hace el `commit`.

| Metodo y ruta | Respuesta |
|---|---|
| `POST /consultas` | `ConsultaRespuesta`. 201 si se creo, 200 si se agrego a una existente |
| `GET /consultas` | `Pagina[ConsultaRespuesta]`, la bandeja. Query `como` y `estado` opcionales |
| `GET /consultas/no-leidos` | `ResumenNoLeidos`. Declarada antes que `/consultas/{consulta_id}` |
| `GET /consultas/{consulta_id}` | `ConsultaRespuesta` |
| `POST /consultas/{consulta_id}/descartar` | `ConsultaRespuesta` |
| `PUT /consultas/{consulta_id}/leido` | 204 |
| `GET /consultas/{consulta_id}/mensajes` | `Pagina[MensajeRespuesta]`, historial descendente |
| `GET /consultas/{consulta_id}/mensajes/nuevos` | `Pagina[MensajeRespuesta]`, ascendente desde `cursor`. Es lo que la app pide cada pocos segundos |
| `POST /consultas/{consulta_id}/mensajes` | `MensajeRespuesta`, 201 |

Registrá el router en `src/api/v1/router.py`.

### 8. Variables

`DIAS_CUENTA_RECIENTE` y `CONSULTAS_POR_DIA_CUENTA_RECIENTE` en `backend/.env.example`, comentadas con su valor por defecto como las demas, y en una tabla de `backend/AGENTS.md`.

## Pruebas obligatorias

En `tests/test_dominio_consultas.py`, con prefijo `test_7_01_` a `test_7_04_`:

1. `requiere_aviso`: verdadero con "pasame al 8888-8888", "+506 7000 0000", "te hago un SINPE", "sinpe movil" y "escribime al WhatsApp"; falso con "lo entrego en 2026", "mi presupuesto es 50000" y "hola".
2. `LimitesConsultas`: `ValueError` con 0; `es_reciente` verdadero a 6 dias y 23 horas, falso a 7 dias exactos; `cabe_otra(4)` verdadero y `cabe_otra(5)` falso con limite 5.
3. `marca_siguiente`: con `ultimo` nulo devuelve `ahora`; con `ultimo` igual o posterior a `ahora`, devuelve `ultimo` mas un microsegundo.
4. `Settings` con `DIAS_CUENTA_RECIENTE=0` o `CONSULTAS_POR_DIA_CUENTA_RECIENTE=0` no carga.

En `tests/test_consultas_api.py`, con prefijo `test_7_05_` en adelante:

5. Abrir sobre un servicio: 201, estado `abierta`, primer mensaje con `es_mio` verdadero, presupuesto y fecha guardados. El artista la ve en su bandeja con `soy` `artista` y `no_leidos` 1.
6. Validaciones al abrir: artista inexistente o de rol publico, 404; a si mismo, 409; servicio ajeno, 404; servicio inactivo, 409; obra vendida, 409; servicio y obra a la vez, 422; presupuesto 0, 422; texto vacio, 422; sin token, 401.
7. Consulta repetida: con la primera `abierta`, la segunda da 200 con el mismo `id` y dos mensajes. Con la primera `descartada`, da 201 y otro `id`.
8. Limite: una cuenta de 2 dias abre 5 consultas con artistas distintos y la sexta da 429. Una cuenta de 8 dias abre 6 sin problema. Para una cuenta de 2 dias, 5 consultas creadas hace 25 horas (insertadas con su `created_at`) no cuentan. La consulta repetida del punto 7 no cuenta para el limite.
9. Aviso suave: un mensaje con "SINPE" da 201, con el texto intacto, `aviso_contacto` verdadero y `aviso` con el texto exacto de `AVISO_PAGO_FUERA`. La otra parte lo ve igual en el historial. Uno sin datos de contacto tiene `aviso` nulo.
10. Acceso: un tercero con token recibe 404 en cada endpoint con `{consulta_id}`. En una consulta `descartada`, enviar da 409. En una `convertida` (estado puesto en la base), enviar da 201.
11. Historial y nuevos: con 25 mensajes, el historial con `tamano=10` recorre las tres paginas del mas nuevo al mas viejo, sin repetidos ni faltantes. `mensajes/nuevos` con el `cursor` del decimo devuelve del 11 al 25 en orden ascendente; con el cursor del ultimo, `items` vacio y `siguiente_cursor` nulo.
12. Marcas: dos llamadas a `servicio.enviar` con el mismo `ahora` dejan marcas estrictamente crecientes, y `ultimo_mensaje_at` de la consulta igual a la del segundo.
13. No leidos: el cliente manda 3 mensajes. El artista ve `no_leidos` 3 y `GET /consultas/no-leidos` da `{"consultas": 1, "mensajes": 3}`. Despues de `PUT leido`, 0 y `{"consultas": 0, "mensajes": 0}`. Para el cliente, sus propios mensajes nunca cuentan.
14. Bandeja: tres consultas; un mensaje nuevo en la mas vieja la pone primera, con `ultimo_mensaje` correcto. Los filtros `como` y `estado` funcionan. Con `tamano=2` se recorre sin repetidos. La bandeja hace el mismo numero de sentencias SQL con 2 consultas que con 8.
15. Descartar: desde `abierta`, 200 y `descartada`; otra vez, 409; desde `cotizada` (estado puesto en la base), 409.
16. `app.openapi()["paths"]` incluye las siete rutas nuevas, y `GET /consultas/no-leidos` no la captura `/consultas/{consulta_id}`.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` y `alembic check` sin error ni diferencias.
- [ ] Los indices de `consultas` y `mensajes` en la base: `SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('consultas', 'mensajes') ORDER BY 1;`.
- [ ] `SELECT count(*) FROM pg_policies;` da 0, y `consultas` y `mensajes` siguen con `relrowsecurity` verdadero en `pg_class`.
- [ ] Desde `backend/`: `pytest -q` pasa, con las 346 anteriores mas las nuevas.
- [ ] Desde `backend/`: `grep -rn "from src.api" src/services src/domain` y `grep -rn "settings" src/services/consultas.py src/domain/consultas.py` salen vacios.
- [ ] Desde `backend/`: `grep -n "OFFSET\|offset(" src/services/consultas.py` sale vacio.
- [ ] Desde la raiz: `bash .github/scripts/reglas-del-repositorio.sh` pasa.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y `git diff --stat develop...HEAD -- backend/tests/` solo los dos archivos nuevos.

## Commit y entrega

Commiteá en `feat/lote-07-consultas-chat` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `feat(backend): esquema de consultas con no leidos y aviso de contacto`, `feat(backend): servicio de consultas y mensajes con limite para cuentas nuevas` y `feat(backend): endpoints de consultas y chat por consulta periodica`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá la salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`, la salida literal de cada criterio, y observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
