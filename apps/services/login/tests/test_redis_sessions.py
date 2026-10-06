from unittest.mock import patch

import app as login_app
import service
from common import redis_store, testing
from common.jwt_auth import ROLE_USER, crear_token
from tests.test_jwt_service import USUARIO, _login


def _c():
    login_app.app.config["TESTING"] = True
    return login_app.app.test_client()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_flujo_http_completo_login_session_extend_refresh_logout():
    c = _c()
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        assert c.get("/session?format=json", headers=_bearer(tokens["session_token"])).get_json()["autenticado"] is True
        nuevo = c.post("/session/extend?format=json", headers=_bearer(tokens["session_token"])).get_json()
        assert nuevo["session_token"]
        refrescado = c.post("/session/refresh?format=json", json={"refresh_token": tokens["refresh_token"]})
        assert refrescado.status_code == 200
        assert c.post("/logout?format=json", headers=_bearer(nuevo["session_token"])).status_code == 200
        assert c.get("/session?format=json", headers=_bearer(nuevo["session_token"])).get_json() == {"autenticado": False}
        assert c.post("/session/refresh?format=json",
                      json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_redis_caido_rutas_de_sesion_dan_503(redis_falso):
    c = _c()
    tokens = _login()
    testing.redis_caido(redis_falso)
    token = tokens["session_token"]
    assert c.get("/session?format=json", headers=_bearer(token)).status_code == 503
    assert c.post("/session/extend?format=json", headers=_bearer(token)).status_code == 503
    assert c.post("/session/refresh?format=json", json={"refresh_token": tokens["refresh_token"]}).status_code == 503
    assert c.post("/logout?format=json", headers=_bearer(token)).status_code == 503


def test_redis_caido_login_verify_da_503_sin_tokens_y_sin_quemar_el_codigo(redis_falso):
    c = _c()
    testing.redis_caido(redis_falso)
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=dict(USUARIO)), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado") as usado, \
         patch.object(service, "verificar_codigo", return_value=True):
        resp = c.post("/login/verify?format=json", json={"email": "a@b.co", "codigo": "123456"})
    assert resp.status_code == 503
    assert "session_token" not in resp.get_data(as_text=True)
    usado.assert_not_called()


def test_rutas_publicas_siguen_funcionando_con_redis_caido(redis_falso):
    c = _c()
    testing.redis_caido(redis_falso)
    with patch.object(service, "registrar", return_value=7), \
         patch.object(service, "iniciar_login", return_value=None), \
         patch.object(service, "verificar_salud", return_value=True):
        r = c.post("/register?format=json", json={"nombre": "A", "apellido_paterno": "B",
                                                   "apellido_materno": "C", "email": "a@b.co",
                                                   "password": "secreta123"})
        assert r.status_code == 201
        assert c.post("/login?format=json", json={"email": "a@b.co", "password": "secreta123"}).status_code == 200
        h = c.get("/health?format=json")
        assert h.status_code == 200 and h.get_json()["redis"] == "error" and h.get_json()["db"] == "ok"


def test_health_ok_y_metrics_publicos():
    c = _c()
    with patch.object(service, "verificar_salud", return_value=True):
        assert c.get("/health?format=json").get_json() == {"status": "ok", "db": "ok", "redis": "ok"}
    assert c.get("/metrics").status_code == 200


def test_la_contrasena_de_redis_no_sale_en_health_ni_metrics(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://:SuperSecreta99@localhost:6379/0")
    c = _c()
    with patch.object(service, "verificar_salud", return_value=True):
        assert "SuperSecreta99" not in c.get("/health?format=json").get_data(as_text=True)
    assert "SuperSecreta99" not in c.get("/metrics").get_data(as_text=True)
