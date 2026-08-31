-- =====================================================================
-- DATOS DE PRUEBA: Libreria en linea
-- =====================================================================
-- Requisitos:
--   1) Haber cargado antes data/library_schema.sql (tablas + funciones).
--   2) Ejecutar sobre una base de datos "library" recien creada/vacia,
--      ya que este script asume que los SERIAL empiezan en 1 (no
--      referencia filas por nombre sino por el id devuelto por las
--      funciones fn_*, que a su vez dependen del orden de insercion).
--
-- Uso:
--   PGPASSWORD=666 psql -h localhost -U library_user -d library \
--     -f data/library_data.sql
--
-- Todo el llenado usa las MISMAS funciones PL/pgSQL que usa la
-- aplicacion (fn_crear_*, fn_asociar_*, fn_definir_concepto,
-- fn_agregar_imagen), para no saltarse la logica de negocio.
-- =====================================================================

BEGIN;

-- pgcrypto se usa solo para generar un hash bcrypt valido para las
-- contrasenas de prueba (compatible con bcrypt.compare() en Node).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------
-- 1. USUARIOS
-- ---------------------------------------------------------------------
-- Contrasena de TODOS los usuarios de prueba: "123456"
-- El primero creado con rol 'admin' respeta la regla de un solo admin.

SELECT fn_crear_usuario(
    'admin_paola',
    'admin@libreria.test',
    crypt('123456', gen_salt('bf')),
    'admin'
);

SELECT fn_crear_usuario(
    'juan_perez',
    'juan.perez@correo.test',
    crypt('123456', gen_salt('bf')),
    'cliente'
);

SELECT fn_crear_usuario(
    'maria_lopez',
    'maria.lopez@correo.test',
    crypt('123456', gen_salt('bf')),
    'cliente'
);

-- ---------------------------------------------------------------------
-- 2. CATALOGOS: formatos, generos, autores, conceptos
-- ---------------------------------------------------------------------

-- formatos -> id_formato: 1 Tapa dura, 2 Tapa blanda, 3 Digital (ePub)
SELECT fn_crear_formato('Tapa dura');
SELECT fn_crear_formato('Tapa blanda');
SELECT fn_crear_formato('Digital (ePub)');

-- generos -> id_genero: 1..6
SELECT fn_crear_genero('Realismo magico');
SELECT fn_crear_genero('Ciencia ficcion');
SELECT fn_crear_genero('Fantasia');
SELECT fn_crear_genero('Distopia');
SELECT fn_crear_genero('Novela historica');
SELECT fn_crear_genero('Ensayo');

-- autores -> id_autor: 1..7
SELECT fn_crear_autor('Gabriel Garcia Marquez');
SELECT fn_crear_autor('Jorge Luis Borges');
SELECT fn_crear_autor('Isabel Allende');
SELECT fn_crear_autor('George Orwell');
SELECT fn_crear_autor('Aldous Huxley');
SELECT fn_crear_autor('J.R.R. Tolkien');
SELECT fn_crear_autor('Mary Shelley');

-- conceptos -> id_concepto: 1..5
SELECT fn_crear_concepto('Realismo magico (recurso literario)');
SELECT fn_crear_concepto('Distopia');
SELECT fn_crear_concepto('Narrador no fiable');
SELECT fn_crear_concepto('Alegoria politica');
SELECT fn_crear_concepto('Mundo secundario (worldbuilding)');

-- ---------------------------------------------------------------------
-- 3. LIBROS
-- ---------------------------------------------------------------------
-- id_libro 1: Cien anios de soledad
SELECT fn_crear_libro('9780307474728', 'Cien anios de soledad', 1967::SMALLINT, 299.99, 12, 1);
-- id_libro 2: El aleph
SELECT fn_crear_libro('9788420633343', 'El aleph', 1949::SMALLINT, 189.50, 8, 2);
-- id_libro 3: La casa de los espiritus
SELECT fn_crear_libro('9788401352836', 'La casa de los espiritus', 1982::SMALLINT, 249.00, 10, 2);
-- id_libro 4: 1984
SELECT fn_crear_libro('9780451524935', '1984', 1949::SMALLINT, 179.90, 20, 2);
-- id_libro 5: Un mundo feliz
SELECT fn_crear_libro('9780060850524', 'Un mundo feliz', 1932::SMALLINT, 169.90, 15, 3);
-- id_libro 6: El senor de los anillos
SELECT fn_crear_libro('9780618640157', 'El senor de los anillos', 1954::SMALLINT, 399.00, 6, 1);
-- id_libro 7: Frankenstein
SELECT fn_crear_libro('9780141439471', 'Frankenstein', 1818::SMALLINT, 149.00, 9, 3);

-- ---------------------------------------------------------------------
-- 4. RELACIONES libro <-> autor  (N:M)
-- ---------------------------------------------------------------------
SELECT fn_asociar_autor(1, 1); -- Cien anios de soledad - Garcia Marquez
SELECT fn_asociar_autor(2, 2); -- El aleph - Borges
SELECT fn_asociar_autor(3, 3); -- La casa de los espiritus - Allende
SELECT fn_asociar_autor(4, 4); -- 1984 - Orwell
SELECT fn_asociar_autor(5, 5); -- Un mundo feliz - Huxley
SELECT fn_asociar_autor(6, 6); -- El senor de los anillos - Tolkien
SELECT fn_asociar_autor(7, 7); -- Frankenstein - Mary Shelley

