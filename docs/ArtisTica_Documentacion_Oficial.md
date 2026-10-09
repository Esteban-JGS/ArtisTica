# ArtísTica

Documentación del proyecto

EIF409, Red social para artistas
Universidad Nacional de Costa Rica

Brian José Zeledón Esquivel
Esteban Granados Sibaja

II Avance, 9 de octubre de 2026

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

### 1.1 Problema

En Costa Rica, quien quiere contratar a un artista suele recurrir a tres herramientas que no fueron pensadas para eso. Instagram sirve para conocer el trabajo del artista, pero no permite contratarlo ni pagarle. La negociación se hace por WhatsApp, donde no queda un registro formal ni hay reglas claras. El pago se hace por SINPE Móvil, que es inmediato y gratuito, pero no protege a ninguna de las partes.

El resultado es una desconfianza que va en ambos sentidos. El cliente teme pagar el adelanto y no recibir lo acordado, y el artista teme hacer el trabajo, o presentarse al evento, sin llegar a cobrar el saldo.

### 1.2 Propuesta

ArtísTica es una aplicación móvil para descubrir y contratar arte hecho por personas, con el pago protegido. Reúne en un mismo lugar el portafolio del artista, la negociación y el cobro. Los pagos se hacen por etapas, el dinero lo custodia una pasarela de pagos inscrita ante la SUGEF y, si surge un desacuerdo, existe un proceso de disputa. La parte social de la aplicación (galería, feed y comentarios) tiene como propósito que el cliente encuentre al artista adecuado.

Para quien contrata, la ventaja principal es poder pagar por etapas, abrir una disputa si algo sale mal y apoyarse en reseñas que solo provienen de trabajos completados. El mismo proceso sirve para encargos, eventos y compra de obras. Para el artista, la aplicación concentra portafolio, clientes y cobros, le muestra métricas basadas en las consultas que recibe y no le cobra por publicar ni por recibir pedidos.

### 1.3 Usuarios

| Rol | Descripción |
|---|---|
| Público | Cuenta gratuita. Puede explorar, seguir, comentar, consultar, contratar y comprar, pero no publica obra |
| Artista, plan Taller | Gratuito. Publica y recibe pedidos sin límite, con una tarifa de servicio del 8% |
| Artista, plan Estudio | Suscripción de unos ₡2,500 al mes, con una tarifa del 5% y herramientas adicionales |
| Moderación | Atiende reportes, revisa el contenido sospechoso de haber sido generado por IA y resuelve disputas |
| Agrupación (etapa 2) | Perfil administrado por varias personas, pensado para bandas, mariachis o compañías de baile |

### 1.4 Modelo operativo

El artista no administra una tienda con productos. Muestra su trabajo e indica que acepta encargos, lo que en el medio se conoce como comisiones abiertas. Todos los pedidos pasan por el mismo proceso, que contempla tres tipos:

| Tipo | Ejemplo | Cobro |
|---|---|---|
| Encargo | Retrato, mural, logo | Anticipo al aceptar la cotización. El saldo se autoriza cuando el cliente ve la vista previa y se cobra cuando la aprueba |
| Evento | Mariachi para una boda | Anticipo al reservar la fecha y saldo antes del evento |
| Obra disponible | Pintura terminada a precio fijo | El monto se autoriza al comprar y se cobra cuando el artista despacha la obra con número de guía |

Cualquier contratación sigue los mismos pasos: consulta, cotización, cobros por etapas, entrega con un plazo para reclamar y reseña. Las conversaciones entre cliente y artista siempre nacen de una consulta, de modo que quedan asociadas a un posible pedido y sirven como evidencia si hay una disputa.

### 1.5 Principios

El diseño del producto parte de cinco principios:

