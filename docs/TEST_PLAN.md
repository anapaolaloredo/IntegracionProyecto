# Plan y resultados de pruebas — Librería en línea (Ejercicio Guiado 02)

**Entorno de ejecución:** PostgreSQL 15 local, base `library`, rol de aplicación `library_user`
(sin privilegios de superusuario, `CREATE ROLE library_user WITH LOGIN PASSWORD '666'` — sin
`SUPERUSER`/`CREATEDB`/`CREATEROLE`), esquema cargado desde `data/library_schema.sql` sin
modificaciones, datos de `data/library_data.sql`. App corriendo con `npm start`
(`BASE_PATH=/library`), probada con `curl` (incluye manejo de cookies de sesión) y con `psql`
directo para las pruebas de integridad de base de datos. Fecha de ejecución: 2026-08-31.

Todas las filas de este documento corresponden a pruebas **efectivamente ejecutadas** contra el
código real del repositorio, no a resultados esperados sin correr.

## Funcionales — autenticación y sesión

| ID | Requisito | Entrada | Pasos | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|---|---|
| TC-05 | RF-01 registro | `nombre_usuario=test_nuevo`, correo y contraseña válidos, sin sesión previa de admin distinta a la ya existente | `POST /library/auth/registro` | Cuenta creada con rol `cliente` (ya existe un admin) | `302 → /library/libros`; fila creada en `usuarios` con `rol='cliente'` | ✅ Pasó |
| TC-06 | RF-02 login | Correo/contraseña válidos (`admin@libreria.test` / `123456`) | `POST /library/auth/login` | Sesión iniciada, redirección al catálogo | `302 → /library/libros` | ✅ Pasó |
| TC-07 | RF-02 login (negativo) | Correo válido, contraseña incorrecta | `POST /library/auth/login` | Error genérico, sin distinguir campo | `401`, `"Credenciales invalidas."` (mismo mensaje que correo inexistente) | ✅ Pasó |
| TC-08 | RF-03 logout | Sesión activa | `POST /library/auth/logout` | Sesión destruida, redirección a login | `302 → /library/auth/login` | ✅ Pasó |

## Funcionales — catálogo, CRUD y relaciones

