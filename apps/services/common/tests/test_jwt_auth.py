import base64
import json
import os
import time

import jwt
import pytest
from flask import Flask, g, jsonify

from common import jwt_auth
from common.jwt_auth import (
    ROLE_ADMIN, ROLE_USER, TokenInvalido, crear_token, decodificar,
    extraer_token, requiere_jwt,
)


def _b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def test_ida_y_vuelta():
    datos = decodificar(crear_token(7, ROLE_USER, "access", 60))
    assert datos["user_id"] == 7 and datos["role_id"] == ROLE_USER and datos["type"] == "access"


def test_expirado_se_rechaza():
    with pytest.raises(TokenInvalido):
        decodificar(crear_token(1, ROLE_USER, "access", -10))


def test_firma_con_otra_clave_se_rechaza():
    ahora = int(time.time())
    falso = jwt.encode({"user_id": 1, "role_id": 1, "type": "access", "jti": "abc123", "iat": ahora, "exp": ahora + 60},
                       "otra-clave-distinta-de-32-bytes-0123456789", algorithm="HS256")
    with pytest.raises(TokenInvalido):
        decodificar(falso)


def test_alg_none_se_rechaza():
    ahora = int(time.time())
    payload = {"user_id": 1, "role_id": 1, "type": "access", "jti": "abc123", "iat": ahora, "exp": ahora + 60}
    sin_firma = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(payload)}."
    with pytest.raises(TokenInvalido):
        decodificar(sin_firma)


def test_alg_distinto_hs512_se_rechaza():
    ahora = int(time.time())
    token = jwt.encode({"user_id": 1, "role_id": 1, "type": "access", "jti": "abc123", "iat": ahora, "exp": ahora + 60},
                       jwt_auth.obtener_secret(), algorithm="HS512")
    with pytest.raises(TokenInvalido):
        decodificar(token)


def test_refresh_no_vale_como_acceso_ni_al_reves():
    with pytest.raises(TokenInvalido):
        decodificar(crear_token(1, ROLE_USER, "refresh", 60), "access")
    with pytest.raises(TokenInvalido):
        decodificar(crear_token(1, ROLE_USER, "access", 60), "refresh")


@pytest.mark.parametrize("user_id,role_id", [("1", 2), (True, 2), (1, 3), (1, "1"), (1, [1])])
def test_claims_invalidos_se_rechazan(user_id, role_id):
    ahora = int(time.time())
    token = jwt.encode({"user_id": user_id, "role_id": role_id, "type": "access", "jti": "abc123", "iat": ahora, "exp": ahora + 60},
                       jwt_auth.obtener_secret(), algorithm="HS256")
    with pytest.raises(TokenInvalido):
        decodificar(token)


def test_falta_claim_obligatorio():
    ahora = int(time.time())
    token = jwt.encode({"user_id": 1, "type": "access", "jti": "abc123", "iat": ahora, "exp": ahora + 60},
                       jwt_auth.obtener_secret(), algorithm="HS256")
    with pytest.raises(TokenInvalido):
        decodificar(token)


def test_sin_secret_key_falla(monkeypatch):
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(RuntimeError):
        crear_token(1, 2, "access", 60)


@pytest.mark.parametrize("valor,esperado", [
    ("Bearer abc", "abc"), ("bearer abc", "abc"), ("Bearer", None), ("Bearer  ", None),
    ("Token abc", None), ("", None), (None, None), ("Bearer a b", None),
])
def test_extraer_token(valor, esperado):
    assert extraer_token(valor) == esperado


@pytest.fixture
def cliente():
    app = Flask(__name__)

    @app.route("/abierta", methods=["POST"])
    @requiere_jwt()
    def abierta():
        return jsonify(user_id=g.user_id, role_id=g.role_id)

    @app.route("/admin", methods=["POST"])
    @requiere_jwt(roles=[ROLE_ADMIN])
    def admin():
        return jsonify(ok=True)

    return app.test_client()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_decorador_sin_token_401(cliente):
    assert cliente.post("/abierta").status_code == 401


def test_decorador_token_malo_401(cliente):
    assert cliente.post("/abierta", headers=_h("basura")).status_code == 401


def test_decorador_refresh_como_acceso_401(cliente):
    assert cliente.post("/abierta", headers=_h(crear_token(1, 2, "refresh", 60))).status_code == 401


def test_decorador_deja_claims_en_g(cliente):
    resp = cliente.post("/abierta", headers=_h(crear_token(9, ROLE_USER, "access", 60)))
    assert resp.status_code == 200 and resp.get_json() == {"user_id": 9, "role_id": 2}


def test_decorador_rol_insuficiente_403(cliente):
    assert cliente.post("/admin", headers=_h(crear_token(1, ROLE_USER, "access", 60))).status_code == 403


def test_decorador_admin_pasa(cliente):
    assert cliente.post("/admin", headers=_h(crear_token(1, ROLE_ADMIN, "access", 60))).status_code == 200


