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

| Versión | Fecha | Contenido |
|---|---|---|
| 1.0 | Septiembre 2026 | I Avance: propuesta técnica y de diseño |
| 2.0 | Octubre 2026 | II Avance: propuesta, distribución, generación de dinero, situaciones y avance |

## Índice

1. Propuesta a desarrollar
2. Estrategia de distribución
3. Esquema de generación de dinero
4. Situaciones presentadas en el desarrollo
5. Avance de desarrollo
6. Anexo: glosario

---

## 1. Propuesta a desarrollar

### 1.1 Problema

En Costa Rica, contratar a un artista se resuelve hoy con tres herramientas que no fueron diseñadas para eso:

| Herramienta | Qué resuelve | Qué deja sin resolver |
|---|---|---|
| Instagram | Muestra el trabajo del artista | No permite contratar ni cobrar |
| WhatsApp | Permite negociar | No deja registro ni reglas |
| SINPE Móvil | Pago inmediato y sin costo | No protege a ninguna de las partes |

La consecuencia es desconfianza en ambos sentidos: el cliente teme pagar el adelanto y no recibir lo acordado, y el artista teme hacer el trabajo o presentarse al evento sin cobrar el saldo.

### 1.2 Propuesta

ArtísTica es una aplicación móvil donde se descubre y se contrata arte hecho por personas, con el pago protegido. Reúne en un mismo lugar el portafolio del artista, la negociación y el cobro. El cobro se hace por hitos, el dinero lo custodia una pasarela inscrita ante la SUGEF y, si algo sale mal, existe un proceso de disputa. La parte social (galería, feed y comentarios) existe para que el cliente encuentre al artista adecuado.

| Para quien contrata | Para el artista |
|---|---|
| Paga por hitos y puede abrir una disputa | Portafolio, clientes y cobro en un solo lugar |
| Reseñas que solo provienen de trabajos completados | Métricas de consultas reales, no de reacciones |
| Un mismo flujo para encargos, eventos y obras | Publicar y recibir pedidos es gratuito |

### 1.3 Usuarios

| Rol | Descripción |
|---|---|
| **Público** | Gratuito. Explora, sigue, comenta, consulta, contrata y compra. No publica obra |
| **Artista, plan Taller** | Gratuito. Publica y recibe pedidos sin límite. Tarifa de servicio de 8% |
| **Artista, plan Estudio** | ≈ ₡2,500 al mes. Tarifa de 5% y herramientas profesionales |
| **Moderación** | Atiende reportes, revisa contenido sospechoso de ser generado por IA y resuelve disputas |
| **Agrupación** (etapa 2) | Perfil con varios administradores: bandas, mariachis, compañías de baile |

### 1.4 Modelo operativo

El artista no sube productos a una tienda: muestra su trabajo y declara que acepta encargos (comisiones abiertas). Un solo motor de pedidos atiende tres tipos:

| Tipo | Ejemplo | Cobro |
|---|---|---|
| **Encargo** | Retrato, mural, logo | Anticipo al aceptar la cotización. El saldo se autoriza con la vista previa y se cobra cuando el cliente la aprueba |
| **Evento** | Mariachi para una boda | Anticipo al reservar la fecha y saldo antes del evento |
| **Obra disponible** | Pintura terminada a precio fijo | Se autoriza al comprar y se cobra al despachar con número de guía |

Toda contratación sigue el mismo camino: consulta, cotización, cobros por hitos, entrega con plazo de disputa y reseña. Las conversaciones entre cliente y artista siempre nacen de una consulta, de modo que cada una queda ligada a un posible pedido y sirve como evidencia ante una disputa.

### 1.5 Principios

