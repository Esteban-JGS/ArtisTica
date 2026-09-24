# [Lote 0] Saneamiento: dejar el backend en estado ejecutable

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto mínimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas con el pago protegido. El repositorio es un monorepo: `backend/` tiene una API FastAPI y un worker en Python 3.12; `mobile/` tiene la app en React Native y Expo, y no es tuya.

El backend se generó de una sola vez y nunca se ejecutó: tiene un único commit y acumula defectos que impiden instalarlo, migrarlo y probarlo. Los lotes siguientes van a reescribir el modelo de datos completo, pero no se puede validar ningún trabajo mientras el proyecto no arranque, porque todo criterio de aceptación quedaría en una afirmación sin evidencia.

Tu lote no agrega funcionalidad. Deja el proyecto instalable, migrable y con las pruebas y el linter en verde.

**Entorno.** Ya existe un entorno virtual en `backend/.venv` con Python 3.12.0. Activalo antes de cualquier comando (en PowerShell: `backend\.venv\Scriptsctivate`) y trabaja siempre dentro de el. No instales nada en el interprete global: la evidencia de los criterios de aceptacion solo vale si sale de ese entorno. En esta maquina `python` fuera del entorno cae a un stub de Microsoft Store; si necesitas el interprete sin activar, usa `py -3`.

## Estado actual del repositorio

Estos son los defectos ya localizados. Verificalos antes de tocar nada; si alguno no existe tal como se describe, anotalo en observaciones y seguí con los demás.

1. `backend/src/models/content.py:6` y `backend/alembic/versions/1a2b3c4d5e6f_initial_migration.py:13` importan `pgvector`, que no aparece en las dependencias de `backend/pyproject.toml:8-21`. Cualquier import del modelo falla.

2. `backend/pyproject.toml:32-34` declara hatchling como backend de build, pero no hay configuración de qué empaquetar y no existe ningún paquete llamado `artistica_backend`. El código vive en `backend/src/`. Por eso `pip install -e .` no sabe qué instalar.

3. `backend/src/core/database.py:9-12` pasa `statement_cache_size` dentro de `connect_args`. Ese parámetro es de asyncpg, no de psycopg 3, que es el driver del proyecto. `prepare_threshold` sí es correcto y se queda: Supavisor en modo transacción no soporta prepared statements.

4. `backend/src/models/users.py:22-25` y `backend/src/models/commissions.py:40-43` usan `sqlalchemy.Enum(..., create_type=False)`. El parámetro `create_type` pertenece a `sqlalchemy.dialects.postgresql.ENUM`, no a `sqlalchemy.Enum`.

5. `backend/alembic.ini:3` dice `sqlalchemy.url = %(ALEMBIC_DATABASE_URL)s`. Esa clave no existe en el ini, y `backend/alembic/env.py:43` llama a `config.get_section`, que interpola. La URL real ya la aporta `env.py:23-24` desde la configuración, así que la línea del ini sobra.

6. `backend/alembic.ini` no tiene `prepend_sys_path = .`, y `backend/alembic/env.py:9-10` importa `src.core.config` y `src.models`.

7. `ruff` no pasa. Hay al menos tres imports sin uso: `uuid` en `backend/src/models/base.py:1`, `List` en `backend/src/api/v1/commissions.py:3`, y `AsyncSessionLocal` en `backend/tests/conftest.py:7`. Además hay 67 líneas con espacios finales en `src`, `tests` y `alembic`, que hacen fallar `ruff format --check`.

8. El endpoint de salud está en `/health` (`backend/src/main.py:29`), pero `backend/tests/test_health.py:6` y `backend/Dockerfile:43` apuntan a `/api/v1/health`. La prueba falla y el contenedor se marca como no saludable.

9. `.github/workflows/main.yml:3-7` solo dispara en `main`. El trabajo ocurre en `develop`, así que el CI nunca corrió sobre este código.

