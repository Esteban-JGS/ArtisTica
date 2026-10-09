# [Lote 8] Contrato de pagos con 3DS

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-08-contrato-3ds
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

Verificá tambien que `develop` ya trae el lote 7: `backend/alembic/versions/c2d3e4f5a6b7_consultas_chat.py` tiene que existir. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Los cobros pasan por una pasarela detras de un contrato abstracto (`src/payments/`): un adaptador real de ONVO Pay y uno falso en memoria para pruebas y para la demo. Nada fuera de `src/payments/` sabe que existe ONVO.

Con tarjeta, el banco puede pedir autenticacion 3D Secure. El flujo acordado con la app movil:

1. La app tokeniza la tarjeta contra ONVO con la clave publicable y le manda a la API solo el `medio_pago_id`.
2. El backend crea la intencion de pago y la confirma con ese id y un `returnUrl`.
3. Si ONVO responde `requires_action`, la API le devuelve a la app la URL de autenticacion (`nextAction.redirectToUrl.url`). La app la abre en el navegador y, al volver, le pide a la API el estado.
4. La API consulta la intencion en ONVO antes de registrar nada como pagado.

Hoy el contrato no puede expresar el paso 3: ONVO levanta `OperacionNoSoportada` ante `requires_action`. Este lote solo cambia el contrato y los dos adaptadores. Los endpoints que lo usan son el lote 8b.

Documentacion de ONVO, consultada el 2026-10-08 en `https://docs.onvopay.com/payments/three-ds`:

- El cuerpo de `POST /v1/payment-intents/{id}/confirm` lleva `paymentMethodId` y `returnUrl`.
- La confirmacion responde `status: "requires_action"` con `nextAction: {"type": "redirect_to_url", "redirectToUrl": {"url": ..., "returnUrl": ...}}`.
- Al terminar la autenticacion, ONVO redirige al `returnUrl` con el parametro `payment_intent_id`. Que la autenticacion salga bien no garantiza que el pago se apruebe: hay que consultar la intencion.

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `backend/src/payments/contrato.py` | `EstadoOperacion` (`autorizado`, `capturado`, `liberado`); `EstadoCobroPasarela` ya tiene `requiere_accion`. `SolicitudCobro` con `medio_pago_id`. `ResultadoCobro` y `ConsultaCobro` sin URL de autenticacion. `CuentaConectada.url_onboarding` usa `field(default=None, repr=False)`: es el patron para una URL sensible |
| `backend/src/payments/onvo.py` | `_crear_y_confirmar` (alrededor de la linea 572) manda solo `paymentMethodId` al confirmar. `_exigir_estado` (alrededor de la linea 800) levanta `OperacionNoSoportada` con `requires_action`. `ESTADOS_COBRO` ya mapea `requires_action` a `REQUIERE_ACCION`. Cada constante del bloque de mapeo lleva su fuente o `POR_CONFIRMAR` |
| `backend/src/payments/falsa.py` | `_Cobro` guarda el estado como `EstadoOperacion`. `MEDIO_PAGO_RECHAZADO` simula un rechazo. `_foto_de` arma el estado de `consultar_cobro`. Idempotencia real con `_repetido` y `_recordar` |
| `backend/tests/test_pasarela_contrato.py` | Pruebas `test_01` a `test_11` y `test_16` sobre la pasarela falsa, con un reloj inyectado |
| `backend/tests/test_pasarela_onvo.py` | Pruebas `test_12` a `test_15` con un transporte simulado (`Simulador`, `intencion(estado, **extra)`, `cuerpo(solicitud)`) |
| `backend/tests/test_pasarela_deuda.py` | Pruebas de la deuda del lote 5e. La linea 214 ya verifica que `consultar_cobro` mapea `requires_action` |

## Objetivo

Que `cobrar` y `autorizar` devuelvan un resultado "requiere accion" con la URL de autenticacion en lugar de fallar, y que la pasarela falsa simule el 3DS completo para las pruebas y la demo.

## Alcance

