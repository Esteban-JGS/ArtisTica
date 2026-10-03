# ArtísTica

**Donde el trabajo se muestra, se conversa y se encarga.**

Documentación del proyecto

EIF409, Red social para artistas
Universidad Nacional de Costa Rica

Brian José Zeledón Esquivel
Esteban Granados Sibaja

II Avance, 9 de octubre de 2026

---

## Control de versiones

| Versión | Entrega | Fecha | Contenido |
|---|---|---|---|
| 1.0 | I Avance | Septiembre 2026 | Propuesta técnica y de diseño: stack tecnológico y pantallas |
| 2.0 | II Avance | 9 de octubre de 2026 | Propuesta a desarrollar, estrategia de distribución, esquema de generación de dinero, situaciones presentadas en el desarrollo y avance de desarrollo |

Este documento es la documentación oficial del proyecto y se actualiza en cada avance. Los montos en colones usan un tipo de cambio de referencia de ₡500 por US$1 y son aproximados.

---

## Índice

1. Propuesta a desarrollar
2. Estrategia de distribución
3. Esquema de generación de dinero
4. Situaciones presentadas en el desarrollo
5. Avance de desarrollo
6. Anexo: glosario

---

## 1. Propuesta a desarrollar

### 1.1 El problema

En Costa Rica, contratar arte funciona hoy con tres herramientas que no fueron pensadas para eso:

| Herramienta | Qué resuelve | Qué deja sin resolver |
|---|---|---|
| Instagram | Es la vitrina: permite ver el trabajo del artista | No permite contratar ni cobrar |
| WhatsApp | Permite negociar el encargo | No deja registro formal ni reglas |
| SINPE Móvil | Permite pagar rápido y sin costo | No ofrece protección a ninguna de las partes |

El resultado es desconfianza en los dos sentidos. El cliente teme pagar el adelanto y que el artista desaparezca o entregue algo distinto a lo acordado. El artista teme hacer el trabajo, o presentarse al evento, y que el cliente no pague el saldo.

### 1.2 La solución

**ArtísTica es donde en Costa Rica se contrata arte hecho por personas, con el pago protegido.**

No es solo una red social para artistas: es el lugar donde una persona descubre a un artista y lo contrata con confianza. La parte social (galería, feed, comentarios y reacciones) existe para alimentar el momento de la contratación.

ArtísTica une la vitrina y la transacción protegida en un mismo lugar. El pago se hace por hitos dentro de la aplicación, el dinero lo custodia una entidad financiera regulada y, si algo sale mal, existe un proceso de disputa.

### 1.3 Propuesta de valor

**Para quien contrata:**

- El anticipo y el saldo se pagan por hitos. El dinero no se pierde si algo sale mal, y existe un proceso de disputa.
- Las reseñas son reales: solo provienen de trabajos completados dentro de la aplicación.
- Encargos, eventos y obras terminadas se contratan con un mismo flujo.

**Para el artista:**

- Portafolio, clientes y cobro seguro en un solo lugar.
- Un panel que muestra qué obras generan consultas reales, no solo reacciones.
- Publicar y abrir comisiones es gratuito.

### 1.4 Usuarios

| Rol | Descripción |
|---|---|
| **Público** | Gratuito. Explora, sigue, reacciona, comenta, consulta a artistas, contrata y compra obras disponibles. No publica obra |
| **Artista, plan Taller** | Gratuito. Publica, abre comisiones y recibe pedidos sin límite. Tarifa de servicio de 8% |
| **Artista, plan Estudio** | Suscripción de ≈ ₡2,500 al mes. Tarifa de 5% y herramientas profesionales |
| **Administración y moderación** | Atiende reportes, revisa contenido sospechoso de haber sido generado por IA y resuelve disputas |
| **Agrupación** (etapa 2) | Perfil con varios miembros administradores: bandas, mariachis y compañías de baile |

### 1.5 Modelo operativo: comisiones abiertas

ArtísTica funciona con **comisiones abiertas**: el artista muestra lo que hace y declara que acepta trabajos. No sube productos a una tienda, porque lo que se vende es su habilidad, no un inventario.

Hay un solo motor de pedidos con tres tipos:

| Tipo de pedido | Ejemplo | Cómo se cobra |
|---|---|---|
| **Encargo** | Un retrato, un mural, un logo | Anticipo al aceptar la cotización. El saldo se autoriza cuando el artista entrega una vista previa con marca de agua, y se cobra cuando el cliente la aprueba. Después se libera el archivo final |
| **Evento** | Un mariachi para una boda, un grupo de baile para quince años | Anticipo al reservar la fecha. Saldo antes del evento |
| **Obra disponible** | Una pintura ya terminada con precio fijo | Se autoriza al confirmar la compra y se cobra cuando el artista despacha con número de guía |