10. `docker-compose.yml:48-52`: el servicio `worker` no define `ALEMBIC_DATABASE_URL`, que `backend/src/core/config.py:13` declara obligatoria. El worker revienta al importar la configuración.

11. `.github/workflows/main.yml:76-83`: el paso que corre migraciones en producción solo define `ALEMBIC_DATABASE_URL`, pero la configuración también exige `DATABASE_URL` y `SUPABASE_URL`. El paso falla antes de migrar.

12. `backend/src/core/config.py:16` declara `SUPABASE_JWT_SECRET` como obligatoria, pero no se usa en ningún lado: `backend/src/core/security.py` verifica los tokens contra el JWKS de Supabase, que es lo correcto. Dejar ese secreto ahí invita a que alguien más adelante valide firmas con secreto compartido.

13. `backend/src/core/config.py:23` declara `DAYS_UNTIL_AUTO_RELEASE`. Pertenece a un modelo de retención de fondos propio que el proyecto ya descartó.

14. `backend/tests/test_commissions.py` define la función `safe_transition` dentro del propio archivo de prueba y después la prueba. No cubre ni una línea de código de producción.

## Objetivo

Que `pip install -e .[dev]`, `ruff check .`, `ruff format --check .`, `alembic upgrade head` y `pytest` corran los cinco sin errores en un entorno limpio.

## Alcance

Archivos que podés crear o modificar:

- `backend/pyproject.toml`
- `backend/alembic.ini`
- `backend/src/core/database.py`
- `backend/src/core/config.py`
- `backend/src/models/base.py`
- `backend/src/models/users.py`
- `backend/src/models/commissions.py`
- `backend/src/api/v1/commissions.py`
- `backend/src/main.py`
- `backend/Dockerfile`
- `backend/.env.example`
- `backend/tests/conftest.py`
- `backend/tests/test_health.py`
- `backend/AGENTS.md` (crear)
- `docker-compose.yml`
- `.github/workflows/main.yml`

Archivos que podés borrar:

- `backend/tests/test_commissions.py`

Además podés aplicar `ruff check --fix .` y `ruff format .` sobre `backend/`, que va a tocar espacios finales en otros archivos de `src`, `tests` y `alembic`. Eso está permitido, siempre que el único cambio en esos archivos sea de formato.

## Prohibido

- Tocar cualquier archivo fuera de las listas anteriores, salvo cambios de puro formato producidos por ruff.
- Tocar `mobile/` por cualquier motivo. Es de otra persona.
- Cambiar el stack o agregar librerías que no estén justificadas por un import que ya existe en el código.
- Cambiar el modelo de datos, agregar o quitar tablas, o crear una migración nueva. El esquema completo se reescribe en el lote siguiente.
- Implementar cualquier endpoint que hoy sea un esqueleto. Los `pass` y los `TODO` se quedan como están.
- Quitar `prepare_threshold=None` de la creación del engine. Supavisor en modo transacción no soporta prepared statements.
- Cambiar la verificación de tokens. `backend/src/core/security.py` valida contra el JWKS de Supabase y eso es correcto: firma, `exp`, `aud` e `iss`, con claves en caché. No lo sustituyas por validación con secreto compartido.
- Desactivar RLS ni agregar políticas de RLS. La migración actual activa RLS sin políticas y así se queda.
- Reformatear con una herramienta que no sea ruff.

## Trabajo a realizar

1. En `backend/pyproject.toml`: agregar `pgvector` a las dependencias. Declarar el extra de asyncio de SQLAlchemy, porque el proyecto usa `create_async_engine`. Agregar la configuración de build de hatchling para que el paquete instalable sea el directorio `src`.

2. En `backend/src/core/database.py`: quitar `statement_cache_size` de `connect_args` y dejar solo `prepare_threshold`. No cambiar nada más del engine.

