# Bitácora de lotes: backend de ArtísTica

Un archivo por proyecto. Se actualiza después de cada validación.
Veredictos posibles: Aprobado, Aprobado con deuda, Rechazado.
Las decisiones se numeran D y las deudas técnicas DT.

## Decisiones de rumbo tomadas

| # | Decisión | Fecha |
|---|---|---|
| D1 | `consulta` es entidad propia, no estado del pedido. La máquina del pedido arranca en `cotizado`. Obra disponible crea la consulta automáticamente en estado `convertida` | 2026-09-23 |
| D2 | `mobile/` es todo el frontend y está fuera de alcance de todo lote. La app consume la API de FastAPI y nunca lee tablas con la anon key | 2026-09-23 |
| D3 | La pasarela de pagos vive detrás de un contrato abstracto. ONVO es el primer adaptador; existe un adaptador falso para pruebas y demo. Las incógnitas de la pasarela son capacidades declaradas, no constantes en el código | 2026-09-23 |
| D4 | Recorte de alcance para noviembre 2026: boosts fuera del MVP, IA y métricas reducidas, webhooks completos sin recorte | 2026-09-23 |
| D5 | Políticas de pedido por defecto, todas como configuración que se cambia sin tocar código. Ver la tabla de políticas abajo | 2026-09-24 |
| D6 | Todo entra por rama y pull request hacia `develop`, fusionado con merge commit, que conserva los commits de la rama y deja que `develop` local se alinee con un `git pull`. Un lote, una rama. El merge es siempre humano. Detalle en `AGENTS.md` | 2026-09-24 |
| D7 | Salidas por vencimiento de los pedidos. Resuelven las preguntas 9 y 10. Ver las dos últimas filas de la tabla de políticas | 2026-09-25 |
| D8 | Cambio de plan y tarifa. Resuelve la pregunta 11. Ver la tabla de políticas | 2026-10-02 |
| D9 | Vigencia supuesta de una autorización: 5 días, configurable. Resuelve la pregunta 12 y la mitad de DT12 | 2026-10-02 |
| D10 | El onboarding de la pasarela se exige solo al primer cobro: sin cuenta conectada, el artista exhibe, recibe consultas y cotiza. `is_verified` es verdadero si y solo si el onboarding está completado. Mitiga la pregunta 8 sin cerrarla | 2026-10-02 |
| D11 | En el MVP, Estudio es una bandera sin cobro real y el artista cambia de plan solo. Bajar a Taller con más servicios u obras que el límite no oculta ni borra nada: solo impide crear nuevos hasta quedar por debajo. El bloqueo por artista de D8 es la fila de `profiles` con `SELECT ... FOR UPDATE` | 2026-10-02 |
| D12 | Medios del MVP: solo imágenes JPEG, PNG y WebP de hasta 5 MB; el video queda fuera. El bucket `medios` es público para lectura y solo se escribe con una URL firmada que emite la API, con una ruta que arma el servidor. Un medio existe recién cuando la API confirma la subida. Los entregables de pedidos irán a un bucket privado | 2026-10-04 |
| D13 | Desde el lote 5 las migraciones se encadenan. La migración inicial ya está aplicada en bases de prueba y no se reescribe más | 2026-10-04 |
| D14 | El lote 5 se divide: el 5 hace la capa de almacenamiento y los medios, y el 5b las obras y los servicios con los límites del plan Taller. La creación de publicaciones pasa al lote 6 y el handler de miniaturas al lote 11, junto con los demás trabajos del worker | 2026-10-04 |

## Políticas de pedido vigentes (D5)