Toda contratación sigue el mismo camino:

1. **Consulta.** El cliente abre una conversación sobre un servicio o una obra del artista.
2. **Cotización.** El artista envía una propuesta formal con descripción, plazo y precio. Mientras el cliente no la acepte, el artista puede ajustarla: así funciona la contraoferta.
3. **Cobros por hitos.** Cada pedido tiene uno o más cobros, que la pasarela ejecuta.
4. **Entrega y ventana de disputa.** Después de la entrega hay un plazo para reclamar.
5. **Reseña.** Ambas partes califican el pedido completado.

Toda conversación entre cliente y artista nace atada a una consulta. No existe el mensaje directo suelto, para que cada conversación quede ligada a un posible pedido y sirva como evidencia en una disputa. Entre artistas, los mensajes son libres.

### 1.6 Principios del producto

1. **Arte hecho por personas.** Se prohíbe el contenido generado por IA. Un clasificador marca lo sospechoso para revisión humana, y nunca bloquea una cuenta de forma automática, porque acusar a un artista humano por un falso positivo es el peor error posible para esta comunidad.
2. **Feed auténtico.** El feed de Seguidos es cronológico y nunca lleva contenido promocionado. Explorar se ordena por las categorías que el usuario eligió, no por predicción de comportamiento.
3. **Artista, no tienda.** Se vende la habilidad del artista. No hay catálogo, existencias ni reventa.
4. **Métricas honestas.** El panel del artista mide respuesta real, como consultas y conversión, no viralidad.
5. **Lo esencial es gratis.** Nunca se cobra por publicar, abrir comisiones, recibir pedidos, la protección del pago ni la verificación de identidad.

### 1.7 Competencia y posicionamiento

| Alternativa | Fortaleza | Por qué no resuelve el problema |
|---|---|---|
| Instagram | Audiencia enorme y vitrina gratuita | Vitrina sin transacción |
| WhatsApp y SINPE Móvil | Inmediatos y sin costo | Transacción sin protección ni reputación |
| Fiverr y plataformas globales | Protegen el pago | Cobran en dólares y no cubren contrataciones locales, como un mariachi para el sábado |

La ventaja defendible a largo plazo es **la reputación acumulada**. Un artista con decenas de encargos completados y reseñados dentro de ArtísTica no se va a otra plataforma a empezar de cero.

### 1.8 Alcance por etapas

| Etapa | Alcance |
|---|---|
| **MVP, entrega académica de noviembre de 2026** | Roles Público y Artista, con el plan Estudio activo como configuración pero sin cobro real. Galería, publicaciones, feed de Seguidos y Explorar. Pedidos de encargo, evento y obra disponible con anticipo y saldo, contra el entorno de pruebas de la pasarela. Métricas, clasificador de estilo, reportes y moderación básica |
| **Etapa 2** | Cobro real de la suscripción y de las promociones, reseñas, agrupaciones, detección de datos de contacto en el chat, disputas completas y programa de artistas fundadores |
| **Etapa 3** | Membresías de fans. Marketplace completo, solo si los datos de obras disponibles lo justifican |
| **Etapa 4** | Expansión regional |

### 1.9 Arquitectura

El proyecto es un repositorio único con dos módulos y dos responsables:

| Módulo | Tecnología | Responsable |
|---|---|---|
| `mobile/` | React Native con Expo, Expo Router y TypeScript | Brian Zeledón Esquivel |
| `backend/` | Python 3.12, FastAPI, SQLAlchemy asíncrono y un worker de trabajos en segundo plano | Esteban Granados Sibaja |

La base de datos, la autenticación y el almacenamiento de archivos son de Supabase, sobre PostgreSQL 15 con pgvector. Los pagos se procesan con ONVO Pay en modo marketplace. El stack completo, con la justificación de cada herramienta, está en la versión 1.0 de este documento.

Tres decisiones de arquitectura cambiaron desde el I Avance y se explican en la sección 4: la protección del pago ya no es un escrow propio, la seguridad a nivel de filas de la base de datos está activa, y la pasarela de pagos quedó detrás de un contrato abstracto.

---

## 2. Estrategia de distribución

### 2.1 Canal del producto

