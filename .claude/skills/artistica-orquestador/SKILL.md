---
name: artistica-orquestador
description: Base de conocimiento y reglas de trabajo para la sesión orquestadora de ArtísTica. Define la idea de negocio, las decisiones técnicas fijas, las decisiones de rumbo tomadas, el estado real del repositorio, el plan de lotes, la plantilla obligatoria para generar prompts de ejecución, los criterios de esfuerzo y de modelo, y la lista de verificación para validar el trabajo devuelto por los agentes ejecutores.
---

# ArtísTica: manual del orquestador

Memoria permanente de la sesión orquestadora. Se lee completo al inicio de cada sesión y se vuelve a consultar antes de generar cada prompt.

Orden de autoridad: **Documento Maestro, después este manual, después el código existente.** El código existente nunca gana: se construyó con un modelo anterior. Si este manual contradice al Documento Maestro, gana el Maestro y hay que corregir este archivo, salvo en las decisiones de la sección 3, que son correcciones acordadas al propio Maestro.

La bitácora vive en `orquestacion/BITACORA.md`. Se actualiza después de cada validación.

---

## 1. La idea en una página

**ArtísTica es donde en Costa Rica se contrata arte hecho por personas, con el pago protegido.**

El dolor: hoy contratar arte funciona con Instagram (vitrina sin transacción) más WhatsApp (negociación sin reglas) más SINPE Móvil (pago sin protección). El cliente teme perder el adelanto; el artista teme no cobrar el saldo.

### Principios innegociables

1. Solo arte hecho por personas. El clasificador marca para revisión humana; nunca banea solo.
2. El feed de Seguidos es cronológico y jamás lleva contenido promocionado.
3. Se vende la habilidad del artista, no inventario. No hay catálogo, stock ni reventa.
4. Las métricas miden respuesta real (consultas, conversión), no viralidad.
5. Nunca se cobra por publicar, abrir comisiones, recibir pedidos, la protección del pago ni la verificación.

### Modelo operativo

Comisiones abiertas, no marketplace. Un solo motor de pedidos con tres tipos:

| Tipo | Disparadores de cobro |
|---|---|
| **Encargo** | Anticipo al aceptar la cotización; saldo autorizado en la vista previa con marca de agua y capturado al aprobar |
| **Evento** | Anticipo al reservar la fecha; saldo antes del evento |
| **Obra disponible** | Cobro autorizado al confirmar y capturado al despachar con número de guía |

### Glosario obligatorio (nombres en código y en interfaz)

| Término | Significado | No usar |
|---|---|---|
| `encargo` | Trabajo hecho a pedido | "comisión" en este sentido |
| `tarifa de servicio` | Porcentaje que cobra ArtísTica | "comisión" en este sentido |
| `obra` | Pieza de la galería (exhibición o disponible) | "producto" |
| `publicacion` | Lo que aparece en el feed | "post de venta" |
| `servicio` | Paquete con precio del artista | "listado" |
| `consulta` | Hilo de conversación abierto por un cliente sobre un servicio u obra | "mensaje directo" |
| `pedido` | Transacción con tipo encargo, evento u obra_disponible | "orden de compra" |
| `cobro` | Cada hito de pago de un pedido | "transacción" |

### Roles y planes

- **Público:** gratis. Explora, sigue, comenta, consulta, contrata y compra. No publica.
- **Artista Taller:** gratis. Tarifa 8%. 2 servicios, 5 obras disponibles, métricas de 30 días.
- **Artista Estudio:** suscripción mensual. Tarifa 5%. Servicios y obras ilimitados, calendario sincronizado, plantillas de cotización, cupos, métricas completas, perfil personalizable, un boost mensual incluido, reporte de ingresos exportable.
- **Agrupación** (etapa posterior) y **Admin/Moderador**.

### Ingresos

Tarifa por pedido (principal), suscripción Estudio (secundaria), boosts por alcance de personas (menor). Los boosts no modifican la tarifa. Se garantiza alcance, nunca ventas.

---

## 2. Decisiones técnicas fijas

El stack no se cambia. Estas reglas son invariantes; ningún prompt puede pedir algo que las rompa.

