"""Prueba contra la BD real (requiere la migracion de pedidos aplicada y .env con DB_*):
    cd apps/services/pedidos && RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_stock_manual.py -q -s
Crea un libro y una cuenta temporales y los borra al terminar."""

import os
import threading
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="requiere BD real (RUN_DB_TESTS=1)")

import repository  # noqa: E402
from common.db import get_connection  # noqa: E402
from common.web import Conflicto  # noqa: E402


@pytest.fixture
def escenario():
    sufijo = uuid.uuid4().hex[:8]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id_formato FROM formatos LIMIT 1")
        id_formato = cur.fetchone()[0]
        cur.execute("INSERT INTO libros (isbn, titulo, precio, stock, id_formato) "
                    "VALUES (%s, %s, 10, 1, %s) RETURNING id_libro", (sufijo.ljust(13, "0")[:13], "T-" + sufijo, id_formato))
        id_libro = cur.fetchone()[0]
        cur.execute("INSERT INTO cuentas (correo, contrasena_hash, rol) VALUES (%s, 'x', 'cliente') "
                    "RETURNING id_cuenta", (f"t{sufijo}@test.co",))
        id_cuenta = cur.fetchone()[0]
    yield id_cuenta, id_libro
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pedidos WHERE id_cuenta = %s", (id_cuenta,))
        cur.execute("DELETE FROM cuentas WHERE id_cuenta = %s", (id_cuenta,))
        cur.execute("DELETE FROM libros WHERE id_libro = %s", (id_libro,))


def _stock(id_libro):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT stock FROM libros WHERE id_libro = %s", (id_libro,))
        return cur.fetchone()[0]


def test_stock_insuficiente_hace_rollback(escenario):
    id_cuenta, id_libro = escenario
    with pytest.raises(Conflicto):
        repository.crear(id_cuenta, [(id_libro, 2)])
    assert _stock(id_libro) == 1
    assert repository.listar(id_cuenta) == []


def test_cancelar_devuelve_stock(escenario):
    id_cuenta, id_libro = escenario
    id_pedido = repository.crear(id_cuenta, [(id_libro, 1)])
    assert _stock(id_libro) == 0
    repository.cambiar_estado(id_pedido, "cancelado", id_cuenta, False)
    assert _stock(id_libro) == 1


def test_dos_pedidos_concurrentes_por_el_ultimo_ejemplar(escenario):
    id_cuenta, id_libro = escenario
    resultados = []

    def intentar():
        try:
            resultados.append(repository.crear(id_cuenta, [(id_libro, 1)]))
        except Conflicto as exc:
            resultados.append(exc)

    hilos = [threading.Thread(target=intentar) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sum(isinstance(r, int) for r in resultados) == 1
    assert sum(isinstance(r, Conflicto) for r in resultados) == 1
    assert _stock(id_libro) == 0
