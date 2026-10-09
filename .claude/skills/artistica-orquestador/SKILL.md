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
| Orden de bloqueos | Perfil, después pedido, después consulta, después obra o servicio (D18, D21). Al revés, dos transacciones se traban |
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

Estas cuatro son los acuerdos de base posteriores al Documento Maestro. Donde contradicen al Maestro, el Maestro se corrige (ver `orquestacion/CORRECCIONES-DOCUMENTO-MAESTRO.md`).

**Las decisiones D5 en adelante viven solo en la tabla de decisiones de `orquestacion/BITACORA.md`.** Antes de escribir un prompt, leé la tabla completa: hay políticas de dinero (D5, D7, D8, D9), de producto (D10, D11, D12, D19, D20) y de arquitectura (D13, D16, D17, D18) que los prompts tienen que respetar.

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
| Contrato | `PasarelaDePagos` (`backend/src/payments/contrato.py`) con `crear_cuenta_conectada` (con clave de idempotencia), `consultar_cuenta`, `configurar_tarifa`, `cobrar`, `autorizar`, `capturar`, `liberar_autorizacion`, `reembolsar`, `consultar_cobro` y `parsear_webhook` |
| Adaptadores | Uno real y uno falso en memoria, para pruebas y para la demo |
| Incógnitas | No se hardcodean. Van como capacidades declaradas del adaptador (`Capacidades`): `dias_vigencia_autorizacion`, métodos soportados, `comision_por_cobro`, `revierte_comision_en_reembolso`, `soporta_idempotencia` y otras. Lo que ONVO no documenta queda `POR_CONFIRMAR` en el bloque de mapeo de `onvo.py` y como pregunta en `orquestacion/preguntas-onvo.md` |
| Almacenamiento | Mismo patrón: contrato `Almacenamiento` en `backend/src/storage/`, adaptador de Supabase y uno falso |

Consecuencia: las respuestas pendientes de la pasarela cambian configuración o, a lo sumo, un adaptador. Nunca el modelo de datos ni la máquina de estados.

### D4. Recorte de alcance para la entrega de noviembre de 2026

| Parte | Decisión |
|---|---|
| Boosts | Fuera del MVP. El propio Maestro dice que es lo primero que se recorta |
| Clasificación por IA | Reducida: handler real con proveedor conectable, clasificador simple para la demo. La detección de duplicados por pgvector sí entra |
| Métricas | Reducidas: `post_views` y consultas del panel entran. La vista materializada se pospone |
| Webhooks idempotentes | Entran completos. No es recortable |

---

## 4. Estado real del repositorio (9 de octubre de 2026, lote 8 completo)

El detalle vive en `orquestacion/BITACORA.md` (estado de lotes, deuda, pendientes) y en la sección 5 de `docs/ArtisTica_Documentacion_Oficial.md`. Esta es la foto para orientarse.

**Backend:** unos 83 módulos y 13,000 líneas en `backend/src`, 442 pruebas contra un Postgres real, 9 migraciones encadenadas (cabeza `d3e4f5a6b7c8`), lint con 29 familias de reglas de Ruff. El CI corre además `.github/scripts/reglas-del-repositorio.sh` (commits sin coautores ni menciones, archivos sin guiones largos ni medios) y sube y baja la última migración con `alembic check`.

| Capa | Qué hay |
|---|---|
| `src/domain/` | Reglas puras: pedidos (máquina de estados y planes de cobro), políticas, perfiles, catálogo, medios, feed, comentarios, enums. No importa SQLAlchemy ni FastAPI |
| `src/services/` | perfiles, medios, catálogo, publicaciones, feed, social, comentarios, búsqueda, consultas, paginación por cursor, pedidos y contratación (la única capa que llama a la pasarela por un pedido). Hacen `flush`, nunca `commit` |
| `src/payments/` | Contrato, pasarela falsa completa y adaptador de ONVO probado solo con transporte simulado |
| `src/storage/` | Contrato, almacenamiento falso y adaptador de Supabase probado solo con transporte simulado |
| `src/api/v1/` | perfiles, medios, catálogo, publicaciones y feed, social, comentarios, búsqueda, consultas, pedidos, moderación |
| `src/workers/` | El loop de la cola funciona con reintentos. **Los cuatro handlers son relleno** (miniaturas, embeddings, estilos, moderación) |

