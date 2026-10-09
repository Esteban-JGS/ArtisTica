# [Lote 9b] Correctivo: ruido para moderación y consultas repetidas a la pasarela

## Rol
Sos ingeniero de backend trabajando en el repositorio de ArtísTica. Seguís en la rama `feat/lote-09b-webhooks-conciliacion`: no crees otra.

## Contexto
La validación del lote 9b encontró dos problemas que solo se notan con ONVO real. El resto de la entrega está aprobado, incluidos tus desvíos 1 a 8.

### 1. Un pago rechazado termina como pendiente para moderación

`src/services/webhooks.py` incluye `SIN_COBRO` en `_PARA_MODERACION`, y así lo pedía el prompt: el error es del orquestador. Con ONVO, cada pago rechazado manda un `payment-intent.failed`, y su referencia nunca se guardó en un cobro:

- un rechazo en `_iniciar_cobro` no guarda la referencia;
- un "La quiero" rechazado hace rollback del pedido entero.

Ese evento termina como `SIN_COBRO`, con `error`, en `GET /moderacion/pagos/eventos`. Cada tarjeta rechazada llenaría la lista de moderación, y las discrepancias reales quedarían tapadas.

**Resultado esperado:**

- Solo `DISCREPANCIA` deja `error`.
- `SIN_COBRO` se marca procesado con `error` nulo. Es un caso esperado, y no hay dinero de por medio: si la pasarela tuviera dinero de un cobro nuestro, `_conciliar_sin_cobro` ya devolvería `DISCREPANCIA`.
- Actualizá la prueba `test_9b_06_referencia_desconocida_sin_dinero_queda_sin_cobro` para que espere `error` nulo.

### 2. Un 3DS abandonado se consulta a la pasarela cada minuto, para siempre

Es tu observación 10. `candidatos_vencimiento` toma los intentos con `Cobro.updated_at <= ahora - abandono_3ds`, y consultar no cambia `updated_at`. Un anticipo abandonado en un encargo `cotizado` se consulta a la pasarela en cada vuelta mientras el pedido siga abierto. ONVO no informa su límite de solicitudes (pregunta 15). Un 429 por estas consultas podría frenar pagos reales.

**Resultado esperado:**

- Cuando `_conciliar_intento` encuentra el intento todavía en espera (`_EN_ESPERA`), pospone la próxima consulta: el cobro recibe `updated_at = ahora`. Así la siguiente consulta llega recién `abandono_3ds` después (30 minutos).
- El cambio va en una función nueva de `src/services/pedidos.py`, `posponer_intento(session, *, cobro, ahora)`, que exige `esperando_autenticacion(cobro)`, asigna `updated_at` explícito y hace `flush`. `contratacion` no escribe columnas de modelos directamente.
- Prueba nueva en `tests/test_webhooks.py`, `test_9b_30_intento_en_espera_se_consulta_cada_media_hora`:
  - un anticipo en espera de 3DS;
  - `barrer` a los +31 minutos consulta una vez y no registra nada;
  - a los +32 minutos no consulta;
  - a los +62 minutos consulta otra vez.
  - Contá las llamadas espiando `consultar_cobro`.

## Alcance
Solo estos archivos:

- backend/src/services/webhooks.py
- backend/src/services/contratacion.py
- backend/src/services/pedidos.py
- backend/tests/test_webhooks.py

## Criterios de aceptación
- [ ] `python -m ruff check .` y `python -m ruff format --check .` pasan.
- [ ] `python -m pytest -q -W error::sqlalchemy.exc.SADeprecationWarning` pasa, con 535 pruebas o más.
- [ ] `grep -n "SIN_COBRO" src/services/webhooks.py` no la muestra dentro de `_PARA_MODERACION`.
- [ ] `git diff --name-only HEAD~1` (o desde el último commit del lote) lista solo archivos del alcance.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.

Un solo commit nuevo en la rama: `fix(backend): sin ruido de pagos rechazados para moderacion y consulta del 3DS cada media hora`. Sin push ni PR, y sin tocar `orquestacion/`.

## Cómo entregar
La salida literal de cada criterio, `git log --oneline develop..HEAD` y observaciones si las hay.

## Estilo
No usar guiones largos ni guiones medios en comentarios ni documentación. Comentarios en español.
