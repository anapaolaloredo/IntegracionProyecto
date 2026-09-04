# Registro de decisiones de ingeniería — Librería en línea (Ejercicio Guiado 02)

Cada decisión sigue el esquema pedido por el ejercicio:

> Necesidad o problema → alternativas consideradas → decisión tomada → justificación técnica →
> riesgo o limitación → evidencia de validación

---

## D-01. Arquitectura monolítica vs. desacoplada/microservicios

- **Necesidad:** elegir la macro-arquitectura del sistema desde el inicio, antes de escribir código.
- **Alternativas consideradas:** (a) monolito server-side (Node.js + Express + EJS); (b) frontend
  SPA + API REST separada; (c) microservicios por dominio (usuarios, catálogo, imágenes).
- **Decisión tomada:** monolito server-side, restricción explícita del ejercicio.
- **Justificación técnica:** para el alcance (una librería en línea con un equipo de una persona y
  un solo entorno de despliegue) un monolito minimiza la complejidad operativa: un solo proceso,
  un solo repositorio, un solo pipeline de despliegue, sin necesidad de orquestar red entre
  servicios ni de resolver consistencia distribuida.
- **Riesgo/limitación:** todo el sistema escala como una sola unidad; un error en un módulo
  (por ejemplo, la subida de imágenes) puede afectar la disponibilidad de todo lo demás. No hay
  aislamiento de fallos entre dominios.
- **Evidencia de validación:** estructura real del repo (`routes/`, `controllers/`, `models/`,
  `middlewares/`, `views/` dentro de un único `app.js`), un solo `package.json`, un solo proceso
  (`npm start`) verificado en `docs/GCP_COMMANDS.md`.

## D-02. Acceso directo a PostgreSQL (sin ORM, sin API intermedia)

- **Necesidad:** decidir cómo la capa de controladores accede a los datos.
- **Alternativas consideradas:** (a) ORM (Sequelize/Prisma); (b) acceso directo con `pg` y SQL
  parametrizado; (c) exponer una API interna (REST/GraphQL) entre la app y la base de datos.
- **Decisión tomada:** acceso directo con `pg`, delegando la lógica de datos a funciones PL/pgSQL
  (`fn_crear_*`, `fn_listar_*`, `fn_actualizar_*`, `fn_eliminar_*`, `fn_asociar_*`) definidas en
  `data/library_schema.sql`.
- **Justificación técnica:** cumple la restricción de "sin APIs ni JSON/XML entre capas"; las
  funciones PL/pgSQL centralizan las reglas de integridad (por ejemplo, la resincronización de
  autores/géneros de un libro) en la base de datos, evitando que la lógica de negocio crítica
  dependa únicamente del código de aplicación.
- **Riesgo/limitación:** la lógica queda repartida entre PostgreSQL (funciones) y Node.js
  (controladores), lo que exige mantener sincronizados dos lenguajes distintos (SQL/PLpgSQL y
  JavaScript) y dificulta portar el proyecto a otro motor de base de datos en el futuro.
- **Evidencia de validación:** todos los modelos (`models/*.js`) invocan `SELECT fn_*(...)` con
  parámetros posicionales (`$1, $2, ...`), nunca concatenación de strings — confirmado por
  inspección directa del código.

## D-03. Renderizado server-side con EJS (sin frontend separado)

- **Necesidad:** decidir cómo se genera la interfaz que ve el usuario.
- **Alternativas consideradas:** (a) SSR con motor de plantillas (EJS/Pug); (b) SPA en
  React/Vue consumiendo una API; (c) HTML estático + JavaScript en el cliente.
- **Decisión tomada:** SSR con EJS.
- **Justificación técnica:** coherente con "sin JSON/XML entre frontend y backend"; el servidor
  entrega HTML ya resuelto, los formularios envían datos vía `POST`/`PUT`(-override)/`DELETE`
  directamente al monolito, sin una capa de serialización intermedia.