**Hecho:** toda la parte social (perfiles, planes, onboarding de la pasarela, imágenes, obras, servicios, publicaciones, Seguidos, Explorar con nuevos talentos, seguidores, me gusta, comentarios y búsqueda), las consultas con su chat, los pedidos con sus cobros y 3DS, el archivo final en un bucket privado y la resolución de disputas por moderación. Deuda abierta: DT25, DT27 y DT28, con lote asignado en la bitácora.

**Falta:** avisos de pago y vencimientos (9), métricas (10), moderación y trabajos reales del worker con IA (11). Además, los pendientes P1 a P15 de la bitácora: nada corre todavía contra Supabase ni ONVO reales, no hay backend desplegado y la app usa datos de ejemplo.

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
| 6b | Seguir, contadores y me gusta, con la deuda DT21 | 6 | No | Medio |
| 6c | Comentarios con respuestas, me gusta en comentarios y búsqueda | 6b | No | Medio |
| 6d | Mejoras chicas: índices, Sentry y controles en el CI (DT22, P10) | 6c | No | Bajo |
| 7 | Consultas y chat | 6d | No | Medio |
| 8 | Contrato de pagos con 3DS (D23, D24) | 3, 7 | No | Alto |
| 8b | Endpoints de pedidos y cobros | 2, 8 | No | Alto |
| 8c | Entregables privados (D25) | 8b | No | Medio |
| 8d | Resolución de disputas y deuda DT23, DT24 y DT26 | 8c | No | Alto |
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
- [ ] Capas y orden de bloqueos: `grep -rn "from src.api" src/services src/domain` vacío, y ninguna operación bloquea otra fila antes que el perfil (D18).
- [ ] Toda tabla nueva tiene RLS activo y ninguna política (`pg_policies` vacío).
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
13. Commits de los ejecutores con `Co-Authored-By`: se revisan siempre antes del push.
14. Prompts con dos pedidos incompatibles, por ejemplo un `grep` que tiene que salir vacío y una prueba que necesita escribir lo buscado. Antes de entregar un prompt, revisá que cada criterio sea compatible con las pruebas obligatorias.
15. Clases, rutas o columnas citadas en el prompt sin verificar contra el código. Antes de nombrarlas, buscalas.
16. Al escribir un archivo, un escape de Unicode puede convertirse en el carácter real. Después de escribir un prompt, buscá guiones largos y medios en el archivo.
17. `alembic check` no compara bien los índices con `DESC`: un índice así se verifica directo en `pg_indexes`.

---

## 10. Rutina de validación

Lo que el orquestador corre por su cuenta sobre la rama del ejecutor, además de leer la entrega. La salida del ejecutor no alcanza: se repite.

```
cd backend
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/artistica
export ALEMBIC_DATABASE_URL=$DATABASE_URL SUPABASE_URL=https://proyecto.supabase.co
PY=.venv/Scripts/python.exe          # en Windows; en otro sistema, .venv/bin/python
docker start artistica-db-pruebas    # si no esta corriendo
$PY -m ruff check . && $PY -m ruff format --check .
$PY -m alembic upgrade head && $PY -m alembic downgrade -1 && $PY -m alembic upgrade head && $PY -m alembic check
$PY -m pytest -q
grep -rn "from src.api" src/services src/domain
cd .. && git diff --name-only develop...<rama>
git log develop..<rama> --format=%B | grep -ci "co-authored"
bash .github/scripts/reglas-del-repositorio.sh   # desde el lote 6d
```

