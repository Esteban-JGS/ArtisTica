# [Lote 8d] Resolución de disputas por moderación y deuda DT23, DT24 y DT26

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-08d-disputas
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

Verificá tambien que `develop` ya trae el lote 8c: `grep -n "firmar_descarga" backend/src/storage/contrato.py` tiene que mostrar el metodo. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica. Este lote mueve dinero: leé el prompt completo antes de empezar.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. Cuando cliente y artista no se ponen de acuerdo, cualquiera de los dos abre una **disputa** (lote 8b) y el pedido queda `en_disputa`, congelado. La resuelve el equipo de moderacion, con la evidencia del chat de la consulta, la cotizacion y las vistas previas. Puede completar el pedido, capturando lo autorizado, o cancelarlo, liberando lo autorizado. En cualquiera de los dos casos puede ordenar reembolsos de lo ya capturado, anticipo incluido (D5).

Las reglas puras ya existen (`dominio.planear_resolucion`) y el registro tambien (`pedidos.resolver_disputa`, que exige un perfil admin y verifica los hechos contra el plan). Falta la capa que ejecuta el plan en la pasarela, y los endpoints de moderacion.

El lote paga ademas tres deudas:

| Deuda | Que |
|---|---|
| DT23 | SQLAlchemy 2.1 marca obsoletos `Result.tuples()` y `select().distinct(columna)` para `DISTINCT ON`. Hoy son 216 avisos en `pytest`, y `pyproject.toml` no pone tope a la version |
| DT24, la mitad pendiente | Se acepta como esta: las pruebas que importan ayudas de otro archivo de pruebas funcionan, y moverlas a `conftest.py` tocaria cuatro archivos sin cambiar nada. Este lote no lo hace |
| DT26 | `MedioRespuesta` arma `url_publica` tambien para un medio del bucket privado, y `bucket_publico` es opcional en `pedidos.entregar_vista_previa`. La tercera parte de DT26 (un medio privado todavia no entregado se puede asignar a una obra) **se acepta**: no da acceso a nada, solo deja una imagen rota en la galeria del propio artista |

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `backend/src/services/contratacion.py` | La unica capa que llama a la pasarela por un pedido. Ayudas que este lote reutiliza: `_Contexto`, `_bloquear` (perfil del artista y despues pedido), `_tarifa` (D8), `_clave_captura`, `_clave_liberacion`, `_clave_reembolso`, `_soltar_intentos_en_espera`. `cancelar` es el modelo a seguir: valida todas las transiciones, ejecuta el plan en la pasarela y recien despues registra |
| `backend/src/services/pedidos.py` | `resolver_disputa(session, *, pedido_id, destino, resolucion, admin_id, hechos, ahora)` (alrededor de la linea 767). `PedidoDetalle` con `soy: Rol` (cliente o artista), `cobros`, `vistas_previas` y `finales`. `entregar_vista_previa(..., bucket_publico: str \| None = None)` |
| `backend/src/domain/pedidos.py` | `planear_resolucion(tipo, estado, destino, cobros, reembolsos_ordenados)`, `HechosPasarela(liberados, capturados, reembolsos)`, `verificar_hechos`. No se toca |
| `backend/src/models/pedidos.py` | `Disputa`: `pedido_id` unico, `abierta_por_id`, `motivo`, `estado` (`abierta`, `resuelta`), `resolucion`, `resuelta_por_id`, `resuelta_en` |
| `backend/src/services/consultas.py` | Chat de la consulta, solo para participantes. Linea 142: `.distinct(Mensaje.consulta_id)`; linea 159: `.tuples()` |
| `backend/src/services/comentarios.py` | `.tuples()` en las lineas 115, 138 y 162 |
| `backend/src/services/publicaciones.py` | `.tuples()` en la linea 71 |
| `backend/tests/test_consultas_api.py` | `.tuples()` en la linea 578 |
| `backend/src/api/deps.py` | `Admin`: perfil con rol `admin`, si no 403 |
| `backend/src/schemas/medios.py` | `MedioRespuesta.desde(medio, almacenamiento)` arma `url` y `miniatura_url` con `url_publica` para cualquier bucket. `schemas/catalogo.py` ya lee `settings` en un esquema, asi que aca tambien se puede |
| `backend/tests/test_servicio_pedidos.py` (lineas 139, 190 y 593) y `backend/tests/test_pedidos_api.py` (linea 701) | Llaman a `entregar_vista_previa` sin `bucket_publico` |
| `backend/pyproject.toml` | `"sqlalchemy[asyncio]>=2.0.25"` |

## Objetivo

Que moderacion vea las disputas abiertas con su evidencia y las resuelva, y que la pasarela ejecute la resolucion antes de registrarla. Y que `pytest` corra sin avisos de obsolescencia de SQLAlchemy.

## Alcance