| Política | Valor por defecto |
|---|---|
| Anticipo de encargo y evento | El artista lo elige entre 30% y 50% en cada cotización. Si no elige, 50% |
| Ventana de disputa | 7 días desde la entrega. Para eventos, desde la fecha del evento. Si nadie abre disputa, el pedido se completa solo |
| Cancelación de evento por el cliente | Más de 30 días de anticipación: se devuelve el 100% de lo cobrado. De 7 a 30 días: 50%. Menos de 7 días: nada |
| Cancelación de encargo por el cliente | Antes del anticipo, sin costo. Después, el anticipo no se devuelve |
| Cancelación o incumplimiento del artista | Se devuelve el 100% de lo cobrado, en cualquier tipo de pedido |
| Anticipo en una disputa | Moderación puede ordenar su devolución total o parcial. Resuelve la errata C4: el anticipo no se devuelve cuando el cliente cancela por su cuenta, pero sí cuando el artista incumple, y la disputa es justamente como se establece un incumplimiento |
| Monto mínimo por pedido | ₡2,500 |
| Evento cuya fecha llega con el saldo impago (D7) | Cuenta como cancelación del cliente con menos de 7 días: el anticipo no se devuelve y el pedido pasa a `cancelado` |
| Autorización del saldo de un encargo que vence antes de la aprobación (D7) | El cliente puede volver a autorizar el mismo cobro. Si no lo hace en 7 días desde el vencimiento, el artista puede abrir una disputa |
| Cambio de plan (D8) | El plan cambia de inmediato. Cada pedido conserva la tarifa del plan vigente cuando se creó: si un artista sube de Taller a Estudio, sus pedidos abiertos siguen al 8% y los que se crean después ya van al 5%. Cuando no le quedan pedidos abiertos al 8%, todo queda al 5%. Bajar de plan funciona igual en sentido contrario |
| Tarifa en la pasarela (D8) | ONVO tiene una sola tarifa por cuenta. Si el artista no tiene pedidos abiertos con tarifas distintas, la cuenta queda fija en la tarifa de su plan. Si los tiene, el backend fija la tarifa de la cuenta a la del pedido justo antes de cada operación que mueve dinero, con un bloqueo por artista para que dos cobros no se crucen. Si ONVO confirma comisión por cobro, se usa eso y el ajuste desaparece |
| Vigencia supuesta de una autorización (D9) | 5 días, en `DIAS_VIGENCIA_AUTORIZACION_SUPUESTA`. Solo se usa cuando la pasarela declara la vigencia como desconocida. Se reemplaza por el valor real cuando ONVO lo confirme |

## Estado de los lotes

| # | Título | Estado | Veredicto | Deuda |
|---|---|---|---|---|
| 0 | Saneamiento: que el proyecto arranque | Cerrado | Aprobado con deuda | DT1 a DT4 |
| 1 | Esquema de dominio y migración única de reemplazo | Cerrado | Aprobado con deuda | DT5 a DT7 |
| 1b | Cerrar los huecos del esquema | Cerrado | Aprobado | Ninguna |
| 2 | Máquina de estados de pedidos y cobros | Cerrado | Aprobado con deuda | DT9, DT10 |
| 3 | Capa de pasarela: contrato, adaptador real y adaptador falso | Cerrado | Aprobado con deuda | DT11 a DT15 |
| 4 | Identidad, roles, planes y onboarding | Cerrado | Aprobado con deuda | DT16 a DT18 |
| 5 | Almacenamiento y medios con subida firmada | Cerrado | Aprobado con deuda | DT19, DT20 |
| 5b | Obras y servicios con límites de plan | Pendiente | | |
| 6 | Publicaciones, feed Seguidos y Explorar por cursor | Pendiente | | |
| 7 | Consultas y chat | Pendiente | | |
| 8 | Endpoints de pedidos y cobros | Pendiente | | |
| 9 | Webhooks idempotentes y vigilancia de autorizaciones | Pendiente | | |
| 10 | Métricas: post_views y panel | Pendiente | | |
| 11 | Moderación, reportes y jobs del worker (miniaturas y clasificación) | Pendiente | | |

## Entregas del curso

| Avance | Fecha | Contenido | Archivo |
|---|---|---|---|
| I Avance | Septiembre 2026 | Propuesta técnica y de diseño: stack y pantallas | `mobile/docs/Artistica_Propuesta.docx` |
| II Avance | 9 de octubre de 2026 | Propuesta, distribución, generación de dinero, situaciones presentadas y avance de desarrollo | `docs/entregas/ArtisTica_II_Avance.docx`, generado desde `docs/ArtisTica_Documentacion_Oficial.md` |

## Deuda acumulada

