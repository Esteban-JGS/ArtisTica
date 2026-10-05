# [Lote 5d] Deuda: esquema y enums

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c refactor/lote-05d-deuda-esquema
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. El backend es FastAPI con SQLAlchemy 2.0 async sobre Postgres 15 (Supabase), con migraciones de Alembic **encadenadas**: la inicial no se toca.

Este lote no agrega funcionalidad: paga tres deudas tecnicas del esquema.

| # | Problema | Resultado esperado |
|---|---|---|
| DT6 | Los valores por defecto se asignan en Python (`default=`), no en la base. Un insert por SQL crudo (un seed, el panel de Supabase, un trabajo futuro) tiene que darlos todos, o falla o queda inconsistente | Toda columna con `default=` en el modelo tiene tambien su `server_default` en la base, con el mismo valor |
| DT7 | `reportes` y `moderation_actions` conservan nombres en ingles y sus columnas de persona no tienen llave foranea | Nombres en español y llaves foraneas hacia `profiles` |
| DT9 | El dominio (`src/domain/`) importa sus enums desde `src.models`, asi que importar el dominio carga SQLAlchemy entero. El dominio tiene que ser logica pura | Los enums viven en un modulo neutro del dominio; los modelos los importan de ahi |

Nadie usa todavia las tablas de moderacion fuera de los modelos, y ningun entorno tiene datos que haya que conservar en ellas.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno obligatorias y la base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) estan en `AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/models/base.py` | `IdMixin.id` con `default=uuid.uuid4`; `TimestampMixin` con `created_at` y `updated_at` en `default=lambda: datetime.now(UTC)`, y `onupdate` en `updated_at`. `pg_enum(cls, name)` arma el `ENUM` de Postgres con `create_type=False` |
| `src/models/users.py` | Enums `RolPerfil`, `PlanArtista`, `EstadoOnboarding`. Defaults en `categorias` (`list`), `rol`, `plan`, `is_verified`, `pasarela_onboarding` |
| `src/models/catalogo.py` | Enums `EstadoObra`, `TipoServicio`. Defaults en `obras.estado`, `obras.categorias`, `servicios.activo` |
| `src/models/consultas.py` | Enum `EstadoConsulta`. Default en `consultas.estado` |
| `src/models/medios.py` | Enum `EstadoMedia`. Default en `media_assets.estado`. `bucket` ya tiene `server_default` |
| `src/models/pedidos.py` | Enums `TipoPedido`, `EstadoPedido`, `TipoEntregable`, `EstadoDisputa`, `TipoCobro`, `EstadoCobro`. Defaults en `pedidos.estado`, `pedidos.moneda` (`"CRC"`), `cobros.estado`, `cobros.monto_reembolsado` (`Decimal("0")`) y `disputas.estado` |
| `src/models/operacion.py` | Enum `EstadoReporte`. `Job` con defaults en `status` (`"pending"`), `attempts` (0) y `max_attempts` (3). `Reporte` con `reporter_id`, `target_type`, `target_id`, `reason`, `estado`. `ModerationAction` (tabla `moderation_actions`) con `admin_id`, `target_type`, `target_id`, `action`, `nota`. Ninguna de las columnas de persona tiene llave foranea |
| `src/models/__init__.py` | Reexporta modelos y enums. Lo usan servicios, esquemas, endpoints y pruebas |
| `src/domain/pedidos.py:24-27` | Importa `EstadoObra`, `EstadoConsulta`, `EstadoCobro`, `EstadoPedido`, `TipoCobro`, `TipoPedido` y `PlanArtista` desde `src.models.*` |
| `src/domain/perfiles.py:10` | Importa `EstadoOnboarding`, `PlanArtista`, `RolPerfil` desde `src.models.users` |
| `alembic/env.py` | `context.configure(connection=..., target_metadata=...)` sin `compare_server_default` |
| `alembic/versions/` | `1a2b3c4d5e6f` (inicial) y `5b6c7d8e9f01` (medios), que es la cabeza |
| `src/workers/handlers/moderation.py` | Menciona `ModerationAction` en un comentario. No se toca: el lote 11 lo reescribe |

## Objetivo