| ID | Requisito | Entrada | Pasos | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|---|---|
| TC-04 | RF-04 catálogo autenticado | Sesión de administrador activa | `GET /library/libros` | Catálogo accesible, HTML renderiza | `200`, `<h1>Catalogo de libros</h1>` | ✅ Pasó |
| TC-09a | RF-07 CRUD autores — crear | Admin, `nombre_autor=Autor De Prueba TC09` | `POST /library/autores` | Autor creado | Fila creada, `id_autor=8` | ✅ Pasó |
| TC-09b | RF-06 CRUD libros — crear | Admin, ISBN/título/formato/autor/género válidos | `POST /library/libros` | Libro creado con relaciones | `302 → /library/libros/12`; fila creada en `libros` | ✅ Pasó |
| TC-09c | RF-07 CRUD autores — editar | Admin, `_method=PUT`, nuevo nombre | `POST /library/autores/8?_method=PUT` | Registro actualizado | `nombre_autor` cambiado a "Autor Editado TC09" en BD | ✅ Pasó |
| TC-09d | RF-07 CRUD autores — eliminar | Admin, `_method=DELETE` | `POST /library/autores/8?_method=DELETE` | Registro eliminado | `count(*)=0` para `id_autor=8` | ✅ Pasó |
| TC-10 | RF-11 relación libro-autor / libro-género | Admin asocia 2 autores y 2 géneros al libro 1 | `fn_asociar_autor`/`fn_asociar_genero` (misma función que usa el controlador) | Ambas relaciones N:M quedan asociadas sin duplicar | `fn_listar_autores_por_libro(1)` y `fn_listar_generos_por_libro(1)` devuelven 3 filas cada una (1 original + 2 nuevas), sin duplicados | ✅ Pasó |
| TC-11 | RF-12 concepto con definición por libro | Mismo `id_concepto=1` definido en libro 1 y libro 2 con texto distinto | `fn_definir_concepto(1,1,'...')`, `fn_definir_concepto(2,1,'...')` | Cada libro conserva su propia definición | `fn_listar_conceptos_por_libro(1)` y `(2)` devuelven textos distintos para el mismo concepto | ✅ Pasó |
| TC-12a | RF-13/14 imágenes — subida válida | Admin, PNG válido, `es_portada=on` | `POST /library/libros/12/imagenes` (multipart) | Imagen aceptada, nombre generado por el sistema, marcada portada | `302`; fila en `imagenes_libro` con `url_imagen=/uploads/1788230305174-823191468.png` (no el nombre original) y `es_portada=true` | ✅ Pasó |
| TC-12b | RF-13 imágenes — archivo inválido | Admin, archivo `.exe` con contenido de texto | `POST /library/libros/12/imagenes` (multipart) | Rechazado por extensión/MIME, sin exponer detalles internos, con mensaje visible al usuario | **Re-ejecutado tras el fix:** redirección `302` a `/library/libros/12` (en vez de `500`), la página muestra `"Solo se permiten imagenes (jpg, jpeg, png, webp, gif)."` en un `<div class="mensaje-error">`. También se probó el límite de tamaño (&gt;5&nbsp;MB): mensaje `"El archivo supera el tamano maximo permitido (5 MB)."` | ✅ Pasó (corregido, ver `docs/ENGINEERING_DECISIONS.md` y sección de hallazgos) |
| TC-21 | RF-05 búsqueda por ISBN/título | `GET /library/libros?q=Prueba` | Sólo los libros coincidentes deberían aparecer | **Re-ejecutado tras implementar la búsqueda:** `?q=Prueba` devuelve 1 tarjeta (antes mostraba las 8); `?q=1111111111111` (ISBN exacto) devuelve la misma 1 tarjeta; `?q=xyznoexiste` muestra `"No se encontraron libros que coincidan con..."`; sin `q` se siguen mostrando los 8 libros | ✅ Pasó (implementado, ver hallazgos) |

## Autorización por rol

| ID | Requisito | Entrada | Pasos | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|---|---|
| TC-13 | RF-17 visitante | Sin sesión | `GET /library/libros` | Redirección a login | `302 → /library/auth/login` | ✅ Pasó |
| TC-14a | RF-17 cliente — lectura de ruta admin | Sesión de `juan_perez` (cliente) | `GET /library/usuarios` | `403` controlado | `403`, `<h1>Acceso denegado</h1>` (sin stack trace) | ✅ Pasó |
| TC-14b | RF-17 cliente — escritura en ruta admin | Sesión de `juan_perez` (cliente) | `POST /library/libros` | `403` controlado | `403`, `<h1>Acceso denegado</h1>` | ✅ Pasó |

## Integridad y restricciones de PostgreSQL (pruebas negativas — vía `psql`)

