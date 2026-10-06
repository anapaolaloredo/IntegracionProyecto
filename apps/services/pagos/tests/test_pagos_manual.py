"""Contra la BD real (migracion aplicada):
    cd apps/services/pagos && RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_pagos_manual.py -q -s"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="requiere BD real (RUN_DB_TESTS=1)")

import repository  # noqa: E402
from common.db import get_connection  # noqa: E402
from common.web import Conflicto, Prohibido  # noqa: E402


@pytest.fixture
def pedido():
    sufijo = uuid.uuid4().hex[:8]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO cuentas (correo, contrasena_hash, rol) VALUES (%s, 'x', 'cliente') "
                    "RETURNING id_cuenta", (f"p{sufijo}@test.co",))
        id_cuenta = cur.fetchone()[0]
        cur.execute("INSERT INTO pedidos (id_cuenta, total) VALUES (%s, 50) RETURNING id_pedido", (id_cuenta,))
        id_pedido = cur.fetchone()[0]
    yield id_cuenta, id_pedido
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pagos WHERE id_pedido = %s", (id_pedido,))
        cur.execute("DELETE FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        cur.execute("DELETE FROM cuentas WHERE id_cuenta = %s", (id_cuenta,))


def _estado(id_pedido):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT estado FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        return cur.fetchone()[0]


def test_pago_marca_pedido_pagado_y_no_se_paga_dos_veces(pedido):
    id_cuenta, id_pedido = pedido
    pago = repository.registrar(id_pedido, id_cuenta, False, "tarjeta", None)
    assert pago["monto"] == 50 and _estado(id_pedido) == "pagado"
    with pytest.raises(Conflicto):
        repository.registrar(id_pedido, id_cuenta, False, "tarjeta", None)
    assert _estado(id_pedido) == "pagado"


def test_pedido_ajeno_prohibido_y_monto_distinto_conflicto(pedido):
    id_cuenta, id_pedido = pedido
    with pytest.raises(Prohibido):
        repository.registrar(id_pedido, id_cuenta + 100000, False, "tarjeta", None)
    from decimal import Decimal
    with pytest.raises(Conflicto):
        repository.registrar(id_pedido, id_cuenta, False, "tarjeta", Decimal("49.99"))
    assert _estado(id_pedido) == "pendiente"


def test_reembolso_devuelve_pedido_a_pendiente(pedido):
    id_cuenta, id_pedido = pedido
    pago = repository.registrar(id_pedido, id_cuenta, False, "efectivo", None)
    repository.reembolsar(pago["id_pago"])
    assert _estado(id_pedido) == "pendiente"
