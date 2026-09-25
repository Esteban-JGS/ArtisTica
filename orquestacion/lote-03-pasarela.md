# [Lote 3] Capa de pasarela: contrato, adaptador falso y adaptador de ONVO

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-03-pasarela
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Los pedidos se cobran por hitos: un anticipo que se cobra de inmediato, y un saldo que se autoriza primero y se captura despues. **ArtísTica nunca custodia dinero:** lo custodia una pasarela externa, en modo marketplace, con una cuenta conectada por artista. La tarifa de ArtísTica cae en la cuenta principal y el neto se liquida directo al artista.

La pasarela elegida es **ONVO Pay**, pero **hay seis preguntas sin responder** que condicionan la integracion, y la decision de proveedor tiene que poder cambiarse. Por eso la pasarela vive detras de un contrato abstracto, y nada fuera de `src/payments/` sabe que ONVO existe.

Tu lote construye esa capa: el contrato, un adaptador falso completo para pruebas y para la demo academica, y el adaptador de ONVO.

### Lo que se sabe de ONVO

- Modo marketplace: cada artista es una cuenta conectada y completa un onboarding alojado por ONVO, donde registra su cuenta IBAN.
- Los cobros se hacen en nombre de la cuenta conectada.
- La comision de la plataforma se configura por cuenta conectada.
- La autorizacion diferida (autorizar ahora, capturar despues) existe solo para tarjeta en integraciones por API, y vence si no se captura.
- Metodos: tarjeta y SINPE Movil.

### Lo que no se sabe, y no podes asumir

1. Cuantos dias dura una autorizacion antes de vencer.
2. Si se puede retrasar la liquidacion al vendedor por transaccion.
3. Si el modo marketplace acepta SINPE Movil.
4. Si la comision se puede definir por cobro, o solo por cuenta.
5. Quien absorbe contracargos y reembolsos despues de liquidar, y si se revierte la comision de la plataforma en un reembolso.
6. Si una persona fisica sin actividad inscrita en Hacienda puede completar el onboarding.

**Cada una de estas incognitas se expresa como una capacidad declarada del adaptador**, nunca como una constante enterrada en el codigo.

## Estado actual del repositorio

- **No existe** `backend/src/payments/`.
- `backend/src/services/pedidos.py` (lote 2) recibe de la pasarela, como parametros: una `referencia_pasarela` por cobro, un `autorizado_hasta`, y un `HechosPasarela` con los cobros liberados, capturados y los montos reembolsados. La accion de soltar una autorizacion se llama `LIBERAR_AUTORIZACION`. **Tu lote no toca ese servicio**: lo conecta el lote 8. Pero los nombres y los tipos que devuelvas tienen que encajar con esos.
- La tabla `eventos_pasarela` ya existe, con restriccion unica sobre `(proveedor, evento_externo_id)`. **Tu lote no persiste eventos**: eso es el lote 9. Tu lote solo los verifica y los normaliza.
- `httpx` ya esta en las dependencias. No hace falta ninguna libreria nueva.
- `backend/src/core/config.py`: `Settings` con pydantic-settings.

## Objetivo

Que cualquier parte del backend pueda cobrar, autorizar, capturar, liberar, reembolsar y verificar webhooks a traves de un contrato unico, con un adaptador falso completo y un adaptador de ONVO aislado.

## Diseno

### Estructura

```
backend/src/payments/
├── __init__.py
├── contrato.py     Protocol, tipos de valor, enums, capacidades
├── errores.py      Taxonomia de errores
├── falsa.py        PasarelaFalsa, en memoria
├── onvo.py         PasarelaOnvo, con httpx
├── config.py       Configuracion propia del adaptador de ONVO
└── fabrica.py      obtener_pasarela()
```

### El contrato

`PasarelaDePagos` es un `typing.Protocol`. Todas las operaciones son `async`, salvo `capacidades`.

| Operacion | Devuelve | Hace |
|---|---|---|
| `capacidades` (propiedad) | `Capacidades` | Lo que este adaptador puede hacer |
| `crear_cuenta_conectada` | `CuentaConectada` | Inicia el onboarding del artista y devuelve la URL alojada |
| `consultar_cuenta` | `CuentaConectada` | Estado del onboarding |
| `configurar_tarifa` | `None` | Fija el porcentaje de la plataforma en una cuenta conectada. Lo usa el cambio de plan |
| `cobrar` | `ResultadoCobro` | Autoriza y captura en un paso. Es el anticipo |
| `autorizar` | `ResultadoCobro` | Autoriza sin capturar. Devuelve `autorizado_hasta` |
| `capturar` | `ResultadoCobro` | Captura una autorizacion, total o parcialmente |
| `liberar_autorizacion` | `ResultadoCobro` | Suelta una autorizacion sin capturar |
| `reembolsar` | `ResultadoReembolso` | Devuelve total o parcialmente un cobro capturado |
| `parsear_webhook` | `EventoRecibido` | Verifica la firma y normaliza el evento |