1. **Arte hecho por personas.** Un clasificador marca el contenido sospechoso de ser generado por IA para revisión humana; nunca bloquea una cuenta de forma automática.
2. **Feed auténtico.** Seguidos es cronológico y nunca incluye contenido promocionado.
3. **Artista, no tienda.** Se vende la habilidad del artista: no hay catálogo, existencias ni reventa.
4. **Métricas honestas.** Se mide respuesta real (consultas y conversión), no viralidad.
5. **Lo esencial es gratis.** Publicar, recibir pedidos, la protección del pago y la verificación no se cobran.

### 1.6 Competencia

| Alternativa | Fortaleza | Limitación |
|---|---|---|
| Instagram | Audiencia y vitrina gratuita | No permite contratar ni cobrar |
| WhatsApp y SINPE Móvil | Inmediatos y sin costo | Sin protección ni reputación |
| Fiverr y plataformas globales | Protegen el pago | Cobran en dólares y no cubren contrataciones locales como eventos |

La ventaja sostenible es la reputación acumulada: un artista con decenas de trabajos reseñados en ArtísTica no tiene incentivo para empezar de cero en otra plataforma.

### 1.7 Alcance por etapas

| Etapa | Alcance |
|---|---|
| **MVP, noviembre de 2026** | Público y Artista, galería de imágenes (el video queda para después), feed, Explorar, los tres tipos de pedido con anticipo y saldo sobre el entorno de pruebas de la pasarela, métricas y moderación básica |
| **Etapa 2** | Cobro real de Estudio, promociones, reseñas, agrupaciones, disputas completas y artistas fundadores |
| **Etapa 3** | Membresías de fans. Venta de obra a mayor escala solo si los datos lo justifican |
| **Etapa 4** | Expansión regional |

### 1.8 Arquitectura

| Capa | Tecnología | Responsable |
|---|---|---|
| Aplicación móvil | React Native con Expo y TypeScript | Brian Zeledón Esquivel |
| API y procesos en segundo plano | Python 3.12 y FastAPI | Esteban Granados Sibaja |
| Datos, autenticación y archivos | Supabase sobre PostgreSQL 15 | Compartido |
| Pagos | ONVO Pay, modo marketplace | Esteban Granados Sibaja |

La aplicación nunca accede a la base de datos directamente: todo pasa por la API. El detalle del stack está en la versión 1.0 de este documento.

---

## 2. Estrategia de distribución

### 2.1 Canal

ArtísTica se publica como aplicación para iOS y Android en App Store y Google Play, compilada desde un mismo código con EAS, el servicio de compilación de Expo. Antes del lanzamiento público se distribuye como beta cerrada a los artistas fundadores. El primer mercado es Costa Rica, y no se invierte en publicidad pagada hasta que haya pedidos orgánicos.

### 2.2 Arranque del mercado

Sin artistas no llegan clientes y sin clientes los artistas no se quedan. Por eso se empieza por la oferta, con pocos artistas y perfiles completos, en dos nichos donde el pago anticipado es un problema real:

| Nicho de entrada | Ejemplos | Motivo |
|---|---|---|
| **Música y baile para eventos** | Mariachis, bandas, grupos de baile para bodas y quince años | Monto alto y el adelanto es una fuente frecuente de conflicto |
| **Encargos visuales** | Retratos, ilustración, murales, logos | Monto alto y entrega verificable con vista previa |

### 2.3 Oferta y demanda

- **Artistas fundadores.** Los primeros 100 reciben el plan Estudio gratis por seis meses. Se reclutan en persona en escuelas de arte y música, casas de cultura y ferias.
- **Nuevos talentos.** Explorar reserva una de cada cinco posiciones para artistas con menos de 50 seguidores, sin necesidad de pagar promociones. Los dos valores son configurables.
- **Clientes.** Se buscan donde ya se contrata arte: organizadores de bodas, salones de eventos, restaurantes y comercios. Se prioriza al cliente empresarial porque repite.

### 2.4 Contratación dentro de la aplicación

