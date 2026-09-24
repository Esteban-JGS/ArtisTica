# Correcciones al Documento Maestro

Erratas detectadas al validar el documento contra el repositorio, el 23 de septiembre de 2026. Aplicar sobre `docs/ArtisTica_Documento_Maestro.md` y subir la versión a 1.1.

El Documento Maestro vive en `docs/`, versionado. Las correcciones quedan en el historial.

---

## C1. Sección 2.4, estados del pedido (bloqueante)

**Problema.** La sección lista `consulta` como primer estado del pedido, mientras que §5.4 lista `consultas` y `pedidos` como tablas separadas y §2.2 define consulta como una conversación. No se puede modelar el esquema con la contradicción abierta.

**Se resuelve a favor de entidad separada.** Tres razones:

1. La obra disponible no tiene consulta previa: "La quiero" crea el pedido sin negociación. Si `consulta` fuera un estado del pedido, uno de los tres tipos tendría que saltárselo, y se rompe la promesa del motor único.
2. La métrica "conversión de consulta a encargo" de §3.2 exige que las consultas no convertidas sean filas contables. Si viven dentro de `pedidos`, toda métrica de dinero queda contaminada con vitrineo.
3. El hilo de conversación sobrevive aunque nunca haya cotización, tal como lo describe §2.6.

**Texto de reemplazo para el bloque de estados de §2.4:**

> La consulta es una entidad propia, no un estado del pedido. Tiene su propio ciclo: `abierta`, `cotizada`, `convertida`, `descartada`. El chat cuelga de la consulta.
>
> El pedido nace cuando el cliente acepta una cotización, y su máquina de estados es:
>
> ```
> cotizado → anticipo_pagado → en_proceso → vista_previa_entregada → saldo_pagado → completado
> ```
>
> - `rechazado`: desde cotizado.
> - `cancelado`: según la política de cada tipo de pedido.
> - `en_disputa`: desde vista_previa_entregada o después de la entrega.
>
> Todo pedido referencia una consulta. Para obra disponible, el toque de "La quiero" crea la consulta de forma automática, ya en estado `convertida`, de modo que exista un solo mecanismo de chat y un hilo donde coordinar la entrega.
>
> Para eventos, `vista_previa_entregada` no aplica: el saldo se cobra antes de la fecha. Para obra disponible, el pedido pasa de confirmado a despachado y a completado. Toda transición no contemplada debe levantar un error.

---

## C2. Sección 5.1, estructura del monorepo (bloqueante para los prompts)

**Problema.** El diagrama dice `app/` para el frontend. En el disco la carpeta es `mobile/`, y `/app` es además el `WORKDIR` de `backend/Dockerfile` y `backend/Dockerfile.worker`. Una prohibición que diga "no toques /app" es ambigua o directamente falsa.

**Texto de reemplazo:**

```
monorepo/
├── mobile/     React Native + Expo (Brian)
└── backend/    FastAPI (Esteban)
    ├── API     atiende a la app
    └── worker  IA, miniaturas, moderación, vencimientos y webhooks de pago
```

**Agregar a continuación:**

> La app consume la API de FastAPI y nunca lee tablas de Supabase con la anon key. Es la única forma compatible con RLS activo sin políticas: la anon key viaja dentro del binario de la app.

---

## C3. Sección 5.3, pagos: aislar la pasarela

**Problema.** El documento fija ONVO Pay como decisión cerrada, pero §5.6 deja seis preguntas abiertas que condicionan el diseño y que a la fecha siguen sin respuesta.

**Agregar al bloque "ONVO Pay en modo marketplace":**

> La integración vive detrás de un contrato abstracto de pasarela, con las operaciones de crear cuenta conectada, autorizar, capturar, cancelar autorización, reembolsar y parsear webhook. ONVO es el primer adaptador; existe además un adaptador falso en memoria para pruebas y para la demo académica. Las respuestas pendientes de §5.6 no se hardcodean: son capacidades declaradas del adaptador (`dias_vigencia_autorizacion`, `soporta_sinpe`, `comision_por_cobro`, `revierte_comision_en_reembolso`). Así, cambiar de pasarela cuesta un adaptador y no el modelo de datos.

---

## C4. Sección 2.3 contra 2.5, el anticipo en una disputa (no bloqueante, pero hay que cerrarlo)

**Problema.** §2.3 paso 3 dice que el anticipo "no se reembolsa salvo incumplimiento del artista". §2.5 dice que una disputa puede terminar en reembolso, sin excluir el anticipo. Un cliente puede leer las dos frases y sacar conclusiones opuestas.

**Pendiente de tu decisión.** Hay que escribir cuál de las dos manda, y si el reembolso parcial puede alcanzar al anticipo. Bloquea el lote 2.

---

## C5. Sección 3.2, filas que no diferencian los planes (cosmético)

Dos filas de la tabla Taller contra Estudio dicen lo mismo en ambas columnas o no se entienden:

- "Pedidos activos simultáneos: sin límite / sin límite". Si no diferencia, sobra en una tabla comparativa. Conviene moverla a §3.3, donde se listan las cosas que nunca se limitan.
- "Video: corto y limitado / corto". No queda claro cuál es la diferencia. Hay que escribir el número o borrar la fila.

---

## C6. Decisiones que siguen abiertas y bloquean lotes

| # | Pregunta | Bloquea |
|---|---|---|
| 1 | Porcentaje del anticipo: ¿fijo, o lo elige el artista entre 30 y 50? | Lote 2 |
| 2 | Ventana para abrir una disputa, en días | Lote 2 |
| 3 | Política de cancelación de eventos, en días y porcentajes | Lote 2 |
| 4 | C4 de este documento: el anticipo frente a la disputa | Lote 2 |
| 5 | Si una persona física sin actividad inscrita puede completar el onboarding de la pasarela | Lote 4 |

---

## Lo que se verificó y está correcto

Para que no se revise dos veces:

- La tabla de netos por precio de §4.2 cuadra con tarifa de 8% y 5% más procesamiento de 3.9% más 0.25 dólares, en los diez casos.
- La tabla de §4.4 sobre cuántos boosts paga una venta cuadra con esos netos.
- La aritmética de §4.7 cuadra: 215 pedidos por 9 dólares netos más 1,200 de suscripciones da cerca de los 3,200 mensuales del objetivo.
- El precio de Estudio es coherente entre §3.2, §4.1 y §4.3, y con el canvas.