ArtísTica se distribuye como **aplicación móvil para iOS y Android**, a través de App Store y Google Play. Las versiones se compilan con EAS, el servicio de compilación de Expo, lo que permite publicar en las dos tiendas desde un mismo código.

Antes del lanzamiento público, la aplicación se distribuye como **beta cerrada** a los artistas fundadores, por medio de los canales de prueba de cada tienda. Así la plataforma se abre al público con oferta real ya cargada.

### 2.2 El reto principal: arrancar un mercado de dos lados

Una plataforma de contratación tiene un problema de arranque: sin artistas no llegan clientes, y sin clientes los artistas no se quedan. La estrategia ataca primero la oferta, con artistas buenos y perfiles completos, y después la demanda, buscándola donde ya se contrata arte.

El criterio es de calidad sobre cantidad: **una aplicación con 30 artistas buenos vale más que una con 300 perfiles vacíos.**

### 2.3 Dos nichos de entrada

| Nicho | Ejemplos | Por qué se empieza por aquí |
|---|---|---|
| **Música y baile para eventos** | Mariachis, bandas, grupos de baile para bodas, quince años y eventos de empresa | Ticket alto y el problema del adelanto es muy frecuente |
| **Encargos visuales** | Retratos, ilustración, murales y logos | Ticket alto y entrega verificable con vista previa |

### 2.4 Oferta: los 100 artistas fundadores

- Los primeros 100 artistas reciben el plan Estudio gratis durante seis meses.
- Se reclutan de forma presencial, antes del lanzamiento, en escuelas de arte y música de las universidades, casas de cultura y ferias.
- Reciben acompañamiento directo del equipo durante el arranque.

### 2.5 Demanda: donde ya se contrata arte

- **Organizadores de bodas y salones de eventos**, que contratan música y baile con frecuencia.
- **Restaurantes y negocios** que necesitan murales o identidad visual.
- **Particulares** que organizan bodas, quince años y fiestas, o que buscan retratos e ilustraciones.

Se prioriza al cliente empresarial, porque repite y paga más que un particular.

### 2.6 Descubrimiento justo

Explorar reserva una cuota fija para **Nuevos talentos**, artistas con pocos seguidores. Demuestra que la visibilidad en ArtísTica no depende de pagar una promoción, y le da a cada artista nuevo una oportunidad real desde el primer día.

### 2.7 Mantener la contratación dentro de la aplicación

Eliminar el chat no evita que un cliente contrate por fuera: encuentra al artista en Instagram en segundos. La estrategia es que el camino por dentro sea el más conveniente:

1. **Protección solo adentro:** anticipo y saldo protegidos, con proceso de disputa.
2. **Reputación solo adentro:** las reseñas vienen únicamente de pedidos completados en la aplicación.
3. **Aviso informativo:** si en el chat aparecen teléfonos, "SINPE" o "WhatsApp", se recuerda que fuera de la aplicación no hay protección ni reseña. Informa, no bloquea.
4. **Perfil sin teléfonos ni enlaces de WhatsApp.** El enlace a Instagram sí se permite, porque es vitrina y no canal de cobro.
5. **SINPE Móvil dentro de la aplicación,** si la pasarela lo permite en modo marketplace.
6. **Tarifa moderada,** de 8% y 5%, para que la diferencia frente a cobrar por fuera sea razonable.

### 2.8 Inversión y expansión

- No se invierte en publicidad pagada hasta que los artistas reciban pedidos de forma orgánica.
- La infraestructura inicial cuesta cerca de US$100 al mes.
- El primer mercado es Costa Rica. La expansión regional está prevista para la etapa 4, y como ONVO Pay opera en otros países, no obliga a cambiar de pasarela.

---

## 3. Esquema de generación de dinero

### 3.1 Fuentes de ingreso

| Fuente | Mecanismo | Rol |
|---|---|---|
| **Tarifa por pedido** | 8% en el plan Taller, 5% en Estudio | Principal. ArtísTica gana solo cuando el artista gana |
| **Suscripción Estudio** | ≈ ₡2,500 al mes | Secundaria. Para artistas que ya venden |
| **Promociones** | Paquetes por alcance de personas | Complementaria y menor. Etapa 2 |
| **Membresías de fans** | Apoyo mensual del público a un artista | Futura. Etapa 3 |

El negocio escala con el volumen contratado, no con la cantidad de suscriptores.

### 3.2 Tarifa por pedido

