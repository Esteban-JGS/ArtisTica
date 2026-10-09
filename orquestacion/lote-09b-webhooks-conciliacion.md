# [Lote 9b] Webhooks idempotentes, ledger y DT28

## Rol
Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto mínimo
ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. La pasarela (ONVO, o una falsa en pruebas y en la demo) custodia el dinero. ArtísTica no guarda saldos: registra en `cobros` lo que la pasarela confirmó.

Hoy faltan tres cosas:

1. **No hay endpoint de webhooks.** Si un cliente completa el 3DS y cierra la app antes de volver, el pago queda hecho en la pasarela y sin registrar hasta que alguien llame a `verificar`.
2. **El ledger no se escribe.** `ledger_entries` existe y nadie la escribe, así que no hay un registro de cada captura y cada reembolso.
3. **DT28.** Si una cancelación o una resolución de disputa falla a mitad de camino y se reintenta con otro plan, puede reembolsar dos veces, o responder 502 al liberar algo que la pasarela ya capturó.

Decisiones ya tomadas (D29, D30 y D31):

- **El webhook se procesa en la misma petición,** no en el worker: la pasarela falsa vive en la memoria del proceso de la API. El endpoint sigue estos pasos:
  1. Verifica el origen.
  2. Guarda el evento.
  3. Confirma.
  4. Lo procesa en otra transacción.

  Responde 200 apenas el evento quedó guardado, aunque el proceso falle. El barrido lo reintenta.
- **Procesar un evento es conciliar su cobro.** Se consulta el cobro en la pasarela y se registra solo lo que ella confirma: **un webhook nunca mueve dinero ni registra nada por sí solo**. Lo que no cuadra no se corrige automáticamente, se marca como discrepancia para moderación.
- **El ledger lleva una fila por cada captura y cada reembolso,** escrita en la misma transacción que cambia el cobro, con una clave única. Lo que la pasarela no informa queda nulo.
- **DT28:** antes de ejecutar un plan, se consulta cada cobro que el plan toca y se toma como hecho lo que ya esté hecho.

El criterio que manda en este lote es que el flujo funcione con **ONVO real**, no solo con la pasarela falsa. De ONVO se sabe esto (ver `src/payments/onvo.py`):

- Solo documenta `payment-intent.succeeded` y `payment-intent.failed`. **No documenta ningún evento para una autorización aprobada** (`requires_capture`), que es lo que usan el saldo de un encargo y "La quiero".
- No firma el cuerpo: manda el secreto tal cual en `X-Webhook-Secret`.
- No informa su tiempo de espera ni su política de reintentos (pregunta 17).

De ahí salen tres reglas:

1. El webhook es un atajo, no la única vía. El barrido concilia cualquier intento que siga esperando el 3DS pasados 30 minutos, haya o no webhook.
2. Procesar un webhook solo **consulta** la pasarela, así que cortarlo a mitad de camino es seguro. Tiene un tiempo máximo, para responder antes de que ONVO se canse de esperar.
3. Las pruebas recorren el endpoint completo también con el adaptador de ONVO y su transporte simulado, con el formato de evento que documenta ONVO.

## Estado actual del repositorio

Pasarela (no se toca):

- `src/payments/contrato.py`:
  - `parsear_webhook(cuerpo, encabezados) -> EventoRecibido`, con `proveedor`, `evento_externo_id`, `tipo` (`TipoEvento`), `referencia` (opcional) y `payload`.
  - `consultar_cobro(referencia) -> ConsultaCobro`, con `estado` (`EstadoCobroPasarela`), `monto`, `monto_capturado`, `monto_reembolsado` (nulos si el proveedor no los informa) y `metadatos` (`pedido_id` y `cobro_id`, que pone `contratacion` al cobrar).
- `src/payments/errores.py`: `FirmaInvalida`, `SolicitudInvalida` y `OperacionNoSoportada` (ONVO sin `ONVO_WEBHOOK_SECRET`).
- `src/payments/falsa.py`:
  - firma con `X-Firma-Pasarela`;
  - `construir_evento(tipo, referencia=..., evento_id=...)` arma cuerpo y encabezados firmados para las pruebas;
  - `consultar_cobro` informa `monto_reembolsado`;
  - `programar_falla(operacion, error)` hace fallar la siguiente llamada.