- `backend/src/payments/contrato.py`
- `backend/src/payments/onvo.py`
- `backend/src/payments/falsa.py`
- `backend/tests/test_pasarela_contrato.py` (solo agregar pruebas)
- `backend/tests/test_pasarela_onvo.py` (agregar pruebas y ajustar las que esperaban `OperacionNoSoportada` por 3DS, si hay)
- `backend/tests/test_pasarela_deuda.py` (solo si una prueba existente deja de valer por este cambio; decí cual en observaciones)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular `mobile/`, `src/services/`, `src/api/`, `src/models/` y las migraciones.
- Agregar librerias.
- Que algo fuera de `src/payments/` tenga que conocer a ONVO.
- Registrar o devolver la URL de autenticacion en un `repr`, un log o un mensaje de error.
- Dar por pagado un cobro porque el cliente volvio del 3DS: el estado final sale siempre de `consultar_cobro`.
- `float` para dinero, o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Trabajo a realizar

### 1. Contrato

- `EstadoOperacion.REQUIERE_ACCION = "requiere_accion"`.
- `SolicitudCobro.url_retorno: str | None = None`. A donde vuelve el cliente despues del 3DS. Se valida en `validar_solicitud` con una funcion nueva `validar_url_retorno`: si viene, tiene que tener esquema (`https://...` o uno propio como `artistica://...`), sin espacios, y no puede ser vacia. Si no, `SolicitudInvalida`.
- `ResultadoCobro.url_autenticacion: str | None = field(default=None, repr=False)`. Solo con `estado == REQUIERE_ACCION`, y en ese caso nunca nula.
- `ConsultaCobro.url_autenticacion: str | None = field(default=None, repr=False)`. Con `estado == REQUIERE_ACCION`, la URL si el proveedor la informa.
- Docstrings de `cobrar` y `autorizar` en el protocolo: devuelven el resultado final, o `REQUIERE_ACCION` con la referencia y la URL. En ese caso el cobro todavia no movio dinero, y quien llama sigue con `consultar_cobro(referencia)` hasta ver `AUTORIZADO`, `CAPTURADO`, `FALLIDO` o `LIBERADO`.

### 2. Adaptador de ONVO

- Bloque de mapeo: `CAMPO_URL_RETORNO = "returnUrl"`, `CAMPO_ACCION_SIGUIENTE = "nextAction"`, `CAMPO_REDIRIGIR = "redirectToUrl"`, `CAMPO_URL = "url"` y `ACCION_REDIRIGIR = "redirect_to_url"`, con la fuente de arriba en un comentario.
- `_crear_y_confirmar` manda `returnUrl` en la confirmacion cuando la solicitud trae `url_retorno`.
- Si la confirmacion vuelve en `requires_action`, `cobrar` y `autorizar` devuelven `ResultadoCobro(estado=REQUIERE_ACCION, referencia=<id de la intencion>, monto=<monto de la solicitud>, url_autenticacion=<nextAction.redirectToUrl.url>)`. Si `nextAction` no es `redirect_to_url` o no trae la URL, se levanta el mismo error que hoy da `_respuesta_inesperada` (no reintentable).
- `consultar_cobro` completa `url_autenticacion` desde `nextAction` cuando el estado es `requires_action`.
- `capturar`, `liberar_autorizacion` y `reembolsar` no cambian. `_exigir_estado` ya no menciona 3DS como no soportado en los caminos de `cobrar` y `autorizar`.
- `POR_CONFIRMAR`: si ONVO acepta un `returnUrl` con esquema propio, y si una intencion en `requires_action` se puede cancelar. Las dos ya estan en `orquestacion/preguntas-onvo.md`; solo referencialas en el comentario.

### 3. Pasarela falsa

- `MEDIO_PAGO_3DS = "medio_falso_3ds"`. Con ese `medio_pago_id`, `cobrar` y `autorizar` dejan el cobro en `REQUIERE_ACCION` y devuelven `url_autenticacion = "https://pasarela-falsa.invalid/3ds/<referencia>"`. La falsa recuerda si el cobro era diferido.
- `completar_autenticacion(referencia: str, *, aprobada: bool) -> None`, para pruebas y demo:
  - Aprobada y diferido: `AUTORIZADO`, con `autorizado_hasta` calculado con el reloj en ese momento, igual que `autorizar`.
  - Aprobada y no diferido: `CAPTURADO`, con `capturado_en`.
  - Rechazada: el cobro queda fallido. `consultar_cobro` da `FALLIDO`, y capturar o reembolsar dan `SolicitudInvalida`.
  - Sobre un cobro que no esta en `REQUIERE_ACCION`: `SolicitudInvalida`.
