# Changelog de cambios asistidos por IA

Formato: fecha — resumen — archivos — referencia al detalle completo.

## 2026-08-31

- **BASE_PATH configurable para reverse proxy `/library`.** La app estaba montada en `"/"`; se
  agregó `BASE_PATH` (con fallback) para montar rutas/estáticos, inyectar `res.locals.basePath` y
  prefijar cada `res.redirect()`, más el ajuste de las 26 vistas EJS con rutas absolutas. Archivos:
  `app.js`, `routes/index.js`, `middlewares/auth.js`, 4 controladores, 26 vistas. Detalle: sección
  10 de `html/ejercicio02/index.html`.
- **Corrección de manejo de error en subida de imágenes (TC-12b) e implementación de búsqueda por
  ISBN/título (RF-05).** `middlewares/upload.js`, `routes/libros.js`, `models/libroModel.js`,
  `controllers/libroController.js`, `views/libros/catalogo.ejs`, `views/libros/detalle.ejs`.
  Detalle: `docs/TEST_PLAN.md`.
- **Triggers y vistas de PostgreSQL agregados** (`trg_una_portada_por_libro`,
  `trg_libros_fecha_actualizacion`, `trg_usuarios_auditoria_rol`, `vista_catalogo_libros`,
  `vista_administradores`, `vista_libros_stock_bajo`). Archivos: `data/library_schema.sql`,
  `data/library_triggers.sql` (nuevo), `data/library_views.sql` (nuevo),
  `models/libroModel.js`. Detalle: `docs/ENGINEERING_DECISIONS.md` (D-13, D-14, D-15).
- **Mostrar `mensajeError` en vistas donde se guardaba pero nunca se leía** (`usuarios/listar.ejs`
  y las 4 vistas `listar.ejs` de catálogos genéricos). Archivos:
  `controllers/usuarioController.js`, `controllers/catalogoController.js`,
  `views/usuarios/listar.ejs`, `views/formatos/listar.ejs`, `views/generos/listar.ejs`,
  `views/autores/listar.ejs`, `views/conceptos/listar.ejs`. Detalle:
  `docs/AI_PROMPT_HISTORY.md`, Entrada 1 — cambio pequeño y verificable ejecutado siguiendo
  `docs/PROMPT_MAESTRO_IA.md` para la Tarea 2e.
- **Bug reportado por la estudiante (probando la app real): columna ID vacía en el listado de
  Autores**, con los links de "Editar"/"Eliminar" apuntando a `/autores/undefined/...`. Causa:
  `catalogoController.js` calcula el nombre de columna de id como
  `` `id_${vista.slice(0, -1)}` `` (quita una sola letra final), lo cual funciona para
  `formatos→formato`, `generos→genero`, `conceptos→concepto`, pero **no** para `autores→autor`
  (plural irregular en español: "autor" + "es", no "autor" + "s" — el resultado era `id_autore`,
  no `id_autor`). Fix: pasar el `idCampo` explícito (`'id_autor'`) al registrar el catálogo de
  autores en `routes/index.js`, en vez de depender del cálculo automático. Archivo modificado:
  `routes/index.js`. Verificado con `curl` contra la app real: la columna ID ya muestra los
  valores reales y los links de editar apuntan a un id numérico, no a `undefined`.
- **Documentación ampliada de `docs/GCP_COMMANDS.md`**: se agregó la sección "7.1" con los 3
  problemas reales resueltos durante el primer despliegue (conflicto de `git pull` con
  `node_modules`, permisos `EACCES` por dueño incorrecto, y `bcrypt` con binario incompatible),
  con los comandos exactos usados en cada caso — reconstruidos revisando la propia conversación
  de depuración, no inventados.

## 2026-09-01

- **Configuración real de NGINX documentada** (`docs/GCP_COMMANDS.md`, sección 7.1): la
  estudiante compartió el `server{}`/`location{}` real usado en el servidor; se corrigió la
  suposición anterior de que el reverse proxy era Apache.
- **Diagramas generados como imágenes estáticas reales** (no sólo Mermaid embebido): se
  renderizaron `docs/ARCHITECTURE_MONOLITHIC.png` y `docs/DB_DESIGN_ER_4FN.png` con
  `@mermaid-js/mermaid-cli` a partir de la arquitectura y el esquema reales del proyecto.
- **Texto alternativo de imágenes implementado** (D-17): columna `texto_alternativo` en
  `imagenes_libro`, parámetro nuevo en `fn_agregar_imagen` (compatible hacia atrás con
  `DEFAULT ''`), campo en el formulario de subida, y uso en el `alt` del detalle de libro y de la
  miniatura del catálogo (`vista_catalogo_libros.portada_alt`). Archivos:
  `data/library_schema.sql`, `data/library_views.sql`, `models/libroModel.js`,
  `controllers/libroController.js`, `views/libros/detalle.ejs`, `views/libros/catalogo.ejs`.
  Verificado con una subida real vía `curl` (TC-30).
- **Seed ampliado a 30 filas por tabla** (D-18): `usuarios`, `autores`, `generos`, `conceptos` y
  `libros` llegan a 30; `formatos` se dejó en 8 por decisión documentada (no existen 30 formatos
  de libro reales distintos). Archivo: `data/library_data.sql`. Verificado recargando toda la
  base de datos desde cero y contando filas por tabla.
- **Scripts reorganizados al esquema `db/00...06`** que pide el ejercicio (antes eran
  `data/library_*.sql` sueltos): `00_create_database.sql`, `01_schema.sql`,
  `02_seed_30_per_table.sql`, `03_all_queries_before_stored_procedures.sql` (consultas de
  referencia, con nota explícita de que el proyecto no tuvo una etapa previa real sin funciones),
  `04_stored_procedures.sql`, `05_triggers.sql`, `06_views.sql`. Verificado cargando los 7 en
  orden contra una base de datos nueva.
- **Bug de "categoría"**: se documentó como decisión de diseño (D-16) que "categoría" se cubre
  con el catálogo `generos` existente, en vez de dejarlo como pregunta abierta.
- **Entrega empaquetada**: `apps/web-monolito01/.env.example` (nombres de variables reales del
  código, sin valores) y `descargas/ejercicio02.tar.gz` (668 KB), verificado sin `.env` real ni
  `node_modules` dentro.
- **Corregido un bug real de presentación en el propio reporte**: las etiquetas de estado
  (listo/parcial/pendiente) del índice de `html/ejercicio02/index.html` habían perdido su texto
  visible (`<span class="indice-estado listo"></span>`, vacío) en algún punto de ediciones
  anteriores; se restauraron con el estado real y actualizado de cada sección.
