# [Lote 5e] Deuda: contrato de pagos

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c fix/lote-05e-deuda-pagos
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. **ArtísTica nunca custodia dinero:** lo custodia una pasarela externa en modo marketplace, con una cuenta conectada por artista. La pasarela vive detras de un contrato abstracto (`src/payments/contrato.py`) con dos adaptadores: uno falso en memoria, para pruebas y demo, y uno de ONVO Pay. Nada fuera de `src/payments/` sabe que ONVO existe.

Este lote no agrega flujos nuevos: paga tres deudas del contrato que los lotes 8 y 9 necesitan resueltas.

| # | Problema | Resultado esperado |
|---|---|---|
| DT11 | ONVO no firma el cuerpo de los webhooks: manda el secreto tal cual. El secreto prueba el origen, no la integridad. La regla para el lote 9 es **nunca mover dinero por un webhook solo, sino consultar antes el cobro a la pasarela**, pero el contrato no tiene una operacion de consulta | El contrato tiene `consultar_cobro`, implementada en los dos adaptadores |
| DT12 | ONVO no informa cuanto dura una autorizacion, asi que `autorizado_hasta` vuelve nulo, y el servicio de pedidos exige una fecha. La politica decidida (D9) es suponer 5 dias, configurable | La politica existe en configuracion y en `PoliticasPedido`, con una funcion que da el vencimiento efectivo |
| DT17 | Si la pasarela crea la cuenta conectada y despues falla el commit, el siguiente intento crea otra cuenta. `crear_cuenta_conectada` no recibe clave de idempotencia ni metadatos | `crear_cuenta_conectada` recibe clave de idempotencia y metadatos; el adaptador falso la respeta y el servicio de perfiles la usa |

Usar `consultar_cobro` al recibir un webhook es trabajo del lote 9, y aplicar el vencimiento efectivo al autorizar es del lote 8. Aca solo se construyen las piezas y se prueban.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno obligatorias y la base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) estan en `AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/payments/contrato.py` | `PasarelaDePagos` (Protocol, `runtime_checkable`) con `crear_cuenta_conectada(*, nombre, tarifa_porcentaje)`, `consultar_cuenta`, `configurar_tarifa`, `cobrar`, `autorizar`, `capturar`, `liberar_autorizacion`, `reembolsar`, `parsear_webhook`. `EstadoOperacion` tiene `autorizado`, `capturado` y `liberado`. `ResultadoCobro` lleva `referencia`, `estado`, `monto`, `autorizado_hasta`, `capturado_en`. `SolicitudCobro.metadatos` lleva los ids de pedido y cobro. Helpers `validar_referencia`, `validar_clave` |
| `src/payments/falsa.py` | Estado en memoria. Idempotencia real con `_repetido` y `_recordar` (misma clave y misma huella devuelve lo mismo; misma clave con otra huella falla). `programar_falla`, `completar_onboarding`, `tarifa_de`, `inspeccionar_cobro`, `total_cobros`, reloj inyectable. `OPERACIONES` lista las operaciones que admiten `programar_falla` |
| `src/payments/onvo.py` | Bloque de mapeo con fuentes o `POR_CONFIRMAR`. `ENCABEZADO_IDEMPOTENCIA = None`: ONVO no documenta idempotencia. Estados de intencion: `succeeded`, `requires_capture`, `canceled`, `requires_action`, y `requires_payment_method` o `failed` como rechazo (`lastPaymentError` trae el motivo). `_solicitar(..., repetible=...)` decide si un error incierto es reintentable. `DIAS_VIGENCIA_AUTORIZACION = None` |
| `src/payments/__init__.py` | Reexporta los tipos del contrato y los errores |
| `src/core/config.py` | Politicas de pedido (D5) con sus valores por defecto. No existe `DIAS_VIGENCIA_AUTORIZACION_SUPUESTA` |
| `src/domain/politicas.py` | `PoliticasPedido`, dataclass congelado **sin valores por defecto**, con validaciones en `__post_init__` y `desde_config(config)` |
| `src/services/perfiles.py` | `iniciar_onboarding` llama `pasarela.crear_cuenta_conectada(nombre=..., tarifa_porcentaje=...)` con el perfil bloqueado |
| `tests/test_pasarela_contrato.py`, `tests/test_pasarela_onvo.py` | Pruebas `test_01_` a `test_16_` y `test_01_` a `test_15_`. Las de ONVO usan `httpx.MockTransport` y no tocan la red |

## Objetivo

Que el contrato de pagos permita consultar un cobro, crear cuentas conectadas de forma idempotente y calcular el vencimiento efectivo de una autorizacion, con los dos adaptadores y el servicio de perfiles al dia.

## Diseno