-- ---------------------------------------------------------------------
-- 5. RELACIONES libro <-> genero  (N:M)
-- ---------------------------------------------------------------------
SELECT fn_asociar_genero(1, 1); -- Cien anios de soledad - Realismo magico
SELECT fn_asociar_genero(2, 1); -- El aleph - Realismo magico
SELECT fn_asociar_genero(2, 3); -- El aleph - Fantasia
SELECT fn_asociar_genero(3, 1); -- La casa de los espiritus - Realismo magico
SELECT fn_asociar_genero(3, 5); -- La casa de los espiritus - Novela historica
SELECT fn_asociar_genero(4, 2); -- 1984 - Ciencia ficcion
SELECT fn_asociar_genero(4, 4); -- 1984 - Distopia
SELECT fn_asociar_genero(5, 2); -- Un mundo feliz - Ciencia ficcion
SELECT fn_asociar_genero(5, 4); -- Un mundo feliz - Distopia
SELECT fn_asociar_genero(6, 3); -- El senor de los anillos - Fantasia
SELECT fn_asociar_genero(7, 2); -- Frankenstein - Ciencia ficcion
SELECT fn_asociar_genero(7, 3); -- Frankenstein - Fantasia

-- ---------------------------------------------------------------------
-- 6. CONCEPTOS DEFINIDOS POR LIBRO (definicion propia del par libro-concepto)
-- ---------------------------------------------------------------------
SELECT fn_definir_concepto(1, 1,
  'En esta novela lo sobrenatural (lluvias de flores, ascensiones al cielo) se narra con el mismo tono que los hechos cotidianos de la familia Buendia.');
SELECT fn_definir_concepto(2, 1,
  'Borges mezcla objetos imposibles (el Aleph, que contiene todos los puntos del universo) con la vida cotidiana de Buenos Aires.');
SELECT fn_definir_concepto(4, 2,
  'Oceania es un estado totalitario que vigila y controla el pensamiento de sus ciudadanos mediante el Gran Hermano y la Policia del Pensamiento.');
SELECT fn_definir_concepto(4, 4,
  'La novela funciona como critica al totalitarismo del siglo XX (estalinismo, fascismo) a traves de la ficcion de Oceania.');
SELECT fn_definir_concepto(5, 2,
  'El Estado Mundial de Huxley controla a la poblacion mediante placer, condicionamiento genetico y la droga soma, en vez de represion directa.');
SELECT fn_definir_concepto(6, 5,
  'La Tierra Media es un mundo ficticio completo con su propia geografia, idiomas, pueblos e historia, construido por Tolkien a lo largo de decadas.');
SELECT fn_definir_concepto(7, 3,
  'La historia se presenta a traves de cartas y el propio relato de Victor Frankenstein, cuya version de los hechos el lector debe poner en duda.');

-- ---------------------------------------------------------------------
-- 7. IMAGENES POR LIBRO (una portada por libro + una imagen adicional)
-- ---------------------------------------------------------------------
-- Nota: estas URLs son de ejemplo. En uso real, las imagenes se suben
-- desde la vista de detalle del libro (multer) y quedan en
-- /uploads/<archivo>. Aqui se referencian URLs externas solo para
-- tener datos de muestra visibles sin subir archivos manualmente.
SELECT fn_agregar_imagen(1, 'https://covers.openlibrary.org/b/isbn/9780307474728-L.jpg', 0::SMALLINT, true);
SELECT fn_agregar_imagen(2, 'https://covers.openlibrary.org/b/isbn/9788420633343-L.jpg', 0::SMALLINT, true);
SELECT fn_agregar_imagen(3, 'https://covers.openlibrary.org/b/isbn/9788401352836-L.jpg', 0::SMALLINT, true);
SELECT fn_agregar_imagen(4, 'https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg', 0::SMALLINT, true);
SELECT fn_agregar_imagen(5, 'https://covers.openlibrary.org/b/isbn/9780060850524-L.jpg', 0::SMALLINT, true);
SELECT fn_agregar_imagen(6, 'https://covers.openlibrary.org/b/isbn/9780618640157-L.jpg', 0::SMALLINT, true);
SELECT fn_agregar_imagen(7, 'https://covers.openlibrary.org/b/isbn/9780141439471-L.jpg', 0::SMALLINT, true);

COMMIT;

-- ---------------------------------------------------------------------
-- Verificacion rapida (opcional, solo lectura)
-- ---------------------------------------------------------------------
-- SELECT nombre_usuario, rol FROM usuarios;
-- SELECT titulo, precio, stock FROM libros ORDER BY titulo;
-- SELECT l.titulo, a.nombre_autor FROM libros l
--   JOIN libro_autor la ON la.id_libro = l.id_libro
--   JOIN autores a ON a.id_autor = la.id_autor ORDER BY l.titulo;