1. Solo se publica arte hecho por personas. Un clasificador señala el contenido sospechoso de haber sido generado por IA para que lo revise una persona, y nunca bloquea una cuenta de forma automática.
2. El feed de Seguidos es cronológico y nunca incluye contenido promocionado.
3. Lo que se ofrece es la habilidad del artista. No hay catálogo, existencias ni reventa.
4. Las métricas miden la respuesta que recibe el artista, como las consultas y las contrataciones, y no la cantidad de reacciones.
5. Publicar, recibir pedidos, la protección del pago y la verificación son gratuitos.

### 1.6 Competencia

Instagram ofrece audiencia y una vitrina gratuita, pero no permite contratar ni cobrar. WhatsApp y SINPE Móvil son inmediatos y no tienen costo, aunque no dan protección a las partes ni construyen reputación. Plataformas globales como Fiverr sí protegen el pago, pero cobran en dólares y no cubren contrataciones locales como los eventos.

La ventaja que ArtísTica puede sostener en el tiempo es la reputación acumulada. Un artista con decenas de trabajos reseñados en la plataforma tiene pocos motivos para empezar de cero en otra.

### 1.7 Alcance por etapas

| Etapa | Alcance |
|---|---|
| MVP, noviembre de 2026 | Público y Artista, galería de imágenes (el video queda para después), feed, Explorar, los tres tipos de pedido con anticipo y saldo sobre el entorno de pruebas de la pasarela, métricas y moderación básica |
| Etapa 2 | Cobro real del plan Estudio, promociones, reseñas, agrupaciones, disputas completas, programa de artistas fundadores, notificaciones push, mensajes libres entre artistas e imágenes en el chat |
| Etapa 3 | Membresías de fans y, solo si los datos lo justifican, venta de obra a mayor escala |
| Etapa 4 | Expansión regional |

### 1.8 Arquitectura

| Capa | Tecnología | Responsable |
|---|---|---|
| Aplicación móvil | React Native con Expo y TypeScript | Brian Zeledón Esquivel |
| API y procesos en segundo plano | Python 3.12 y FastAPI | Esteban Granados Sibaja |
| Datos, autenticación y archivos | Supabase sobre PostgreSQL 15 | Compartido |
| Pagos | ONVO Pay en modo marketplace | Esteban Granados Sibaja |

La aplicación nunca accede directamente a la base de datos; todas sus operaciones pasan por la API. El detalle de las tecnologías se encuentra en la versión del I Avance.

---

## 2. Estrategia de distribución

### 2.1 Canal

ArtísTica se publicará como aplicación para iOS y Android en App Store y Google Play. Ambas versiones se compilan desde el mismo código con EAS, el servicio de compilación de Expo. Antes del lanzamiento público, la aplicación se distribuirá como beta cerrada entre los artistas fundadores. El primer mercado es Costa Rica, y no se invertirá en publicidad pagada mientras no haya pedidos orgánicos.

### 2.2 Arranque del mercado

Una plataforma de este tipo enfrenta un problema de arranque: sin artistas no llegan clientes, y sin clientes los artistas no se quedan. Por eso se empezará por la oferta, con pocos artistas y perfiles completos, en dos nichos donde el pago anticipado es un problema real.

El primero es la música y el baile para eventos, como mariachis, bandas y grupos de baile para bodas y quince años. Son contrataciones de monto alto en las que el adelanto es una fuente frecuente de conflictos. El segundo son los encargos visuales, como retratos, ilustraciones, murales y logos, que también tienen montos altos y permiten verificar la entrega con una vista previa.

### 2.3 Oferta y demanda

Para atraer a los primeros artistas, los 100 primeros tendrán el plan Estudio gratis durante seis meses. Se reclutarán en persona en escuelas de arte y música, casas de cultura y ferias.

Para que los artistas nuevos tengan visibilidad sin pagar promociones, la sección Explorar reserva una de cada cinco posiciones a artistas con menos de 50 seguidores. Ambos valores se pueden ajustar.

Los clientes se buscarán donde ya se contrata arte: organizadores de bodas, salones de eventos, restaurantes y comercios. Se dará prioridad al cliente empresarial, porque contrata de forma recurrente.