- `src/payments/onvo.py:556`: el `evento_externo_id` de ONVO se compone de tipo, id y fecha. Solo `payment-intent.*` trae `referencia`.

Modelos y migraciones:

- `src/models/finanzas.py`:
  - `LedgerEntry`: `pedido_id`, `cobro_id`, `profile_id`, `tipo_evento`, `monto_bruto`, `tarifa_artistica`, `costo_procesamiento`, `monto_neto_artista` (los cuatro montos NOT NULL), `referencia_pasarela` y `ocurrido_en`. No tiene índices en sus tres llaves foráneas.
  - `EventoPasarela`: `proveedor`, `evento_externo_id`, `tipo`, `payload`, `procesado_en`, `error`, y el único `uq_eventos_pasarela_proveedor_evento_externo_id`.
  - Las dos tablas están vacías en todo entorno, porque nadie las escribe.
- Cabeza de Alembic: `d3e4f5a6b7c8` (`alembic/versions/d3e4f5a6b7c8_intentos_de_cobro.py`, que sirve de ejemplo de estilo). `tests/test_esquema.py` exige que todo default tenga `server_default`, y que toda tabla tenga RLS sin políticas.

Servicios:

- `src/services/contratacion.py` es la **única capa que llama a la pasarela por un pedido**.
  - `_clave_reembolso` (línea 174) arma hoy `reembolsar-{cobro}-{monto}`.
  - `_resolver_intento` (313) consulta un intento en espera de 3DS y registra lo que la pasarela confirma.
  - `_soltar_intentos_en_espera` (455).
  - `cancelar` (864) y `_ejecutar_cancelacion` (907), que ejecutan liberaciones y reembolsos sin consultar antes.
  - `resolver_disputa` (959), que ejecuta en el orden de `_ORDEN_RESOLUCION` (948): capturas, liberaciones y reembolsos, sin consultar antes.
  - `verificar_cobro` (1047), que en "La quiero" rechaza el pedido si el 3DS terminó sin dinero.
  - `_cancelar_vencido` (1131), del barrido.
  - Los contextos `_Entorno` y `_Contexto`.
- `src/services/pedidos.py`: registra hechos y hace `flush`. Las capturas se registran en tres funciones:
  - `registrar_anticipo_capturado` (405);
  - `registrar_saldo_capturado` (590);
  - `registrar_despacho` (649).

  `_aplicar_plan` (216) aplica capturas y reembolsos de un plan, y la usan `cancelar_pedido` (707), `resolver_disputa` (780) y `cancelar_por_vencimiento` (859). `disputas_abiertas` muestra cómo se pagina por cursor con `traer_pagina`.
- `src/tareas/barrido.py`: corre cada minuto dentro de la API. Procesa cada pedido en su propia transacción y loguea las fallas con `logger.warning` (líneas 76 y 93).

API:

- `src/api/v1/moderacion.py` exige `Admin` en todo, y ninguna respuesta lleva la referencia de la pasarela.
- `src/api/v1/router.py` registra los routers.
- `src/api/deps.py` tiene `Pasarela`, `Sesion` y `Admin`.
- `src/main.py` traduce `ErrorPasarela` a 502.

## Objetivo
Que un webhook repetido se procese una sola vez y concilie su cobro contra la pasarela, que cada captura y cada reembolso queden asentados en el ledger, y que reintentar una cancelación o una resolución con otro plan nunca mueva dinero dos veces.

## Alcance
Archivos que podés crear o modificar, todos dentro de `backend/`:

- alembic/versions/e4f5a6b7c8d9_conciliacion.py (nuevo)
- src/models/finanzas.py
- src/services/ledger.py (nuevo)
- src/services/webhooks.py (nuevo)
- src/services/pedidos.py
- src/services/contratacion.py
- src/tareas/barrido.py
- src/schemas/pagos.py (nuevo)
- src/api/v1/pagos.py (nuevo)
- src/api/v1/moderacion.py
- src/api/v1/router.py
- tests/test_webhooks.py (nuevo)
- tests/test_ledger.py (nuevo)
- tests/test_dt28.py (nuevo)

