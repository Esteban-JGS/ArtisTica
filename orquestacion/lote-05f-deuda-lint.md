# [Lote 5f] Deuda: politica de lint

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c chore/lote-05f-deuda-lint
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas. Todo el trabajo de este lote va en esa rama.

Verificá tambien que `develop` ya trae el lote 5e: `git log --oneline -5 develop` tiene que mostrar el merge del PR #15. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. El backend es FastAPI con SQLAlchemy async. El lint es Ruff, fijado en `>=0.16.8,<0.17`, y lo corren el CI (`ruff check .` y `ruff format --check .`) y `pre-commit`.

Cuando se armo el proyecto, la politica de lint quedo en un conjunto acotado de reglas (deuda DT8), a revisar cuando hubiera codigo suficiente para juzgarla. Ya lo hay. Este lote **amplia las reglas y corrige lo que encuentren, sin cambiar ningun comportamiento**.

El orquestador ya midio cada familia de reglas sobre el codigo actual. Las que se suman son las que detectan errores reales o fijan un estilo que conviene antes de que los lotes siguientes escriban mas endpoints. Las que se ignoran son las que, en este dominio, solo generan ruido.

## Estado actual del repositorio

Rutas relativas a `backend/`. La base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) y las variables de entorno estan en `AGENTS.md`.

