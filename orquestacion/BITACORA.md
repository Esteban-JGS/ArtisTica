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
| 0 | Saneamiento: que el proyecto arranque | Prompt generado | | |
| 1 | Esquema de dominio y migración única de reemplazo | Pendiente | | |
| 2 | Máquina de estados de pedidos y cobros | Pendiente | | |
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

Ninguna todavía.

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