### 2.4 Contratación dentro de la aplicación

Un cliente puede encontrar al artista en Instagram y contratarlo por fuera. Para reducir ese riesgo, el camino dentro de la aplicación tiene que ser el más conveniente. La protección del pago y las reseñas solo existen dentro de ArtísTica, el perfil no admite teléfonos ni enlaces de WhatsApp, el chat muestra un aviso cuando detecta datos de contacto y la tarifa se mantiene moderada.

---

## 3. Esquema de generación de dinero

Los montos en colones se calculan con un tipo de cambio de referencia de ₡500 por US$1 y son aproximados.

### 3.1 Fuentes de ingreso

| Fuente | Mecanismo | Importancia |
|---|---|---|
| Tarifa por pedido | 8% en Taller y 5% en Estudio | Principal. ArtísTica solo gana cuando el artista gana |
| Suscripción Estudio | Unos ₡2,500 al mes | Secundaria |
| Promociones | Paquetes según la cantidad de personas alcanzadas | Complementaria, desde la etapa 2 |
| Membresías de fans | Aporte mensual del público a un artista | Futura, en la etapa 3 |

### 3.2 Tarifa por pedido

La tarifa es la misma para los tres tipos de pedido dentro de cada plan, para que no haya incentivo a clasificar mal un pedido. Cada pedido tiene un monto mínimo de ₡2,500, porque en montos pequeños el costo fijo de procesamiento pesa demasiado. El costo de procesamiento de la pasarela (3.9% más US$0.25 con tarjeta y 1.5% con SINPE Móvil) y la retención tributaria del 2% se descuentan al artista, de modo que la tarifa es ingreso neto de la plataforma.

La siguiente tabla muestra ejemplos de pagos con tarjeta, en dólares y sin incluir la retención del 2%.

| Pedido | Taller: plataforma | Taller: artista | Estudio: plataforma | Estudio: artista |
|---|---|---|---|---|
| 20 | 1.60 | 17.37 | 1.00 | 17.97 |
| 100 | 8.00 | 87.85 | 5.00 | 90.85 |
| 1,000 | 80.00 | 880.75 | 50.00 | 910.75 |

### 3.3 Suscripción Estudio

La suscripción cuesta unos ₡2,500 al mes o ₡25,000 al año. Incluye la tarifa del 5%, calendario sincronizado, plantillas de cotización, métricas completas, perfil personalizable y una promoción mensual.

La suscripción se paga sola cuando el artista factura más de ₡85,000 al mes en pedidos. Por ejemplo, un grupo musical con cuatro contrataciones de ₡150,000 al mes paga ₡48,000 de tarifa en Taller y ₡32,500 en Estudio, con la suscripción incluida.

Cuando un artista cambia de plan, cada pedido conserva la tarifa vigente en el momento en que se creó, de modo que nadie paga una tarifa distinta a la que aceptó al cotizar. En el MVP el plan Estudio se activa sin cobro real; el cobro de la suscripción llegará en la etapa 2.

### 3.4 Promociones

Las promociones se venden por alcance. Una persona cuenta como alcanzada cuando la publicación ocupó al menos la mitad de su pantalla durante un segundo, no sigue al artista y su cuenta tiene siete días o más de antigüedad.

| Paquete | Precio aproximado |
|---|---|
| 1,000 personas | ₡1,000 |
| 3,000 personas | ₡2,500 |
| 10,000 personas | ₡6,000 |

Las publicaciones promocionadas nunca aparecen en Seguidos, siempre llevan la etiqueta "Promocionado" y en Explorar ocupan como máximo uno de cada ocho elementos. Antes de la compra, el sistema muestra cuántas personas elegibles hay, para no vender un alcance que no se puede cumplir.

### 3.5 Reglas del dinero en cada pedido