| ID | Amenaza / regla | Sentencia ejecutada | Resultado esperado | Error real de PostgreSQL | Estado |
|---|---|---|---|---|---|
| TC-15 | RF-16 un solo Administrador | `SELECT fn_crear_usuario('otro_admin', 'otroadmin@x.com', crypt('123456', gen_salt('bf')), 'admin');` | Rechazado | `ERROR: duplicate key value violates unique constraint "uq_usuarios_admin_unico" DETALLE: Key (rol)=(admin) already exists.` | ✅ Pasó |
| TC-16 | ISBN duplicado | `SELECT fn_crear_libro('9780307474728','Duplicado ISBN',2020::smallint,10.00,5,1);` | Rechazado | `ERROR: duplicate key value violates unique constraint "libros_isbn_key"` | ✅ Pasó |
| TC-17a | Stock negativo | `SELECT fn_crear_libro('9999999999999','Stock negativo',2020::smallint,10.00,-5,1);` | Rechazado | `ERROR: new row for relation "libros" violates check constraint "libros_stock_check"` | ✅ Pasó |
| TC-17b | Precio inválido (&lt; 0) | `SELECT fn_crear_libro('9999999999998','Precio invalido',2020::smallint,-1.00,5,1);` | Rechazado | `ERROR: new row for relation "libros" violates check constraint "libros_precio_check"` | ✅ Pasó |
| TC-18 | FK inexistente | `SELECT fn_crear_libro('9999999999997','Formato inexistente',2020::smallint,10.00,5,9999);` | Rechazado | `ERROR: insert or update on table "libros" violates foreign key constraint "libros_id_formato_fkey" DETALLE: Key (id_formato)=(9999) is not present in table "formatos".` | ✅ Pasó |
| TC-19 | Eliminación que viola relación | `DELETE FROM autores WHERE id_autor = 1;` (autor referenciado por un libro) | Rechazado | `ERROR: update or delete on table "autores" violates foreign key constraint "libro_autor_id_autor_fkey" DETALLE: Key (id_autor)=(1) is still referenced from table "libro_autor".` | ✅ Pasó |
| TC-20 | Inyección SQL con caracteres especiales | Consulta preparada (mismo mecanismo `$1` que usa `pg`): `PREPARE p(varchar) AS SELECT fn_crear_concepto($1); EXECUTE p($$malicioso'); DROP TABLE conceptos; --$$);` | El valor se trata como dato literal; la tabla no se ve afectada | `fn_crear_concepto` devolvió `id=6`; `conceptos` pasó de 5 a 6 filas (una fila nueva, no una tabla borrada); `nombre_concepto` guardado literalmente como `malicioso'); DROP TABLE conceptos; --` | ✅ Pasó |

## Triggers y vistas (agregados el 2026-08-31, probados contra base de datos recreada desde cero)

