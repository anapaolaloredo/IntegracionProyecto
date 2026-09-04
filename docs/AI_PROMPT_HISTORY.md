# Historial de prompts a IA — cambios aplicados al proyecto

Cada entrada sigue el formato de `docs/PROMPT_MAESTRO_IA.md`.

---

## Entrada 1 — 2026-08-31 — Mostrar `mensajeError` en vistas donde se guardaba pero no se leía

### Prompt exacto usado

```
CONTEXTO
--------
Proyecto "Libreria en linea" (Node.js + Express + EJS + PostgreSQL). Al corregir el hallazgo
TC-12b del plan de pruebas (subida de imagen invalida daba error 500 en vez de un mensaje
controlado), se detecto que req.session.mensajeError se usa en 4 lugares del codigo pero solo se
LEE y muestra en una vista (auth/login.ejs). Las otras 3 escrituras (requerirSesion,
libroController.subirImagen -ya corregido-, catalogoController.eliminar, usuarioController.eliminar)
guardan el mensaje pero las vistas usuarios/listar.ejs y las 4 vistas listar.ejs de catalogos
genericos (formatos/generos/autores/conceptos) nunca lo leen ni lo muestran: el mensaje se pierde
en silencio.

NECESIDAD
---------
Que cuando catalogoController.eliminar o usuarioController.eliminar guarden un mensajeError (por
ejemplo, al intentar eliminar un formato en uso por un libro, o al intentar que el admin se
elimine a si mismo), ese mensaje se vea de verdad en la pagina a la que se redirige.

ALCANCE PERMITIDO
------------------
- apps/web-monolito01/src/controllers/usuarioController.js (solo el metodo listar)
- apps/web-monolito01/src/controllers/catalogoController.js (solo el metodo listar)
- apps/web-monolito01/src/views/usuarios/listar.ejs
- apps/web-monolito01/src/views/formatos/listar.ejs
- apps/web-monolito01/src/views/generos/listar.ejs
- apps/web-monolito01/src/views/autores/listar.ejs
- apps/web-monolito01/src/views/conceptos/listar.ejs

RESTRICCIONES
-------------
No modificar los metodos eliminar/crear/actualizar (ya guardan el mensaje correctamente). No
modificar ninguna consulta SQL, ningun modelo, ni la logica de negocio de los catalogos. Seguir el
mismo patron ya usado y verificado en libroController.detalle/libros/detalle.ejs (leer y limpiar
req.session.mensajeError, pasarlo a la vista, mostrarlo en un <div class="mensaje-error">).

CRITERIO DE ACEPTACION
-----------------------
Al intentar una accion que ya genera un mensajeError (eliminar el propio usuario admin, eliminar
un formato en uso), la pagina de listado correspondiente debe mostrar ese mensaje. Una carga
normal de la misma pagina, sin ningun error pendiente, no debe mostrar ningun mensaje.

PRUEBAS A EJECUTAR ANTES DE ACEPTAR EL CAMBIO
-----------------------------------------------
1. Levantar la app real contra una base de datos de prueba.
2. Iniciar sesion como administrador.
3. POST /library/usuarios/<propio_id>?_method=DELETE, luego GET /library/usuarios -> debe
   mostrar "No puedes eliminar tu propia cuenta...".
4. POST /library/formatos/<id_en_uso>?_method=DELETE, luego GET /library/formatos -> debe mostrar
   "No se pudo eliminar: probablemente esta en uso...".
5. Repetir el GET de ambas paginas una segunda vez y confirmar que el mensaje ya NO aparece
   (el flash se consume una sola vez).

RIESGO ESPERADO
----------------
Bajo: es un cambio aditivo (agregar una linea de lectura en el controlador y un bloque condicional
en la vista), sin tocar logica de negocio ni consultas SQL. El riesgo principal es olvidar limpiar
`req.session.mensajeError` despues de leerlo, lo que haria que el mensaje se repitiera en cada
carga de la pagina en vez de mostrarse una sola vez.
```

### Respuesta relevante (resumen de lo aplicado)

Se agregó, en `usuarioController.listar` y en el `listar` de la fábrica
`crearCatalogoController`, la lectura y limpieza de `req.session.mensajeError` antes de renderizar,
pasándolo a la vista. Se agregó `<% if (mensajeError) { %><div class="mensaje-error">...<% } %>`
justo después del `<h1>` en `usuarios/listar.ejs` y en las 4 vistas `listar.ejs` de catálogos
genéricos (formatos, géneros, autores, conceptos), replicando exactamente el patrón ya usado y
probado en `libros/detalle.ejs`.

### Archivos modificados

- `apps/web-monolito01/src/controllers/usuarioController.js`
- `apps/web-monolito01/src/controllers/catalogoController.js`
- `apps/web-monolito01/src/views/usuarios/listar.ejs`
- `apps/web-monolito01/src/views/formatos/listar.ejs`
- `apps/web-monolito01/src/views/generos/listar.ejs`
- `apps/web-monolito01/src/views/autores/listar.ejs`
- `apps/web-monolito01/src/views/conceptos/listar.ejs`

### Riesgo introducido

Bajo, confirmado tras la prueba: ninguno de los métodos `eliminar`/`crear`/`actualizar` se tocó;
sólo se agregó lectura+limpieza del mensaje en `listar`. El riesgo real (olvidar limpiar
`req.session.mensajeError`, causando que el mensaje se repita en cada carga) se descartó
explícitamente con la prueba 5.

### Pruebas ejecutadas y resultado

Se levantó la app real (`npm start` con variables de entorno apuntando a PostgreSQL local) y se
probó con `curl` manejando cookies de sesión:

1. Login como administrador → `302` (sesión iniciada).
2. `POST /library/usuarios/2?_method=DELETE` (auto-eliminación) → `302`; `GET /library/usuarios` →
   mostró `"No puedes eliminar tu propia cuenta mientras tienes la sesion activa."` en
   `<div class="mensaje-error">`.
3. `POST /library/formatos/1?_method=DELETE` (formato en uso) → `302`; `GET /library/formatos` →
   mostró `"No se pudo eliminar: probablemente esta en uso por uno o mas libros."`.
4. Repetición de ambos `GET`: `0` ocurrencias de `mensaje-error` en el HTML — el mensaje no se
   repite, se consume una sola vez.

**Resultado: cambio aceptado.** Las 4 verificaciones de la sección "Pruebas a ejecutar" del prompt
se cumplieron. Este mismo hallazgo estaba explícitamente anotado como pendiente en
`docs/TEST_PLAN.md` (sección "Pendiente") desde la corrección de TC-12b; con este cambio queda
cerrado.