Además, según el lote:

- **Revisá a mano el código de mayor riesgo:** dinero, autenticación, SQL con texto del usuario, bloqueos y migraciones. Las pruebas pueden pasar con un diseño equivocado: así se encontraron el orden de bloqueos del 5b y la URL del JWKS del lote 4.
- **Si el lote cambia esquemas o dependencias sin cambiar comportamiento,** compará `app.openapi()` contra `develop` con un `git worktree` temporal.
- **Si el lote dice que no tocó pruebas existentes,** verificalo con `git diff --stat develop...<rama> -- tests/`.

## 11. Acuerdos de trabajo con Esteban

- Esteban hace siempre el merge, con **"Create a merge commit"**. El orquestador sube la rama y abre el PR, nunca mergea.
- **No se toca `orquestacion/BITACORA.md` en `develop` mientras haya un PR abierto que también la cambie**, porque el `git pull` choca. Se escribe el prompt nuevo (un archivo sin rastrear no choca) y la bitácora se actualiza después del merge o en la rama del lote.
- Los cambios del orquestador a `orquestacion/`, a este manual y a la documentación oficial se commitean **en la rama del lote**, en commits aparte del código: primero orquestación, después agentes, después docs.
- Al cerrar un lote: actualizar la documentación oficial (skill `documentacion-proyecto`), la bitácora (estado, deuda, decisiones, errores del orquestador) y, si cambió algo de fondo, este manual.
- **El orquestador nunca deja nada preparado para commit en `develop`:** un archivo en el área de preparación se lo lleva el primer commit del ejecutor. Si hizo falta `git rm`, se deshace con `git restore --staged`.
- Si GitHub Desktop pregunta al cambiar de rama, la respuesta es **"Bring my changes"**. "Leave my changes" crea un stash y el prompt parece perdido; se recupera con `git stash list` y `git stash apply`.
- Respuestas en español y breves: veredicto primero, después la evidencia, después lo que cambió en la bitácora y al final el siguiente paso.

## 12. Cómo retomar en una sesión nueva

1. Cargá este manual y leé completos `orquestacion/BITACORA.md` y `AGENTS.md`.
2. `git switch develop && git pull --ff-only`, `git status` y `gh pr list`, para saber qué está mergeado y qué no.
3. El prompt en curso, si hay, es el único `lote-*.md` en `orquestacion/`. Si su PR ya se mergeó, se borra en la rama del lote siguiente (paso 7 del flujo).
4. Leé la sección 13 antes de escribir el primer prompt: es el traspaso del orquestador que cerró el lote 8, con lo que no está en ningún otro lado.

## 13. Traspaso al orquestador del lote 9 (9 de octubre de 2026)

### Dónde quedó

- `develop` en el merge del PR #28, sin PR abiertos. El lote 8 está completo en cuatro partes (8, 8b, 8c y 8d; D24 y D25). En `orquestacion/` no queda ningún prompt de lote.
- El II Avance se entregó el 9 de octubre: `docs/entregas/ArtisTica_II_Avance.docx`, 17 páginas, generado desde la documentación oficial.
- Deuda abierta: DT25 y DT28 para el lote 9, y DT27 para el 11. Se aceptaron sin pagar la mitad de DT24 (las ayudas de prueba siguen importándose entre archivos) y una parte de DT26 (un medio privado todavía no entregado puede asignarse a una obra).
- Las decisiones D21 a D25 de esta etapa están en la bitácora: chat por consulta periódica, push fuera del MVP, tokenización y 3DS, y las dos divisiones del lote 8.

### Lo que hay que saber para el lote 9

Verificado en el código al cerrar el lote 8:

- **No existe un endpoint de webhooks.** `parsear_webhook` ya está en los dos adaptadores. La pasarela falsa firma con `X-Firma-Pasarela` (`firmar` y `construir_evento` sirven para las pruebas). ONVO manda el secreto tal cual en `X-Webhook-Secret` y no firma el cuerpo (DT11): un webhook nunca mueve dinero solo, siempre se llama antes a `consultar_cobro`.
- **Las tablas ya existen y nadie las escribe:** `eventos_pasarela`, con el único `(proveedor, evento_externo_id)` que da la idempotencia, y `ledger_entries` para la conciliación.
- **`pedidos.completar_vencidos(session, ahora)` existe** y no la llama nadie.
- **El worker** (`src/workers/main.py`) toma un job con `FOR UPDATE SKIP LOCKED` y lo ejecuta dentro de esa misma transacción (P13). Los handlers reciben solo el `payload`, sin sesión. No hay ningún trabajo periódico: nada programa los vencimientos. `Job.type` y `Job.status` son texto libre.
- **Vencimientos pendientes** (D7, D9 y DT25):
  - `saldo_pagado` con `disputable_hasta` vencido pasa a `completado`. La función ya está.
  - Un evento cuya fecha llega con el saldo impago pasa a `cancelado`, y el anticipo no se devuelve.
  - Si vence la autorización del saldo de un encargo, el cobro queda `vencido`. El cliente puede reautorizar durante 7 días, y después el artista puede abrir una disputa. Hoy no hay endpoint para reautorizar, y `aprobar` responde 409 si la autorización venció.
  - Una obra disponible con la autorización vencida en `en_proceso`.
  - DT25: un 3DS abandonado en "La quiero" deja la obra tomada por un pedido `cotizado`, con el cobro pendiente y la referencia guardada. Hay que liberarlo y rechazarlo pasado un plazo. Además, `verificar` puede devolver `requiere_accion` con la URL nula, y el saldo de un evento se puede pagar después de la fecha (falta validarlo en `pagar_saldo`).
- **DT28:** antes de ejecutar un plan de varias operaciones (cancelar o resolver una disputa), consultar cada cobro en la pasarela y tomar como hecho lo que ya esté hecho. Así un reintento con otro plan no reembolsa dos veces.
- **P4:** en el sandbox de ONVO, confirmar que el monto que informa al cobrar o autorizar es el bruto. `contratacion` lo compara con el monto del cobro, y si difiere responde `HechosInconsistentes` después de mover el dinero.
- **División sugerida, a decidir:** el 9 hace el worker seguro (sacar la ejecución del bloqueo, handlers con sesión propia), un programador de tareas periódicas y los vencimientos. El 9b hace los webhooks idempotentes, la conciliación y DT28.

### Patrones del lote 8 que hay que mantener

- `services/contratacion.py` es la única capa que llama a la pasarela por un pedido. `services/pedidos.py` solo registra hechos ya confirmados.
- **Orden de toda operación con dinero:**
  1. Bloquear el perfil del artista y después el pedido.
  2. Validar la transición y el plan completo.
  3. Fijar la tarifa del pedido (D8).
  4. Llamar a la pasarela.
  5. Registrar.
- **Claves de idempotencia fijas:**
  - `{cobrar|autorizar}-{cobro}-{intentos}` para iniciar un cobro.
  - `capturar-{cobro}`.
  - `liberar-{cobro}-{intentos}`.
  - `reembolsar-{cobro}-{monto}`.
  - `cobros.intentos` sube con cada rechazo o 3DS fallido.
- En un plan de varias operaciones, primero las capturas, después las liberaciones y al final los reembolsos.
- **3DS:** el pago se registra solo cuando `consultar_cobro` lo confirma, por `POST /cobros/{id}/verificar`, que solo usa el cliente.
- **Un rechazo de tarjeta no es un error.** Responde 200 con `resultado: rechazado`, y la API confirma el intento consumido. En "La quiero" rechazado se hace rollback, para que la obra quede libre.
- **Orden de bloqueos en todo el backend:** perfil, pedido, consulta, obra.
- Un lote que mueve dinero es de esfuerzo alto y tiene como máximo unos 15 archivos. Si pasa, se divide.