- **Riesgo/limitación:** cualquier interacción dinámica en el cliente (validación instantánea,
  actualizaciones parciales) requeriría JavaScript adicional en el navegador o una recarga
  completa de página; no hay una experiencia tipo SPA.
- **Evidencia de validación:** las 26 vistas `.ejs` del proyecto no contienen lógica de negocio ni
  SQL — sólo interpolación de datos ya resueltos por el controlador (verificado por inspección).

## D-04. Sin APIs REST/GraphQL/SOAP (restricción pedagógica)

- **Necesidad:** decidir si exponer algún endpoint programático adicional (por ejemplo, para una
  futura app móvil) durante este ejercicio.
- **Alternativas consideradas:** (a) no exponer ninguna API; (b) exponer una API interna mínima
  de solo lectura "por si acaso".
- **Decisión tomada:** (a), ninguna API.
- **Justificación técnica:** requisito explícito del ejercicio; además evita superficie de ataque
  adicional (no hay endpoints JSON que requieran su propia autenticación/autorización y validación
  de esquema).
- **Riesgo/limitación:** si en el futuro se necesita un cliente distinto al navegador (app móvil,
  integración con otro sistema), habría que construir esa capa de API desde cero sobre el monolito
  actual, posiblemente reestructurando controladores que hoy responden con `render`/`redirect` en
  vez de JSON.
- **Evidencia de validación:** `package.json` no incluye dependencias de un framework de API
  (no hay `cors`, ni serializadores JSON de respuesta); todas las rutas terminan en `res.render(...)`
  o `res.redirect(...)`.

## D-05. PostgreSQL en el mismo servidor que la aplicación

- **Necesidad:** decidir dónde vive la base de datos respecto a la aplicación Node.js.
- **Alternativas consideradas:** (a) PostgreSQL en la misma instancia de Compute Engine; (b) Cloud
  SQL (PostgreSQL gestionado) en un proyecto/instancia separada.
- **Decisión tomada:** (a), PostgreSQL co-localizado en `maquina-integracion`.
- **Justificación técnica:** simplifica el ejercicio (una sola instancia que administrar, sin
  configurar redes privadas ni Cloud SQL Auth Proxy) y evita costo/latencia de red adicional para
  un volumen de datos de práctica.
- **Riesgo/limitación:** sin aislamiento de recursos entre la app y la base de datos (ver D-01);
  sin backups automáticos ni alta disponibilidad que sí ofrecería un servicio gestionado; un
  reinicio o falla de la instancia se lleva ambos servicios a la vez.
- **Evidencia de validación:** `config/db.js` apunta a `PGHOST=localhost` por defecto; confirmado
  en `docs/GCP_COMMANDS.md` que PostgreSQL se instaló con `dnf` en la misma instancia.

## D-06. Organización modular tipo MVC server-side

- **Necesidad:** evitar concentrar toda la lógica en `app.js` o en las vistas, tal como pide el
  ejercicio.
- **Alternativas consideradas:** (a) todo en `app.js`; (b) separación por capas
  (`routes/controllers/models/middlewares/views`).
- **Decisión tomada:** (b).
- **Justificación técnica:** cada carpeta tiene una responsabilidad única y verificable: `routes/`
  sólo despacha, `controllers/` valida y orquesta, `models/` es el único punto de acceso a datos,
  `middlewares/` centraliza autenticación/autorización/inyección de contexto, `views/` sólo
  presenta.
- **Riesgo/limitación:** más archivos y más indirección para cambios pequeños; un desarrollador
  nuevo necesita entender el flujo completo (ruta → middleware → controlador → modelo → vista)
  para hacer un cambio end-to-end.
- **Evidencia de validación:** `app.js` mide ~65 líneas y sólo hace inicialización/montaje; no
  contiene `SELECT`/`INSERT` ni validaciones de negocio (verificado por inspección).

## D-07. Fábrica genérica para los catálogos simples (formatos/géneros/autores/conceptos)

- **Necesidad:** los cuatro catálogos (formatos, géneros, autores, conceptos) comparten el mismo
  CRUD (id + nombre); evitar duplicar rutas/controladores cuatro veces.
