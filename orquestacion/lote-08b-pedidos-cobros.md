# [Lote 8b] Endpoints de pedidos y cobros

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-08b-pedidos-cobros
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

Verificá tambien que `develop` ya trae el lote 8: `grep -n "REQUIERE_ACCION" backend/src/payments/contrato.py` tiene que mostrar `EstadoOperacion.REQUIERE_ACCION`. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica. Este lote mueve dinero: leé el prompt completo antes de empezar.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Un cliente y un artista conversan en una **consulta** (lote 7). El artista cotiza y nace un **pedido**, con sus **cobros**: anticipo y saldo en un encargo o un evento, y un cobro total en una obra disponible. El dinero lo custodia la pasarela (ONVO, o una falsa en pruebas y demo); ArtísTica nunca guarda saldos.

| Tipo | Cobros |
|---|---|
| `encargo` | Anticipo cobrado al aceptar la cotizacion. Saldo autorizado cuando el cliente ve la vista previa, y capturado cuando la aprueba |
| `evento` | Anticipo cobrado al aceptar. Saldo cobrado antes de la fecha del evento |
| `obra_disponible` | "La quiero": total autorizado al confirmar, y capturado cuando el artista despacha con numero de guia |

Las reglas puras (`src/domain/pedidos.py`) y el registro en la base (`src/services/pedidos.py`) ya existen y estan probados, pero no tienen endpoints y **no llaman a la pasarela**: reciben los hechos que la pasarela ya confirmo. Este lote agrega la capa que llama a la pasarela y despues registra, y los endpoints.

Pago con tarjeta, acordado con la app (D23):

1. La app tokeniza la tarjeta contra ONVO y le manda a la API solo el `metodo_pago_id`.
2. La API cobra o autoriza. Si el banco pide 3D Secure, la pasarela devuelve `REQUIERE_ACCION` con una `url_autenticacion` (lote 8). La API se la devuelve a la app, que la abre en el navegador.
3. Al volver, la app llama a "verificar el cobro". La API consulta la pasarela y recien ahi registra el pago. Volver del navegador no prueba nada.

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `backend/src/services/pedidos.py` | Todas las transiciones, cada una bloquea el pedido con `FOR UPDATE`: `crear_pedido_desde_cotizacion` (bloquea la consulta, no el perfil), `actualizar_cotizacion`, `crear_pedido_obra_disponible` (crea la consulta ya `convertida`), `rechazar_pedido`, `registrar_anticipo_capturado`, `iniciar_trabajo`, `registrar_vista_previa` (vista previa y saldo autorizado en un solo paso), `registrar_saldo_capturado`, `confirmar_obra`, `registrar_despacho`, `planear_cancelacion`, `cancelar_pedido`, `abrir_disputa`. `_fijar_referencia` exige que un cobro no cambie de referencia de pasarela |
| `backend/src/domain/pedidos.py` | Tablas de transiciones, `cotizar`, `planear_cancelacion`, `HechosPasarela`, `verificar_hechos`, `rol_en_pedido`. No se toca |
| `backend/src/domain/politicas.py` | `PoliticasPedido.desde_config(settings)` y `vencimiento_autorizacion(informado, ahora)` (D9) |
| `backend/src/models/pedidos.py` | `Pedido` y `Cobro` (`referencia_pasarela` unica y nula, `pasarela`, `autorizado_hasta`, `capturado_en`, `monto_reembolsado`), `Entregable`, `Disputa` |
| `backend/src/services/perfiles.py` | `bloquear_perfil` y `exigir_cobro_habilitado(perfil)` (D10: el onboarding se exige recien al primer cobro) |
| `backend/src/payments/contrato.py` | `PasarelaDePagos` con `cobrar`, `autorizar`, `capturar`, `liberar_autorizacion`, `reembolsar`, `consultar_cobro`, `configurar_tarifa` y `capacidades` (`comision_por_cobro`). `SolicitudCobro` con `medio_pago_id`, `url_retorno`, `metadatos`, `clave_idempotencia` y `tarifa_porcentaje`. `ResultadoCobro` y `ConsultaCobro` con `url_autenticacion` |
| `backend/src/payments/falsa.py` | `MEDIO_PAGO_3DS`, `MEDIO_PAGO_RECHAZADO`, `completar_autenticacion(referencia, aprobada=...)`, `completar_onboarding(cuenta_id)`. Idempotencia real: misma clave con otros datos da `SolicitudInvalida` |
| `backend/src/payments/errores.py` | `PagoRechazado`, `AutorizacionVencida`, `PasarelaNoDisponible` |
| `backend/src/api/deps.py` | `Sesion`, `Usuario`, `Pasarela` (sobrescrita por el fixture `pasarela_falsa` de `tests/conftest.py`) |
| `backend/src/main.py` | `ErrorPasarela` da 502 y `PasarelaNoDisponible`, 503 |
| `backend/src/schemas/social.py` y `backend/src/schemas/medios.py` | `PerfilResumido.desde(perfil)` e `ImagenPublica.desde(medio, almacenamiento)` |
| `backend/tests/test_servicio_pedidos.py` | Usa `registrar_vista_previa` en las lineas 134 y 183 |
| `backend/tests/test_perfiles_api.py:81` | Llama a `crear_pedido_desde_cotizacion` con su firma actual |
| `backend/alembic/versions/` | Cabeza `c2d3e4f5a6b7` |

