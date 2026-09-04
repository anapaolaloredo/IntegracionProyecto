# Prompt maestro para solicitar mejoras pequeñas y verificables con IA

Este archivo no existía en ningún material del curso ni del proyecto — el enunciado del ejercicio
(Tarea 2e) lo menciona como si ya debiera existir, pero se confirmó que no está en Blackboard ni
en el repositorio, así que se creó aquí mismo como la plantilla reutilizable que pide el ejercicio.

**Propósito:** que cada vez que se le pida a una IA una mejora al proyecto, la petición quede
acotada, verificable, y con evidencia de que la estudiante entendió y validó el resultado — no que
la IA sustituya el análisis.

## Plantilla

Copiar y llenar esta plantilla antes de enviar el prompt real a la IA:

```
CONTEXTO
--------
[Qué proyecto es, en qué estado está, qué se acaba de hacer antes de este cambio.]

NECESIDAD
---------
[Un problema concreto y pequeño, ya observado — no una idea vaga de "mejorar algo".]

ALCANCE PERMITIDO
------------------
[Lista exacta de archivos que la IA puede tocar. Si no está en la lista, no se toca.]

RESTRICCIONES
-------------
[Qué NO debe cambiar: lógica de negocio, modelos, otras funcionalidades, estilo del código, etc.]

CRITERIO DE ACEPTACIÓN
-----------------------
[Cómo se sabe que el cambio quedó bien — una condición observable, no "que funcione mejor".]

PRUEBAS A EJECUTAR ANTES DE ACEPTAR EL CAMBIO
-----------------------------------------------
[Pasos concretos y reproducibles para verificar el resultado antes de darlo por bueno.]

RIESGO ESPERADO
----------------
[Qué podría salir mal con este cambio, aunque sea pequeño.]
```

## Cómo se usa

1. Llenar la plantilla de arriba para el cambio que se quiere pedir.
2. Enviar ese contenido como el prompt real a la IA (el prompt exacto, tal cual, sin resumirlo).
3. Ejecutar las pruebas de la sección "Pruebas a ejecutar" contra el resultado.
4. Registrar el prompt exacto, la respuesta relevante, los archivos modificados, el riesgo
   introducido, las pruebas ejecutadas y el resultado en `docs/AI_PROMPT_HISTORY.md`.
5. Agregar una línea a `docs/AI_CHANGELOG.md` resumiendo el cambio.

Un ejemplo real, ya ejecutado con este mismo formato, está en `docs/AI_PROMPT_HISTORY.md`
(entrada del 31/08/2026: mostrar `mensajeError` en las vistas donde se guardaba pero nunca se
leía).