- **Alternativas consideradas:** (a) un controlador y un archivo de rutas por catálogo (repetido
  4 veces); (b) una fábrica (`crearCatalogoController`, `crearCatalogoRoutes`) parametrizada por
  modelo/vista/etiqueta.
- **Decisión tomada:** (b).
- **Justificación técnica:** reduce a un único lugar el CRUD genérico; agregar un quinto catálogo
  en el futuro sólo requiere una tabla, un modelo y una línea de registro en `routes/index.js`.
- **Riesgo/limitación:** un error en la fábrica afecta a los cuatro catálogos simultáneamente; el
  código es menos explícito para quien busca la lógica de "autores" directamente en un archivo
  llamado `autores.js` (no existe; vive en `catalogoController.js`/`catalogoRoutes.js`).
- **Evidencia de validación:** `catalogoController.js` y `catalogoRoutes.js` (30-60 líneas cada
  uno) reemplazan lo que serían ~8 archivos casi idénticos.

## D-08. Autenticación con `bcrypt` + sesiones persistidas en PostgreSQL

- **Necesidad:** decidir cómo se autentica al usuario y dónde vive el estado de sesión.
- **Alternativas consideradas:** (a) contraseñas en texto plano (descartado de inicio, inaceptable);
  (b) hash con `bcrypt` + sesión en memoria; (c) hash con `bcrypt` + sesión persistida en
  PostgreSQL vía `connect-pg-simple`; (d) autenticación sin estado con JWT.
- **Decisión tomada:** (c).
- **Justificación técnica:** `bcrypt` es el estándar de facto para hash de contraseñas con
  factor de costo ajustable (10 rondas); persistir la sesión en PostgreSQL (en vez de memoria)
  evita perder las sesiones activas si el proceso Node se reinicia, y evita añadir una pieza de
  infraestructura extra (Redis) sólo para este propósito. JWT se descartó porque el ejercicio no
  usa APIs/tokens entre capas.
- **Riesgo/limitación:** la tabla de sesiones comparte la misma base de datos que los datos de
  negocio (ver D-05): un pico de tráfico de sesión compite por recursos con las consultas de
  catálogo/CRUD. Además, `bcrypt` es un módulo nativo compilado — en el despliegue real se
  encontró justamente un problema de binario incompatible ("invalid ELF header") al mover el
  proyecto a un servidor con arquitectura/SO distinto, que requirió recompilarlo con
  `npm rebuild bcrypt --build-from-source` y las herramientas de compilación del sistema
  (`gcc`, `make`, `python3`).
- **Evidencia de validación:** tabla `session` creada automáticamente por
  `connect-pg-simple` (`createTableIfMissing: true`); login/logout probados manualmente
  (ver `docs/TEST_PLAN.md`, casos TC-06 a TC-08 — pendientes de ejecución formal) y evidencia de
  sesión de administrador activa en `evidencias/02-catalogo-libros-admin-local.png`.

## D-09. Autorización por rol centralizada en middleware (no dispersa en cada controlador)

- **Necesidad:** garantizar que las funciones de administración (crear/editar/eliminar libros,
  catálogos y usuarios) sólo sean accesibles por el rol `admin`, y que ningún controlador quede
  sin ese candado por descuido.
- **Alternativas consideradas:** (a) verificar el rol manualmente al inicio de cada función de
  controlador; (b) dos middlewares reutilizables (`requerirSesion`, `requerirAdmin`) aplicados
  desde las rutas.
- **Decisión tomada:** (b).
- **Justificación técnica:** aplicar el candado en la capa de rutas hace visible, en un solo
  archivo por dominio, qué operación requiere qué nivel de acceso, en vez de tener que revisar el
  cuerpo de cada función de controlador para confirmarlo.
- **Riesgo/limitación:** si una ruta nueva se agrega sin recordar anteponer `requerirAdmin`,
  queda accesible a cualquier usuario autenticado sin que ningún test lo detecte automáticamente
  (no hay pruebas automatizadas de autorización todavía, ver `docs/TEST_PLAN.md`).