### Tipos de valor

Todos `dataclass(frozen=True)`. El dinero es siempre `Decimal`.

- `MetodoPago`: enum `tarjeta`, `sinpe_movil`.
- `EstadoCuenta`: enum `pendiente`, `completada`, `rechazada`.
- `EstadoOperacion`: enum `autorizado`, `capturado`, `liberado`.
- `Capacidades`: `metodos` (conjunto de `MetodoPago`), `autorizacion_diferida` (conjunto de metodos que la admiten), `dias_vigencia_autorizacion` (entero o `None` si se desconoce), `comision_por_cobro` (booleano), `revierte_comision_en_reembolso` (booleano o `None`), `soporta_idempotencia` (booleano).
- `SolicitudCobro`: `monto`, `moneda` (por defecto `CRC`), `metodo`, `cuenta_conectada_id`, `tarifa_porcentaje`, `descripcion`, `clave_idempotencia`, y `metadatos` (un mapping de texto a texto, donde quien llama pone ids de pedido y cobro). **La capa de pagos no conoce los pedidos**: solo transporta esos metadatos.
- `ResultadoCobro`: `referencia`, `estado`, `monto`, `autorizado_hasta` (nullable), `capturado_en` (nullable).
- `ResultadoReembolso`: `referencia_cobro`, `referencia_reembolso`, `monto`, `total_reembolsado`.
- `CuentaConectada`: `id`, `estado`, `url_onboarding` (nullable).
- `TipoEvento`: enum `cobro_autorizado`, `cobro_capturado`, `cobro_fallido`, `autorizacion_vencida`, `reembolso_confirmado`, `cuenta_actualizada`, `desconocido`.
- `EventoRecibido`: `proveedor`, `evento_externo_id`, `tipo`, `referencia` (nullable), `payload`. Coincide con las columnas de `eventos_pasarela`.

**Una referencia por cobro.** La referencia que devuelve `autorizar` es la misma que se usa para `capturar`, `liberar_autorizacion` y `reembolsar`. Es la que el lote 2 guarda en `cobros.referencia_pasarela`.

### Errores

En `errores.py`, todos heredan de `ErrorPasarela`, que tiene un atributo `reintentable`:

| Error | Reintentable | Cuando |
|---|---|---|
| `PagoRechazado` | No | La pasarela rechazo el pago: fondos, tarjeta, antifraude |
| `PasarelaNoDisponible` | Si | Timeout, error 5xx, red |
| `CredencialesInvalidas` | No | 401 o 403. Es un error de configuracion |
| `SolicitudInvalida` | No | Datos incoherentes: capturar mas de lo autorizado, reembolsar mas de lo capturado, misma clave de idempotencia con datos distintos |
| `AutorizacionVencida` | No | Capturar una autorizacion que ya vencio |
| `OperacionNoSoportada` | No | La operacion o el metodo no esta en las capacidades |
| `FirmaInvalida` | No | El webhook no pasa la verificacion |

El lote 9 va a decidir si reintenta un job mirando solo `reintentable`. Por eso tiene que ser correcto en cada caso.

### Reglas que cumple todo adaptador

- Rechaza montos que no sean `Decimal` con `TypeError`, y montos menores o iguales a cero con `SolicitudInvalida`.
- Toda operacion que mueve dinero exige una `clave_idempotencia` no vacia.
- Antes de llamar al proveedor, verifica las capacidades: `autorizar` con un metodo que no admite autorizacion diferida levanta `OperacionNoSoportada`.
- Ningun secreto aparece en `repr`, en `str`, en mensajes de error ni en logs. Los secretos son `SecretStr`.

### El adaptador falso

`PasarelaFalsa`, en memoria, determinista. Es lo que usan las pruebas y **la demo de noviembre**, asi que tiene que comportarse como una pasarela de verdad, no devolver siempre exito.

