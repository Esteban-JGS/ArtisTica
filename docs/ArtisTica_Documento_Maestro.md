# ArtísTica: Documento Maestro del Proyecto

**Versión:** 1.0 (consolidación del modelo de negocio)
**Fecha:** septiembre 2026
**Equipo:** Esteban Granados Sibaja (backend, infraestructura y DevOps) y Brian Zeledón Esquivel (aplicación móvil)
**Mercado inicial:** Costa Rica
**Estado:** MVP en construcción, con entrega académica en noviembre 2026

> Tipo de cambio de referencia usado en este documento: ≈ ₡500 por US$1. Los montos en colones son aproximados.

---

## Índice

1. Resumen ejecutivo y propuesta de valor
2. Modelo operativo: comisiones abiertas en lugar de marketplace
3. Usuarios y planes
4. Modelo de ingresos y monetización
5. Arquitectura y stack técnico
6. Estrategia de lanzamiento (go-to-market)
7. Riesgos, beneficios y mitigaciones

---

## 1. Resumen ejecutivo y propuesta de valor

### 1.1 Qué es ArtísTica

**ArtísTica es donde en Costa Rica se contrata arte hecho por personas, con el pago protegido.**

No es "otra red social para artistas". Es el lugar donde una persona descubre a un artista y lo contrata con confianza. La parte social (galería, feed, comentarios, reacciones) existe para alimentar ese momento de contratación, no como fin en sí misma.

### 1.2 El dolor que resuelve

Hoy, en Costa Rica, contratar arte funciona con la combinación **Instagram + WhatsApp + SINPE Móvil**:

| Herramienta | Qué resuelve | Qué deja sin resolver |
|---|---|---|
| Instagram | Vitrina: ver el trabajo del artista | No tiene forma de contratar ni cobrar |
| WhatsApp | Negociar el encargo | No deja registro formal ni reglas |
| SINPE Móvil | Pagar rápido y sin costo | No hay protección para ninguna de las partes |

El resultado es miedo de los dos lados:

- **El cliente** teme pagar el adelanto y que el artista desaparezca o entregue algo distinto a lo acordado.
- **El artista** teme hacer el trabajo o presentarse al evento y que el cliente no pague el saldo.

ArtísTica une vitrina y transacción protegida en un mismo lugar: el pago se hace por hitos dentro de la aplicación, el dinero lo custodia una entidad regulada (ONVO) y, si algo sale mal, existe un proceso de disputa.

### 1.3 Propuesta de valor

> ArtísTica es la comunidad donde los artistas muestran lo que hacen y consiguen trabajo sin salir de la aplicación, con pago protegido dentro de la plataforma. Es un espacio solo para creadores humanos, con un feed que muestra lo que cada quien elige seguir y un panel que le revela a cada artista qué obras tienen mejor respuesta.

**Para el cliente:** contratar sin miedo a perder el adelanto, con reglas claras y reseñas reales.
**Para el artista:** portafolio, clientes y cobro seguro en un solo lugar, más datos sobre qué parte de su trabajo genera interés real.

### 1.4 Principios que no se negocian

1. **Arte hecho por personas.** Se prohíbe el contenido generado por IA. El clasificador marca contenido sospechoso para revisión humana; nunca banea de forma automática, porque acusar a un artista humano por un falso positivo es el peor error posible para esta comunidad. La lectura de metadatos C2PA sirve como señal complementaria.
2. **Feed auténtico.** El feed de Seguidos es cronológico y nunca lleva contenido promocionado. Explorar funciona por las categorías que el usuario eligió, no por predicción de comportamiento.
3. **Artista, no tienda.** Se vende la habilidad del artista, no inventario. No existe catálogo, stock ni reventa.
4. **Métricas honestas.** El panel del artista mide respuesta real (consultas, conversión), no viralidad.

### 1.5 Competencia y posicionamiento

| Alternativa | Fortaleza | Por qué no resuelve el problema |
|---|---|---|
| Instagram | Audiencia enorme, vitrina gratuita | Vitrina sin transacción |
| WhatsApp + SINPE Móvil | Inmediato, sin costo | Transacción sin protección ni reputación |
| Fiverr y plataformas globales similares | Protegen el pago | Globales, cobran en dólares, no cubren contrataciones locales como un mariachi para el sábado |

**Ventaja defendible a largo plazo:** la reputación acumulada. Un artista con decenas de encargos completados y reseñados dentro de ArtísTica no se va a otra plataforma a empezar de cero.

---

## 2. Modelo operativo: comisiones abiertas en lugar de marketplace

### 2.1 La decisión

ArtísTica funciona con **comisiones abiertas**: el artista muestra lo que hace y declara que acepta trabajos. No sube productos a una tienda.

La única excepción es la **obra disponible**: el artista puede marcar una obra ya terminada como disponible con precio fijo. Cuando un cliente toca "La quiero", se abre un encargo con precio fijo por el mismo flujo, sin negociación. Así se cubre la venta directa sin construir un marketplace.