- **Evidencia de validación — auditoría línea por línea de `routes/*.js` (2026-08-31):**
  - `routes/usuarios.js`: `router.use(requerirSesion, requerirAdmin)` protege **todo** el router
    de usuarios de una sola vez — ninguna ruta de gestión de usuarios es alcanzable sin rol admin.
  - `routes/libros.js`: `router.use(requerirSesion)` protege todo el router; **todas** las rutas
    de escritura (`POST`, `PUT`, `DELETE`, subir/eliminar imagen, definir/eliminar concepto)
    añaden explícitamente `requerirAdmin`; sólo listar (`GET /`) y ver detalle (`GET /:id`)
    quedan abiertas a cualquier usuario con sesión, que es el comportamiento esperado (RF-04).
  - `routes/catalogoRoutes.js` (fábrica reusada por formatos/géneros/autores/conceptos): listar
    requiere sólo sesión; crear/editar/eliminar requieren `requerirSesion` **y** `requerirAdmin`
    explícitamente en cada ruta.
  - `middlewares/auth.js`, función `requerirAdmin`: rechaza con `403` si no hay sesión **o** si
    `req.session.usuario.rol !== 'admin'` — no hay ninguna ruta de escape (por ejemplo, no confía
    en ningún dato proveniente del cliente como un header o query param para decidir el rol; lee
    únicamente `req.session.usuario`, que sólo el propio servidor puede establecer en el login).
  - Conclusión de la auditoría: **no se encontró ninguna ruta administrativa sin protección** al
    31/08/2026. Esta verificación debe repetirse cada vez que se agregue una ruta nueva.

## D-10. Un solo Administrador, reforzado en dos capas (aplicación + base de datos)

- **Necesidad:** el ejercicio exige que exista como máximo un Administrador en todo momento.
- **Alternativas consideradas:** (a) validarlo únicamente en el controlador de registro
  (`if (hayAdmin) rol = 'cliente'`); (b) reforzarlo además con una restricción de base de datos.
- **Decisión tomada:** (b), las dos capas a la vez (defensa en profundidad).
- **Justificación técnica:** la validación en la aplicación es la primera línea de defensa y da
  una experiencia de usuario correcta (el registro nunca "falla" por esto en el flujo normal:
  simplemente el primer usuario es admin y el resto cliente). El índice único parcial en
  PostgreSQL (`uq_usuarios_admin_unico`) es la garantía real: incluso si alguien insertara un
  segundo admin saltándose la aplicación (acceso directo a la base, un bug futuro, una
  migración manual), PostgreSQL rechaza la operación.
- **Riesgo/limitación:** si el índice único se elimina accidentalmente en una migración futura,
  la única defensa que queda es la lógica de aplicación, que sí puede tener bugs; conviene un
  test automatizado que falle si el índice desaparece del esquema.
- **Evidencia de validación:** `data/library_schema.sql` línea 48,
  `CREATE UNIQUE INDEX uq_usuarios_admin_unico ...`; caso de prueba TC-15 en
  `docs/TEST_PLAN.md` (pendiente de ejecución formal, pero la restricción existe y es verificable
  por inspección directa del esquema).

## D-11. Imágenes en el sistema de archivos local, no en almacenamiento de objetos

- **Necesidad:** decidir dónde y cómo se guardan las imágenes de portada/galería de cada libro.
- **Alternativas consideradas:** (a) `multer` con `diskStorage` hacia `public/uploads/` en el
  mismo servidor; (b) subir a un bucket de Cloud Storage y guardar sólo la URL en PostgreSQL.
- **Decisión tomada:** (a).
- **Justificación técnica:** simplicidad para el alcance del ejercicio: no requiere credenciales
  de un servicio externo ni manejar subida asíncrona a un bucket; `multer` ya resuelve nombre de
  archivo generado por el sistema, validación de extensión/MIME y límite de tamaño (5 MB).
