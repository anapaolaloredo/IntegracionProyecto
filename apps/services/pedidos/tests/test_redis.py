import time

import app as pedidos_app
from common import redis_store, testing
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, decodificar
from common.testing import auth_header
from common.web import Conflicto

USER = auth_header(2, ROLE_USER)
PEDIDO = {"id_pedido": 10, "id_cuenta": 2, "estado": "pendiente", "total": 5.0, "fecha_creacion": None,
          "lineas": []}


def _c():
    pedidos_app.app.config["TESTING"] = True
    return pedidos_app.app.test_client()


def test_token_revocado_da_401():
    jti = decodificar(USER["Authorization"].split()[1])["jti"]
    redis_store.revocar_jti(jti, int(time.time()) + 60)
    assert _c().post("/api/pedidos", json={}, headers=USER).status_code == 401


def test_redis_caido_rutas_protegidas_503_y_health_informa(redis_falso, monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    c = _c()
    testing.redis_caido(redis_falso)
    assert c.get("/api/pedidos", headers=USER).status_code == 503
    assert c.post("/api/pedidos", json={"lineas": [{"id_libro": 1, "cantidad": 1}]}, headers=USER).status_code == 503
    h = c.get("/health")
    assert h.status_code == 200 and h.get_json()["redis"] == "error"


def test_crear_pedido_invalida_cache_del_catalogo(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pedidos_app.repository, "crear", lambda *a: 11)
    monkeypatch.setattr(pedidos_app.repository, "obtener", lambda i: dict(PEDIDO, id_pedido=i))
    monkeypatch.setattr(pedidos_app.redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    resp = _c().post("/api/pedidos", json={"lineas": [{"id_libro": 1, "cantidad": 1}]}, headers=USER)
    assert resp.status_code == 201 and llamadas == [1]


def test_crear_pedido_fallido_no_invalida(monkeypatch):
    llamadas = []

    def sin_stock(*a):
        raise Conflicto("Stock insuficiente")

    monkeypatch.setattr(pedidos_app.repository, "crear", sin_stock)
    monkeypatch.setattr(pedidos_app.redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    resp = _c().post("/api/pedidos", json={"lineas": [{"id_libro": 1, "cantidad": 1}]}, headers=USER)
    assert resp.status_code == 409 and llamadas == []


def test_cancelar_invalida_pero_enviar_no(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pedidos_app.repository, "cambiar_estado", lambda *a: None)
    monkeypatch.setattr(pedidos_app.redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    c = _c()
    assert c.patch("/api/pedidos/10/estado", json={"estado": "cancelado"}, headers=USER).status_code == 200
    assert llamadas == [1]
    assert c.patch("/api/pedidos/10/estado", json={"estado": "enviado"},
                   headers=auth_header(1, ROLE_ADMIN)).status_code == 200
    assert llamadas == [1]


def test_invalidar_cache_con_redis_caido_no_rompe_el_pedido(redis_falso, monkeypatch):
    # la invalidacion es fail-open, pero con Redis caido requiere_jwt ya devuelve 503 antes:
    # se prueba la funcion directamente
    testing.redis_caido(redis_falso)
    redis_store.cache_invalidar_libros()  # no lanza
