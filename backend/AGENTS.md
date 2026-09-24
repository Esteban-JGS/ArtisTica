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

## Variables de entorno

La configuracion se valida al importar cualquier modulo, asi que sin estas tres no
corre ni `pytest`. Ponelas en un `backend/.env` (ignorado por git) o exportalas:

| Variable | Para que |
|---|---|
| `DATABASE_URL` | Conexion de la API. Puerto 6543, el pooler |
| `ALEMBIC_DATABASE_URL` | Conexion de las migraciones. Puerto 5432, directa |
| `SUPABASE_URL` | Base para el JWKS que verifica los tokens |

Opcional: `SUPABASE_SERVICE_KEY`, `SENTRY_DSN`, `ENVIRONMENT`.
Ver `backend/.env.example`. La `SUPABASE_SERVICE_KEY` jamas llega al cliente movil.

## Reglas

1. El codigo vive en `backend/src`. Se importa como `src.<modulo>`.
2. `mobile/` no se toca por ningun motivo. Es de otra persona.
3. No se usan guiones largos ni guiones medios en comentarios ni documentacion.