| Área | Regla |
|---|---|
| Lenguaje y framework | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| Base de datos | Supabase PostgreSQL 15, SQLAlchemy 2.0 **async**, psycopg 3 async, Alembic |
| Async | Endpoints `async def` con `AsyncSession`. Nunca mezclar sesiones sincrónicas dentro de handlers async |
| Pooling | Supavisor: 6543 para la app, 5432 para migraciones. Engine con `prepare_threshold=None` |
| Seguridad de datos | RLS activo **sin políticas permisivas** en todas las tablas. El backend entra con `service_role`. Toda la autorización vive en FastAPI. La `service_role` key nunca llega al cliente |
| Autenticación | Supabase Auth. El backend solo verifica el JWT contra el JWKS con `PyJWKClient` (firma, `exp`, `aud`, `iss`), claves en caché. Nunca con secreto compartido |
| Archivos | Supabase Storage con signed upload URLs. El archivo nunca pasa por la API |
| Trabajos pesados | Tabla `jobs` en Postgres con `FOR UPDATE SKIP LOCKED`, worker aparte, reintentos con backoff y estado `dead` |
| Pagos | Detrás de un contrato abstracto (ver decisión D3). El adaptador real es ONVO Pay en modo marketplace: cuenta conectada por artista, tarifa configurada por cuenta conectada |
| Custodia | La pasarela custodia el dinero. ArtísTica **no** administra fondos de terceros. No existe saldo propio, retención propia ni payouts desde fondos nuestros |
| Ledger | Registro y conciliación de pedidos, cobros y liquidaciones. **Nunca** una columna de saldo mutable |
| Atomicidad | El estado del pedido y el estado del cobro cambian en la misma transacción de base de datos |
| Orden de bloqueos | El perfil se bloquea antes que la obra, el servicio o el pedido (D18). Al revés, dos transacciones se traban |
| Capas | `src/domain/` no importa SQLAlchemy ni FastAPI; `src/services/` no importa `src/api/` |
| Idempotencia | Todo webhook de pago se procesa una sola vez aunque llegue repetido |
| Chat | Toda conversación cliente-artista pertenece a una consulta. Entre artistas, mensajes libres. Público con público, no existe |
| Búsqueda y similitud | pgvector con índice HNSW (recomendación y detección de obra duplicada) y tsvector para texto |
| Métricas | `post_views` con una vista por usuario, obra y día, insertada de forma asíncrona. Todo en UTC, convertido a `America/Costa_Rica` al consultar |
| Paginación | Cursor en feed y listados. Nunca `OFFSET` grande |
| Medios | Redimensionado en el teléfono, miniaturas en el worker. El ancho de banda de Storage es el primer límite real |
| Frontend | **`mobile/` es todo el frontend y es territorio del desarrollador móvil. Ningún prompt lo toca.** Todo lote trabaja dentro de `backend/`, salvo los pocos archivos de raíz que un prompt liste de forma explícita |

---

## 3. Decisiones de rumbo tomadas

Estas cuatro son acuerdos posteriores al Documento Maestro. Donde contradicen al Maestro, el Maestro se corrige (ver `orquestacion/CORRECCIONES-DOCUMENTO-MAESTRO.md`).

### D1. `consulta` es entidad, no estado del pedido

El Maestro §2.4 la listaba como primer estado del pedido y §5.4 como tabla aparte. Gana entidad aparte, por tres razones:

1. Obra disponible no tiene consulta previa: "La quiero" crea el pedido sin negociación. Si `consulta` fuera un estado del pedido, uno de los tres tipos tendría que saltárselo y se rompe el motor único.
2. La métrica "conversión de consulta a encargo" exige que las consultas no convertidas sean filas contables. Meterlas en `pedidos` contamina toda métrica de dinero.
3. El hilo sobrevive aunque nunca haya cotización.

Forma concreta:

- `consultas`: `cliente_id`, `artista_id`, referencia opcional a servicio u obra, estado propio `abierta`, `cotizada`, `convertida`, `descartada`.
- `mensajes`: cuelga de `consulta_id`. Un solo mecanismo de chat en todo el sistema.
- `pedidos`: `consulta_id` obligatorio. Para obra disponible, "La quiero" crea la consulta automáticamente en estado `convertida`.
- Máquina del pedido: `cotizado → anticipo_pagado → en_proceso → vista_previa_entregada → saldo_pagado → completado`, más `rechazado`, `cancelado` y `en_disputa`. Toda transición no contemplada levanta error.

### D2. `mobile/` es todo el frontend

El Maestro §5.1 y la versión previa de este manual decían `/app`. En el disco el frontend es `mobile/`, y `/app` es además el `WORKDIR` de los Dockerfile del backend. La app consume la API de FastAPI y nunca lee tablas con la anon key, que es lo único compatible con RLS deny all.

### D3. La pasarela vive detrás de un contrato abstracto