def test_on_event_recibe_resultado_y_error_response_personalizado():
    app = Flask(__name__)
    eventos = []

    @app.route("/x", methods=["POST"])
    @requiere_jwt(error_response=lambda m, s: (f"<e>{m}</e>", s), on_event=lambda *a: eventos.append(a))
    def x():
        return "ok"

    c = app.test_client()
    resp = c.post("/x")
    assert resp.status_code == 401 and resp.data.startswith(b"<e>")
    assert eventos[-1][2][0] == 401
    c.post("/x", headers=_h(crear_token(1, 2, "access", 60)))
    assert eventos[-1][2] is None


def test_secret_de_ejemplo_se_rechaza(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "Change-Me-same-value-in-every-service")
    with pytest.raises(RuntimeError) as exc:
        jwt_auth.obtener_secret()
    assert "Change-Me" not in str(exc.value)


def test_secret_de_31_caracteres_se_rechaza(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a" * 31)
    with pytest.raises(RuntimeError):
        jwt_auth.obtener_secret()


def test_secret_de_32_caracteres_se_acepta(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    assert jwt_auth.obtener_secret() == "a" * 32


import time as _time

from common import redis_store, testing
from common.redis_store import RedisNoDisponible


def test_tokens_llevan_jti_unico():
    a = decodificar(crear_token(1, ROLE_USER, "access", 60))
    b = decodificar(crear_token(1, ROLE_USER, "access", 60))
    assert a["jti"] and a["jti"] != b["jti"]


def test_jti_explicito():
    assert decodificar(crear_token(1, ROLE_USER, "access", 60, jti="fijo"))["jti"] == "fijo"


def test_token_sin_jti_se_rechaza():
    ahora = int(_time.time())
    token = jwt.encode({"user_id": 1, "role_id": 2, "type": "access", "iat": ahora, "exp": ahora + 60},
                       jwt_auth.obtener_secret(), algorithm="HS256")
    with pytest.raises(TokenInvalido):
        decodificar(token)


def test_jwt_secret_key_tiene_prioridad_y_secret_key_es_alias(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "otra-clave-distinta-de-32-bytes-0123456789")
    assert jwt_auth.obtener_secret() == "otra-clave-distinta-de-32-bytes-0123456789"
    monkeypatch.delenv("JWT_SECRET_KEY")
    assert jwt_auth.obtener_secret() == os.environ["SECRET_KEY"]


def test_jwt_secret_key_placeholder_o_corta_se_rechaza(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me-algo-muy-largo-pero-de-ejemplo")
    with pytest.raises(RuntimeError):
        jwt_auth.obtener_secret()
    monkeypatch.setenv("JWT_SECRET_KEY", "corta")
    with pytest.raises(RuntimeError):
        jwt_auth.obtener_secret()


def _flask_con_vista(**kw):
    app = Flask(__name__)

    @app.route("/x", methods=["POST"])
    @requiere_jwt(**kw)
    def x():
        return jsonify(ok=True)

    return app.test_client()


def test_token_revocado_da_401_en_el_decorador():
    token = crear_token(1, ROLE_USER, "access", 60, jti="rev1")
    redis_store.revocar_jti("rev1", decodificar(token)["exp"])
    resp = _flask_con_vista().post("/x", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401 and "revocado" in resp.get_json()["mensaje"].lower()


def test_revocado_gana_sobre_rol_insuficiente():
    token = crear_token(1, ROLE_USER, "access", 60, jti="rev2")
    redis_store.revocar_jti("rev2", decodificar(token)["exp"])
    resp = _flask_con_vista(roles=[ROLE_ADMIN]).post("/x", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_redis_caido_da_503_y_no_deja_pasar(redis_falso):
    testing.redis_caido(redis_falso)
    token = crear_token(1, ROLE_ADMIN, "access", 60)
    resp = _flask_con_vista().post("/x", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503


def test_sin_token_o_token_malo_no_consulta_redis(redis_falso):
    testing.redis_caido(redis_falso)  # si consultara Redis daria 503 en vez de 401
    c = _flask_con_vista()
    assert c.post("/x").status_code == 401
    assert c.post("/x", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_on_event_recibe_503_y_401_revocado(redis_falso):
    eventos = []
    c = _flask_con_vista(on_event=lambda t, d, r: eventos.append(r))
    token = crear_token(1, 2, "access", 60, jti="rev3")
    redis_store.revocar_jti("rev3", decodificar(token)["exp"])
    c.post("/x", headers={"Authorization": f"Bearer {token}"})
    testing.redis_caido(redis_falso)
    c.post("/x", headers={"Authorization": f"Bearer {crear_token(1, 2, 'access', 60)}"})
    assert [e[0] for e in eventos] == [401, 503]


def test_metricas_de_rechazo_por_revocacion():
    from common import metrics
    token = crear_token(1, 2, "access", 60, jti="rev4")
    redis_store.revocar_jti("rev4", decodificar(token)["exp"])
    _flask_con_vista().post("/x", headers={"Authorization": f"Bearer {token}"})
    assert 'jwt_rejected_total{motivo="revocado"' in metrics.render("t")
