-- =====================================================================
-- Migracion: normaliza usuarios (persona vs credenciales) para el
-- microservicio de autenticacion (apps/services/login).
-- Ejecutar UNA sola vez, contra una base de datos que ya tiene cargado
-- data/library_schema.sql (+ opcionalmente data/library_data.sql):
--   psql -U library_user -d library -f data/migrations/2026-09-18_normalizar_usuarios.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Tabla personas (1:1 con usuarios) + backfill desde nombre_usuario
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personas (
    id_usuario        INT PRIMARY KEY REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    nombre            VARCHAR(100) NOT NULL,
    apellido_paterno  VARCHAR(100) NOT NULL,
    apellido_materno  VARCHAR(100) NOT NULL
);

-- Backfill: el nombre_usuario existente se usa como nombre provisional;
-- los apellidos quedan como placeholder '(pendiente)' porque no existian
-- antes de esta migracion (son datos de prueba, se pueden corregir a mano).
INSERT INTO personas (id_usuario, nombre, apellido_paterno, apellido_materno)
SELECT id_usuario, nombre_usuario, '(pendiente)', '(pendiente)'
FROM usuarios
ON CONFLICT (id_usuario) DO NOTHING;

-- ---------------------------------------------------------------------
-- 2. Eliminar nombre_usuario de usuarios (ya vive en personas.nombre)
-- ---------------------------------------------------------------------
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_nombre_usuario_key;
ALTER TABLE usuarios DROP COLUMN IF EXISTS nombre_usuario;

-- ---------------------------------------------------------------------
-- 3. Tablas propias del microservicio de login
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS codigos_verificacion (
    id_codigo    SERIAL PRIMARY KEY,
    id_usuario   INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    codigo_hash  VARCHAR(255) NOT NULL,
    expira_en    TIMESTAMP NOT NULL,
    usado        BOOLEAN NOT NULL DEFAULT false,
    creado_en    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_codigos_verificacion_usuario ON codigos_verificacion (id_usuario);

CREATE TABLE IF NOT EXISTS sesiones (
    token        VARCHAR(64) PRIMARY KEY,
    id_usuario   INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    creada_en    TIMESTAMP NOT NULL DEFAULT now(),
    expira_en    TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sesiones_usuario ON sesiones (id_usuario);

-- ---------------------------------------------------------------------
-- 4. Rol de minimo privilegio para el microservicio de login
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auth_service_user') THEN
        CREATE ROLE auth_service_user WITH LOGIN PASSWORD 'change-me-auth';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE library TO auth_service_user;
GRANT USAGE ON SCHEMA public TO auth_service_user;

GRANT SELECT, INSERT, UPDATE ON usuarios, personas TO auth_service_user;
GRANT SELECT, INSERT, UPDATE ON codigos_verificacion, sesiones TO auth_service_user;
GRANT DELETE ON sesiones TO auth_service_user;

GRANT USAGE, SELECT ON SEQUENCE usuarios_id_usuario_seq TO auth_service_user;
GRANT USAGE, SELECT ON SEQUENCE codigos_verificacion_id_codigo_seq TO auth_service_user;
