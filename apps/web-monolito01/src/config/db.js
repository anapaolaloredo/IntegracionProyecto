// Conexion directa a PostgreSQL (sin ORM). Todo el acceso a datos pasa
// por las funciones PL/pgSQL definidas en data/library_schema.sql.
require('dotenv').config();
const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.PGHOST || 'localhost',
  port: process.env.PGPORT || 5432,
  database: process.env.PGDATABASE || 'library',
  user: process.env.PGUSER || 'library_user',
  password: process.env.PGPASSWORD || '666',
  max: 10,
  idleTimeoutMillis: 30000
});

pool.on('error', (err) => {
  console.error('Error inesperado en el pool de PostgreSQL:', err);
});

module.exports = pool;
