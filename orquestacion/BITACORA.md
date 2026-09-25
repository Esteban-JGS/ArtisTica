# Bitácora de lotes: backend de ArtísTica

Un archivo por proyecto. Se actualiza después de cada validación.
Veredictos posibles: Aprobado, Aprobado con deuda, Rechazado.

## Decisiones de rumbo tomadas

| # | Decisión | Fecha |
|---|---|---|
| D1 | `consulta` es entidad propia, no estado del pedido. La máquina del pedido arranca en `cotizado`. Obra disponible crea la consulta automáticamente en estado `convertida` | 2026-09-23 |
| D2 | `mobile/` es todo el frontend y está fuera de alcance de todo lote. La app consume la API de FastAPI y nunca lee tablas con la anon key | 2026-09-23 |
| D3 | La pasarela de pagos vive detrás de un contrato abstracto. ONVO es el primer adaptador; existe un adaptador falso para pruebas y demo. Las incógnitas de la pasarela son capacidades declaradas, no constantes en el código | 2026-09-23 |
| D4 | Recorte de alcance para noviembre 2026: boosts fuera del MVP, IA y métricas reducidas, webhooks completos sin recorte | 2026-09-23 |

## Estado de los lotes

| # | Título | Estado | Veredicto | Deuda |
|---|---|---|---|---|
| 0 | Saneamiento: que el proyecto arranque | Cerrado | Aprobado con deuda | D1 a D4 |
| 1 | Esquema de dominio y migración única de reemplazo | Cerrado | Aprobado con deuda | D5 a D7 |
| 1b | Cerrar los huecos del esquema | Cerrado | Aprobado | Ninguna |
| 2 | Máquina de estados de pedidos y cobros | Pendiente. Incluye el indice unico parcial sobre `pedidos(obra_id)` para obra disponible, observacion 5 del lote 1b | | |
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

| Origen | Deuda | Cuando se paga |
|---|---|---|
| Lote 0 | La politica de lint quedo en un conjunto acotado de reglas. Ampliarla obligaria a reescribir codigo existente, asi que se revisa cuando el esquema nuevo este puesto | Despues del lote 1 |
| Lote 0 | El prompt original pedia correr `ruff check --fix` y a la vez no tocar archivos fuera del alcance. Con una version de ruff mas nueva esas dos instrucciones se contradicen. Los prompts siguientes fijan la politica de lint antes de pedir un `--fix` | Corregido en el addendum |
| Lote 0, D1 | `B904` silenciado con per-file-ignores en `src/api/deps.py` y `src/core/security.py`. Falta el `raise ... from` | Lote 4, que toca los dos archivos |
| Lote 0, D2 | El worker solo depende de `db` en compose, asi que su primera consulta llega antes de que la API migre y loguea un `relation jobs does not exist`. El loop reintenta, pero ensucia el arranque | Lote 9, que toca el worker |
| Lote 0, D3 | `asyncio.set_event_loop_policy` queda obsoleto en Python 3.14. El reemplazo es `asyncio.run(..., loop_factory=...)` | Cuando se suba de version de Python |
| Lote 0, D4 | `docker-compose.yml` publica el 5432, que en la maquina de Esteban ya ocupa otro contenedor. Hoy se resuelve con un override local fuera del repositorio | Cuando estorbe |
| Lote 1, D5 | `src/models/operation.py` quedo como reexportacion de tres lineas hacia `operacion.py`, porque `workers/main.py` importa `Job` desde ahi y estaba prohibido tocarlo | Lote 9, que toca el worker |
| Lote 1, D6 | Los valores por defecto se asignan en Python y no con `server_default`. Un insert por SQL crudo tiene que darlos explicitos | Sin fecha. Bajo impacto mientras todo pase por SQLAlchemy |
| Lote 1, D7 | `reportes` y `moderation_actions` conservan nombres de columna en ingles y sin llave foranea en `reporter_id` y `admin_id` | Lote 11, que toca moderacion |
| Orquestador | El criterio de aceptacion que buscaba columnas de saldo con `grep` sobre el codigo era erroneo: los valores de enum del dominio contienen esas palabras de forma legitima. Se reemplaza por una consulta a `information_schema.columns` | Corregido desde el lote 1b |

## Preguntas abiertas que bloquean diseño

| # | Pregunta | Bloquea | Estado |
|---|---|---|---|
| 1 | Porcentaje del anticipo: fijo o elegible por el artista entre 30 y 50 | Lote 2 | Abierta |
| 2 | Ventana para abrir una disputa, en días | Lote 2 | Abierta |
| 3 | Política de cancelación de eventos, en días y porcentajes | Lote 2 | Abierta |
| 4 | Duración de una autorización antes de vencer (pasarela) | Lote 3, mitigada por D3 | Abierta |
| 5 | Si el modo marketplace acepta SINPE Móvil (pasarela) | Lote 3, mitigada por D3 | Abierta |
| 6 | Si la comisión se define por cobro o solo por cuenta (pasarela) | Lote 3, mitigada por D3 | Abierta |
| 7 | Quién absorbe contracargos y reembolsos después de liquidar (pasarela) | Lote 9, mitigada por D3 | Abierta |
| 8 | Si una persona física sin actividad inscrita puede completar el onboarding | Lote 4 | Abierta |
