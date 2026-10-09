# [Lote 8c] Entregables en un bucket privado

## Paso 0: crear la rama

Antes de tocar cualquier archivo, desde la raiz del repositorio:

```
git switch develop
git pull --ff-only
git switch -c feat/lote-08c-entregables-privados
```

Verificá con `git branch --show-current`. Si la rama ya existe, detenete y avisá: no la sobrescribas.

Verificá tambien que `develop` ya trae el lote 8b: `backend/src/services/contratacion.py` tiene que existir. Si no, detenete y avisá.

## Rol

Sos ingeniero de backend trabajando en el repositorio de ArtísTica.

## Contexto minimo

ArtísTica es una plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. En un **encargo**, el artista entrega vistas previas con marca de agua. El cliente autoriza el saldo al verlas, y cuando aprueba se cobra (lote 8b). Lo que falta es el **archivo final**: la obra sin marca de agua, que el cliente recibe despues de pagar.

La vista previa vive en el bucket publico `medios`, como las imagenes de la galeria. El archivo final no puede: cualquiera con la URL lo descargaria sin pagar. Va a un bucket **privado** (D12), y se descarga con una URL firmada que dura poco y que solo pide un participante del pedido.

Hoy el contrato de almacenamiento no sabe firmar descargas. Este lote lo agrega, prepara el bucket privado y suma los endpoints del archivo final. Paga ademas la mitad de la deuda DT24.

## Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `backend/src/storage/contrato.py` | `Almacenamiento` con `firmar_subida`, `info`, `descargar`, `subir`, `borrar` y `url_publica`. `SubidaFirmada` marca sus campos sensibles con `field(repr=False)` |
| `backend/src/storage/supabase.py` | Bloque de mapeo con fuentes (`[api]`, `[js]`, `[docs]`). `self._url_base` ya incluye `/storage/v1`: `url_publica` le suma `/object/public/{bucket}/{ruta}`. `preparar_bucket(bucket, *, tamano_maximo, tipos)` crea o actualiza un bucket **siempre publico**. `_preparar_bucket_medios()`, al final del archivo, es lo que corre `python -m src.storage.supabase` |
| `backend/src/storage/falso.py` | `AlmacenamientoFalso` con reloj inyectable, `simular_subida` y `existe` |
| `backend/src/services/medios.py` | `solicitar_subida(..., bucket=...)` ya recibe el bucket. `confirmar_subida` usa el bucket del medio. `tomar_medios_sueltos` y `_sirve` eligen medios sueltos para una obra o una publicacion, y **no miran los entregables** (DT24) |
| `backend/src/api/v1/medios.py` | `POST /medios` (subida al bucket publico), `POST /medios/{medio_id}/confirmar`, `GET` y `DELETE` |
| `backend/src/schemas/medios.py` | `SolicitudSubida` (tipo y tamano validados) y `SubidaRespuesta.desde(medio, subida)` |
| `backend/src/services/pedidos.py` | `entregar_vista_previa` valida el medio (del artista, confirmado, sin obra ni publicacion, no usado). `PedidoDetalle` lleva `vistas_previas`. Las lecturas no hacen N+1 |
| `backend/src/services/contratacion.py` | Envuelve cada operacion con el control de quien puede hacerla: `_visible`, `_exigir_rol`, y un tercero recibe 404 |
| `backend/src/models/pedidos.py` | `Entregable` con `tipo` (`TipoEntregable`: `vista_previa`, `final`), `media_asset_id` y `nota` |
| `backend/src/core/config.py` | `BUCKET_MEDIOS`, `MEDIO_TAMANO_MAXIMO_BYTES` |

Documentacion de Supabase Storage para firmar una descarga, consultada el 2026-10-08 en `https://github.com/supabase/storage`, `src/http/routes/object/getSignedURL.ts`:

- Ruta `POST /object/sign/{bucket}/{ruta}`, bajo el mismo prefijo que las demas.
- Cuerpo `{"expiresIn": <segundos>}`.
- Respuesta `{"signedURL": "/object/sign/{bucket}/{ruta}?token=..."}`, **relativa** a `/storage/v1`.

## Objetivo

Que el artista suba el archivo final de un encargo pagado a un bucket privado, y que solo el cliente y el artista lo descarguen con una URL firmada de corta duracion.

## Alcance

- `backend/src/storage/contrato.py`
- `backend/src/storage/falso.py`
- `backend/src/storage/supabase.py`
- `backend/src/core/config.py` (solo `BUCKET_ENTREGABLES`, `DESCARGA_FIRMADA_SEGUNDOS` y su regla en el validador)
- `backend/src/services/medios.py` (solo DT24)
- `backend/src/services/pedidos.py`
- `backend/src/services/contratacion.py`
- `backend/src/schemas/pedidos.py`
- `backend/src/api/v1/pedidos.py`
- `backend/.env.example` y `backend/AGENTS.md` (las variables nuevas y el bucket privado en el comando de preparacion)
- `backend/tests/test_almacenamiento_supabase.py` (solo agregar pruebas)
- `backend/tests/test_entregables_api.py` (nuevo)

