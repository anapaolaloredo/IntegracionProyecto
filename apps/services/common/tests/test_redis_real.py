"""Pruebas opcionales contra el Redis real de GCP.

Estos tests se saltan por defecto a menos que REDIS_REAL_URL esté definida.
Se pueden ejecutar en la instancia de GCP con (del directorio apps/services):

  read -rs REDIS_PW
  export REDIS_REAL_URL="redis://:${REDIS_PW}@localhost:6379/0"
  login/.venv/bin/python -m pytest common/tests/test_redis_real.py -q

(Redis solo escucha en localhost de la instancia de GCP, por lo que estas
pruebas no se pueden ejecutar desde la máquina local.)
"""

import os
import time
import urllib.parse
import uuid

import pytest
import redis

from common import redis_store

URL = os.getenv("REDIS_REAL_URL")
pytestmark = pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")


@pytest.fixture
def real(monkeypatch):
    redis_store.reiniciar()
    monkeypatch.setenv("REDIS_URL", URL)
    yield redis_store
    redis_store.reiniciar()


@pytest.fixture
def cleanup_jti(real):
    """Limpia todas las claves zz-test-* creadas durante la prueba, incluso si falla."""
    jtis = []
    yield jtis
    for jti in jtis:
        try:
            real.cliente().delete(f"jwt:revoked:{jti}")
            real.cliente().delete(f"session:{jti}")
            real.cliente().delete(f"refresh:{jti}")
        except redis.RedisError:
            pass


def test_ping_y_estado_ok(real):
    assert real.estado() == "ok"


def test_revocacion_con_ttl_real(cleanup_jti):
    jti = "zz-test-" + uuid.uuid4().hex
    cleanup_jti.append(jti)
    assert redis_store.jti_revocado(jti) is False
    redis_store.revocar_jti(jti, int(time.time()) + 30)
    assert redis_store.jti_revocado(jti) is True
    assert 1 <= redis_store.cliente().ttl("jwt:revoked:" + jti) <= 30


def test_sesion_y_refresh_con_ttl_real(cleanup_jti):
    jti = "zz-test-" + uuid.uuid4().hex
    cleanup_jti.append(jti)
    redis_store.guardar_sesion(jti, {"user_id": 1, "jti_refresh": "r"}, 30)
    redis_store.guardar_refresh(jti, 1, 30)
    assert redis_store.obtener_sesion(jti)["user_id"] == 1 and redis_store.refresh_vigente(jti) is True
    redis_store.borrar_sesion(jti)
    redis_store.borrar_refresh(jti)
    assert redis_store.obtener_sesion(jti) is None and redis_store.refresh_vigente(jti) is False


def test_politica_noeviction_configurada(real):
    try:
        politica = real.cliente().config_get("maxmemory-policy").get("maxmemory-policy")
    except redis.ResponseError:
        pytest.skip("CONFIG GET no disponible en este Redis: verificar maxmemory-policy a mano")
    assert politica == "noeviction", f"el Redis de GCP usa {politica}; se recomienda noeviction"


def test_sin_contrasena_es_rechazado(real):
    parsed = urllib.parse.urlsplit(URL)

    # Validar que la URL tiene userinfo (para una prueba significativa)
    if not parsed.username:
        pytest.skip("la URL no trae contraseña; un Redis sin requirepass es un hallazgo de seguridad")

    # Construir URL sin contraseña (manteniendo scheme, host, port, db)
    sin_pass = urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.hostname if parsed.hostname else parsed.netloc.split("@")[-1],
        parsed.path,
        parsed.query,
        parsed.fragment
    ))
    if parsed.port:
        sin_pass = sin_pass.replace(f"://{parsed.hostname}", f"://{parsed.hostname}:{parsed.port}", 1)

    cliente = redis.Redis.from_url(sin_pass, socket_timeout=2, socket_connect_timeout=2)
    try:
        resultado = cliente.ping()
        pytest.fail("Redis acepta conexiones sin contraseña")
    except redis.AuthenticationError:
        pass  # Esperado: autenticación rechazada
    except redis.ResponseError as e:
        if "NOAUTH" in str(e).upper() or "Authentication required" in str(e):
            pass  # Esperado: autenticación rechazada
        else:
            raise  # Otro error de respuesta, no es autenticación
    except redis.ConnectionError:
        pytest.fail("Redis no es alcanzable")
    except redis.TimeoutError:
        pytest.fail("Timeout al conectar a Redis")
    except redis.RedisError as e:
        if isinstance(e, (redis.ConnectionError, redis.TimeoutError)):
            pytest.fail("Redis no es alcanzable")
        raise  # Otro tipo de error
    finally:
        try:
            cliente.close()
        except Exception:
            pass


def test_url_enmascarada_no_filtra_la_contrasena(real):
    clave = urllib.parse.urlsplit(URL).password
    if not clave:
        pytest.skip("la URL no trae contraseña")

    enmascarada = real.url_enmascarada(URL)
    fuga = clave in enmascarada
    assert not fuga, "la contraseña aparece en la URL enmascarada"
