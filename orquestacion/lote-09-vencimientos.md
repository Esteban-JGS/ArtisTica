# [Lote 9] Worker seguro, barrido de vencimientos y DT25

## Rol
Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto mínimo
ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Un pedido es de tipo `encargo`, `evento` u `obra_disponible`, y cada hito de pago es un `cobro`. La pasarela custodia el dinero: ArtísTica no guarda saldos, solo registra hechos que la pasarela ya confirmó.

Hoy nada pasa por el paso del tiempo. Un pedido con la ventana de disputa vencida no se completa, una autorización vencida queda `autorizado` para siempre, un evento cuya fecha llegó sin el saldo queda trabado, y un 3DS abandonado en "La quiero" deja la obra tomada. Este lote agrega un barrido periódico que resuelve esos casos y permite al cliente volver a autorizar un saldo vencido. Además, hace seguro el worker de la cola de trabajos, que hoy ejecuta cada job con la fila bloqueada.

Las reglas de negocio de este lote, ya decididas:

| Caso | Regla |
|---|---|
| `saldo_pagado` con `disputable_hasta` vencido | Pasa a `completado`. La función ya existe |
| Autorización vencida (`autorizado_hasta <= ahora`) de un cobro `autorizado` | El cobro pasa a `vencido`. Si la pasarela todavía la tiene viva, primero se libera, para que el cliente no quede con dos retenciones al volver a autorizar |
| Saldo de un encargo `vencido` en `vista_previa_entregada` | El cliente lo vuelve a autorizar con el mismo `POST /pedidos/{id}/saldo` durante `DIAS_REAUTORIZACION_SALDO` (7) días desde `autorizado_hasta`. Pasado el plazo, el barrido cancela el pedido como cancelación del cliente después del anticipo: el anticipo queda para el artista |
| Obra disponible en `en_proceso` con el total `vencido` | El barrido cancela el pedido como incumplimiento del artista. No hay nada capturado que devolver, y la obra queda libre sola, porque el índice `ux_pedidos_obra_activa` solo cuenta pedidos vivos |
| Evento en `anticipo_pagado` cuya `fecha_evento` ya llegó | Se cancela. El anticipo no se devuelve y el saldo pendiente se anula |
| "La quiero" con el 3DS abandonado: pedido `cotizado`, total `pendiente` con referencia y `MINUTOS_ABANDONO_3DS` (30) desde `pedidos.created_at` | Se consulta el cobro. Si el cliente sí completó la autorización, se registra. Si no, se libera en la pasarela y se rechaza el pedido |
| Saldo de un evento pagado en la fecha del evento o después | `pagar_saldo` responde 409 (`FueraDePlazo`) |
| `consultar_cobro` dice `requiere_accion` sin URL | `verificar` y `pagar_saldo` responden `pendiente`, no `requiere_accion` con URL nula |

Regla que vale en todo el barrido: si un cobro del pedido espera un 3DS (estado `pendiente` con `referencia_pasarela`), antes de vencer o cancelar nada se consulta ese intento en la pasarela. Si ya cobró o autorizó, se registra como lo haría `verificar` y el pedido no se cancela.

## Estado actual del repositorio

Worker:

- `backend/src/workers/main.py:33-91`: `worker_loop` toma un job con `FOR UPDATE SKIP LOCKED` y lo ejecuta **dentro de esa misma transacción**. Un job lento retiene la conexión y el bloqueo todo el tiempo. Si el proceso muere a mitad de camino, el rollback devuelve el job a `pending` sin contar el intento.
- `backend/src/workers/main.py:29-30`: instala los manejadores de señales al importar el módulo. Así no se puede importar en una prueba sin efectos.
- `backend/src/workers/dispatcher.py`: `dispatch_job(job_type, payload)` busca el handler en `HANDLERS`. Los cuatro handlers de `backend/src/workers/handlers/` son relleno y reciben solo el `payload`. **No se tocan.**
- `backend/src/models/operacion.py:13-28`: `Job` con `type` y `status` de texto libre, `attempts`, `max_attempts` (3), `run_after`, `locked_at`, `locked_by` y `last_error`.
- No hay ninguna prueba del worker.

