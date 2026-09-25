# Consultas técnicas para ONVO Pay

**De:** equipo de ArtísTica
**Asunto:** integración en modo marketplace, consultas antes de pasar a producción

## Contexto

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas: encargos, eventos y venta de obras terminadas. Queremos integrar ONVO Pay en modo marketplace, con una cuenta conectada por artista, cobrando con `onBehalfOf` y la comisión de la plataforma configurada con `marketplaceAppFee`.

Cobramos por hitos. Un anticipo se captura de inmediato al aceptar una cotización, y el saldo se autoriza con `captureMethod: manual` cuando el artista entrega una vista previa, y se captura cuando el cliente la aprueba. Por eso varias preguntas giran alrededor de la autorización diferida.

Revisamos la documentación pública y la especificación OpenAPI. Estas son las dudas que no pudimos resolver con ellas.

## Autorización y captura

1. ¿Cuántos días dura una autorización con `captureMethod: manual` antes de pasar a `canceled`? ¿Varía según el emisor o la marca de la tarjeta?
2. ¿Qué código de error estable devuelve `capture` cuando la autorización ya venció?
3. Un rechazo en `confirm`, ¿siempre llega como respuesta 2xx con estado `requires_payment_method` y `lastPaymentError`, o en algunos casos como un código 4xx? ¿Cuáles?

## Modo marketplace

4. ¿SINPE Móvil funciona con `onBehalfOf` en modo marketplace?
5. ¿Hay forma de fijar la comisión por intención de pago, y no solo con `marketplaceAppFee` de la cuenta? Si la tarifa de la cuenta cambia entre la autorización y la captura, ¿cuál se aplica?
6. ¿Se puede retener la liquidación al vendedor de una intención concreta hasta que la liberemos?
7. Si un reembolso ocurre después de liquidar al vendedor, ¿de qué cuenta sale el dinero? ¿Se devuelve el `marketplaceAppFee`? ¿Quién absorbe los contracargos?

## Cuentas conectadas

8. ¿Una persona física sin actividad económica inscrita en Hacienda puede completar el onboarding? Muchos artistas en Costa Rica trabajan de manera informal.
9. ¿Una cuenta en estado `inactive` o `temporally_suspended` puede volver a `active`?
10. ¿Se puede cobrar a nombre de una cuenta que está en `awaiting_approval`?

## Idempotencia y límites

11. ¿Aceptan una clave de idempotencia en `confirm` y en `refunds`? ¿Con qué nombre de encabezado, y por cuánto tiempo la recuerdan?
12. ¿Tienen un límite de solicitudes? ¿Con qué código responden al superarlo, y envían `Retry-After`?

## Webhooks

13. ¿Qué evento envían cuando una intención queda en `requires_capture`, cuando una autorización vence, cuando un reembolso se completa o falla, y cuando cambia el estado de una cuenta conectada?
14. ¿El webhook trae un identificador único de evento o de entrega? ¿Cuál es la política de reintentos?
15. ¿Ofrecen una firma HMAC del cuerpo con marca de tiempo? Si no, ¿publican direcciones IP de origen fijas?

## Pagos con autenticación adicional

16. ¿Cómo se completa un pago que queda en `requires_action` por 3D Secure en una integración por API desde una app móvil?

Gracias. Si alguna de estas respuestas ya está documentada y no la encontramos, con el enlace nos basta.