Que el dominio importe sin cargar SQLAlchemy, que la base tenga los mismos valores por defecto que los modelos, y que las tablas de moderacion tengan nombres en español y llaves foraneas, todo con una sola migracion reversible.

## Trabajo a realizar

### 1. Enums en un modulo neutro (DT9)

- Creá `src/domain/enums.py` con **los catorce enums**, con los mismos nombres de clase y los mismos valores. Sin importar nada fuera de la biblioteca estandar.
- Cada modulo de `src/models/` importa sus enums desde `src.domain.enums` y los sigue exponiendo, de modo que `from src.models import PlanArtista` y `from src.models.users import PlanArtista` siguen funcionando y devuelven **la misma clase** que `src.domain.enums.PlanArtista`.
- `src/domain/pedidos.py` y `src/domain/perfiles.py` importan los enums desde `src.domain.enums`. Ningun archivo de `src/domain/` importa `src.models`.
- Los servicios, esquemas y endpoints no se tocan: siguen importando desde `src.models`, que reexporta.

### 2. Valores por defecto en la base (DT6)

En los modelos, cada columna con `default=` suma un `server_default` equivalente, y **conserva** el `default=` de Python para que un objeto nuevo tenga el valor antes del `flush`:

| Caso | `server_default` |
|---|---|
| `IdMixin.id` | `text("gen_random_uuid()")` |
| `created_at`, `updated_at` | `func.now()` |
| Enums | El valor como texto, por ejemplo `"exhibicion"` |
| Booleanos | `text("true")` o `text("false")` |
| Enteros y dinero | `"0"`, `"3"` |
| Arreglos vacios (`categorias`) | El literal de arreglo vacio que Postgres acepte para `varchar[]` |
| `moneda`, `jobs.status` | El texto |

`updated_at` sigue actualizandose solo desde Python con `onupdate`. **No** agregues triggers.

### 3. Moderacion en español con llaves foraneas (DT7)

| Antes | Despues |
|---|---|
| Tabla `moderation_actions`, clase `ModerationAction` | Tabla `acciones_moderacion`, clase `AccionModeracion` |
| `reportes.reporter_id` | `reportante_id` |
| `moderation_actions.admin_id` | `moderador_id` |
| `target_type`, `target_id` (en las dos) | `objetivo_tipo`, `objetivo_id` |
| `reportes.reason` | `motivo` |
| `moderation_actions.action` | `accion` |

- `reportante_id` y `moderador_id` pasan a llave foranea hacia `profiles.id` con `ondelete="SET NULL"`, y por eso pasan a **nulas**: el historial de moderacion sobrevive aunque se borre la cuenta.
- Indice en `reportante_id` y en `moderador_id`, como el resto de las llaves foraneas.
- La clave primaria de la tabla renombrada pasa a llamarse como dicta `NAMING_CONVENTION` (`pk_acciones_moderacion`).
- `objetivo_tipo` sigue siendo texto. Su enum lo decide el lote 11.
- `src/models/__init__.py` exporta `AccionModeracion` en lugar de `ModerationAction`.

### 4. Migracion

Una sola migracion nueva con `down_revision = "5b6c7d8e9f01"`, que:

- agrega los `server_default` de la seccion 2 a todas las columnas que correspondan, en todas las tablas;
- renombra la tabla, la clave primaria y las columnas de la seccion 3, cambia la nulidad y crea llaves foraneas e indices;
- tiene un `downgrade` que deja el esquema exactamente como en `5b6c7d8e9f01`.

Las listas de tablas y columnas van escritas en la migracion, no calculadas desde los modelos: una migracion no puede depender del codigo que cambia despues. El RLS de la tabla renombrada se conserva solo; verificalo.

### 5. Comparacion de defaults en Alembic