Pedidos y cobros:

- `backend/src/domain/pedidos.py:82-86`: `TRANSICIONES_COBRO`. `vencido` no tiene salida.
- `backend/src/domain/pedidos.py:357-377`: `_accion_al_cerrar` decide qué hacer con cada cobro al cerrar un pedido. Un cobro `vencido` no requiere acción.
- `backend/src/domain/pedidos.py:390-416`: `planear_cancelacion` exige un actor (`Rol`) y levanta `FueraDePlazo` para un evento con `ahora >= fecha_evento`. No sirve para el barrido, que cancela sin actor y justamente después de la fecha.
- `backend/src/services/pedidos.py:146-176`: `esperando_autenticacion`, `registrar_intento_en_espera` y `descartar_intento` (que deja la referencia nula y sube `intentos`).
- `backend/src/services/pedidos.py:550-574`: `registrar_saldo_autorizado` valida la transición del pedido a `vista_previa_entregada`. Falla si el pedido ya está ahí, que es el caso de la reautorización.
- `backend/src/services/pedidos.py:373-388`: `rechazar_pedido` anula los cobros, descarta la consulta y deja el pedido `rechazado`.
- `backend/src/services/pedidos.py:694-718`: `cancelar_pedido` necesita `actor_id`.
- `backend/src/services/pedidos.py:810-829`: `completar_vencidos(session, ahora)` existe y no la llama nadie.
- `backend/src/services/contratacion.py`: es la **única capa que llama a la pasarela por un pedido**. Tiene estas piezas:
  - `_bloquear` (línea 175), que toma el perfil del artista y después el pedido.
  - `_seguir_intento` (293), que consulta un intento en espera de 3DS y lo registra, o devuelve `None` si terminó sin dinero.
  - `_iniciar_cobro` (324), `_capturar` (392) y `_soltar_intentos_en_espera` (415).
  - `pagar_saldo` (663) y `verificar_cobro` (990).
  - Las claves de idempotencia (142-155): `{cobrar|autorizar}-{cobro}-{intentos}`, `capturar-{cobro}`, `liberar-{cobro}-{intentos}` y `reembolsar-{cobro}-{monto}`.
- `_Contexto` (131) lleva un `usuario: Profile` que solo usa `_resultado` para armar la respuesta de la API.
- `backend/src/payments/falsa.py`: acepta un `reloj` inyectable.
  - `consultar_cobro` informa `liberado` para una autorización cuyo `autorizado_hasta` ya pasó según **su** reloj.
  - `liberar_autorizacion` acepta un cobro `autorizado` o `requiere_accion`.
  - `completar_autenticacion(referencia, aprobada=...)` simula el regreso del banco.
  - `obtener_pasarela()` (`src/payments/fabrica.py`) da una instancia por proceso.
- `backend/src/main.py:25-29`: el `lifespan` está vacío.
- `backend/src/domain/politicas.py`: `PoliticasPedido` y `desde_config`.
- `backend/src/core/config.py:52-82`: las políticas con sus valores por defecto.

Pruebas: `tests/conftest.py` tiene `sesion_api`, que abre una transacción externa y une la sesión con `join_transaction_mode="create_savepoint"`. Así los `commit` liberan savepoints y todo se deshace al final. `tests/test_pedidos_api.py` tiene las ayudas `encargo(..., hasta=...)`, `artista`, `perfil`, `obra`, `pagar`, `ruta`, `ruta_la_quiero`, `ruta_verificar` y `cobros_db`. `tests/test_cobros_api.py` muestra cómo usar una `PasarelaFalsa(reloj=...)` propia. Importar esas ayudas desde otro archivo de prueba está aceptado.

## Objetivo
Que el worker ejecute cada job fuera del bloqueo y recupere los que quedan colgados, y que un barrido periódico dentro del proceso de la API aplique todos los vencimientos de la tabla de arriba sin mover dinero dos veces.

## Alcance
Archivos que podés crear o modificar:

- backend/src/workers/main.py
- backend/src/tareas/__init__.py (nuevo)
- backend/src/tareas/barrido.py (nuevo)
- backend/src/main.py
- backend/src/core/config.py
- backend/src/domain/politicas.py
- backend/src/domain/pedidos.py
- backend/src/services/pedidos.py
- backend/src/services/contratacion.py
- backend/.env.example
- backend/tests/conftest.py
- backend/tests/test_worker.py (nuevo)
- backend/tests/test_vencimientos.py (nuevo)
- backend/tests/test_dominio_pedidos.py
- backend/tests/test_configuracion.py

## Prohibido
- Tocar cualquier archivo fuera de la lista anterior. En particular, no se tocan `src/api/`, `src/schemas/`, `src/payments/`, `src/models/`, `alembic/`, los handlers del worker ni `dispatcher.py`.
- Tocar `mobile/`, que es de otra persona.
- Cambiar el stack o agregar librerías nuevas.
- Crear una migración. Este lote no cambia el esquema.
- Cambiar una ruta, un campo de request o un campo de respuesta de la API. El contrato con la app no cambia: la reautorización usa el mismo `POST /pedidos/{id}/saldo`.
- Inventar funcionalidades que no estén en este prompt: nada de webhooks, `ledger_entries` ni `eventos_pasarela`, que son del lote 9b.
- Llamar a la pasarela desde fuera de `services/contratacion.py`. El barrido llama a funciones de `contratacion`, nunca a la pasarela directo.
- Bloquear filas en otro orden que perfil, pedido, consulta, obra (D18). El perfil siempre primero.
- Un `commit` dentro de `src/services/`. Los servicios hacen `flush`; confirma quien llama (el barrido o el worker).
- Usar `pg_advisory_lock` de sesión. Con Supavisor en modo transacción no es seguro.
- Mover dinero dos veces. Toda llamada a la pasarela usa las claves de idempotencia existentes.

## Trabajo a realizar

### 1. Worker seguro (`src/workers/main.py`)

Partí el loop en funciones que se puedan probar. Cada una recibe `sesiones: async_sessionmaker[AsyncSession]` y `ahora`, y abre sus propias transacciones:

1. `recuperar_colgados(sesiones, *, ahora, tiempo_maximo) -> int`: un job en `processing` con `locked_at < ahora - tiempo_maximo` cuenta como un intento fallido. Sube `attempts`, guarda `last_error` con un texto que diga que superó el tiempo máximo, y vuelve a `pending` con el mismo backoff de hoy (`2**attempts` minutos) o pasa a `dead` si llegó a `max_attempts`. Limpia `locked_at` y `locked_by`.
2. `tomar_job(sesiones, *, ahora, worker_id) -> JobTomado | None`: en una transacción corta, `FOR UPDATE SKIP LOCKED` sobre el `pending` más viejo con `run_after <= ahora`. Lo marca `processing` con `locked_at` y `locked_by`, hace **commit** y devuelve un dataclass congelado con `id`, `type` y `payload`.
3. `cerrar_job(sesiones, job_id, *, worker_id, error: str | None, ahora) -> None`: en otra transacción, bloquea la fila. Si ya no está en `processing` con ese `locked_by` (porque otro worker la recuperó), no toca nada y loguea un aviso. Si no, la marca `completed` o aplica el fallo con el mismo backoff y el mismo `dead`, y limpia el bloqueo.
4. `procesar_uno(sesiones, *, ahora, worker_id, despachar=dispatch_job) -> bool`: toma, ejecuta `despachar(job.type, job.payload)` **fuera de toda transacción**, atrapa cualquier excepción y cierra. Devuelve si hubo un job.
5. `worker_loop()` usa `AsyncSessionLocal`, llama a `recuperar_colgados` al arrancar y después cada tanto (por ejemplo, cada 60 vueltas), y duerme 2 segundos cuando no hay jobs. Los manejadores de señales se instalan dentro de una función `main()` que corre bajo `if __name__ == "__main__"`, no al importar.

Un handler que necesite la base abre su propia sesión. Dejalo escrito en el docstring del módulo. Los handlers de hoy no cambian.

### 2. Configuración y políticas

En `core/config.py`, con valores por defecto y validación:

| Variable | Defecto | Validación |
|---|---|---|
| `DIAS_REAUTORIZACION_SALDO` | 7 | `ge=1` |
| `MINUTOS_ABANDONO_3DS` | 30 | `ge=5` |
| `BARRIDO_ACTIVO` | `True` | |
| `BARRIDO_INTERVALO_SEGUNDOS` | 60 | `ge=10` |
| `JOB_TIEMPO_MAXIMO_MINUTOS` | 15 | `ge=1` |

En `PoliticasPedido` se agregan `plazo_reautorizacion_saldo: timedelta` y `abandono_3ds: timedelta`, los dos positivos y leídos en `desde_config`. Documentá las cinco variables en `.env.example`, comentadas como las demás.

### 3. Dominio (`src/domain/pedidos.py`)

1. `TRANSICIONES_COBRO`: agregá `vencido` a `pendiente`. Es la única salida de `vencido` y solo la usa la reautorización.
2. `limite_reautorizacion(autorizado_hasta, politicas) -> datetime` y `validar_reautorizacion(estado_pedido, estado_saldo, autorizado_hasta, ahora, politicas)`. Admite un encargo en `vista_previa_entregada` con el saldo `vencido` o `pendiente` (un reintento después de un rechazo), y levanta `FueraDePlazo` si `ahora >= limite`. Cualquier otro caso levanta `InvalidStateTransition`.
3. `validar_saldo_evento_a_tiempo(fecha_evento, ahora)`: `FueraDePlazo` si `fecha_evento` es nula o `ahora >= fecha_evento`.
4. `planear_vencimiento(tipo, estado, cobros) -> PlanCobros`: el plan de una cancelación por vencimiento, sin actor ni fecha.
   - Valida la transición a `cancelado`.
   - Acepta solo tres casos: encargo en `vista_previa_entregada`, evento en `anticipo_pagado` y obra disponible en `en_proceso`.
   - Reusa `_accion_al_cerrar` con porcentaje 0 para encargo y evento, así el anticipo se conserva, y 100 para la obra, que no tiene nada capturado.
   - Un cobro `pendiente` se anula sin pasarela (`CANCELAR`), y uno `vencido` no lleva acción.

### 4. Servicio de pedidos (`src/services/pedidos.py`)

Solo registra hechos ya confirmados y hace `flush`:

1. `registrar_saldo_autorizado`: si el pedido ya está en `vista_previa_entregada` (reautorización), no vuelve a validar la transición del pedido, solo la del cobro (`pendiente` a `autorizado`). El resto queda igual.
2. `reabrir_saldo_vencido(session, *, cobro)`: de `vencido` a `pendiente`. La referencia queda nula y `intentos` sube, así la clave `autorizar-{cobro}-{intentos}` es nueva. `autorizado_hasta` **se conserva**: de ahí sale el plazo de reautorización.
3. `registrar_autorizacion_vencida(session, *, pedido_id, cobro_id, ahora)`: de `autorizado` a `vencido`. Exige `autorizado_hasta <= ahora`.
4. `cancelar_por_vencimiento(session, *, pedido_id, hechos, ahora) -> PlanCobros`: recalcula `planear_vencimiento` bajo bloqueo, exige los hechos con `verificar_hechos`, aplica el plan y deja el pedido `cancelado`. Es igual a `cancelar_pedido`, pero sin actor.
5. `candidatos_vencimiento(session, *, ahora, politicas) -> CandidatosVencimiento`: un dataclass congelado con una tupla de ids de pedido por caso. Hace lecturas sin bloqueo y cada tupla tiene un tope razonable (por ejemplo, 100). Los casos son:
   - `la_quiero_abandonados`: obra disponible `cotizado`, total `pendiente` con referencia y `created_at <= ahora - abandono_3ds`.
   - `autorizaciones_vencidas`: pedidos con un cobro `autorizado` y `autorizado_hasta <= ahora`, en encargo `vista_previa_entregada` u obra disponible `en_proceso`.
   - `reautorizaciones_vencidas`: encargo en `vista_previa_entregada` con el saldo `vencido` o `pendiente` y `autorizado_hasta + plazo_reautorizacion_saldo <= ahora`.
   - `eventos_impagos`: evento en `anticipo_pagado` con `fecha_evento <= ahora`.