| Regla | Valor |
|---|---|
| Anticipo de encargos y eventos | Entre 30% y 50%, a elección del artista. Si no elige, 50% |
| Plazo de disputa | Siete días desde la entrega, o desde la fecha del evento. Si nadie reclama, el pedido se completa |
| El cliente cancela un evento | Con más de 30 días de anticipación se le devuelve el 100%; de 7 a 30 días, el 50%; con menos de 7 días, nada |
| El cliente cancela un encargo | Sin costo antes del anticipo. Después, el anticipo no se devuelve |
| El artista cancela o incumple | Se devuelve el 100% de lo cobrado |
| Disputa | Moderación decide si el pedido se completa o se cancela, y puede ordenar la devolución total o parcial de lo cobrado, incluido el anticipo |
| El evento llega con el saldo sin pagar | Se trata como una cancelación del cliente con menos de siete días |

Todas estas reglas se pueden cambiar por configuración, sin modificar el código.

### 3.6 Costos

| Costo | Monto |
|---|---|
| Infraestructura | Unos US$100 al mes al inicio |
| IVA | 13% sobre la tarifa, la suscripción y las promociones |
| Tiendas de aplicaciones | 15% sobre las suscripciones y promociones vendidas dentro de la aplicación, desde la etapa 2 |
| Artistas fundadores | Seis meses del plan Estudio gratis para 100 artistas |
| Operación y aspectos legales | Horas de moderación y soporte, y cumplimiento de la Ley 8968 de protección de datos |

### 3.7 Viabilidad

Con un pedido promedio de US$150, una tarifa promedio del 7% y 300 suscriptores del plan Estudio, llegar a unos US$3,200 al mes, que cubren dos salarios modestos y la infraestructura, requiere cerca de 215 pedidos al mes, es decir, unos siete por día. Cada pedido deja alrededor de US$9 netos después del IVA, y las suscripciones aportan unos US$1,200.

### 3.8 Ideas descartadas

Durante el diseño se descartaron varias formas de generar ingresos. Cobrarle al artista por estar en la plataforma reduciría la oferta, y sin artistas no hay contenido ni compradores. Una verificación pagada haría que la insignia dejara de significar una identidad confirmada. Una tarifa distinta según el tipo de pedido incentivaría a clasificar mal los pedidos y, además, la pasarela no la soporta. Las promociones por tiempo se descartaron porque, en categorías pequeñas, el artista terminaría pagando por casi ninguna vista. Por último, la venta de inventario contradice la propuesta y compite directamente con Facebook Marketplace.

---

## 4. Situaciones presentadas en el desarrollo

Esta sección resume los problemas más relevantes que surgieron durante el desarrollo, qué afectaban y cómo se resolvieron.

### 4.1 Producto y negocio

#### Custodia del dinero

La propuesta del I Avance retenía el pago en una cuenta propia hasta que el cliente aprobara la entrega. Al revisarla se encontró que custodiar dinero de terceros obliga a inscribirse ante la SUGEF como intermediario financiero. La custodia pasó entonces a ONVO Pay, que ya cuenta con esa inscripción, con cobros por etapas, y ArtísTica no guarda saldos. En el mismo cambio se agregó el rol Público, que es el que contrata.

#### Tienda o comisiones abiertas

Se evaluó vender obras como una tienda, con existencias y envíos. Esa opción requería dos procesos de pago distintos, competía con Facebook Marketplace y necesitaba cerca de 540 pedidos al mes para sostenerse. Se optó por las comisiones abiertas con un solo proceso de pedidos. La venta directa queda cubierta por la obra disponible, y la meta baja a unos 215 pedidos al mes.

#### Reglas de dinero incompletas

Al programar los estados del pedido faltaban definiciones: el porcentaje del anticipo, el plazo para abrir una disputa y la política de cancelación de eventos. Además, algunos vencimientos dejaban el pedido sin salida. Se fijaron valores configurables (sección 3.5) y se estableció que una autorización vencida puede renovarse durante siete días; si no se renueva, el artista puede abrir una disputa.

