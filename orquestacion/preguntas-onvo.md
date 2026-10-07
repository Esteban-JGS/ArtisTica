# Consultas técnicas para ONVO Pay

**De:** equipo de ArtísTica
**Asunto:** integración en modo marketplace, consultas antes de pasar a producción

## Contexto

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas: encargos, eventos y venta de obras terminadas. Queremos integrar ONVO Pay en modo marketplace, con una cuenta conectada por artista, cobrando con `onBehalfOf` y la comisión de la plataforma configurada con `marketplaceAppFee`.

Cobramos por hitos. Un anticipo se captura de inmediato al aceptar una cotización, y el saldo se autoriza con `captureMethod: manual` cuando el artista entrega una vista previa, y se captura cuando el cliente la aprueba. Por eso varias preguntas giran alrededor de la autorización diferida.

Revisamos la documentación pública y la especificación OpenAPI. Estas son las dudas que no pudimos resolver con ellas.

## Autorización y captura

1. La descripción de `captureMethod` indica que los fondos se liberan si no se captura en un máximo de 30 días. ¿Cuál es la vigencia mínima garantizada de una autorización antes de pasar a `canceled`? ¿Varía según el emisor o la marca de la tarjeta? ¿La intención expone en algún campo la fecha en que vence?
2. ¿Qué código de error estable devuelve `capture` cuando la autorización ya venció?
3. Un rechazo en `confirm`, ¿siempre llega como respuesta 2xx con estado `requires_payment_method` y `lastPaymentError`, o en algunos casos como un código 4xx? ¿Cuáles?
4. Los estados `requires_confirmation` y `deferred` no aparecen en el enum de `PaymentIntent.status`. ¿Una intención puede quedar en alguno de ellos, o `deferred` solo existe como evento?
5. En una intención `partially_refunded` o `refunded`, ¿hay algún campo con el total reembolsado, o hay que sumar los reembolsos de `GET /v1/refunds`? ¿Se puede filtrar esa lista por intención?

## Modo marketplace

6. ¿SINPE Móvil funciona con `onBehalfOf` en modo marketplace?
7. ¿Hay forma de fijar la comisión por intención de pago, y no solo con `marketplaceAppFee` de la cuenta? Si la tarifa de la cuenta cambia entre la autorización y la captura, ¿cuál se aplica?
   Si no existe comisión por intención: ¿hay algún límite para actualizar `marketplaceAppFee` con frecuencia? Mientras un artista tenga pedidos abiertos con tarifas distintas, necesitaríamos ajustarla justo antes de cada cobro.
8. ¿Se puede retener la liquidación al vendedor de una intención concreta hasta que la liberemos?
9. Si un reembolso ocurre después de liquidar al vendedor, ¿de qué cuenta sale el dinero? ¿Se devuelve el `marketplaceAppFee`? ¿Quién absorbe los contracargos?

## Cuentas conectadas

10. ¿Una persona física sin actividad económica inscrita en Hacienda puede completar el onboarding? Muchos artistas en Costa Rica trabajan de manera informal.
11. ¿Una cuenta en estado `inactive` o `temporally_suspended` puede volver a `active`?
12. ¿Se puede cobrar a nombre de una cuenta que está en `awaiting_approval`?
13. `CreateConnectedAccount` solo admite `businessName` y `marketplaceAppFee`. ¿Hay forma de guardar un identificador propio en la cuenta conectada (metadatos o un `externalId`), o de buscar una cuenta por ese identificador? Lo necesitamos para recuperar una cuenta creada cuando nuestra base no alcanzó a guardar su id.

## Idempotencia y límites

14. ¿Aceptan una clave de idempotencia al crear una cuenta conectada, en `confirm` y en `refunds`? ¿Con qué nombre de encabezado, y por cuánto tiempo la recuerdan?
15. ¿Tienen un límite de solicitudes? ¿Con qué código responden al superarlo, y envían `Retry-After`?

## Webhooks

16. ¿Qué evento envían cuando una intención queda en `requires_capture`, cuando una autorización vence, cuando un reembolso se completa o falla, y cuando cambia el estado de una cuenta conectada?
17. ¿El webhook trae un identificador único de evento o de entrega? ¿Cuál es la política de reintentos?
18. ¿Ofrecen una firma HMAC del cuerpo con marca de tiempo? Si no, ¿publican direcciones IP de origen fijas?

## Pagos con autenticación adicional

19. ¿Cómo se completa un pago que queda en `requires_action` por 3D Secure en una integración por API desde una app móvil?

Gracias. Si alguna de estas respuestas ya está documentada y no la encontramos, con el enlace nos basta.