Nada fuera de `backend/src/payments/` sabe que existe ONVO.

| Elemento | Forma |
|---|---|
| Contrato | `PasarelaDePagos` con `crear_cuenta_conectada`, `autorizar`, `capturar`, `cancelar_autorizacion`, `reembolsar`, `parsear_webhook` |
| Adaptadores | Uno real y uno falso en memoria, para pruebas y para la demo |
| Incógnitas | No se hardcodean. Van como capacidades declaradas del adaptador: `dias_vigencia_autorizacion`, `soporta_sinpe`, `comision_por_cobro`, `revierte_comision_en_reembolso` |

Consecuencia: las respuestas pendientes de la pasarela cambian configuración o, a lo sumo, un adaptador. Nunca el modelo de datos ni la máquina de estados.

### D4. Recorte de alcance para la entrega de noviembre de 2026

| Parte | Decisión |
|---|---|
| Boosts | Fuera del MVP. El propio Maestro dice que es lo primero que se recorta |
| Clasificación por IA | Reducida: handler real con proveedor conectable, clasificador simple para la demo. La detección de duplicados por pgvector sí entra |
| Métricas | Reducidas: `post_views` y consultas del panel entran. La vista materializada se pospone |
| Webhooks idempotentes | Entran completos. No es recortable |

---

## 4. Estado real del repositorio (auditoría del 23 de septiembre de 2026)

El backend son 1271 líneas en 38 archivos, con **un solo commit**. Nunca se ejecutó. Los otros commits del repositorio son de `mobile/`.

### Qué se elimina

| Qué | Por qué |
|---|---|
| `src/models/commissions.py` completo | Máquina de un solo pago con `pagada_en_retencion` y `liberada`: escrow propio |
| `LedgerEntry` con debit/credit, `Payout`, `GET /profiles/me/balance` | Saldo mutable y desembolso desde fondos nuestros |
| `handlers/escrow.py` y el job `release_escrow` | Libera retención propia, que no existe |
| `SUPABASE_JWT_SECRET` y `DAYS_UNTIL_AUTO_RELEASE` en config | Config muerta que invita a errores conocidos |
| `tests/test_commissions.py` | Prueba una función definida dentro del propio test |
| La migración inicial entera | La base nunca se migró: se reemplaza el archivo en vez de encadenar ALTERs |

### Qué se rescata

| Qué | Condición |
|---|---|
| `src/core/security.py` | Tal cual. Es lo mejor hecho del repositorio |
| `src/workers/main.py` | Tal cual el loop. Solo cambian los handlers |
| `src/api/deps.py` | Con cambios: dependencias de rol y de plan |
| Dockerfile, Dockerfile.worker, compose, workflow | Con los arreglos del lote 0 |
| `Job`, `Report`, `ModerationAction`, `Follow`, `Comment`, `Reaction`, `MediaAsset` | Con renombrado al glosario |
| Índices HNSW y GIN | El SQL se reusa en la migración nueva |

### Qué no existe y hay que construir

`obras`, `servicios`, `consultas`, `pedidos` con tipo, `cobros` por hitos, `resenas`, `impulsos`, `post_views`, agrupaciones, rol Público, planes Taller y Estudio, cuenta conectada, y toda la integración de pagos.

---

## 5. Plan de lotes

| # | Título | Depende de | Paralelo | Esfuerzo |
|---|---|---|---|---|
| 0 | Saneamiento: que el proyecto arranque | Nada | No | Bajo |
| 1 | Esquema de dominio y migración única de reemplazo | 0 | No | Alto |
| 2 | Máquina de estados de pedidos y cobros | 1 | No | Alto |
| 3 | Capa de pasarela: contrato, adaptador real y falso | 1, 2 | No | Alto |
| 4 | Identidad, roles, planes y onboarding | 1, 3 | No | Medio |
| 5 | Almacenamiento y medios con subida firmada | 1, 4 | No | Medio |
| 5c | Deuda: infraestructura y configuración | 5 | No | Bajo |
| 5d | Deuda: esquema y enums | 5c | No | Alto |
| 5e | Deuda: contrato de pagos | 5d | No | Alto |
| 5f | Deuda: política de lint | 5e | No | Bajo |
| 5b | Obras y servicios con límites de plan | 5f | No | Medio |
| 6 | Publicaciones, feed Seguidos y Explorar por cursor | 5b | No | Medio |
| 6b | Seguir, contadores, comentarios, reacciones y búsqueda | 6 | No | Medio |
| 7 | Consultas y chat | 1, 4 | No | Medio |
| 8 | Endpoints de pedidos y cobros | 2, 3, 7 | No | Medio alto |
| 9 | Webhooks idempotentes y vigilancia de autorizaciones | 3, 8 | No | Alto |
| 10 | Métricas: `post_views` y panel | 1, 6 | Sí, con 11 | Medio |
| 11 | Moderación, reportes y jobs del worker (miniaturas y clasificación) | 1, 5 | Sí, con 10 | Medio |