| # | Origen | Deuda | Cuándo se paga |
|---|---|---|---|
| DT1 | Lote 0 | `B904` silenciado con per-file-ignores en `src/api/deps.py` y `src/core/security.py`. Falta el `raise ... from` | Pagada en el lote 4 |
| DT2 | Lote 0 | El worker solo depende de `db` en compose, así que su primera consulta llega antes de que la API migre y loguea un `relation jobs does not exist`. El loop reintenta, pero ensucia el arranque | Lote 9, que toca el worker |
| DT3 | Lote 0 | `asyncio.set_event_loop_policy` queda obsoleto en Python 3.14. El reemplazo es `asyncio.run(..., loop_factory=...)` | Cuando se suba de versión de Python |
| DT4 | Lote 0 | `docker-compose.yml` publica el 5432, que en la máquina de Esteban ya ocupa otro contenedor. Hoy se resuelve con un override local fuera del repositorio | Cuando estorbe |
| DT5 | Lote 1 | `src/models/operation.py` quedó como reexportación de tres líneas hacia `operacion.py`, porque `workers/main.py` importa `Job` desde ahí | Lote 9, que toca el worker |
| DT6 | Lote 1 | Los valores por defecto se asignan en Python y no con `server_default`. Un insert por SQL crudo tiene que darlos explícitos | Sin fecha. Bajo impacto mientras todo pase por SQLAlchemy |
| DT7 | Lote 1 | `reportes` y `moderation_actions` conservan nombres de columna en inglés y sin llave foránea en `reporter_id` y `admin_id` | Lote 11, que toca moderación |
| DT8 | Lote 0 | La política de lint quedó en un conjunto acotado de reglas. Se revisa cuando haya código de dominio suficiente para juzgarla | Después del lote 8 |
| DT9 | Lote 2 | El dominio importa los enums desde `src.models`. Pasa el grep de pureza, pero en ejecución carga SQLAlchemy. Hay que mover los enums a un módulo neutro | Lote 8 |
| DT10 | Lote 2 | Faltan tres salidas por paso del tiempo: evento cuya fecha llega con el saldo impago, que queda trabado en `anticipo_pagado`; encargo cuya autorización del saldo vence en `vista_previa_entregada`, sin forma de reautorizar; y obra disponible cuya autorización vence en `en_proceso`, que está en la tabla pero sin función en el servicio | Lote 9, que vigila vencimientos. Reglas decididas en D7 |
| DT11 | Lote 3 | ONVO no firma el cuerpo de los webhooks: manda el secreto tal cual en `X-Webhook-Secret`. El secreto prueba el origen, no la integridad. Regla para el lote 9: nunca mover dinero por un webhook solo; antes, consultar la intención a la pasarela. El contrato no tiene todavía una operación de consulta de cobro | Lote 9 |
| DT12 | Lote 3 | ONVO no informa cuánto dura una autorización, así que `autorizado_hasta` vuelve nulo, pero el servicio del lote 2 exige una fecha. El valor quedó decidido en D9: 5 días | Lote 8 |
| DT13 | Lote 3 | 3DS no está cubierto: un pago en `requires_action` levanta `OperacionNoSoportada` | Antes de producción |
| DT14 | Lote 3 | Nada impide usar la pasarela falsa en producción. La fábrica debería negarse cuando `ENVIRONMENT` sea producción | Antes de producción |
| DT15 | Lote 3 | La pasarela falsa guarda su estado en memoria, una instancia por proceso. La demo tiene que correr con un solo worker de uvicorn | Antes de la demo |
| DT16 | Lote 4 | Por D11, cualquier artista pasa a Estudio sin pagar y su tarifa baja de 8% a 5%. Sirve para la demo; en producción vacía la tarifa | Antes de producción: el cambio a Estudio queda atado al cobro real o a una asignación de admin |
| DT17 | Lote 4 | Si la pasarela crea la cuenta conectada y después falla el commit, la cuenta queda huérfana y el siguiente intento crea otra. `crear_cuenta_conectada` no recibe clave de idempotencia ni metadatos | Lote 8, que vuelve a tocar el contrato de pagos |
| DT18 | Lote 4 | Las llamadas a la pasarela se hacen con el `FOR UPDATE` del perfil tomado (D8). Con Supavisor en modo transacción, una pasarela lenta retiene una conexión del pool hasta el timeout de 15 s | Revisar con carga antes de producción |
| DT19 | Lote 5 | Los medios que nunca se confirman, o cuya confirmación se rechazó, quedan como filas pendientes y cuentan para el límite de 20. Nada los limpia. Además el límite se cuenta sin bloqueo, así que dos solicitudes simultáneas pueden pasarlo por una | Lote 11: job que borra pendientes viejos, fila y objeto |
| DT20 | Lote 5 | El adaptador de Supabase Storage solo se probó con transporte simulado. Falta correrlo contra el proyecto real: `python -m src.storage.supabase` para crear el bucket, una subida firmada de punta a punta, y confirmar que la firma dura 2 horas y que las claves nuevas de Supabase (`sb_secret_...`) funcionan en `apikey` y `Authorization` | Antes de la demo, con el proyecto de Supabase de desarrollo |

## Errores del orquestador