| ID | Objeto | Entrada | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|---|
| TC-22 | Trigger `trg_una_portada_por_libro` | Libro 1 ya tenía una imagen con `es_portada=true`; se agrega una segunda con `fn_agregar_imagen(1, '/uploads/segunda-portada.jpg', 1::smallint, true)` | La imagen anterior se desmarca sola, sin que la función lo pida explícitamente | La imagen `id_imagen=1` pasó a `es_portada=false` automáticamente al insertar la `id_imagen=8` con `true` | ✅ Pasó |
| TC-23 | Trigger `trg_libros_fecha_actualizacion` | `fn_actualizar_libro(1, ...)` sobre un libro existente | `fecha_actualizacion` cambia, `fecha_creacion` no | `fecha_creacion` se mantuvo en `21:01:48`, `fecha_actualizacion` pasó a `21:02:11` | ✅ Pasó |
| TC-24 | Trigger `trg_usuarios_auditoria_rol` | `fn_actualizar_usuario` cambia el rol de `admin_paola` a `cliente` y luego el de `juan_perez` a `admin` | Ambos cambios quedan en `usuarios_auditoria_rol` con rol anterior/nuevo y fecha | 2 filas insertadas: `(1, admin→cliente)` y `(2, cliente→admin)`, con `fecha_cambio` real | ✅ Pasó |
| TC-25 | Vista `vista_administradores` | Tras el cambio de rol anterior | Sólo debe listar al Administrador vigente | Devolvió únicamente a `juan_perez` (ya no `admin_paola`) | ✅ Pasó |
| TC-26 | Vista `vista_libros_stock_bajo` | `UPDATE libros SET stock=3 WHERE id_libro=2` | El libro con stock bajo aparece en la vista | Devolvió "El aleph", `stock=3` | ✅ Pasó |
| TC-27 | Vista `vista_catalogo_libros` (ahora usada por `LibroModel.listarConDetalle`) | `GET /library/libros` y `GET /library/libros?q=aleph` contra la app real | El catálogo y la búsqueda siguen funcionando igual que antes de mover el JOIN a la vista | `200` en ambos; catálogo completo (7 libros) sin `q`, 1 resultado con `q=aleph` | ✅ Pasó |
| TC-28 | `mensajeError` visible en `usuarios/listar.ejs` y catálogos genéricos (Tarea 2e, `docs/AI_PROMPT_HISTORY.md`) | Admin intenta auto-eliminarse (`POST /library/usuarios/2?_method=DELETE`) y eliminar un formato en uso (`POST /library/formatos/1?_method=DELETE`) | El mensaje de error queda visible en la página de listado, y no se repite en una carga posterior | `GET /library/usuarios` mostró "No puedes eliminar tu propia cuenta..."; `GET /library/formatos` mostró "No se pudo eliminar: probablemente esta en uso..."; una segunda carga de ambas páginas ya no mostró el mensaje | ✅ Pasó |
| TC-29 | Bug reportado por la estudiante: columna ID vacía en `GET /library/autores` | Cargar el listado de autores con sesión de administrador | La columna ID muestra el id real de cada autor, y "Editar"/"Eliminar" apuntan a ese id | Antes del fix: columna ID vacía, links a `/autores/undefined/editar` (causa: `id_${vista.slice(0,-1)}` calculaba `id_autore` en vez de `id_autor`, plural irregular). Después del fix (`idCampo='id_autor'` explícito en `routes/index.js`): columna ID muestra `5, 1, 4, 3...` reales, links `/library/autores/5/editar` correctos | ✅ Pasó (corregido) |
| TC-30 | Texto alternativo de imágenes (D-17) | Admin sube una imagen con `texto_alternativo="Ilustracion de prueba TC-30"` vía `POST /library/libros/1/imagenes` (multipart) | El texto se guarda y aparece como `alt` del `<img>` en el detalle del libro | Fila creada en `imagenes_libro` con `texto_alternativo='Ilustracion de prueba TC-30'`; `GET /library/libros/1` renderiza `<img alt="Ilustracion de prueba TC-30">` | ✅ Pasó |

## Despliegue bajo reverse proxy

| ID | Requisito | Entrada | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|---|
| TC-01 | RNF-06 despliegue | `GET http://IP_SERVIDOR/library/` sin sesión, `BASE_PATH=/library` | Redirección a `/library/auth/login`, estáticos con prefijo | `302`; página renderiza con `href`/`action` ya prefijados (ver `evidencias/01-...png`) | ✅ Pasó |
| TC-02 | RNF-06 despliegue | `curl` directo a rutas y estáticos bajo `/library` | 200 dentro del prefijo, 404 fuera | Confirmado con `curl -w "%{http_code}"` | ✅ Pasó |
| TC-03 | RNF-06 despliegue local | `BASE_PATH=''`, acceso a `/` y `/auth/login` | Comportamiento idéntico al de antes del cambio, sin prefijo | `/` → 302 a `/auth/login`; formulario sin prefijo | ✅ Pasó |

## Hallazgos encontrados durante la ejecución de estas pruebas (ambos corregidos y re-probados)

1. **TC-12b (UX de manejo de errores) — corregido.** Cuando `multer` rechazaba un archivo por
   tipo inválido, el error de `fileFilter` llegaba directo al manejador de errores global de
   Express (página completa "Error interno", `500`) en vez de seguir el patrón del resto de la
   app (redirigir de vuelta con un mensaje). **Fix aplicado:** `middlewares/upload.js` ahora
   exporta `subirImagenControlado`, que envuelve `upload.single('imagen')` y captura el error de
   `multer` (tipo inválido o `LIMIT_FILE_SIZE`), lo guarda en `req.session.mensajeError` y
   redirige a `/libros/:id`. También se descubrió — y se corrigió — que `libros/detalle.ejs`
   nunca mostraba `mensajeError` (el mecanismo de mensaje flash sólo se leía en el login);
   `LibroController.detalle` ahora lo lee, lo limpia de la sesión y lo pasa a la vista, que lo
   renderiza en un `<div class="mensaje-error">`. Re-ejecutado: `302` en vez de `500`, mensaje
   visible en la página del libro; también verificado el caso de archivo &gt;5&nbsp;MB con un
   mensaje propio.
