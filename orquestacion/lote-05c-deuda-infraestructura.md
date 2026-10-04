# [Lote 5c] Deuda: infraestructura y configuracion

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c chore/lote-05c-deuda-infraestructura
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. El backend es FastAPI con un worker aparte que procesa una cola de trabajos en Postgres. Para pruebas y para la demo existen adaptadores **falsos** de la pasarela de pagos y del almacenamiento, que guardan su estado en memoria de cada proceso.

Este lote no agrega funcionalidad: paga seis deudas tecnicas registradas en la bitacora (DT2, DT4, DT5, DT14, DT15 y DT16). Son de arranque, de configuracion y de reglas que solo tienen sentido en produccion.

### Las deudas

| # | Problema | Resultado esperado |
|---|---|---|
| DT2 | En `docker-compose.yml` el worker solo espera a la base. Su primera consulta llega antes de que la API corra las migraciones y loguea `relation jobs does not exist` | El worker arranca recien cuando la API esta sana, y la API esta sana despues de migrar |
| DT4 | Compose publica la base en el 5432 fijo, que en la maquina de Esteban ya esta ocupado | El puerto del host se elige con una variable, con 5432 por defecto |
| DT5 | `src/models/operation.py` es una reexportacion de tres lineas que existe solo porque `src/workers/main.py` importa `Job` desde ahi | El worker importa desde `src.models`, y `operation.py` desaparece |
| DT14 | Nada impide usar la pasarela falsa en produccion | La configuracion no carga en produccion con `PASARELA=falsa` |
| DT15 | Los adaptadores falsos guardan estado por proceso; con mas de un worker de uvicorn, cada proceso ve otro estado y la demo se rompe | La configuracion no carga con un adaptador falso y `WORKERS` mayor que 1 |
| DT16 | Cualquier artista se pasa a Estudio sin pagar y su tarifa baja de 8% a 5%. Sirve para la demo, no para produccion | Un interruptor de configuracion habilita el autoservicio de Estudio; en produccion tiene que estar apagado |

### Decision que este lote implementa

La demo corre con `ENVIRONMENT=demo`, nunca con `production`. En produccion la configuracion rechaza los adaptadores falsos y el cambio a Estudio sin cobro. Bajar de Estudio a Taller se permite siempre.

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `docker-compose.yml` (raiz) | Servicios `db` (pgvector, puerto `"5432:5432"`, con healthcheck), `api` (corre `alembic upgrade head` y despues uvicorn) y `worker`. El worker tiene `depends_on: db: condition: service_healthy`. La API **no** tiene healthcheck en compose |
| `backend/Dockerfile` | Instala `curl` y define un `HEALTHCHECK` con curl a `/health`. Arranca uvicorn con `--workers ${WORKERS:-1}` |
| `backend/src/workers/main.py:10` | `from src.models.operation import Job` |
| `backend/src/models/operation.py` | Reexporta `Job` desde `operacion.py` |
| `backend/src/core/config.py` | `Settings` con `ENVIRONMENT: str = "dev"`, `PASARELA: str = "falsa"`, `ALMACENAMIENTO: str = "falso"`. No conoce `WORKERS`. No valida combinaciones |
| `backend/src/storage/__init__.py` | La fabrica ya rechaza `falso` con `ENVIRONMENT` igual a `production` o `prod`. Se queda como esta |
| `backend/src/payments/fabrica.py` | No tiene ninguna regla de produccion. No se toca: la regla vive en la configuracion |
| `backend/src/services/perfiles.py` | `cambiar_plan(session, pasarela, perfil_id, plan, politicas)` cambia el plan sin ninguna condicion de autoservicio |
| `backend/src/api/v1/perfiles.py` | `PUT /perfiles/yo/plan` llama a `servicio.cambiar_plan` |
| `.github/workflows/main.yml` | El job de despliegue corre `alembic upgrade head` sin definir `ENVIRONMENT`, asi que usa `dev`. No se toca |

Base de pruebas local: el contenedor `artistica-db-pruebas` en el puerto 5433 (ver `backend/AGENTS.md`).

## Objetivo

Que las seis deudas queden pagadas, con la configuracion rechazando al cargar toda combinacion insegura para produccion o rota para la demo.

## Trabajo a realizar

### 1. Compose (`docker-compose.yml`)

- `db`: el puerto del host sale de `${DB_PUERTO_LOCAL:-5432}`. El puerto interno sigue siendo 5432, y las URLs internas (`db:5432`) no cambian.
- `api`: healthcheck propio en compose que no dependa de curl, por ejemplo `["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]`, con un `start_period` que cubra el tiempo de las migraciones.
- `worker`: `depends_on` de `api` con `condition: service_healthy`, ademas del de `db`.
- Comentarios breves que digan por que.

### 2. Worker (`backend/src/workers/main.py` y `backend/src/models/operation.py`)

Cambiá el import a `from src.models import Job` y borrá `operation.py`. Nada mas en el worker: su logica la reescribe un lote posterior.

### 3. Configuracion (`backend/src/core/config.py`)

Agregá:

```python
WORKERS: int = Field(default=1, ge=1)
ESTUDIO_AUTOSERVICIO: bool = True
```

y un `@model_validator(mode="after")` que levante un error claro, nombrando las variables, en estos casos:

| Condicion | Por que |
|---|---|
| `ENVIRONMENT` es `production` o `prod` (sin distinguir mayusculas) y `PASARELA` es `falsa` | DT14 |
| `ENVIRONMENT` de produccion y `ALMACENAMIENTO` es `falso` | La misma regla que ya tiene la fabrica de almacenamiento, ahora al cargar |
| `ENVIRONMENT` de produccion y `ESTUDIO_AUTOSERVICIO` verdadero | DT16 |
| `WORKERS` mayor que 1 y `PASARELA` es `falsa` o `ALMACENAMIENTO` es `falso` | DT15 |

