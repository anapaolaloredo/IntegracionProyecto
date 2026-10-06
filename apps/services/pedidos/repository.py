"""Acceso a datos de pedidos. Toda operacion que toca stock corre en UNA
transaccion con SELECT ... FOR UPDATE sobre las filas de libros / pedidos."""

from psycopg.rows import dict_row

import transiciones
from common.db import get_connection
from common.web import Conflicto, NoEncontrado


def crear(id_cuenta, items):
    """items: [(id_libro, cantidad)] sin ids repetidos. Descuenta stock o hace rollback."""
    ids = [id_libro for id_libro, _ in items]
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Orden por id: dos pedidos concurrentes bloquean en el mismo orden (sin deadlock).
        cur.execute("SELECT id_libro, precio, stock FROM libros WHERE id_libro = ANY(%s) "
                    "ORDER BY id_libro FOR UPDATE", (ids,))
        libros = {fila["id_libro"]: fila for fila in cur.fetchall()}
        total = 0
        for id_libro, cantidad in items:
            libro = libros.get(id_libro)
            if libro is None:
                raise NoEncontrado(f"El libro {id_libro} no existe.")
            if libro["stock"] < cantidad:
                raise Conflicto(f"Stock insuficiente para el libro {id_libro} "
                                f"(disponible {libro['stock']}, pedido {cantidad}).")
            total += libro["precio"] * cantidad
        cur.execute("INSERT INTO pedidos (id_cuenta, total) VALUES (%s, %s) RETURNING id_pedido",
                    (id_cuenta, total))
        id_pedido = cur.fetchone()["id_pedido"]
        for id_libro, cantidad in items:
            cur.execute("INSERT INTO lineas_pedido (id_pedido, id_libro, cantidad, precio_unitario) "
                        "VALUES (%s, %s, %s, %s)", (id_pedido, id_libro, cantidad, libros[id_libro]["precio"]))
            cur.execute("UPDATE libros SET stock = stock - %s WHERE id_libro = %s", (cantidad, id_libro))
        return id_pedido


def listar(id_cuenta=None):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        consulta = "SELECT id_pedido, id_cuenta, estado, total, fecha_creacion FROM pedidos"
        if id_cuenta is None:
            cur.execute(consulta + " ORDER BY id_pedido DESC")
        else:
            cur.execute(consulta + " WHERE id_cuenta = %s ORDER BY id_pedido DESC", (id_cuenta,))
        return cur.fetchall()


def obtener(id_pedido):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_pedido, id_cuenta, estado, total, fecha_creacion FROM pedidos "
                    "WHERE id_pedido = %s", (id_pedido,))
        pedido = cur.fetchone()
        if not pedido:
            return None
        cur.execute("SELECT lp.id_libro, l.isbn, l.titulo, lp.cantidad, lp.precio_unitario "
                    "FROM lineas_pedido lp JOIN libros l ON l.id_libro = lp.id_libro "
                    "WHERE lp.id_pedido = %s ORDER BY lp.id_linea", (id_pedido,))
        pedido["lineas"] = cur.fetchall()
        return pedido


def cambiar_estado(id_pedido, nuevo, id_actor, es_admin):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_cuenta, estado FROM pedidos WHERE id_pedido = %s FOR UPDATE", (id_pedido,))
        pedido = cur.fetchone()
        if not pedido:
            raise NoEncontrado("Pedido no encontrado.")
        transiciones.validar(pedido["estado"], nuevo, es_admin, pedido["id_cuenta"] == id_actor)
        if nuevo == "cancelado":  # devuelve el stock
            # Bloquea los libros en orden de id (igual que crear) para evitar deadlocks:
            # el UPDATE ... FROM los bloquearia en el orden del plan de ejecucion.
            cur.execute("SELECT l.id_libro FROM libros l JOIN lineas_pedido lp ON lp.id_libro = l.id_libro "
                        "WHERE lp.id_pedido = %s ORDER BY l.id_libro FOR UPDATE OF l", (id_pedido,))
            cur.fetchall()
            cur.execute("UPDATE libros l SET stock = l.stock + lp.cantidad FROM lineas_pedido lp "
                        "WHERE lp.id_pedido = %s AND l.id_libro = lp.id_libro", (id_pedido,))
        cur.execute("UPDATE pedidos SET estado = %s WHERE id_pedido = %s", (nuevo, id_pedido))


def eliminar(id_pedido):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pedidos WHERE id_pedido = %s AND estado = 'cancelado'", (id_pedido,))
        if cur.rowcount == 1:
            return
        cur.execute("SELECT estado FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        fila = cur.fetchone()
        if not fila:
            raise NoEncontrado("Pedido no encontrado.")
        raise Conflicto(f"Solo se pueden eliminar pedidos cancelados (este esta {fila[0]}).")