### 5. Contratación (`src/services/contratacion.py`)

Las operaciones del barrido, una por caso. Cada una recibe `session`, `pasarela`, `pedido_id`, `ahora` y `politicas`, y sigue siempre los mismos pasos:

1. Bloquea perfil y pedido.
2. **Vuelve a comprobar la condición bajo bloqueo**. Si ya no aplica, devuelve `False` sin tocar nada.
3. Llama a la pasarela con las claves existentes.
4. Registra con `services/pedidos` y devuelve `True`.

Para resolver un intento en espera de 3DS, extraé de `_seguir_intento` una función que consulte y registre sin armar la respuesta de la API, y que la usen los dos. El `_Contexto` del barrido puede llevar el perfil del artista como `usuario`, o lo podés cambiar para que no lo necesite. Elegí lo más limpio y anotalo en observaciones.

1. `soltar_la_quiero_abandonado`: resuelve el intento.
   - Si la pasarela lo autorizó, lo registra (`confirmar_obra`, el camino normal) y devuelve `True`.
   - Si sigue en `requiere_accion` o `pendiente`, lo libera con `liberar-{cobro}-{intentos}`. Si la pasarela responde `OperacionNoSoportada` (ONVO puede no permitir cancelar en `requires_action`, pregunta 20), lo loguea y sigue: en el peor caso queda una autorización que nadie captura y vence sola.
   - Después `descartar_intento` y `rechazar_pedido`.
   - Si ya terminó sin dinero, solo `descartar_intento` y `rechazar_pedido`.
2. `vencer_autorizacion`: para cada cobro `autorizado` con `autorizado_hasta <= ahora`, consulta la pasarela.
   - `autorizado`: la libera con `liberar-{cobro}-{intentos}`.
   - `liberado` o `fallido`: no hace nada en la pasarela.
   - `capturado`: levanta `HechosInconsistentes` y no registra.
   - Después `registrar_autorizacion_vencida`. Si el pedido es una obra disponible, en la misma transacción lo cancela con `cancelar_por_vencimiento` (el plan sale vacío).
3. `cerrar_reautorizacion_vencida`: resuelve primero el intento de 3DS del saldo, si hay. Si autorizó, lo registra y devuelve `True` sin cancelar. Si no, libera en la pasarela lo que siga en curso, con el mismo criterio de `_soltar_intentos_en_espera`, y cancela con `cancelar_por_vencimiento`.
4. `cancelar_evento_impago`: lo mismo. Si el intento del saldo cobró, lo registra y el pedido queda `saldo_pagado`. Si no, cancela con `cancelar_por_vencimiento`. El anticipo se conserva y el saldo pendiente se anula.

Cambios en lo que ya existe:

- `pagar_saldo`, encargo:
  - Si el pedido está en `en_proceso`, sigue el camino de hoy.
  - Si está en `vista_previa_entregada`, llama a `validar_reautorizacion`. Si el saldo está `vencido`, llama a `reabrir_saldo_vencido` y sigue con `_iniciar_cobro` como siempre. Un rechazo o un 3DS se comportan igual que hoy.
- `pagar_saldo`, evento: llama a `validar_saldo_evento_a_tiempo` antes de llamar a la pasarela.
- `_seguir_intento` y `_iniciar_cobro`: con `requiere_accion` y la URL nula, el resultado es `PENDIENTE`. El intento queda en espera igual.

### 6. Barrido (`src/tareas/barrido.py`)

1. `barrer(sesiones, pasarela, *, ahora, politicas) -> ResumenBarrido`:
   - Lee los candidatos en una sesión.
   - Procesa cada pedido en **su propia sesión y transacción**, con `commit` si salió bien y rollback si falló. Una falla en un pedido se loguea con el id del pedido y el tipo de la excepción, sin el mensaje de la pasarela, y no frena a los demás.
   - Al final llama a `completar_vencidos` en su propia transacción.
   - El orden es: "La quiero" abandonados, autorizaciones vencidas, reautorizaciones vencidas, eventos impagos y completar.
   - Devuelve un dataclass con cuántos hizo y cuántos fallaron de cada caso.
