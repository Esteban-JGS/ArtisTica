# [Lote 2] Maquina de estados de pedidos y cobros

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-02-maquina-estados
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Un cliente abre una `consulta` con un artista; si prospera, nace un `pedido`. Hay tres tipos de pedido, con cobros por hitos:

| Tipo | Cobros |
|---|---|
| `encargo` | Anticipo al aceptar la cotizacion; saldo autorizado cuando el artista entrega la vista previa con marca de agua, y capturado cuando el cliente la aprueba |
| `evento` | Anticipo al reservar la fecha; saldo antes del evento |
| `obra_disponible` | Un solo cobro total, autorizado cuando el cliente confirma y capturado cuando el artista despacha con numero de guia |

Una pasarela externa ejecuta los cobros y custodia el dinero. **ArtísTica nunca administra fondos de terceros.** La integracion con la pasarela se construye en el lote siguiente, no en este.

Tu lote construye el corazon del negocio: **las reglas de que puede pasarle a un pedido y a sus cobros, y la garantia de que el pedido y el cobro cambian juntos o no cambian.**

## Estado actual del repositorio

- `backend/src/models/pedidos.py`: `Pedido`, `Cobro`, `Resena`, `Entregable`, `Disputa`, con sus enums `TipoPedido`, `EstadoPedido`, `TipoCobro`, `EstadoCobro`, `TipoEntregable`, `EstadoDisputa`. El dinero es `Numeric(12, 2)` sobre `Decimal`. `pedidos.consulta_id` es unico. `pedidos.tarifa_porcentaje` congela la tarifa al crearse.
- `backend/src/models/consultas.py`: `Consulta`, con `EstadoConsulta` (`abierta`, `cotizada`, `convertida`, `descartada`).
- `backend/src/models/catalogo.py`: `Obra`, con `EstadoObra` (`exhibicion`, `disponible`, `vendida`) y `precio`.
- `backend/src/models/users.py`: `Profile`, con `plan` (`taller`, `estudio`).
- `backend/src/models/base.py`: `Base`, mixins, el helper `pg_enum` y una convencion de nombres para restricciones.
- `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py`: la unica migracion. **Todavia no se aplico en ningun ambiente con datos, asi que se reescribe en su lugar.** No se crea una migracion nueva.
- `backend/src/core/config.py`: `Settings` con pydantic-settings. Exige `DATABASE_URL`, `ALEMBIC_DATABASE_URL` y `SUPABASE_URL`.
- `backend/src/core/exceptions.py`: `ArtisTicaException`, `ResourceNotFound`, `InvalidStateTransition`.
- `backend/tests/conftest.py`: fixtures `test_db`, `async_session` (que hace rollback al terminar) y `async_client`.
- **No existen** `backend/src/domain/` ni `backend/src/services/`.

## Objetivo

Que todas las transiciones de pedidos y cobros vivan en un solo lugar, validadas por tipo de pedido, con politicas configurables, y aplicadas de forma atomica sobre la base.

## Arquitectura del lote

Tres capas, en este orden de dependencia:

1. **`src/domain/politicas.py`**: las politicas del negocio como un `dataclass` inmutable, construible desde la configuracion.
2. **`src/domain/pedidos.py`**: logica **pura**. Sin base de datos, sin `async`, sin `Settings`. Recibe valores y devuelve valores o levanta excepciones. Todo lo que se pueda probar sin base de datos vive aca.
3. **`src/services/pedidos.py`**: funciones `async` que reciben una `AsyncSession`, cargan filas, le preguntan al dominio si una operacion es valida, y aplican los cambios.

**El servicio no llama a la pasarela.** Recibe como entrada los hechos que la pasarela ya confirmo (una referencia, una fecha de vencimiento de la autorizacion, un monto devuelto). El lote que integra la pasarela va a llamar primero a la pasarela y despues a este servicio.

**El servicio no hace commit.** Hace `flush`. La transaccion la abre y la cierra quien lo llama: el endpoint o el job. Asi, el cambio del pedido y el del cobro caen siempre en la misma transaccion.

**El servicio bloquea la fila del pedido** con `SELECT ... FOR UPDATE` cada vez que lo va a cambiar, para que dos operaciones simultaneas sobre el mismo pedido se serialicen.