### 2.2 Glosario

La palabra "comisión" tenía dos significados (trabajo a pedido y porcentaje de la plataforma). Se separan así:

| Término | Significado |
|---|---|
| **Encargo** | Trabajo hecho a pedido para un cliente |
| **Evento** | Contratación con fecha y lugar (música, baile, presentaciones) |
| **Obra disponible** | Obra terminada que el artista ofrece con precio fijo |
| **Tarifa de servicio** | Porcentaje que cobra ArtísTica sobre cada pedido |
| **Obra** | Pieza de la galería del artista; puede ser solo de exhibición o estar disponible |
| **Publicación** | Lo que aparece en el feed; puede mostrar una obra o ser independiente (proceso, agenda) |
| **Servicio** | Paquete con precio que el artista ofrece ("Serenata 30 min", "Retrato A4") |
| **Consulta** | Conversación que abre un cliente sobre un servicio o una obra; puede convertirse en pedido |
| **Pedido** | Toda transacción: tiene tipo (encargo, evento u obra disponible) y uno o más cobros |
| **Cobro (hito)** | Cada pago parcial de un pedido: anticipo o saldo |

**Regla de interfaz:** las publicaciones nunca tienen precio ni botón de compra. Una obra disponible muestra la etiqueta "Disponible" y el botón vive en la ficha de la obra o en el perfil ("Solicitar encargo").

### 2.3 El flujo único

Los tres tipos de pedido comparten el mismo motor: consulta, pedido, cobros por hitos, disputa y reseña. Solo cambia qué dispara cada cobro.

#### Encargo

1. **Consulta:** el cliente toca "Consultar" o "Solicitar encargo" en el perfil o en un servicio. Describe la idea, adjunta referencias, indica presupuesto y plazo deseado.
2. **Cotización:** el artista responde por el chat de esa consulta y envía una propuesta formal (descripción, cantidad de revisiones, fecha de entrega, precio). El cliente acepta o contraoferta.
3. **Anticipo (30 a 50%):** se cobra al aceptar la propuesta y se captura de inmediato. Es el pago al artista por comenzar; no se reembolsa salvo incumplimiento del artista.
4. **Vista previa:** el artista entrega una versión con marca de agua. En ese momento se autoriza el saldo en la tarjeta del cliente.
5. **Aprobación:** cuando el cliente aprueba, se captura el saldo.
6. **Entrega final:** el archivo final (o la obra física) se libera después del cobro del saldo.
7. **Reseña:** ambas partes pueden calificar el pedido completado.

#### Evento

1. Consulta y cotización igual que en el encargo, con **fecha y lugar**.
2. **Anticipo al reservar:** reserva la fecha del artista.
3. **Saldo antes del evento:** se cobra con la anticipación definida en la política del pedido.
4. **Cancelación:** la devolución depende de con cuánta anticipación se cancele (política por definir).
5. Reseña después del evento.

#### Obra disponible

1. El cliente toca "La quiero" en una obra disponible.
2. Se crea un pedido con precio fijo, sin negociación.
3. El cobro se **autoriza** al confirmar y se **captura** cuando el artista despacha con número de guía, dentro del plazo de vigencia de la autorización. Si el artista no despacha a tiempo, el pedido se cancela solo y se liberan los fondos.
4. Reseña después de la entrega.

### 2.4 Estados del pedido

Propuesta de máquina de estados alineada con los hitos:

```
consulta → cotizado → anticipo_pagado → en_proceso → vista_previa_entregada → saldo_pagado → completado
```

- `rechazado`: desde consulta o cotizado.
- `cancelado`: según la política de cada tipo de pedido.
- `en_disputa`: desde vista_previa_entregada o después de la entrega.

Para eventos, `vista_previa_entregada` no aplica: el saldo se cobra antes de la fecha. Para obra disponible, el pedido pasa de confirmado a despachado y a completado. Toda transición no contemplada debe levantar un error.

### 2.5 Disputas, cancelaciones y reembolsos

- Una disputa congela el pedido y la resuelve el equipo de moderación con base en evidencia: el chat de la consulta, la propuesta aceptada, las vistas previas y, en envíos, la guía.
- Resultados posibles: el pago sigue su curso, se reembolsa o se reembolsa de forma parcial.
- La ventana para abrir una disputa y la política de cancelación de eventos quedan por definir en números concretos, pero deben ser cortas y públicas.
- Mientras más claras sean las reglas por defecto, menos disputas requieren intervención humana. Resolver a mano una disputa de un pedido pequeño cuesta más que la tarifa cobrada.

### 2.6 Chat y contacto

No existe el mensaje directo suelto entre cliente y artista. Toda conversación nace atada a algo:

| Relación | Regla |
|---|---|
| Cliente con artista | Solo mediante una **consulta** sobre un servicio o una obra. Si avanza, esa misma conversación se convierte en el pedido. |
| Artista con artista | Mensajes directos libres. Es la socialización real (colaborar, pedir consejo) y no tiene riesgo de fuga. |
| Público con público | No existe. |

