"""Acceso a datos de autores y su relacion con libros (autores, libro_autor)."""

from psycopg import errors
from psycopg.rows import dict_row

from common.db import get_connection
from common.web import Conflicto, NoEncontrado


def listar():
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_autor, nombre_autor FROM autores ORDER BY nombre_autor")
        return cur.fetchall()


def obtener(id_autor):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_autor, nombre_autor FROM autores WHERE id_autor = %s", (id_autor,))
        autor = cur.fetchone()
        if not autor:
            return None
        cur.execute("SELECT l.id_libro, l.isbn, l.titulo FROM libro_autor la "
                    "JOIN libros l ON l.id_libro = la.id_libro "
                    "WHERE la.id_autor = %s ORDER BY l.titulo", (id_autor,))
        autor["libros"] = cur.fetchall()
        return autor


def crear(nombre):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO autores (nombre_autor) VALUES (%s) RETURNING id_autor", (nombre,))
            return cur.fetchone()[0]
    except errors.UniqueViolation:
        raise Conflicto("El autor ya existe.")


def renombrar(id_autor, nombre):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE autores SET nombre_autor = %s WHERE id_autor = %s", (nombre, id_autor))
            return cur.rowcount == 1
    except errors.UniqueViolation:
        raise Conflicto("Ya existe un autor con ese nombre.")


def eliminar(id_autor):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM autores WHERE id_autor = %s", (id_autor,))
            return cur.rowcount == 1
    except errors.ForeignKeyViolation:
        raise Conflicto("El autor tiene libros asociados; desvinculalos primero.")


def vincular(id_autor, id_libro):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO libro_autor (id_libro, id_autor) VALUES (%s, %s) "
                        "ON CONFLICT DO NOTHING", (id_libro, id_autor))
            return cur.rowcount == 1
    except errors.ForeignKeyViolation:
        raise NoEncontrado("El autor o el libro no existe.")


def desvincular(id_autor, id_libro):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM libro_autor WHERE id_autor = %s AND id_libro = %s", (id_autor, id_libro))
        return cur.rowcount == 1