#### Cambio de plan con pedidos abiertos

ONVO aplica una sola tarifa por cuenta, mientras que ArtísTica la fija por pedido. Si un artista cambiaba de plan con pedidos abiertos, esos pedidos podían terminar cobrándose con la tarifa nueva. Para evitarlo, cada pedido conserva su tarifa y el sistema ajusta la de la cuenta justo antes de cada cobro. También se consultó a ONVO si admite una tarifa por cobro.

#### Artistas informales y el registro en la pasarela

ONVO no ha confirmado si una persona sin actividad inscrita en Hacienda puede registrarse como cuenta de cobro, y muchos artistas costarricenses trabajan de manera informal. Para no dejarlos fuera, el registro en la pasarela se exige recién en el primer cobro; antes de eso, el artista puede exhibir su obra, recibir consultas y cotizar. La insignia de verificado se obtiene al completar ese registro y no se vende.

### 4.2 Técnicas y de equipo

#### Backend inicial no ejecutable

La primera versión del backend nunca se había ejecutado, y una auditoría encontró 14 defectos. Como ninguna prueba corría, no había forma de verificar los avances. Se dedicó una etapa completa a corregirlo, y desde entonces la integración continua valida cada cambio.

#### Seguridad de la base de datos

En el I Avance la base de datos no usaba seguridad a nivel de filas. Como la clave pública viaja dentro de la aplicación, cualquiera habría podido leer o escribir datos. Ahora esa seguridad está activa en todas las tablas, y la aplicación solo se comunica con la API.

#### Tablas faltantes en el esquema de datos

Faltaban tablas para los entregables y las disputas, y nada impedía vender dos veces la misma obra, lo que bloqueaba varias etapas posteriores. Como todavía no había datos, se reescribió la migración inicial con esas tablas y con un índice único que impide las ventas duplicadas.

#### Incertidumbre sobre la pasarela

ONVO solo documenta un máximo de 30 días para una autorización, sin garantizar un mínimo. Tampoco aclara si admite SINPE Móvil en modo marketplace, y sus avisos de pago no van firmados. Diseñar directamente sobre ONVO habría atado el sistema a esos supuestos, y un aviso alterado podría haber movido dinero. Por eso la pasarela quedó detrás de una interfaz común con dos implementaciones, una simulada y otra de ONVO, y ningún aviso mueve dinero sin consultar antes el estado del cobro.

#### Verificación de sesiones

La verificación de sesiones heredada de la primera versión buscaba las claves públicas de Supabase en una dirección equivocada y aceptaba un solo tipo de firma. Ningún usuario real habría podido iniciar sesión, y las pruebas no lo detectaban porque todavía no había endpoints. Se corrigió la dirección, se aceptan los dos tipos de firma asimétrica que usa Supabase y se agregaron pruebas con sesiones firmadas.

#### Cambios cruzados en el repositorio

Al inicio, los cambios se subían directamente a la rama de integración, y en una ocasión uno quedó en la rama equivocada, con el riesgo de sobrescribir el trabajo del otro integrante. Desde entonces cada integrante trabaja en su propio módulo, y todo cambio entra por pull request con evidencia de que fue verificado.

#### Chat sin tiempo real

El documento base dejaba abierta la tecnología del chat. El servicio de tiempo real de Supabase exige reglas de acceso sobre la tabla de mensajes que contradicen la decisión de que nadie lea la base de datos fuera de la API. Un canal de tiempo real propio, por su parte, implicaba manejar reconexiones, renovación de sesiones y estado compartido entre servidores, algo que el volumen del MVP no justifica.

Se optó por que la aplicación consulte cada pocos segundos si hay mensajes nuevos. Cada mensaje se guarda con la conversación bloqueada y con una marca de tiempo que nunca retrocede, de modo que ninguno se pierde entre una consulta y la siguiente. Las notificaciones push pasaron a la etapa 2.

#### Verificación 3D Secure en los pagos con tarjeta