Refuerzos:

- Detección de teléfonos, "SINPE" y "WhatsApp" en el chat con un **aviso suave**: "Si pagás fuera de ArtísTica, no tenés protección ni reseña". Informa, no bloquea.
- El perfil no puede mostrar teléfonos ni enlaces de WhatsApp. El enlace a Instagram sí se permite, porque es vitrina y no canal de cobro.
- Límite diario de consultas nuevas para cuentas recientes, contra el spam.

La socialización pública vive en los comentarios y reacciones.

### 2.7 Reputación

Las reseñas solo provienen de **pedidos completados dentro de la aplicación**. Fuera de la app se puede cobrar, pero no se construye reputación. Es el principal incentivo para que el trato se cierre adentro.

### 2.8 Descubrimiento y feed

| Superficie | Reglas |
|---|---|
| **Seguidos** | Cronológico. Nunca lleva contenido promocionado. |
| **Explorar** | Por categorías elegidas. Mezcla contenido orgánico reciente, recomendaciones por similitud de estilo, una cuota fija de **Nuevos talentos** (artistas con pocos seguidores) y como máximo 1 publicación promocionada cada 8 elementos. |
| **Búsqueda** | Resultados orgánicos primero; como máximo 1 promocionado arriba, solo si coincide con la búsqueda. |

La recomendación usa señales limitadas: categoría, similitud de estilo y recencia. Nunca tiempo en pantalla.

### 2.9 Por qué se descartó el marketplace tradicional

| Criterio | Marketplace de productos | Comisiones abiertas (elegido) |
|---|---|---|
| Motores de pago | Dos (compra con envío + encargo) | Uno solo con tres tipos de pedido |
| Operación | Envíos, existencias, devoluciones por "no me gustó" | Entregas acordadas por pedido |
| Ticket promedio | Bajo (piezas pequeñas) | Alto (eventos, murales, encargos) |
| Competencia directa | Facebook Marketplace e Instagram ya lo cubren | Nadie cubre bien el encargo protegido |
| Filosofía original | La contradice (catálogo, stock) | La respeta (se vende habilidad) |
| Plazo de noviembre | Dos flujos a medias | Un flujo terminado |
| Pedidos mensuales para sostener el negocio (ilustrativo) | ≈ 540 (ticket de US$60) | ≈ 215 (ticket de US$150) |

Si los datos muestran demanda fuerte de obras disponibles, el marketplace completo se evalúa en la Etapa 3.

---

## 3. Usuarios y planes

### 3.1 Roles

| Rol | Descripción |
|---|---|
| **Público** | Gratis. Explora, sigue, reacciona, comenta, guarda en colecciones, consulta a artistas, contrata y compra obras disponibles. No publica ni tiene galería. |
| **Artista: Taller** | Plan gratuito para creadores. |
| **Artista: Estudio** | Plan de suscripción para creadores. |
| **Agrupación** (Etapa 2) | Perfil con varios miembros administradores: bandas, mariachis, compañías de baile. |
| **Admin / Moderador** | Reportes, revisión de contenido sospechoso de IA, moderación, disputas. |

### 3.2 Taller frente a Estudio

| Funcionalidad | Taller (gratis) | Estudio (≈ ₡2,500/mes) |
|---|---|---|
| Galería y publicaciones | Sí | Sí |
| Comisiones abiertas y recepción de pedidos | Sí, sin límite | Sí, sin límite |
| Pedidos activos simultáneos | Sin límite | Sin límite |
| Pago protegido y disputas | Sí | Sí |
| Aparecer en Explorar | Sí | Sí |
| **Tarifa de servicio** | **8%** | **5%** |
| Servicios publicados | 2 | Ilimitados |
| Obras disponibles | 5 | Ilimitadas |
| Calendario de disponibilidad | Manual | Sincronizado con Google Calendar y bloqueo automático de fechas contratadas |
| Plantillas de cotización | No | Sí |
| Cupos de comisiones (cierre automático al llenarse) | No | Sí |
| Métricas | Últimos 30 días | Historial completo: qué obras generan consultas, conversión de consulta a encargo, días y horas de mayor actividad, provincias de origen |
| Perfil | Estándar | Personalizable, con obras destacadas |
| Boost incluido | No | 1,000 personas al mes (no acumulable) |
| Reporte de ingresos exportable para Hacienda | No | Sí |
| Video | Corto y limitado | Corto |

**Precio de Estudio:** ≈ ₡2,500 al mes (≈ US$5) o ≈ ₡25,000 al año (≈ US$50).

### 3.3 Lo que nunca se limita ni se cobra

- Publicar.
- Abrir comisiones.
- Recibir pedidos y la cantidad de pedidos activos.
- La protección del pago y las disputas.
- Aparecer en exploración orgánica.
- La verificación de identidad.