## Objetivo

Que cliente y artista recorran por la API los tres tipos de pedido, de la cotizacion al despacho o la aprobacion, con cancelacion y disputa, cobrando por la pasarela con 3DS y sin cobrar nunca dos veces.

## Alcance

- `backend/src/models/pedidos.py` (solo `Cobro.intentos`)
- `backend/alembic/versions/d3e4f5a6b7c8_intentos_de_cobro.py` (nuevo)
- `backend/src/services/pedidos.py`
- `backend/src/services/contratacion.py` (nuevo)
- `backend/src/schemas/pedidos.py` (nuevo)
- `backend/src/api/v1/pedidos.py` (nuevo)
- `backend/src/api/v1/router.py`
- `backend/src/core/config.py` (solo `URL_RETORNO_PAGO`)
- `backend/.env.example` y `backend/AGENTS.md` (la variable nueva)
- `backend/tests/test_servicio_pedidos.py` (adaptar a la vista previa en dos pasos y sumar pruebas)
- `backend/tests/test_pedidos_api.py` (nuevo)
- `backend/tests/test_cobros_api.py` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular `mobile/`, `src/domain/`, `src/payments/` y `src/services/consultas.py`.
- Agregar librerias.
- Que algo fuera de `src/payments/` conozca a ONVO.
- Registrar un pago porque el cliente volvio del 3DS: el estado sale siempre de `consultar_cobro`.
- Llamar a la pasarela antes de validar la transicion: primero se valida, despues se cobra, despues se registra.
- Bloquear filas en otro orden que **perfil del artista, pedido, consulta, obra** (D18, D21).
- Columnas de saldo, `float` para dinero, o un `noqa` sin codigo y motivo.
- Webhooks, vencimientos o reautorizacion de un saldo vencido: son el lote 9.
- Bucket privado, archivo final o resolucion de disputas: son el lote 8c.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Trabajo a realizar

### 1. Intentos de cobro

Un cobro rechazado o con 3DS fallido se reintenta con otra tarjeta. Como la clave de idempotencia tiene que ser la misma al repetir el **mismo** intento, y distinta en un intento **nuevo**, cada cobro cuenta sus intentos.

- `Cobro.intentos: int`, no nulo, `default=0` y `server_default` 0, con check `intentos >= 0`. No es un saldo: cuenta intentos.
- Migracion `d3e4f5a6b7c8`, `down_revision = "c2d3e4f5a6b7"`, reversible, `alembic check` limpio.

### 2. Servicio de pedidos (`src/services/pedidos.py`)

- **Vista previa en dos pasos (D24).** `registrar_vista_previa` se reemplaza por:
  - `entregar_vista_previa(session, *, pedido_id, media_asset_id, nota)`: encargo en `en_proceso`. El medio tiene que ser del artista del pedido, confirmado (`subido_en` no nulo), sin borrar, sin obra ni publicacion, y no usado en otro entregable. Si no es del artista o no existe, `ResourceNotFound`; si no cumple el resto, `ReglaDeNegocioViolada`. Crea el `Entregable` de tipo `vista_previa`. El pedido **sigue** en `en_proceso`. Se pueden entregar varias, una por revision.
  - `registrar_saldo_autorizado(session, *, pedido_id, referencia_pasarela, autorizado_hasta, ahora)`: lo que hacia la otra con el saldo, mas la exigencia de que exista al menos una vista previa. Pasa el pedido a `vista_previa_entregada`.