## Prohibido
- Tocar cualquier archivo fuera de la lista anterior. En particular, `src/payments/`, `src/domain/`, `src/core/` y `mobile/`.
- Cambiar el stack o agregar librerías nuevas.
- Más de una migración.
- Cambiar una ruta o un campo de request o respuesta que ya existe. Solo se agregan dos rutas nuevas.
- Registrar un pago, un rechazo o un reembolso por lo que dice el webhook. Siempre se llama antes a `consultar_cobro`.
- Corregir automáticamente una discrepancia. Se marca y se deja para moderación.
- Llamar a la pasarela por un pedido desde fuera de `services/contratacion.py`. `parsear_webhook` sí puede llamarse desde `services/webhooks.py`, porque no es una operación sobre un pedido.
- Bloquear en otro orden que: evento de la pasarela, perfil, pedido, consulta, obra.
- Un `commit` dentro de `src/services/`. Confirman la API y el barrido.
- Editar o borrar una fila de `ledger_entries`.
- Devolver en una respuesta la referencia de la pasarela, el `payload` del evento o una URL de autenticación.
- Loguear el mensaje de una excepción de la pasarela. Solo el nombre de su tipo.

## Trabajo a realizar

### 1. Migración `e4f5a6b7c8d9` (revisa `d3e4f5a6b7c8`) y modelos

En `ledger_entries`:

- columna `clave` (String, NOT NULL, única con nombre `uq_ledger_entries_clave`);
- `tarifa_artistica`, `costo_procesamiento` y `monto_neto_artista` pasan a admitir nulos;
- índices en `pedido_id`, `cobro_id` y `profile_id`.

En `eventos_pasarela`:

- columna `intentos` (Integer, NOT NULL, `server_default="0"`);
- índice parcial `ix_eventos_pasarela_pendientes` sobre `created_at` con `procesado_en IS NULL`.

El modelo refleja exactamente la migración, así que `alembic check` no detecta nada. El downgrade revierte todo. Dejá un comentario en el downgrade: volver a NOT NULL falla si ya hay filas con nulos, y es aceptable porque es una vuelta atrás de desarrollo.

### 2. Ledger (`src/services/ledger.py`)

Constantes `CAPTURA = "captura"` y `REEMBOLSO = "reembolso"`, y dos funciones que solo agregan filas y hacen `flush`:

- `asentar_captura(session, *, pedido, cobro, ahora)`:
  - `clave = f"captura-{cobro.id}"`;
  - `monto_bruto = cobro.monto`;
  - `tarifa_artistica = porcentaje_de(cobro.monto, pedido.tarifa_porcentaje)` (de `src.domain.pedidos`);
  - `costo_procesamiento` y `monto_neto_artista` nulos;
  - `profile_id = pedido.artista_id`;
  - `referencia_pasarela = cobro.referencia_pasarela`.
- `asentar_reembolso(session, *, pedido, cobro, monto, ahora)`:
  - `clave = f"reembolso-{cobro.id}-{cobro.monto_reembolsado}"`, con el acumulado **después** de aplicar este reembolso;
  - `monto_bruto = monto`, siempre positivo: el tipo dice que es una devolución;
  - los otros tres montos nulos.

En `services/pedidos.py`, llamalas en la misma transacción que cambia el cobro:

- `asentar_captura` en `registrar_anticipo_capturado`, `registrar_saldo_capturado` y `registrar_despacho`;
- en `_aplicar_plan`, después de aplicar cada `CAPTURAR` y cada `REEMBOLSAR`. Para eso `_aplicar_plan` recibe el pedido.

Una autorización, una liberación o un vencimiento no mueven dinero y no se asientan.

### 3. DT28 en `services/contratacion.py`

Antes de ejecutar las acciones de pasarela de `cancelar`, `resolver_disputa` y `_cancelar_vencido`, consultá cada cobro que el plan toca y decidí con esta tabla:

