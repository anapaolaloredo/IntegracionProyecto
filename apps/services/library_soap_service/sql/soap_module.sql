-- =====================================================================
-- Modulo SOAP de clasificacion Cloud — tablas y objetos PROPIOS
-- =====================================================================
-- Este script NO modifica ninguna tabla del monolito (libros, conceptos,
-- libro_concepto, generos, libro_genero, autores, formatos, usuarios).
-- Solo agrega tablas nuevas que referencian esas tablas por FK, mas un
-- rol de aplicacion de minimo privilegio para el modulo SOAP.
--
-- Mapeo de nombres genericos del ejercicio -> nombres reales del esquema:
--   books          -> libros
--   concepts       -> conceptos
--   book_concepts  -> libro_concepto
--   categories     -> generos (via libro_genero)
--
-- Ejecutar despues de db/01_schema.sql (o data/library_schema.sql), como
-- un rol con permiso para crear tablas y roles (p.ej. library_user o
-- postgres), UNA sola vez:
--   psql -d library -f apps/services/library_soap_service/sql/soap_module.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. TABLAS PROPIAS DEL MODULO SOAP
-- ---------------------------------------------------------------------

-- Identidad minima del usuario del cliente SOAP (NO es la tabla usuarios
-- del monolito: esta app no autentica compradores, solo identifica a
-- quien esta clasificando conceptos).
CREATE TABLE IF NOT EXISTS clasificadores (
    id_clasificador   SERIAL PRIMARY KEY,
    nombre            VARCHAR(100) NOT NULL,
    apellido          VARCHAR(100) NOT NULL,
    correo            VARCHAR(150) NOT NULL UNIQUE,
    fecha_registro    TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clasificadores_correo ON clasificadores (correo);

-- Cada fila es "este clasificador dijo que este concepto, en este libro,
-- corresponde a este modelo Cloud". id_libro e id_concepto referencian
-- las tablas del monolito, en solo lectura desde este modulo.
CREATE TABLE IF NOT EXISTS clasificaciones_cloud (
    id_clasificacion  SERIAL PRIMARY KEY,
    id_clasificador   INT  NOT NULL REFERENCES clasificadores(id_clasificador) ON DELETE CASCADE,
    id_libro          INT  NOT NULL REFERENCES libros(id_libro)                ON DELETE RESTRICT,
    id_concepto       INT  NOT NULL REFERENCES conceptos(id_concepto)          ON DELETE RESTRICT,
    modelo_cloud      VARCHAR(4) NOT NULL CHECK (modelo_cloud IN ('IaaS','PaaS','SaaS','FaaS')),
    fecha_clasificacion TIMESTAMP NOT NULL DEFAULT now(),
    -- Auditoria minima: que cliente de escritorio origino la peticion
    -- (mismo valor que clientes_servidos.tipo_cliente). Se guarda aqui
    -- ademas de en clientes_servidos porque responde una pregunta distinta:
    -- "quien clasifico esto" vs "cuantas peticiones ha hecho ese tipo de cliente".
    origen_cliente    VARCHAR(50),

    -- Regla de negocio del ejercicio: un clasificador no puede clasificar
    -- dos veces el mismo concepto (en el mismo libro). Es la restriccion
    -- que el servicio traduce a SOAP Fault 409 (ver soap/faults.py).
    CONSTRAINT uq_clasificador_libro_concepto UNIQUE (id_clasificador, id_libro, id_concepto)
);

CREATE INDEX IF NOT EXISTS idx_clasificaciones_clasificador ON clasificaciones_cloud (id_clasificador);
CREATE INDEX IF NOT EXISTS idx_clasificaciones_modelo       ON clasificaciones_cloud (modelo_cloud);

-- Contabiliza, por tipo de cliente de escritorio (p.ej. "electron-desktop",
-- "zeep-python"), cuantas peticiones ha atendido el servicio.
CREATE TABLE IF NOT EXISTS clientes_servidos (
    id_cliente          SERIAL PRIMARY KEY,
    tipo_cliente        VARCHAR(50)  NOT NULL,
    identificador       VARCHAR(150) NOT NULL,
    peticiones_atendidas INT         NOT NULL DEFAULT 0 CHECK (peticiones_atendidas >= 0),
    primera_peticion    TIMESTAMP    NOT NULL DEFAULT now(),
    ultima_peticion     TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_tipo_identificador UNIQUE (tipo_cliente, identificador)
);

-- ---------------------------------------------------------------------
-- 2. VISTA: conceptos pendientes de un clasificador (dato compuesto que
--    integra book_concepts + concepts + books + categories del monolito)
-- ---------------------------------------------------------------------
-- No es "pendiente" en abstracto: es pendiente PARA un clasificador dado
-- (todavia no aparece en clasificaciones_cloud para ese clasificador).
CREATE OR REPLACE VIEW vista_conceptos_pendientes AS
SELECT
    l.id_libro,
    l.isbn,
    l.titulo               AS titulo_libro,
    c.id_concepto,
    c.nombre_concepto,
    lc.definicion,
    COALESCE(STRING_AGG(DISTINCT g.nombre_genero, ', '), '') AS categorias
FROM libro_concepto lc
JOIN libros l     ON l.id_libro = lc.id_libro
JOIN conceptos c  ON c.id_concepto = lc.id_concepto
LEFT JOIN libro_genero lg ON lg.id_libro = l.id_libro
LEFT JOIN generos g       ON g.id_genero = lg.id_genero
GROUP BY l.id_libro, l.isbn, l.titulo, c.id_concepto, c.nombre_concepto, lc.definicion;

-- ---------------------------------------------------------------------
-- 3. FUNCIONES (equivalentes a "stored procedures" parametrizados)
-- ---------------------------------------------------------------------

-- 3.1 Conceptos que un clasificador aun no ha clasificado.
CREATE OR REPLACE FUNCTION fn_obtener_conceptos_pendientes(p_id_clasificador INT)
RETURNS TABLE (
    isbn VARCHAR, titulo_libro VARCHAR, id_concepto INT,
    nombre_concepto VARCHAR, definicion TEXT, categorias TEXT
) AS $$
    SELECT v.isbn, v.titulo_libro, v.id_concepto, v.nombre_concepto, v.definicion, v.categorias
    FROM vista_conceptos_pendientes v
    WHERE NOT EXISTS (
        SELECT 1 FROM clasificaciones_cloud cc
        WHERE cc.id_clasificador = p_id_clasificador
          AND cc.id_libro = v.id_libro
          AND cc.id_concepto = v.id_concepto
    )
    ORDER BY v.titulo_libro, v.nombre_concepto;
$$ LANGUAGE sql STABLE;

-- 3.2 Registrar clasificacion. Crea al clasificador si no existe (por
-- correo). Lanza unique_violation (23505) si ya la habia clasificado;
-- ese error lo traduce app.py/faults.py a SOAP Fault 409.
CREATE OR REPLACE FUNCTION fn_registrar_clasificacion(
    p_nombre       VARCHAR,
    p_apellido     VARCHAR,
    p_correo       VARCHAR,
    p_isbn         VARCHAR,
    p_id_concepto  INT,
    p_modelo_cloud VARCHAR,
    p_origen_cliente VARCHAR
) RETURNS INT AS $$
DECLARE
    v_id_clasificador INT;
    v_id_libro        INT;
    v_id_clasificacion INT;
BEGIN
    SELECT id_libro INTO v_id_libro FROM libros WHERE isbn = p_isbn;
    IF v_id_libro IS NULL THEN
        RAISE EXCEPTION 'LIBRO_NO_ENCONTRADO: isbn % no existe', p_isbn
            USING ERRCODE = 'P0002';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM conceptos WHERE id_concepto = p_id_concepto) THEN
        RAISE EXCEPTION 'CONCEPTO_NO_ENCONTRADO: id_concepto % no existe', p_id_concepto
            USING ERRCODE = 'P0002';
    END IF;

    INSERT INTO clasificadores (nombre, apellido, correo)
    VALUES (p_nombre, p_apellido, p_correo)
    ON CONFLICT (correo) DO UPDATE SET correo = EXCLUDED.correo
    RETURNING id_clasificador INTO v_id_clasificador;

    INSERT INTO clasificaciones_cloud (id_clasificador, id_libro, id_concepto, modelo_cloud, origen_cliente)
    VALUES (v_id_clasificador, v_id_libro, p_id_concepto, p_modelo_cloud, p_origen_cliente)
    RETURNING id_clasificacion INTO v_id_clasificacion;

    RETURN v_id_clasificacion;
