# [Lote 1] Esquema de dominio y migracion unica de reemplazo

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. El modelo es de **comisiones abiertas, no marketplace**: el artista muestra lo que hace y declara que acepta trabajos, en vez de subir productos a una tienda.

Hay un solo motor de pedidos con tres tipos, que comparten consulta, cotizacion, cobros por hitos, disputa y resena:

| Tipo | Cobros |
|---|---|
| `encargo` | Anticipo al aceptar la cotizacion; saldo autorizado en la vista previa con marca de agua y capturado al aprobar |
| `evento` | Anticipo al reservar la fecha; saldo antes del evento |
| `obra_disponible` | Autorizado al confirmar, capturado al despachar con numero de guia |

Una pasarela externa custodia el dinero. **ArtísTica nunca administra fondos de terceros.** No existe saldo propio, retencion propia ni desembolsos desde fondos nuestros.

El backend actual se construyo con un modelo anterior (marketplace con retencion propia) y hay que reemplazar su esquema completo. Tu lote define el modelo de datos nuevo. Nada mas: ni endpoints, ni servicios, ni logica de negocio.

## Estado actual del repositorio

El lote anterior dejo el proyecto ejecutable. Hoy existe:

- `backend/src/models/`: `base.py` (Base y TimestampMixin), `users.py` (`Profile`, `Follow`), `content.py` (`Post`, `MediaAsset`, `Comment`, `Reaction`), `commissions.py` (`Commission`, `CommissionMessage`, `CommissionDeliverable`), `finance.py` (`LedgerEntry` con debito y credito, `Payment`, `Payout`), `operation.py` (`Job`, `Report`, `ModerationAction`).
- `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py`: crea 15 tablas, dos tipos enum, extensiones `uuid-ossp`, `vector` y `pg_trgm`, un indice HNSW, uno GIN, y activa RLS sin politicas en todas las tablas.
- `backend/src/schemas/`: `profiles.py`, `posts.py`, `media.py`, `commissions.py`.
- `backend/src/api/v1/`: `router.py`, `profiles.py`, `posts.py`, `media.py`, `commissions.py`. **Los ocho endpoints son esqueletos**: docstring, un comentario `TODO` y nada mas.
- `backend/src/api/deps.py`: `get_db`, `get_current_user`, `get_current_admin`. Importa `ProfileRole` de `models.users`.
- `backend/src/workers/handlers/escrow.py`: handler `release_escrow`, registrado en `dispatcher.py`.
- `backend/src/workers/main.py`: el loop de la cola. Funciona y no se toca.

Lo que esta mal y hay que eliminar:

1. `Commission` modela un pedido de un solo pago con estados de retencion propia (`pagada_en_retencion`, `liberada`). No existe ese modelo.
2. `LedgerEntry` con `type` de debito y credito, mas `Payout`, implican un saldo propio y desembolsos desde fondos nuestros.
3. `handlers/escrow.py` libera una retencion que no existe.
4. No hay rol de usuario consumidor: `ProfileRole` solo tiene `artista` y `admin`.
5. No hay planes de artista, ni cuenta conectada de pasarela.
6. No existen `obras`, `servicios`, `consultas`, `pedidos` con tipo, `cobros` por hitos ni `resenas`.
7. En los modelos viejos el dinero se anota `Mapped[float]` sobre `Numeric`. Es incorrecto: SQLAlchemy devuelve `Decimal`.

**Dato decisivo: la base nunca se migro en ningun ambiente con datos.** Por eso este lote **reescribe la migracion inicial en su lugar**, en vez de encadenar `ALTER`. Es la ultima vez que se puede hacer.

## Objetivo

Reemplazar el esquema completo por el del modelo vigente, en una sola migracion inicial reescrita, con los modelos SQLAlchemy que le corresponden.

## Decisiones de diseno ya tomadas

No las cambies. Si alguna te parece equivocada, aplicala igual y anotala en observaciones.

### D1. La consulta es una entidad, no un estado del pedido

Un cliente abre una `consulta` sobre un servicio o una obra. Si prospera, nace un `pedido` que la referencia. La mayoria de las consultas nunca se convierten, y tienen que seguir siendo filas contables porque la conversion de consulta a pedido es una metrica del producto.

Para `obra_disponible` no hay negociacion: el flujo crea igual una consulta, ya en estado `convertida`, para que exista un solo mecanismo de chat y un hilo donde coordinar la entrega.