Un cliente puede encontrar al artista en Instagram y contratarlo por fuera. Para evitarlo, el camino interno debe ser el más conveniente: la protección del pago y las reseñas solo existen dentro de la aplicación, el perfil no admite teléfonos ni enlaces de WhatsApp, el chat muestra un aviso si detecta datos de contacto y la tarifa es moderada.

---

## 3. Esquema de generación de dinero

Los montos en colones usan un tipo de cambio de referencia de ₡500 por US$1 y son aproximados.

### 3.1 Fuentes de ingreso

| Fuente | Mecanismo | Peso |
|---|---|---|
| **Tarifa por pedido** | 8% en Taller, 5% en Estudio | Principal: ArtísTica gana solo cuando el artista gana |
| **Suscripción Estudio** | ≈ ₡2,500 al mes | Secundaria |
| **Promociones** | Paquetes por personas alcanzadas | Complementaria, desde la etapa 2 |
| **Membresías de fans** | Apoyo mensual del público a un artista | Futura, etapa 3 |

### 3.2 Tarifa por pedido

- Una sola tarifa por plan, igual para los tres tipos de pedido, para no incentivar que se clasifiquen mal.
- Monto mínimo por pedido de ₡2,500, porque el costo fijo de procesamiento pesa más en montos pequeños.
- El procesamiento de la pasarela (tarjeta: 3.9% más US$0.25; SINPE Móvil: 1.5%) y la retención tributaria de 2% se descuentan al artista. La tarifa es ingreso neto de la plataforma.

Ejemplos con pago por tarjeta, en dólares y sin incluir la retención de 2%:

| Pedido | Taller: plataforma | Taller: artista | Estudio: plataforma | Estudio: artista |
|---|---|---|---|---|
| 20 | 1.60 | 17.37 | 1.00 | 17.97 |
| 100 | 8.00 | 87.85 | 5.00 | 90.85 |
| 1,000 | 80.00 | 880.75 | 50.00 | 910.75 |

### 3.3 Suscripción Estudio

Cuesta ≈ ₡2,500 al mes o ≈ ₡25,000 al año. Incluye la tarifa de 5%, calendario sincronizado, plantillas de cotización, métricas completas, perfil personalizable y una promoción mensual.

Se paga sola a partir de ≈ ₡85,000 al mes en pedidos. Por ejemplo, un grupo musical con cuatro contrataciones de ₡150,000 paga ₡48,000 de tarifa en Taller y ₡32,500 en Estudio, suscripción incluida.

Al cambiar de plan, cada pedido conserva la tarifa vigente cuando se creó, de modo que nadie paga una tarifa distinta a la que aceptó al cotizar. En el MVP, Estudio se activa sin cobro real; el cobro de la suscripción llega en la etapa 2.

### 3.4 Promociones

Se vende alcance, no días ni vistas: una persona cuenta como alcanzada cuando la publicación estuvo al menos 50% visible en su pantalla durante un segundo, no sigue al artista y su cuenta tiene siete días o más.

| Paquete | Precio |
|---|---|
| 1,000 personas | ≈ ₡1,000 |
| 3,000 personas | ≈ ₡2,500 |
| 10,000 personas | ≈ ₡6,000 |

Nunca aparecen en Seguidos, siempre llevan la etiqueta "Promocionado" y en Explorar ocupan como máximo uno de cada ocho elementos. Antes de comprar, el sistema muestra cuántas personas elegibles hay, para no vender un alcance que no se puede entregar.

### 3.5 Reglas del dinero en cada pedido

| Regla | Valor |
|---|---|
| Anticipo de encargos y eventos | Entre 30% y 50%, a elección del artista. Por defecto, 50% |
| Plazo de disputa | 7 días desde la entrega o desde la fecha del evento. Sin reclamo, el pedido se completa |
| Cliente cancela un evento | Más de 30 días antes: se devuelve 100%. De 7 a 30 días: 50%. Menos de 7 días: nada |
| Cliente cancela un encargo | Sin costo antes del anticipo. Después, el anticipo no se devuelve |
| Artista cancela o incumple | Se devuelve el 100% de lo cobrado |
| Evento que llega con el saldo sin pagar | Se trata como cancelación del cliente con menos de 7 días |