END;
$$ LANGUAGE plpgsql;

-- 3.3 Progreso de un clasificador (por correo): total clasificado vs
-- total de conceptos existentes en el catalogo.
CREATE OR REPLACE FUNCTION fn_obtener_progreso_usuario(p_correo VARCHAR)
RETURNS TABLE (total_conceptos BIGINT, total_clasificados BIGINT, total_pendientes BIGINT) AS $$
    WITH clasificador AS (
        SELECT id_clasificador FROM clasificadores WHERE correo = p_correo
    ),
    totales AS (
        SELECT COUNT(*) AS total FROM libro_concepto
    ),
    clasificados AS (
        SELECT COUNT(*) AS total FROM clasificaciones_cloud cc, clasificador cl
        WHERE cc.id_clasificador = cl.id_clasificador
    )
    SELECT
        (SELECT total FROM totales),
        COALESCE((SELECT total FROM clasificados), 0),
        (SELECT total FROM totales) - COALESCE((SELECT total FROM clasificados), 0);
$$ LANGUAGE sql STABLE;

-- 3.4 Registrar/actualizar el contador de peticiones de un cliente.
CREATE OR REPLACE FUNCTION fn_registrar_cliente_servido(p_tipo_cliente VARCHAR, p_identificador VARCHAR)
RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    INSERT INTO clientes_servidos (tipo_cliente, identificador, peticiones_atendidas)
    VALUES (p_tipo_cliente, p_identificador, 1)
    ON CONFLICT (tipo_cliente, identificador)
    DO UPDATE SET peticiones_atendidas = clientes_servidos.peticiones_atendidas + 1,
                  ultima_peticion = now()
    RETURNING id_cliente INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- 3.5 (Tarea 1 - trabajo en casa) Estadisticas por modelo Cloud.