- Aplica a los tres tipos de pedido.
- Es una sola tarifa por plan. No varía por tipo de pedido, porque eso invita a clasificar mal los pedidos.
- **Monto mínimo por pedido: ₡2,500 (≈ US$5).** El costo fijo de procesamiento golpea proporcionalmente más a los montos pequeños.
- El costo de procesamiento de la pasarela (tarjeta: 3.9% más US$0.25; SINPE Móvil: 1.5%) y la retención tributaria de 2% se descuentan del lado del artista. La tarifa de ArtísTica es ingreso limpio para la plataforma.

Ejemplos con pago por tarjeta, en dólares:

| Precio del pedido | Taller: ArtísTica recibe | Taller: el artista recibe | Estudio: ArtísTica recibe | Estudio: el artista recibe |
|---|---|---|---|---|
| 20 | 1.60 | 17.37 | 1.00 | 17.97 |
| 50 | 4.00 | 43.80 | 2.50 | 45.30 |
| 100 | 8.00 | 87.85 | 5.00 | 90.85 |
| 250 | 20.00 | 220.00 | 12.50 | 227.50 |
| 1,000 | 80.00 | 880.75 | 50.00 | 910.75 |

Con SINPE Móvil, en un pedido de US$1,000 el procesamiento baja de US$39.25 a US$15.

### 3.3 Suscripción Estudio

**Precio:** ≈ ₡2,500 al mes, o ≈ ₡25,000 al año.

Un artista que no vende no va a pagar, y está bien: el negocio vive de la tarifa por pedido. Estudio es para quien ya genera trabajo, con cuatro argumentos:

1. **Ahorra dinero.** La tarifa baja de 8% a 5%. Con esa diferencia, Estudio se paga solo a partir de ≈ ₡85,000 al mes en pedidos.
2. **Organiza el trabajo:** calendario sincronizado, servicios ilimitados, plantillas de cotización y cupos de comisiones.
3. **Muestra qué funciona:** métricas completas orientadas a decisiones.
4. **Da presencia:** perfil personalizable, obras destacadas y una promoción mensual incluida.

**Ejemplo:** un grupo musical con cuatro contrataciones de ₡150,000 al mes paga ₡48,000 de tarifa en Taller. En Estudio paga ₡30,000 de tarifa más ₡2,500 de suscripción: ahorra más de ₡15,000 al mes.

**Cambio de plan.** El plan cambia de inmediato, pero cada pedido conserva la tarifa del plan vigente cuando se creó. Si un artista sube de Taller a Estudio, sus pedidos abiertos siguen al 8% y los que se crean después van al 5%. Así nadie paga una tarifa distinta a la que aceptó al cotizar.

### 3.4 Promociones por alcance

Se venden **personas alcanzadas**, no días ni vistas sueltas. Una persona cuenta como alcanzada cuando la publicación estuvo al menos 50% visible durante un segundo, frente a una cuenta que no es del artista, tiene al menos siete días de antigüedad y no lo sigue todavía.

| Paquete | Precio |
|---|---|
| 1,000 personas | ≈ ₡1,000 |
| 3,000 personas | ≈ ₡2,500 |
| 10,000 personas | ≈ ₡6,000 |

Reglas que protegen la calidad del feed:

- Nunca aparecen en Seguidos ni en notificaciones, y siempre llevan la etiqueta "Promocionado".
- En Explorar, como máximo una publicación promocionada cada ocho elementos.
- Antes de comprar, el sistema muestra cuántas personas elegibles hay. **No se vende lo que no se puede entregar.**
- **Se garantiza el alcance, no las ventas.** Esta frase aparece en la pantalla de compra.

Las promociones quedaron fuera del MVP de noviembre y se implementan en la etapa 2.

### 3.5 Reglas del dinero en cada pedido

| Regla | Valor |
|---|---|
| Anticipo de encargos y eventos | El artista lo elige entre 30% y 50% en cada cotización. Si no elige, 50% |
| Ventana de disputa | 7 días desde la entrega. Para eventos, desde la fecha del evento. Si nadie reclama, el pedido se completa solo |
| Cancelación de un evento por el cliente | Más de 30 días de anticipación: se devuelve el 100%. De 7 a 30 días: 50%. Menos de 7 días: nada |
| Cancelación de un encargo por el cliente | Antes del anticipo, sin costo. Después, el anticipo no se devuelve |
| Cancelación o incumplimiento del artista | Se devuelve el 100% de lo cobrado |
| Anticipo en una disputa | Moderación puede ordenar devolverlo, total o parcialmente |
| Evento cuya fecha llega con el saldo impago | Cuenta como cancelación del cliente con menos de 7 días |

Todas estas reglas son configurables sin modificar el código.

### 3.6 Lo que nunca se cobra

