-- =====================================================================
-- Migracion: tablas de Pedidos y Pagos (apps/services/pedidos y pagos).
-- Additive-only. Requiere data/library_schema.sql y
-- data/migrations/2026-09-18_tablas_login.sql ya aplicados.
-- Ejecutar: psql -d library -f data/migrations/2026-10-06_pedidos_pagos.sql
-- =====================================================================

CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido       SERIAL PRIMARY KEY,
    id_cuenta       INT NOT NULL REFERENCES cuentas(id_cuenta),
    estado          VARCHAR(12) NOT NULL DEFAULT 'pendiente'
                        CHECK (estado IN ('pendiente','pagado','enviado','cancelado')),
    total           NUMERIC(10,2) NOT NULL CHECK (total >= 0),
    fecha_creacion  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pedidos_cuenta ON pedidos (id_cuenta);

CREATE TABLE IF NOT EXISTS lineas_pedido (
    id_linea         SERIAL PRIMARY KEY,
    id_pedido        INT NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    id_libro         INT NOT NULL REFERENCES libros(id_libro),
    cantidad         INT NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    UNIQUE (id_pedido, id_libro)
);

CREATE TABLE IF NOT EXISTS pagos (
    id_pago     SERIAL PRIMARY KEY,
    id_pedido   INT NOT NULL REFERENCES pedidos(id_pedido),
    monto       NUMERIC(10,2) NOT NULL CHECK (monto > 0),
    metodo      VARCHAR(20) NOT NULL CHECK (metodo IN ('tarjeta','transferencia','efectivo')),
    fecha_pago  TIMESTAMP NOT NULL DEFAULT now()
);
-- Un pedido se paga una sola vez (respaldo de la validacion de estado).
CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_pedido ON pagos (id_pedido);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'library_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON pedidos, lineas_pedido, pagos,
              cuentas, personas, autores, libro_autor TO library_user;
        GRANT SELECT, UPDATE ON libros TO library_user;
        GRANT SELECT ON libros, formatos TO library_user;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO library_user;
    END IF;
END $$;
