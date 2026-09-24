---
trigger: glob
globs: "backend/alembic/**/*.py, backend/alembic.ini"
description: Reglas para migraciones de Alembic en ArtísTica.
---

# Migraciones

- **Una sola migracion por lote.** Si una tarea necesita dos, esta mal dividida.
- **Toda migracion es reversible.** Si no puede serlo, hay que decirlo explicitamente y explicar por que.
- **Ninguna migracion borra datos en silencio.** Si destruye algo, va escrito en la descripcion y en la entrega.
- **Toda tabla nueva se crea con RLS activo y sin politicas.** La linea de `ENABLE ROW LEVEL SECURITY` no es opcional ni se agrega despues.
- Los tipos enum los crea la migracion con SQL explicito, y los modelos los referencian con `create_type=False` usando el `ENUM` del dialecto de PostgreSQL.
- Los indices HNSW de pgvector y los GIN de tsvector se crean en la misma migracion que la tabla, no en una posterior.
- Las migraciones corren contra el puerto 5432, no contra el pooler.

## Estado actual

La base nunca se migro en ningun ambiente. Mientras eso siga siendo cierto, el esquema se corrige **reemplazando la migracion inicial**, no encadenando `ALTER`. Esa ventana se cierra en cuanto exista un ambiente con datos: a partir de ahi, toda correccion es una migracion nueva.