| Acción del plan | Lo que dice la pasarela | Qué se hace |
|---|---|---|
| Capturar | `autorizado` | Capturar, como hoy |
| Capturar | `capturado` por el monto del cobro | Ya hecho: no se llama, cuenta como capturado |
| Capturar | `liberado` o `fallido` | `FueraDePlazo` (el mensaje de hoy) |
| Liberar | `autorizado`, `requiere_accion` o `pendiente` | Liberar, como hoy |
| Liberar | `liberado` o `fallido` | Ya hecho: no se llama, cuenta como liberado |
| Liberar | `capturado` | `InvalidStateTransition` (409) con un mensaje que diga que ya se cobró y que se resuelva como completado o con reembolso. Nunca 502 |
| Reembolsar `m` | `capturado`, con `r = monto_reembolsado de la pasarela - cobro.monto_reembolsado` | Si `r == 0`, reembolsar `m`. Si `r == m`, ya hecho. Si `0 < r < m`, reembolsar solo `m - r`. Si `r > m`, `HechosInconsistentes` (409) diciendo que ya se devolvió más de lo ordenado |
| Reembolsar `m` | `capturado` sin `monto_reembolsado` informado | Como hoy: reembolsar `m`. Loguear un aviso de que no se pudo verificar |
| Cualquiera | Otra combinación | `HechosInconsistentes` |

Detalles de la tabla:

- **Hechos que se registran:** en todos los casos, los del plan completo. Un reembolso hecho en partes se registra como `m`, y una captura ya hecha cuenta como capturada.
- **Clave de reembolso:** `_clave_reembolso` pasa a `reembolsar-{cobro}-{hasta}`. `hasta` es el total reembolsado en la pasarela al terminar esta llamada: el `monto_reembolsado` informado (o `cobro.monto_reembolsado` si no lo informa) más lo que se reembolsa ahora. Repetir la misma operación da la misma clave, y un plan distinto después de un reembolso parcial da otra.
- **Orden:** `_ORDEN_RESOLUCION` se mantiene.
- **Las consultas van antes de mover dinero:** primero se consultan todos los cobros del plan, y recién después se ejecuta la primera operación de dinero. Así, un 409 de la tabla no deja nada a medias.

### 4. Conciliar un cobro (`services/contratacion.py`)

`conciliar_cobro(session, pasarela, referencia, *, ahora, politicas) -> Conciliacion`. **Solo llama a `consultar_cobro`**: nunca a `cobrar`, `autorizar`, `capturar`, `liberar_autorizacion`, `reembolsar` ni `configurar_tarifa`. Es un dataclass congelado con `resultado` (un `StrEnum` con `REGISTRADO`, `SIN_CAMBIOS`, `SIN_COBRO` y `DISCREPANCIA`) y `detalle: str | None`. El detalle es un texto para moderación con ids internos, nunca la referencia.

1. Buscá el cobro por `referencia_pasarela` sin bloquear.
   - **Si no hay cobro:** consultá la pasarela.
     - Si la foto está `autorizado` o `capturado` y sus `metadatos` traen un `cobro_id` existente, es dinero sin registro: devolvé `DISCREPANCIA` con el `cobro_id`.
     - Si no, devolvé `SIN_COBRO`. También si la pasarela responde `SolicitudInvalida` porque no conoce la referencia, que es lo que hace la falsa con una referencia inexistente.
   - **Si hay cobro:** bloqueá perfil y pedido (`_bloquear`), volvé a leer el cobro y comprobá que sigue teniendo esa referencia. Si cambió, seguí como si no hubiera cobro.
2. **Si el cobro espera el 3DS** (`pedidos.esperando_autenticacion`): `_resolver_intento`.
   - Si registró, `REGISTRADO`.
   - Si terminó sin dinero y el pedido es una obra disponible `cotizado`, `rechazar_pedido` como hace `verificar_cobro`, y `REGISTRADO`.
   - Si sigue en espera, `SIN_CAMBIOS`.
3. **Si no espera, comparás la base con la foto:**
   - Coinciden estos pares:
     - `autorizado` en la base con `autorizado` en la pasarela;
     - `capturado` o `reembolsado` con `capturado`, si el `monto_reembolsado` informado es igual al de la base o no viene informado;
     - `cancelado` o `vencido` con `liberado` o `fallido`;
     - `autorizado` vencido según `autorizado_hasta <= ahora` con `liberado`, que lo resuelve el barrido.

     En todos esos casos, `SIN_CAMBIOS`.
   - Cualquier otro par es `DISCREPANCIA`, con un detalle que nombre el cobro, el estado en la base y el estado en la pasarela. **No se cambia nada.**

### 5. Webhooks (`services/webhooks.py`)

- `recibir(session, pasarela, cuerpo, encabezados) -> EventoPasarela`:
  - llama a `parsear_webhook` (sus excepciones suben);
  - inserta con `INSERT ... ON CONFLICT (proveedor, evento_externo_id) DO NOTHING`;
  - si ya existía, lo lee;
  - devuelve la fila. No hace `commit`.