3. En `backend/src/models/users.py` y `backend/src/models/commissions.py`: usar el `ENUM` del dialecto de PostgreSQL en vez de `sqlalchemy.Enum`, conservando el mismo nombre de tipo (`profile_role_enum` y `commission_state_enum`) y `create_type=False`, porque los tipos los crea la migración.

4. En `backend/alembic.ini`: borrar la línea de `sqlalchemy.url` y agregar `prepend_sys_path = .`.

5. Decidir un solo camino para el endpoint de salud: se queda en `/health`, fuera del prefijo versionado, porque lo consumen la plataforma de despliegue y el healthcheck del contenedor. Ajustar `backend/tests/test_health.py` y `backend/Dockerfile` para que apunten ahí.

6. En `backend/src/core/config.py`: eliminar `SUPABASE_JWT_SECRET` y `DAYS_UNTIL_AUTO_RELEASE`. Agregar `SUPABASE_SERVICE_KEY` como opcional, que es la clave con la que el backend entrará a la base saltando RLS. Reflejar los tres cambios en `backend/.env.example`, dejando escrito que esa clave jamás puede llegar al cliente móvil.

7. En `docker-compose.yml`: agregar `ALEMBIC_DATABASE_URL` al servicio `worker` y quitar `SUPABASE_JWT_SECRET` de los dos servicios. Quitar la clave `version`, que está obsoleta.

8. En `.github/workflows/main.yml`: agregar `develop` a las ramas que disparan el flujo, tanto en `push` como en `pull_request`. El trabajo de despliegue sigue condicionado a `main`. Agregar al paso de migración en producción las variables de entorno que la configuración exige y hoy faltan.

9. Borrar `backend/tests/test_commissions.py`.

10. Quitar los imports sin uso y correr `ruff check --fix .` y `ruff format .` desde `backend/`.

11. Crear `backend/AGENTS.md` con, y solo con, lo siguiente: los comandos de instalación, linter, formato, migración y pruebas; la regla de que el código vive en `backend/src`; la regla de que `mobile/` no se toca; y la regla de estilo de que no se usan guiones largos ni guiones medios en comentarios ni documentación. Nada de arquitectura ni de modelo de datos: eso se escribe cuando el esquema esté definido, en un lote posterior.

## Criterios de aceptación

Cada casilla se demuestra con la salida real del comando, pegada en la entrega.

- [ ] `cd backend && pip install -e ".[dev]"` termina con éxito en un entorno virgen.
- [ ] `cd backend && python -c "import src.models; import src.main; import src.workers.main"` no lanza ninguna excepción.
- [ ] `cd backend && ruff check .` no reporta errores.
- [ ] `cd backend && ruff format --check .` no reporta archivos por reformatear.
- [ ] `cd backend && alembic upgrade head` corre limpio contra una base PostgreSQL vacía con la extensión vector disponible.
- [ ] `cd backend && alembic downgrade base` corre limpio a continuación.
- [ ] `cd backend && pytest` pasa, con al menos la prueba de salud en verde.
- [ ] `docker compose up --build` levanta los tres servicios y ninguno queda en reinicio. El healthcheck del contenedor de la API llega a estado saludable.
- [ ] `git diff --stat` no muestra ni un archivo dentro de `mobile/`.
- [ ] No existe ninguna migración nueva: `ls backend/alembic/versions` sigue mostrando un solo archivo.
- [ ] `grep -rn "SUPABASE_JWT_SECRET\|DAYS_UNTIL_AUTO_RELEASE" backend .github docker-compose.yml` no devuelve nada.

## Cómo entregar

1. El diff completo.
2. La lista de archivos creados, modificados y borrados.
3. La salida literal de cada comando de los criterios de aceptación, en el mismo orden.
4. Una sección de observaciones al final.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objeción en observaciones. Si un defecto de la lista no existe tal como se describe, decilo ahí con la evidencia.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentación. Explicaciones breves. Se prefiere código correcto a párrafos.
