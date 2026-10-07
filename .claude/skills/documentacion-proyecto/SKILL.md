---
name: documentacion-proyecto
description: Mantiene al dia la documentacion oficial del proyecto ArtísTica (docs/ArtisTica_Documentacion_Oficial.md), que es un entregable academico del curso EIF409. Usar antes de abrir o aprobar cualquier pull request, al cerrar un lote del backend, al registrar una decision en la bitacora, al cambiar precios, tarifas, planes o politicas, al encontrar un problema relevante durante el desarrollo, y cuando se prepara un avance del curso. Decide que secciones afecta un cambio, las actualiza o deja escrito por que no aplica.
---

# Documentación oficial del proyecto

`docs/ArtisTica_Documentacion_Oficial.md` es la documentación oficial de ArtísTica y un entregable del curso EIF409 de la Universidad Nacional. Se entrega en cada avance, convertida a Word, y se vuelve a tocar en el siguiente. Si queda desactualizada, el equipo entrega algo que no describe el proyecto real.

Esta skill tiene una sola tarea: **que ningún cambio relevante entre al repositorio sin que la documentación lo refleje, o sin dejar escrito por qué no hace falta.**

## Cuándo se aplica

| Momento | Quién |
|---|---|
| Antes de abrir un pull request | La sesión o persona que lo abre |
| Al validar un lote del backend | El orquestador, como parte de la lista de verificación |
| Al registrar una decisión `D` o una política nueva en `orquestacion/BITACORA.md` | Quien la registra |
| Al preparar un avance del curso | Todo el equipo |

## Qué sección afecta cada tipo de cambio

| Si el cambio... | Revisar la sección |
|---|---|
| Cambia qué es el producto, sus usuarios, roles, planes, principios o alcance por etapas | 1. Propuesta a desarrollar |
| Cambia canales, nichos, reclutamiento de artistas, demanda o expansión | 2. Estrategia de distribución |
| Cambia tarifas, precios, suscripción, promociones, costos, o cualquier regla de dinero del pedido (anticipo, disputa, cancelación, mínimos) | 3. Esquema de generación de dinero |
| Resuelve un problema no trivial, cambia una decisión anterior, o descubre algo de un proveedor externo | 4. Situaciones presentadas en el desarrollo |
| Termina un lote, agrega una pantalla, cambia el número de pruebas, o cambia el estado de un componente | 5. Avance de desarrollo |
| Introduce o renombra un término del dominio | 6. Anexo: glosario |

Un mismo cambio puede tocar varias secciones. Una decisión de precio, por ejemplo, toca la 3 y, si reemplaza algo anterior, la 4.

## Procedimiento

1. **Mirá el cambio completo:** `git diff --stat develop...HEAD`, y las decisiones nuevas de la bitácora si las hay.
2. **Ubicá cada cambio en la tabla de arriba.** Si ninguno aplica, el resultado es "no aplica", con la razón en una línea. Cambios de formato, refactorizaciones internas sin efecto visible y correcciones de la propia documentación de proceso normalmente no aplican.
3. **Si aplica, actualizá la sección** con lo que el cambio realmente hizo, verificado en el código o en la salida de los comandos. Nunca con lo que se planeaba hacer.
4. **En la sección 5, mantené los números al día:** cantidad de pruebas, tablas y estado de cada componente. Sacalos de la salida real, no de la memoria.
5. **En la sección 4, agregá una entrada nueva** con el mismo formato que las existentes: **Situación**, **Impacto**, **Resolución**. No reescribas situaciones viejas: son historia.
6. **Declaralo en el pull request**, en la casilla de documentación de la plantilla: qué secciones se actualizaron, o por qué no aplica.

## Reglas de redacción

El público es el cuerpo docente del curso, no el equipo de desarrollo.

- Español formal y neutro. Sin voseo: "el artista elige", no "elegís".
- Sin guiones largos ni guiones medios, como en el resto del repositorio.
- Sin jerga interna del repositorio: nada de "lote 2", "DT10", nombres de funciones ni rutas de archivo. En su lugar, lo que significa: "la etapa de reglas de pedidos", "una autorización que vence".
- Nombres del glosario del dominio: encargo, tarifa de servicio, obra, pedido, cobro. Nunca "comisión" en el sentido de porcentaje.
- Montos en colones con el signo ₡ y "aproximado" cuando corresponda. Dólares como US$.
- Solo hechos verificables en el repositorio o en las fuentes citadas. Lo pendiente se dice como pendiente.
- No mencionar herramientas de asistencia en el documento. Esa decisión, si se toma, la toma el equipo.

## Al cerrar un avance del curso

1. Subir la versión en la tabla **Control de versiones** y la fecha de la portada.
2. Revisar las cinco secciones completas, no solo las tocadas por el último cambio.
3. Generar el Word en `docs/entregas/`, con el número del avance en el nombre:

   ```
   cd docs/herramientas
   npm install
   npm run generar -- ../ArtisTica_Documentacion_Oficial.md ../entregas/ArtisTica_<N>_Avance.docx
   npm run indice -- ../entregas/ArtisTica_<N>_Avance.docx -Pdf
   ```

   El conversor cubre el Markdown que usa la documentación: portada hasta el primer `---`, títulos de nivel 2 a 4, párrafos con negrita y código, listas, tablas, y `---` como salto de página. `## Índice` se reemplaza por la tabla de contenido de Word, con los títulos de nivel 2 y 3 del Markdown. Formato fijo: Arial 12 en el texto, títulos de 16, 14 y 12 puntos, tablas en 10. Si se agrega otro elemento de Markdown, hay que extender `docs/herramientas/generar-docx.mjs`.

   `npm run indice` necesita Microsoft Word: calcula los números de página del índice y, con `-Pdf`, exporta una copia en PDF para revisar.
4. Revisar el PDF a ojo antes de entregar: que ninguna sección deje una página casi vacía ni una tabla partida. Extensión de referencia: 13 páginas en el II Avance. Se prefiere una frase menos a una página más.
5. Registrar la entrega en la tabla **Entregas del curso** de la bitácora.

## Verificación rápida

```
grep -c $'—\|–' docs/ArtisTica_Documentacion_Oficial.md   # debe dar 0
```
