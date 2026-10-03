# [Lote 4] Identidad, roles, planes y onboarding de la pasarela

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-04-identidad-planes
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. La app movil se autentica con Supabase Auth y consume esta API de FastAPI; nunca lee la base directamente. El backend entra a Postgres con `service_role`, RLS esta activo sin politicas, y **toda la autorizacion vive en FastAPI**. Por eso este lote es de seguridad aunque parezca de perfiles.

Roles y planes:

| Rol | Que puede |
|---|---|
| `publico` | Explora, sigue, comenta, consulta, contrata. No publica |
| `artista` | Lo anterior, mas galeria, servicios y pedidos. Tiene plan |
| `admin` | Moderacion. Se asigna a mano en la base, nunca por la API |

| Plan del artista | Tarifa de servicio | Limites (los aplica el lote 5, no este) |
|---|---|---|
| `taller` | 8% | 2 servicios, 5 obras disponibles |
| `estudio` | 5% | Sin limite |

Cada artista que cobra tiene una **cuenta conectada** en la pasarela de pagos y completa un **onboarding** alojado por la pasarela (identidad y cuenta IBAN). La verificacion del perfil no se vende: sale de ese onboarding.

Este es el primer lote con endpoints. Lo que dejes en `deps.py`, en los manejadores de error y en el fixture de pruebas de API lo van a reusar todos los lotes siguientes.

### Decisiones que este lote implementa

1. **El onboarding se exige solo al primer cobro.** Un artista sin cuenta conectada exhibe, recibe consultas y cotiza. Muchos artistas son informales y no se sabe todavia si la pasarela los acepta; no pueden quedar fuera de la plataforma por eso. Este lote deja la funcion que lo exige; la llama el lote 8.
2. **`is_verified` es verdadero si y solo si el onboarding esta completado.** Nadie lo cambia por otra via.
3. **Cambio de plan (D8).** El plan cambia de inmediato. Cada pedido ya creado conserva su `tarifa_porcentaje`; eso ya lo hace el servicio de pedidos y no se toca. La pasarela tiene **una sola tarifa por cuenta**: si el artista no tiene pedidos abiertos con una tarifa distinta de la del plan nuevo, la cuenta se fija en la tarifa del plan nuevo. Si los tiene, la cuenta no se toca, porque el lote 8 la ajusta antes de cada operacion que mueve dinero.
4. **El bloqueo por artista es la fila de `profiles` con `SELECT ... FOR UPDATE`.** Todo lo que cambia la tarifa de la cuenta conectada lo hace con ese bloqueo tomado, para que un cambio de plan no se cruce con un cobro. El lote 8 va a usar la misma funcion.
5. **En el MVP, Estudio es una bandera sin cobro real.** El artista cambia de plan solo, en los dos sentidos. Bajar a Taller con mas servicios u obras que el limite no oculta ni borra nada; el lote 5 solo impedira crear nuevos hasta quedar por debajo.
6. **El perfil no puede mostrar telefonos ni enlaces de WhatsApp.** Un enlace a Instagram si se permite.

## Estado actual del repositorio

Rutas relativas a `backend/`. Las variables de entorno obligatorias estan en `backend/AGENTS.md`.