**Razón:** si el plan gratuito se queda sin poder recibir trabajo, el artista se va a WhatsApp y ArtísTica pierde la tarifa, que es más dinero que la suscripción.

### 3.4 Por qué un artista pagaría Estudio

Un artista que no vende no va a pagar, y está bien: el negocio vive de la tarifa por pedido. Estudio es para quien ya genera trabajo en la plataforma. Tiene cuatro argumentos:

1. **Ahorra dinero.** La tarifa baja de 8% a 5%. Con una diferencia de 3 puntos, Estudio se paga solo a partir de ≈ ₡85,000 al mes en pedidos (≈ US$167). La app debe mostrárselo al artista con sus propios números: "Este mes habrías ahorrado ₡4,200 con Estudio".
2. **Organiza el trabajo como profesional.** Calendario sincronizado, servicios ilimitados, plantillas de cotización y cupos.
3. **Muestra qué funciona.** Métricas completas orientadas a decisiones, no a vanidad.
4. **Da presencia.** Perfil personalizable, obras destacadas y un boost mensual incluido.

**Ejemplo, el cliente ideal de Estudio:** un grupo musical con 4 contrataciones de ₡150,000 al mes paga ₡48,000 de tarifa en Taller y ₡30,000 en Estudio, más ₡2,500 de suscripción. Se ahorra más de ₡15,000 al mes y además obtiene el calendario.

### 3.5 Verificación

La verificación no se vende. Si el check se compra, deja de significar "esta persona es quien dice ser" y pasa a significar "esta persona pagó". El onboarding de ONVO ya recoge la identidad y la cuenta bancaria de quien cobra, así que la verificación sale como consecuencia de ese proceso y es gratuita.

### 3.6 Nombres de los planes

- **Taller** y **Estudio** funcionan para todas las disciplinas (taller de pintura o de danza; estudio de grabación, de arte o de baile) y describen una progresión natural.
- Se descartaron "Galería" y "Obra" porque chocan con nombres de funcionalidades, y "Aprendiz/Maestro" porque juzga el talento: un profesional en el plan gratuito quedaría como "aprendiz".

### 3.7 Programa de artistas fundadores

Los primeros 100 artistas reciben Estudio gratis durante 6 meses. Es la herramienta principal para resolver el arranque en frío de la plataforma (ver sección 6).

---

## 4. Modelo de ingresos y monetización

### 4.1 Fuentes de ingreso, en orden de importancia

| Fuente | Mecanismo | Rol |
|---|---|---|
| **Tarifa por pedido** | 8% en Taller, 5% en Estudio | Principal. ArtísTica gana solo cuando el artista gana. |
| **Suscripción Estudio** | ≈ ₡2,500 al mes | Secundaria. Para artistas que ya venden. |
| **Boosts** | Por alcance de personas, segmentados | Complementaria y menor. |
| **Membresías de fans** (Etapa 3) | Apoyo mensual del público a un artista | Futura. |

### 4.2 Tarifa por pedido

**Reglas:**

- Aplica a los tres tipos de pedido: encargo, evento y obra disponible.
- Una sola tarifa por plan. No varía por tipo de pedido: hacerlo invita a clasificar mal y ONVO define la comisión por cuenta de vendedor, no por cobro.
- **Precio mínimo por pedido: US$5 (≈ ₡2,500).** El costo fijo de procesamiento (US$0.25) golpea proporcionalmente más a los montos pequeños, y ONVO no permite una comisión mínima por cobro.
- Sin tope por pedido (no es nativo en ONVO). Para montos altos, la palanca es el método de pago: SINPE Móvil tiene un costo de procesamiento mucho menor que la tarjeta.

**Quién paga qué:** en el modo marketplace de ONVO, los costos de procesamiento y la retención de 2% se descuentan del lado del artista. La tarifa de ArtísTica es ingreso limpio para la plataforma.

**Tarifas públicas de ONVO consultadas (confirmar en contrato):** tarjeta 3.9% + US$0.25; SINPE Móvil 1.5%. Tilopay, como referencia: tarjeta 4.25% + US$0.35; SINPE Móvil 2% + US$0.35.

**Ejemplos con pago por tarjeta** (sin incluir la retención de 2%, que es tributaria):

| Precio | Taller: ArtísTica recibe | Taller: artista recibe | Estudio: ArtísTica recibe | Estudio: artista recibe |
|---|---|---|---|---|
| US$20 | 1.60 | 17.37 | 1.00 | 17.97 |
| US$50 | 4.00 | 43.80 | 2.50 | 45.30 |
| US$100 | 8.00 | 87.85 | 5.00 | 90.85 |
| US$250 | 20.00 | 220.00 | 12.50 | 227.50 |
| US$1,000 | 80.00 | 880.75 | 50.00 | 910.75 |

Con SINPE Móvil, en un pedido de US$1,000 el procesamiento baja de US$39.25 a US$15.

### 4.3 Suscripción Estudio

