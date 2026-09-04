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

-- Bitacora de cambios de rol (quien se volvio/dejo de ser admin y cuando).
-- La llena el trigger trg_usuarios_auditoria_rol (ver library_triggers.sql).
CREATE TABLE usuarios_auditoria_rol (
    id_auditoria  SERIAL PRIMARY KEY,
    id_usuario    INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    rol_anterior  VARCHAR(10) NOT NULL,
    rol_nuevo     VARCHAR(10) NOT NULL,
    fecha_cambio  TIMESTAMP NOT NULL DEFAULT now()
);

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
    fecha_creacion    TIMESTAMP     NOT NULL DEFAULT now(),
    -- La mantiene al dia el trigger trg_libros_fecha_actualizacion (ver
    -- library_triggers.sql); no se escribe manualmente desde la aplicacion.
    fecha_actualizacion TIMESTAMP   NOT NULL DEFAULT now()
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
    id_imagen          SERIAL PRIMARY KEY,
    id_libro           INT NOT NULL REFERENCES libros(id_libro) ON DELETE CASCADE,
    url_imagen         VARCHAR(500) NOT NULL,
    -- Texto alternativo para accesibilidad (atributo alt del <img>). Si se
    -- deja vacio, la vista usa un texto por defecto ("Imagen de <titulo>").
    texto_alternativo  VARCHAR(255) NOT NULL DEFAULT '',
    orden              SMALLINT NOT NULL DEFAULT 0,
    es_portada         BOOLEAN NOT NULL DEFAULT false
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

