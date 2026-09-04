-- =====================================================================
-- 03. CONSULTAS EQUIVALENTES SIN FUNCIONES PL/pgSQL — Libreria en linea
-- =====================================================================
-- Nota de honestidad tecnica: este proyecto se diseno desde el inicio
-- para que TODA la logica de acceso a datos viviera en funciones
-- PL/pgSQL (ver docs/ENGINEERING_DECISIONS.md, decision D-02), no hubo
-- una etapa previa real de "consultas sueltas" que despues se hayan
-- convertido en procedimientos almacenados.
--
-- Este archivo existe para cumplir el punto del ejercicio que pide un
-- script "antes de los stored procedures": documenta, a manera de
-- referencia y comparacion, el SQL equivalente en crudo (sin la
-- envoltura de fn_*) para las operaciones mas representativas de cada
-- dominio. No se ejecutan contra la base de datos real del proyecto
-- (la aplicacion siempre usa las funciones de 04_stored_procedures.sql);
-- sirven para que quede explicito que la funcion no oculta nada
-- estructuralmente distinto de una consulta parametrizada normal.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Autenticacion: buscar usuario por correo (equivalente de
-- fn_obtener_usuario_por_correo, usado por AuthController.iniciarSesion)
-- ---------------------------------------------------------------------
SELECT id_usuario, nombre_usuario, correo, contrasena_hash, rol
FROM usuarios
WHERE correo = $1;

-- ---------------------------------------------------------------------
-- Registro de usuario (equivalente de fn_crear_usuario)
-- ---------------------------------------------------------------------
INSERT INTO usuarios (nombre_usuario, correo, contrasena_hash, rol)
VALUES ($1, $2, $3, $4)
RETURNING id_usuario;

-- ---------------------------------------------------------------------
-- CRUD de libros (equivalente de fn_crear_libro / fn_actualizar_libro /
-- fn_eliminar_libro / fn_obtener_libro)
-- ---------------------------------------------------------------------
INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, id_formato)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id_libro;

UPDATE libros
   SET titulo = $2, anio_publicacion = $3, precio = $4, stock = $5, id_formato = $6
 WHERE id_libro = $1;

DELETE FROM libros WHERE id_libro = $1;

SELECT * FROM libros WHERE id_libro = $1;

-- ---------------------------------------------------------------------
-- Catalogo con detalle (equivalente de lo que hoy resuelve la vista
-- vista_catalogo_libros, ver 06_views.sql)
-- ---------------------------------------------------------------------
SELECT l.*, f.nombre_formato,
       COALESCE(STRING_AGG(DISTINCT a.nombre_autor, ', '), '') AS autores,
       COALESCE(STRING_AGG(DISTINCT g.nombre_genero, ', '), '') AS generos
FROM libros l
JOIN formatos f ON f.id_formato = l.id_formato
LEFT JOIN libro_autor la ON la.id_libro = l.id_libro
LEFT JOIN autores a ON a.id_autor = la.id_autor
LEFT JOIN libro_genero lg ON lg.id_libro = l.id_libro
LEFT JOIN generos g ON g.id_genero = lg.id_genero
WHERE $1::text IS NULL OR l.isbn = $1 OR l.titulo ILIKE '%' || $1 || '%'
GROUP BY l.id_libro, f.nombre_formato
ORDER BY l.titulo;

-- ---------------------------------------------------------------------
-- Relacion libro-autor (equivalente de fn_asociar_autor)
-- ---------------------------------------------------------------------
INSERT INTO libro_autor (id_libro, id_autor)
VALUES ($1, $2)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Un solo Administrador: la misma consulta que protege el indice unico
-- parcial uq_usuarios_admin_unico (ver 01_schema.sql)
-- ---------------------------------------------------------------------
SELECT count(*) FROM usuarios WHERE rol = 'admin';