- ≈ ₡2,500 al mes o ≈ ₡25,000 al año.
- En el MVP, Estudio es una bandera que cambia la tarifa y los límites, sin cobro real.
- En la Etapa 2, si se vende dentro de la app, Apple y Google exigen su sistema de pagos (15% en ambos casos para desarrolladores pequeños y suscripciones).
- Cuando un artista cambia de plan, se actualiza la comisión configurada en su cuenta conectada de ONVO.

### 4.4 Boosts: reglas completas

**Qué se vende: personas alcanzadas, no vistas sueltas ni días.** Vender por tiempo en una plataforma pequeña equivale a cobrar por casi nada. Contar personas distintas es más fácil de entender y más difícil de inflar.

**Qué cuenta como persona alcanzada.** La publicación estuvo al menos 50% visible en pantalla durante al menos un segundo, frente a una cuenta que:

- No es del propio artista.
- Tiene al menos 7 días de antigüedad y algo de actividad.
- No sigue ya al artista (ese público ya lo ve en Seguidos; el boost es para llegar a gente nueva).

A cada persona se le muestra como máximo 2 veces, pero se cobra una sola.

**Paquetes (precio fijo y publicado, sin subasta):**

| Paquete | Precio |
|---|---|
| 1,000 personas | ≈ ₡1,000 (US$2) |
| 3,000 personas | ≈ ₡2,500 (US$5) |
| 10,000 personas | ≈ ₡6,000 (US$12) |

**Segmentación:**

- Usuarios que eligieron alguna de las categorías de la publicación (máximo 2, validadas por el clasificador de estilo).
- Opcionalmente, por provincia. Clave para eventos: un mariachi de Cartago no quiere pagar por público en Liberia.

**Dónde aparece:**

- Explorar: máximo 1 promocionado cada 8 elementos.
- Búsqueda: máximo 1 arriba, solo si coincide con la búsqueda.
- Nunca en Seguidos ni en notificaciones.
- Siempre con la etiqueta "Promocionado".
- Si el usuario oculta un promocionado, baja la entrega de ese boost.

**Antes de comprar,** el sistema muestra cuántas personas elegibles hay en la categoría y provincia, y la duración estimada. Si la audiencia elegible es menor que el paquete, ese paquete no se puede comprar: **no se vende lo que no se puede entregar**.

**Si no se completa:** el plazo máximo es de 30 días. Lo no entregado se devuelve como crédito para otro boost, en proporción a lo que faltó. Se usa crédito en lugar de dinero porque los reembolsos dentro de las tiendas de apps son un problema aparte.

**Durante el boost:**

- El artista puede pausarlo en cualquier momento.
- Si cancela, recibe crédito por lo no entregado.
- Si edita la imagen o la categoría, el boost se pausa y vuelve a revisión (evita la "obra comodín").

**Elegibilidad:** cuenta de artista con al menos 7 días, publicación aprobada por moderación y sin reportes pendientes, máximo 2 boosts activos por artista.

**Retiro por moderación:** si se retira por romper las reglas, no hay devolución.

**Saturación:** si una categoría tiene demasiados boosts activos, se reparten el espacio por turnos y la entrega se alarga. La estimación previa a la compra ya lo refleja.

**Reporte al artista:** personas alcanzadas, reacciones, visitas al perfil y consultas iniciadas desde el boost.

**Garantía:** se garantiza el alcance, no las ventas. Esta frase aparece textual en la pantalla de compra.

**Relación con la tarifa:** ninguna. El boost no modifica la tarifa del pedido.

**Cuándo le conviene al artista** (cuántos boosts de US$5 paga una sola venta extra, con el neto de Taller):

| Precio del pedido | Neto del artista | Boosts que paga una venta |
|---|---|---|
| US$20 | 17.37 | 3.5 |
| US$50 | 43.80 | 8.8 |
| US$100 | 87.85 | 17.6 |
| US$250 | 220.00 | 44 |
| US$1,000 | 880.75 | 176 |

Para piezas baratas conviene lo orgánico. De US$100 hacia arriba, una sola venta paga decenas de boosts.

**Costo para ArtísTica:** el boost no cuesta dinero (el espacio ya existe); cuesta atención del usuario. Por eso se controla con límites de densidad y no con precio. Es una fuente de ingreso menor y nunca justifica sacrificar la calidad del feed.

### 4.5 Ideas descartadas y por qué

| Idea original | Motivo del descarte |
|---|---|
| Cobrar por convertirse en artista | Vacía la plataforma: sin oferta no hay contenido, usuarios ni compradores. |
| Plan de US$3 | Demasiado cerca del de US$5; tras IVA y tienda de apps quedan ≈ US$2.25. |
| Boost que elimina la comisión de la venta | Canibaliza la tarifa justo en los pedidos de mayor valor y es explotable (boost de un día sincronizado con una venta ya negociada, obra comodín). Con la comisión por cuenta de ONVO, además liberaría todas las ventas del artista durante el boost. |
| Boost por tiempo | En categorías pequeñas se paga por casi nada. |
| Verificación pagada | Vacía el significado de la insignia. |
| Tarifa distinta por tipo de producto | Invita a clasificar mal y no es nativa en ONVO. |
| Venta de stock o catálogo | Contradice la filosofía y compite con Facebook Marketplace. |