La maquina de estados del pedido arranca en `cotizado`. **No existe un estado `consulta` dentro del pedido.**

### D2. La tarifa se congela en el pedido

`pedidos` guarda el porcentaje de tarifa vigente al crearse. Si el artista cambia de plan despues, los pedidos viejos no se reescriben.

### D3. La pasarela es intercambiable

Ninguna columna se llama como un proveedor concreto. Se usa `pasarela` y `referencia_pasarela`. Todavia no esta decidido cual se usa en produccion.

### D4. Los impulsos quedan fuera

Los boosts se recortaron del alcance de la primera entrega. **No crees la tabla.** Una tabla sin codigo que la use es peso muerto.

## Esquema a construir

Todas las tablas: llave primaria `id` UUID con `uuid4` por defecto, mas `created_at` y `updated_at` con `DateTime(timezone=True)`.

Reglas transversales:

- **Dinero**: `Numeric(12, 2)` anotado como `Mapped[Decimal]`. Nunca `float`.
- **Porcentajes**: `Numeric(5, 2)`.
- **Fechas**: siempre `DateTime(timezone=True)`, en UTC.
- **Borrado suave**: `deleted_at` nullable en obras, publicaciones, comentarios, servicios y medios.
- Las llaves foraneas a `profiles.id` no llevan `ondelete=CASCADE` cuando el registro es historia contable (pedidos, cobros, asientos, resenas).

### Tipos enum de PostgreSQL

Los crea la migracion con SQL explicito. Los modelos los referencian con el `ENUM` del dialecto de PostgreSQL, `create_type=False` y `values_callable`, y las clases Python heredan de `enum.StrEnum`.

| Tipo | Valores |
|---|---|
| `rol_perfil` | `publico`, `artista`, `admin` |
| `plan_artista` | `taller`, `estudio` |
| `estado_onboarding` | `no_iniciado`, `pendiente`, `completado`, `rechazado` |
| `estado_obra` | `exhibicion`, `disponible` |
| `tipo_servicio` | `encargo`, `evento` |
| `estado_consulta` | `abierta`, `cotizada`, `convertida`, `descartada` |
| `tipo_pedido` | `encargo`, `evento`, `obra_disponible` |
| `estado_pedido` | `cotizado`, `anticipo_pagado`, `en_proceso`, `vista_previa_entregada`, `saldo_pagado`, `completado`, `rechazado`, `cancelado`, `en_disputa` |
| `tipo_cobro` | `anticipo`, `saldo`, `total` |
| `estado_cobro` | `pendiente`, `autorizado`, `capturado`, `cancelado`, `reembolsado`, `vencido` |
| `estado_media` | `pendiente`, `procesado`, `fallido` |
| `estado_reporte` | `pendiente`, `revisado`, `descartado` |

### Tablas

**`profiles`** (`src/models/users.py`). El `id` viene de `auth.users` de Supabase, sin valor por defecto.

`handle` unico e indexado, `nombre`, `bio` nullable, `categorias` ARRAY de String, `provincia` nullable, `rol` (`rol_perfil`, por defecto `publico`), `plan` (`plan_artista`, por defecto `taller`), `is_verified` booleano, `pasarela_cuenta_id` String nullable, `pasarela_onboarding` (`estado_onboarding`, por defecto `no_iniciado`).

**`follows`**: `seguidor_id`, `seguido_id`, ambos a `profiles.id`. **Restriccion unica** sobre el par y CHECK de que no sean iguales.

**`obras`** (`src/models/catalogo.py`): `artista_id`, `titulo`, `descripcion` nullable, `estado` (`estado_obra`, por defecto `exhibicion`), `precio` nullable, `categorias` ARRAY, `style_embedding` Vector(1536) nullable, `hash_imagen` String nullable indexado (para detectar la misma obra subida por cuentas distintas), `deleted_at`.

CHECK: si `estado` es `disponible`, `precio` no puede ser nulo y debe ser mayor que cero.

**`servicios`** (`src/models/catalogo.py`): `artista_id`, `titulo`, `descripcion` nullable, `precio_base`, `tipo` (`tipo_servicio`), `activo` booleano por defecto verdadero, `deleted_at`.

**`publicaciones`** (`src/models/social.py`): `artista_id`, `texto`, `obra_id` nullable (una publicacion puede mostrar una obra), `search_vector` TSVECTOR, `deleted_at`.