2. `ciclo(sesiones, pasarela, *, intervalo, politicas_de, reloj)` llama a `barrer` y duerme `intervalo`, para siempre.
   - `politicas_de` es una función que devuelve las políticas; `reloj` devuelve la hora UTC.
   - Una excepción de una vuelta se loguea y no corta el ciclo. `CancelledError` sí lo corta.
3. En `src/main.py`, el `lifespan` arranca `ciclo` con `asyncio.create_task` si `BARRIDO_ACTIVO`. Usa `AsyncSessionLocal`, `obtener_pasarela()` (la misma instancia que usa la API, por eso corre acá y no en el worker), `BARRIDO_INTERVALO_SEGUNDOS` y `PoliticasPedido.desde_config(settings)`. Al apagar, cancela la tarea y la espera.

El `ASGITransport` de httpx que usan las pruebas no corre el `lifespan`, así que ninguna prueba arranca el ciclo. No lo cambies.

Dos procesos de la API pueden barrer a la vez. No hace falta un bloqueo global: el paso 2 de cada operación, con perfil y pedido bloqueados, hace que el segundo no haga nada.

### 7. Pruebas

En `conftest.py`, un fixture `sesiones_prueba` que devuelva un `async_sessionmaker` unido a una conexión con una transacción externa y `join_transaction_mode="create_savepoint"`. Tiene que compartir la conexión con `sesion_api` cuando la prueba usa los dos, para que el barrido vea lo que creó la API. Al final, rollback.

`tests/test_worker.py`, como mínimo:

1. `tomar_job` marca `processing` y el job no vuelve a salir en un segundo `tomar_job`.
2. Un job que termina bien queda `completed`. Uno que falla queda `pending`, con `attempts` 1 y `run_after` corrido, y en el último intento queda `dead`.
3. `procesar_uno` ejecuta el handler fuera de la transacción: el handler de prueba abre otra sesión y ve el job en `processing` ya confirmado.
4. `recuperar_colgados` recupera un `processing` viejo, cuenta el intento, y no toca uno reciente.
5. `cerrar_job` no pisa un job que otro worker recuperó (`locked_by` distinto).
6. Importar `src.workers.main` no instala manejadores de señales: `signal.getsignal(signal.SIGINT)` sigue igual después del import.

`tests/test_vencimientos.py`, por la API y llamando a `barrer`, con una `PasarelaFalsa(reloj=...)` propia y `ahora` explícito, como mínimo:

1. Una autorización del saldo vencida: el barrido deja el cobro `vencido` y el pedido en `vista_previa_entregada`. Si la falsa todavía la tiene viva según su reloj, el barrido la libera. Si ya la informa `liberado`, no llama a `liberar_autorizacion`.
2. Reautorización: con el saldo `vencido`, `POST /saldo` responde `completado`, el saldo queda `autorizado` con una referencia nueva y `intentos` subió en 1. Después `aprobar` captura y el pedido queda `saldo_pagado`.
3. Reautorización con 3DS: `requiere_accion`, `completar_autenticacion` y `verificar` dejan el saldo `autorizado`.
4. Reautorización rechazada: responde `rechazado`, el saldo queda `pendiente`, y un segundo intento con otra tarjeta funciona.
5. Reautorización fuera de plazo: 409.
6. Pasado el plazo sin reautorizar, el barrido cancela el pedido. El anticipo sigue `capturado` sin reembolso, y la pasarela no recibió ninguna llamada de reembolso.
7. Pasado el plazo con un 3DS de reautorización que el cliente sí completó: el barrido registra el saldo `autorizado` y **no** cancela.
8. Obra disponible con el total vencido en `en_proceso`: el barrido cancela el pedido y otro cliente puede hacer "La quiero" sobre la misma obra.
9. Evento cuya fecha llegó: el barrido lo cancela con el anticipo `capturado` y el saldo `cancelado`. Si el saldo tenía un 3DS que cobró, queda `saldo_pagado`.
10. `POST /saldo` de un evento en su fecha o después: 409, sin llamar a la pasarela.
11. DT25: "La quiero" con 3DS sin completar. Antes de `MINUTOS_ABANDONO_3DS` el barrido no toca nada. Después, el pedido queda `rechazado`, la falsa informa el cobro `liberado` y otro cliente puede pedir la obra. Si el 3DS se aprobó antes del barrido, el pedido queda `en_proceso`.
12. `verificar` con `requiere_accion` y URL nula responde `pendiente`.
13. Idempotencia: dos `barrer` seguidos con el mismo `ahora` dan el mismo estado final, y el segundo no hace ninguna llamada de dinero a la pasarela.
14. Aislamiento: si la pasarela falla en un pedido (`programar_falla`), los demás pedidos del mismo barrido se procesan, y el que falló queda como estaba.
15. `barrer` completa los `saldo_pagado` con la ventana vencida.