| Archivo | Estado |
|---|---|
| `src/core/security.py` | Verifica el JWT con `PyJWKClient`. **Tiene dos defectos que rompen la autenticacion contra un proyecto real de Supabase:** la URL del JWKS es `/auth/v1/jwks`, y la correcta es `/auth/v1/.well-known/jwks.json`; y solo acepta `RS256`, cuando las claves asimetricas de Supabase pueden ser `ES256` (curva eliptica, la recomendada) o `RS256`. Ademas le faltan los `raise ... from` (deuda DT1) |
| `src/api/deps.py` | `get_db`, `get_current_user_payload`, `get_current_user`, `get_current_admin`. Le faltan los `raise ... from` (DT1). `verify_token` es sincronica y, cuando las claves no estan en cache, hace una peticion HTTP: llamada asi desde un `async def` bloquea el loop |
| `pyproject.toml` | Silencia `B904` con `per-file-ignores` en esos dos archivos. Es la deuda DT1 |
| `src/models/users.py` | `Profile` ya tiene todo lo que este lote necesita: `handle` unico, `nombre`, `bio`, `categorias`, `provincia`, `rol`, `plan`, `is_verified`, `pasarela_cuenta_id`, `pasarela_onboarding`. **No hace falta migracion** |
| `src/api/v1/router.py` | Router vacio |
| `src/main.py` | Sin manejadores de excepciones |
| `src/core/exceptions.py` | `ArtisTicaException`, `ResourceNotFound`, `InvalidStateTransition`, `ReglaDeNegocioViolada` y sus subclases |
| `src/domain/pedidos.py` | `ESTADOS_TERMINALES` (linea 75) y `tarifa_para_plan` (linea 197). Reusalos, no los dupliques |
| `src/payments/` | Contrato `PasarelaDePagos` con `crear_cuenta_conectada`, `consultar_cuenta`, `configurar_tarifa`. `fabrica.obtener_pasarela()` da una instancia por proceso. `PasarelaFalsa` tiene `completar_onboarding`, `rechazar_onboarding`, `tarifa_de` y `programar_falla` para pruebas |
| `src/services/pedidos.py` | Convencion que se mantiene: el servicio hace `flush` y no `commit`; abre y cierra la transaccion quien llama |
| `tests/conftest.py` | `test_db`, `async_session` (con rollback) y `async_client`. No hay forma de probar endpoints con la base sin dejar datos |

## Objetivo

Que un usuario autenticado con Supabase pueda registrarse, editar su perfil, pasar a artista, cambiar de plan y completar el onboarding de la pasarela, con la autenticacion funcionando contra un proyecto real y la deuda DT1 pagada.

## Diseno

### 1. Seguridad (`src/core/security.py`)

- `JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"`.
- `algorithms=["ES256", "RS256"]`. Nunca un algoritmo simetrico.
- Cada `raise HTTPException` dentro de un `except` lleva `from` (la excepcion original, o `None` si no aporta).
- El `except Exception` final se queda: un JWKS caido no puede devolver 500 con detalles. Que loguee el tipo de la excepcion, nunca el token.
- `verify_token` sigue siendo sincronica.

### 2. Dependencias (`src/api/deps.py`)

| Dependencia | Devuelve | Falla con |
|---|---|---|
| `get_db` | `AsyncSession`. Sin cambios | |
| `get_current_user_payload` | El payload verificado. Llama `verify_token` con `fastapi.concurrency.run_in_threadpool` | 401 |
| `get_current_user_id` | `uuid.UUID` del `sub`. Sirve para el registro, cuando todavia no hay perfil | 401 si falta o esta malformado |
| `get_current_user` | `Profile` | 404 con `detail="Perfil no registrado"` si no existe. La app usa ese 404 para mandar al registro |
| `get_current_artista` | `Profile` con `rol == artista` | 403 |
| `get_current_admin` | `Profile` con `rol == admin`. Sin cambios de comportamiento | 403 |
| `get_pasarela` | `PasarelaDePagos`, via `obtener_pasarela()` | |

Las pruebas sobrescriben `get_current_user_payload` y `get_pasarela` con `app.dependency_overrides`. Por eso ningun endpoint llama a `obtener_pasarela()` ni a `verify_token` directamente.

### 3. Dominio puro (`src/domain/perfiles.py`, nuevo)

Sin base ni pasarela. Puede importar enums de `src.models` y funciones de `src.domain.pedidos`, como ya hace el dominio de pedidos.

- `PROVINCIAS`: las siete de Costa Rica, con tilde: San José, Alajuela, Cartago, Heredia, Guanacaste, Puntarenas, Limón.
- `HANDLES_RESERVADOS = frozenset({"yo", "admin", "artistica", "soporte", "api"})`.
- `normalizar_handle(texto) -> str`: recorta espacios y pasa a minusculas. Valido si cumple `^[a-z0-9_]{3,30}$` y no esta reservado; si no, `ValueError` con mensaje claro.
- `contiene_contacto_prohibido(texto) -> bool`. Verdadero si el texto tiene:
  - un telefono de Costa Rica: ocho digitos que empiezan con 2, 4, 5, 6, 7 u 8, con o sin un separador (espacio, punto o guion) despues del cuarto, con o sin prefijo `+506` o `506`;
  - `whatsapp`, `wa.me` o `api.whatsapp`, sin distinguir mayusculas.
  Un enlace a Instagram, un año como `2026` o un monto como `25000` no cuentan.
