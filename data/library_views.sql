-- =====================================================================
-- VISTAS: Libreria en linea
-- =====================================================================
-- Requisito: haber cargado antes library_schema.sql.
--
--   1) vista_catalogo_libros -> antes esta consulta (JOIN + STRING_AGG de
--      autores/generos + subconsulta de portada) vivia duplicada como texto
--      SQL dentro de models/libroModel.js. Convertirla en vista centraliza
--      la definicion en un solo lugar (la base de datos) y permite que la
--      aplicacion solo filtre/ordene sobre ella (ver LibroModel.listarConDetalle).
--
--   2) vista_administradores -> util para auditar rapido, en cualquier
--      momento, quien tiene hoy el rol de Administrador (complementa la
--      bitacora historica de usuarios_auditoria_rol).
--
--   3) vista_libros_stock_bajo -> reporte de inventario (RF de control de
--      stock): libros con 5 unidades o menos, para reabastecer.
-- =====================================================================

CREATE OR REPLACE VIEW vista_catalogo_libros AS
SELECT
    l.id_libro, l.isbn, l.titulo, l.anio_publicacion, l.precio, l.stock,
    l.id_formato, l.fecha_creacion, l.fecha_actualizacion,
    f.nombre_formato,
    COALESCE(STRING_AGG(DISTINCT a.nombre_autor, ', '), '') AS autores,
    COALESCE(STRING_AGG(DISTINCT g.nombre_genero, ', '), '') AS generos,
    (SELECT il.url_imagen FROM imagenes_libro il
       WHERE il.id_libro = l.id_libro AND il.es_portada = true LIMIT 1) AS portada,
    (SELECT il.texto_alternativo FROM imagenes_libro il
       WHERE il.id_libro = l.id_libro AND il.es_portada = true LIMIT 1) AS portada_alt
FROM libros l
JOIN formatos f ON f.id_formato = l.id_formato
LEFT JOIN libro_autor la ON la.id_libro = l.id_libro
LEFT JOIN autores a ON a.id_autor = la.id_autor
LEFT JOIN libro_genero lg ON lg.id_libro = l.id_libro
LEFT JOIN generos g ON g.id_genero = lg.id_genero
GROUP BY l.id_libro, f.nombre_formato;

CREATE OR REPLACE VIEW vista_administradores AS
SELECT id_usuario, nombre_usuario, correo, fecha_registro
FROM usuarios
WHERE rol = 'admin';

CREATE OR REPLACE VIEW vista_libros_stock_bajo AS
SELECT id_libro, isbn, titulo, stock
FROM libros
WHERE stock <= 5
ORDER BY stock ASC;
