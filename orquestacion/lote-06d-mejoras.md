# [Lote 6d] Mejoras chicas: indices, Sentry y controles en el CI

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c chore/lote-06d-mejoras
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

Verificá tambien que `develop` ya trae el lote 6c: `git log --oneline -5 develop` tiene que mostrar el merge del PR #20, y `backend/alembic/versions/` tiene que tener `a0b1c2d3e4f5_comentarios.py`. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas. Este lote no agrega funcionalidad. Junta cuatro mejoras chicas antes de empezar la parte de contratacion y cobro:

| # | Que | Por que |
|---|---|---|
| 1 | Deuda DT22: un indice que sobra y uno que falta | `ix_comentarios_publicacion_id` lo cubre el compuesto `(publicacion_id, created_at)`. La busqueda de artistas pagina por `profiles.created_at` sin indice |
| 2 | Configuracion de Sentry (pendiente P10) | Hoy manda el 100% de las trazas y, por defecto, adjunta las variables locales de cada error, que pueden incluir tokens de sesion |
| 3 | El CI verifica las migraciones | Hoy solo corre `alembic upgrade head`. La reversibilidad y la deriva entre modelos y base se revisan a mano en cada validacion |
| 4 | El CI hace cumplir dos reglas del repositorio | Commits sin lineas `Co-Authored-By` ni menciones a herramientas de asistencia, y archivos sin guiones largos ni medios. Las dos ya fallaron una vez y solo se detectaron a mano |

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `backend/src/models/social.py` | `Comentario.publicacion_id` con `index=True`, y ademas el indice compuesto `(publicacion_id, created_at)` del lote 6c |
| `backend/src/models/users.py` | `Profile` sin indice en `created_at` |
| `backend/alembic/versions/` | Cabeza `a0b1c2d3e4f5`. `alembic/env.py` compara tambien los `server_default` |
| `backend/src/main.py` | `sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, traces_sample_rate=1.0)`, solo si hay `SENTRY_DSN` |
| `backend/src/core/config.py` | `SENTRY_DSN: str \| None = None`, y el validador `_rechazar_combinaciones_inseguras` |
| `.github/workflows/main.yml` | Job `lint-and-test`: ruff, `ruff format --check`, y `alembic upgrade head && pytest` contra un Postgres de servicio. El checkout no trae historial (`fetch-depth` por defecto). Job `deploy` solo en push a `main` |
| `.claude/skills/documentacion-proyecto/SKILL.md` | Contiene los dos guiones a proposito, en su comando de verificacion. Es la unica excepcion |
| `mobile/` | Es de otra persona y tiene sus propias reglas. El control de guiones **no** lo revisa |

La base de pruebas local (contenedor `artistica-db-pruebas`, puerto 5433) y las variables estan en `backend/AGENTS.md`.

## Trabajo a realizar

### 1. DT22

- `Comentario.publicacion_id` deja de tener `index=True`; el compuesto queda.
- `Profile` suma el indice `ix_profiles_created_at_id` sobre `(created_at DESC, id DESC)`.
- Una migracion con `down_revision = "a0b1c2d3e4f5"`, reversible, con `alembic check` limpio.

### 2. Sentry

- `src/core/sentry.py` (nuevo) con `configurar_sentry(config) -> bool`: si no hay `SENTRY_DSN`, no hace nada y devuelve `False`. Si hay, llama a `sentry_sdk.init` con `dsn`, `environment`, `traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE`, `send_default_pii=False` e `include_local_variables=False`, y devuelve `True`.
- `src/core/config.py`: `SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1, ge=0, le=1)`.
- `src/main.py` llama a `configurar_sentry(settings)` en lugar del `init` actual.

### 3. Migraciones en el CI

En el paso de pruebas, despues de `alembic upgrade head`: `alembic downgrade -1`, `alembic upgrade head` y `alembic check`, y recien despues `pytest`. Si cualquiera falla, falla el job.

### 4. Reglas del repositorio en el CI

Un paso nuevo en `lint-and-test`, antes de instalar dependencias, con `fetch-depth: 0` en el checkout:

- **Commits:** solo en `pull_request`. Revisa los mensajes de `base.sha..head.sha` y falla si alguno contiene `co-authored-by` o `claude`, sin distinguir mayusculas, mostrando cual.
- **Guiones:** falla si algun archivo versionado de `backend/`, `docs/`, `orquestacion/`, `.agents/`, `.github/`, `AGENTS.md` o `CLAUDE.md` contiene un guion largo o uno medio, mostrando archivo y linea. Excluye los `.docx` y el `package-lock.json`. `.claude/` queda afuera por la excepcion de arriba.

Escribí el chequeo en un script versionado `.github/scripts/reglas-del-repositorio.sh` (bash, con `set -euo pipefail`) que el workflow llama, para poder correrlo tambien a mano. Probalo localmente sobre el arbol actual (tiene que pasar) y sobre un archivo de prueba con un guion largo (tiene que fallar); borra el archivo de prueba despues.

## Alcance

- `backend/src/models/social.py` y `backend/src/models/users.py` (solo los indices)
- `backend/alembic/versions/<nueva>_indices.py` (nuevo)
- `backend/src/core/sentry.py` (nuevo)
- `backend/src/main.py` (solo Sentry)
- `backend/src/core/config.py` (solo `SENTRY_TRACES_SAMPLE_RATE`)
- `backend/.env.example` (la variable nueva)
- `backend/tests/test_configuracion.py` (solo agregar pruebas)
- `.github/workflows/main.yml` y `.github/scripts/reglas-del-repositorio.sh` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular `mobile/` y el job `deploy`.
- Agregar librerias.
- Cambiar comportamiento de la API.
- Escribir en el script o en el workflow un guion largo o medio literal: el patron se arma con escapes (por ejemplo `$'\u2014'` o `\xE2\x80\x94`), para que el propio archivo pase el control.
- `= Depends(...)`, `float` para dinero o un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Pruebas obligatorias

En `tests/test_configuracion.py`, con prefijo `test_6d_01_` a `test_6d_03_`:

1. Sin `SENTRY_DSN`, `configurar_sentry` devuelve `False` y no llama a `sentry_sdk.init` (`monkeypatch` sobre `sentry_sdk.init`).
2. Con `SENTRY_DSN`, la llama una vez con `send_default_pii=False`, `include_local_variables=False` y el `traces_sample_rate` de la configuracion.
3. `SENTRY_TRACES_SAMPLE_RATE` de `-0.1` o `1.5` no carga.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` y `alembic check` sin error ni diferencias.
- [ ] Desde `backend/`: `pytest -q` pasa, con las 343 anteriores mas las tres nuevas.
- [ ] Desde la raiz: `bash .github/scripts/reglas-del-repositorio.sh` pasa sobre el arbol actual, y falla con un archivo de prueba que tenga un guion largo (pegá las dos salidas).
- [ ] `grep -n "fetch-depth\|alembic check\|reglas-del-repositorio" .github/workflows/main.yml` muestra los tres cambios.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance, y ninguno bajo `mobile/`.

## Commit y entrega

Commiteá en `chore/lote-06d-mejoras` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `fix(backend): indices de comentarios y de busqueda de artistas`, `fix(backend): Sentry sin datos sensibles y con muestreo configurable` y `chore(ci): migraciones reversibles y reglas del repositorio en el CI`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá la salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`, la salida literal de cada criterio, y observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