- `tarifa_fija_de_cuenta(plan, tarifas_abiertas, politicas) -> Decimal | None`. Devuelve la tarifa del plan (con `tarifa_para_plan`) si todas las tarifas de `tarifas_abiertas` son iguales a ella, o si no hay ninguna. Si alguna difiere, devuelve `None`: la cuenta no se fija y la ajusta el lote 8 por operacion.
- `puede_cobrar(perfil) -> bool`: rol artista, `pasarela_cuenta_id` no nulo y onboarding `completado`.

### 4. Servicio (`src/services/perfiles.py`, nuevo)

Hace `flush` y nunca `commit`, igual que el servicio de pedidos. Recibe la pasarela como parametro.

| Funcion | Que hace |
|---|---|
| `bloquear_perfil(session, perfil_id) -> Profile` | `SELECT ... FOR UPDATE` sobre `profiles`. `ResourceNotFound` si no existe. Es el bloqueo por artista de la decision 4 |
| `registrar(session, perfil_id, handle, nombre) -> Profile` | Crea el perfil con rol `publico`. `PerfilYaRegistrado` si ya existe ese id. El `flush` va dentro de `session.begin_nested()`; si salta `IntegrityError` por el handle, levanta `HandleNoDisponible` y la transaccion externa sigue usable |
| `actualizar(session, perfil, cambios) -> Profile` | Aplica solo los campos presentes. Mismo tratamiento del handle duplicado |
| `hacerse_artista(session, perfil) -> Profile` | `publico` pasa a `artista` con plan `taller`. Si ya es artista, no hace nada. Si es `admin`, `ReglaDeNegocioViolada` |
| `cambiar_plan(session, pasarela, perfil_id, plan, politicas) -> ResultadoCambioPlan` | Ver abajo |
| `iniciar_onboarding(session, pasarela, perfil_id, politicas) -> CuentaConectada` | Ver abajo |
| `sincronizar_onboarding(session, pasarela, perfil_id) -> Profile` | Consulta la cuenta y aplica `aplicar_estado_cuenta`. Sin cuenta, no hace nada |
| `aplicar_estado_cuenta(perfil, estado: EstadoCuenta)` | Traduce `pendiente`, `completada`, `rechazada` a `EstadoOnboarding` y fija `is_verified`. El lote 9 la va a llamar desde el webhook `cuenta_actualizada` |
| `exigir_cobro_habilitado(perfil)` | `CobroNoHabilitado` si no `puede_cobrar`. La llama el lote 8 antes del primer cobro |

**`cambiar_plan`**, en este orden:

1. `bloquear_perfil`. Si no es artista, `ActorNoAutorizado`. Si el plan es el mismo, devuelve sin tocar nada ni llamar a la pasarela.
2. Cambia `perfil.plan`.
3. Si tiene `pasarela_cuenta_id`: lee las `tarifa_porcentaje` de sus pedidos como artista cuyo estado no esta en `ESTADOS_TERMINALES`, y calcula `tarifa_fija_de_cuenta`. Si da un valor, llama `pasarela.configurar_tarifa` **con el bloqueo todavia tomado**.
4. Si la pasarela falla con `ErrorPasarela`, el cambio de plan **se conserva igual**: loguea una advertencia con el id del perfil y el tipo de error, y marca `tarifa_sincronizada=False`. No es grave, porque el lote 8 ajusta la tarifa antes de cada operacion que mueve dinero.

`ResultadoCambioPlan` es un dataclass congelado con `plan`, `tarifa_porcentaje` (la del plan nuevo) y `tarifa_sincronizada: bool | None` (`None` si no hay cuenta o si quedo pendiente por pedidos con otra tarifa).

**`iniciar_onboarding`**, en este orden:

1. `bloquear_perfil`. Si no es artista, `ActorNoAutorizado`. El bloqueo evita que dos llamadas simultaneas creen dos cuentas.
2. Si el onboarding esta `rechazado`, `ReglaDeNegocioViolada` con un mensaje que mande a soporte.
3. Si no tiene cuenta: `pasarela.crear_cuenta_conectada(nombre=perfil.nombre, tarifa_porcentaje=tarifa_para_plan(...))`, guarda el id y aplica el estado.
4. Si ya tiene cuenta: `pasarela.consultar_cuenta` y aplica el estado.
5. Devuelve la `CuentaConectada`. Su `url_onboarding` puede venir nula al consultar; es lo esperado.

La `url_onboarding` **nunca** se loguea ni se guarda en la base: solo viaja en la respuesta al dueño.

Excepciones nuevas en `src/core/exceptions.py`, todas subclase de `ReglaDeNegocioViolada`: `PerfilYaRegistrado`, `HandleNoDisponible`, `CobroNoHabilitado`.

### 5. Esquemas (`src/schemas/__init__.py` y `src/schemas/perfiles.py`, nuevos)

Pydantic v2. Las validaciones de forma viven aca y llaman al dominio; un error de validacion da 422.

| Esquema | Campos |
|---|---|
| `RegistroPerfil` | `handle`, `nombre` (1 a 80 caracteres, recortado) |
| `ActualizacionPerfil` | Todos opcionales: `handle`, `nombre`, `bio` (hasta 500), `categorias` (hasta 5, cada una de 1 a 40, sin repetidas), `provincia` (una de `PROVINCIAS` o nula) |
| `PerfilPublico` | `handle`, `nombre`, `bio`, `categorias`, `provincia`, `es_artista`, `verificado` |
| `PerfilPropio` | Lo publico, mas `rol`, `plan` (nulo si no es artista), `tarifa_porcentaje` (la del plan, nula si no es artista), `onboarding`, `puede_cobrar` |
| `CambioPlan` | `plan` |
| `ResultadoPlan` | `plan`, `tarifa_porcentaje`, `tarifa_sincronizada` |
| `EstadoOnboardingRespuesta` | `estado`, `url_onboarding`, `puede_cobrar` |

`nombre` y `bio` se rechazan si `contiene_contacto_prohibido`. Ningun esquema expone `pasarela_cuenta_id`. El dinero y las tarifas son `Decimal`.

### 6. Endpoints (`src/api/v1/perfiles.py`, nuevo)