Solo una pareja corre en paralelo: 10 con 11. Los lotes con endpoints comparten `router.py`, `deps.py` y `conftest.py`, así que van en serie.

---

## 6. Plantilla obligatoria de prompt de ejecución

Todo prompt usa esta estructura. Un prompt sin criterios de aceptación verificables no se entrega. Cada prompt es autocontenido: la sesión que lo recibe no tiene el Documento Maestro, ni el repositorio en su cabeza, ni la conversación del orquestador.

```markdown
# [Lote N] Título corto del trabajo

## Rol
Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto mínimo
[Cinco a diez líneas: qué es ArtísTica, qué parte del sistema se toca y por qué.
Solo lo necesario para este lote.]

## Estado actual del repositorio
[Qué existe hoy en los archivos que se van a tocar, con ruta y línea.
Si algo está mal, decir qué está mal y por qué.]

## Objetivo
[Una sola frase con el resultado esperado.]

## Alcance
Archivos que podés crear o modificar:
- ruta/uno.py
- ruta/dos.py

## Prohibido
- Tocar cualquier archivo fuera de la lista anterior.
- Tocar mobile/, que es de otra persona.
- Cambiar el stack o agregar librerías nuevas.
- Inventar funcionalidades que no estén en este prompt.
- [Invariantes relevantes al lote, copiadas de la sección 2.]

## Trabajo a realizar
1. [Paso concreto]

## Criterios de aceptación
- [ ] [Condición verificable con un comando, no subjetiva]
- [ ] `ruff check .` pasa sin errores.
- [ ] `pytest` pasa.

## Paso 0: crear la rama
Antes de tocar cualquier archivo:

    git switch develop
    git pull --ff-only
    git switch -c feat/lote-NN-descripcion

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y
avisá: no la sobrescribas.

Al terminar, commiteá en esa rama **solo los archivos del alcance**, con un
mensaje convencional (`tipo(backend): descripcion`). Los mensajes no llevan
lineas `Co-Authored-By` ni mencionan herramientas de asistencia. No commitees
nada de `orquestacion/`. No hagas push ni abras PR: eso lo hace el orquestador.

## Cómo entregar
Salida de `git diff --stat develop...HEAD`, lista de archivos tocados,
salida literal de cada comando de los criterios de aceptación, y una
sección de observaciones al final.
Si algo del prompt te parece equivocado, hacelo igual y anotá la objeción
en observaciones.

## Estilo
No usar guiones largos ni guiones medios en comentarios ni documentación.
Explicaciones breves; se prefiere código correcto a párrafos.
```

### Flujo de ramas por lote

1. Escribir el prompt en `orquestacion/` **sin commitearlo** y sin crear ninguna rama. Todo prompt empieza con el "Paso 0: crear la rama", con el nombre exacto que sigue el estándar: `feat/lote-NN-descripcion`, o `fix/lote-NN-descripcion` para un correctivo que no cabe en la rama original.
2. La sesión ejecutora crea la rama desde `develop` actualizado, trabaja y commitea ahí solo su alcance. No hace push.
3. Validar con `git diff develop...HEAD`, que muestra solo lo del lote.
4. Si se rechaza: el prompt de corrección le pide seguir en la misma rama, sin crear otra.
5. Con veredicto aprobado: commitear en esa rama el prompt y la bitácora, `git push -u origin <rama>` y abrir el PR con `gh pr create --base develop`, llenando la plantilla de `.github/pull_request_template.md`.
6. El merge lo hace Esteban, con merge commit. Nunca el orquestador. Después del merge, `git pull` en `develop` basta para alinear.
7. En la rama del lote siguiente, el orquestador borra de `orquestacion/` el prompt del lote ya fusionado, y sus correctivos o addendums. En `orquestacion/` solo queda el prompt del lote en curso. Lo borrado sigue en el historial: `git log --diff-filter=D --oneline -- orquestacion/<archivo>` da el commit del borrado, y `git show <commit>^:orquestacion/<archivo>` lo muestra.