Publicar, abrir comisiones, recibir pedidos y la cantidad de pedidos activos, la protección del pago y las disputas, aparecer en la exploración orgánica, y la verificación de identidad.

**Razón:** si el plan gratuito se queda sin poder recibir trabajo, el artista se va a WhatsApp y ArtísTica pierde la tarifa, que representa más dinero que la suscripción. Por la misma razón la verificación no se vende: si la insignia se compra, deja de significar "esta persona es quien dice ser" y pasa a significar "esta persona pagó".

### 3.7 Costos

| Costo | Monto o regla |
|---|---|
| Infraestructura | ≈ US$100 al mes al inicio: base de datos, hosting, monitoreo de errores y cuentas de desarrollador |
| IVA | 13% sobre la tarifa, la suscripción y las promociones. ArtísTica conserva ≈ 88.5% |
| Tiendas de aplicaciones | 15% sobre la suscripción y las promociones vendidas dentro de la aplicación, desde la etapa 2. Encargos, eventos y obras físicas no pagan esta comisión |
| Artistas fundadores | Seis meses de Estudio gratis para los primeros 100 |
| Horas humanas | Moderación, disputas y soporte |
| Legal | Términos de uso y cumplimiento de la Ley 8968 de protección de datos |

### 3.8 Orden de magnitud

Supuestos ilustrativos: ticket promedio de US$150, tarifa promedio de 7%, 300 suscriptores de Estudio, y una meta de ≈ US$3,200 al mes, equivalente a dos salarios modestos más la infraestructura.

- Cada pedido deja ≈ US$9 netos después de IVA.
- Las suscripciones aportan ≈ US$1,200.
- El resto requiere **≈ 215 pedidos al mes, unos 7 por día.**

### 3.9 Ideas de monetización descartadas

| Idea | Por qué se descartó |
|---|---|
| Cobrar por convertirse en artista | Vacía la plataforma: sin oferta no hay contenido, ni usuarios, ni compradores |
| Un plan de US$3 | Demasiado cerca del de US$5; después de IVA y tiendas quedan ≈ US$2.25 |
| Una promoción que elimina la tarifa de la venta | Canibaliza la tarifa justo en los pedidos de mayor valor y se presta a abuso |
| Promociones por tiempo | En categorías pequeñas se paga por casi nada |
| Verificación pagada | Le quita el significado a la insignia |
| Tarifa distinta por tipo de pedido | Invita a clasificar mal y la pasarela no la soporta |
| Venta de inventario o catálogo | Contradice la propuesta y compite con Facebook Marketplace |

---

## 4. Situaciones presentadas en el desarrollo

Cada situación se presenta con su impacto y con la forma en que se resolvió.

### 4.1 Producto y modelo de negocio

#### Cambio de modelo: de escrow propio a pago custodiado por una entidad regulada

**Situación.** La propuesta del I Avance planteaba una red social solo de artistas, con el pago retenido en un escrow propio hasta aprobar la entrega.

**Impacto.** Retener y liberar dinero de terceros convierte a la plataforma en intermediario financiero, una actividad que en Costa Rica exige inscripción ante la SUGEF. Además, sin un rol de usuario consumidor, la plataforma no tenía quién contratara.

**Resolución.** La custodia pasó a ONVO Pay, que está inscrita ante la SUGEF para administrar recursos de terceros. La protección del pago se construye con cobros por hitos: anticipo, saldo autorizado y saldo capturado. ArtísTica no guarda ningún saldo propio: solo registra y concilia lo que ocurre en la pasarela. Volvió el rol Público, que contrata y compra.

#### Marketplace de productos frente a comisiones abiertas

**Situación.** Se evaluó vender obras como en una tienda, con existencias y envíos.

**Impacto.** Exigía dos motores de pago, competía con Facebook Marketplace e Instagram, y con un ticket promedio bajo hacían falta ≈ 540 pedidos al mes para sostener el negocio.

**Resolución.** Se eligió el modelo de comisiones abiertas, con un solo motor para tres tipos de pedido. La venta directa se cubre con la "obra disponible" a precio fijo. Con un ticket mayor, alcanzan ≈ 215 pedidos al mes.

#### La palabra "comisión" tenía dos significados

**Situación.** "Comisión" se usaba tanto para el trabajo a pedido como para el porcentaje que cobra la plataforma.

**Impacto.** Generaba ambigüedad en los documentos, en la interfaz y en el código.

**Resolución.** Se definió un glosario obligatorio: **encargo** para el trabajo a pedido y **tarifa de servicio** para el porcentaje. El glosario completo está en el anexo.