- `consultar_cobro` refleja cada estado, con `url_autenticacion` mientras siga en `REQUIERE_ACCION`.
- `liberar_autorizacion` sobre un cobro en `REQUIERE_ACCION` lo deja `LIBERADO`: es como se anula una autenticacion abandonada.
- `capturar` y `reembolsar` sobre un cobro en `REQUIERE_ACCION`: `SolicitudInvalida`.
- Idempotencia: repetir `cobrar` o `autorizar` con la misma clave devuelve el mismo resultado guardado, aunque la autenticacion ya se haya completado. El estado vigente se lee con `consultar_cobro`. Documentalo en el docstring.
- `inspeccionar_cobro` sigue funcionando con los estados nuevos.

## Pruebas obligatorias

Con prefijo `test_8_01_` en adelante. Las de la falsa en `test_pasarela_contrato.py`, las de ONVO en `test_pasarela_onvo.py`.

Pasarela falsa:

1. `cobrar` con `MEDIO_PAGO_3DS` devuelve `REQUIERE_ACCION`, referencia y la URL. `consultar_cobro` da `REQUIERE_ACCION` con la misma URL. Aprobada: `consultar_cobro` da `CAPTURADO` con `monto_capturado` igual al monto.
2. `autorizar` con `MEDIO_PAGO_3DS` y aprobada: `AUTORIZADO`, con `autorizado_hasta` igual al reloj de ese momento mas los dias de las capacidades. Despues `capturar` funciona.
3. Rechazada: `FALLIDO`, y `capturar` da `SolicitudInvalida`.
4. `liberar_autorizacion` sobre un cobro en `REQUIERE_ACCION`: `LIBERADO`. `completar_autenticacion` sobre ese cobro: `SolicitudInvalida`.
5. `capturar` antes de completar la autenticacion: `SolicitudInvalida`.
6. Idempotencia: la misma clave devuelve la misma referencia y el mismo resultado, antes y despues de completar.
7. `url_retorno` vacia, con espacios o sin esquema: `SolicitudInvalida`. Con `https://...` o `artistica://pago`, se acepta.
8. `repr` de `ResultadoCobro` y de `ConsultaCobro` no contiene la URL de autenticacion.
9. Sin `MEDIO_PAGO_3DS`, `cobrar` y `autorizar` siguen devolviendo `CAPTURADO` y `AUTORIZADO` sin URL (no cambio nada).

ONVO, con el transporte simulado:

10. La confirmacion lleva `paymentMethodId` y `returnUrl` cuando hay `url_retorno`, y no lleva `returnUrl` cuando no hay.
11. Una confirmacion en `requires_action` con `nextAction.redirectToUrl.url` devuelve `REQUIERE_ACCION` con esa URL, en `cobrar` y en `autorizar`.
12. Una confirmacion en `requires_action` sin `nextAction`, o con otro `type`, levanta el error no reintentable.
13. `consultar_cobro` de una intencion en `requires_action` devuelve la URL de `nextAction`.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `pytest -q` pasa, con las 366 anteriores mas las nuevas. Si alguna existente cambio, decí cual y por que.
- [ ] Desde `backend/`: `grep -rn "onvo\|ONVO" src --include=*.py | grep -v "^src/payments/"` no muestra nada nuevo respecto de `develop`.
- [ ] Desde `backend/`: `alembic check` sin diferencias (este lote no toca el esquema).
- [ ] Desde la raiz: `bash .github/scripts/reglas-del-repositorio.sh` pasa.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance.

## Commit y entrega

Commiteá en `feat/lote-08-contrato-3ds` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `feat(backend): contrato de pagos con autenticacion 3DS` y `feat(backend): 3DS en la pasarela falsa y en el adaptador de ONVO`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá la salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`, la salida literal de cada criterio, y observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
