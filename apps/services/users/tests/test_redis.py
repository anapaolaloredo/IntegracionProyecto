import time

import app as users_app
from common import redis_store, testing
from common.jwt_auth import ROLE_ADMIN, decodificar
from common.testing import auth_header


def _c():
    users_app.app.config["TESTING"] = True
    return users_app.app.test_client()


def test_token_revocado_da_401():
    headers = auth_header(1, ROLE_ADMIN)
    jti = decodificar(headers["Authorization"].split()[1])["jti"]
    redis_store.revocar_jti(jti, int(time.time()) + 60)
    assert _c().get("/api/users", headers=headers).status_code == 401
    assert _c().post("/api/users", json={}, headers=headers).status_code == 401


def test_redis_caido_rutas_protegidas_503_y_publicas_siguen(redis_falso, monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    c = _c()
    testing.redis_caido(redis_falso)
    assert c.get("/api/users", headers=auth_header(1, ROLE_ADMIN)).status_code == 503
    assert c.post("/api/users", json={}, headers=auth_header(1, ROLE_ADMIN)).status_code == 503
    assert c.get("/api/roles").status_code == 200
    h = c.get("/health")
    assert h.status_code == 200 and h.get_json()["redis"] == "error" and h.get_json()["servicio"] == "users"


def test_health_y_metrics_son_publicos(monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    c = _c()
    assert c.get("/health").get_json()["status"] == "ok"
    assert c.get("/metrics").status_code == 200


def test_health_bd_caida_da_503(monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: False)
    assert _c().get("/health").status_code == 503