- `backend/src/services/contratacion.py`
- `backend/src/services/pedidos.py`
- `backend/src/services/consultas.py` (la lectura para moderacion y DT23)
- `backend/src/services/comentarios.py` y `backend/src/services/publicaciones.py` (solo DT23)
- `backend/src/schemas/pedidos.py`
- `backend/src/schemas/medios.py` (solo DT26)
- `backend/src/api/v1/moderacion.py` (nuevo)
- `backend/src/api/v1/router.py`
- `backend/pyproject.toml` (solo la version de SQLAlchemy)
- `backend/tests/test_servicio_pedidos.py` y `backend/tests/test_pedidos_api.py` (solo pasar `bucket_publico`)
- `backend/tests/test_consultas_api.py` (solo la linea de DT23)
- `backend/tests/test_entregables_api.py` (solo agregar la prueba de DT26)
- `backend/tests/test_moderacion_api.py` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular `mobile/`, `src/domain/`, `src/payments/`, los modelos y las migraciones. Este lote no cambia el esquema.
- Agregar librerias, o cambiar otra version que no sea la de SQLAlchemy.
- Llamar a la pasarela antes de validar el plan completo, o registrar antes de ejecutarlo.
- Bloquear en otro orden que perfil del artista, pedido, consulta, obra (D18, D21).
- Que un cliente o un artista lleguen a un endpoint de moderacion, o que moderacion vea la referencia de la pasarela o una URL de autenticacion.
- `float` para dinero, o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Trabajo a realizar

### 1. Resolver una disputa (`services/contratacion.py`)

`resolver_disputa(session, pasarela, admin, pedido_id, *, destino, resolucion, reembolsos, ahora, politicas) -> PedidoDetalle`:

1. `destino` es `EstadoPedido.COMPLETADO` o `EstadoPedido.CANCELADO`. Si no, `ReglaDeNegocioViolada`.
2. Bloquea el perfil del artista del pedido y despues el pedido, con `_bloquear`. Un pedido que no existe da `ResourceNotFound`.
3. Exige que el pedido tenga una disputa `abierta`. Si no, `InvalidStateTransition`, sin llamar a la pasarela.
4. Calcula `dominio.planear_resolucion(...)` con los `reembolsos` (cobro y monto) y valida cada transicion de cobro del plan, como `cancelar`.
5. `_soltar_intentos_en_espera` sobre los cobros, igual que en `cancelar`.
6. Ejecuta el plan en la pasarela:
   - `CAPTURAR`: `_tarifa` y despues `capturar` con `_clave_captura`. `AutorizacionVencida` se traduce a `FueraDePlazo` ("la autorizacion vencio: no se puede completar capturando; resolver como cancelado o con reembolso").
   - `LIBERAR_AUTORIZACION`: con `_clave_liberacion`.
   - `REEMBOLSAR`: con `_clave_reembolso`.
7. Arma `HechosPasarela` con lo ejecutado y llama a `pedidos.resolver_disputa` con `admin_id=admin.id`.
8. Si una llamada falla a mitad de camino, la excepcion sube y no se registra nada. Las claves fijas hacen que el reintento no capture, libere ni reembolse dos veces.

Devuelve el detalle del pedido para moderacion (punto 2).

### 2. Lecturas para moderacion (`services/pedidos.py` y `services/consultas.py`)

- `PedidoDetalle.soy` pasa a `Rol | None`. Es `None` cuando mira moderacion. Las lecturas existentes de las partes no cambian.
- `PedidoDetalle.disputa: Disputa | None`, cargada en la misma pasada que el resto, sin N+1. La ven las partes y moderacion.
- `detalle_para_moderacion(session, pedido_id) -> PedidoDetalle`, sin control de participante, con `soy=None`.
- `disputas_abiertas(session, parametros) -> tuple[list[PedidoDetalle], str | None]`: los pedidos `en_disputa` con disputa `abierta`, de la disputa **mas vieja** a la mas nueva. Paginado por cursor sobre la fecha de la disputa, sin `OFFSET` y sin N+1.
- `entregar_vista_previa`: `bucket_publico: str` pasa a obligatorio (DT26).
- `services/consultas.py`: `mensajes_para_moderacion(session, pedido_id, parametros)`, el chat de la consulta del pedido del mas viejo al mas nuevo, con el remitente. Sin control de participante, porque lo llama solo la API de moderacion.

### 3. Esquemas

`schemas/pedidos.py`:

- `ResolucionDisputa` (`extra="forbid"`):
  - `destino`: `completado` o `cancelado`.
  - `resolucion`: de 1 a 2000 caracteres.
  - `reembolsos`: lista de `{cobro_id, monto}`, vacia por defecto, sin cobros repetidos. El monto es `Decimal` positivo con dos decimales como maximo.
- `DisputaRespuesta`: `estado`, `motivo`, `abierta_por` (`PerfilResumido`), `created_at`, `resolucion` y `resuelta_en`. `PedidoRespuesta` la suma como `disputa: DisputaRespuesta | None`, y `soy` pasa a opcional.
- `MensajeModeracion`: `remitente` (`PerfilResumido`), `texto`, `aviso_contacto` y `created_at`.