## Prohibido

- Tocar cualquier archivo fuera de la lista anterior, y en particular `mobile/`, `src/payments/`, los modelos y las migraciones. Este lote no cambia el esquema.
- Agregar librerias.
- Que algo fuera de `src/storage/` conozca a Supabase.
- Devolver una URL publica de un objeto del bucket privado, o una URL firmada de descarga a quien no participa del pedido.
- Poner un token o una URL firmada en un `repr`, un log o un mensaje de error.
- Leer `settings` desde `src/services/`: los buckets y la duracion llegan como parametros.
- Un `noqa` sin codigo y motivo.
- Commits con lineas `Co-Authored-By` o que mencionen herramientas de asistencia.

## Trabajo a realizar

### 1. Contrato de almacenamiento

- `DescargaFirmada` (`frozen`, `kw_only`): `url: str = field(repr=False)` y `expira_en: datetime`.
- `Almacenamiento.firmar_descarga(bucket: str, ruta: str, *, segundos: int) -> DescargaFirmada`. `segundos` tiene que ser positivo; si no, `ValueError`.

### 2. Adaptador de Supabase

- Bloque de mapeo: `RUTA_FIRMAR_DESCARGA = "/object/sign/{bucket}/{ruta}"`, `CAMPO_EXPIRA = "expiresIn"` y `CAMPO_URL_FIRMADA_DESCARGA = "signedURL"`, con la fuente de arriba.
- `firmar_descarga` hace el POST y devuelve `self._url_base + signedURL`, con `expira_en = reloj() + segundos`. Si la respuesta no trae `signedURL` o no empieza con `/`, se levanta el error de respuesta inesperada que ya usa el adaptador.
- `preparar_bucket` recibe `publico: bool` por nombre. Por defecto `True`, para no cambiar ninguna llamada existente.
- `python -m src.storage.supabase` prepara los dos buckets: `BUCKET_MEDIOS` publico, como hoy, y `BUCKET_ENTREGABLES` privado, con los mismos tipos y el mismo tamano maximo. Imprime una linea por bucket.

### 3. Almacenamiento falso

`firmar_descarga` devuelve `https://almacenamiento-falso.invalid/firmada/{bucket}/{ruta}?expira=<timestamp>` y la expiracion con su reloj. Si el objeto no existe, `ErrorAlmacenamiento` no reintentable, igual que `descargar`.

### 4. Configuracion

- `BUCKET_ENTREGABLES: str = "entregables"`.
- `DESCARGA_FIRMADA_SEGUNDOS: int = Field(default=600, ge=60, le=3600)`.
- El validador de configuracion rechaza que `BUCKET_ENTREGABLES` sea igual a `BUCKET_MEDIOS`.

### 5. Servicios

`services/pedidos.py`:

- `entregar_final(session, *, pedido_id, media_asset_id, nota, bucket_privado)`:
  - El pedido tiene que ser un encargo en `saldo_pagado` o `completado`. Si no, `InvalidStateTransition`.
  - El medio tiene que cumplir las mismas reglas que la vista previa, y ademas estar en `bucket_privado`. Si no, `ReglaDeNegocioViolada`.
  - Crea un `Entregable` de tipo `final`. Puede haber varios.
- `entregar_vista_previa` recibe `bucket_publico` y exige que el medio este en ese bucket. Una vista previa en el bucket privado no se veria.
- `PedidoDetalle.finales: list[EntregableFinal]` con el entregable y su medio, cargados en la misma consulta que las vistas previas, sin N+1.

`services/contratacion.py`:

- `solicitar_subida_final(session, almacenamiento, usuario, pedido_id, content_type, tamano_bytes, *, bucket_privado, maximo_pendientes)`. Solo el artista del pedido, y solo en un encargo `saldo_pagado` o `completado`. Usa `medios.solicitar_subida` con `bucket=bucket_privado`.
- `entregar_final(...)`: solo el artista.
- `descargar_entregable(session, almacenamiento, usuario, pedido_id, entregable_id, *, segundos) -> DescargaFirmada`. Cliente o artista del pedido; un tercero recibe 404. Solo entregables `final`: una vista previa da 409, porque es publica y ya viene en el detalle.

`services/medios.py` (DT24): `tomar_medios_sueltos` no acepta un medio que ya sea un entregable. Se busca en `entregables` dentro de la misma operacion, con los medios ya bloqueados, y se responde con el mismo `ReglaDeNegocioViolada` de hoy.