- **Riesgo/limitación:** las imágenes viven y mueren con la instancia (sin réplicas, sin CDN); si
  el disco se llena o la instancia se recrea sin migrar `public/uploads/`, se pierden todas las
  imágenes aunque los registros en PostgreSQL sigan intactos (referencia a un archivo que ya no
  existe).
- **Evidencia de validación:** `middlewares/upload.js` (filtro de extensión/MIME, límite de
  tamaño) y `controllers/libroController.js` (`urlPublica = /uploads/${req.file.filename}`,
  nunca el nombre original del archivo).

## D-12. Prefijo de despliegue configurable (`BASE_PATH`) para el reverse proxy `/library`

- Ver el detalle completo, ya documentado con este mismo esquema, en la sección "Decisiones de
  ingeniería" de `html/ejercicio02/index.html` (sección 12) y en el historial de esta sesión de
  trabajo con IA (`docs/AI_PROMPT_HISTORY.md`, pendiente de consolidar formalmente). Resumen:
  se introdujo una constante `BASE_PATH` (con `??` en vez de `||` para poder desactivarla en
  local sin perder la capacidad de fijarla vacía explícitamente) usada para montar rutas y
  estáticos, inyectar `res.locals.basePath` en las vistas, y prefijar cada `res.redirect()`.

## D-13. Reglas de negocio movidas de la función llamante a un trigger sobre la tabla

- **Necesidad:** la regla "máximo una portada por libro" ya estaba protegida por un índice único
  parcial (`uq_imagenes_portada_unica`), pero la *acción* de desmarcar la portada anterior al
  agregar una nueva sólo vivía como un `UPDATE` manual dentro de `fn_agregar_imagen`. Cualquier
  otra vía de escritura sobre `imagenes_libro` (una migración, un script de mantenimiento, una
  función nueva) se hubiera topado con el índice único como un simple error, sin el
  comportamiento de "rotar" la portada.
- **Alternativas consideradas:** (a) dejarlo como estaba, dependiendo de que toda escritura pase
  siempre por `fn_agregar_imagen`; (b) mover la lógica a un trigger `BEFORE INSERT OR UPDATE` en
  la propia tabla `imagenes_libro`.
- **Decisión tomada:** (b), `trg_una_portada_por_libro` (`data/library_triggers.sql`), y se
  simplificó `fn_agregar_imagen` quitándole el `UPDATE` manual que ahora sería lógica duplicada.
- **Justificación técnica:** la tabla es el lugar correcto para una invariante que depende sólo de
  sus propios datos (un builder externo no tiene por qué saber que existe esa regla); mantenerla
  en una sola función obliga a que **todo** código futuro recuerde llamar a esa función y no a
  otra.
- **Riesgo/limitación:** un trigger `BEFORE INSERT` que a su vez hace `UPDATE` sobre la misma
  tabla exige cuidado para no crear una recursión infinita — se resolvió con la guarda
  `IF NEW.es_portada THEN ...` (el `UPDATE` interno pone `es_portada = false`, por lo que la
  recursión se detiene sola en la siguiente invocación del trigger).
- **Evidencia de validación:** `docs/TEST_PLAN.md`, TC-22 — se insertó una segunda imagen con
  `es_portada=true` para el mismo libro y la primera se desmarcó sola, sin ningún cambio en el
  código de la aplicación (Node.js no se tocó para este caso).

## D-14. Consulta de catálogo centralizada en una vista de PostgreSQL

- **Necesidad:** `LibroModel.listarConDetalle` tenía, como texto SQL embebido en JavaScript, un
  `JOIN` de 5 tablas con `STRING_AGG` para autores/géneros y una subconsulta para la portada. Si
  otro punto de la aplicación (o un reporte futuro) necesitara la misma vista de "libro con
  detalle agregado", habría que copiar y mantener ese mismo SQL en dos lugares.