- **`crear_pedido_desde_cotizacion` bloquea el perfil del artista antes que la consulta.** Lee la consulta sin bloquear para saber quien es el artista, `bloquear_perfil`, y despues el bloqueo de la consulta que ya hace. Asi un cambio de plan no se cruza con la tarifa que se congela en el pedido (D8). La firma no cambia.
- **Lecturas** para la API, sin N+1:
  - `listar(session, usuario, como, estado, consulta_id, parametros)`: pedidos donde participa, con los filtros opcionales, paginados con `traer_pagina` por `created_at` descendente.
  - `detalle(session, usuario, pedido_id)`: un pedido donde participa.
  - Cada `PedidoDetalle` lleva el pedido, el cliente y el artista, el rol de quien mira, sus cobros y sus vistas previas con su medio, en un numero fijo de consultas por pagina. Un tercero recibe `ResourceNotFound`.

### 3. Contratacion (`src/services/contratacion.py`, nuevo)

Es la unica capa que llama a la pasarela para un pedido. Hace `flush`, nunca `commit`. Recibe `pasarela`, `ahora`, `politicas`, `url_retorno` y `nombre_pasarela` como parametros; no lee `settings` ni el reloj.

**Antes de toda operacion que mueve dinero**, en este orden:

1. Lee el pedido sin bloquear. Si quien llama no participa, `ResourceNotFound`; si participa pero no le corresponde la operacion, `ActorNoAutorizado`.
2. `bloquear_perfil` del **artista** del pedido. Despues bloquea el pedido.
3. Valida la transicion con las funciones del dominio. Si no corresponde, falla aca, sin llamar a la pasarela.
4. Para `cobrar` y `autorizar`: `exigir_cobro_habilitado(artista)`.
5. Tarifa (D8): si `pasarela.capacidades.comision_por_cobro`, la manda en `SolicitudCobro.tarifa_porcentaje`. Si no, `configurar_tarifa(artista.pasarela_cuenta_id, pedido.tarifa_porcentaje)` justo antes de `cobrar`, `autorizar` o `capturar`.

**Claves de idempotencia**, siempre deterministas:

| Operacion | Clave |
|---|---|
| `cobrar` o `autorizar` | `f"{operacion}-{cobro.id}-{cobro.intentos}"` |
| `capturar` | `f"capturar-{cobro.id}"` |
| `liberar_autorizacion` | `f"liberar-{cobro.id}-{cobro.intentos}"` |
| `reembolsar` | `f"reembolsar-{cobro.id}-{monto}"` |

Los `metadatos` llevan `pedido_id` y `cobro_id`.

**Iniciar un cobro** (`cobrar` o `autorizar`, con `metodo_pago_id` y `MetodoPago.TARJETA`):

- Si el cobro ya tiene `referencia_pasarela` y sigue `pendiente`, hay un intento anterior esperando 3DS. Primero se verifica como en `verificar_cobro`:
  - Si sigue en `REQUIERE_ACCION`, se devuelve otra vez su URL, sin crear otro intento.
  - Si ya quedo `AUTORIZADO` o `CAPTURADO`, se registra.
  - Si quedo `FALLIDO` o `LIBERADO`, se limpia la referencia, `intentos += 1`, y se sigue con un intento nuevo.
- `PagoRechazado`: `intentos += 1`, `flush`, y el resultado es `rechazado`. **No** se levanta la excepcion, para que la API confirme el incremento.
- `REQUIERE_ACCION`: se guarda la referencia en el cobro, que sigue `pendiente`, y se devuelve la URL.
- Resultado final: se registra con la funcion de `services/pedidos.py` que corresponde:

| Pedido y cobro | Operacion | Registro |
|---|---|---|
| Encargo o evento, anticipo | `cobrar` | `registrar_anticipo_capturado` |
| Encargo, saldo | `autorizar` | `registrar_saldo_autorizado`, con `politicas.vencimiento_autorizacion(resultado.autorizado_hasta, ahora)` |
| Evento, saldo | `cobrar` | `registrar_saldo_capturado` |
| Obra disponible, total | `autorizar` | `confirmar_obra`, con el mismo vencimiento |

**`verificar_cobro(session, pasarela, usuario, cobro_id, ahora, politicas)`**: lo que la app llama al volver del 3DS.

