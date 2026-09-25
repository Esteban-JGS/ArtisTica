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

## Estado de los lotes

| # | Título | Estado | Veredicto | Deuda |
|---|---|---|---|---|
| 0 | Saneamiento: que el proyecto arranque | Cerrado | Aprobado con deuda | DT1 a DT4 |
| 1 | Esquema de dominio y migración única de reemplazo | Cerrado | Aprobado con deuda | DT5 a DT7 |
| 1b | Cerrar los huecos del esquema | Cerrado | Aprobado | Ninguna |
| 2 | Máquina de estados de pedidos y cobros | Cerrado | Aprobado con deuda | DT9, DT10 |
| 3 | Capa de pasarela: contrato, adaptador real y adaptador falso | Pendiente | | |
| 4 | Identidad, roles, planes y onboarding | Pendiente | | |
| 5 | Obras, servicios y medios con Storage firmado | Pendiente | | |
| 6 | Feed Seguidos y Explorar por cursor | Pendiente | | |
| 7 | Consultas y chat | Pendiente | | |
| 8 | Endpoints de pedidos y cobros | Pendiente | | |
| 9 | Webhooks idempotentes y vigilancia de autorizaciones | Pendiente | | |
| 10 | Métricas: post_views y panel | Pendiente | | |
| 11 | Moderación, reportes y jobs de clasificación | Pendiente | | |

## Deuda acumulada

| # | Origen | Deuda | Cuándo se paga |
|---|---|---|---|
| DT1 | Lote 0 | `B904` silenciado con per-file-ignores en `src/api/deps.py` y `src/core/security.py`. Falta el `raise ... from` | Lote 4, que toca los dos archivos |
| DT2 | Lote 0 | El worker solo depende de `db` en compose, así que su primera consulta llega antes de que la API migre y loguea un `relation jobs does not exist`. El loop reintenta, pero ensucia el arranque | Lote 9, que toca el worker |
| DT3 | Lote 0 | `asyncio.set_event_loop_policy` queda obsoleto en Python 3.14. El reemplazo es `asyncio.run(..., loop_factory=...)` | Cuando se suba de versión de Python |
| DT4 | Lote 0 | `docker-compose.yml` publica el 5432, que en la máquina de Esteban ya ocupa otro contenedor. Hoy se resuelve con un override local fuera del repositorio | Cuando estorbe |
| DT5 | Lote 1 | `src/models/operation.py` quedó como reexportación de tres líneas hacia `operacion.py`, porque `workers/main.py` importa `Job` desde ahí | Lote 9, que toca el worker |
| DT6 | Lote 1 | Los valores por defecto se asignan en Python y no con `server_default`. Un insert por SQL crudo tiene que darlos explícitos | Sin fecha. Bajo impacto mientras todo pase por SQLAlchemy |
| DT7 | Lote 1 | `reportes` y `moderation_actions` conservan nombres de columna en inglés y sin llave foránea en `reporter_id` y `admin_id` | Lote 11, que toca moderación |
| DT8 | Lote 0 | La política de lint quedó en un conjunto acotado de reglas. Se revisa cuando haya código de dominio suficiente para juzgarla | Después del lote 8 |
| DT9 | Lote 2 | El dominio importa los enums desde `src.models`. Pasa el grep de pureza, pero en ejecución carga SQLAlchemy. Hay que mover los enums a un módulo neutro | Lote 8 |
| DT10 | Lote 2 | Faltan tres salidas por paso del tiempo: evento cuya fecha llega con el saldo impago, que queda trabado en `anticipo_pagado`; encargo cuya autorización del saldo vence en `vista_previa_entregada`, sin forma de reautorizar; y obra disponible cuya autorización vence en `en_proceso`, que está en la tabla pero sin función en el servicio | Lote 9, que vigila vencimientos. Dependen de las preguntas 9 y 10 |

## Errores del orquestador

| Lote | Error | Corrección |
|---|---|---|
| 0 | El prompt pedía correr `ruff check --fix` y a la vez no tocar archivos fuera del alcance. Con una versión de ruff más nueva, esas dos instrucciones se contradicen | Addendum del lote 0. Los prompts fijan la política de lint antes de pedir un `--fix` |
| 1 | El criterio que buscaba columnas de saldo con `grep` sobre el código era erróneo: los valores de enum del dominio contienen esas palabras de forma legítima | Desde el lote 1b se usa una consulta a `information_schema.columns` |
| 1 | La especificación del esquema no cubría entregables, disputas, obra vendida ni índices de llaves foráneas | Lote 1b |
| 1b | Se pidió el índice de `follows.seguido_id` sin listar `users.py`, que es donde vive `Follow` | Aceptado el cambio fuera de alcance |
| 2 | El plan de cancelación solo preveía liberar, reembolsar y conservar. Faltaban cancelar un cobro que nunca llegó a la pasarela, y capturar un saldo autorizado cuando moderación resuelve a favor del artista. Tampoco se previeron las salidas por vencimiento de DT10 | El ejecutor agregó las dos acciones; DT10 queda para el lote 9 |

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
| 8 | Si una persona física sin actividad inscrita puede completar el onboarding | Lote 4 | Abierta |
| 9 | Evento cuya fecha llega con el saldo impago. Propuesta: se trata como cancelación del cliente con menos de 7 días, así que el anticipo no se devuelve y el pedido pasa a `cancelado` | Lote 9 | Abierta, con propuesta |
| 10 | Encargo cuya autorización del saldo vence antes de que el cliente apruebe. Propuesta: se permite reautorizar el mismo cobro; si el cliente no reautoriza en 7 días, el artista puede abrir disputa | Lote 9 | Abierta, con propuesta |