`schemas/medios.py` (DT26): `MedioRespuesta` da `url` y `miniatura_url` solo si `medio.bucket == settings.BUCKET_MEDIOS`. Para cualquier otro bucket, las dos van nulas.

### 4. Endpoints (`api/v1/moderacion.py`)

Todos con la dependencia `Admin`.

| Metodo y ruta | Respuesta |
|---|---|
| `GET /moderacion/disputas` | `Pagina[PedidoRespuesta]`, las abiertas, de la mas vieja a la mas nueva |
| `GET /moderacion/pedidos/{pedido_id}` | `PedidoRespuesta` con `soy` nulo |
| `GET /moderacion/pedidos/{pedido_id}/mensajes` | `Pagina[MensajeModeracion]`, el chat de la consulta del pedido |
| `POST /moderacion/pedidos/{pedido_id}/disputa/resolver` | `PedidoRespuesta` |

Registrá el router en `src/api/v1/router.py`.

### 5. DT23

- Reemplazá cada `.tuples()` por la forma que indica el aviso: el `Row` ya se desempaqueta solo.
- Reemplazá `.distinct(Mensaje.consulta_id)` por `postgresql.distinct_on`, como extension de la consulta.
- `pyproject.toml`: `"sqlalchemy[asyncio]>=2.1,<2.2"`.

## Pruebas obligatorias

Prefijo `test_8d_01_` en adelante. Las de moderacion van en `test_moderacion_api.py`, con la `PasarelaFalsa` del fixture `pasarela_falsa` y un perfil con rol `admin` creado en la base.

1. **Completar con captura:** un encargo en disputa desde `vista_previa_entregada` (saldo autorizado). Moderacion resuelve `completado` sin reembolsos: el saldo queda capturado en la pasarela falsa, el pedido `completado` y la disputa `resuelta`, con `resuelta_por` y `resolucion`.
2. **Cancelar con liberacion y reembolso del anticipo:** el mismo caso, resuelto `cancelado` con un reembolso total del anticipo. La autorizacion del saldo queda liberada, el anticipo reembolsado en la pasarela falsa, y en la base `monto_reembolsado` del anticipo es igual a su monto.
3. **Reembolso parcial al completar:** un evento en disputa desde `saldo_pagado`, resuelto `completado` con un reembolso parcial del saldo. Solo se reembolsa ese monto.
4. **Validaciones antes de la pasarela:** un pedido sin disputa abierta, un reembolso sobre un cobro de otro pedido, un monto mayor que lo reembolsable, o `destino` igual a `rechazado`, dan 409 o 422. La pasarela falsa no registro ninguna operacion nueva.
5. **Autorizacion vencida:** con una `PasarelaFalsa(reloj=...)` propia, se avanza el reloj y `completado` da 409. El pedido sigue `en_disputa`.
6. **Idempotencia:** se programa una falla de la pasarela falsa en la segunda operacion del plan, el primer intento da error y no registra nada. El reintento termina, y la pasarela falsa tiene una sola captura y un solo reembolso.
7. **Permisos:** el cliente, el artista y un tercero reciben 403 en los cuatro endpoints.
8. **Lecturas:** `GET /moderacion/disputas` lista solo las abiertas, de la mas vieja a la mas nueva, sin repetidos al paginar, con el mismo numero de sentencias SQL con 2 que con 6. El detalle trae `disputa` y `soy` nulo. Los mensajes traen el chat de la consulta con su remitente. Ninguna respuesta contiene la referencia de la pasarela.
9. **La parte ve la disputa:** el cliente ve `disputa` en `GET /pedidos/{id}` antes y despues de la resolucion.
10. **DT26:** en `test_entregables_api.py`, la confirmacion de un medio del bucket privado devuelve `url` y `miniatura_url` nulas; uno del publico, con URL.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `pip install -e ".[dev]"` instala una SQLAlchemy 2.1, y `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `alembic check` sin diferencias.
- [ ] Desde `backend/`: `pytest -q -W error::sqlalchemy.exc.SADeprecationWarning` pasa, con las 431 anteriores mas las nuevas.
- [ ] Desde `backend/`: `grep -rn "\.tuples()\|\.distinct(Mensaje" src tests` sale vacio.
- [ ] Desde `backend/`: `grep -rn "from src.api" src/services src/domain` y `grep -n "settings" src/services/contratacion.py src/services/pedidos.py src/services/consultas.py src/services/comentarios.py` salen vacios.
- [ ] Desde la raiz: `bash .github/scripts/reglas-del-repositorio.sh` pasa.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance.

## Commit y entrega

Commiteá en `feat/lote-08d-disputas` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `fix(backend): consultas sin formas obsoletas de SQLAlchemy 2.1`, `feat(backend): resolucion de disputas por moderacion` y `fix(backend): sin url publica para medios privados`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá la salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`, la salida literal de cada criterio, y observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