Todas las reglas son configurables sin modificar el código.

### 3.6 Costos

| Costo | Monto |
|---|---|
| Infraestructura | ≈ US$100 al mes al inicio |
| IVA | 13% sobre tarifa, suscripción y promociones |
| Tiendas de aplicaciones | 15% sobre suscripción y promociones vendidas dentro de la aplicación, desde la etapa 2 |
| Artistas fundadores | Seis meses de Estudio gratis para 100 artistas |
| Operación y legal | Horas de moderación y soporte; cumplimiento de la Ley 8968 de protección de datos |

### 3.7 Viabilidad

Con un pedido promedio de US$150, una tarifa promedio de 7% y 300 suscriptores de Estudio, alcanzar ≈ US$3,200 al mes (dos salarios modestos más infraestructura) requiere ≈ 215 pedidos al mes, unos siete por día. Cada pedido deja ≈ US$9 netos después de IVA y las suscripciones aportan ≈ US$1,200.

### 3.8 Ideas descartadas

| Idea | Motivo |
|---|---|
| Cobrar por ser artista | Sin oferta no hay contenido ni compradores |
| Verificación pagada | La insignia dejaría de significar identidad confirmada |
| Tarifa distinta por tipo de pedido | Incentiva clasificar mal y la pasarela no la soporta |
| Promociones por tiempo | En categorías pequeñas se paga por casi nada |
| Venta de inventario | Contradice la propuesta y compite con Facebook Marketplace |

---

## 4. Situaciones presentadas en el desarrollo

### 4.1 Producto y negocio

#### Custodia del dinero

**Situación.** La propuesta del I Avance retenía el pago en un escrow propio hasta aprobar la entrega.

**Impacto.** Custodiar dinero de terceros exige inscripción ante la SUGEF como intermediario financiero.

**Resolución.** La custodia pasó a ONVO Pay, inscrita ante la SUGEF, con cobros por hitos; ArtísTica no guarda saldos. Se agregó el rol Público, que contrata.

#### Tienda o comisiones abiertas

**Situación.** Se evaluó vender obras como una tienda, con existencias y envíos.

**Impacto.** Requería dos motores de pago, competía con Facebook Marketplace y exigía ≈ 540 pedidos al mes para sostenerse.

**Resolución.** Se adoptaron las comisiones abiertas con un solo motor de pedidos. La venta directa se cubre con la obra disponible y la meta baja a ≈ 215 pedidos al mes.

#### Reglas de dinero incompletas

**Situación.** Faltaban el anticipo, el plazo de disputa y la cancelación de eventos, y algunos vencimientos dejaban el pedido sin salida.

**Impacto.** No era posible programar los estados del pedido.

**Resolución.** Se fijaron valores configurables (sección 3.5). Una autorización vencida puede renovarse durante siete días; si no se renueva, el artista puede abrir una disputa.

#### Cambio de plan con pedidos abiertos

**Situación.** ONVO aplica una sola tarifa por cuenta, y ArtísTica la fija por pedido.

**Impacto.** Al cambiar de plan, los pedidos abiertos podrían cobrarse con la tarifa nueva.

**Resolución.** Cada pedido conserva su tarifa y el sistema ajusta la de la cuenta justo antes de cada cobro. Se consultó a ONVO si admite una tarifa por cobro.

#### Artistas informales y el registro en la pasarela

**Situación.** ONVO no ha confirmado si una persona sin actividad inscrita en Hacienda puede completar su registro como cuenta de cobro.

**Impacto.** Muchos artistas costarricenses son informales y podrían quedar fuera de la plataforma.

**Resolución.** El registro en la pasarela se exige solo al primer cobro: antes, el artista exhibe su obra, recibe consultas y cotiza. La insignia de verificado se obtiene al completar ese registro y no se vende.