En `alembic/env.py`, activá `compare_server_default=True` en el `context.configure` en linea. Asi `alembic check` detecta si un modelo y la base dejan de coincidir en un default. Si produce diferencias falsas que no se arreglan escribiendo el `server_default` igual a como lo devuelve Postgres, dejalo apagado y explicalo en observaciones: la prueba 3 cubre el mismo riesgo.

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `src/domain/enums.py` (nuevo)
- `src/domain/pedidos.py` (solo imports)
- `src/domain/perfiles.py` (solo imports)
- `src/models/base.py`
- `src/models/users.py`
- `src/models/catalogo.py`
- `src/models/consultas.py`
- `src/models/medios.py`
- `src/models/pedidos.py`
- `src/models/operacion.py`
- `src/models/__init__.py`
- `alembic/env.py`
- `alembic/versions/<nueva>_esquema_defectos_y_moderacion.py` (nuevo)
- `tests/test_esquema.py` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior: servicios, esquemas, endpoints, pagos, almacenamiento, worker y la migracion inicial y la de medios.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias.
- Cambiar el nombre o los valores de un enum, o el nombre de cualquier otra tabla o columna.
- Quitar un `default=` de Python.
- Agregar triggers o funciones en la base.
- Desactivar el RLS de cualquier tabla.

## Pruebas obligatorias

En `tests/test_esquema.py`, con prefijo `test_01_` a `test_07_`. Las que tocan la base usan la sesion con rollback de `conftest.py`.

1. **Dominio puro.** En un subproceso (`subprocess.run([sys.executable, "-c", ...])`), importar `src.domain.pedidos`, `src.domain.perfiles`, `src.domain.medios`, `src.domain.politicas` y `src.domain.enums`, y verificar que ningun modulo de `sys.modules` empiece con `sqlalchemy`. Tiene que ser un subproceso porque en el proceso de pytest SQLAlchemy ya esta cargado.
2. **Misma clase.** `src.models.PlanArtista is src.domain.enums.PlanArtista`, y lo mismo para `EstadoPedido` y `EstadoReporte`.
3. **Modelo coherente.** Recorrer `Base.metadata`: toda columna con `default` no nulo tiene `server_default`. Y contra la base: para cada una de esas columnas, `information_schema.columns.column_default` no es nulo.
4. **Insert crudo en `profiles`.** `INSERT` con solo `id`, `handle` y `nombre`. Al leerla: `rol = 'publico'`, `plan = 'taller'`, `is_verified` falso, `pasarela_onboarding = 'no_iniciado'`, `categorias` vacio, `created_at` no nulo.
5. **Insert crudo en `jobs`.** Solo `type`, `payload` y `run_after`. Al leerla: `id` generado, `status = 'pending'`, `attempts = 0`, `max_attempts = 3`.
6. **Moderacion.** No existe la tabla `moderation_actions` y si `acciones_moderacion`. Ninguna de las dos tablas tiene columnas `reporter_id`, `admin_id`, `target_type`, `target_id`, `reason` ni `action`. Existen las llaves foraneas de `reportante_id` y `moderador_id` hacia `profiles`, con `ON DELETE SET NULL`.
7. **RLS.** `pg_class.relrowsecurity` es verdadero en `reportes` y en `acciones_moderacion`, y no hay ninguna politica en `pg_policies` para ellas.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] La migracion es reversible: `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head` corren sin error.
- [ ] Despues del `downgrade -1`, `\d moderation_actions` existe con sus columnas originales (pegá la salida de `psql` o de una consulta a `information_schema.columns`).
- [ ] `alembic heads` muestra una sola cabeza, y `alembic check` dice `No new upgrade operations detected.`, con `compare_server_default` activo o con la explicacion de por que no.
- [ ] `pytest -v` pasa, muestra las siete pruebas obligatorias, y las 263 anteriores siguen pasando.
- [ ] `grep -rn "class .*StrEnum" src/models` no devuelve nada.
- [ ] `grep -rn "src.models" src/domain` no devuelve nada.
- [ ] `grep -rn "ModerationAction\|moderation_actions\|reporter_id" src tests --include=*.py` solo devuelve la migracion inicial y el comentario de `src/workers/handlers/moderation.py`.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `refactor/lote-05d-deuda-esquema` **solo los archivos del alcance**, con mensajes convencionales. Sugerencia de tres commits: `refactor(backend): enums del dominio en un modulo neutro`, `fix(backend): valores por defecto tambien en la base` y `refactor(backend): moderacion en espanol con llaves foraneas`. Si la migracion unica obliga a juntar los dos ultimos, juntalos. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. La tabla de columnas a las que se agrego `server_default`, con el valor de cada una.
5. Una tabla con DT6, DT7 y DT9 y la evidencia de que quedaron pagadas.
6. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