### 4.6 Impuestos y comisiones de terceros

- **IVA de 13%** sobre la tarifa de servicio, la suscripción y los boosts. Si los precios lo incluyen, ArtísTica conserva ≈ 88.5%.
- **Tiendas de apps:** 15% sobre Estudio y boosts vendidos dentro de la app (Etapa 2). Encargos, eventos y obras físicas no pasan por esta regla.
- **Retención de 2%** en cobros con tarjeta, del lado del artista.

### 4.7 Orden de magnitud (ilustrativo)

**Supuestos:** ticket promedio de US$150, tarifa promedio de 7%, 300 suscriptores de Estudio y un objetivo de ≈ US$3,200 al mes (dos salarios modestos más infraestructura).

- Cada pedido deja ≈ US$9 netos después de IVA.
- Las suscripciones aportan ≈ US$1,200.
- El resto requiere **≈ 215 pedidos al mes, unos 7 por día**.

El negocio escala con el volumen contratado, no con la cantidad de suscriptores.

---

## 5. Arquitectura y stack técnico

### 5.1 Visión general

```
monorepo/
├── app/        React Native + Expo (Brian)
└── backend/    FastAPI (Esteban)
    ├── API     atiende a la app
    └── worker  IA, miniaturas, moderación, vencimientos y webhooks de pago
```

El backend se separa en dos servicios para que la IA y los procesos de pago no bloqueen a la app.

### 5.2 Stack

| Capa | Tecnología |
|---|---|
| Lenguaje backend | Python 3.12 |
| Framework y servidor | FastAPI + Uvicorn |
| Validación y configuración | Pydantic v2 + pydantic-settings |
| ORM y migraciones | SQLAlchemy 2.0 (async) + Alembic |
| Driver | psycopg 3 (async) |
| Verificación de tokens | PyJWT con PyJWKClient |
| Cliente HTTP | httpx (ONVO y pruebas) |
| Cola de trabajos | Tabla `jobs` en Postgres con `FOR UPDATE SKIP LOCKED` |
| Pagos | ONVO Pay en modo marketplace |
| Base de datos | Supabase (PostgreSQL 15) con pgvector y tsvector |
| Pooling | Supavisor (6543 para la app, 5432 para migraciones) |
| Autenticación | Supabase Auth: Google, Apple y correo |
| Almacenamiento | Supabase Storage con signed upload URLs |
| Despliegue | Docker, Railway, GitHub Actions |
| Calidad | Ruff, pytest, pre-commit |
| Errores | Sentry |
| App | React Native (Expo), Expo Router, TypeScript |
| Estado y datos en la app | Supabase JS, TanStack Query, Zustand |
| UI y formularios | NativeWind, React Hook Form + Zod, FlashList |
| Notificaciones | Expo Notifications |

Entornos: un proyecto de Supabase para desarrollo y otro para producción.

### 5.3 Decisiones técnicas clave

**ONVO Pay en modo marketplace.**
- Cada artista es una cuenta conectada y completa un onboarding alojado por ONVO, donde registra su cuenta IBAN.
- Los cobros se hacen en nombre del artista: la tarifa de ArtísTica cae en la cuenta principal y el neto se liquida directo al artista.
- ONVO está inscrita ante SUGEF para administrar recursos de terceros, así que **la custodia del dinero es de ONVO, no de ArtísTica**.
- La comisión se configura por cuenta conectada; cambia cuando el artista cambia de plan.

**Pago protegido por hitos.**
- ONVO no retiene fondos por semanas. La captura manual (autorizar ahora, cobrar después) solo existe para tarjeta en integraciones por API y vence si no se captura.
- Por eso la protección se construye con hitos: anticipo capturado al aceptar, saldo autorizado en la vista previa o al confirmar y capturado al aprobar o despachar.
- Un job del worker vigila las autorizaciones próximas a vencer para cancelar o avisar a tiempo.

**Ledger como registro, no como saldo.**
- Como ArtísTica no custodia dinero, el ledger registra y concilia pedidos, hitos y cobros contra ONVO. No existe una columna de saldo mutable.
- El estado del pedido y el estado del cobro deben cambiar en la misma transacción de base de datos.

**Seguridad de datos.**
- **RLS activo sin políticas permisivas** en todas las tablas. La anon key viaja dentro de la app, así que sin RLS cualquiera podría leer y escribir la base directamente. El backend entra con `service_role` y toda la autorización vive en FastAPI.
- Los tokens de Supabase se verifican contra el JWKS del proyecto (firma, `exp`, `aud`, `iss`), con las claves en caché.
- La `service_role` key nunca llega al cliente móvil.