- Recibe `reloj` (un callable que devuelve un `datetime` con zona horaria) y `capacidades` en el constructor, con valores por defecto razonables: tarjeta y SINPE, autorizacion diferida solo para tarjeta, 7 dias de vigencia, comision por cuenta, idempotencia soportada.
- Lleva el estado de cada cobro: autorizado, monto capturado, monto reembolsado, vencimiento.
- **Idempotencia real:** la misma clave con los mismos datos devuelve el mismo resultado sin repetir el efecto. La misma clave con datos distintos levanta `SolicitudInvalida`.
- `programar_falla(operacion, error)`: la proxima llamada a esa operacion levanta ese error. Asi se prueban los caminos de fallo.
- Firma webhooks con HMAC SHA256 del cuerpo y un secreto propio, y los verifica con `hmac.compare_digest`. Expone `firmar(cuerpo)` para que las pruebas construyan webhooks validos.
- `completar_onboarding(cuenta_id)` simula que el artista termino el onboarding.

### El adaptador de ONVO

`PasarelaOnvo`, con `httpx.AsyncClient`. Recibe el cliente por inyeccion, para que las pruebas usen `httpx.MockTransport` y **nunca toquen la red**.

**Regla de honestidad, la mas importante del lote:** no inventes la API de ONVO.

- Si tenes acceso a la documentacion oficial de ONVO Pay, usala. Cada ruta y cada nombre de campo lleva un comentario con la URL de la documentacion de donde sale.
- Lo que no puedas confirmar va marcado `POR_CONFIRMAR` en un comentario, y **todo el mapeo** (rutas, nombres de campos, nombres de eventos, encabezados) vive en un solo bloque de constantes al principio de `onvo.py`. Asi, cuando lleguen las respuestas, se corrige en un solo lugar.
- Las capacidades de ONVO que dependen de las seis preguntas quedan en su valor mas conservador: `dias_vigencia_autorizacion=None`, `autorizacion_diferida` solo tarjeta, `comision_por_cobro=False`, `revierte_comision_en_reembolso=None`, SINPE fuera de `metodos` hasta que se confirme.
- Si la verificacion de firma de webhooks de ONVO no se puede confirmar, `parsear_webhook` levanta `OperacionNoSoportada` con un mensaje claro. **Es preferible un error honesto a una verificacion inventada**, porque una firma mal verificada deja entrar pagos falsos.
- La conversion de `Decimal` a la unidad que espera el proveedor vive en una sola funcion, con prueba. Si la unidad no esta confirmada, marcala `POR_CONFIRMAR`.
- Timeout configurado en el cliente. `httpx.TimeoutException` y los errores de red se traducen a `PasarelaNoDisponible`.

### Configuracion

- `backend/src/core/config.py`: un solo campo nuevo, `PASARELA: str = "falsa"`. Es texto libre a proposito, para que el nombre del proveedor no aparezca fuera de `payments/`. La fabrica lo valida.
- `backend/src/payments/config.py`: un `BaseSettings` propio con prefijo `ONVO_`: `ONVO_API_KEY` (`SecretStr`, opcional), `ONVO_BASE_URL` (opcional), `ONVO_WEBHOOK_SECRET` (`SecretStr`, opcional), y un timeout.
- `fabrica.obtener_pasarela()`: devuelve la falsa por defecto. Con `PASARELA=onvo` y sin clave, falla al construir con un mensaje que dice que variable falta. Un valor desconocido de `PASARELA` tambien falla con mensaje claro.

## Alcance

Podes crear o modificar:

- `backend/src/payments/__init__.py` (crear)
- `backend/src/payments/contrato.py` (crear)
- `backend/src/payments/errores.py` (crear)
- `backend/src/payments/falsa.py` (crear)
- `backend/src/payments/onvo.py` (crear)
- `backend/src/payments/config.py` (crear)
- `backend/src/payments/fabrica.py` (crear)
- `backend/src/core/config.py` (solo el campo `PASARELA`)
- `backend/.env.example` (documentar `PASARELA` y las variables `ONVO_`)
- `backend/tests/test_pasarela_contrato.py` (crear)
- `backend/tests/test_pasarela_onvo.py` (crear)

## Prohibido