- Bloquea en el mismo orden.
- Si el cobro no esta `pendiente` o no tiene referencia, devuelve el estado actual sin llamar a la pasarela.
- Si no, `consultar_cobro`:
  - `REQUIERE_ACCION`: la URL otra vez.
  - `PENDIENTE`: resultado `pendiente`.
  - `AUTORIZADO` o `CAPTURADO`: se registra con la tabla de arriba. Si no es lo que esa operacion espera, `HechosInconsistentes`.
  - `FALLIDO` o `LIBERADO`: limpia la referencia, `intentos += 1`, resultado `rechazado`.

**Operaciones**, cada una una funcion:

| Funcion | Quien | Que hace |
|---|---|---|
| `cotizar(consulta_id, ...)` | Artista de la consulta | `crear_pedido_desde_cotizacion`, con `nombre_pasarela`. Solo encargo o evento |
| `actualizar_cotizacion(pedido_id, ...)` | Artista | La contraoferta que ya existe |
| `rechazar(pedido_id)` | Cliente o artista | Si un cobro `pendiente` espera 3DS, primero `liberar_autorizacion` de esa referencia; despues `rechazar_pedido` |
| `pagar_anticipo(pedido_id, metodo_pago_id)` | Cliente | Iniciar el cobro del anticipo |
| `iniciar_trabajo(pedido_id)` | Artista | Encargo |
| `entregar_vista_previa(pedido_id, medio_id, nota)` | Artista | Encargo |
| `pagar_saldo(pedido_id, metodo_pago_id)` | Cliente | Encargo: autoriza el saldo. Evento: lo cobra |
| `aprobar(pedido_id)` | Cliente | Encargo en `vista_previa_entregada`: `capturar` el saldo y `registrar_saldo_capturado`. `AutorizacionVencida` se traduce a `FueraDePlazo` ("la autorizacion del saldo vencio"); reautorizar es el lote 9 |
| `la_quiero(obra_id, metodo_pago_id)` | Cualquiera menos el artista de la obra | Bloquea el perfil del artista de la obra, `crear_pedido_obra_disponible` y en la misma transaccion inicia la autorizacion del total. Si la pasarela rechaza, no se guarda nada y la obra queda libre: el resultado `rechazado` se devuelve **sin** commit |
| `despachar(pedido_id, guia_envio)` | Artista | `capturar` el total y `registrar_despacho` |
| `cancelar(pedido_id)` | Cliente o artista | Ver abajo |
| `abrir_disputa(pedido_id, motivo)` | Cliente o artista | La que ya existe |

**Cancelar:**

1. Bloquea en el orden de siempre y calcula `planear_cancelacion`.
2. Ejecuta en la pasarela cada accion del plan: `LIBERAR_AUTORIZACION` y `REEMBOLSAR` con sus claves.
3. Arma `HechosPasarela` con lo ejecutado y llama a `cancelar_pedido`.
4. Si un cobro `pendiente` espera 3DS, libera tambien esa referencia. Eso no entra en los hechos, porque el plan lo trata como `CANCELAR` sin pasarela.
5. Si una llamada falla a mitad de camino, la excepcion sube y no se registra nada. Las claves fijas hacen que el reintento no libere ni reembolse dos veces.

**Resultado de un pago**: un `ResultadoPago` con el pedido detallado, el cobro, `resultado` (`completado`, `requiere_accion`, `pendiente` o `rechazado`), `url_autenticacion` y un `mensaje` para `rechazado`.

### 4. Esquemas (`src/schemas/pedidos.py`)

- Entrada:
  - `NuevaCotizacion`: `tipo` (`encargo` o `evento`), `descripcion` de 1 a 2000 caracteres, `monto_total`, `anticipo_porcentaje` opcional, `fecha_evento`, `lugar_evento` y `fecha_entrega_estimada` opcionales.
  - `Pago`: `metodo_pago_id` de 1 a 200 caracteres, sin espacios.
  - `NuevaVistaPrevia`: `medio_id` y `nota` opcional de hasta 1000 caracteres.
  - `Despacho`: `guia_envio` de 1 a 100 caracteres.
  - `NuevaDisputa`: `motivo` de 1 a 2000 caracteres.
  - Todas con `extra="forbid"`. El dinero es `Decimal`, validado como el resto de los montos.
- Salida:
  - `CobroRespuesta`: `id`, `tipo`, `estado`, `monto`, `monto_reembolsado`, `autorizado_hasta`, `capturado_en`, y `esperando_autenticacion` (pendiente con referencia). Nunca la referencia de la pasarela.
  - `VistaPreviaRespuesta`: `id`, `nota`, `created_at` e `imagen: ImagenPublica`.
  - `PedidoRespuesta`: todos los campos del pedido que ve un participante, `soy`, `cliente` y `artista` como `PerfilResumido`, `cobros` y `vistas_previas`.
  - `ResultadoPagoRespuesta`: `resultado`, `url_autenticacion`, `mensaje`, `cobro` y `pedido`.