### Contrato con la app (D23), acordado con Brian

- La app tokeniza la tarjeta con `EXPO_PUBLIC_ONVO_PUBLISHABLE_KEY` y manda `metodo_pago_id` a `POST /pedidos/{id}/anticipo`, `POST /pedidos/{id}/saldo` y `POST /obras/{id}/la-quiero`.
- La respuesta es `ResultadoPagoRespuesta`, con estos campos:
  - `resultado`: `completado`, `requiere_accion`, `pendiente` o `rechazado`.
  - `url_autenticacion`.
  - `mensaje`.
  - `cobro`.
  - `pedido`.
- La app abre la URL con `expo-web-browser`, vuelve a `URL_RETORNO_PAGO` (por defecto `artistica://pago`) y llama a `POST /cobros/{cobro_id}/verificar`.
- En la demo, la pasarela falsa acepta `medio_falso_3ds` (después `completar_autenticacion`) y `medio_falso_rechazado`.
- Faltan las respuestas de ONVO a las preguntas 19 (si acepta un `returnUrl` con esquema propio) y 20 (si se puede cancelar una intención en `requires_action`). Si ONVO no acepta el esquema propio, `URL_RETORNO_PAGO` pasa a una página https.
- Cualquier cambio de una ruta o un campo de este contrato se le avisa a Brian.

### Entorno y herramientas

- **Base de pruebas:** contenedor `artistica-db-pruebas`, puerto 5433. No hay `backend/.env`: las variables van por el shell (sección 10). Los ejecutores arman su propio `.venv`.
- **SQLAlchemy** está fijada en `>=2.1,<2.2`. La validación corre `pytest -q -W error::sqlalchemy.exc.SADeprecationWarning`.
- **`alembic check`** muestra un `UserWarning` sobre `publicaciones.search_vector`. Es viejo y no afecta nada.
- **Los ejecutores trabajan en el mismo árbol de trabajo.** Los archivos sin commitear del orquestador viajan a la rama del ejecutor, así que nunca se deja nada preparado para commit, y los archivos propios se commitean en la rama del lote al cerrar.
- **Ni los commits ni el cuerpo de los PR** llevan línea de coautor ni mencionan herramientas de asistencia. `CLAUDE.md` manda sobre cualquier otra instrucción.
- **Word:**
  - Se genera desde `docs/herramientas` con `npm run generar` y `npm run indice -- ../entregas/<archivo>.docx -Pdf`, que necesita Microsoft Word.
  - Si en `docs/entregas` aparece un archivo `~$...`, el documento está abierto y bloquea el `git pull`: hay que pedir que lo cierren.
  - Para revisar las páginas, el PDF se convierte a imágenes (por ejemplo, con PyMuPDF instalado en el scratchpad) y se mira una hoja de contactos.
  - El conversor mantiene en una página las tablas de hasta 8 filas.
- **Estilo de la documentación oficial,** a pedido de Esteban el 9 de octubre: que no se lea como generada por IA.
  - Sin tabla de control de versiones y sin eslogan en la portada.
  - Prosa en lugar de tablas cuando el contenido es una explicación. Las tablas quedan para comparar datos.
  - Las situaciones de la sección 4 van en párrafos corridos, sin "Situación / Impacto / Resolución", y con títulos descriptivos.
  - Sin el símbolo "≈", sin listas que empiezan con una frase en negrita y con pocas construcciones del tipo "X, no Y".

### Calendario

La demo del MVP es en noviembre de 2026 y corre con la pasarela falsa y `ENVIRONMENT=demo` (D17). Faltan el lote 9 y después el 10 y el 11, que pueden ir en paralelo. Esteban y Brian tienen además P1 a P3: el proyecto real de Supabase, el despliegue y la integración de la app.