- `procesar(session, pasarela, evento_id, *, ahora, politicas) -> bool`:
  - toma el evento con `FOR UPDATE SKIP LOCKED`. Si está bloqueado o ya tiene `procesado_en`, devuelve `False`;
  - si `tipo` es de cobro (`cobro_autorizado`, `cobro_capturado`, `cobro_fallido`, `autorizacion_vencida` o `reembolso_confirmado`) y trae `referencia`, llama a `contratacion.conciliar_cobro`;
  - cualquier otro tipo, o uno sin referencia, se marca procesado sin acción;
  - marca `procesado_en = ahora`. Con `DISCREPANCIA` o `SIN_COBRO` guarda el detalle en `error`; si no, deja `error` nulo.
- `registrar_fallo(session, evento_id, error_tipo: str)`: sube `intentos` y guarda en `error` solo el nombre del tipo de la excepción.
- `pendientes(session, *, ahora) -> tuple[uuid.UUID, ...]`: eventos sin `procesado_en`, con `intentos < INTENTOS_MAXIMOS_EVENTO` (5, constante del módulo) y `created_at <= ahora - ESPERA_REINTENTO_EVENTO` (1 minuto), los más viejos primero, hasta 100.
- `con_error(session, parametros)`: eventos con `error` no nulo, del más nuevo al más viejo, paginados por cursor con `traer_pagina`. Incluye los procesados con discrepancia y los que agotaron los intentos.

### 6. Endpoint del webhook (`api/v1/pagos.py`)

`POST /api/v1/pagos/webhook`. No lleva autenticación de usuario: el origen lo prueba `parsear_webhook`. Lee el cuerpo crudo con `await request.body()` y los encabezados.

1. Llama a `webhooks.recibir`. Según la excepción:
   - `FirmaInvalida`: 401;
   - `SolicitudInvalida`: 400;
   - `OperacionNoSoportada`: 503.

   En los tres casos no se guarda nada.
2. `commit`.
3. Si el evento ya estaba procesado, responde 200 con `{"estado": "repetido"}`.
4. Si no, en una transacción nueva:
   - llama a `webhooks.procesar` dentro de `asyncio.timeout(TIEMPO_MAXIMO_PROCESO_SEGUNDOS)`, una constante de 8 segundos en `api/v1/pagos.py`, y hace `commit`. Cortarlo es seguro porque procesar solo consulta la pasarela;
   - si `procesar` levanta, o se pasa del tiempo, hace rollback, llama a `registrar_fallo` en otra transacción con `commit`, y loguea solo el tipo de la excepción. El barrido lo retoma.
5. En todos los casos posteriores al paso 2, responde 200 con `{"estado": "recibido"}`.

Esquema de respuesta: `WebhookRespuesta(estado: Literal["recibido", "repetido"])`, en `schemas/pagos.py`.

### 7. Moderación

`GET /api/v1/moderacion/pagos/eventos`, solo `Admin`, paginado como `/moderacion/disputas`, con `con_error`. La respuesta es `EventoPasarelaRespuesta` (en `schemas/pagos.py`), con `id`, `proveedor`, `tipo`, `intentos`, `error`, `procesado_en` y `created_at`. Sin `payload`, sin `evento_externo_id` y sin referencia.

### 8. Barrido (`src/tareas/barrido.py`)

- Agregá un caso `eventos_pendientes`: para cada id de `webhooks.pendientes`, `procesar` en su propia transacción. Si falla, `registrar_fallo` en otra. Contalo en `ResumenBarrido`.
- Agregá un caso `intentos_en_espera`, que es la vía que no depende de ONVO.
  - En `pedidos.candidatos_vencimiento` sumá el campo `intentos_en_espera`: las referencias de cobros `pendiente` con `referencia_pasarela` y `updated_at <= ahora - abandono_3ds`, de pedidos en un estado no terminal. Quedan fuera los de "La quiero" `cotizado`, que ya tienen su propio caso.
  - Para cada referencia, `conciliar_cobro` en su propia transacción.
  - Así, un saldo o un anticipo cuyo 3DS se completó sin volver a la app queda registrado aunque nunca llegue un webhook.
  - Este caso va antes que los vencimientos.
