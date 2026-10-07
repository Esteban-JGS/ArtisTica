# [Lote 5b] Correctivo: capas de la paginacion y orden de los bloqueos

Seguí en la misma rama, sin crear otra:

```
git switch feat/lote-05b-obras-servicios
git branch --show-current
```

Los dos problemas vienen del prompt, no de tu trabajo.

## 1. La paginacion vive en la capa equivocada

`src/services/catalogo.py` importa `ParametrosPagina` y `traer_pagina` de `src/api/paginacion.py`: el servicio depende de la API y arrastra FastAPI. El feed y los listados siguientes van a repetir el problema si no se corrige ahora.

- Mové a `src/services/paginacion.py` (nuevo) todo lo que no es HTTP: `ParametrosPagina` como dataclass, el codec del cursor, `traer_pagina` y la excepcion de cursor invalido (una subclase de `ReglaDeNegocioViolada` o una propia del modulo, sin `HTTPException`).
- En `src/api/paginacion.py` queda solo lo de HTTP: la dependencia que lee `cursor` y `tamano` de la consulta y arma `ParametrosPagina`, la traduccion de cursor invalido a 422, y el esquema `Pagina[T]`.
- Ni `src/services/` ni `src/domain/` importan nada de `src.api`.

## 2. Orden de los bloqueos: siempre el perfil antes que la obra

`editar_obra` bloquea la obra y despues, si pasa a `disponible`, el perfil. El lote 8 va a bloquear el perfil para fijar la tarifa (D8) y despues la obra al despachar. Dos transacciones que toman los mismos bloqueos en orden inverso pueden trabarse y Postgres aborta una con un error.

- Regla para todo el backend: **el perfil se bloquea antes que la obra, el servicio o el pedido**.
- En `editar_obra` y `editar_servicio`: si los cambios pueden requerir el bloqueo del perfil (pasar a `disponible`, activar), se bloquea el perfil **primero** y despues la obra o el servicio. Si no lo requieren, no se bloquea el perfil.
- Dejá la regla escrita en el docstring del modulo `src/services/catalogo.py`, en una o dos lineas.

## Alcance

- `backend/src/services/paginacion.py` (nuevo)
- `backend/src/api/paginacion.py`
- `backend/src/services/catalogo.py`
- `backend/src/api/v1/catalogo.py` (solo si cambian los imports)
- `backend/tests/test_dominio_catalogo.py` (solo imports, y una prueba nueva)

## Prueba nueva

`test_16_paginacion_sin_fastapi`: en un subproceso, importar `src.services.paginacion` y `src.services.catalogo` y verificar que ningun modulo de `sys.modules` empiece con `fastapi`. Mirá como lo hace `test_01_` de `tests/test_esquema.py`.

## Criterios

Con la salida pegada, desde `backend/`:

- [ ] `ruff check .` y `ruff format --check .` pasan.
- [ ] `pytest -q` pasa con 308 pruebas.
- [ ] `grep -rn "from src.api\|import src.api" src/services src/domain` no devuelve nada.
- [ ] `git show --stat HEAD` muestra solo archivos del alcance de este correctivo.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.

Un commit nuevo, por ejemplo `refactor(backend): paginacion en la capa de servicios y bloqueo del perfil primero`. No reescribas los commits anteriores. No commitees nada de `orquestacion/`, no hagas push ni abras PR.

Entregá la salida de cada criterio y, si hace falta, observaciones.
