# [Lote 1b] Cerrar los huecos del esquema antes de que se cierre la ventana

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Un solo motor de pedidos con tres tipos: `encargo`, `evento` y `obra_disponible`, con cobros por hitos que ejecuta una pasarela externa. ArtísTica nunca custodia fondos.

El lote anterior reemplazo el esquema completo: 19 tablas y 12 tipos enum en una sola migracion inicial. Quedo bien, pero el diseno tenia cuatro huecos que su ejecutor detecto y, correctamente, no lleno por su cuenta.

**Por que ahora y no despues.** La base todavia no se migro en ningun ambiente con datos, asi que la migracion inicial se puede seguir reescribiendo en su lugar. En cuanto exista un ambiente con datos, cada uno de estos cambios cuesta una migracion con `ALTER` sobre tablas vivas. Esta es la ultima vez que sale barato.

## Estado actual del repositorio

- `backend/src/models/`: `base.py` (con `Base`, `IdMixin`, `TimestampMixin`, `SoftDeleteMixin`, el helper `pg_enum` y una convencion de nombres para restricciones), `users.py`, `catalogo.py`, `social.py`, `medios.py`, `consultas.py`, `pedidos.py`, `finanzas.py`, `metricas.py`, `operacion.py`, y `operation.py`, que es una reexportacion de tres lineas hacia `operacion.py` porque `workers/main.py` importa `Job` desde ahi.
- `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py`: crea extensiones, los 12 enums desde un diccionario `ENUMS`, las 19 tablas, un indice HNSW sobre `obras.style_embedding` con `vector_l2_ops`, un GIN sobre `publicaciones.search_vector`, y activa RLS sin politicas en todas las tablas y en `alembic_version`.
- `backend/alembic/` **no tiene `script.py.mako`**, asi que `alembic revision` no puede generar archivos.
- `backend/src/api/v1/router.py` no expone rutas. Es lo esperado.

## Objetivo

Cerrar los cuatro huecos de dominio y los indices faltantes, reescribiendo la misma migracion inicial.

## Lo que falta y hay que agregar

### 1. Entregables del pedido

El flujo del encargo entrega una vista previa con marca de agua, y despues el archivo final. Hoy no hay ningun vinculo entre `media_assets` y `pedidos`, asi que el estado `vista_previa_entregada` no tiene donde apoyarse.

Tabla **`entregables`** en `src/models/pedidos.py`:

`pedido_id` indexado, `media_asset_id`, `tipo` del nuevo enum `tipo_entregable` con valores `vista_previa` y `final`, `nota` String nullable.

Enum nuevo: `tipo_entregable` con `vista_previa`, `final`.

### 2. Disputas

Existe el estado `en_disputa`, pero no hay donde guardar quien la abrio, por que, ni como se resolvio. El equipo de moderacion la resuelve con base en el chat, la propuesta y las vistas previas.

Tabla **`disputas`** en `src/models/pedidos.py`:

`pedido_id` **unico**, `abierta_por_id` a `profiles.id`, `motivo` String, `estado` del nuevo enum `estado_disputa` con valores `abierta`, `en_revision`, `resuelta`, `resolucion` String nullable, `resuelta_por_id` nullable a `profiles.id`, `resuelta_en` nullable con zona horaria.

Enum nuevo: `estado_disputa` con `abierta`, `en_revision`, `resuelta`.

### 3. Obra vendida

Nada impide hoy que dos pedidos se abran sobre la misma obra disponible, y el enum `estado_obra` no tiene como expresar que ya se vendio.

Agregar el valor **`vendida`** al enum `estado_obra`, que queda con `exhibicion`, `disponible`, `vendida`.

Ajustar el CHECK de `obras` para que el precio siga siendo obligatorio y positivo tanto en `disponible` como en `vendida`, porque una obra vendida conserva su precio.

**No** agregues logica que haga la transicion. Eso va en el lote de pedidos.

### 4. Indices que faltan en llaves foraneas y en el feed

Agregar:

- `pedidos.cliente_id`
- `follows.seguido_id`
- `obras.artista_id`
- `servicios.artista_id`
- `comentarios.publicacion_id`
- Compuesto sobre `publicaciones` por `artista_id` y `created_at` descendente, que es el acceso del feed cronologico.

