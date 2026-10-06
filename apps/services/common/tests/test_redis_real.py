"""Pruebas opcionales contra el Redis real de GCP.

Estos tests se saltan por defecto a menos que REDIS_REAL_URL esté definida.
Se pueden ejecutar en la instancia de GCP con:

  REDIS_REAL_URL=redis://:<password>@localhost:6379/0 .venv/bin/python -m pytest common/tests/test_redis_real.py -q

(Redis solo escucha en localhost de la instancia de GCP, por lo que estas
pruebas no se pueden ejecutar desde la máquina local.)
"""

import os
import time
import uuid

import pytest
import redis

from common import redis_store

URL = os.getenv("REDIS_REAL_URL")
pytestmark = pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")


@pytest.fixture
def real():
    redis_store.reiniciar()
    os.environ["REDIS_URL"] = URL
    yield redis_store
    redis_store.reiniciar()
    os.environ.pop("REDIS_URL", None)


def test_ping_y_estado_ok(real):
    assert real.estado() == "ok"


def test_revocacion_con_ttl_real(real):
    jti = "zz-test-" + uuid.uuid4().hex
    assert real.jti_revocado(jti) is False
    real.revocar_jti(jti, int(time.time()) + 30)
    assert real.jti_revocado(jti) is True
    assert 1 <= real.cliente().ttl("jwt:revoked:" + jti) <= 30
    real.cliente().delete("jwt:revoked:" + jti)


def test_sesion_y_refresh_con_ttl_real(real):
    jti = "zz-test-" + uuid.uuid4().hex
    real.guardar_sesion(jti, {"user_id": 1, "jti_refresh": "r"}, 30)
    real.guardar_refresh(jti, 1, 30)
    assert real.obtener_sesion(jti)["user_id"] == 1 and real.refresh_vigente(jti) is True
    real.borrar_sesion(jti)
    real.borrar_refresh(jti)
    assert real.obtener_sesion(jti) is None and real.refresh_vigente(jti) is False


def test_politica_noeviction_configurada(real):
    politica = real.cliente().config_get("maxmemory-policy").get("maxmemory-policy")
    assert politica == "noeviction", f"el Redis de GCP usa {politica}; se recomienda noeviction"


def test_sin_contrasena_es_rechazado(real):
    sin_pass = URL.split("://", 1)[0] + "://" + URL.split("@", 1)[-1]
    cliente = redis.Redis.from_url(sin_pass, socket_timeout=2, socket_connect_timeout=2)
    with pytest.raises(redis.RedisError):
        cliente.ping()  # un Redis sin requirepass respondería PONG: eso es un hallazgo de seguridad


def test_url_enmascarada_no_filtra_la_contrasena(real):
    clave = URL.split("://", 1)[1].split("@", 1)[0].split(":", 1)[-1]
    assert clave not in real.url_enmascarada(URL)