- **Alternativas consideradas:** (a) dejar la consulta como texto SQL dentro del modelo Node.js;
  (b) convertirla en una vista de PostgreSQL (`vista_catalogo_libros`) y que el modelo sólo
  filtre/ordene sobre ella.
- **Decisión tomada:** (b).
- **Justificación técnica:** la definición de "cómo se ve un libro con su detalle agregado" es
  responsabilidad del modelo de datos, no de una capa de aplicación específica; centralizarla en
  una vista evita que dos consultas del mismo dato diverjan con el tiempo, y deja que
  `LibroModel.listarConDetalle` sea una consulta trivial de una sola tabla (la vista) con un
  `WHERE` parametrizado para la búsqueda (RF-05).
- **Riesgo/limitación:** una vista con `GROUP BY`/agregaciones no es *updatable* directamente;
  eso ya era cierto de la consulta original (era de sólo lectura para el catálogo), así que no
  introduce una limitación nueva, pero hay que recordarlo si en el futuro se quisiera escribir a
  través de esta vista.
- **Evidencia de validación:** `docs/TEST_PLAN.md`, TC-27 — tras el cambio, `GET /library/libros`
  y `GET /library/libros?q=aleph` contra la app real siguen devolviendo exactamente los mismos
  resultados que antes de mover el `JOIN` a la vista.

## D-15. Bitácora de auditoría para cambios de rol de usuario

- **Necesidad:** la regla de "un solo Administrador" ya está protegida por un índice único
  parcial, pero no existía ningún registro de **cuándo** y **a quién** se le asignó o quitó el
  rol de admin — información relevante para cualquier revisión de seguridad posterior a un
  incidente.
- **Alternativas consideradas:** (a) no llevar bitácora (el estado actual siempre se puede leer
  de `usuarios.rol`); (b) tabla `usuarios_auditoria_rol` llenada por un trigger `AFTER UPDATE`.
- **Decisión tomada:** (b), `trg_usuarios_auditoria_rol` (`data/library_triggers.sql`).
- **Justificación técnica:** un trigger `AFTER UPDATE` con la guarda
  `NEW.rol IS DISTINCT FROM OLD.rol` garantiza que se registre el cambio sin importar qué
  función/ruta de la aplicación lo haya provocado, y sin que la aplicación tenga que acordarse de
  escribir el log manualmente en cada lugar donde se cambia un rol.
- **Riesgo/limitación:** la bitácora crece indefinidamente (no hay política de retención/purga);
  para el alcance de este ejercicio no es un problema, pero en producción real convendría
  archivar registros antiguos.
- **Evidencia de validación:** `docs/TEST_PLAN.md`, TC-24 — se degradó al admin existente y se
  ascendió a otro usuario; ambos cambios quedaron en `usuarios_auditoria_rol` con rol anterior,
  rol nuevo y fecha real.

## D-16. "Categoría" no se modela como catálogo independiente

- **Necesidad:** el enunciado del ejercicio menciona "CRUD de libros, autores, géneros, formatos,
  categorías y conceptos", pero el modelo de datos sólo tiene `formatos`, `generos`, `autores` y
  `conceptos` — no existe una tabla `categorias` separada.
- **Alternativas consideradas:** (a) agregar una quinta tabla `categorias` independiente, sin que
  quede claro en qué se diferenciaría de `generos` para una librería; (b) tratar "categoría" como
  sinónimo de "género" en este dominio (es la lectura más natural: "categoría de un libro" y
  "género de un libro" describen la misma clasificación temática).
- **Decisión tomada:** (b). No se agrega una tabla `categorias` adicional.
- **Justificación técnica:** agregar una tabla que sea funcionalmente idéntica a `generos` (mismo
  CRUD, misma forma, sin una regla de negocio que las distinga) sería redundancia de esquema sin
  beneficio real — la propia normalización 4FN (`docs/NORMALIZATION_4FN.md`) ya identifica
  `generos` como el catálogo que resuelve esa dependencia multivaluada del libro.
