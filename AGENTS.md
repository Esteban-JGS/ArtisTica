# ArtísTica

Plataforma costarricense donde se contrata arte hecho por personas, con el pago protegido. No es una red social: la parte social alimenta el momento de contratación.

La fuente de verdad del producto es `ArtisTica_Documento_Maestro.md`. Las decisiones de rumbo posteriores viven en `orquestacion/BITACORA.md` y las erratas del Maestro en `orquestacion/CORRECCIONES-DOCUMENTO-MAESTRO.md`. Si algo se contradice, gana el Maestro más su errata.

## Estructura

```
monorepo/
├── mobile/        React Native + Expo. Territorio de Brian
├── backend/       FastAPI y worker en Python 3.12. Territorio de Esteban
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

## Estilo

No usar guiones largos ni guiones medios en comentarios, mensajes de commit ni documentacion.
Explicaciones breves. Se prefiere codigo correcto a parrafos.
Codigo e identificadores en el idioma del glosario del dominio; comentarios en espanol.
