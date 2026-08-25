-- =====================================================================
-- BASE DE DATOS: Librería en línea (app monolítica Node.js + PostgreSQL)
-- =====================================================================
--
-- ANÁLISIS DE DEPENDENCIAS
-- ------------------------------------------------------------------
-- Dependencias funcionales (FD):
--   isbn -> titulo, anio_publicacion, precio, stock, id_formato
--   id_autor -> nombre_autor
--   id_genero -> nombre_genero
--   id_formato -> nombre_formato
--   id_concepto -> nombre_concepto
--   (id_libro, id_concepto) -> definicion   (la definición depende del PAR
--       libro-concepto, no solo del concepto: un mismo concepto puede
--       tener definiciones distintas según el libro -> se modela como
--       entidad asociativa, no como MVD pura)
--
-- Dependencias multivaluadas (MVD), independientes entre sí sobre libro:
--   isbn ->> id_autor   (un libro tiene varios autores, independiente del género)
--   isbn ->> id_genero  (un libro tiene varios géneros, independiente del autor)
--   isbn ->> id_imagen  (un libro tiene varias imágenes, independiente de autor/género)
--
-- Al existir MVDs independientes (autor, género, imagen) sobre libro, el
-- modelo se descompone en 4FN usando tablas puente separadas
-- (libro_autor, libro_genero, imagenes_libro) en vez de una sola tabla
-- que combine estos atributos multivaluados (lo que generaría anomalías
-- de redundancia tipo producto cartesiano).
--
-- Formato y género/categoría son catálogos independientes (1:N con libro
-- para formato, N:M con libro para género), sin relación funcional entre sí.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. TABLAS
-- ---------------------------------------------------------------------

CREATE TABLE usuarios (
    id_usuario       SERIAL PRIMARY KEY,
    nombre_usuario   VARCHAR(50)  NOT NULL UNIQUE,
    correo           VARCHAR(150) NOT NULL UNIQUE,
    contrasena_hash  VARCHAR(255) NOT NULL,
    rol              VARCHAR(10)  NOT NULL DEFAULT 'cliente'
                         CHECK (rol IN ('admin','cliente')),
    fecha_registro   TIMESTAMP    NOT NULL DEFAULT now()
);

-- Regla de negocio: máximo un administrador en todo el sistema
CREATE UNIQUE INDEX uq_usuarios_admin_unico
    ON usuarios (rol)
    WHERE rol = 'admin';