### 4.2 Técnicas y de equipo

#### Backend inicial no ejecutable

**Situación.** La primera versión del backend nunca se había ejecutado; una auditoría encontró 14 defectos.

**Impacto.** Ninguna prueba corría y ningún avance se podía verificar.

**Resolución.** Se dedicó una etapa a sanearlo y desde entonces la integración continua valida cada cambio.

#### Seguridad de la base de datos

**Situación.** El I Avance no usaba seguridad a nivel de filas en la base de datos.

**Impacto.** Con la clave pública que viaja dentro de la aplicación, cualquiera podría leer o escribir la base de datos.

**Resolución.** La seguridad a nivel de filas está activa en todas las tablas y la aplicación solo se comunica con la API.

#### Huecos en el esquema de datos

**Situación.** Faltaban tablas para entregables y disputas, y nada impedía vender dos veces una obra.

**Impacto.** Varias etapas posteriores no se podían construir.

**Resolución.** Como aún no había datos, se reescribió la migración inicial con esas tablas y un índice único contra ventas duplicadas.

#### Incertidumbre sobre la pasarela

**Situación.** ONVO solo documenta un máximo de 30 días para una autorización, sin un mínimo garantizado, no aclara si admite SINPE Móvil en modo marketplace, y sus avisos de pago no van firmados.

**Impacto.** Diseñar directamente sobre ONVO ataba el sistema a supuestos, y un aviso alterado podía mover dinero.

**Resolución.** La pasarela quedó detrás de un contrato con una implementación simulada y otra de ONVO, y ningún aviso mueve dinero sin consultar antes el cobro.

#### Verificación de sesiones

**Situación.** La verificación de las sesiones, heredada de la primera versión, buscaba las claves públicas de Supabase en una dirección equivocada y aceptaba un solo tipo de firma.

**Impacto.** Ningún usuario real habría podido iniciar sesión, y las pruebas no lo detectaban porque aún no existían endpoints.

**Resolución.** Se corrigió la dirección, se aceptan los dos tipos de firma asimétrica que usa Supabase y se agregaron pruebas con sesiones firmadas.

#### Cambios cruzados en el repositorio

**Situación.** Al inicio los cambios iban directo a la rama de integración, y uno quedó en la rama equivocada.

**Impacto.** Riesgo de sobrescribir el trabajo del otro integrante.

**Resolución.** Cada integrante tiene un módulo propio y todo cambio entra por pull request con evidencia de verificación.

---

## 5. Avance de desarrollo

### 5.1 Estado general

| Componente | Estado |
|---|---|
| Aplicación: pantallas y diseño | Avanzado, con datos de ejemplo |
| Backend: base ejecutable e integración continua | Completo |
| Backend: esquema de base de datos | Completo para el MVP |
| Backend: reglas de pedidos y cobros | Completo y probado |
| Backend: capa de pagos | Completa, con pasarela simulada y adaptador de ONVO |
| Backend: identidad, roles y planes | Completo y probado |
| Backend: almacenamiento de imágenes | Completo, con almacenamiento simulado y adaptador de Supabase |
| Backend: obras y servicios | Completo, con los límites del plan Taller |
| Backend: publicaciones y feed | Completo: Seguidos cronológico y Explorar con cuota de nuevos talentos |
| Backend: seguidores y me gusta | Completo, con contadores que nunca alteran el orden del feed |
| Backend: comentarios y búsqueda | Completo: comentarios con un nivel de respuestas y búsqueda de publicaciones y artistas |
| Endpoints de negocio e integración con la aplicación | En desarrollo: toda la parte social disponible (perfiles, planes, imágenes, obras, servicios, publicaciones, feed, seguidores, me gusta, comentarios y búsqueda). Falta la contratación |

### 5.2 Backend