### 6. Endpoints

| Metodo y ruta | Quien | Respuesta |
|---|---|---|
| `POST /pedidos/{pedido_id}/entregables/subida` | Artista | `SubidaRespuesta`, 201. El cuerpo es una `SolicitudSubida`. La confirmacion es la de siempre, `POST /medios/{medio_id}/confirmar` |
| `POST /pedidos/{pedido_id}/entregables/final` | Artista | `PedidoRespuesta`, 201. Cuerpo `{medio_id, nota}`, con la nota de hasta 1000 caracteres |
| `GET /pedidos/{pedido_id}/entregables/{entregable_id}/descarga` | Cliente o artista | `{url, expira_en}` |

`PedidoRespuesta` suma `finales: list[FinalRespuesta]` con `id`, `nota`, `created_at` y `content_type`. **Sin URL**: se pide con el endpoint de descarga.

La API pasa `settings.BUCKET_ENTREGABLES`, `settings.BUCKET_MEDIOS`, `settings.DESCARGA_FIRMADA_SEGUNDOS` y `settings.MEDIOS_PENDIENTES_MAXIMOS`.

## Pruebas obligatorias

Prefijo `test_8c_01_` en adelante.

En `test_almacenamiento_supabase.py`, con el transporte simulado que ya usa ese archivo:

1. `firmar_descarga` hace `POST /storage/v1/object/sign/{bucket}/{ruta}` con `{"expiresIn": N}` y devuelve la URL absoluta. Una respuesta sin `signedURL`, o con una URL que no empieza con `/`, levanta el error de respuesta inesperada.
2. `preparar_bucket(..., publico=False)` manda `public: false`. Sin el parametro, manda `true`.
3. El `repr` de `DescargaFirmada` no contiene la URL.

En `test_entregables_api.py`, con el almacenamiento falso y la pasarela falsa:

4. **Camino feliz:** encargo hasta `saldo_pagado` por la API. El artista pide la subida, el medio queda en `entregables`, se confirma y se entrega como final. El cliente y el artista descargan con una URL firmada que expira a los `DESCARGA_FIRMADA_SEGUNDOS`. El detalle trae `finales` sin URL.
5. **Antes de pagar:** pedir la subida o entregar el final en `en_proceso` o `vista_previa_entregada` da 409.
6. **Permisos:** un tercero recibe 404 en la subida, la entrega y la descarga. El cliente no puede pedir la subida ni entregar.
7. **Buckets cruzados:** un medio del bucket publico como final, o uno del privado como vista previa, da 409.
8. **Descargar una vista previa** por el endpoint de descarga da 409.
9. **DT24:** un medio entregado como vista previa no se puede usar en una obra (`POST /obras`) ni en una publicacion: 409.
10. **Configuracion:** con `BUCKET_ENTREGABLES` igual a `BUCKET_MEDIOS`, no carga. Con `DESCARGA_FIRMADA_SEGUNDOS` de 30, tampoco.

## Criterios de aceptacion

Con la salida de cada comando pegada.

- [ ] Desde `backend/`: `ruff check .` y `ruff format --check .` pasan.
- [ ] Desde `backend/`: `alembic check` sin diferencias.
- [ ] Desde `backend/`: `pytest -q` pasa, con las 419 anteriores mas las nuevas.
- [ ] Desde `backend/`: `grep -rn "from src.api" src/services src/domain` y `grep -n "settings" src/services/contratacion.py src/services/pedidos.py src/services/medios.py` salen vacios.
- [ ] Desde `backend/`: `grep -rni "supabase" src --include=*.py | grep -v "^src/storage/\|^src/core/"` no muestra nada nuevo respecto de `develop` (hoy: un comentario en `models/users.py` y un `TODO` del worker).
- [ ] Desde la raiz: `bash .github/scripts/reglas-del-repositorio.sh` pasa.
- [ ] `git log develop..HEAD --format=%B | grep -ci "co-authored"` da 0.
- [ ] `git diff --stat develop...HEAD` muestra solo archivos del alcance.

## Commit y entrega

Commiteá en `feat/lote-08c-entregables-privados` **solo los archivos del alcance**, con mensajes convencionales y sin lineas de coautor. Sugerencia: `feat(backend): descarga firmada y bucket privado en el almacenamiento` y `feat(backend): archivo final del encargo en el bucket privado`. No commitees nada de `orquestacion/`. No hagas push ni abras PR.

Entregá la salida de `git diff --stat develop...HEAD` y `git log --oneline develop..HEAD`, la salida literal de cada criterio, y observaciones.

Si algo de este prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Estilo

No usar guiones largos ni guiones medios en comentarios ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en espanol, segun el glosario; comentarios en espanol.