CREATE TABLE formatos (
    id_formato      SERIAL PRIMARY KEY,
    nombre_formato  VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE generos (
    id_genero      SERIAL PRIMARY KEY,
    nombre_genero  VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE autores (
    id_autor      SERIAL PRIMARY KEY,
    nombre_autor  VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE conceptos (
    id_concepto      SERIAL PRIMARY KEY,
    nombre_concepto  VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE libros (
    id_libro          SERIAL PRIMARY KEY,
    isbn              VARCHAR(13)  NOT NULL UNIQUE,
    titulo            VARCHAR(255) NOT NULL,
    anio_publicacion  SMALLINT     CHECK (anio_publicacion BETWEEN 1450 AND
                                     EXTRACT(YEAR FROM now())::INT + 1),
    precio            NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    stock             INT           NOT NULL DEFAULT 0 CHECK (stock >= 0),
    id_formato        INT           NOT NULL REFERENCES formatos(id_formato),
    fecha_creacion    TIMESTAMP     NOT NULL DEFAULT now()
);

-- N:M libro <-> autor
CREATE TABLE libro_autor (
    id_libro  INT NOT NULL REFERENCES libros(id_libro)  ON DELETE CASCADE,
    id_autor  INT NOT NULL REFERENCES autores(id_autor)  ON DELETE RESTRICT,
    PRIMARY KEY (id_libro, id_autor)
);

-- N:M libro <-> género
CREATE TABLE libro_genero (
    id_libro   INT NOT NULL REFERENCES libros(id_libro)   ON DELETE CASCADE,
    id_genero  INT NOT NULL REFERENCES generos(id_genero) ON DELETE RESTRICT,
    PRIMARY KEY (id_libro, id_genero)
);

-- N:M libro <-> concepto, con atributo propio de la relación (definicion)
CREATE TABLE libro_concepto (
    id_libro     INT  NOT NULL REFERENCES libros(id_libro)       ON DELETE CASCADE,
    id_concepto  INT  NOT NULL REFERENCES conceptos(id_concepto) ON DELETE RESTRICT,
    definicion   TEXT NOT NULL,
    PRIMARY KEY (id_libro, id_concepto)
);

-- 1:N libro -> imágenes
CREATE TABLE imagenes_libro (
    id_imagen    SERIAL PRIMARY KEY,
    id_libro     INT NOT NULL REFERENCES libros(id_libro) ON DELETE CASCADE,
    url_imagen   VARCHAR(500) NOT NULL,
    orden        SMALLINT NOT NULL DEFAULT 0,
    es_portada   BOOLEAN NOT NULL DEFAULT false
);

-- Máximo una portada por libro
CREATE UNIQUE INDEX uq_imagenes_portada_unica
    ON imagenes_libro (id_libro)
    WHERE es_portada = true;

-- ---------------------------------------------------------------------
-- 2. ÍNDICES DE APOYO
-- ---------------------------------------------------------------------
CREATE INDEX idx_libros_titulo        ON libros (titulo);
CREATE INDEX idx_libro_autor_autor    ON libro_autor (id_autor);
CREATE INDEX idx_libro_genero_genero  ON libro_genero (id_genero);
CREATE INDEX idx_libro_concepto_concepto ON libro_concepto (id_concepto);
CREATE INDEX idx_imagenes_libro       ON imagenes_libro (id_libro);

-- =====================================================================
-- 3. CRUD (funciones PL/pgSQL) PARA CADA TABLA
-- =====================================================================

-- ---------- usuarios ----------
CREATE OR REPLACE FUNCTION fn_crear_usuario(
    p_nombre_usuario VARCHAR, p_correo VARCHAR, p_contrasena_hash VARCHAR,
    p_rol VARCHAR DEFAULT 'cliente'
) RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO usuarios (nombre_usuario, correo, contrasena_hash, rol)
    VALUES (p_nombre_usuario, p_correo, p_contrasena_hash, p_rol)
    RETURNING id_usuario INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_obtener_usuario(p_id INT)
RETURNS SETOF usuarios AS $$
    SELECT * FROM usuarios WHERE id_usuario = p_id;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_listar_usuarios()
RETURNS SETOF usuarios AS $$
    SELECT * FROM usuarios ORDER BY id_usuario;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_usuario(
    p_id INT, p_nombre_usuario VARCHAR, p_correo VARCHAR, p_rol VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE usuarios
       SET nombre_usuario = p_nombre_usuario,
           correo = p_correo,
           rol = p_rol
     WHERE id_usuario = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_usuario(p_id INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM usuarios WHERE id_usuario = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- formatos (catálogo) ----------
CREATE OR REPLACE FUNCTION fn_crear_formato(p_nombre VARCHAR)
RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO formatos (nombre_formato) VALUES (p_nombre)
    RETURNING id_formato INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_formatos()
RETURNS SETOF formatos AS $$
    SELECT * FROM formatos ORDER BY nombre_formato;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_formato(p_id INT, p_nombre VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE formatos SET nombre_formato = p_nombre WHERE id_formato = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_formato(p_id INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM formatos WHERE id_formato = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- generos (catálogo) ----------
CREATE OR REPLACE FUNCTION fn_crear_genero(p_nombre VARCHAR)
RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO generos (nombre_genero) VALUES (p_nombre)
    RETURNING id_genero INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_generos()
RETURNS SETOF generos AS $$
    SELECT * FROM generos ORDER BY nombre_genero;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_genero(p_id INT, p_nombre VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE generos SET nombre_genero = p_nombre WHERE id_genero = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_genero(p_id INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM generos WHERE id_genero = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- autores (catálogo) ----------
CREATE OR REPLACE FUNCTION fn_crear_autor(p_nombre VARCHAR)
RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO autores (nombre_autor) VALUES (p_nombre)
    RETURNING id_autor INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_autores()
RETURNS SETOF autores AS $$
    SELECT * FROM autores ORDER BY nombre_autor;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_autor(p_id INT, p_nombre VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE autores SET nombre_autor = p_nombre WHERE id_autor = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_autor(p_id INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM autores WHERE id_autor = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- conceptos (catálogo) ----------
CREATE OR REPLACE FUNCTION fn_crear_concepto(p_nombre VARCHAR)
RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO conceptos (nombre_concepto) VALUES (p_nombre)
    RETURNING id_concepto INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_conceptos()
RETURNS SETOF conceptos AS $$
    SELECT * FROM conceptos ORDER BY nombre_concepto;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_concepto(p_id INT, p_nombre VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE conceptos SET nombre_concepto = p_nombre WHERE id_concepto = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_concepto(p_id INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM conceptos WHERE id_concepto = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- libros ----------
CREATE OR REPLACE FUNCTION fn_crear_libro(
    p_isbn VARCHAR, p_titulo VARCHAR, p_anio SMALLINT, p_precio NUMERIC,
    p_stock INT, p_id_formato INT
) RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, id_formato)
    VALUES (p_isbn, p_titulo, p_anio, p_precio, p_stock, p_id_formato)
    RETURNING id_libro INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_obtener_libro(p_id INT)
RETURNS SETOF libros AS $$
    SELECT * FROM libros WHERE id_libro = p_id;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_listar_libros()
RETURNS SETOF libros AS $$
    SELECT * FROM libros ORDER BY titulo;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_libro(
    p_id INT, p_titulo VARCHAR, p_anio SMALLINT, p_precio NUMERIC,
    p_stock INT, p_id_formato INT
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE libros
       SET titulo = p_titulo,
           anio_publicacion = p_anio,
           precio = p_precio,
           stock = p_stock,
           id_formato = p_id_formato
     WHERE id_libro = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_libro(p_id INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM libros WHERE id_libro = p_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- libro_autor ----------
CREATE OR REPLACE FUNCTION fn_asociar_autor(p_id_libro INT, p_id_autor INT)
RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO libro_autor (id_libro, id_autor)
    VALUES (p_id_libro, p_id_autor)
    ON CONFLICT DO NOTHING;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_autores_por_libro(p_id_libro INT)
RETURNS SETOF autores AS $$
    SELECT a.* FROM autores a
    JOIN libro_autor la ON la.id_autor = a.id_autor
    WHERE la.id_libro = p_id_libro;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_desasociar_autor(p_id_libro INT, p_id_autor INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM libro_autor WHERE id_libro = p_id_libro AND id_autor = p_id_autor;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- libro_genero ----------
CREATE OR REPLACE FUNCTION fn_asociar_genero(p_id_libro INT, p_id_genero INT)
RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO libro_genero (id_libro, id_genero)
    VALUES (p_id_libro, p_id_genero)
    ON CONFLICT DO NOTHING;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_generos_por_libro(p_id_libro INT)
RETURNS SETOF generos AS $$
    SELECT g.* FROM generos g
    JOIN libro_genero lg ON lg.id_genero = g.id_genero
    WHERE lg.id_libro = p_id_libro;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_desasociar_genero(p_id_libro INT, p_id_genero INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM libro_genero WHERE id_libro = p_id_libro AND id_genero = p_id_genero;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- libro_concepto ----------
CREATE OR REPLACE FUNCTION fn_definir_concepto(
    p_id_libro INT, p_id_concepto INT, p_definicion TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO libro_concepto (id_libro, id_concepto, definicion)
    VALUES (p_id_libro, p_id_concepto, p_definicion)
    ON CONFLICT (id_libro, id_concepto)
    DO UPDATE SET definicion = EXCLUDED.definicion;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_conceptos_por_libro(p_id_libro INT)
RETURNS TABLE(id_concepto INT, nombre_concepto VARCHAR, definicion TEXT) AS $$
    SELECT c.id_concepto, c.nombre_concepto, lc.definicion
    FROM conceptos c
    JOIN libro_concepto lc ON lc.id_concepto = c.id_concepto
    WHERE lc.id_libro = p_id_libro;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_eliminar_concepto_de_libro(p_id_libro INT, p_id_concepto INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM libro_concepto WHERE id_libro = p_id_libro AND id_concepto = p_id_concepto;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ---------- imagenes_libro ----------
CREATE OR REPLACE FUNCTION fn_agregar_imagen(
    p_id_libro INT, p_url VARCHAR, p_orden SMALLINT DEFAULT 0, p_es_portada BOOLEAN DEFAULT false
) RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    IF p_es_portada THEN
        UPDATE imagenes_libro SET es_portada = false WHERE id_libro = p_id_libro;
    END IF;
    INSERT INTO imagenes_libro (id_libro, url_imagen, orden, es_portada)
    VALUES (p_id_libro, p_url, p_orden, p_es_portada)
    RETURNING id_imagen INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_listar_imagenes_por_libro(p_id_libro INT)
RETURNS SETOF imagenes_libro AS $$
    SELECT * FROM imagenes_libro WHERE id_libro = p_id_libro ORDER BY orden;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_actualizar_imagen(
    p_id_imagen INT, p_url VARCHAR, p_orden SMALLINT
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE imagenes_libro
       SET url_imagen = p_url, orden = p_orden
     WHERE id_imagen = p_id_imagen;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_eliminar_imagen(p_id_imagen INT)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM imagenes_libro WHERE id_imagen = p_id_imagen;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;