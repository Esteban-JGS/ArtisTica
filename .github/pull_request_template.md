<!--
Titulo del PR: igual que un commit convencional, porque se fusiona con squash
y el titulo pasa a ser el commit de develop.
  tipo(alcance): descripcion en minusculas y sin punto final
  Ejemplo: feat(backend): lote 2, maquina de estados de pedidos y cobros
Tipos: feat, fix, refactor, test, docs, chore, design
Alcances: backend, mobile, orquestacion, agentes, ci
-->

## Resumen

<!-- Que cambia y por que, en dos o tres lineas. El por que importa mas que el que. -->

## Area y lote

- **Area:** <!-- backend / mobile / docs / infraestructura -->
- **Lote:** <!-- numero y nombre, o "no aplica" -->
- **Prompt:** <!-- ruta en orquestacion/, o "no aplica" -->

## Cambios principales

<!-- Lista corta. Los cambios de puro formato no se listan. -->

-

## Decisiones tomadas

<!-- Lo que se decidio y no era obvio, con la razon. Si nada, borrar la seccion. -->

## Como se verifico

<!-- Salida literal de los comandos, no una afirmacion. Un criterio sin evidencia no esta cumplido. -->

```
```

## Lista de control

- [ ] El titulo sigue el formato de commit convencional.
- [ ] No toca el territorio de otra persona (`backend/` y `mobile/` no se cruzan).
- [ ] No sube secretos ni un `.env` real.
- [ ] El CI pasa.

**Si toca `backend/`:**

- [ ] `ruff check .`, `ruff format --check .` y `pytest` pasan.
- [ ] Ninguna columna de saldo, disponible, retenido o acumulado.
- [ ] El dinero es `Decimal` sobre `Numeric`, nunca `float`.
- [ ] Toda tabla nueva tiene RLS activo y sin politicas.
- [ ] Como maximo una migracion, y reversible.
- [ ] Si toca pagos: el estado del pedido y el del cobro cambian en la misma transaccion.

## Deuda y observaciones

<!-- Lo que queda pendiente, con el lote donde se paga. Si nada, escribir "ninguna". -->