Algunos bancos exigen una verificación adicional del titular de la tarjeta, conocida como 3D Secure, antes de aprobar un pago. La capa de pagos trataba ese caso como un error, de modo que un cliente cuyo banco la pidiera no habría podido pagar un anticipo ni comprar una obra.

Ahora la aplicación registra la tarjeta directamente con ONVO y solo envía a la API un identificador, así que los datos de la tarjeta nunca pasan por los servidores de ArtísTica. Si el banco pide la verificación, la API devuelve la dirección donde el cliente se autentica y, cuando este vuelve, consulta el resultado con ONVO antes de dar el pago por hecho. La pasarela simulada reproduce este caso para las pruebas y la demostración.

#### Reintentos de pago

Un pago puede fallar a medias: la pasarela cobra, pero la respuesta no llega o falla el registro en la base de datos. También puede ser rechazado, y entonces el cliente vuelve a intentar con otra tarjeta. Si cada reintento se tratara como un pago nuevo, el cliente podría pagar dos veces el mismo anticipo; si se tratara como el mismo, no podría cambiar de tarjeta.

La solución fue asignar a cada intento un identificador fijo que la pasarela reconoce, de manera que repetir el mismo intento devuelve el resultado anterior sin cobrar otra vez. Un rechazo cierra el intento, y el siguiente pago usa un identificador nuevo. Además, ninguna operación llama a la pasarela sin validar antes que el pedido esté en el estado correcto.

#### Almacenamiento del archivo final

Las imágenes de la galería se guardan en un almacenamiento de lectura pública, porque deben poder verse sin restricciones. El archivo final de un encargo, en cambio, es la obra sin marca de agua, y guardado en ese mismo lugar cualquiera que obtuviera su dirección podría descargarlo sin pagar.

Por eso los archivos finales van a un almacenamiento privado separado. Solo el artista puede subirlos, y únicamente después de que el cliente pagó el saldo. Para descargarlos, el cliente o el artista solicitan a la API un enlace firmado que vence a los diez minutos.

#### Resolución de disputas con varias operaciones de pago

Resolver una disputa puede requerir varias operaciones en la pasarela, como cobrar el saldo autorizado, liberar otra autorización y devolver parte del anticipo. Cualquiera de ellas puede fallar, por ejemplo porque la autorización ya venció. Si la devolución se ejecutaba primero y el cobro fallaba después, el cliente recibía su dinero sin que la disputa quedara resuelta.

Se definió un orden: primero se ejecuta lo que puede fallar por una regla del negocio, que es cobrar lo autorizado, después las liberaciones y al final las devoluciones. La resolución solo se registra cuando todas terminaron, y cada operación lleva un identificador fijo para que repetirla no cobre ni devuelva dos veces.

#### Feed de Seguidos en la aplicación

El prototipo del feed de Seguidos mostraba publicaciones de cuentas que la persona no seguía, en el mismo orden que Para ti, lo que contradecía el principio de un feed cronológico limitado a las cuentas seguidas. Ahora Seguidos muestra solo esas cuentas y las publicaciones propias, de la más reciente a la más antigua, mientras que Para ti conserva su propio orden.

#### Identidad visual del tablero

La textura de corcho del fondo estaba teñida con el color terracota de la marca y, al aclararla, quedaba en un tono salmón. El color de marca se confundía con el fondo, con un contraste cercano a 2 a 1, y la interfaz se veía plana. El corcho recuperó un tono natural con el grano visible, la navegación y los selectores pasaron a un tono de tinta oscura, y el texto siempre se apoya sobre papel o vidrio, nunca directamente sobre el corcho.

---

## 5. Avance de desarrollo

### 5.1 Estado general