#### La consulta: ¿estado del pedido o entidad propia?

**Situación.** El diseño trataba la consulta a la vez como el primer estado de un pedido y como un registro aparte.

**Impacto.** Sin resolverlo no se podía construir la base de datos.

**Resolución.** La consulta es una entidad propia, por tres razones. La obra disponible se compra sin negociación, así que no tiene consulta previa. La métrica de conversión de consulta a pedido exige contar las consultas que nunca se convirtieron. Y la conversación debe existir aunque nunca haya cotización.

#### Reglas de dinero sin definir y contradicciones entre ellas

**Situación.** El porcentaje del anticipo, la ventana de disputa y la política de cancelación de eventos estaban pendientes. Además, un punto decía que el anticipo nunca se devuelve, y otro que una disputa puede terminar en reembolso.

**Impacto.** Sin estas reglas no se podía programar la máquina de estados de los pedidos.

**Resolución.** Se definieron valores por defecto, configurables sin tocar el código (sección 3.5). La contradicción se resolvió así: el anticipo no se devuelve cuando el cliente cancela por su cuenta, pero sí cuando el artista incumple, y la disputa es justamente el mecanismo para establecer ese incumplimiento.

#### Pedidos que se quedaban trabados por el paso del tiempo

**Situación.** Al programar la máquina de estados se detectaron casos sin salida: un evento cuya fecha llega con el saldo sin pagar, y una autorización de pago que vence antes de que el cliente apruebe la entrega.

**Impacto.** El pedido quedaba detenido para siempre, sin poder completarse ni cancelarse.

**Resolución.** El saldo impago al llegar el evento cuenta como cancelación tardía del cliente. Una autorización vencida se puede renovar durante siete días y, si no se renueva, el artista puede abrir una disputa.

#### Cambio de plan con pedidos abiertos

**Situación.** Al revisar la pasarela se encontró que ONVO tiene una sola tarifa por cuenta, mientras que ArtísTica fija la tarifa en cada pedido.

**Impacto.** Si un artista sube de plan con pedidos abiertos, la pasarela podría cobrar todos sus pedidos con la tarifa nueva.

**Resolución.** El plan cambia de inmediato y cada pedido conserva la tarifa con la que se creó. Mientras un artista tenga pedidos abiertos con tarifas distintas, el sistema ajusta la tarifa de su cuenta justo antes de cada cobro. Se consultó a ONVO si existe una tarifa por cobro, que haría innecesario el ajuste.

### 4.2 Técnicas

#### El backend inicial no se podía ejecutar

**Situación.** La primera versión del backend se construyó con el modelo anterior y nunca se había ejecutado. Al auditarla se encontraron 14 defectos: una dependencia faltante, un parámetro de otro controlador de base de datos, una configuración de migraciones que no cargaba, un chequeo de salud que apuntaba a una ruta inexistente, y una integración continua que nunca se disparaba en la rama de trabajo.

**Impacto.** Ninguna prueba podía correr, así que ningún avance se podía verificar.

**Resolución.** Se dedicó una etapa completa a sanear el proyecto antes de escribir funcionalidad. Desde entonces la integración continua corre en cada cambio, y pasa en verde.

#### Seguridad de la base de datos

**Situación.** El I Avance proponía manejar toda la autorización en la API, sin seguridad a nivel de filas en la base de datos.

**Impacto.** La aplicación móvil incluye una clave pública de Supabase. Sin seguridad a nivel de filas, cualquiera que extraiga esa clave del instalador podría leer y escribir la base de datos directamente.

**Resolución.** La seguridad a nivel de filas está activa en todas las tablas y sin ninguna política que dé acceso. La aplicación nunca lee tablas directamente: todo pasa por la API, que entra con una credencial de servidor y decide qué puede hacer cada usuario.

#### Huecos en el esquema de la base de datos

**Situación.** Después de construir el esquema se detectaron relaciones que faltaban: no había dónde guardar la vista previa ni el archivo final de un encargo, ni el motivo y la resolución de una disputa, y nada impedía vender dos veces la misma obra.

**Impacto.** Varias etapas posteriores no se habrían podido construir.

**Resolución.** Como la base todavía no tenía datos en ningún ambiente, se corrigió reescribiendo la migración inicial en lugar de acumular parches. Se agregaron las tablas de entregables y disputas, el estado "vendida" de una obra, y un índice único que impide a nivel de base de datos dos ventas vivas de la misma obra.

#### Incertidumbre sobre la pasarela de pagos