| Lote | Error | Corrección |
|---|---|---|
| 0 | El prompt pedía correr `ruff check --fix` y a la vez no tocar archivos fuera del alcance. Con una versión de ruff más nueva, esas dos instrucciones se contradicen | Addendum del lote 0. Los prompts fijan la política de lint antes de pedir un `--fix` |
| 1 | El criterio que buscaba columnas de saldo con `grep` sobre el código era erróneo: los valores de enum del dominio contienen esas palabras de forma legítima | Desde el lote 1b se usa una consulta a `information_schema.columns` |
| 1 | La especificación del esquema no cubría entregables, disputas, obra vendida ni índices de llaves foráneas | Lote 1b |
| 1b | Se pidió el índice de `follows.seguido_id` sin listar `users.py`, que es donde vive `Follow` | Aceptado el cambio fuera de alcance |
| 2 | El plan de cancelación solo preveía liberar, reembolsar y conservar. Faltaban cancelar un cobro que nunca llegó a la pasarela, y capturar un saldo autorizado cuando moderación resuelve a favor del artista. Tampoco se previeron las salidas por vencimiento de DT10 | El ejecutor agregó las dos acciones; DT10 queda para el lote 9 |
| 3 | La tabla de errores marcaba `PasarelaNoDisponible` siempre como reintentable. Con una pasarela sin idempotencia, reintentar una confirmación o un reembolso tras un timeout cobraría o devolvería dos veces | El ejecutor lo marcó reintentable solo cuando la operación se puede repetir sin efecto doble |
| 0 | La auditoría dio `src/core/security.py` por bueno para rescatar tal cual. Tenía la URL del JWKS equivocada (`/auth/v1/jwks` en vez de `/auth/v1/.well-known/jwks.json`) y solo aceptaba `RS256`, cuando Supabase firma con `ES256` o `RS256`: la autenticación nunca habría funcionado contra un proyecto real | Lote 4 corrige los dos defectos y lo prueba con tokens firmados en la prueba |
| 4 | El criterio que listaba rutas con `app.routes` falla en FastAPI 0.141, donde `include_router` deja un `_IncludedRouter` sin `path` | Se verifica con `app.openapi()["paths"]`, que no depende de la estructura interna |

## Preguntas abiertas que bloquean diseño

| # | Pregunta | Bloquea | Estado |
|---|---|---|---|
| 1 | Porcentaje del anticipo | Lote 2 | Cerrada por D5 |
| 2 | Ventana para abrir una disputa | Lote 2 | Cerrada por D5 |
| 3 | Política de cancelación de eventos | Lote 2 | Cerrada por D5 |
| 4 | Duración de una autorización antes de vencer (pasarela) | Lote 3, mitigada por D3 | Abierta |
| 5 | Si el modo marketplace acepta SINPE Móvil (pasarela) | Lote 3, mitigada por D3 | Abierta |
| 6 | Si la comisión se define por cobro o solo por cuenta (pasarela) | Lote 3, mitigada por D3 | Abierta |
| 7 | Quién absorbe contracargos y reembolsos después de liquidar (pasarela) | Lote 9, mitigada por D3 | Abierta |
| 8 | Si una persona física sin actividad inscrita puede completar el onboarding | Lote 4, mitigada por D10 | Abierta |
| 9 | Evento cuya fecha llega con el saldo impago. Propuesta: se trata como cancelación del cliente con menos de 7 días, así que el anticipo no se devuelve y el pedido pasa a `cancelado` | Lote 9 | Cerrada por D7 |
| 10 | Encargo cuya autorización del saldo vence antes de que el cliente apruebe. Propuesta: se permite reautorizar el mismo cobro; si el cliente no reautoriza en 7 días, el artista puede abrir disputa | Lote 9 | Cerrada por D7 |
| 11 | Con ONVO la tarifa es de la cuenta del artista, no del cobro. Si el artista cambia de plan con pedidos abiertos, sus saldos se cobrarían con la tarifa nueva, aunque el lote 2 la congela por pedido. Propuesta: el cambio de tarifa en la cuenta se aplica recién cuando el artista no tiene cobros autorizados ni pendientes; mientras tanto el plan cambia en ArtísTica pero la cuenta conserva la tarifa vieja | Lote 4 | Cerrada por D8 |
| 12 | Vigencia supuesta de una autorización cuando la pasarela no la informa. Propuesta: 5 días, configurable, y se reemplaza por el valor real cuando ONVO lo confirme | Lote 8 | Cerrada por D9 |
| 13 | Para cobrar, ONVO exige un medio de pago tokenizado en la app con la clave publicable. La tarjeta nunca pasa por nuestra API, que es lo correcto, pero obliga a coordinar con la app móvil | Lote 8 y `mobile/` | Abierta, coordinar con Brian |