| Componente | Estado |
|---|---|
| Aplicación móvil, pantallas y diseño | Avanzado. El flujo completo de un encargo se puede recorrer con datos de ejemplo |
| Backend, base de datos e integración continua | Completo. El proyecto se ejecuta, el esquema cubre el MVP y cada cambio se valida automáticamente |
| Backend, parte social | Completo. Incluye perfiles y planes, imágenes, obras y servicios, publicaciones, feed, seguidores, me gusta, comentarios y búsqueda |
| Backend, contratación y pagos | Completo. Incluye consultas y chat, los tres tipos de pedido, cobros con verificación 3D Secure, archivo final privado y resolución de disputas por moderación |
| Backend, avisos de pago y vencimientos | Pendiente |
| Backend, métricas, moderación de contenido y procesos con IA | Pendiente |
| Integración de la aplicación con la API | Pendiente. La aplicación todavía usa datos de ejemplo |

### 5.2 Backend

El backend se construyó por etapas. La siguiente tabla resume lo que quedó listo en cada una.

| Etapa | Resultado |
|---|---|
| Saneamiento | El proyecto se instala y se migra sin errores, y las pruebas y la integración continua pasan |
| Esquema de datos | 21 tablas con seguridad a nivel de filas, entre ellas perfiles, obras, publicaciones, consultas, pedidos, cobros, disputas, métricas y moderación |
| Reglas de pedidos | Todas las transiciones de pedidos y cobros, el cálculo de anticipo y saldo, las cancelaciones, las disputas y los vencimientos |
| Capa de pagos | Interfaz común de pasarela, una pasarela simulada completa y el adaptador de ONVO, con la verificación 3D Secure que puede pedir el banco del cliente |
| Identidad y planes | Registro y edición de perfiles, roles, cambio de plan que respeta la tarifa de cada pedido y registro del artista en la pasarela |
| Almacenamiento e imágenes | Subida directa desde el teléfono con un permiso firmado, verificación del tamaño y el tipo antes de aceptar la imagen, y borrado |
| Obras y servicios | Galería del artista con obras en exhibición o disponibles, servicios de encargo y de evento, y catálogo público paginado. Los límites del plan Taller nunca ocultan contenido cuando el artista baja de plan |
| Publicaciones y feed | Publicaciones con texto, imágenes y una obra opcional, nunca con precio. El feed Seguidos es cronológico, y Explorar se filtra por categorías y reserva una cuota para nuevos talentos |
| Seguidores y me gusta | Seguir artistas, contadores, listas de seguidores y me gusta en publicaciones. Los contadores se muestran, pero no alteran el orden de ningún feed |
| Comentarios y búsqueda | Comentarios con un nivel de respuestas y me gusta, que no admiten teléfonos ni WhatsApp. Búsqueda de publicaciones en español y de artistas por nombre, ordenada por fecha |
| Consultas y chat | El cliente abre una consulta sobre un servicio, una obra o en general, y conversa con el artista en ese hilo. La bandeja se ordena por el último mensaje y cuenta los no leídos. Si un mensaje menciona un teléfono, WhatsApp o SINPE, ambas partes ven un aviso, pero el mensaje no se bloquea. Una cuenta con menos de siete días puede abrir hasta cinco consultas cada 24 horas |
| Pedidos y cobros | El artista cotiza desde la consulta y el cliente paga el anticipo. En un encargo, el artista entrega vistas previas, el cliente autoriza el saldo al verlas y se cobra cuando aprueba; en un evento, el saldo se cobra antes de la fecha; una obra disponible se reserva con el total autorizado y se cobra al despacharla. También hay contraoferta, rechazo, cancelación con las políticas de reembolso y apertura de disputas. Cada pago se confirma con la pasarela antes de registrarse |
| Archivo final | Una vez pagado el encargo, el artista sube el archivo final a un almacenamiento privado, y solo las dos partes pueden descargarlo con un enlace que vence a los diez minutos |
| Disputas | Moderación ve las disputas abiertas, de la más antigua a la más reciente, con el pedido y el chat de la consulta como evidencia. Al resolver, la API ejecuta en la pasarela lo que se decidió (cobrar lo autorizado, liberarlo o devolver lo cobrado) y después registra la resolución |

