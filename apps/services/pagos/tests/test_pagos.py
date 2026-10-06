import pytest

import app as pagos_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header

ADMIN = auth_header(1, ROLE_ADMIN)
USER2 = auth_header(2, ROLE_USER)
USER3 = auth_header(3, ROLE_USER)
PAGO = {"id_pago": 4, "id_pedido": 10, "id_cuenta": 2, "monto": 100.0, "metodo": "tarjeta", "fecha_pago": None}


@pytest.fixture
def c(monkeypatch):
    pagos_app.app.config["TESTING"] = True
    monkeypatch.setattr(pagos_app.repository, "obtener", lambda i: dict(PAGO) if i == 4 else None)
    return pagos_app.app.test_client()


@pytest.mark.parametrize("metodo,ruta", [("post", "/api/pagos"), ("delete", "/api/pagos/4")])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


def test_pagos_no_se_editan(c):
    assert c.put("/api/pagos/4", json={}, headers=ADMIN).status_code == 405
    assert c.patch("/api/pagos/4", json={}, headers=ADMIN).status_code == 405


def test_lecturas_exigen_jwt(c):
    assert c.get("/api/pagos").status_code == 401
    assert c.get("/api/pagos/4").status_code == 401


def test_registrar_pago_pasa_actor_y_metodo(c, monkeypatch):
    visto = []
    monkeypatch.setattr(pagos_app.repository, "registrar",
                        lambda *a: visto.append(a) or dict(PAGO))
    resp = c.post("/api/pagos", json={"id_pedido": 10, "metodo": "tarjeta"}, headers=USER2)
    assert resp.status_code == 201
    assert visto == [(10, 2, False, "tarjeta", None)]


def test_registrar_pago_con_monto_decimal(c, monkeypatch):
    from decimal import Decimal
    visto = []
    monkeypatch.setattr(pagos_app.repository, "registrar", lambda *a: visto.append(a) or dict(PAGO))
    c.post("/api/pagos", json={"id_pedido": 10, "metodo": "efectivo", "monto": 99.9}, headers=USER2)
    assert visto[0][4] == Decimal("99.9")


@pytest.mark.parametrize("cuerpo", [
    {}, {"metodo": "tarjeta"}, {"id_pedido": 10}, {"id_pedido": "10", "metodo": "tarjeta"},
    {"id_pedido": True, "metodo": "tarjeta"}, {"id_pedido": 10, "metodo": "bitcoin"},
    {"id_pedido": 10, "metodo": "tarjeta", "monto": "mucho"},
    {"id_pedido": 10, "metodo": "tarjeta", "monto": -5}, {"id_pedido": 10, "metodo": "tarjeta", "monto": True},
])
def test_registrar_pago_valida(c, monkeypatch, cuerpo):
    llamado = []
    monkeypatch.setattr(pagos_app.repository, "registrar", lambda *a: llamado.append(a))
    assert c.post("/api/pagos", json=cuerpo, headers=USER2).status_code == 400
    assert not llamado


def test_listar_user_solo_suyos_admin_todos(c, monkeypatch):
    vistos = []
    monkeypatch.setattr(pagos_app.repository, "listar", lambda id_cuenta=None: vistos.append(id_cuenta) or [])
    c.get("/api/pagos", headers=USER2)
    c.get("/api/pagos", headers=ADMIN)
    assert vistos == [2, None]


def test_ver_pago_ajeno_403(c):
    assert c.get("/api/pagos/4", headers=USER2).status_code == 200
    assert c.get("/api/pagos/4", headers=USER3).status_code == 403
    assert c.get("/api/pagos/4", headers=ADMIN).status_code == 200
    assert c.get("/api/pagos/99", headers=ADMIN).status_code == 404


def test_reembolso_solo_admin(c, monkeypatch):
    monkeypatch.setattr(pagos_app.repository, "reembolsar", lambda i: None)
    assert c.delete("/api/pagos/4", headers=USER2).status_code == 403
    assert c.delete("/api/pagos/4", headers=ADMIN).status_code == 200