- Tocar cualquier archivo fuera de esa lista. En especial `mobile/`, `backend/src/services/**`, `backend/src/domain/**`, `backend/src/models/**`, `backend/src/api/**`, `backend/src/workers/**`, la migracion y `backend/pyproject.toml`.
- Crear una migracion.
- Que `payments/` importe algo de `src.models`, `src.domain` o `src.services`. La capa de pagos no conoce el dominio.
- Que algo fuera de `payments/` mencione a ONVO o importe su adaptador directamente. Todo pasa por la fabrica y el contrato.
- **Inventar rutas, campos o mecanismos de firma de ONVO.** Lo no confirmado se marca `POR_CONFIRMAR`.
- Pruebas que hagan llamadas de red reales.
- Usar `float` para dinero o porcentajes.
- Persistir eventos o cobros en la base. Esta capa no toca la base.
- Agregar librerias nuevas.

## Pruebas obligatorias

**Del contrato**, en `test_pasarela_contrato.py`, contra `PasarelaFalsa`:

1. `cobrar` deja el cobro capturado de inmediato.
2. `autorizar` fija `autorizado_hasta` segun la vigencia de las capacidades y el reloj inyectado.
3. `capturar` total y parcial funcionan; capturar mas de lo autorizado levanta `SolicitudInvalida`.
4. Capturar despues de `autorizado_hasta` levanta `AutorizacionVencida`.
5. Despues de `liberar_autorizacion`, capturar falla.
6. Reembolso parcial y total funcionan, y `total_reembolsado` acumula; reembolsar mas de lo capturado levanta `SolicitudInvalida`.
7. **Idempotencia:** la misma clave dos veces devuelve el mismo resultado y hay un solo efecto; la misma clave con otro monto levanta `SolicitudInvalida`.
8. `autorizar` con un metodo sin autorizacion diferida levanta `OperacionNoSoportada`.
9. Un webhook firmado se verifica y se normaliza; un cuerpo alterado levanta `FirmaInvalida`; un tipo de evento desconocido se normaliza a `desconocido` en vez de fallar.
10. Fallas programadas: `PagoRechazado` con `reintentable` falso, `PasarelaNoDisponible` con `reintentable` verdadero.
11. Un monto `float` levanta `TypeError`; un monto cero o negativo, `SolicitudInvalida`.

**Del adaptador de ONVO**, en `test_pasarela_onvo.py`, con `httpx.MockTransport`:

12. Cada operacion arma la solicitud que dice el bloque de mapeo: metodo, ruta, autenticacion y cuerpo, con el monto en la unidad del proveedor.
13. Mapeo de errores: un rechazo del proveedor es `PagoRechazado`; 401 es `CredencialesInvalidas`; 5xx y timeout son `PasarelaNoDisponible`.
14. La clave de API no aparece en el `repr` del adaptador, del config, ni en el mensaje de ningun error.
15. La conversion de montos no pierde centimos.

**De la fabrica**, en cualquiera de los dos archivos:

16. Sin configurar nada devuelve la falsa; `PASARELA=onvo` sin clave falla con un mensaje que nombra la variable; un valor desconocido falla.

Nombrá las pruebas con prefijo `test_01_` a `test_16_`, para que se puedan contar.

## Criterios de aceptacion

Con la salida de cada comando pegada. Las variables de entorno obligatorias estan en `backend/AGENTS.md`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `python -c "import src.main; import src.payments.fabrica; import src.payments.falsa; import src.payments.onvo"` no lanza excepcion.
- [ ] `pytest -v` pasa, y la salida muestra las dieciseis pruebas obligatorias. Las pruebas del lote 2 siguen pasando.
- [ ] Nada fuera de `payments/` menciona a ONVO: `grep -rniI "onvo" backend/src --exclude-dir=payments` no devuelve nada.
- [ ] La capa de pagos no conoce el dominio: `grep -rnE "from src\.(models|domain|services)|import src\.(models|domain|services)" backend/src/payments/` no devuelve nada.
- [ ] Las pruebas de ONVO no usan red: `grep -n "MockTransport" backend/tests/test_pasarela_onvo.py` devuelve al menos una linea, y ninguna prueba construye un cliente sin transporte simulado.
- [ ] `grep -rn "Mapped\[float\]\|: float" backend/src/` no devuelve nada.
- [ ] El bloque de mapeo de ONVO existe y cada entrada tiene fuente o `POR_CONFIRMAR`: pegá el bloque completo en la entrega.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `feat/lote-03-pasarela` **solo los archivos del alcance**, con un mensaje convencional (`feat(backend): ...`). No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. El bloque de mapeo de ONVO completo.
5. **Una tabla de lo que quedo `POR_CONFIRMAR`**, con lo que habria que preguntarle a ONVO para cerrarlo.
6. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
