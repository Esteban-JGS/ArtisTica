---
trigger: always_on
description: Glosario obligatorio del dominio de ArtísTica, para nombres en codigo, base de datos e interfaz.
---

# Glosario obligatorio

La palabra "comision" tenia dos significados y se prohibio. Estos son los nombres correctos en codigo, en base de datos y en interfaz.

| Termino | Significado | No usar |
|---|---|---|
| `encargo` | Trabajo hecho a pedido para un cliente | "comision" en este sentido |
| `tarifa de servicio` | Porcentaje que cobra ArtisTica sobre un pedido | "comision" en este sentido |
| `obra` | Pieza de la galeria: solo exhibicion, o disponible con precio | "producto" |
| `publicacion` | Lo que aparece en el feed | "post de venta" |
| `servicio` | Paquete con precio que ofrece el artista | "listado" |
| `consulta` | Hilo de conversacion que abre un cliente sobre un servicio u obra | "mensaje directo" |
| `pedido` | Transaccion con tipo `encargo`, `evento` u `obra_disponible` | "orden de compra" |
| `cobro` | Cada hito de pago de un pedido: anticipo o saldo | "transaccion" |
| `resena` | Calificacion, solo de pedidos completados dentro de la app | "rating" |
| `impulso` | Promocion pagada, vendida por alcance de personas | "anuncio", "ad" |

## Roles y planes

- `publico`: gratis. Explora, sigue, comenta, consulta, contrata y compra. No publica.
- `artista` con plan `taller`: gratis. Tarifa 8%. 2 servicios, 5 obras disponibles, metricas de 30 dias.
- `artista` con plan `estudio`: suscripcion. Tarifa 5%. Servicios y obras ilimitados, metricas completas.
- `admin`: reportes, moderacion y disputas.

## Relaciones que definen el modelo

- Una `consulta` es una entidad propia, no un estado del `pedido`.
- Todo `pedido` referencia una `consulta`. Para `obra_disponible`, la consulta se crea automaticamente en estado `convertida`.
- Los `mensajes` cuelgan de `consulta_id`. Es el unico mecanismo de chat del sistema.
- Chat cliente con artista: solo mediante consulta. Artista con artista: mensajes libres. Publico con publico: no existe.
