-- =====================================================================
-- 02. DATOS DE PRUEBA (SEED) — Libreria en linea
-- =====================================================================
-- Requisitos: haber cargado antes, en orden, 00_create_database.sql,
-- 01_schema.sql, 04_stored_procedures.sql, 05_triggers.sql y
-- 06_views.sql. Ejecutar sobre una base de datos "library" recien
-- creada/vacia (asume que los SERIAL empiezan en 1).
--
-- Uso:
--   PGPASSWORD=666 psql -h localhost -U library_user -d library \
--     -f db/02_seed_30_per_table.sql
--
-- Todo el llenado usa las MISMAS funciones PL/pgSQL que usa la
-- aplicacion (fn_crear_*, fn_asociar_*, fn_definir_concepto,
-- fn_agregar_imagen), para no saltarse la logica de negocio.
--
-- Filas por tabla: usuarios 30, autores 30, generos 30, conceptos 30,
-- libros 30. formatos se queda en 8 (decision documentada en
-- docs/ENGINEERING_DECISIONS.md): no existen 30 formatos de libro
-- reales distintos, forzar ese numero produciria relleno sin sentido
-- de dominio.
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

-- =====================================================================
-- AMPLIACION DEL SEED A ~30 FILAS POR TABLA (agregado 2026-09-01)
-- =====================================================================
-- No se modifico nada de lo que ya existia arriba (usuarios 1-3, formatos
-- 1-3, generos 1-6, autores 1-7, conceptos 1-5, libros 1-7 y sus relaciones)
-- para no invalidar evidencia/capturas ya tomadas contra esos IDs.
--
-- 'formatos' se amplia a 8 (no a 30): a diferencia de autores/generos/
-- conceptos/libros, no existen realmente 30 formatos distintos de libro;
-- forzar 30 aqui produciria filas de relleno sin sentido de dominio
-- (ver docs/ENGINEERING_DECISIONS.md, decision sobre el seed).
-- =====================================================================