**Base de datos.**
- SQLAlchemy async en todo; nunca se mezclan sesiones sincrónicas dentro de endpoints async.
- Supavisor en modo transacción no soporta prepared statements: el engine se crea con `prepare_threshold=None`.

**Cola de trabajos (worker).**
Tipos de job: miniaturas, embeddings, clasificación de estilo, moderación de imágenes, vigilancia de autorizaciones por vencer y procesamiento idempotente de webhooks de ONVO. Reintentos con backoff exponencial y estado `dead` al agotar intentos.

**Chat atado a consultas.**
Toda conversación cliente-artista pertenece a una consulta o a un pedido. Entre artistas, mensajes libres.

**pgvector.**
Similitud de estilo para recomendaciones en Explorar y detección de la misma imagen subida por cuentas distintas (obra robada o duplicada). Índice HNSW desde la migración inicial.

**Métricas.**
- Tabla `post_views`: una vista por usuario, por obra y por día, registrada de forma asíncrona.
- Todo se guarda en UTC y se convierte a `America/Costa_Rica` al consultar.
- Una vista materializada refrescada por el worker alimenta el panel.

**Medios.**
- Las imágenes se redimensionan en el teléfono antes de subir.
- El worker genera miniaturas (Pillow).
- El video es corto y limitado. El ancho de banda de Storage es el primer límite real de la plataforma.

**Inteligencia artificial.**
- Clasificador de estilo: valida que la categoría declarada coincida con el contenido (antifraude en boosts y descubrimiento).
- Detección de contenido generado por IA: marca para revisión humana.
- Moderación de imágenes NSFW.

### 5.4 Entidades principales

`profiles` (plan, `connected_account_id` de ONVO), `obras` (estado de exhibición o disponible, precio opcional), `publicaciones`, `servicios`, `consultas`, `pedidos` (tipo: encargo, evento, obra_disponible), `cobros` (anticipo, saldo), `mensajes`, `resenas`, `impulsos` (boosts), `post_views`, `reportes`, `moderation_actions`, `jobs`.

### 5.5 Pendientes técnicos

- **Capa de chat en tiempo real:** WebSockets en FastAPI o Supabase Realtime (esta última exige políticas RLS específicas para la tabla de mensajes).
- **Modelo de embeddings** para pgvector y dónde corre (API externa o dentro del worker).
- **Compras dentro de la app** (Etapa 2): una librería del lado de la app y un webhook del lado del backend.

### 5.6 Preguntas abiertas para ONVO

1. ¿Cuántos días dura una autorización antes de vencer?
2. ¿Se puede retrasar la liquidación al vendedor por transacción?
3. ¿El modo marketplace acepta SINPE Móvil o solo tarjeta?
4. ¿Se puede definir la comisión por cobro y no solo por cuenta?
5. ¿Quién absorbe contracargos y reembolsos después de liquidar, y se revierte la comisión del marketplace en un reembolso?
6. **La más importante:** ¿una persona física sin actividad inscrita en Hacienda puede completar el onboarding? Muchos artistas en Costa Rica son informales.

---

## 6. Estrategia de lanzamiento (go-to-market)

### 6.1 Dos nichos de entrada

1. **Música y baile para eventos:** bodas, quince años, eventos de empresa. Mariachis, bandas, grupos de baile.
2. **Encargos visuales:** retratos, ilustración, murales, logos.

Son los de mayor ticket y los que más sufren el problema del adelanto.

### 6.2 Los 100 artistas fundadores

- Reciben Estudio gratis durante 6 meses.
- Se consiguen a mano, antes del lanzamiento: escuelas de arte y música de las universidades, casas de cultura y ferias.
- Una app con 30 artistas buenos vale más que una con 300 perfiles vacíos.

### 6.3 Demanda

Se busca donde ya se contrata arte:

- Organizadores de bodas.
- Salones de eventos.
- Restaurantes y negocios que necesitan murales o identidad visual.

Un cliente empresarial repite y paga más que un particular.

### 6.4 Descubrimiento justo

La cuota de Nuevos talentos en Explorar demuestra que la visibilidad no depende de pagar un boost.

### 6.5 Métodos de pago

Ofrecer SINPE Móvil dentro de la app (si el modo marketplace de ONVO lo permite) reduce el costo para el artista y la principal razón para cerrar el trato afuera.

### 6.6 Costos iniciales

- Infraestructura: ≈ US$100 al mes.
- No invertir en publicidad hasta que los artistas reciban pedidos de forma orgánica.

### 6.7 Etapas