### 5. Endpoints (`src/api/v1/pedidos.py`)

Todos piden token. La API pasa `ahora=datetime.now(UTC)`, `PoliticasPedido.desde_config(settings)`, `settings.URL_RETORNO_PAGO` y `settings.PASARELA.strip().lower()`, y hace el `commit`, salvo en el rechazo de "La quiero".

| Metodo y ruta | Respuesta |
|---|---|
| `POST /consultas/{consulta_id}/cotizacion` | `PedidoRespuesta`, 201 |
| `PUT /pedidos/{pedido_id}/cotizacion` | `PedidoRespuesta` |
| `POST /pedidos/{pedido_id}/rechazar` | `PedidoRespuesta` |
| `POST /pedidos/{pedido_id}/anticipo` | `ResultadoPagoRespuesta` |
| `POST /pedidos/{pedido_id}/iniciar` | `PedidoRespuesta` |
| `POST /pedidos/{pedido_id}/vistas-previas` | `PedidoRespuesta`, 201 |
| `POST /pedidos/{pedido_id}/saldo` | `ResultadoPagoRespuesta` |
| `POST /pedidos/{pedido_id}/aprobar` | `PedidoRespuesta` |
| `POST /obras/{obra_id}/la-quiero` | `ResultadoPagoRespuesta`; 201 si se creo el pedido |
| `POST /pedidos/{pedido_id}/despacho` | `PedidoRespuesta` |
| `POST /pedidos/{pedido_id}/cancelar` | `PedidoRespuesta` |
| `POST /pedidos/{pedido_id}/disputa` | `PedidoRespuesta`, 201 |
| `POST /cobros/{cobro_id}/verificar` | `ResultadoPagoRespuesta`. Es `POST` porque puede registrar el pago |
| `GET /pedidos` | `Pagina[PedidoRespuesta]`, query `como`, `estado` y `consulta_id` opcionales |
| `GET /pedidos/{pedido_id}` | `PedidoRespuesta` |

`resultado == "rechazado"` responde 200 con el mensaje: es un resultado normal, no un error del servidor.

### 6. Configuracion

`URL_RETORNO_PAGO: str = "artistica://pago"`, con un comentario: a donde vuelve la app despues del 3DS; si ONVO no acepta el esquema propio (pregunta 19 de `orquestacion/preguntas-onvo.md`), se cambia por una pagina https. En `backend/.env.example` y en la tabla de `backend/AGENTS.md`.

## Pruebas obligatorias

Contra la base de pruebas, con la `PasarelaFalsa` del fixture `pasarela_falsa` y un artista con el onboarding completado (`completar_onboarding`). Prefijo `test_8b_01_` en adelante.

En `test_servicio_pedidos.py`:

1. Adaptar las pruebas que usaban `registrar_vista_previa` a los dos pasos.
2. `entregar_vista_previa` con un medio ajeno, sin confirmar, de una obra o ya usado: el error que corresponde. `registrar_saldo_autorizado` sin vista previa: `ReglaDeNegocioViolada`.
3. `crear_pedido_desde_cotizacion` bloquea el perfil antes que la consulta: con un listener de `before_cursor_execute`, la primera sentencia `FOR UPDATE` es sobre `profiles`.

En `test_pedidos_api.py`, de punta a punta por la API:

4. **Encargo completo:** el artista cotiza, el cliente paga el anticipo (`completado`), el artista inicia y entrega una vista previa, el cliente paga el saldo (autorizado, `vista_previa_entregada`) y aprueba (`saldo_pagado`, con `disputable_hasta`). La pasarela falsa muestra el anticipo capturado y el saldo capturado. La tarifa de la cuenta conectada es la del pedido.
5. **Evento:** cotizacion con fecha, anticipo, saldo cobrado, `saldo_pagado` con `disputable_hasta` igual a la fecha mas la ventana.
6. **Obra disponible:** "La quiero" (201, `en_proceso`, total autorizado), despacho con guia (`saldo_pagado`, obra `vendida`). Un segundo "La quiero" sobre la misma obra da 409.
7. **Permisos:** el cliente no puede cotizar, iniciar, entregar ni despachar; el artista no puede pagar ni aprobar: 403. Un tercero recibe 404 en cada ruta con `{pedido_id}`. El artista no puede pedir su propia obra.
8. **Orden:** pagar el saldo antes de la vista previa, aprobar sin saldo autorizado, o despachar un encargo: 409, y la pasarela falsa no registro ninguna operacion nueva (`total_cobros` no cambia).
9. **Sin onboarding:** el artista cotiza; el cliente paga el anticipo y recibe 409 (`CobroNoHabilitado`), sin llamar a la pasarela.
10. **Rechazar y contraoferta:** el artista actualiza la cotizacion; el cliente rechaza; el pedido queda `rechazado`, los cobros `cancelado` y la consulta `descartada`.
11. **Cancelar:** encargo con anticipo pagado, cancelado por el cliente: el anticipo se conserva (sin reembolso). El mismo caso cancelado por el artista: reembolso total en la pasarela falsa. Obra disponible confirmada y cancelada: la autorizacion se libera.
12. **Disputa:** el cliente abre una disputa en `vista_previa_entregada`: `en_disputa`. Sin motivo: 422.
13. **Listados:** `GET /pedidos` con `como` y `estado`, y con `consulta_id`, sin repetidos al paginar. El numero de sentencias SQL es el mismo con 2 pedidos que con 6.

En `test_cobros_api.py`, el 3DS y los intentos:

14. **Anticipo con 3DS aprobado:** `metodo_pago_id = MEDIO_PAGO_3DS` da `requiere_accion` con URL y el pedido sigue `cotizado`. `verificar` antes de completar: otra vez `requiere_accion` con la misma URL. `completar_autenticacion(aprobada=True)` y `verificar`: `completado` y `anticipo_pagado`. Un segundo `verificar`: `completado`, sin nueva operacion en la pasarela.
15. **3DS rechazado y reintento:** `completar_autenticacion(aprobada=False)` y `verificar`: `rechazado`, `intentos == 1`, sin referencia. Un nuevo pago con otra tarjeta da `completado`, con una clave de idempotencia distinta.
16. **Pago rechazado:** `MEDIO_PAGO_RECHAZADO` da 200 con `rechazado` y `intentos == 1` confirmado en la base. El reintento con una tarjeta buena: `completado`.
17. **Repetir el mismo intento:** dos `POST /anticipo` seguidos con 3DS pendiente devuelven la misma referencia y URL, y la pasarela tiene un solo cobro.
18. **Saldo de encargo con 3DS** y **"La quiero" con 3DS:** `verificar` registra `vista_previa_entregada` y `en_proceso`, con `autorizado_hasta`.
19. **"La quiero" rechazado:** con `MEDIO_PAGO_RECHAZADO` no queda pedido ni consulta en la base, y otro cliente puede pedir la obra.
20. **Rechazar con 3DS pendiente:** la autorizacion pendiente queda `LIBERADO` en la pasarela falsa.
21. **Aprobar con la autorizacion vencida:** con una `PasarelaFalsa(reloj=...)` propia puesta en `app.dependency_overrides[get_pasarela]`, se avanza el reloj mas alla de `autorizado_hasta` y `aprobar` da 409. El pedido sigue en `vista_previa_entregada`.
22. **Ninguna respuesta** de la API incluye la referencia de la pasarela.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` y `alembic check` sin error ni diferencias.
- [ ] Desde `backend/`: `pytest -q` pasa, con las 389 anteriores, menos o mas las adaptadas, mas las nuevas.
- [ ] Desde `backend/`: `grep -rn "from src.api" src/services src/domain` y `grep -n "settings" src/services/contratacion.py` salen vacios.
- [ ] Desde `backend/`: `grep -rn "onvo\|ONVO" src --include=*.py | grep -v "^src/payments/"` sale vacio.
- [ ] Desde `backend/`: `grep -n "referencia_pasarela" src/schemas/pedidos.py` sale vacio.
- [ ] `SELECT count(*) FROM pg_policies;` da 0.
- [ ] Desde la raiz: `bash .github/scripts/reglas-del-repositorio.sh` pasa.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance.

## Commit y entrega

Commiteá en `feat/lote-08b-pedidos-cobros` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `feat(backend): intentos de cobro y vista previa en dos pasos`, `feat(backend): contratacion con la pasarela, 3DS e idempotencia` y `feat(backend): endpoints de pedidos y cobros`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá la salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`, la salida literal de cada criterio, y observaciones. En observaciones, decí en particular donde tuviste que elegir el orden de una llamada a la pasarela respecto de un registro.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