### 1. Consulta de cobro (DT11)

En `contrato.py`:

```python
class EstadoCobroPasarela(enum.StrEnum):
    PENDIENTE = "pendiente"              # creado o en proceso, sin resultado
    REQUIERE_ACCION = "requiere_accion"  # 3DS u otra accion del cliente
    AUTORIZADO = "autorizado"            # capturable
    CAPTURADO = "capturado"
    LIBERADO = "liberado"                # cancelado, o autorizacion vencida
    FALLIDO = "fallido"

@dataclass(frozen=True, kw_only=True)
class ConsultaCobro:
    referencia: str
    estado: EstadoCobroPasarela
    monto: Decimal
    monto_capturado: Decimal | None      # None si el proveedor no lo informa
    monto_reembolsado: Decimal | None    # None si el proveedor no lo informa
    autorizado_hasta: datetime | None
    metadatos: Mapping[str, str]

# En PasarelaDePagos
async def consultar_cobro(self, referencia: str) -> ConsultaCobro: ...
```

`EstadoOperacion` **no cambia**: describe el resultado de una operacion, no la foto de un cobro. La consulta es de solo lectura, asi que siempre es repetible.

**Falsa:** responde desde su estado interno. Guarda los `metadatos` de la solicitud al cobrar o autorizar, para devolverlos. Una autorizacion cuyo `autorizado_hasta` ya paso segun el reloj se informa como `liberado`. Una referencia desconocida falla igual que hoy en las demas operaciones. Agregá `consultar_cobro` a `OPERACIONES`.

**ONVO:** `GET` de la intencion de pago. Sumá al bloque de mapeo la ruta y la tabla de estados, cada entrada con fuente o `POR_CONFIRMAR`:

| Estado de ONVO | `EstadoCobroPasarela` |
|---|---|
| `requires_confirmation`, `processing`, `deferred` | `pendiente` |
| `requires_payment_method` sin `lastPaymentError` | `pendiente` |
| `requires_payment_method` con `lastPaymentError`, `failed` | `fallido` |
| `requires_action` | `requiere_accion` |
| `requires_capture` | `autorizado` |
| `succeeded` | `capturado` |
| `canceled` | `liberado` |

Un estado que no esta en la tabla levanta `ErrorPasarela` (no se adivina). `monto_capturado` sale de `receivedAmount` si viene. `monto_reembolsado` queda en `None` salvo que la documentacion muestre de donde leerlo. `metadatos` sale de `metadata`, solo los pares texto a texto.

### 2. Vencimiento efectivo de una autorizacion (DT12)

- `src/core/config.py`: `DIAS_VIGENCIA_AUTORIZACION_SUPUESTA: int = Field(default=5, ge=1)`, junto a las demas politicas.
- `src/domain/politicas.py`: campo `vigencia_autorizacion_supuesta: timedelta`, validado positivo, cargado en `desde_config`, y un metodo:

```python
def vencimiento_autorizacion(
    self, informado: datetime | None, ahora: datetime
) -> datetime:
    """El que informa la pasarela, o ahora mas la vigencia supuesta (D9)."""
```

Si la pasarela informa una fecha, gana esa. `ahora` tiene que tener zona horaria; si no, `ValueError`.

### 3. Cuenta conectada idempotente (DT17)

Firma nueva en el contrato y en los dos adaptadores:

```python
async def crear_cuenta_conectada(
    self,
    *,
    nombre: str,
    tarifa_porcentaje: Decimal,
    clave_idempotencia: str,
    metadatos: Mapping[str, str] = {},  # usar un default inmutable
) -> CuentaConectada: ...
```

- **Falsa:** con la misma clave y los mismos datos devuelve la misma cuenta sin crear otra; con la misma clave y otros datos falla con `SolicitudInvalida`, igual que sus cobros. Agregá `total_cuentas()` como control de prueba.
- **ONVO:** valida la clave con `validar_clave`. Mientras `ENCABEZADO_IDEMPOTENCIA` sea `None`, no manda encabezado. Si la documentacion de ONVO admite metadatos en la cuenta conectada, mandalos con la fuente; si no, no los mandes y anotalo como `POR_CONFIRMAR`. Con ONVO el riesgo de cuenta duplicada sigue hasta que confirmen idempotencia: eso queda en observaciones.
- **Servicio de perfiles:** `iniciar_onboarding` pasa `clave_idempotencia=f"cuenta-conectada-{perfil.id}"` y `metadatos={"perfil_id": str(perfil.id)}`.

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `src/payments/contrato.py`
- `src/payments/falsa.py`
- `src/payments/onvo.py`
- `src/payments/__init__.py`
- `src/core/config.py` (solo la variable nueva)
- `src/domain/politicas.py`
- `src/services/perfiles.py` (solo la llamada a `crear_cuenta_conectada`)
- `tests/test_pasarela_deuda.py` (nuevo)
- Cualquier archivo de `tests/` que construya `PoliticasPedido` a mano o llame a `crear_cuenta_conectada`, solo para adaptarlo a las firmas nuevas
- `.env.example` (la variable nueva, en la seccion de politicas)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior. En particular `src/services/pedidos.py`, `src/domain/pedidos.py`, los endpoints y los modelos.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias.
- Cambiar `EstadoOperacion` o el comportamiento de las operaciones existentes.
- Que algo fuera de `src/payments/` mencione ONVO.
- Inventar un encabezado o un campo de ONVO sin fuente: lo que no este documentado va como `POR_CONFIRMAR` y no se envia.
- Pruebas que usen red.