- Pasá los dos `logger.warning` de fallas a `logger.error`, con el mismo texto sin mensaje de la pasarela. Así Sentry avisa de un pedido que falla en cada vuelta (DT29).

## Criterios de aceptación
- [ ] `python -m ruff check .` y `python -m ruff format --check .` pasan.
- [ ] `python -m alembic upgrade head`, `downgrade -1`, `upgrade head` y `alembic check` pasan, y `check` no detecta cambios.
- [ ] `python -m pytest -q -W error::sqlalchemy.exc.SADeprecationWarning` pasa, con al menos 503 pruebas más las nuevas.
- [ ] `git diff --name-only develop...HEAD` lista solo archivos del alcance, y `alembic/versions` tiene una sola migración nueva.
- [ ] `grep -rn "from src.api" src/services src/domain src/tareas` sale vacío.
- [ ] `grep -rln "pasarela\.\(cobrar\|autorizar\|capturar\|liberar_autorizacion\|reembolsar\|consultar_cobro\)" src/services src/tareas src/api` lista solo `src/services/contratacion.py`.
- [ ] `grep -rn "commit()" src/services` sale vacío.
- [ ] `grep -rnE "update\(LedgerEntry|delete\(LedgerEntry" src` sale vacío.
- [ ] La salida de `pytest -v tests/test_webhooks.py tests/test_ledger.py tests/test_dt28.py` va pegada completa.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.

## Pruebas obligatorias

Con nombres `test_9b_NN_...`, numerados del 1 al 29 como abajo. Usá la pasarela falsa y las ayudas de `tests/test_pedidos_api.py` y `tests/test_cobros_api.py`; importarlas entre archivos está aceptado.

`tests/test_webhooks.py`:

1. **3DS completado sin volver a la app:**
   - el anticipo queda `requiere_accion` y se llama a `completar_autenticacion(aprobada=True)`;
   - el webhook `cobro_capturado` registra el anticipo `capturado` y el pedido `anticipo_pagado`, sin que nadie llame a `verificar`;
   - queda una fila de ledger.
2. **El mismo evento dos veces:** la segunda respuesta es `repetido`, hay una sola fila en `eventos_pasarela` y `consultar_cobro` se llamó una sola vez.
3. **Firma inválida:** 401, sin fila en `eventos_pasarela` y sin llamar a la pasarela.
4. **El webhook dice `capturado` pero la pasarela dice `requiere_accion`:** no se registra nada y el resultado es `SIN_CAMBIOS`.
5. **"La quiero" con el 3DS rechazado:** el webhook `cobro_fallido` deja el pedido `rechazado` y la obra libre.
6. **Referencia desconocida sin dinero:** procesado, con `error` que dice sin cobro. **Referencia desconocida con `metadatos.cobro_id` de un cobro existente y la foto `capturado`:** procesado como discrepancia.
7. **Discrepancia:** un cobro `capturado` en la base y reembolsado en la pasarela por fuera, con un `reembolsar` directo a la falsa. El webhook lo marca discrepancia y el cobro no cambia.
8. **Falla al procesar:** con `programar_falla("consultar_cobro", ...)`, la respuesta es 200, el evento queda sin `procesado_en` con `intentos` 1 y el tipo de la excepción en `error`. `barrer` con `ahora` un minuto después lo procesa.
9. **Intentos agotados:** con 5 intentos, `barrer` no lo toma más y aparece en `GET /moderacion/pagos/eventos`.
10. **Moderación:** `GET /moderacion/pagos/eventos` responde 403 a quien no es admin. La respuesta de admin no trae `payload`, `evento_externo_id` ni la referencia.
11. **Evento de tipo desconocido o sin referencia:** procesado sin acción y sin llamar a la pasarela.

`tests/test_webhooks.py`, con el adaptador de ONVO: `PasarelaOnvo` con el `Simulador` de `tests/test_pasarela_onvo.py` como transporte, sobrescribiendo `get_pasarela`. El cobro de la base lleva una referencia `pi_...` puesta directo en la base.

