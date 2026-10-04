# Backend de ArtísTica

## Comandos

Todos se corren desde `backend/`, con el entorno virtual activo (`.venv\Scripts\Activate.ps1` en PowerShell).

| Tarea | Comando |
|---|---|
| Instalacion | `pip install -e ".[dev]"` |
| Linter | `ruff check .` |
| Formato | `ruff format .` (verificar con `ruff format --check .`) |
| Migracion | `alembic upgrade head` |
| Pruebas | `pytest` |
| Preparar el bucket de medios | `python -m src.storage.supabase` |

`python -m src.storage.supabase` crea el bucket `BUCKET_MEDIOS` en Supabase
Storage, o lo actualiza si existe: publico para lectura, con el limite de
tamano y los tipos de imagen permitidos. Es idempotente y necesita
`SUPABASE_SERVICE_KEY`. Se corre a mano, una vez por proyecto de Supabase.

## Base de pruebas local

Las pruebas corren contra una base migrada. En local se usa el contenedor
`artistica-db-pruebas` (pgvector) en el puerto 5433, usuario y clave
`postgres`, base `artistica`. Si no esta corriendo: `docker start artistica-db-pruebas`.

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/artistica
ALEMBIC_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/artistica
```

Despues `alembic upgrade head` y `pytest`.

## Variables de entorno

La configuracion se valida al importar cualquier modulo, asi que sin estas tres no
corre ni `pytest`. Ponelas en un `backend/.env` (ignorado por git) o exportalas:

| Variable | Para que |
|---|---|
| `DATABASE_URL` | Conexion de la API. Puerto 6543, el pooler |
| `ALEMBIC_DATABASE_URL` | Conexion de las migraciones. Puerto 5432, directa |
| `SUPABASE_URL` | Base para el JWKS que verifica los tokens |

Opcional: `SUPABASE_SERVICE_KEY`, `SENTRY_DSN`, `ENVIRONMENT`.

Almacenamiento de medios, todas opcionales:

| Variable | Defecto | Para que |
|---|---|---|
| `ALMACENAMIENTO` | `falso` | `falso` (en memoria) o `supabase`. `supabase` exige `SUPABASE_SERVICE_KEY`; `falso` no arranca con `ENVIRONMENT=production` |
| `ALMACENAMIENTO_TIMEOUT_SEGUNDOS` | `15` | Espera por solicitud a Storage |
| `BUCKET_MEDIOS` | `medios` | Bucket publico de la galeria |
| `MEDIO_TAMANO_MAXIMO_BYTES` | `5242880` | Tamano maximo de una imagen (5 MB) |
| `MEDIOS_PENDIENTES_MAXIMOS` | `20` | Subidas sin confirmar por artista |

Ver `backend/.env.example`. La `SUPABASE_SERVICE_KEY` jamas llega al cliente movil.

## Reglas

1. El codigo vive en `backend/src`. Se importa como `src.<modulo>`.
2. `mobile/` no se toca por ningun motivo. Es de otra persona.
3. No se usan guiones largos ni guiones medios en comentarios ni documentacion.