## Politicas (decision D5, ya tomada)

Todas configurables por variable de entorno, con estos valores por defecto:

| Politica | Valor por defecto | Variable |
|---|---|---|
| Anticipo minimo | 30% | `ANTICIPO_PORCENTAJE_MINIMO` |
| Anticipo maximo | 50% | `ANTICIPO_PORCENTAJE_MAXIMO` |
| Anticipo si el artista no elige | 50% | `ANTICIPO_PORCENTAJE_DEFECTO` |
| Ventana de disputa | 7 dias | `DIAS_VENTANA_DISPUTA` |
| Cancelacion de evento: reembolso total si la anticipacion es mayor a | 30 dias | `CANCELACION_EVENTO_DIAS_TOTAL` |
| Cancelacion de evento: reembolso parcial si la anticipacion es al menos | 7 dias | `CANCELACION_EVENTO_DIAS_PARCIAL` |
| Porcentaje del reembolso parcial | 50% | `CANCELACION_EVENTO_PORCENTAJE_PARCIAL` |
| Monto minimo por pedido | 2500.00 | `MONTO_MINIMO_PEDIDO` |
| Tarifa de servicio, plan Taller | 8% | `TARIFA_TALLER_PORCENTAJE` |
| Tarifa de servicio, plan Estudio | 5% | `TARIFA_ESTUDIO_PORCENTAJE` |

Los valores por defecto viven **una sola vez**, en `Settings`. `PoliticasPedido` no tiene valores por defecto: se construye con `PoliticasPedido.desde_config(settings)`. Las pruebas del dominio construyen instancias explicitas, lo que prueba de paso que las politicas se pueden cambiar.

## Reglas de negocio

### Dinero

- Todo calculo es `Decimal`, cuantizado a `0.01` con `ROUND_HALF_UP`.
- `anticipo = cuantizar(monto_total * porcentaje / 100)` y `saldo = monto_total - anticipo`. **El saldo se calcula por resta**, para que anticipo mas saldo den exactamente el total, centimo por centimo.
- Ningun pedido por debajo del monto minimo.

### Porcentaje de anticipo

- `encargo` y `evento`: el artista lo elige dentro del rango; si no elige, se usa el defecto. Fuera del rango, se rechaza.
- `obra_disponible`: no tiene anticipo. El porcentaje es nulo.

### Tarifa

Al crear el pedido se copia la tarifa del plan del artista a `pedidos.tarifa_porcentaje`. Si el artista cambia de plan despues, el pedido no cambia.

### Cotizacion y contraoferta

`pedidos.consulta_id` es unico: una consulta tiene como mucho un pedido. Por eso:

- Mientras el pedido esta en `cotizado`, el artista puede **actualizar la cotizacion** (monto, descripcion, porcentaje de anticipo, fechas). Asi funciona la contraoferta: es el mismo pedido.
- `rechazado` es terminal y pasa la consulta a `descartada`.

### Estados de la consulta

| Momento | Consulta pasa a |
|---|---|
| Se crea el pedido de encargo o evento | `cotizada` |
| Se captura el anticipo, o se confirma una obra disponible | `convertida` |
| Se rechaza el pedido | `descartada` |

### Obra disponible

- Solo se puede pedir una obra en estado `disponible`, con precio, que no sea del propio cliente. El monto del pedido es el precio de la obra.
- "La quiero" crea en una sola operacion la consulta, ya en estado `convertida`, y el pedido con su cobro total.
- La obra pasa a `vendida` cuando el cobro se captura en el despacho. No antes.
- **Garantia en la base:** un indice unico parcial sobre `pedidos(obra_id)` para los pedidos de tipo `obra_disponible` que no esten `rechazado` ni `cancelado`. Si dos clientes piden la misma obra a la vez, el segundo recibe una excepcion de dominio `ObraNoDisponible`, traducida desde el error de integridad.

### Ventana de disputa

Cuando el pedido entra en `saldo_pagado`, se fija `disputable_hasta`:

| Tipo | Desde |
|---|---|
| `encargo` | El momento en que se captura el saldo, que es cuando se libera el archivo final |
| `evento` | La fecha del evento |
| `obra_disponible` | El despacho, porque no se registra la recepcion |

