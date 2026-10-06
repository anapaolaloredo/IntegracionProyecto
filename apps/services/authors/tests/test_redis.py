import time

import app as authors_app
from common import redis_store, testing
from common.jwt_auth import ROLE_ADMIN, decodificar
from common.testing import auth_header


def _c():
    authors_app.app.config["TESTING"] = True
    return authors_app.app.test_client()


def test_token_revocado_da_401():
    headers = auth_header(1, ROLE_ADMIN)
    jti = decodificar(headers["Authorization"].split()[1])["jti"]
    redis_store.revocar_jti(jti, int(time.time()) + 60)
    assert _c().post("/api/authors", json={"nombre_autor": "X"}, headers=headers).status_code == 401


def test_redis_caido_rutas_protegidas_503_y_publicas_siguen(redis_falso, monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    monkeypatch.setattr(authors_app.repository, "listar", lambda: [])
    c = _c()
    testing.redis_caido(redis_falso)
    r = c.post("/api/authors", json={"nombre_autor": "X"}, headers=auth_header(1, ROLE_ADMIN))
    assert r.status_code == 503
    assert c.get("/api/authors").status_code == 200
    h = c.get("/health")
    assert h.status_code == 200 and h.get_json()["redis"] == "error" and h.get_json()["servicio"] == "authors"


def test_health_y_metrics_son_publicos(monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    c = _c()
    assert c.get("/health").get_json()["status"] == "ok"
    assert c.get("/metrics").status_code == 200


def test_health_bd_caida_da_503(monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: False)
    assert _c().get("/health").status_code == 503