24. **Evento de ONVO de punta a punta:** el cuerpo es `{"type": "payment-intent.succeeded", "data": {"id": "pi_...", "updatedAt": "..."}}`, con el encabezado `X-Webhook-Secret`. El simulador responde a `GET /v1/payment-intents/pi_...` con `succeeded` y el monto en céntimos. El anticipo queda `capturado` y hay una sola solicitud `GET` al simulador.
25. **Sin secreto o con el secreto equivocado:**
    - con el secreto equivocado, 401;
    - con `ONVO_WEBHOOK_SECRET` sin configurar, 503;
    - en ninguno de los dos casos se guarda el evento.
26. **Monto distinto (P4):** si ONVO informa un monto distinto del cobro, no se registra nada y el evento queda con error.

`tests/test_webhooks.py`, también:

27. **Barrido como respaldo:** un saldo de encargo con el 3DS completado en la falsa, sin webhook y sin `verificar`. `barrer` con `ahora` 31 minutos después lo deja `autorizado` y el pedido en `vista_previa_entregada`. Con `ahora` 10 minutos después no hace nada.
28. **Solo consulta:** al procesar cualquier webhook de este archivo, la pasarela recibe únicamente `consultar_cobro`. Verificalo espiando las operaciones de dinero, como `espiar` en `tests/test_cobros_api.py`.
29. **Tiempo máximo:** con una pasarela cuya `consultar_cobro` tarda más que el límite (parcheá la constante a un valor chico), la respuesta es 200, el evento queda sin procesar con `intentos` 1 y el pedido sin cambios.

`tests/test_ledger.py`:

12. **Encargo completo:** dos filas de captura (anticipo y saldo), con `tarifa_artistica` según la tarifa del pedido y los otros dos montos nulos. La suma de `monto_bruto` es igual al total del pedido.
13. **Evento cancelado por el cliente con el 50%:** una fila de reembolso por la mitad de lo capturado.
14. **Obra despachada:** una fila de captura. **Disputa resuelta con captura del saldo y reembolso parcial del anticipo:** las dos filas.
15. **Ningún hecho sin dinero se asienta:** una autorización, una liberación o un vencimiento no agregan filas.
16. **Dos filas con la misma clave:** la segunda viola `uq_ledger_entries_clave`.

`tests/test_dt28.py`:

17. **Reembolso hecho por un intento anterior que no se registró:** antes de resolver, se llama a `reembolsar` directo en la falsa con el mismo monto. Al resolver no hay una llamada nueva de reembolso, el total reembolsado en la falsa es `m` y el cobro queda con `m` registrado.
18. **Reintento con un monto mayor:** primero se reembolsó 3,000 directo y después se resuelve con 5,000. Hay una sola llamada de reembolso, por 2,000, y la falsa termina con 5,000.
19. **Reintento con un monto menor que lo ya devuelto:** 409, sin llamadas de dinero y sin cambios en la base.
20. **Resolver como cancelado un saldo que la pasarela ya capturó:** 409, nunca 502, sin llamadas de dinero.
21. **Captura ya hecha:** resolver como completado un saldo ya capturado en la falsa no vuelve a capturar y registra el pedido `completado`.
22. **Cancelación del cliente con un reembolso ya hecho por un intento anterior:** no reembolsa dos veces.
23. **La clave de reembolso** es `reembolsar-{cobro}-{hasta}` y cambia entre el escenario 17 y el 18.

## Paso 0: crear la rama
Antes de tocar cualquier archivo:

    git switch develop
    git pull --ff-only
    git switch -c feat/lote-09b-webhooks-conciliacion

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

En el árbol de trabajo vas a ver `orquestacion/BITACORA.md` modificado y dos prompts en `orquestacion/`. Son del orquestador: no los toques ni los commitees.

Al terminar, commiteá en esa rama **solo los archivos del alcance**, en commits convencionales con sentido por sí solos. Por ejemplo:

1. migración y ledger;
2. DT28;
3. webhooks y conciliación.

Los mensajes no llevan líneas `Co-Authored-By` ni mencionan herramientas de asistencia. No hagas push ni abras PR.

## Cómo entregar
Pegá la salida de `git diff --stat develop...HEAD`, la lista de archivos y la salida literal de cada criterio de aceptación. Al final, una sección de observaciones con cualquier desvío y su razón. Si algo del prompt te parece equivocado, hacelo igual y anotá la objeción en observaciones.

## Estilo
No usar guiones largos ni guiones medios en comentarios ni documentación.
Explicaciones breves; se prefiere código correcto a párrafos.
Identificadores en español, como el resto del dominio; comentarios en español.
