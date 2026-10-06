import pytest

import app as pedidos_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header

ADMIN = auth_header(1, ROLE_ADMIN)
USER2 = auth_header(2, ROLE_USER)
USER3 = auth_header(3, ROLE_USER)
PEDIDO = {"id_pedido": 10, "id_cuenta": 2, "estado": "pendiente", "total": 100.0, "fecha_creacion": None,
          "lineas": []}


@pytest.fixture
def c(monkeypatch):
    pedidos_app.app.config["TESTING"] = True
    r = pedidos_app.repository
    monkeypatch.setattr(r, "obtener", lambda i: dict(PEDIDO) if i == 10 else None)
    return pedidos_app.app.test_client()


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/pedidos"), ("patch", "/api/pedidos/10/estado"),
    ("put", "/api/pedidos/10/estado"), ("delete", "/api/pedidos/10"),
])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


def test_lecturas_exigen_jwt(c):
    assert c.get("/api/pedidos").status_code == 401
    assert c.get("/api/pedidos/10").status_code == 401


def test_crear_pedido_fusiona_lineas_duplicadas(c, monkeypatch):
    visto = {}

    def crear(id_cuenta, items):
        visto.update(id_cuenta=id_cuenta, items=items)
        return 11

    monkeypatch.setattr(pedidos_app.repository, "crear", crear)
    monkeypatch.setattr(pedidos_app.repository, "obtener", lambda i: dict(PEDIDO, id_pedido=i))
    cuerpo = {"lineas": [{"id_libro": 5, "cantidad": 1}, {"id_libro": 5, "cantidad": 2},
                         {"id_libro": 3, "cantidad": 4}]}
    resp = c.post("/api/pedidos", json=cuerpo, headers=USER2)
    assert resp.status_code == 201 and resp.get_json()["id_pedido"] == 11
    assert visto == {"id_cuenta": 2, "items": [(3, 4), (5, 3)]}


@pytest.mark.parametrize("lineas", [
    [], None, "x", [{}], [{"id_libro": 1}], [{"id_libro": 1, "cantidad": 0}],
    [{"id_libro": 1, "cantidad": -2}], [{"id_libro": 1, "cantidad": 1.5}],
    [{"id_libro": 1, "cantidad": True}], [{"id_libro": "1", "cantidad": 1}], [7],
])
def test_crear_pedido_rechaza_lineas_invalidas(c, monkeypatch, lineas):
    llamado = []
    monkeypatch.setattr(pedidos_app.repository, "crear", lambda *a: llamado.append(a))
    assert c.post("/api/pedidos", json={"lineas": lineas}, headers=USER2).status_code == 400
    assert not llamado  # no se toco el stock


def test_listar_user_ve_solo_lo_suyo_y_admin_todo(c, monkeypatch):
    pedidos = []
    monkeypatch.setattr(pedidos_app.repository, "listar", lambda id_cuenta=None: pedidos.append(id_cuenta) or [])
    c.get("/api/pedidos", headers=USER2)
    c.get("/api/pedidos", headers=ADMIN)
    assert pedidos == [2, None]


def test_ver_pedido_ajeno_403_y_propio_200(c):
    assert c.get("/api/pedidos/10", headers=USER2).status_code == 200
    assert c.get("/api/pedidos/10", headers=USER3).status_code == 403
    assert c.get("/api/pedidos/10", headers=ADMIN).status_code == 200
    assert c.get("/api/pedidos/99", headers=ADMIN).status_code == 404


def test_cambiar_estado_invoca_repositorio_con_actor(c, monkeypatch):
    visto = []
    monkeypatch.setattr(pedidos_app.repository, "cambiar_estado", lambda *a: visto.append(a))
    resp = c.patch("/api/pedidos/10/estado", json={"estado": "cancelado"}, headers=USER2)
    assert resp.status_code == 200 and visto == [(10, "cancelado", 2, False)]
    assert c.put("/api/pedidos/10/estado", json={"estado": "enviado"}, headers=ADMIN).status_code == 200
    assert c.patch("/api/pedidos/10/estado", json={"estado": 5}, headers=USER2).status_code == 400


def test_eliminar_solo_admin(c, monkeypatch):
    monkeypatch.setattr(pedidos_app.repository, "eliminar", lambda i: None)
    assert c.delete("/api/pedidos/10", headers=USER2).status_code == 403
    assert c.delete("/api/pedidos/10", headers=ADMIN).status_code == 200