Al cierre de este avance, el backend cuenta con 442 pruebas automatizadas. La base de datos no almacena ningún saldo, porque ArtísTica no custodia dinero, y todos los montos se calculan con aritmética decimal exacta.

### 5.3 Aplicación móvil

La aplicación usa la estética de un tablero de corcho. Las publicaciones y las fichas son notas de papel sujetas con una chinche, el portafolio se muestra como fotos instantáneas pegadas con cinta, y la navegación y los encabezados son paneles de vidrio que flotan sobre el fondo.

| Área | Pantallas |
|---|---|
| Acceso | Bienvenida, registro e inicio de sesión |
| Social | Inicio con Seguidos y Para ti, Explorar con filtros, publicar, comentar y compartir |
| Perfiles | Perfil propio con edición y activación del perfil de artista, perfil de otros artistas y visor de obras. El portafolio se puede ver en una, dos o tres columnas |
| Contratación | Solicitud de un encargo desde una publicación, cotización del artista, pago del anticipo, entrega y aprobación de la vista previa, y reseña |
| Mensajes | Chats, seguimiento de pedidos y notificaciones |

Todo el recorrido funciona con datos de ejemplo, porque las pantallas todavía no se conectan con la API.

### 5.4 Pendiente para la entrega final

| Área | Pendiente |
|---|---|
| Contratación | Recepción de los avisos de pago y seguimiento de las autorizaciones que vencen |
| Pago desde la aplicación | Formulario de tarjeta que envía los datos directamente a la pasarela y solo comparte con la API el identificador que esta devuelve, además de la verificación 3D Secure cuando el banco la pida |
| Pasarela real | Enviar las consultas técnicas a ONVO, obtener acceso a su entorno de pruebas y probar el adaptador en ese entorno |
| Inteligencia artificial | Elegir el proveedor. Lo necesitan la detección de contenido sospechoso de haber sido generado por IA, la clasificación de estilos y la búsqueda por similitud, que hoy solo tienen su estructura |
| Métricas y moderación | Panel del artista y reportes |
| Contenido | Miniaturas de las imágenes |
| Entorno | Proyecto de Supabase configurado para la base de datos, la autenticación y el almacenamiento |
| Integración | Conectar la aplicación con la API en sesiones, feed, perfiles, chat, imágenes y pedidos |

La demostración de noviembre usará la pasarela simulada, que reproduce autorizaciones que vencen, pagos rechazados y avisos de pago.

### 5.5 Riesgos

| Riesgo | Mitigación |
|---|---|
| Plazo: quedan tres etapas de backend y la integración | Las promociones ya salieron del MVP y, si hace falta, Explorar puede quedar solo con el filtro por categorías |
| ONVO no responde a tiempo | La demostración no depende de ONVO |
| El proveedor de IA no se define a tiempo | La moderación funciona con reportes y revisión humana. El clasificador solo marca contenido para esa revisión, así que su ausencia no bloquea la demostración |
| La integración llega tarde | Los endpoints se construyen en el orden en que la aplicación los necesita |

## 6. Anexo: glosario

| Término | Significado |
|---|---|
| Encargo | Trabajo hecho a pedido para un cliente |
| Evento | Contratación con fecha y lugar, como música, baile o presentaciones |
| Obra disponible | Obra terminada que el artista ofrece a precio fijo |
| Consulta | Conversación que abre un cliente sobre un servicio o una obra, y que puede convertirse en pedido |
| Pedido | Toda contratación. Tiene un tipo y uno o más cobros |
| Cobro | Cada pago parcial de un pedido: anticipo, saldo o total |
| Tarifa de servicio | Porcentaje que cobra ArtísTica sobre cada pedido |
| Taller y Estudio | Planes del artista. Taller es gratuito y Estudio es de suscripción |
| Pasarela | Empresa que procesa los pagos y custodia el dinero |
