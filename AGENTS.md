# ArtísTica

Plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. No es una red social: la parte social alimenta el momento de contratación.

La fuente de verdad del producto es `docs/ArtisTica_Documento_Maestro.md`. Las decisiones de rumbo posteriores viven en `orquestacion/BITACORA.md` y las erratas del Maestro en `orquestacion/CORRECCIONES-DOCUMENTO-MAESTRO.md`. Si algo se contradice, gana el Maestro más su errata.

## Estructura

```
monorepo/
├── mobile/        React Native + Expo. Territorio de Brian
├── backend/       FastAPI y worker en Python 3.12. Territorio de Esteban
├── docs/          Documentacion oficial del curso, Documento Maestro y Canvas
└── orquestacion/  Plan de lotes, bitacora y prompts de ejecucion
```

**Quien trabaja en `backend/` no toca `mobile/`, y al reves.** No es una preferencia: son dos personas distintas y los cambios cruzados rompen el trabajo del otro.

La app consume la API de FastAPI. Nunca lee tablas de Supabase directamente con la anon key, porque RLS esta activo sin politicas permisivas y la anon key viaja dentro del binario.

## Modelo operativo, en una tabla

Comisiones abiertas, no marketplace. Un solo motor de pedidos con tres tipos:

| Tipo | Cobros |
|---|---|
| `encargo` | Anticipo al aceptar la cotizacion; saldo autorizado en la vista previa y capturado al aprobar |
| `evento` | Anticipo al reservar la fecha; saldo antes del evento |
| `obra_disponible` | Autorizado al confirmar, capturado al despachar |

## Principios que no se negocian

1. Solo arte hecho por personas. El clasificador marca para revision humana; nunca banea solo.
2. El feed de Seguidos es cronologico y jamas lleva contenido promocionado.
3. Se vende la habilidad del artista, no inventario. No hay catalogo, stock ni reventa.
4. Las metricas miden respuesta real (consultas, conversion), no viralidad.
5. Nunca se cobra por publicar, abrir comisiones, recibir pedidos, la proteccion del pago ni la verificacion.

## Como se trabaja

El backend avanza por lotes definidos en `orquestacion/BITACORA.md`. Cada lote tiene un prompt autocontenido con alcance cerrado. Si estas ejecutando un lote, no salgas de su lista de archivos, y si algo del prompt te parece equivocado, hacelo igual y anotá la objecion en observaciones.

## Ramas, commits y pull requests

**Nadie commitea directo en `develop` ni en `main`.** Todo entra por pull request.

| Rama | Para que |
|---|---|
| `main` | Lo entregable. Solo recibe merges desde `develop` en hitos |
| `develop` | Integracion. Base de todas las ramas de trabajo |
| `tipo/descripcion-corta` | Una por unidad de trabajo, siempre desde `develop` |

Nombres de rama: `feat/lote-02-maquina-estados`, `fix/worker-arranque`, `design/notas-corcho-textura`, `docs/errata-maestro`. Los lotes del backend llevan siempre `lote-NN` en el nombre.

**Commits** en formato convencional y en espanol: `tipo(alcance): descripcion`. Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `design`. Alcances: `backend`, `mobile`, `orquestacion`, `agentes`, `ci`.

**Pull requests** hacia `develop`, con la plantilla de `.github/pull_request_template.md`, y titulo en formato de commit convencional. Se fusionan con **merge commit** ("Create a merge commit"): se conservan los commits de la rama, y `develop` local se actualiza con un `git pull` normal. Por eso cada commit dentro de una rama tiene que ser convencional y tener sentido por si solo. Para ver una linea por PR: `git log --first-parent develop`.

Flujo de un lote del backend:

1. El orquestador escribe el prompt en `orquestacion/` y lo deja sin commitear.
2. **El primer paso de todo prompt es crear la rama**: la sesion ejecutora actualiza `develop` y crea desde ahi la rama con el nombre que el prompt indica, siguiendo el estandar de arriba.
3. La sesion trabaja y commitea en esa rama solo los archivos de su alcance. No commitea nada de `orquestacion/`, no hace push ni abre PR.
4. El orquestador valida contra `develop` y emite veredicto. Si rechaza, el correctivo va en la misma rama.
5. Con veredicto aprobado, el orquestador commitea el prompt y la bitacora en la misma rama, la sube y abre el PR.
6. Esteban revisa y hace el merge. El merge es siempre humano.
7. En la rama del lote siguiente, el orquestador borra el prompt del lote ya fusionado. En `orquestacion/` solo queda el prompt en curso; los anteriores se recuperan del historial con `git log --diff-filter=D -- orquestacion/<archivo>`.

## Documentacion oficial

`docs/ArtisTica_Documentacion_Oficial.md` es un entregable del curso EIF409 y se actualiza en cada avance. **Antes de abrir cualquier pull request**, aplicar la skill `documentacion-proyecto` (o la regla `.agents/rules/documentacion.md`): actualizar las secciones que el cambio afecta, o dejar escrito en el PR por que no aplica. La plantilla de PR tiene una casilla obligatoria para eso.

## Estilo

No usar guiones largos ni guiones medios en comentarios, mensajes de commit ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en el idioma del glosario del dominio; comentarios en espanol.
