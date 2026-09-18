"""Acceso a datos: unico modulo (junto con connection.py) que ejecuta SQL
directamente. service.py nunca abre una conexion ni escribe SQL.

Las tablas reales son cuentas/personas/codigos_verificacion/sesiones
(independientes del monolito, ver Task 1). Las columnas id_cuenta se
alias-ean como id_usuario en el SQL para que el resto del microservicio
(service.py, app.py) trabaje con ese nombre sin conocer el de la tabla."""

from psycopg.rows import dict_row
from db.connection import get_connection


def crear_usuario(correo, contrasena_hash, nombre, apellido_paterno, apellido_materno, rol="cliente"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cuentas (correo, contrasena_hash, rol) "
                "VALUES (%s, %s, %s) RETURNING id_cuenta",
                (correo, contrasena_hash, rol),
            )
            id_usuario = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO personas (id_cuenta, nombre, apellido_paterno, apellido_materno) "
                "VALUES (%s, %s, %s, %s)",
                (id_usuario, nombre, apellido_paterno, apellido_materno),
            )
        conn.commit()
        return id_usuario


def obtener_usuario_por_correo(correo):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT c.id_cuenta AS id_usuario, c.correo, c.contrasena_hash, c.rol, p.nombre "
                "FROM cuentas c JOIN personas p ON p.id_cuenta = c.id_cuenta "
                "WHERE c.correo = %s",
                (correo,),
            )
            return cur.fetchone()


def guardar_codigo(id_usuario, codigo_hash, expira_en):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO codigos_verificacion (id_cuenta, codigo_hash, expira_en) "
                "VALUES (%s, %s, %s) RETURNING id_codigo",
                (id_usuario, codigo_hash, expira_en),
            )
            id_codigo = cur.fetchone()[0]
        conn.commit()
        return id_codigo


def obtener_codigo_vigente(id_usuario):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id_codigo, codigo_hash FROM codigos_verificacion "
                "WHERE id_cuenta = %s AND usado = false AND expira_en > now() "
                "ORDER BY creado_en DESC LIMIT 1",
                (id_usuario,),
            )
            return cur.fetchone()


def marcar_codigo_usado(id_codigo):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE codigos_verificacion SET usado = true WHERE id_codigo = %s",
                (id_codigo,),
            )
        conn.commit()


def crear_sesion(token, id_usuario, expira_en):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sesiones (token, id_cuenta, expira_en) VALUES (%s, %s, %s)",
                (token, id_usuario, expira_en),
            )
        conn.commit()


def obtener_sesion_vigente(token):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT s.id_cuenta AS id_usuario, c.correo, p.nombre "
                "FROM sesiones s "
                "JOIN cuentas c ON c.id_cuenta = s.id_cuenta "
                "JOIN personas p ON p.id_cuenta = s.id_cuenta "
                "WHERE s.token = %s AND s.expira_en > now()",
                (token,),
            )
            return cur.fetchone()


def eliminar_sesion(token):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sesiones WHERE token = %s", (token,))
        conn.commit()


def verificar_conexion():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
