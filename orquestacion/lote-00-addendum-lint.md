# [Lote 0, addendum] Politica de lint explicita y cierre del lote

Este addendum corrige el prompt original del lote 0. No lo reemplaza: lo que ya aplicaste sigue valiendo.

## Decision: no se revierte nada

El arbol se queda como esta. Se verifico lo siguiente antes de decidirlo:

- La migracion inicial cambio 533 lineas, pero es **equivalente**: siguen las 15 tablas, el bucle de `ENABLE ROW LEVEL SECURITY` y los indices HNSW y GIN. El cambio es comillas simples a dobles y saltos de linea.
- `alembic/env.py` solo gano lineas en blanco entre funciones.
- Los endpoints perdieron el `pass`, pero quedaron como funciones con docstring y comentario, que devuelven `None` igual que antes. No se implemento ningun endpoint.

El paso 10 del prompt original te pedia correr `ruff check --fix .` y al mismo tiempo no tocar archivos fuera de la lista. Con la version de ruff instalada esas dos instrucciones se contradicen. El error es del prompt, no tuyo.

## Lo que hay que hacer

### 1. Politica de lint explicita en `backend/pyproject.toml`

El problema de fondo es que el proyecto no declara que reglas usa, asi que hereda las de la version de ruff que toque instalarse. Eso se arregla declarandolas.

Agregar debajo de `[tool.ruff]`:

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP", "B", "ASYNC"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends",
    "fastapi.Query",
    "fastapi.Path",
    "fastapi.Body",
    "fastapi.Header",
    "fastapi.File",
    "fastapi.Form",
    "fastapi.Security",
]
```

Por que ese conjunto y no el minimo:

- `I` y `UP` ya se aplicaron al arbol. Sacarlos ahora obligaria a revertir.
- `B` (bugbear) y `ASYNC` valen la pena: este backend lo van a escribir agentes durante once lotes, y `ASYNC` vigila justo las invariantes de async que mas nos importan.
- `extend-immutable-calls` elimina los 21 avisos `B008`. No es silenciar un defecto: `Depends(...)` en el valor por defecto es la forma correcta de declarar dependencias en FastAPI, y ruff documenta esta opcion para eso.
- `BLE` queda fuera a proposito. Los tres `except Exception` que marcaba son deliberados: uno cierra la verificacion de token en 401 y otro evita que un job tumbe el worker.

### 2. Fijar la version de ruff

En `backend/pyproject.toml`, dependencias de desarrollo: cambiar `ruff>=0.2.1` por un rango cerrado a la version menor que tenes instalada, para que el CI no instale una distinta.

En `.pre-commit-config.yaml`, el `rev` dice `v0.2.1` mientras el entorno usa otra version. Alinealo con la misma. Hoy el repositorio corre dos linters distintos segun por donde entres.

### 3. Arreglar el build de las dos imagenes

Las dos etapas de builder hacen `COPY pyproject.toml` y despues `pip install .`, sin copiar `src/`. Ahora que hatchling empaqueta `src`, el build falla en las dos.

En `backend/Dockerfile` y `backend/Dockerfile.worker`: copiar `src/` en la etapa builder **antes** del `pip install`.

### 4. Alembic en Windows

psycopg en modo async no funciona con el event loop por defecto de Windows. En `backend/alembic/env.py`, antes de `asyncio.run(...)`, seleccionar la politica de event loop de tipo selector solo cuando la plataforma sea Windows. Es un no-op en Linux y desbloquea el trabajo local del equipo, que desarrolla en Windows.

## Alcance ampliado

A la lista del prompt original se agregan, y solo estos:

- `backend/Dockerfile.worker`
- `backend/alembic/env.py`
- `.pre-commit-config.yaml`

## Sigue prohibido

- Tocar `mobile/`.
- Crear una migracion nueva o cambiar tablas, columnas o tipos de la existente. Reformatearla ya paso y se acepta; cambiar su contenido no.
- Implementar endpoints. Los `TODO` se quedan.
- Quitar `prepare_threshold=None`.
- Cambiar la verificacion de tokens por secreto compartido.
- Desactivar RLS o agregar politicas.
- Agregar reglas de lint que obliguen a reescribir codigo mas alla de lo que ya quedo aplicado.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] `ruff check .` no reporta errores.
- [ ] `ruff format --check .` no reporta archivos por reformatear.
- [ ] `python -c "import src.models; import src.main; import src.workers.main"` no lanza excepcion.
- [ ] `pytest` pasa.
- [ ] `alembic upgrade head` y despues `alembic downgrade base` corren limpios. Si Windows lo impide pese al arreglo del punto 4, corrélos dentro del contenedor y decilo.
- [ ] `docker compose up --build` levanta los tres servicios, ninguno queda reiniciandose y el healthcheck de la API llega a saludable.
- [ ] `git status --short` no muestra ningun archivo bajo `mobile/`.
- [ ] `ls backend/alembic/versions` sigue mostrando un solo archivo.
- [ ] `git diff --stat backend/alembic/versions/` confirma que la migracion no cambio despues de este addendum.

## Como entregar

Diff completo, lista de archivos tocados, salida literal de cada comando en orden, y observaciones.

## Estilo

No usar guiones largos ni guiones medios. Explicaciones breves.