Compará `PASARELA` y `ALMACENAMIENTO` sin espacios y en minusculas, igual que las fabricas. Los entornos de produccion van en una constante con nombre.

### 4. Cambio de plan (`backend/src/services/perfiles.py` y `backend/src/api/v1/perfiles.py`)

`cambiar_plan` recibe un parametro nuevo `estudio_autoservicio: bool`. Si es falso y el plan pedido es `estudio`, levanta `ActorNoAutorizado("El plan Estudio se activa con la suscripcion")` **antes** de tocar nada. Bajar a `taller` sigue permitido siempre. El endpoint pasa `settings.ESTUDIO_AUTOSERVICIO`.

### 5. Documentacion (`backend/AGENTS.md` y `backend/.env.example`)

- `WORKERS`, `ESTUDIO_AUTOSERVICIO` y `DB_PUERTO_LOCAL`, con una linea cada una.
- Una seccion corta "Reglas de produccion" con la tabla del punto 3, y la regla de que la demo corre con `ENVIRONMENT=demo`.

## Alcance

Archivos que podés crear, modificar o borrar:

- `docker-compose.yml`
- `backend/src/workers/main.py` (solo el import)
- `backend/src/models/operation.py` (borrar)
- `backend/src/core/config.py`
- `backend/src/services/perfiles.py` (solo `cambiar_plan`)
- `backend/src/api/v1/perfiles.py` (solo el endpoint de plan)
- `backend/tests/test_configuracion.py` (nuevo)
- `backend/tests/test_perfiles_api.py` (solo agregar pruebas)
- `backend/AGENTS.md`
- `backend/.env.example`

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior. En particular `src/payments/`, `src/storage/`, el `Dockerfile` y el workflow de CI.
- Tocar `mobile/`, que es de otra persona.
- Agregar librerias.
- Cambiar la logica del worker mas alla del import.
- Bloquear la bajada de Estudio a Taller.

## Pruebas obligatorias

Nombralas con prefijo `test_01_` a `test_08_`.

**Configuracion** (`tests/test_configuracion.py`). Construí `Settings(...)` con argumentos explicitos; nunca cambies el `settings` global. Pasá las tres variables obligatorias como argumentos para no depender del entorno.

1. Con los valores por defecto y `ENVIRONMENT=dev`, carga.
2. `ENVIRONMENT=production` con `PASARELA="falsa"` falla y el mensaje nombra `PASARELA`. Lo mismo con `" Falsa "`.
3. `ENVIRONMENT=prod` con `ALMACENAMIENTO="falso"` falla y nombra `ALMACENAMIENTO`.
4. `ENVIRONMENT=production` con `PASARELA=onvo`, `ALMACENAMIENTO=supabase` y `ESTUDIO_AUTOSERVICIO=True` falla y nombra `ESTUDIO_AUTOSERVICIO`; con `ESTUDIO_AUTOSERVICIO=False`, carga.
5. `WORKERS=2` con algun adaptador falso falla y nombra `WORKERS`; `WORKERS=2` con `PASARELA=onvo` y `ALMACENAMIENTO=supabase` carga. `WORKERS=0` falla.
6. `ENVIRONMENT=demo` con los adaptadores falsos, `WORKERS=1` y autoservicio carga.

**Plan** (`tests/test_perfiles_api.py`):

7. Con `ESTUDIO_AUTOSERVICIO` en falso (`monkeypatch` sobre `settings`), `PUT /perfiles/yo/plan` a `estudio` da 403 y el plan sigue en `taller`. Si el artista tiene cuenta conectada, `pasarela_falsa.tarifa_de(cuenta)` sigue en 8.
8. Con `ESTUDIO_AUTOSERVICIO` en falso, un artista que ya esta en `estudio` puede bajar a `taller` y recibe 200.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `pytest -v` pasa, muestra las ocho pruebas obligatorias, y las 255 anteriores siguen pasando.
- [ ] `test ! -e backend/src/models/operation.py` y `grep -rn "models.operation\|models import operation" backend/src backend/tests` no devuelve nada.
- [ ] Desde la raiz: `docker compose config --quiet` no da error.
- [ ] Desde la raiz: `DB_PUERTO_LOCAL=5434 docker compose config` muestra el puerto publicado 5434, y sin la variable muestra 5432.
- [ ] Desde la raiz: `docker compose config` muestra que `worker` depende de `api` con `condition: service_healthy`, y que `api` tiene healthcheck.
- [ ] Desde `backend/`: `ENVIRONMENT=production python -c "import src.core.config"` falla con un mensaje que nombra `PASARELA`.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`, `src/payments/` ni `src/storage/`.

Opcional, si tenés el 5432 libre o usás `DB_PUERTO_LOCAL`: `docker compose up -d` y pegá los logs del worker mostrando que arranca sin `relation jobs does not exist`. Si no lo corrés, decilo en observaciones.

## Commit y entrega

Commiteá en `chore/lote-05c-deuda-infraestructura` **solo los archivos del alcance**, con mensajes convencionales (`fix(backend): ...`, `chore(backend): ...`). No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La lista de archivos creados, modificados y borrados.
3. La salida literal de cada criterio, en orden.
4. Una tabla con cada deuda (DT2, DT4, DT5, DT14, DT15, DT16) y la evidencia de que quedo pagada.
5. Observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