2. **TC-21 (RF-05 no implementado) — corregido.** Se agregó la búsqueda por ISBN/título:
   `LibroModel.listarConDetalle(busqueda)` ahora filtra con
   `WHERE $1::text IS NULL OR l.isbn = $1 OR l.titulo ILIKE '%' || $1 || '%'` (parametrizado,
   sin concatenar el término de búsqueda directamente en el SQL); `LibroController.catalogo` lee
   `req.query.q`; `views/libros/catalogo.ejs` agrega un formulario `GET` con el campo `q`, un
   botón "Limpiar" y un mensaje de "sin resultados" cuando corresponde. Re-ejecutado: filtra por
   título parcial y por ISBN exacto, conserva el catálogo completo sin `q`, y muestra el mensaje
   de "no se encontraron libros" cuando no hay coincidencias.

## Verificación manual de la estudiante (navegador real, 2026-08-31)

Además de las pruebas automatizadas de arriba, la estudiante probó la aplicación manualmente en el
navegador (capturas en `html/ejercicio02/evidencias/`: `catalogo.png`, `usuarios.png`,
`autores.png`, `libroguardado.png`, `vistaclientecatalogo.png`, `usuariocreadodesderegistro.png`):
catálogo con 7 libros, listado de usuarios, creación de un libro nuevo ("Don Quijote de la
Mancha") con autor y género asociados, registro de un nuevo usuario cliente, y la vista de
catálogo como usuario cliente (no administrador). Confirmación textual de la estudiante: **"todo
crud funciona de lo que vi"**. De esta revisión manual salió el hallazgo real de TC-29 (columna ID
vacía en Autores), ya corregido arriba.

## Resumen

- **30 de 30 casos ejecutados; 30 de 30 pasan** (21 originales, corregidos TC-12b y TC-21, TC-22 a
  TC-27 al implementar los triggers y vistas, TC-28 al corregir el `mensajeError` sin mostrar,
  TC-29 al corregir el bug de columna ID vacía en Autores encontrado por la estudiante, y TC-30 al
  implementar el texto alternativo de imágenes).
- El seed se re-ejecutó completo con las 30 filas por tabla (`db/02_seed_30_per_table.sql`) contra
  una base de datos recreada desde cero con la secuencia `db/00→01→04→05→06→02`, confirmando
  conteos reales: `usuarios=30, autores=30, generos=30, conceptos=30, libros=30, formatos=8,
  libro_autor=30, libro_genero=51, imagenes_libro=30`.
- Los tres hallazgos corregidos (TC-12b, TC-21, TC-29) se volvieron a ejecutar contra la misma
  base de datos y la misma app real para confirmar el fix — ninguno se dio por bueno sin
  reprobarlo.

## Pendiente

- Automatizar estos casos como pruebas repetibles (hoy `test/iniciosesion.test.js` está vacío y
  `test/usuarios.test.js` no correría tal cual, ver `docs/ENGINEERING_DECISIONS.md`).
- Repetir esta ejecución contra el servidor real en GCP (aquí se ejecutó contra una base de datos
  y una instancia local de PostgreSQL 15, levantadas específicamente para esta prueba).
- ~~El mismo patrón de `mensajeError` nunca leído... en `usuarios/listar.ejs` y catálogos
  genéricos~~ — **corregido el 2026-08-31** como la mejora pequeña y verificable de la Tarea 2e
  (ver TC-28 y `docs/AI_PROMPT_HISTORY.md`).
