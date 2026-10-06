import time

import app as pagos_app
from common import redis_store, testing
from common.jwt_auth import ROLE_USER, decodificar
from common.testing import auth_header

USER = auth_header(2, ROLE_USER)
PAGO = {"id_pago": 4, "id_pedido": 10, "id_cuenta": 2, "monto": 100.0, "metodo": "tarjeta", "fecha_pago": None}


def _c():
    pagos_app.app.config["TESTING"] = True
    return pagos_app.app.test_client()


def test_token_revocado_da_401():
    jti = decodificar(USER["Authorization"].split()[1])["jti"]
    redis_store.revocar_jti(jti, int(time.time()) + 60)
    assert _c().post("/api/pagos", json={}, headers=USER).status_code == 401


def test_redis_caido_rutas_protegidas_503_y_health_informa(redis_falso, monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    c = _c()
    testing.redis_caido(redis_falso)
    assert c.get("/api/pagos", headers=USER).status_code == 503
    assert c.post("/api/pagos", json={"id_pedido": 10, "metodo": "tarjeta"}, headers=USER).status_code == 503
    h = c.get("/health")
    assert h.status_code == 200
    assert h.get_json()["redis"] == "error" and h.get_json()["servicio"] == "pagos"


def test_pago_no_invalida_cache(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pagos_app.repository, "registrar", lambda *a: dict(PAGO))
    monkeypatch.setattr(redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    resp = _c().post("/api/pagos", json={"id_pedido": 10, "metodo": "tarjeta"}, headers=USER)
    assert resp.status_code == 201 and llamadas == []