## Pruebas obligatorias

En `tests/test_pasarela_deuda.py`, con prefijo `test_01_` a `test_10_`. Las de ONVO con `httpx.MockTransport`; podés copiar el helper minimo que necesites de `test_pasarela_onvo.py`.

1. **Falsa, autorizado.** Despues de `autorizar`, `consultar_cobro` da `autorizado`, el monto, `autorizado_hasta` y los mismos `metadatos` de la solicitud.
2. **Falsa, ciclo.** Despues de `capturar` da `capturado` con `monto_capturado`; despues de un `reembolsar` parcial informa `monto_reembolsado`; otra autorizacion liberada da `liberado`.
3. **Falsa, vencida.** Con el reloj despues de `autorizado_hasta`, la consulta da `liberado`.
4. **ONVO, solicitud.** `consultar_cobro` hace `GET` a la ruta del mapeo con la autorizacion, y una respuesta 5xx da `PasarelaNoDisponible` reintentable.
5. **ONVO, estados.** Parametrizada sobre cada fila de la tabla de la seccion 1, incluidos los dos casos de `requires_payment_method`. Un estado desconocido da `ErrorPasarela`.
6. **ONVO, datos.** `monto`, `monto_capturado` (desde `receivedAmount`) y `metadatos` salen bien convertidos; un metadato que no es texto se descarta.
7. **Cuenta idempotente en la falsa.** Misma clave y mismos datos: misma cuenta y `total_cuentas()` igual a 1. Misma clave con otro nombre: `SolicitudInvalida`. Otra clave: cuenta nueva.
8. **Cuenta en ONVO.** Una clave vacia da `SolicitudInvalida` sin llamar a la red; con clave valida, la solicitud no lleva encabezado de idempotencia mientras el mapeo diga `None`.
9. **Vencimiento efectivo.** Con fecha informada devuelve esa; con `None` devuelve `ahora` mas 5 dias; `ahora` sin zona horaria da `ValueError`; `DIAS_VIGENCIA_AUTORIZACION_SUPUESTA=0` no carga.
10. **Onboarding sin duplicar.** Con `sesion_api` y `pasarela_falsa`: llamar a `servicio.iniciar_onboarding`, hacer rollback del savepoint en vez de commit (simula que el commit fallo), y volver a llamarlo. La falsa tiene una sola cuenta y el id guardado es el mismo.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `pytest -v` pasa, muestra las diez pruebas obligatorias, y las 270 anteriores siguen pasando.
- [ ] `python -c "from src.payments import PasarelaDePagos; from src.payments.falsa import PasarelaFalsa; print(isinstance(PasarelaFalsa(), PasarelaDePagos))"` imprime `True`.
- [ ] `grep -rniI "onvo" src --exclude-dir=payments` no devuelve nada.
- [ ] `grep -n "consultar_cobro" src/payments/contrato.py src/payments/falsa.py src/payments/onvo.py` muestra la operacion en los tres.
- [ ] `grep -rn "crear_cuenta_conectada(" src` muestra que toda llamada pasa `clave_idempotencia`.
- [ ] El bloque de mapeo de ONVO con las entradas nuevas: pegalas en la entrega, cada una con fuente o `POR_CONFIRMAR`.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `fix/lote-05e-deuda-pagos` **solo los archivos del alcance**, con mensajes convencionales. Sugerencia: `feat(backend): consulta de cobro en el contrato de pagos`, `fix(backend): cuenta conectada con clave de idempotencia` y `feat(backend): vencimiento efectivo de una autorizacion`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. Las entradas nuevas del bloque de mapeo de ONVO, y una tabla de lo que quedo `POR_CONFIRMAR` con la pregunta concreta para ONVO.
5. Una tabla con DT11, DT12 y DT17 y la evidencia de que quedaron pagadas, o de que parte queda pendiente de ONVO.
6. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