`pyproject.toml` hoy:

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP", "B", "ASYNC"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", ...]
```

Lo que las reglas nuevas encuentran hoy, medido por el orquestador:

| Regla | Donde | Que es |
|---|---|---|
| `FAST002` (29) | Endpoints y `deps.py` | Dependencias con `= Depends(...)` en vez de `Annotated[..., Depends(...)]`, que es lo que recomienda FastAPI |
| `FAST001` (11) | Endpoints | `response_model` igual a la anotacion de retorno |
| `S101` (431) | Pruebas | `assert`. Se ignora en `tests/` |
| `S105` (4) | `src/storage/supabase.py` y pruebas | Falsos positivos: constantes del mapeo con la palabra "token", y secretos falsos de prueba |
| `G004` (6) | `src/workers/main.py` | Logs con f-string |
| `BLE001` (2) | `src/workers/main.py` | `except Exception`. El loop del worker tiene que sobrevivir a cualquier error: es intencional |
| `TRY400` (3), `TRY300` (1) | Varios | `logger.error` dentro de un `except` en vez de `logger.exception`, y un `return` dentro del `try` |
| `FBT001`, `FBT003` | `src/domain/pedidos.py:358` y `:410`, `src/services/perfiles.py:159` (`estudio_autoservicio`) y pruebas | Booleanos posicionales |
| `ARG001` | `src/main.py:30` (`app` del lifespan), `src/workers/main.py:22`, `src/workers/handlers/thumbnails.py:6`, pruebas | Argumentos sin usar; en pruebas, fixtures pedidas solo por su efecto |
| `PLC0415` (3) | `src/storage/__init__.py`, `src/storage/supabase.py` | Imports diferidos, intencionales |
| `T201` (1) | `src/storage/supabase.py:398` | El `print` del comando `python -m src.storage.supabase`, intencional |
| `ERA001` (3) | `src/workers/handlers/thumbnails.py` | Codigo comentado en el handler de relleno |
| `PT011`, `PT018`, `PT006`, `PT012` | Pruebas | `pytest.raises` sin `match`, asserts compuestos, nombres de `parametrize` |
| `PLW1510`, `S603` | `tests/test_esquema.py` | `subprocess.run` sin `check` |
| `SIM300` (2), `RET504` (1) | Varios | Condiciones al reves y una asignacion innecesaria |

`DTZ`, `RUF`, `C4`, `PIE`, `PERF`, `PTH` y `LOG` dan cero hoy. Se activan igual, para que nadie las rompa despues: en especial `DTZ`, que impide fechas sin zona horaria en un sistema que guarda todo en UTC.

## Objetivo

Que `ruff check .` pase con la politica nueva, con todo lo encontrado corregido o justificado en la misma linea, y sin ningun cambio de comportamiento.

## Trabajo a realizar

### 1. Politica nueva en `pyproject.toml`

```toml
[tool.ruff.lint]
select = [
    "E4", "E7", "E9", "F", "I", "UP", "B", "ASYNC",
    "DTZ", "RUF", "C4", "PIE", "PERF", "PTH", "LOG", "G",
    "SIM", "RET", "T20", "S", "BLE", "PT", "ERA", "N",
    "ARG", "FBT", "PL", "TRY", "FAST",
]
ignore = [
    "N818",     # Las excepciones del dominio se nombran en espanol, sin sufijo Error
    "PLR2004",  # Los literales de las reglas y de las pruebas se leen mejor en su lugar
    "PLR0913",  # Los servicios reciben sesion, pasarela, ids y politicas explicitos
    "PLR0917",  # Idem, en posicion
    "TRY003",   # Los mensajes en espanol de las excepciones son parte del dominio
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106", "S603", "S607"]
```

Comentá en el archivo, en una linea, el motivo de cada `ignore` y de cada `per-file-ignores`, como arriba. Conservá `extend-immutable-calls`. No agregues ningun otro `ignore` ni `per-file-ignores`: si una regla molesta en un caso legitimo, va un `noqa` en esa linea.

### 2. Correcciones

Corregí cada hallazgo. Las formas esperadas:

- **`FAST002`:** `Annotated[Tipo, Depends(funcion)]` en todos los endpoints y en `deps.py`. Si ayuda, definí alias en `deps.py`, por ejemplo `Sesion = Annotated[AsyncSession, Depends(get_db)]`, y usalos en los endpoints. Las pruebas que usan `app.dependency_overrides` tienen que seguir funcionando sin cambios: las llaves son las funciones, no los alias.
- **`FAST001`:** sacá el `response_model` redundante, conservando la anotacion de retorno y el `status_code`.
- **`G004`:** `logger.info("Job %s ...", job.id)` en vez de f-strings.
- **`TRY400`:** `logger.exception` dentro de un `except` cuando se quiere la traza; si la traza no debe salir (por ejemplo, porque llevaria datos sensibles), `noqa` con el motivo.
- **`FBT`:** los booleanos pasan a argumento de solo palabra clave (`*, estudio_autoservicio: bool`) y las llamadas los pasan por nombre. Eso incluye `src/domain/pedidos.py` y su llamada en `src/services/pedidos.py`.
- **`ARG001`:** en `src` se renombra con `_` delante si la firma la impone otro (el `lifespan`, el manejador de señales, el handler de relleno). En pruebas, una fixture pedida solo por su efecto pasa a `@pytest.mark.usefixtures(...)`.
- **`ERA001`:** se borra el codigo comentado. Un comentario que explica lo que falta queda en prosa.
- **`PT011`:** `pytest.raises(..., match="...")` con un fragmento del mensaje real.
- **`PT018`:** un `assert` por condicion.
- **`PLW1510`:** `check=True` o `check=False` explicito, segun lo que la prueba necesite.

### 3. `noqa` permitidos

Solo estos, y cada uno con el motivo en la misma linea (`# noqa: BLE001  el loop del worker no puede caerse`):

| Donde | Regla | Motivo |
|---|---|---|
| `src/workers/main.py`, los dos `except Exception` del loop | `BLE001` | El worker no puede caerse por un job |
| `src/core/security.py`, el `except Exception` final | `BLE001` | Un JWKS caido no puede dar 500 con detalles |
| Imports diferidos de `src/storage/` | `PLC0415` | Evitar cargar el modulo dos veces o un import circular, segun el caso |
| `print` de `src/storage/supabase.py` | `T201` | Es la salida del comando de consola |
| Constantes del mapeo de `src/storage/supabase.py` con "token" | `S105` | Son nombres de campo, no secretos |

Si aparece algun otro caso que creas que necesita `noqa`, ponelo con su motivo y listalo en observaciones. El orquestador decide si se acepta.

### 4. `backend/AGENTS.md`

Agregá a las reglas una linea: un `noqa` siempre lleva el codigo de la regla y el motivo en la misma linea, y no se agregan `ignore` globales sin pasar por el orquestador.

## Alcance

- `backend/pyproject.toml`
- Cualquier archivo `.py` bajo `backend/src/`, `backend/tests/` y `backend/alembic/`, **solo para corregir hallazgos del lint**
- `backend/AGENTS.md`

## Prohibido

- Cambiar comportamiento. Ningun mensaje de error, codigo HTTP, valor por defecto, nombre de ruta, consulta ni regla de negocio cambia. Renombrar un argumento posicional a solo palabra clave no es cambio de comportamiento; cambiar lo que hace la funcion si.
- Cambiar la version de Ruff o agregar librerias.
- Agregar `ignore` o `per-file-ignores` fuera de los de la seccion 1.
- Un `noqa` sin codigo de regla o sin motivo.
- Tocar `mobile/`, que es de otra persona, ni nada fuera de `backend/`.
- Correr `ruff check --fix --unsafe-fixes` sin revisar cada cambio. `ruff check --fix` con fixes seguros si se permite.

## Criterios de aceptacion

Con la salida de cada comando pegada, corridos desde `backend/`.

- [ ] `ruff check .` y `ruff format --check .` pasan con la politica nueva.
- [ ] `ruff check . --statistics` con la politica nueva no muestra nada, y `ruff check . --select ALL --statistics | head -20` se pega solo como referencia de lo que queda afuera.
- [ ] `grep -rn "noqa" src tests alembic` muestra solo los casos de la seccion 3 (o los que justifiques en observaciones), cada uno con codigo y motivo.
- [ ] `grep -rn "= Depends(" src` no devuelve nada.
- [ ] `pytest -q` pasa con **292 pruebas**, las mismas que antes.
- [ ] `alembic upgrade head` corre y `alembic check` dice `No new upgrade operations detected.`
- [ ] `git diff --stat develop...HEAD` muestra solo archivos de `backend/`.

## Commit y entrega

Commiteá en `chore/lote-05f-deuda-lint` **solo los archivos del alcance**, con mensajes convencionales. Sugerencia: un commit por familia de cambios, por ejemplo `chore(backend): politica de lint ampliada`, `refactor(backend): dependencias de FastAPI con Annotated`, `refactor(backend): correcciones del lint en src`, `test(backend): correcciones del lint en pruebas`. Cada commit tiene que dejar `pytest` pasando; `ruff check .` puede quedar limpio recien en el ultimo. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá:

1. La salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`.
2. La salida literal de cada criterio, en orden.
3. La lista de `noqa` final, con archivo, linea, regla y motivo.
4. Observaciones, en especial cualquier correccion que te haya hecho dudar de si cambiaba comportamiento.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