**`comentarios`** (`src/models/social.py`): `publicacion_id`, `profile_id`, `texto`, `deleted_at`.

**`reacciones`** (`src/models/social.py`): `publicacion_id`, `profile_id`, `tipo` String. **Restriccion unica** sobre los tres.

**`media_assets`** (`src/models/medios.py`): `propietario_id` a `profiles.id`, `obra_id` nullable, `publicacion_id` nullable, `tipo` String, `storage_path`, `thumbnail_path` nullable, `estado` (`estado_media`, por defecto `pendiente`), `deleted_at`.

**`consultas`** (`src/models/consultas.py`): `cliente_id`, `artista_id`, `servicio_id` nullable, `obra_id` nullable, `estado` (`estado_consulta`, por defecto `abierta`). Indices por `cliente_id` y por `artista_id`.

CHECK: `cliente_id` distinto de `artista_id`.

**`mensajes`** (`src/models/consultas.py`): `consulta_id` indexado, `remitente_id`, `texto`. Es el unico mecanismo de chat del sistema.

**`pedidos`** (`src/models/pedidos.py`): `consulta_id` **unico y obligatorio**, `cliente_id`, `artista_id`, `tipo` (`tipo_pedido`), `estado` (`estado_pedido`, por defecto `cotizado`), `descripcion`, `monto_total`, `moneda` String de 3 por defecto `CRC`, `tarifa_porcentaje`, `obra_id` nullable, `fecha_evento` nullable, `lugar_evento` nullable, `guia_envio` nullable, `fecha_entrega_estimada` nullable.

CHECK: `monto_total` mayor que cero. Indice por `artista_id` y `estado`.

**`cobros`** (`src/models/pedidos.py`): `pedido_id` indexado, `tipo` (`tipo_cobro`), `estado` (`estado_cobro`, por defecto `pendiente`), `monto`, `pasarela` String, `referencia_pasarela` String nullable **con restriccion unica**, `autorizado_hasta` nullable, `capturado_en` nullable.

CHECK: `monto` mayor que cero.

**`resenas`** (`src/models/pedidos.py`): `pedido_id`, `autor_id`, `destinatario_id`, `calificacion` entero, `texto` nullable. **Restriccion unica** sobre `pedido_id` y `autor_id`.

CHECK: `calificacion` entre 1 y 5.

**`ledger_entries`** (`src/models/finanzas.py`). Registro de conciliacion, **no de saldo**. Cada fila es un hecho ocurrido en la pasarela, nunca se actualiza.

`pedido_id` nullable, `cobro_id` nullable, `profile_id`, `tipo_evento` String, `monto_bruto`, `tarifa_artistica`, `costo_procesamiento`, `monto_neto_artista`, `referencia_pasarela` nullable, `ocurrido_en` con zona horaria.

**Prohibido** que exista cualquier columna de saldo, disponible, retenido o acumulado.

**`eventos_pasarela`** (`src/models/finanzas.py`). Da la idempotencia de los webhooks, que se implementa en un lote posterior.

`proveedor` String, `evento_externo_id` String **con restriccion unica junto a `proveedor`**, `tipo` String, `payload` JSONB, `procesado_en` nullable, `error` nullable.

**`post_views`** (`src/models/metricas.py`): `publicacion_id`, `profile_id`, `dia` de tipo Date. **Restriccion unica** sobre los tres. Es lo que impide inflar las vistas: una por usuario, publicacion y dia.

**`jobs`, `reportes`, `moderation_actions`** (`src/models/operacion.py`). `Job` se conserva tal cual esta hoy, porque el worker depende de su forma. `Report` pasa a tabla `reportes` con `estado` del tipo `estado_reporte`. `ModerationAction` conserva su tabla `moderation_actions` y gana una columna `nota` nullable.

### Indices que la migracion debe crear con SQL explicito

- HNSW sobre `obras.style_embedding`.
- GIN sobre `publicaciones.search_vector`.

## Alcance

Podes crear o modificar:

- `backend/src/models/base.py`
- `backend/src/models/users.py`
- `backend/src/models/catalogo.py`
- `backend/src/models/social.py`
- `backend/src/models/medios.py`
- `backend/src/models/consultas.py`
- `backend/src/models/pedidos.py`
- `backend/src/models/finanzas.py`
- `backend/src/models/metricas.py`
- `backend/src/models/operacion.py`
- `backend/src/models/__init__.py`
- `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py`
- `backend/src/api/deps.py` (solo lo minimo para que siga importando)
- `backend/src/api/v1/router.py`
- `backend/src/workers/dispatcher.py` (solo quitar el handler de retencion)

