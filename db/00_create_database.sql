-- =====================================================================
-- 00. CREACION DE BASE DE DATOS Y ROL DE APLICACION — Libreria en linea
-- =====================================================================
-- Ejecutar como superusuario de PostgreSQL (p.ej. "postgres"), UNA sola
-- vez, antes de 01_schema.sql. El rol library_user NO tiene privilegios
-- de superusuario ni de crear roles/bases de datos (principio de minimo
-- privilegio, ver docs/SECURITY_REVIEW.md control #9).
--
-- Uso:
--   sudo -u postgres psql -f db/00_create_database.sql
-- =====================================================================

DROP DATABASE IF EXISTS library;
DROP ROLE IF EXISTS library_user;

CREATE ROLE library_user WITH LOGIN PASSWORD '666';
CREATE DATABASE library OWNER library_user;

-- pgcrypto se usa en 02_seed_30_per_table.sql para generar hashes bcrypt
-- de las contrasenas de prueba (compatibles con bcrypt.compare() en Node).
-- Requiere privilegios de superusuario para instalarse; una vez instalada,
-- library_user (sin ser superusuario) puede usarla con normalidad.
\c library
CREATE EXTENSION IF NOT EXISTS pgcrypto;