`tests/test_dominio_pedidos.py`: la nueva transición del cobro, `validar_reautorizacion` en sus casos y bordes, `validar_saldo_evento_a_tiempo` y `planear_vencimiento` para los tres tipos y para un estado no admitido.

`tests/test_configuracion.py`: los valores por defecto y el rechazo de un valor fuera de rango en cada variable nueva.

## Criterios de aceptación
- [ ] `python -m ruff check .` y `python -m ruff format --check .` pasan sin errores.
- [ ] `python -m pytest -q -W error::sqlalchemy.exc.SADeprecationWarning` pasa, con al menos 442 pruebas más las nuevas.
- [ ] `python -m alembic check` no detecta cambios (este lote no tiene migración) y `git diff --name-only develop...HEAD -- alembic` sale vacío.
- [ ] `git diff --name-only develop...HEAD` lista solo archivos del alcance.
- [ ] `grep -rn "from src.api" src/services src/domain src/tareas` sale vacío.
- [ ] `grep -rln "pasarela\.\(cobrar\|autorizar\|capturar\|liberar_autorizacion\|reembolsar\|consultar_cobro\)" src/services src/tareas` lista solo `src/services/contratacion.py`.
- [ ] `grep -rn "commit()" src/services` sale vacío. La palabra sola aparece en docstrings y no cuenta.
- [ ] `grep -rn "pg_advisory" src` sale vacío.
- [ ] Las pruebas 6, 7, 11 y 13 de `test_vencimientos.py` existen con esos números en el nombre (`test_9_06_...`) y pasan. Pegá su salida con `-v`.
- [ ] `python -c "import signal, src.workers.main as w; print(signal.getsignal(signal.SIGINT))"` imprime el manejador por defecto de Python.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.

## Paso 0: crear la rama
Antes de tocar cualquier archivo:

    git switch develop
    git pull --ff-only
    git switch -c feat/lote-09-vencimientos

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

En el árbol de trabajo vas a ver `orquestacion/BITACORA.md` modificado y `orquestacion/lote-09-vencimientos.md` sin rastrear. Son del orquestador: no los toques ni los commitees.

Al terminar, commiteá en esa rama **solo los archivos del alcance**, con mensajes convencionales (`tipo(backend): descripcion`). Pueden ser varios commits, cada uno con sentido por sí solo, por ejemplo uno para el worker y otro para los vencimientos. Los mensajes no llevan líneas `Co-Authored-By` ni mencionan herramientas de asistencia. No commitees nada de `orquestacion/`. No hagas push ni abras PR: eso lo hace el orquestador.

## Cómo entregar
Pegá la salida de `git diff --stat develop...HEAD` y la lista de archivos tocados. Después, la salida literal de cada comando de los criterios de aceptación. Al final, una sección de observaciones con:

- cómo resolviste el `_Contexto` del barrido;
- cualquier caso de la tabla de reglas que no hayas podido cubrir tal como está escrito.

Si algo del prompt te parece equivocado, hacelo igual y anotá la objeción en observaciones.

## Estilo
No usar guiones largos ni guiones medios en comentarios ni documentación.
Explicaciones breves; se prefiere código correcto a párrafos.
Identificadores en español, como el resto del dominio; comentarios en español.
