-- =====================================================================
-- Migracion: Tablas propias del microservicio de autenticacion
-- (apps/services/login). Additive-only: no ALTER/DROP on existing tables.
-- Crea un conjunto completamente independiente de tablas de auth
-- que no comparten ni modifican el schema de la aplicacion monolito.
--
-- Ejecutar UNA sola vez contra una base de datos que ya tiene cargado
-- data/library_schema.sql (+ opcionalmente data/library_views.sql y
-- data/library_data.sql). Requiere un rol con privilegio para CREATE ROLE
-- (el rol de aplicacion library_user NO lo tiene): en la instancia GCP,
-- usar el rol postgres (`sudo -u postgres psql -d library -f ...`, mismo
-- patron que ya usa sql/soap_module.sql); en local, el superusuario de tu
-- propio Postgres (p.ej. `psql -d library -f ...` sin -U, si tu usuario de
-- SO ya es superusuario).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Tabla cuentas: Autenticacion independiente del microservicio
--    (username, password, rol - NO toca usuarios del monolito)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cuentas (
    id_cuenta        SERIAL PRIMARY KEY,
    correo           VARCHAR(150) NOT NULL UNIQUE,
    contrasena_hash  VARCHAR(255) NOT NULL,
    rol              VARCHAR(10)  NOT NULL DEFAULT 'cliente'
                         CHECK (rol IN ('admin','cliente')),
    fecha_registro   TIMESTAMP    NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2. Tabla personas: Datos personales (1:1 con cuentas)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personas (
    id_cuenta         INT PRIMARY KEY REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
    nombre            VARCHAR(100) NOT NULL,
    apellido_paterno  VARCHAR(100) NOT NULL,
    apellido_materno  VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------
-- 3. Tablas de funcionalidad: Verificacion y sesiones
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS codigos_verificacion (
    id_codigo    SERIAL PRIMARY KEY,
    id_cuenta    INT NOT NULL REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
    codigo_hash  VARCHAR(255) NOT NULL,
    expira_en    TIMESTAMP NOT NULL,
    usado        BOOLEAN NOT NULL DEFAULT false,
    creado_en    TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_codigos_verificacion_cuenta ON codigos_verificacion (id_cuenta);

CREATE TABLE IF NOT EXISTS sesiones (
    token        VARCHAR(64) PRIMARY KEY,
    id_cuenta    INT NOT NULL REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
    creada_en    TIMESTAMP NOT NULL DEFAULT now(),
    expira_en    TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sesiones_cuenta ON sesiones (id_cuenta);

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

GRANT SELECT, INSERT, UPDATE ON cuentas, personas TO auth_service_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON codigos_verificacion, sesiones TO auth_service_user;

GRANT USAGE, SELECT ON SEQUENCE cuentas_id_cuenta_seq TO auth_service_user;
GRANT USAGE, SELECT ON SEQUENCE codigos_verificacion_id_codigo_seq TO auth_service_user;
