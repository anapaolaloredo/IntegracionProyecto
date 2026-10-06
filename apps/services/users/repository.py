"""Acceso a datos de usuarios: cuentas + personas (las mismas tablas de login).
Nunca selecciona contrasena_hash salvo en obtener_hash."""

from psycopg import errors
from psycopg.rows import dict_row

from common.db import get_connection
from common.web import Conflicto

_COLUMNAS = ("c.id_cuenta AS id_usuario, c.correo, c.rol, c.fecha_registro, "
             "p.nombre, p.apellido_paterno, p.apellido_materno")
_FROM = "FROM cuentas c JOIN personas p ON p.id_cuenta = c.id_cuenta"
_CAMPOS_PERSONA = ("nombre", "apellido_paterno", "apellido_materno")


def listar():
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNAS} {_FROM} ORDER BY c.id_cuenta")
        return cur.fetchall()


def obtener(id_usuario):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNAS} {_FROM} WHERE c.id_cuenta = %s", (id_usuario,))
        return cur.fetchone()


def obtener_hash(id_usuario):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT contrasena_hash FROM cuentas WHERE id_cuenta = %s", (id_usuario,))
        fila = cur.fetchone()
        return fila[0] if fila else None


def crear(correo, contrasena_hash, rol, nombre, apellido_paterno, apellido_materno):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cuentas (correo, contrasena_hash, rol) VALUES (%s, %s, %s) "
                        "RETURNING id_cuenta", (correo, contrasena_hash, rol))
            id_usuario = cur.fetchone()[0]
            cur.execute("INSERT INTO personas (id_cuenta, nombre, apellido_paterno, apellido_materno) "
                        "VALUES (%s, %s, %s, %s)", (id_usuario, nombre, apellido_paterno, apellido_materno))
            return id_usuario
    except errors.UniqueViolation:
        raise Conflicto("Ese correo ya esta registrado.")


def actualizar(id_usuario, campos):
    """campos: subconjunto de correo/nombre/apellido_paterno/apellido_materno. True si el usuario existe."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            existe = False
            if "correo" in campos:
                cur.execute("UPDATE cuentas SET correo = %s WHERE id_cuenta = %s",
                            (campos["correo"], id_usuario))
                existe = cur.rowcount == 1
            personales = {k: v for k, v in campos.items() if k in _CAMPOS_PERSONA}
            if personales:
                sets = ", ".join(f"{k} = %s" for k in personales)  # claves en lista blanca
                cur.execute(f"UPDATE personas SET {sets} WHERE id_cuenta = %s",
                            (*personales.values(), id_usuario))
                existe = existe or cur.rowcount == 1
            return existe
    except errors.UniqueViolation:
        raise Conflicto("Ese correo ya esta registrado.")


def cambiar_password(id_usuario, contrasena_hash):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cuentas SET contrasena_hash = %s WHERE id_cuenta = %s",
                    (contrasena_hash, id_usuario))
        return cur.rowcount == 1


def cambiar_rol(id_usuario, rol):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cuentas SET rol = %s WHERE id_cuenta = %s", (rol, id_usuario))
        return cur.rowcount == 1


def eliminar(id_usuario):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM cuentas WHERE id_cuenta = %s", (id_usuario,))
            return cur.rowcount == 1
    except errors.ForeignKeyViolation:
        raise Conflicto("El usuario tiene pedidos y no se puede eliminar.")