Los cambios del propio orquestador a documentación también van por rama `docs/...` y PR.

### Reglas de división en lotes

- Un lote toca un conjunto de archivos que ningún otro lote paralelo toca.
- Un lote incluye como máximo **una** migración de Alembic.
- Nada de pagos ni migraciones en paralelo con otra cosa.
- Si un lote pasa de unos 15 archivos, se divide.
- El orden lo mandan las dependencias: modelos y migraciones primero, después servicios, después endpoints, después integraciones, después pruebas.

---

## 7. Criterios de esfuerzo, modelo y multiagente

| Tipo de trabajo | Esfuerzo | Configuración |
|---|---|---|
| Modelado de datos, máquina de estados, diseño de la integración de pagos, políticas RLS, migraciones destructivas, decisiones de seguridad | **Alto**: modelo de razonamiento extendido | Un solo agente, sin paralelismo. Revisión humana obligatoria |
| Endpoints nuevos sobre un modelo ya definido, servicios con lógica moderada, handlers de jobs | **Medio** | Un agente por lote |
| CRUD repetitivo, esquemas Pydantic, pruebas unitarias, renombrados mecánicos, documentación, configuración de CI | **Bajo**: modelo rápido | Un agente, o varios en paralelo si los lotes no comparten archivos |

**Paralelo solo si se cumplen las tres condiciones:** los lotes no comparten archivos, ninguno incluye una migración, y ninguno toca pagos, autenticación ni RLS. Si alguna falla, va en serie.

**Regla de costo y beneficio:** el esfuerzo alto se reserva para lo que, si sale mal, cuesta caro arreglar (dinero, datos, seguridad, esquema). Lo repetitivo va con el modelo rápido y criterios de aceptación estrictos que lo compensen.

---

## 8. Lista de verificación para validar lo que devuelva un agente

**Bloqueantes (si falla uno, se rechaza):**

- [ ] Tocó solo los archivos del alcance.
- [ ] No rompió ninguna invariante de la sección 2.
- [ ] No agregó librerías fuera del stack.
- [ ] No tocó `mobile/`.
- [ ] Ningún commit de la rama lleva `Co-Authored-By` ni menciona herramientas de asistencia: `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0. Si aparece y la rama no se subió, se limpian los mensajes sin tocar el árbol antes del push.
- [ ] Los criterios de aceptación se cumplen de verdad, **con la salida del comando pegada**. Un criterio marcado sin evidencia no está cumplido.
- [ ] Si hubo migración: es reversible o está justificado que no lo sea, y no borra datos sin decirlo.
- [ ] Si tocó pagos: el estado del pedido y el del cobro cambian en la misma transacción.
- [ ] Si tocó modelos: no apareció ninguna columna de saldo mutable.
- [ ] La documentación oficial está actualizada según la skill `documentacion-proyecto`, o el PR deja escrito por qué no aplica. Si el lote no la actualizó, el orquestador la actualiza en la misma rama antes de abrir el PR.

**No bloqueantes (se anotan como deuda en la bitácora):**

- [ ] Nombres coherentes con el glosario de la sección 1.
- [ ] Manejo de errores y casos límite.
- [ ] Pruebas que cubren el camino feliz y al menos un camino de fallo.
- [ ] Sin código muerto ni `TODO` sin dueño.

**Veredictos:** Aprobado, Aprobado con deuda (se registra en la bitácora con su lote de arreglo), Rechazado (se genera de inmediato un prompt de corrección corto que cite archivo, problema y resultado esperado, sin repetir el prompt original).

---

## 9. Errores conocidos que hay que vigilar

Salen una y otra vez en este stack:

1. `DATABASE_URL` con esquema equivocado: debe ser `postgresql+psycopg://`.
2. Parámetros de asyncpg pasados a psycopg, como `statement_cache_size`.
3. Prepared statements activas contra Supavisor en modo transacción.
4. `async def` con sesión sincrónica adentro.
5. RLS desactivado "porque la autorización está en la API".
6. Verificación del JWT con secreto compartido en vez de JWKS.
7. Saldos guardados como columna en lugar de calcularse.
8. Webhooks de pago sin idempotencia: las pasarelas reintentan.
9. Paginación con `OFFSET` grande en el feed en vez de cursor.
10. Vistas de métricas sin conversión de zona horaria.
11. `@app.on_event` en vez de `lifespan`.
12. `create_type` pasado a `sqlalchemy.Enum` en vez de al `ENUM` del dialecto de PostgreSQL.