| Etapa | Alcance |
|---|---|
| **MVP (noviembre 2026)** | Público y Artista (Estudio como bandera, sin cobro real). Galería, publicaciones, Seguidos y Explorar. Pedidos de encargo, evento y obra disponible cobrados por ONVO marketplace en sandbox, con anticipo y saldo. Métricas (vistas, interacción, categorías, horarios). Clasificador de estilo. Reportes y moderación básica. Boost básico con segmentación y tope de densidad si el tiempo alcanza (es lo primero que se recorta). |
| **Etapa 2** | Cobro real de Estudio y boosts (compras dentro de la app), reseñas, agrupaciones, detección de datos de contacto en el chat, disputas completas y programa de artistas fundadores. |
| **Etapa 3** | Membresías de fans. Marketplace completo solo si los datos de obras disponibles lo justifican. |
| **Etapa 4** | Expansión regional. ONVO opera en otros países, así que la expansión no obliga a cambiar de pasarela. |

---

## 7. Riesgos, beneficios y mitigaciones

### 7.1 Lo que ganamos con este modelo

- **Un solo motor transaccional** para tres tipos de pedido.
- **Ticket más alto:** misma tarifa, más ingreso por pedido.
- **Ataca un dolor real y local:** el adelanto robado y el saldo impago.
- **Custodia regulada:** ONVO custodia el dinero; ArtísTica no se convierte en intermediario financiero.
- **Coherencia con la filosofía:** se vende la habilidad, no inventario.
- **Viabilidad del plazo:** un flujo completo para noviembre.
- **Menos pedidos necesarios** para sostener el negocio (≈ 215 al mes frente a ≈ 540).

### 7.2 Lo que perdemos y cómo lo compensamos

| Pérdida | Compensación |
|---|---|
| Compra impulsiva de productos | Obra disponible con "La quiero" y precio fijo |
| Volumen potencial de un marketplace | Revisión en Etapa 3 con datos reales |
| Mensajes directos libres cliente-artista | Chat atado a consultas; socialización pública en comentarios; mensajes libres entre artistas |
| Clientes recurrentes que vuelven a contratar por WhatsApp | Se acepta; el diseño apunta a capturar la primera contratación, que es la que necesita protección |

### 7.3 Fuga de clientes fuera de la app

Eliminar el chat no frena la fuga: el cliente encuentra al artista en Instagram en segundos. La estrategia es que el camino por dentro sea el más conveniente:

1. **Protección solo adentro:** anticipo y saldo protegidos, con disputa.
2. **Reputación solo adentro:** las reseñas vienen únicamente de pedidos completados.
3. **Aviso suave** al detectar datos de contacto en el chat.
4. **Perfil sin teléfonos ni WhatsApp.**
5. **SINPE Móvil dentro de la app,** si ONVO lo permite en modo marketplace.
6. **Tarifa moderada** (8% y 5%) para que la diferencia frente a cobrar afuera sea razonable.

### 7.4 Matriz de riesgos

| Área | Riesgo | Mitigación |
|---|---|---|
| Suscripciones | El plan gratuito alcanza y nadie sube a Estudio | Estudio se justifica por ahorro y herramientas, no castigando al gratuito; el negocio no depende de la suscripción |
| Boosts | Feed saturado; artistas pagan y no venden | Tope de densidad, venta por alcance, estimación previa y reporte de resultados |
| Tarifas | Fuga hacia SINPE fuera de la app | Medidas de la sección 7.3 |
| Contenido | Arte generado por IA o robado a otro artista | Clasificador para revisión humana; pgvector detecta duplicados entre cuentas |
| Recomendación | Terminar optimizando engagement por la puerta de atrás | Señales limitadas a categoría, similitud y recencia |
| Artistas | Los informales no completan el onboarding de ONVO | Pregunta 6 a ONVO; exhibir y recibir consultas sin onboarding, exigirlo solo al primer cobro |
| Usuarios | Acoso o spam por chat | Consultas atadas a servicios u obras; límite diario para cuentas recientes |
| Pagos | Una autorización vence antes de capturarse | Hitos, plazos de despacho y job de vigilancia de vencimientos |
| Fraude | Tarjetas robadas; artista que cobra el anticipo y desaparece | Antifraude de ONVO, anticipo acotado, límites a vendedores nuevos, reputación |
| Abuso | Cuentas falsas que se dan reacciones; categorías falsas para ampliar un boost | Peso de interacciones según antigüedad; el clasificador valida la categoría antes de aprobar un boost |
| Métricas | Vistas infladas | Una vista por usuario, por obra y por día; se excluyen las propias |
| Operación | Disputas que consumen horas humanas | Reglas por defecto claras y públicas; ventanas cortas |
| Infraestructura | Ancho de banda de medios agota la cuota | Miniaturas obligatorias, redimensionado en el teléfono, video limitado |
| Mercado | Costa Rica sola no alcanza la escala necesaria | Expansión regional en Etapa 4 |

### 7.5 Supuestos por validar

- Respuestas de ONVO a las 6 preguntas de la sección 5.6.
- Ticket promedio real de los dos nichos iniciales.
- Proporción de artistas que suben a Estudio.
- Disposición de los clientes a pagar dentro de la app frente a SINPE directo.
- Política concreta de cancelación de eventos y ventana de disputas.
