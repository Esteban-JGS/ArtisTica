# [Lote 5e] Correctivo: estados de reembolso en la consulta de cobro

Seguí en la misma rama, sin crear otra:

```
git switch fix/lote-05e-deuda-pagos
git branch --show-current
```

## Por que

La tabla de estados del prompt dejaba fuera `refunded` y `partially_refunded`, que estan en el enum documentado de `PaymentIntent.status` y que ONVO produce cuando alguien reembolsa desde el dashboard. Hoy `consultar_cobro` levanta `ErrorPasarela` con un cobro reembolsado, y el lote 9 va a consultar el cobro antes de mover dinero: un reembolso legitimo se volveria un error de reconciliacion. El error es del prompt, no tuyo.

## Cambios

Solo en `backend/src/payments/onvo.py`, `backend/src/payments/falsa.py` y `backend/tests/test_pasarela_deuda.py`:

1. **`refunded` y `partially_refunded` se mapean a `capturado`**, con la fuente del enum en el bloque de mapeo. El dinero se capturo; el reembolso es otro dato.
2. **`monto_capturado` es `None` en esos dos estados.** Como `receivedAmount` baja con cada reembolso, ahi informa el neto y no lo capturado. En `succeeded` se sigue leyendo de `receivedAmount`. Comentalo en el codigo.
3. **El comentario de `DIAS_VIGENCIA_AUTORIZACION`** cita la descripcion de `captureMethod` en el `openapi.yaml` ("maximo de 30 dias") y aclara que es un **maximo, no un minimo garantizado**: el emisor de la tarjeta puede vencer antes. El valor **sigue en `None`**, para que rija el plazo propio de 5 dias (D9). No cambies el valor.
4. **`total_cuentas` pasa a propiedad**, igual que `total_cobros`. Ajustá la prueba 7.
5. **Pruebas:** sumá `refunded` y `partially_refunded` a la parametrizacion de `test_05_`, verificando estado `capturado` y `monto_capturado` igual a `None`.

## Criterios

Con la salida pegada, desde `backend/`:

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `pytest -q` pasa, con 292 pruebas (las 290 de ahora mas las dos filas nuevas).
- [ ] `grep -n "refunded" src/payments/onvo.py` muestra las dos entradas del mapeo con su fuente.
- [ ] `git diff --stat HEAD~1` (o el rango de tus commits nuevos) muestra solo los tres archivos.

Un solo commit nuevo, por ejemplo `fix(backend): reembolsos de ONVO en la consulta de cobro`. No reescribas los commits anteriores. No commitees nada de `orquestacion/`, no hagas push ni abras PR.

Entregá la salida de cada criterio y, si hace falta, observaciones.