**Situación.** Seis aspectos de ONVO Pay que condicionan el diseño no estaban documentados: cuánto dura una autorización, si SINPE Móvil funciona en modo marketplace, si la tarifa puede fijarse por cobro, entre otros.

**Impacto.** Construir directamente contra ONVO habría atado el diseño a supuestos que podían resultar falsos.

**Resolución.** La pasarela quedó detrás de un contrato abstracto con dos implementaciones: una pasarela simulada completa, que se usa en las pruebas y en la demostración, y el adaptador de ONVO. Cada incógnita es una capacidad declarada del adaptador. Cambiar de pasarela cuesta un adaptador, no rediseñar el sistema. Las preguntas se formalizaron en un documento de consultas para ONVO.

#### Hallazgos en la documentación de ONVO

**Situación.** Al revisar la documentación oficial de ONVO se encontró que los avisos automáticos de pago (webhooks) no firman su contenido, que no hay un mecanismo de idempotencia, y que no se informa la vigencia de una autorización.

**Impacto.** Sin medidas, un aviso alterado podría mover dinero, y reintentar una operación después de una falla de red podría cobrar dos veces.

**Resolución.** Tres reglas. Nunca se mueve dinero solo por un aviso: antes se consulta el cobro a la pasarela. Una operación de cobro o reembolso que falla por tiempo de espera no se reintenta automáticamente. Y se supone una vigencia conservadora de cinco días para las autorizaciones, configurable.

#### Cambios en las herramientas de desarrollo

**Situación.** Una versión nueva de la herramienta de análisis de código activó reglas que la configuración no declaraba, y modificó archivos que no debían cambiar. Además, el controlador asíncrono de PostgreSQL no funciona con el ciclo de eventos por defecto de Windows.

**Impacto.** Las verificaciones daban resultados distintos según la versión instalada, y las migraciones no corrían en las computadoras del equipo.

**Resolución.** La política de análisis de código quedó declarada de forma explícita y con la versión fijada. Las migraciones y las pruebas seleccionan el ciclo de eventos compatible cuando corren en Windows.

### 4.3 Proceso y trabajo en equipo

#### Dos personas trabajando sobre un mismo repositorio

**Situación.** Al principio los cambios se hacían directo sobre la rama de integración, y en una ocasión un cambio quedó en la rama equivocada sin que se notara.

**Impacto.** Riesgo de pisar el trabajo del otro y de perder cambios.

**Resolución.** Se adoptó un flujo formal: territorios separados por módulo, una rama por unidad de trabajo, pull requests con una plantilla común que exige evidencia de verificación, e integración continua en cada pull request. Antes de subir un cambio se verifica el nombre de la rama.

#### Integración entre la aplicación y la API

**Situación.** La aplicación móvil y el backend avanzaron en paralelo: la aplicación tiene sus pantallas con datos de ejemplo, y el backend tiene el dominio de pedidos y pagos probado, pero todavía sin endpoints de negocio.

**Impacto.** La integración es el principal riesgo para la entrega final. Además, ONVO exige que la tarjeta se registre desde la aplicación con una clave pública, lo que agrega trabajo en el módulo móvil.

**Resolución.** Los endpoints se construyen en las próximas etapas, en el orden que necesita la aplicación: identidad, obras, feed, consultas y pedidos. La forma de registrar la tarjeta se coordina entre los dos módulos. Que la tarjeta nunca pase por la API es, además, lo correcto en seguridad.

---

## 5. Avance de desarrollo

### 5.1 Estado general

| Componente | Estado |
|---|---|
| Aplicación móvil: pantallas y diseño | Avanzado. Pantallas principales implementadas con datos de ejemplo |
| Aplicación móvil: inicio de sesión | Cliente de Supabase configurado |
| Backend: base ejecutable, integración continua y despliegue | Completo |
| Backend: esquema de base de datos | Completo para el MVP |
| Backend: reglas de pedidos y cobros | Completo y probado |
| Backend: capa de pagos | Completa, con pasarela simulada y adaptador de ONVO |
| Backend: endpoints de negocio | Pendiente. Hoy la API responde solo el chequeo de salud |
| Integración entre aplicación y API | Pendiente |

### 5.2 Backend

El backend avanza por etapas con alcance cerrado. Cada una se verifica con pruebas automatizadas antes de integrarse.

