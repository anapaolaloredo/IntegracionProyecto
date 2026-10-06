"""Acceso a datos de pagos. Registrar y reembolsar actualizan pedidos.estado en
la MISMA transaccion (misma base `library`), con el pedido bloqueado FOR UPDATE."""

from decimal import Decimal

from psycopg import errors
from psycopg.rows import dict_row

from common.db import get_connection
from common.web import Conflicto, NoEncontrado, Prohibido


def registrar(id_pedido, id_actor, es_admin, metodo, monto):
    try:
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id_cuenta, estado, total FROM pedidos WHERE id_pedido = %s FOR UPDATE",
                        (id_pedido,))
            pedido = cur.fetchone()
            if not pedido:
                raise NoEncontrado("Pedido no encontrado.")
            if pedido["id_cuenta"] != id_actor and not es_admin:
                raise Prohibido("El pedido no te pertenece.")
            if pedido["estado"] != "pendiente":
                raise Conflicto(f"El pedido esta {pedido['estado']}; solo se pagan pedidos pendientes.")
            if monto is not None and Decimal(monto) != pedido["total"]:
                raise Conflicto(f"El monto no coincide con el total del pedido ({pedido['total']}).")
            cur.execute("INSERT INTO pagos (id_pedido, monto, metodo) VALUES (%s, %s, %s) "
                        "RETURNING id_pago, id_pedido, monto, metodo, fecha_pago",
                        (id_pedido, pedido["total"], metodo))
            pago = cur.fetchone()
            cur.execute("UPDATE pedidos SET estado = 'pagado' WHERE id_pedido = %s", (id_pedido,))
            return pago
    except errors.UniqueViolation:
        raise Conflicto("El pedido ya tiene un pago registrado.")


_SELECT = ("SELECT pg.id_pago, pg.id_pedido, p.id_cuenta, pg.monto, pg.metodo, pg.fecha_pago "
           "FROM pagos pg JOIN pedidos p ON p.id_pedido = pg.id_pedido")


def listar(id_cuenta=None):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if id_cuenta is None:
            cur.execute(_SELECT + " ORDER BY pg.id_pago DESC")
        else:
            cur.execute(_SELECT + " WHERE p.id_cuenta = %s ORDER BY pg.id_pago DESC", (id_cuenta,))
        return cur.fetchall()


def obtener(id_pago):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SELECT + " WHERE pg.id_pago = %s", (id_pago,))
        return cur.fetchone()


def reembolsar(id_pago):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT pg.id_pedido, p.estado FROM pagos pg JOIN pedidos p ON p.id_pedido = pg.id_pedido "
                    "WHERE pg.id_pago = %s FOR UPDATE OF p", (id_pago,))
        fila = cur.fetchone()
        if not fila:
            raise NoEncontrado("Pago no encontrado.")
        if fila["estado"] != "pagado":
            raise Conflicto(f"No se puede reembolsar: el pedido esta {fila['estado']}.")
        cur.execute("DELETE FROM pagos WHERE id_pago = %s", (id_pago,))
        cur.execute("UPDATE pedidos SET estado = 'pendiente' WHERE id_pedido = %s", (fila["id_pedido"],))