- **Riesgo/limitación:** si en una iteración futura "categoría" debiera representar algo distinto
  de "género" (por ejemplo, una clasificación por edad de lector o por área temática amplia
  —Ficción/No ficción— independiente del género literario), sí haría falta una tabla nueva; hoy
  no hay ese requisito explícito más allá del enunciado general.
- **Evidencia de validación:** `data/library_schema.sql`/`db/01_schema.sql` — catálogos existentes
  (`formatos`, `generos`, `autores`, `conceptos`) cubren el 100% del CRUD de catálogos usado por la
  aplicación real (`routes/index.js`, 4 registros de `crearCatalogoRoutes`).

## D-17. Texto alternativo de imágenes (accesibilidad)

- **Necesidad:** el ejercicio pide "administrar texto alternativo" para las imágenes de un libro;
  el esquema original sólo guardaba `url_imagen`, `orden` y `es_portada`.
- **Alternativas consideradas:** (a) dejarlo fuera de alcance, usando siempre un `alt` genérico
  generado en la vista ("Imagen de <título>"); (b) agregar una columna `texto_alternativo` y
  permitir que el administrador la capture al subir la imagen.
- **Decisión tomada:** (b).
- **Justificación técnica:** un `alt` genérico por libro no describe el *contenido* de cada imagen
  individual (portada vs. contraportada vs. ilustración interior); permitir texto por imagen es lo
  que realmente sirve a un lector de pantalla. Se mantiene compatibilidad hacia atrás:
  `fn_agregar_imagen` agrega `p_alt` como último parámetro con `DEFAULT ''`, así que las llamadas
  existentes (el seed original, con 4 argumentos) siguen funcionando sin cambios.
- **Riesgo/limitación:** el texto alternativo es opcional (columna `NOT NULL DEFAULT ''`, no
  obligatoria en el formulario); si el administrador no lo llena, la vista cae de vuelta al `alt`
  genérico — no hay validación que obligue a describir la imagen.
- **Evidencia de validación:** `docs/TEST_PLAN.md`, TC-30 — se subió una imagen con texto
  alternativo real y se confirmó que aparece tal cual en el HTML (`<img alt="...">`), tanto en el
  detalle del libro como en la miniatura del catálogo (`vista_catalogo_libros.portada_alt`).

## D-18. Seed ampliado a 30 filas por tabla, excepto `formatos`

- **Necesidad:** el ejercicio pide un seed de al menos 30 filas por tabla
  (`db/02_seed_30_per_table.sql`); el seed original tenía 3-7 filas por tabla.
- **Alternativas consideradas:** (a) forzar exactamente 30 filas en absolutamente todas las
  tablas, incluyendo `formatos`; (b) ampliar a 30 las tablas donde existen realmente esa cantidad
  de valores distintos con sentido de dominio (`usuarios`, `autores`, `generos`, `conceptos`,
  `libros`), y dejar `formatos` con un número realista y documentar por qué.
- **Decisión tomada:** (b). `formatos` se amplió de 3 a 8 (Tapa dura, Tapa blanda, Digital ePub,
  Audiolibro, Pasta dura de colección, Bolsillo, Digital PDF, Cómic/Novela gráfica); las demás
  tablas llegaron a 30.
- **Justificación técnica:** no existen 30 formatos de libro distintos en el mundo real; llenar la
  tabla hasta 30 con nombres como "Formato 9", "Formato 10"... habría sido información de relleno
  sin significado de dominio, lo opuesto a lo que un seed de prueba debe demostrar.
- **Riesgo/limitación:** si un revisor cuenta filas literalmente sin leer la justificación, podría
  marcar `formatos` como incompleto — por eso la decisión queda documentada tanto aquí como en el
  encabezado del propio `db/02_seed_30_per_table.sql`.
- **Evidencia de validación:** conteo real ejecutado contra una base de datos recién cargada con
  `db/00...06` en orden: `usuarios=30, autores=30, generos=30, conceptos=30, libros=30,
  formatos=8, libro_autor=30, libro_genero=51, imagenes_libro=30`.