Podes borrar:

- `backend/src/models/content.py`, `commissions.py`, `finance.py`, `operation.py`
- `backend/src/schemas/profiles.py`, `posts.py`, `media.py`, `commissions.py`
- `backend/src/api/v1/profiles.py`, `posts.py`, `media.py`, `commissions.py`
- `backend/src/workers/handlers/escrow.py`

Los endpoints y esquemas viejos se borran porque son esqueletos vacios que referencian un modelo que deja de existir. Se reescriben en lotes posteriores. Despues de tu lote, `router.py` no expone ninguna ruta, y eso es lo esperado.

## Prohibido

- Tocar cualquier archivo fuera de las listas anteriores. En especial `mobile/`, `backend/src/core/**`, `backend/src/workers/main.py` y `backend/pyproject.toml`.
- Crear una migracion nueva. Se reescribe la existente, conservando su `revision` y su `down_revision`.
- Implementar endpoints, servicios, validaciones de negocio o maquinas de estado. Este lote es solo el modelo de datos.
- Cualquier columna de saldo, monto disponible, retenido o acumulado.
- Anotar dinero como `float`.
- Crear tablas que no esten en la lista de arriba, en especial la de impulsos.
- Agregar politicas de RLS. Toda tabla queda con RLS activo y sin politicas.
- Agregar librerias nuevas.
- Nombrar columnas o tipos con el nombre de un proveedor de pagos concreto.

## Trabajo a realizar

1. Crear los modelos nuevos en los archivos indicados y borrar los viejos.
2. Ajustar `src/models/__init__.py` para que exporte todo lo nuevo.
3. Ajustar `src/api/deps.py` al enum de rol nuevo, sin agregar funcionalidad.
4. Dejar `router.py` sin rutas y sacar el handler de retencion de `dispatcher.py`.
5. Reescribir la migracion inicial completa: extensiones, los doce tipos enum, las tablas, restricciones unicas, CHECK, indices, los dos indices por SQL explicito, y `ENABLE ROW LEVEL SECURITY` en todas las tablas. El `downgrade` tiene que dejar la base como estaba, incluidos los `DROP TYPE`.
6. Verificar que los modelos y la migracion coinciden exactamente, con la comprobacion del criterio de aceptacion correspondiente.

## Criterios de aceptacion

Con la salida de cada comando pegada. Las tres variables de entorno que exige la configuracion estan documentadas en `backend/AGENTS.md`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `python -c "import src.models; import src.main; import src.workers.main"` no lanza excepcion.
- [ ] `pytest` pasa.
- [ ] `alembic upgrade head` corre limpio sobre una base vacia.
- [ ] **Los modelos coinciden con la migracion:** `alembic revision --autogenerate -m "verificacion"` genera un archivo cuyo `upgrade` y `downgrade` quedan vacios. Pega el cuerpo del archivo generado y despues borralo. Si detecta diferencias, corregilas antes de entregar.
- [ ] `alembic downgrade base` corre limpio y no deja tipos enum huerfanos. Demostralo con una consulta al catalogo de PostgreSQL.
- [ ] Todas las tablas quedan con RLS activo y sin politicas. Demostralo con una consulta que liste `relname` y `relrowsecurity` de `pg_class`, y otra que cuente filas en `pg_policies` para el esquema publico, que debe dar cero.
- [ ] No existe ninguna columna de saldo: `grep -rniE "saldo|balance|disponible|retenido|acumulado" backend/src/models/` no devuelve nada.
- [ ] Ninguna anotacion de dinero es `float`: `grep -rn "Mapped\[float\]" backend/src/models/` no devuelve nada.
- [ ] Sigue habiendo un solo archivo en `backend/alembic/versions/`.
- [ ] `git status --short` no muestra ningun archivo bajo `mobile/`.
- [ ] `docker compose up --build -d --wait` levanta los tres servicios sin reinicios.

## Como entregar

1. El diff completo.
2. La lista de archivos creados, modificados y borrados.
3. La salida literal de cada criterio, en orden.
4. Una tabla de las tablas creadas con su cantidad de columnas, para revision rapida.
5. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones. Si encontras una relacion del dominio que el esquema no cubre, decilo ahi en vez de agregarla por tu cuenta.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