Bajo `/api/v1`. Cada handler abre y cierra la transaccion con `await session.commit()` despues de llamar al servicio. Las rutas `/perfiles/yo...` se declaran **antes** que `/perfiles/{handle}`.

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /perfiles` | Token valido, sin perfil (`get_current_user_id`) | 201, `PerfilPropio` |
| `GET /perfiles/yo` | Usuario | 200, `PerfilPropio` |
| `PATCH /perfiles/yo` | Usuario | 200, `PerfilPropio` |
| `POST /perfiles/yo/artista` | Usuario | 200, `PerfilPropio` |
| `PUT /perfiles/yo/plan` | Artista | 200, `ResultadoPlan` |
| `POST /perfiles/yo/onboarding` | Artista | 200, `EstadoOnboardingRespuesta` |
| `GET /perfiles/yo/onboarding` | Artista | 200, `EstadoOnboardingRespuesta`, despues de sincronizar con la pasarela |
| `GET /perfiles/{handle}` | **Sin autenticacion** | 200, `PerfilPublico`; 404 si no existe |

Las politicas salen de `PoliticasPedido.desde_config(settings)`.

### 7. Manejadores de error (`src/main.py`)

Registrados con `app.add_exception_handler`, respuesta `{"detail": "..."}`:

| Excepcion | Codigo | Detalle |
|---|---|---|
| `ResourceNotFound` | 404 | El mensaje de la excepcion |
| `ActorNoAutorizado` | 403 | El mensaje |
| `InvalidStateTransition` y el resto de `ReglaDeNegocioViolada` | 409 | El mensaje |
| `PasarelaNoDisponible` | 503 | Texto fijo: "La pasarela de pagos no esta disponible" |
| Cualquier otro `ErrorPasarela` | 502 | Texto fijo: "La pasarela de pagos rechazo la operacion" |

Los de pasarela no copian el mensaje original y loguean el tipo de error.

### 8. Fixtures de prueba (`tests/conftest.py`)

Agregá, sin romper los existentes:

- `sesion_api`: abre una conexion de `test_db`, empieza una transaccion, crea una `AsyncSession(bind=conexion, expire_on_commit=False, join_transaction_mode="create_savepoint")`, sobrescribe `get_db` para que la devuelva, y al final quita la sobrescritura, cierra la sesion y hace rollback. Asi los `commit` de los handlers no dejan datos.
- `pasarela_falsa`: una `PasarelaFalsa()` nueva, puesta en `get_pasarela`.
- `autenticar_como`: una funcion que recibe un `uuid.UUID` y sobrescribe `get_current_user_payload` para que devuelva `{"sub": str(id)}`. Las sobrescrituras se limpian al terminar cada prueba.

## Alcance

Archivos que podés crear o modificar, todos bajo `backend/`:

- `pyproject.toml` (solo quitar el bloque `per-file-ignores` de DT1)
- `src/core/security.py`
- `src/core/exceptions.py`
- `src/api/deps.py`
- `src/api/v1/router.py`
- `src/api/v1/perfiles.py` (nuevo)
- `src/main.py`
- `src/domain/perfiles.py` (nuevo)
- `src/services/perfiles.py` (nuevo)
- `src/schemas/__init__.py` (nuevo)
- `src/schemas/perfiles.py` (nuevo)
- `tests/conftest.py`
- `tests/test_seguridad.py` (nuevo)
- `tests/test_dominio_perfiles.py` (nuevo)
- `tests/test_perfiles_api.py` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior. En particular `src/models/`, `alembic/`, `src/payments/` y `src/services/pedidos.py`.
- Tocar `mobile/`, que es de otra persona.
- Crear una migracion. El esquema ya tiene todo.
- Agregar librerias. `cryptography` y `pyjwt` ya estan para firmar tokens de prueba.
- Verificar el JWT con un secreto compartido o aceptar un algoritmo simetrico.
- Exponer `pasarela_cuenta_id` o loguear la `url_onboarding` o un token.
- Un endpoint que asigne el rol `admin` o que cambie `is_verified` a mano.
- Llamar a `obtener_pasarela()` o a `verify_token` directo desde un endpoint.
- Usar `float` para tarifas o dinero.
- Implementar limites de servicios u obras, el programa de artistas fundadores o el cobro real de Estudio. Son de otros lotes o de la Etapa 2.

## Pruebas obligatorias

Nombralas con prefijo `test_01_` a `test_20_` para que se puedan contar.

**Seguridad** (`tests/test_seguridad.py`). Generá una clave EC P-256 con `cryptography`, firmá tokens con `jwt.encode(..., algorithm="ES256", headers={"kid": ...})` y reemplazá `jwks_client.get_signing_key_from_jwt` con `monkeypatch`. Ninguna prueba usa red.

1. Un token valido devuelve el payload.
2. Token vencido, `aud` distinto o `iss` distinto dan 401, y la `HTTPException` tiene `__cause__` o `__suppress_context__` (prueba de DT1).
3. Un token firmado con HS256 da 401.
4. `JWKS_URL` termina en `/auth/v1/.well-known/jwks.json`.

**Dominio** (`tests/test_dominio_perfiles.py`):

5. `normalizar_handle`: acepta `Ana_Pinta` como `ana_pinta`; rechaza `ab`, uno de 31 caracteres, `ana-pinta`, `ana pinta` y `yo`.
6. `contiene_contacto_prohibido` detecta `8888-8888`, `8888 8888`, `88888888`, `+506 8888 8888`, `WhatsApp` y `https://wa.me/50688888888`.
7. No da falso positivo con `instagram.com/ana`, `Pinto desde 2026` ni `encargos desde 25000`.
8. `tarifa_fija_de_cuenta`: sin pedidos abiertos da la del plan; con todos a la tarifa del plan da la del plan; con uno distinto da `None`.

**API** (`tests/test_perfiles_api.py`), con `sesion_api`, `pasarela_falsa` y `autenticar_como`:

9. Registro: 201 y rol `publico`. Repetirlo da 409. Otro usuario con el mismo handle da 409.
10. Sin token, `GET /perfiles/yo` da 401 o 403. Con token y sin perfil da 404 con `"Perfil no registrado"`.
11. `PATCH /perfiles/yo` con un telefono en `bio` da 422; con una provincia inexistente da 422; con datos validos da 200.
12. `GET /perfiles/{handle}` sin token da 200 y la respuesta no contiene `pasarela_cuenta_id`, `rol` ni `onboarding`.
13. `POST /perfiles/yo/artista` deja rol `artista`, plan `taller` y `tarifa_porcentaje` 8.
14. `PUT /perfiles/yo/plan` siendo `publico` da 403.
15. Cambio a `estudio` sin cuenta conectada: 200, tarifa 5 y `tarifa_sincronizada` nulo.
16. Cambio a `estudio` con cuenta conectada y sin pedidos abiertos: `tarifa_sincronizada` verdadero y `pasarela_falsa.tarifa_de(cuenta)` vale 5.
17. Cambio a `estudio` con un pedido abierto creado al 8%: el plan cambia, `tarifa_sincronizada` nulo, la cuenta sigue en 8 y el pedido sigue en 8. Creá el pedido con las fabricas o el servicio existentes, igual que `tests/test_servicio_pedidos.py`.
18. Cambio de plan con `programar_falla("configurar_tarifa", PasarelaNoDisponible(...))`: 200, el plan cambio y `tarifa_sincronizada` es falso.
19. Onboarding: el primer `POST` crea la cuenta, devuelve `url_onboarding` y estado `pendiente`. El segundo no crea otra cuenta (el id guardado no cambia). Despues de `completar_onboarding`, `GET /perfiles/yo/onboarding` da `completado`, `puede_cobrar` verdadero, y `GET /perfiles/yo` muestra `verificado` verdadero.
20. Con `programar_falla("crear_cuenta_conectada", PasarelaNoDisponible(...))`, `POST /perfiles/yo/onboarding` da 503 y el perfil queda sin cuenta. Ademas, `exigir_cobro_habilitado` levanta `CobroNoHabilitado` para un artista sin onboarding completado.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] DT1 pagada: `grep -n "per-file-ignores\|B904" pyproject.toml` no devuelve nada, y `ruff check .` sigue pasando.
- [ ] `grep -n "well-known/jwks.json\|ES256" src/core/security.py` devuelve las dos cosas, y `grep -n "HS256" src/core/security.py` no devuelve nada.
- [ ] Este lote no toca el esquema: `git diff --stat develop...HEAD -- src/models alembic` no devuelve nada, y `alembic upgrade head` corre sobre la base de pruebas.
- [ ] `pytest -v` pasa, la salida muestra las veinte pruebas obligatorias, y las pruebas de los lotes 2 y 3 siguen pasando.
- [ ] `grep -rn "pasarela_cuenta_id" src/schemas/` no devuelve nada.
- [ ] `grep -rn "obtener_pasarela\|verify_token" src/api/v1/` no devuelve nada.
- [ ] `grep -rn "url_onboarding" src/ --include=*.py | grep -i "log"` no devuelve nada.
- [ ] `grep -rnE "commit\(" src/services/perfiles.py src/domain/perfiles.py` no devuelve nada.
- [ ] `grep -rn ": float\|Mapped\[float\]" src/` no devuelve nada.
- [ ] `python -c "from src.main import app; print(sorted(r.path for r in app.routes if r.path.startswith('/api/v1/perfiles')))"` muestra las rutas de la seccion 6.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`, `src/models/`, `src/payments/` ni `alembic/`.

## Commit y entrega

Commiteá en `feat/lote-04-identidad-planes` **solo los archivos del alcance**. Podés separar en dos commits convencionales si queda mas claro, por ejemplo `fix(backend): verificacion del token contra el JWKS real de Supabase` y `feat(backend): perfiles, planes y onboarding de la pasarela`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados y modificados.
3. La salida literal de cada criterio, en orden.
4. La tabla de endpoints tal como quedo, con codigo de respuesta y dependencia de cada uno.
5. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