Mas `DIAS_VENTANA_DISPUTA` dias. Un pedido en `saldo_pagado` cuya ventana vencio pasa a `completado` con la funcion de vencimientos.

### Cancelacion

Quien cancela cambia el resultado:

| Quien | Tipo | Resultado |
|---|---|---|
| Artista | Cualquiera | Se devuelve el 100% de lo capturado y se liberan las autorizaciones |
| Cliente | `encargo` | Las autorizaciones y los cobros pendientes se cancelan. **El anticipo capturado no se devuelve** |
| Cliente | `evento` | Segun la anticipacion respecto de la fecha del evento: mayor a 30 dias, 100%; de 7 a 30 dias inclusive, 50%; menos de 7 dias, 0% |
| Cliente | `obra_disponible` | Solo antes del despacho: se libera la autorizacion |

La anticipacion es `fecha_evento - momento_de_cancelacion`. Los bordes son exactos: 30 dias justos es parcial; 7 dias justos es parcial.

El dominio no ejecuta nada: produce un **plan de cancelacion**, una lista de acciones por cobro (`liberar_autorizacion`, `reembolsar` con monto, `conservar`). Quien llama ejecuta el plan en la pasarela y despues le pasa al servicio los hechos resultantes.

### Disputa

- La abre el cliente o el artista del pedido, nadie mas.
- Se puede abrir desde `vista_previa_entregada`, o desde `saldo_pagado` mientras la ventana no haya vencido.
- Crea la fila en `disputas` y pasa el pedido a `en_disputa`, en la misma transaccion.
- La resuelve moderacion hacia `completado` o `cancelado`. Moderacion puede ordenar devolver cualquier cobro, total o parcialmente, **incluido el anticipo**: la disputa es como se establece un incumplimiento del artista.

## Transiciones permitidas

Cualquier transicion que no este en esta tabla levanta `InvalidStateTransition`. La tabla vive en el dominio como datos, no como `if` desparramados.

| Tipo | Desde | Hacia | Evento |
|---|---|---|---|
| todos | `cotizado` | `rechazado` | El cliente rechaza o el artista retira la cotizacion |
| `encargo`, `evento` | `cotizado` | `anticipo_pagado` | Se captura el anticipo |
| `encargo` | `anticipo_pagado` | `en_proceso` | El artista empieza el trabajo |
| `encargo` | `en_proceso` | `vista_previa_entregada` | El artista entrega la vista previa y se autoriza el saldo |
| `encargo` | `vista_previa_entregada` | `saldo_pagado` | El cliente aprueba y se captura el saldo |
| `evento` | `anticipo_pagado` | `saldo_pagado` | Se captura el saldo antes del evento |
| `obra_disponible` | `cotizado` | `en_proceso` | El cliente confirma y se autoriza el cobro total |
| `obra_disponible` | `en_proceso` | `saldo_pagado` | El artista despacha con guia y se captura el cobro |
| todos | `saldo_pagado` | `completado` | Vence la ventana de disputa |
| `encargo` | `vista_previa_entregada` | `en_disputa` | Se abre una disputa |
| todos | `saldo_pagado` | `en_disputa` | Se abre una disputa dentro de la ventana |
| `encargo` | `anticipo_pagado`, `en_proceso`, `vista_previa_entregada` | `cancelado` | Cancela el cliente o el artista |
| `evento` | `anticipo_pagado`, `saldo_pagado` | `cancelado` | Cancela el cliente o el artista, antes de la fecha del evento |
| `obra_disponible` | `en_proceso` | `cancelado` | Cancela el cliente o el artista, o vence la autorizacion sin despacho |
| todos | `en_disputa` | `completado`, `cancelado` | Moderacion resuelve |

`completado`, `rechazado` y `cancelado` son terminales.

## Cambios al esquema

Se reescribe la migracion inicial y se ajusta `models/pedidos.py`:

1. `pedidos.anticipo_porcentaje`: `Numeric(5, 2)`, nullable. CHECK: es nulo si y solo si el tipo es `obra_disponible`; si no es nulo, esta entre 0 y 100 exclusivos. El rango de negocio (30 a 50) **no** va en la base, porque es configurable.
2. `pedidos.disputable_hasta`: `DateTime(timezone=True)`, nullable.
3. `cobros.monto_reembolsado`: `Numeric(12, 2)`, no nulo, por defecto `0`. CHECK: entre 0 y `monto`. Un cobro reembolsado parcialmente queda en estado `reembolsado` con este monto menor que `monto`.
4. Indice unico parcial `ux_pedidos_obra_activa` sobre `pedidos(obra_id)`, con la condicion descrita arriba. Declarado igual en el modelo y en la migracion.

## Superficie del servicio

Funciones `async` en `src/services/pedidos.py`. Los nombres son orientativos; la cobertura no lo es.

| Funcion | Hace |
|---|---|
| `crear_pedido_desde_cotizacion` | Crea el pedido de encargo o evento en `cotizado` con sus dos cobros pendientes, congela la tarifa, pasa la consulta a `cotizada` |
| `actualizar_cotizacion` | Solo en `cotizado`. Recalcula los montos de los dos cobros pendientes |
| `crear_pedido_obra_disponible` | "La quiero": consulta `convertida`, pedido en `cotizado`, cobro total pendiente. Traduce el choque del indice parcial a `ObraNoDisponible` |
| `rechazar_pedido` | `cotizado` a `rechazado`; cobros pendientes a `cancelado`; consulta a `descartada` |
| `registrar_anticipo_capturado` | Anticipo `capturado`, pedido `anticipo_pagado`, consulta `convertida` |
| `iniciar_trabajo` | `anticipo_pagado` a `en_proceso` |
| `registrar_vista_previa` | Crea el entregable de vista previa, saldo `autorizado` con su vencimiento, pedido `vista_previa_entregada` |
| `registrar_saldo_capturado` | Saldo `capturado`, pedido `saldo_pagado`, fija `disputable_hasta` |
| `confirmar_obra` | Cobro total `autorizado`, pedido `en_proceso`, consulta `convertida` |
| `registrar_despacho` | Guarda la guia, cobro total `capturado`, obra `vendida`, pedido `saldo_pagado`, fija `disputable_hasta` |
| `cancelar_pedido` | Recibe quien cancela y los hechos de la pasarela ya ejecutados; aplica el plan; pedido `cancelado` |
| `abrir_disputa` | Valida actor y ventana; crea la disputa; pedido `en_disputa` |
| `resolver_disputa` | Recibe destino, resolucion, admin y hechos de la pasarela; cierra la disputa y el pedido |
| `completar_vencidos` | Pasa a `completado` todo pedido en `saldo_pagado` con `disputable_hasta` anterior a un instante dado. Devuelve cuantos |

Todas las fechas se reciben como parametro (`ahora`), nunca se leen del reloj adentro del dominio. Asi las pruebas controlan el tiempo.

## Alcance

Podes crear o modificar:

- `backend/src/domain/__init__.py` (crear)
- `backend/src/domain/politicas.py` (crear)
- `backend/src/domain/pedidos.py` (crear)
- `backend/src/services/__init__.py` (crear)
- `backend/src/services/pedidos.py` (crear)
- `backend/src/core/config.py` (solo agregar los campos de politicas)
- `backend/src/core/exceptions.py` (solo agregar excepciones de dominio)
- `backend/src/models/pedidos.py`
- `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py`
- `backend/.env.example` (documentar las variables nuevas)
- `backend/tests/conftest.py`
- `backend/tests/test_dominio_pedidos.py` (crear)
- `backend/tests/test_servicio_pedidos.py` (crear)

## Prohibido

- Tocar cualquier archivo fuera de esa lista. En especial `mobile/`, `backend/src/api/**`, `backend/src/workers/**` y `backend/pyproject.toml`.
- Crear una migracion nueva. Se reescribe la existente.
- Llamar a una pasarela, real o simulada, desde el dominio o el servicio.
- Hacer `commit` dentro del servicio.
- Leer el reloj dentro del dominio.
- Usar `float` para dinero o porcentajes.
- Cualquier columna de saldo, disponible, retenido o acumulado. `monto_reembolsado` es un hecho del cobro, no un saldo.
- Implementar endpoints, jobs o notificaciones.
- Agregar librerias nuevas.
- Poner el rango de anticipo de 30 a 50 como restriccion de base de datos.