CREATE OR REPLACE FUNCTION fn_obtener_estadisticas_por_modelo()
RETURNS TABLE (modelo_cloud VARCHAR, total BIGINT) AS $$
    SELECT modelo_cloud, COUNT(*) AS total
    FROM clasificaciones_cloud
    GROUP BY modelo_cloud
    ORDER BY modelo_cloud;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------
-- 4. ROL DE APLICACION DE MINIMO PRIVILEGIO PARA EL MODULO SOAP
-- ---------------------------------------------------------------------
-- No reutiliza library_user (que en este proyecto academico es dueno de
-- toda la base). El modulo SOAP corre con su propio rol, limitado a:
--   - SELECT de solo lectura sobre las tablas del monolito que necesita.
--   - SELECT/INSERT/UPDATE sobre sus 3 tablas propias (nunca DELETE:
--     el historial de clasificaciones no se borra desde este servicio).
--   - EXECUTE sobre las funciones de esta seccion (que ya validan y
--     encapsulan el acceso, evitando dar INSERT directo salvo lo minimo).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'soap_service_user') THEN
        CREATE ROLE soap_service_user WITH LOGIN PASSWORD 'change-me-soap';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE library TO soap_service_user;
GRANT USAGE ON SCHEMA public TO soap_service_user;

-- Solo lectura sobre el catalogo del monolito.
GRANT SELECT ON libros, conceptos, libro_concepto, generos, libro_genero TO soap_service_user;

-- Lectura/escritura controlada sobre las tablas propias del modulo.
GRANT SELECT, INSERT, UPDATE ON clasificadores, clasificaciones_cloud, clientes_servidos TO soap_service_user;
GRANT USAGE, SELECT ON SEQUENCE clasificadores_id_clasificador_seq TO soap_service_user;
GRANT USAGE, SELECT ON SEQUENCE clasificaciones_cloud_id_clasificacion_seq TO soap_service_user;
GRANT USAGE, SELECT ON SEQUENCE clientes_servidos_id_cliente_seq TO soap_service_user;

GRANT SELECT ON vista_conceptos_pendientes TO soap_service_user;

GRANT EXECUTE ON FUNCTION fn_obtener_conceptos_pendientes(INT)   TO soap_service_user;
GRANT EXECUTE ON FUNCTION fn_registrar_clasificacion(VARCHAR, VARCHAR, VARCHAR, VARCHAR, INT, VARCHAR, VARCHAR) TO soap_service_user;
GRANT EXECUTE ON FUNCTION fn_obtener_progreso_usuario(VARCHAR)   TO soap_service_user;
GRANT EXECUTE ON FUNCTION fn_registrar_cliente_servido(VARCHAR, VARCHAR) TO soap_service_user;
GRANT EXECUTE ON FUNCTION fn_obtener_estadisticas_por_modelo()   TO soap_service_user;

-- Explícito por claridad (son los defaults de un rol nuevo, sin BYPASSRLS,
-- sin CREATEDB, sin CREATEROLE, sin SUPERUSER): no se otorga nada mas.
REVOKE ALL ON usuarios, usuarios_auditoria_rol, autores, libro_autor, formatos, imagenes_libro
    FROM soap_service_user;