### 5. La busqueda de texto se mantiene sola

`publicaciones.search_vector` no lo llena nada hoy. Convertilo en **columna generada** a partir de `to_tsvector('spanish', texto)`, de modo que PostgreSQL la mantenga y ningun codigo tenga que acordarse. El indice GIN se queda como esta.

En el modelo, la columna se declara de solo lectura para SQLAlchemy.

### 6. Clase de operador del indice HNSW

El indice usa `vector_l2_ops`, heredado del esquema viejo. La similitud de estilo se compara por coseno. Cambialo a **`vector_cosine_ops`**.

### 7. La plantilla de alembic

Agregar `backend/alembic/script.py.mako`, la plantilla estandar de alembic. Sin ella `alembic revision` no genera archivos, y ese es el comando con el que se verifica que los modelos y la migracion coinciden.

## Alcance

Podes crear o modificar:

- `backend/src/models/catalogo.py`
- `backend/src/models/pedidos.py`
- `backend/src/models/social.py`
- `backend/src/models/__init__.py`
- `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py`
- `backend/alembic/script.py.mako` (crear)

## Prohibido

- Tocar cualquier archivo fuera de esa lista. En especial `mobile/`, `backend/src/core/**`, `backend/src/workers/**` y `backend/pyproject.toml`.
- Crear una migracion nueva. Se reescribe la existente conservando su `revision` y su `down_revision`.
- Implementar endpoints, servicios o maquinas de estado. Sigue siendo solo modelo de datos.
- Cualquier columna de saldo, disponible, retenido o acumulado en `ledger_entries`.
- Anotar dinero como `float`. Es `Numeric(12, 2)` sobre `Decimal`.
- Agregar politicas de RLS. Las tablas nuevas tambien quedan con RLS activo y sin politicas.
- Agregar tablas que no esten en este prompt, en especial la de impulsos.
- Agregar librerias nuevas.

## Trabajo a realizar

1. Agregar los enums `tipo_entregable` y `estado_disputa` al diccionario `ENUMS` de la migracion, y el valor `vendida` a `estado_obra`.
2. Crear los modelos `Entregable` y `Disputa`, y sumarlos a `__init__.py` y a la lista `TABLES` de la migracion, para que hereden el `ENABLE ROW LEVEL SECURITY`.
3. Ajustar el CHECK de `obras` y el enum de estado.
4. Agregar los seis indices.
5. Convertir `search_vector` en columna generada y ajustar el modelo.
6. Cambiar la clase de operador del indice HNSW.
7. Agregar `script.py.mako`.
8. Verificar que modelos y migracion siguen coincidiendo.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `python -c "import src.models; import src.main; import src.workers.main"` no lanza excepcion.
- [ ] `pytest` pasa.
- [ ] `alembic upgrade head` corre limpio sobre una base vacia.
- [ ] `alembic revision --autogenerate -m "verificacion"` genera un archivo con `upgrade` y `downgrade` vacios. Pegá el cuerpo y despues borralo.
- [ ] `alembic downgrade base` corre limpio y no deja tipos enum huerfanos, demostrado con una consulta al catalogo.
- [ ] Las 21 tablas quedan con RLS activo, y `pg_policies` del esquema publico devuelve cero filas.
- [ ] Una consulta a `information_schema.columns` con el patron `saldo|balance|disponible|retenido|acumulado` devuelve cero filas. **No uses grep sobre el codigo para esto**: los valores de enum del dominio contienen esas palabras de forma legitima.
- [ ] `grep -rn "Mapped\[float\]" backend/src/models/` no devuelve nada.
- [ ] `search_vector` es columna generada: demostralo insertando una publicacion y consultando su `search_vector` sin haberlo escrito.
- [ ] El indice de `obras.style_embedding` usa `vector_cosine_ops`, demostrado con una consulta a `pg_indexes`.
- [ ] Sigue habiendo un solo archivo en `backend/alembic/versions/`.
- [ ] `git status --short` no muestra ningun archivo bajo `mobile/`.

## Como entregar

Diff completo, lista de archivos tocados, salida literal de cada criterio en orden, y observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