## Pruebas obligatorias

**Del dominio**, en `test_dominio_pedidos.py`, sin base de datos:

1. Cada transicion de la tabla se acepta para su tipo. Una muestra representativa de transiciones prohibidas levanta `InvalidStateTransition`: al menos `encargo` de `cotizado` a `saldo_pagado`, `evento` a `en_proceso`, `obra_disponible` a `anticipo_pagado`, y cualquier salida desde un estado terminal.
2. Anticipo mas saldo da exactamente el total para montos con centimos impares, por ejemplo 10000.01 al 33%.
3. Un porcentaje de anticipo fuera del rango se rechaza, y la ausencia de porcentaje usa el defecto.
4. Los cuatro bordes de la cancelacion de eventos: 30 dias y un segundo es total; 30 dias justos es parcial; 7 dias justos es parcial; 6 dias y 23 horas es cero.
5. El plan de cancelacion: el cliente cancela un encargo con anticipo capturado y el anticipo se conserva; el artista cancela y todo se devuelve.
6. Las politicas son configurables: con una ventana de 3 dias, `disputable_hasta` cambia.

**Del servicio**, en `test_servicio_pedidos.py`, contra una base migrada:

7. Camino completo de un encargo: de `cotizado` a `completado` por vencimiento de la ventana, con la consulta terminando en `convertida` y los dos cobros en `capturado`.
8. Dos pedidos de obra disponible sobre la misma obra: el segundo falla con `ObraNoDisponible`. Despues de rechazar el primero, se puede crear otro.
9. **Atomicidad:** si la actualizacion del cobro falla en la base al hacer `flush`, el estado del pedido no cambia. Una forma de forzarlo es registrar una captura con una `referencia_pasarela` que ya usa otro cobro, que viola la restriccion unica; una forma de aislarlo es un `savepoint`.
10. Abrir una disputa despues de `disputable_hasta` se rechaza; antes, crea la fila en `disputas`.
11. `completar_vencidos` completa solo los pedidos con la ventana vencida.
12. La tarifa queda congelada: cambiar el plan del artista despues de crear el pedido no cambia `tarifa_porcentaje`.

## Criterios de aceptacion

Con la salida de cada comando pegada. Las variables de entorno obligatorias estan en `backend/AGENTS.md`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `python -c "import src.models; import src.main; import src.workers.main; import src.domain.pedidos; import src.services.pedidos"` no lanza excepcion.
- [ ] `pytest -v` pasa contra una base migrada, y la salida muestra las doce pruebas obligatorias.
- [ ] El dominio es puro: `grep -nE "import (sqlalchemy|asyncio)|from sqlalchemy|AsyncSession|settings|datetime.now|utcnow" backend/src/domain/pedidos.py` no devuelve nada.
- [ ] El servicio no hace commit y bloquea el pedido: `grep -n "commit" backend/src/services/pedidos.py` no devuelve nada, y `grep -n "with_for_update" backend/src/services/pedidos.py` devuelve al menos una linea.
- [ ] `alembic upgrade head` y `alembic downgrade base` corren limpios sobre una base vacia, sin tipos enum huerfanos.
- [ ] `alembic revision --autogenerate -m "verificacion"` genera `upgrade` y `downgrade` vacios. Pegá el cuerpo y borralo.
- [ ] El esquema creado desde los modelos con `create_all` es identico al de la migracion, comparando `pg_dump --schema-only` de las dos bases.
- [ ] `pg_indexes` muestra `ux_pedidos_obra_activa` con su condicion.
- [ ] Una consulta a `information_schema.columns` con el patron `saldo|balance|disponible|retenido|acumulado` devuelve cero filas.
- [ ] `grep -rn "Mapped\[float\]\|: float" backend/src/` no devuelve nada.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `feat/lote-02-maquina-estados` **solo los archivos del alcance**, con un mensaje convencional (`feat(backend): ...`). No commitees nada de `orquestacion/`: el prompt y la bitacora los commitea el orquestador. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones. Si encontras una transicion que el negocio necesita y la tabla no tiene, decilo ahi en vez de agregarla.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
