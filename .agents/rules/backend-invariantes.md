---
trigger: glob
globs: "backend/**/*.py, backend/**/*.toml, backend/**/*.ini"
description: Invariantes tecnicas del backend de ArtísTica. Ninguna se puede romper, sin importar lo que pida la tarea.
---

# Invariantes del backend

El stack no se cambia. Ninguna tarea, por urgente que parezca, justifica romper una de estas reglas. Si una tarea parece exigirlo, es la tarea la que esta mal planteada: hacela igual hasta donde se pueda y anotá la objecion.

## Dinero

- **ArtisTica no custodia fondos de terceros.** La pasarela los custodia. No existe saldo propio, retencion propia ni desembolsos desde fondos nuestros.
- **Nunca una columna de saldo mutable.** El ledger es registro y conciliacion. Un saldo se calcula, no se guarda.
- **El estado del pedido y el estado del cobro cambian en la misma transaccion de base de datos.** Si uno falla, fallan los dos.
- **Todo webhook de pago es idempotente.** Las pasarelas reintentan: el mismo evento entregado tres veces produce un solo efecto.
- **Nada fuera de `backend/src/payments/` sabe que pasarela se usa.** El contrato abstracto expone `crear_cuenta_conectada`, `autorizar`, `capturar`, `cancelar_autorizacion`, `reembolsar` y `parsear_webhook`. Lo que no esta confirmado con la pasarela va como capacidad declarada del adaptador, no como constante en el codigo.

## Seguridad

- **RLS activo sin politicas permisivas en todas las tablas.** No se desactiva "porque la autorizacion esta en la API". La anon key viaja dentro de la app.
- **Toda la autorizacion vive en FastAPI.** El backend entra con `service_role`, y esa clave jamas llega al cliente movil.
- **El JWT se verifica contra el JWKS de Supabase** con `PyJWKClient`: firma, `exp`, `aud` e `iss`, con claves en cache. Nunca con secreto compartido.
- **Los archivos nunca pasan por la API.** Supabase Storage con signed upload URLs.

## Base de datos y async

- SQLAlchemy 2.0 async, psycopg 3 async, Alembic. Postgres 15 en Supabase.
- Endpoints `async def` con `AsyncSession`. Nunca una sesion sincronica dentro de un handler async.
- Supavisor en modo transaccion no soporta prepared statements: el engine se crea con `prepare_threshold=None`. Ese parametro no se quita.
- `statement_cache_size` es de asyncpg. No existe en psycopg 3. No lo pases en `connect_args`.
- `create_type` pertenece al `ENUM` del dialecto de PostgreSQL, no a `sqlalchemy.Enum`.
- 6543 para la app, 5432 para migraciones.

## Rendimiento y datos

- Paginacion por cursor en feed y listados. Nunca `OFFSET` grande.
- Trabajos pesados a la tabla `jobs` con `FOR UPDATE SKIP LOCKED`, worker aparte, reintentos con backoff y estado `dead`.
- `post_views`: una vista por usuario, por obra y por dia. Las propias no cuentan.
- Todo se guarda en UTC y se convierte a `America/Costa_Rica` al consultar.
- pgvector con indice HNSW para similitud de estilo y deteccion de obra duplicada; tsvector para texto.
- Miniaturas obligatorias, redimensionado en el telefono. El ancho de banda de Storage es el primer limite real de la plataforma.

## Producto

- El feed de Seguidos es cronologico y nunca lleva contenido promocionado.
- Explorar usa solo categoria, similitud de estilo y recencia. Nunca tiempo en pantalla ni senales de retencion.
- Ningun clasificador banea de forma automatica: marca para revision humana.

## Errores que ya aparecieron en este repositorio

1. `pgvector` importado sin estar en las dependencias.
2. `statement_cache_size` pasado a psycopg.
3. `create_type` pasado a `sqlalchemy.Enum`.
4. `alembic.ini` interpolando una clave que no existe en el ini.
5. `alembic.ini` sin `prepend_sys_path = .` mientras `env.py` importa `src`.
6. Config obligatoria declarada y nunca usada, que invita a validar firmas con secreto compartido.
7. Endpoint de salud en una ruta y healthcheck del contenedor en otra.
8. `@app.on_event` en vez de `lifespan`.
