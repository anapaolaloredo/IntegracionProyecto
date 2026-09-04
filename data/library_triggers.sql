-- =====================================================================
-- TRIGGERS: Libreria en linea
-- =====================================================================
-- Requisito: haber cargado antes library_schema.sql (incluye la columna
-- libros.fecha_actualizacion y la tabla usuarios_auditoria_rol que estos
-- triggers usan).
--
-- Cada trigger resuelve un problema concreto que las funciones/constraints
-- por si solas no cubrian, no se agregaron solo para cumplir un checklist:
--
--   1) trg_una_portada_por_libro   -> antes esta regla SOLO vivia dentro de
--      fn_agregar_imagen (un UPDATE manual antes del INSERT). Si algo
--      insertaba/actualizaba imagenes_libro por otra via, el indice unico
--      parcial uq_imagenes_portada_unica simplemente rechazaba la operacion
--      en vez de "rotar" la portada. Mover la regla a un trigger sobre la
--      tabla la hace valida sin importar el camino de escritura.
--
--   2) trg_libros_fecha_actualizacion -> hoy libros solo registraba
--      fecha_creacion; no habia forma de saber cuando fue la ultima vez
--      que cambio el precio/stock/titulo de un libro (RNF-07 trazabilidad).
--
--   3) trg_usuarios_auditoria_rol -> la regla de "un solo Administrador" ya
--      esta protegida por uq_usuarios_admin_unico, pero no habia registro
--      de CUANDO y A QUIEN se le asigno o quito el rol de admin. Esto
--      complementa esa proteccion con evidencia auditable.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Una sola portada por libro (BEFORE INSERT OR UPDATE en imagenes_libro)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_una_portada_por_libro()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.es_portada THEN
        UPDATE imagenes_libro
           SET es_portada = false
         WHERE id_libro = NEW.id_libro
           AND es_portada = true
           AND id_imagen IS DISTINCT FROM NEW.id_imagen;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_una_portada_por_libro ON imagenes_libro;
CREATE TRIGGER trg_una_portada_por_libro
    BEFORE INSERT OR UPDATE ON imagenes_libro
    FOR EACH ROW
    EXECUTE FUNCTION trg_fn_una_portada_por_libro();

-- ---------------------------------------------------------------------
-- 2. Sello de tiempo automatico en libros (BEFORE UPDATE)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_libros_fecha_actualizacion()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_libros_fecha_actualizacion ON libros;
CREATE TRIGGER trg_libros_fecha_actualizacion
    BEFORE UPDATE ON libros
    FOR EACH ROW
    EXECUTE FUNCTION trg_fn_libros_fecha_actualizacion();

-- ---------------------------------------------------------------------
-- 3. Auditoria de cambios de rol (AFTER UPDATE en usuarios)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_auditar_cambio_rol()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.rol IS DISTINCT FROM OLD.rol THEN
        INSERT INTO usuarios_auditoria_rol (id_usuario, rol_anterior, rol_nuevo)
        VALUES (OLD.id_usuario, OLD.rol, NEW.rol);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_usuarios_auditoria_rol ON usuarios;
CREATE TRIGGER trg_usuarios_auditoria_rol
    AFTER UPDATE ON usuarios
    FOR EACH ROW
    EXECUTE FUNCTION trg_fn_auditar_cambio_rol();