-- ---------------------------------------------------------------------
-- USUARIOS (4..30, todos rol 'cliente': ya existe el admin unico)
-- ---------------------------------------------------------------------
SELECT fn_crear_usuario('carlos_ramirez', 'carlos.ramirez@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('sofia_torres', 'sofia.torres@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('diego_martinez', 'diego.martinez@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('valentina_cruz', 'valentina.cruz@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('andres_flores', 'andres.flores@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('camila_ortiz', 'camila.ortiz@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('luis_mendoza', 'luis.mendoza@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('daniela_reyes', 'daniela.reyes@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('javier_castillo', 'javier.castillo@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('paula_vargas', 'paula.vargas@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('ricardo_soto', 'ricardo.soto@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('fernanda_rojas', 'fernanda.rojas@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('miguel_navarro', 'miguel.navarro@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('laura_dominguez', 'laura.dominguez@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('eduardo_silva', 'eduardo.silva@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('gabriela_paredes', 'gabriela.paredes@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('alejandro_ibarra', 'alejandro.ibarra@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('monica_delgado', 'monica.delgado@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('roberto_aguilar', 'roberto.aguilar@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('patricia_nunez', 'patricia.nunez@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('sergio_campos', 'sergio.campos@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('veronica_luna', 'veronica.luna@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('hector_fuentes', 'hector.fuentes@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('adriana_marin', 'adriana.marin@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('oscar_bravo', 'oscar.bravo@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('karla_espinoza', 'karla.espinoza@correo.test', crypt('123456', gen_salt('bf')), 'cliente');
SELECT fn_crear_usuario('felipe_guerrero', 'felipe.guerrero@correo.test', crypt('123456', gen_salt('bf')), 'cliente');

-- ---------------------------------------------------------------------
-- FORMATOS (4..8)
-- ---------------------------------------------------------------------
SELECT fn_crear_formato('Audiolibro');
SELECT fn_crear_formato('Pasta dura de coleccion');
SELECT fn_crear_formato('Bolsillo');
SELECT fn_crear_formato('Digital (PDF)');
SELECT fn_crear_formato('Comic / Novela grafica');

-- ---------------------------------------------------------------------
-- GENEROS (7..30)
-- ---------------------------------------------------------------------
SELECT fn_crear_genero('Terror');
SELECT fn_crear_genero('Misterio');
SELECT fn_crear_genero('Policial');
SELECT fn_crear_genero('Romance');
SELECT fn_crear_genero('Aventura');
SELECT fn_crear_genero('Drama');
SELECT fn_crear_genero('Comedia');
SELECT fn_crear_genero('Poesia');
SELECT fn_crear_genero('Biografia');
SELECT fn_crear_genero('Autobiografia');
SELECT fn_crear_genero('Filosofia');
SELECT fn_crear_genero('Autoayuda');
SELECT fn_crear_genero('Infantil');
SELECT fn_crear_genero('Juvenil');
SELECT fn_crear_genero('Thriller');
SELECT fn_crear_genero('Suspenso');
SELECT fn_crear_genero('Western');
SELECT fn_crear_genero('Belico');
SELECT fn_crear_genero('Satira');
SELECT fn_crear_genero('Fabula');
SELECT fn_crear_genero('Mitologia');
SELECT fn_crear_genero('Divulgacion cientifica');
SELECT fn_crear_genero('Costumbrismo');
SELECT fn_crear_genero('Picaresca');

-- ---------------------------------------------------------------------
-- AUTORES (8..30)
-- ---------------------------------------------------------------------
SELECT fn_crear_autor('Mark Twain');
SELECT fn_crear_autor('Charles Dickens');
SELECT fn_crear_autor('Jane Austen');
SELECT fn_crear_autor('Fiodor Dostoyevski');
SELECT fn_crear_autor('Leon Tolstoi');
SELECT fn_crear_autor('Franz Kafka');
SELECT fn_crear_autor('Miguel de Cervantes');
SELECT fn_crear_autor('Homero');
SELECT fn_crear_autor('William Shakespeare');
SELECT fn_crear_autor('Emily Bronte');
SELECT fn_crear_autor('Victor Hugo');
SELECT fn_crear_autor('Edgar Allan Poe');
SELECT fn_crear_autor('H.G. Wells');
SELECT fn_crear_autor('Julio Verne');
SELECT fn_crear_autor('Oscar Wilde');
SELECT fn_crear_autor('Herman Melville');
SELECT fn_crear_autor('Antoine de Saint-Exupery');
SELECT fn_crear_autor('Albert Camus');
SELECT fn_crear_autor('Ray Bradbury');
SELECT fn_crear_autor('Kurt Vonnegut');
SELECT fn_crear_autor('Truman Capote');
SELECT fn_crear_autor('Gustave Flaubert');
SELECT fn_crear_autor('Anton Chejov');

-- ---------------------------------------------------------------------
-- CONCEPTOS (6..30)
-- ---------------------------------------------------------------------
SELECT fn_crear_concepto('Metafora');
SELECT fn_crear_concepto('Simbolismo');
SELECT fn_crear_concepto('Ironia');
SELECT fn_crear_concepto('Foreshadowing (anticipacion narrativa)');
SELECT fn_crear_concepto('In medias res');
SELECT fn_crear_concepto('Flashback (analepsis)');
SELECT fn_crear_concepto('Monologo interior');
SELECT fn_crear_concepto('Realismo sucio');
SELECT fn_crear_concepto('Bildungsroman');
SELECT fn_crear_concepto('Antiheroe');
SELECT fn_crear_concepto('Satira social');
SELECT fn_crear_concepto('Literatura del absurdo');
SELECT fn_crear_concepto('Alegoria');
SELECT fn_crear_concepto('Novela epistolar');
SELECT fn_crear_concepto('Perspectiva multiple');
SELECT fn_crear_concepto('Metaficcion');
SELECT fn_crear_concepto('Intertextualidad');
SELECT fn_crear_concepto('Deus ex machina');
SELECT fn_crear_concepto('Climax narrativo');
SELECT fn_crear_concepto('Elipsis narrativa');
SELECT fn_crear_concepto('Prolepsis');
SELECT fn_crear_concepto('Voz narrativa');
SELECT fn_crear_concepto('Punto de vista');
SELECT fn_crear_concepto('Tragedia clasica');
SELECT fn_crear_concepto('Comedia de costumbres');

-- ---------------------------------------------------------------------
-- LIBROS (8..30) -- autor_idx/genero_idx abajo ya son los id reales
-- (7 originales + los nuevos creados arriba, en orden de insercion)
-- ---------------------------------------------------------------------
-- id_libro 8: Las aventuras de Huckleberry Finn
SELECT fn_crear_libro('9799000000011', 'Las aventuras de Huckleberry Finn', 1884::SMALLINT, 159.00, 14, 2);
-- id_libro 9: Grandes esperanzas
SELECT fn_crear_libro('9799000000012', 'Grandes esperanzas', 1861::SMALLINT, 219.00, 11, 1);
-- id_libro 10: Orgullo y prejuicio
SELECT fn_crear_libro('9799000000013', 'Orgullo y prejuicio', 1813::SMALLINT, 189.00, 18, 2);
-- id_libro 11: Crimen y castigo
SELECT fn_crear_libro('9799000000014', 'Crimen y castigo', 1866::SMALLINT, 229.00, 9, 1);
-- id_libro 12: Ana Karenina
SELECT fn_crear_libro('9799000000015', 'Ana Karenina', 1877::SMALLINT, 259.00, 7, 1);
-- id_libro 13: La metamorfosis
SELECT fn_crear_libro('9799000000016', 'La metamorfosis', 1915::SMALLINT, 139.00, 16, 2);
-- id_libro 14: Don Quijote de la Mancha
SELECT fn_crear_libro('9799000000017', 'Don Quijote de la Mancha', 1605::SMALLINT, 299.00, 13, 1);
-- id_libro 15: Hamlet
SELECT fn_crear_libro('9799000000018', 'Hamlet', 1601::SMALLINT, 179.00, 10, 2);
-- id_libro 16: Cumbres borrascosas
SELECT fn_crear_libro('9799000000019', 'Cumbres borrascosas', 1847::SMALLINT, 199.00, 8, 1);
-- id_libro 17: Los miserables
SELECT fn_crear_libro('9799000000020', 'Los miserables', 1862::SMALLINT, 289.00, 6, 1);
-- id_libro 18: Narraciones extraordinarias
SELECT fn_crear_libro('9799000000021', 'Narraciones extraordinarias', 1845::SMALLINT, 169.00, 12, 2);
-- id_libro 19: La guerra de los mundos
SELECT fn_crear_libro('9799000000022', 'La guerra de los mundos', 1898::SMALLINT, 179.90, 17, 3);
-- id_libro 20: Veinte mil leguas de viaje submarino
SELECT fn_crear_libro('9799000000023', 'Veinte mil leguas de viaje submarino', 1870::SMALLINT, 189.90, 15, 2);
-- id_libro 21: El retrato de Dorian Gray
SELECT fn_crear_libro('9799000000024', 'El retrato de Dorian Gray', 1890::SMALLINT, 209.00, 9, 1);
-- id_libro 22: Moby Dick
SELECT fn_crear_libro('9799000000025', 'Moby Dick', 1851::SMALLINT, 249.00, 5, 1);
-- id_libro 23: El principito
SELECT fn_crear_libro('9799000000026', 'El principito', 1943::SMALLINT, 129.00, 25, 2);
-- id_libro 24: El extranjero
SELECT fn_crear_libro('9799000000027', 'El extranjero', 1942::SMALLINT, 159.90, 10, 2);
-- id_libro 25: Cronicas marcianas
SELECT fn_crear_libro('9799000000028', 'Cronicas marcianas', 1950::SMALLINT, 169.90, 14, 3);
-- id_libro 26: Matadero Cinco
SELECT fn_crear_libro('9799000000029', 'Matadero Cinco', 1969::SMALLINT, 179.00, 8, 2);
-- id_libro 27: A sangre fria
SELECT fn_crear_libro('9799000000030', 'A sangre fria', 1966::SMALLINT, 199.00, 7, 1);
-- id_libro 28: Madame Bovary
SELECT fn_crear_libro('9799000000031', 'Madame Bovary', 1857::SMALLINT, 219.00, 6, 1);
-- id_libro 29: El jardin de los cerezos
SELECT fn_crear_libro('9799000000032', 'El jardin de los cerezos', 1904::SMALLINT, 129.00, 5, 2);
-- id_libro 30: Fahrenheit 451
SELECT fn_crear_libro('9799000000033', 'Fahrenheit 451', 1953::SMALLINT, 189.90, 19, 3);

-- ---------------------------------------------------------------------
-- RELACIONES libro <-> autor (8..30)
-- ---------------------------------------------------------------------
SELECT fn_asociar_autor(8, 8); -- Las aventuras de Huckleberry Finn
SELECT fn_asociar_autor(9, 9); -- Grandes esperanzas
SELECT fn_asociar_autor(10, 10); -- Orgullo y prejuicio
SELECT fn_asociar_autor(11, 11); -- Crimen y castigo
SELECT fn_asociar_autor(12, 12); -- Ana Karenina
SELECT fn_asociar_autor(13, 13); -- La metamorfosis
SELECT fn_asociar_autor(14, 14); -- Don Quijote de la Mancha
SELECT fn_asociar_autor(15, 16); -- Hamlet
SELECT fn_asociar_autor(16, 17); -- Cumbres borrascosas
SELECT fn_asociar_autor(17, 18); -- Los miserables
SELECT fn_asociar_autor(18, 19); -- Narraciones extraordinarias
SELECT fn_asociar_autor(19, 20); -- La guerra de los mundos
SELECT fn_asociar_autor(20, 21); -- Veinte mil leguas de viaje submarino
SELECT fn_asociar_autor(21, 22); -- El retrato de Dorian Gray
SELECT fn_asociar_autor(22, 23); -- Moby Dick
SELECT fn_asociar_autor(23, 24); -- El principito
SELECT fn_asociar_autor(24, 25); -- El extranjero
SELECT fn_asociar_autor(25, 26); -- Cronicas marcianas
SELECT fn_asociar_autor(26, 27); -- Matadero Cinco
SELECT fn_asociar_autor(27, 28); -- A sangre fria
SELECT fn_asociar_autor(28, 29); -- Madame Bovary
SELECT fn_asociar_autor(29, 30); -- El jardin de los cerezos
SELECT fn_asociar_autor(30, 26); -- Fahrenheit 451

-- ---------------------------------------------------------------------
-- RELACIONES libro <-> genero (8..30)
-- ---------------------------------------------------------------------
SELECT fn_asociar_genero(8, 5); -- Las aventuras de Huckleberry Finn
SELECT fn_asociar_genero(8, 19); -- Las aventuras de Huckleberry Finn
SELECT fn_asociar_genero(9, 6); -- Grandes esperanzas
SELECT fn_asociar_genero(9, 5); -- Grandes esperanzas
SELECT fn_asociar_genero(10, 10); -- Orgullo y prejuicio
SELECT fn_asociar_genero(10, 7); -- Orgullo y prejuicio
SELECT fn_asociar_genero(11, 6); -- Crimen y castigo
SELECT fn_asociar_genero(11, 9); -- Crimen y castigo
SELECT fn_asociar_genero(12, 6); -- Ana Karenina
SELECT fn_asociar_genero(12, 10); -- Ana Karenina
SELECT fn_asociar_genero(13, 6); -- La metamorfosis
SELECT fn_asociar_genero(14, 24); -- Don Quijote de la Mancha
SELECT fn_asociar_genero(14, 7); -- Don Quijote de la Mancha
SELECT fn_asociar_genero(15, 6); -- Hamlet
SELECT fn_asociar_genero(16, 10); -- Cumbres borrascosas
SELECT fn_asociar_genero(16, 6); -- Cumbres borrascosas
SELECT fn_asociar_genero(17, 5); -- Los miserables
SELECT fn_asociar_genero(17, 6); -- Los miserables
SELECT fn_asociar_genero(18, 1); -- Narraciones extraordinarias
SELECT fn_asociar_genero(18, 8); -- Narraciones extraordinarias
SELECT fn_asociar_genero(19, 2); -- La guerra de los mundos
SELECT fn_asociar_genero(20, 2); -- Veinte mil leguas de viaje submarino
SELECT fn_asociar_genero(20, 5); -- Veinte mil leguas de viaje submarino
SELECT fn_asociar_genero(21, 8); -- El retrato de Dorian Gray
SELECT fn_asociar_genero(22, 5); -- Moby Dick
SELECT fn_asociar_genero(22, 6); -- Moby Dick
SELECT fn_asociar_genero(23, 20); -- El principito
SELECT fn_asociar_genero(23, 13); -- El principito
SELECT fn_asociar_genero(24, 6); -- El extranjero
SELECT fn_asociar_genero(25, 2); -- Cronicas marcianas
SELECT fn_asociar_genero(26, 2); -- Matadero Cinco
SELECT fn_asociar_genero(26, 18); -- Matadero Cinco
SELECT fn_asociar_genero(27, 9); -- A sangre fria
SELECT fn_asociar_genero(27, 3); -- A sangre fria
SELECT fn_asociar_genero(28, 10); -- Madame Bovary
SELECT fn_asociar_genero(28, 6); -- Madame Bovary
SELECT fn_asociar_genero(29, 7); -- El jardin de los cerezos
SELECT fn_asociar_genero(30, 2); -- Fahrenheit 451
SELECT fn_asociar_genero(30, 4); -- Fahrenheit 451

-- ---------------------------------------------------------------------
-- IMAGENES (portada) PARA LOS LIBROS NUEVOS, CON TEXTO ALTERNATIVO
-- ---------------------------------------------------------------------
SELECT fn_agregar_imagen(8, 'https://covers.openlibrary.org/b/isbn/9799000000011-L.jpg', 0::SMALLINT, true, 'Portada de Las aventuras de Huckleberry Finn');
SELECT fn_agregar_imagen(9, 'https://covers.openlibrary.org/b/isbn/9799000000012-L.jpg', 0::SMALLINT, true, 'Portada de Grandes esperanzas');
SELECT fn_agregar_imagen(10, 'https://covers.openlibrary.org/b/isbn/9799000000013-L.jpg', 0::SMALLINT, true, 'Portada de Orgullo y prejuicio');
SELECT fn_agregar_imagen(11, 'https://covers.openlibrary.org/b/isbn/9799000000014-L.jpg', 0::SMALLINT, true, 'Portada de Crimen y castigo');
SELECT fn_agregar_imagen(12, 'https://covers.openlibrary.org/b/isbn/9799000000015-L.jpg', 0::SMALLINT, true, 'Portada de Ana Karenina');
SELECT fn_agregar_imagen(13, 'https://covers.openlibrary.org/b/isbn/9799000000016-L.jpg', 0::SMALLINT, true, 'Portada de La metamorfosis');
SELECT fn_agregar_imagen(14, 'https://covers.openlibrary.org/b/isbn/9799000000017-L.jpg', 0::SMALLINT, true, 'Portada de Don Quijote de la Mancha');
SELECT fn_agregar_imagen(15, 'https://covers.openlibrary.org/b/isbn/9799000000018-L.jpg', 0::SMALLINT, true, 'Portada de Hamlet');
SELECT fn_agregar_imagen(16, 'https://covers.openlibrary.org/b/isbn/9799000000019-L.jpg', 0::SMALLINT, true, 'Portada de Cumbres borrascosas');
SELECT fn_agregar_imagen(17, 'https://covers.openlibrary.org/b/isbn/9799000000020-L.jpg', 0::SMALLINT, true, 'Portada de Los miserables');
SELECT fn_agregar_imagen(18, 'https://covers.openlibrary.org/b/isbn/9799000000021-L.jpg', 0::SMALLINT, true, 'Portada de Narraciones extraordinarias');
SELECT fn_agregar_imagen(19, 'https://covers.openlibrary.org/b/isbn/9799000000022-L.jpg', 0::SMALLINT, true, 'Portada de La guerra de los mundos');
SELECT fn_agregar_imagen(20, 'https://covers.openlibrary.org/b/isbn/9799000000023-L.jpg', 0::SMALLINT, true, 'Portada de Veinte mil leguas de viaje submarino');
SELECT fn_agregar_imagen(21, 'https://covers.openlibrary.org/b/isbn/9799000000024-L.jpg', 0::SMALLINT, true, 'Portada de El retrato de Dorian Gray');
SELECT fn_agregar_imagen(22, 'https://covers.openlibrary.org/b/isbn/9799000000025-L.jpg', 0::SMALLINT, true, 'Portada de Moby Dick');
SELECT fn_agregar_imagen(23, 'https://covers.openlibrary.org/b/isbn/9799000000026-L.jpg', 0::SMALLINT, true, 'Portada de El principito');
SELECT fn_agregar_imagen(24, 'https://covers.openlibrary.org/b/isbn/9799000000027-L.jpg', 0::SMALLINT, true, 'Portada de El extranjero');
SELECT fn_agregar_imagen(25, 'https://covers.openlibrary.org/b/isbn/9799000000028-L.jpg', 0::SMALLINT, true, 'Portada de Cronicas marcianas');
SELECT fn_agregar_imagen(26, 'https://covers.openlibrary.org/b/isbn/9799000000029-L.jpg', 0::SMALLINT, true, 'Portada de Matadero Cinco');
SELECT fn_agregar_imagen(27, 'https://covers.openlibrary.org/b/isbn/9799000000030-L.jpg', 0::SMALLINT, true, 'Portada de A sangre fria');
SELECT fn_agregar_imagen(28, 'https://covers.openlibrary.org/b/isbn/9799000000031-L.jpg', 0::SMALLINT, true, 'Portada de Madame Bovary');
SELECT fn_agregar_imagen(29, 'https://covers.openlibrary.org/b/isbn/9799000000032-L.jpg', 0::SMALLINT, true, 'Portada de El jardin de los cerezos');
SELECT fn_agregar_imagen(30, 'https://covers.openlibrary.org/b/isbn/9799000000033-L.jpg', 0::SMALLINT, true, 'Portada de Fahrenheit 451');

COMMIT;

-- ---------------------------------------------------------------------
-- Verificacion rapida (opcional, solo lectura)
-- ---------------------------------------------------------------------
-- SELECT nombre_usuario, rol FROM usuarios;
-- SELECT titulo, precio, stock FROM libros ORDER BY titulo;
-- SELECT l.titulo, a.nombre_autor FROM libros l
--   JOIN libro_autor la ON la.id_libro = l.id_libro
--   JOIN autores a ON a.id_autor = la.id_autor ORDER BY l.titulo;