| Etapa | Entregó |
|---|---|
| Saneamiento | Proyecto instalable y migrable, con análisis de código y pruebas en verde, y la integración continua activa en la rama de trabajo |
| Esquema de dominio | 21 tablas y 14 tipos enumerados: perfiles, seguimientos, obras, servicios, publicaciones, comentarios, reacciones, archivos, consultas, mensajes, pedidos, cobros, entregables, disputas, reseñas, conciliación de pagos, avisos de la pasarela, métricas, reportes, acciones de moderación y trabajos en segundo plano. Seguridad a nivel de filas activa en todas |
| Máquina de estados | Todas las transiciones de pedidos y cobros, validadas por tipo de pedido. Cálculo exacto de anticipo y saldo, plan de cancelación, disputas y vencimientos. Cada cambio de un pedido y su cobro ocurre en una sola transacción |
| Capa de pagos | Contrato de pasarela, pasarela simulada completa para pruebas y demostración, y adaptador de ONVO basado en su documentación oficial |

**Indicadores al cierre de este avance:**

- 207 pruebas automatizadas, todas en verde.
- Integración continua en verde en cada pull request y en cada integración a la rama principal de trabajo.
- Ninguna columna de saldo en la base de datos: ArtísTica no custodia dinero.
- Todos los montos se manejan con aritmética decimal exacta, nunca con punto flotante.

### 5.3 Aplicación móvil

Pantallas implementadas, con el rediseño visual de estilo Liquid Glass:

- **Inicio:** feed con estética de tablero de corcho, con publicaciones como notas, y selector entre Seguidos y Para ti.
- **Explorar, Mensajes y Perfil.**
- **Crear,** con acceso desde la barra de navegación flotante.
- **Comentarios y Compartir,** como hojas deslizables.
- **Inicio de sesión** con galería de obras.
- **Navegación flotante** que se oculta al desplazarse, y **fondo personalizable** por el usuario.

Las pantallas usan datos de ejemplo hasta que la API exponga sus endpoints.

### 5.4 Lo que falta para la entrega final

| Etapa | Contenido |
|---|---|
| Identidad y planes | Perfiles, roles, cambio de plan y registro del artista ante la pasarela |
| Obras, servicios y archivos | Galería, servicios con precio y carga de imágenes directa al almacenamiento |
| Feed | Seguidos cronológico y Explorar por categorías |
| Consultas y chat | Conversaciones atadas a consultas, con el aviso de datos de contacto |
| Pedidos | Endpoints que conectan la máquina de estados con la pasarela |
| Avisos de pago | Recepción idempotente de avisos de la pasarela y vigilancia de autorizaciones por vencer |
| Métricas | Vistas por usuario y por día, y el panel del artista |
| Moderación | Reportes y clasificación de estilo para revisión humana |
| Integración | Conexión de las pantallas de la aplicación con la API |

La demostración de noviembre usa la pasarela simulada, que se comporta como una real: autorizaciones que vencen, rechazos y avisos firmados.

### 5.5 Riesgos para la entrega final

| Riesgo | Mitigación |
|---|---|
| Plazo: quedan ocho etapas de backend y la integración | Las promociones ya se recortaron del MVP. Si hace falta recortar más, Explorar queda solo por categorías |
| ONVO no responde las consultas a tiempo | La demostración no depende de ONVO: usa la pasarela simulada |
| La integración entre aplicación y API llega tarde | Los endpoints se construyen en el orden en que la aplicación los necesita |

---

## 6. Anexo: glosario

| Término | Significado |
|---|---|
| **Encargo** | Trabajo hecho a pedido para un cliente |
| **Evento** | Contratación con fecha y lugar: música, baile o presentaciones |
| **Obra** | Pieza de la galería de un artista. Puede ser solo de exhibición o estar disponible para la venta |
| **Obra disponible** | Obra terminada que el artista ofrece a precio fijo |
| **Publicación** | Lo que aparece en el feed |
| **Servicio** | Paquete con precio que ofrece el artista, por ejemplo "Serenata de 30 minutos" |
| **Consulta** | Conversación que abre un cliente sobre un servicio o una obra. Puede convertirse en pedido |
| **Pedido** | Toda transacción. Tiene un tipo (encargo, evento u obra disponible) y uno o más cobros |
| **Cobro** | Cada pago parcial de un pedido: anticipo, saldo o total |
| **Tarifa de servicio** | Porcentaje que cobra ArtísTica sobre cada pedido |
| **Taller y Estudio** | Planes del artista: el gratuito y el de suscripción |
| **Pasarela** | Entidad que procesa los pagos y custodia el dinero |
| **Cuenta conectada** | Cuenta de un artista dentro de la pasarela, a la que se liquida su dinero |