| Etapa | Resultado |
|---|---|
| Saneamiento | Proyecto instalable y migrable, con pruebas e integración continua en verde |
| Esquema de datos | 21 tablas con seguridad a nivel de filas: perfiles, obras, publicaciones, consultas, pedidos, cobros, disputas, métricas y moderación, entre otras |
| Reglas de pedidos | Todas las transiciones de pedidos y cobros, cálculo de anticipo y saldo, cancelaciones, disputas y vencimientos |
| Capa de pagos | Contrato de pasarela, pasarela simulada completa y adaptador de ONVO |
| Identidad y planes | Registro y edición de perfiles, roles, cambio de plan que respeta la tarifa de cada pedido y registro del artista en la pasarela |
| Almacenamiento e imágenes | Subida directa desde el teléfono con un permiso firmado, verificación de tamaño y tipo antes de aceptar la imagen, y borrado |
| Obras y servicios | Galería del artista con obras en exhibición o disponibles, servicios de encargo y de evento, límites del plan Taller que nunca ocultan contenido al bajar de plan, y catálogo público paginado |
| Publicaciones y feed | Publicaciones con texto, imágenes y una obra opcional, nunca con precio; feed Seguidos en orden cronológico y Explorar filtrado por categorías con cuota de nuevos talentos |
| Seguidores y me gusta | Seguir artistas, contadores y listas de seguidores, y me gusta en publicaciones. Los contadores se muestran pero no ordenan ningún feed |
| Comentarios y búsqueda | Comentarios con un nivel de respuestas y me gusta, que no admiten teléfonos ni WhatsApp; búsqueda de publicaciones en español y de artistas por nombre, siempre por recencia |

Indicadores al cierre del avance:

- 346 pruebas automatizadas.
- Ningún saldo almacenado en la base de datos: ArtísTica no custodia dinero.
- Montos calculados con aritmética decimal exacta.

### 5.3 Aplicación móvil

Pantallas implementadas con el rediseño visual Liquid Glass: Inicio (feed con estética de tablero de corcho y selector entre Seguidos y Para ti), Explorar, Mensajes, Perfil, Crear, Comentarios, Compartir e Inicio de sesión. La navegación es flotante y el fondo es personalizable. Las pantallas usan datos de ejemplo hasta conectarse con la API.

### 5.4 Pendiente para la entrega final

| Etapa | Contenido |
|---|---|
| Contenido | Miniaturas de imágenes |
| Contratación | Consultas, chat, pedidos y recepción de avisos de pago |
| Métricas y moderación | Panel del artista, reportes y clasificación para revisión humana |
| Integración | Conexión de la aplicación con la API |

La demostración de noviembre usa la pasarela simulada, que reproduce autorizaciones que vencen, rechazos y avisos de pago.

### 5.5 Riesgos

| Riesgo | Mitigación |
|---|---|
| Plazo: quedan cinco etapas de backend y la integración | Las promociones ya salieron del MVP; si hace falta, Explorar queda solo por categorías |
| ONVO no responde a tiempo | La demostración no depende de ONVO |
| La integración llega tarde | Los endpoints se construyen en el orden en que la aplicación los necesita |

## 6. Anexo: glosario

| Término | Significado |
|---|---|
| **Encargo** | Trabajo hecho a pedido para un cliente |
| **Evento** | Contratación con fecha y lugar: música, baile o presentaciones |
| **Obra disponible** | Obra terminada que el artista ofrece a precio fijo |
| **Consulta** | Conversación que abre un cliente sobre un servicio o una obra; puede convertirse en pedido |
| **Pedido** | Toda transacción. Tiene un tipo y uno o más cobros |
| **Cobro** | Cada pago parcial de un pedido: anticipo, saldo o total |
| **Tarifa de servicio** | Porcentaje que cobra ArtísTica sobre cada pedido |
| **Taller y Estudio** | Planes del artista: el gratuito y el de suscripción |
| **Pasarela** | Entidad que procesa los pagos y custodia el dinero |
