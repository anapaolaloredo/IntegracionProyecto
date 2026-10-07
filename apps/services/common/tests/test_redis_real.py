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


def url_sin_userinfo(url):
    """
    Construye una URL quitando el userinfo (usuario:contraseña).

    Ejemplos:
    - redis://:s3cr3t@localhost:6379/0 -> redis://localhost:6379/0
    - rediss://:s3cr3t@[::1]:6380/2 -> rediss://[::1]:6380/2
    - redis://localhost:6379/0 -> None (sin userinfo, nada que quitar)

    Args:
        url: URL a procesar

    Returns:
        URL sin userinfo, o None si la URL no tiene userinfo
    """
    parsed = urllib.parse.urlsplit(url)

    # Si no hay userinfo (username o password), no hay nada que quitar
    if not parsed.username and not parsed.password:
        return None

    # Extraer la parte host:port sin userinfo usando rpartition
    # Esto preserva IPv6 brackets, case, y port exactamente como en la URL original
    host_port = parsed.netloc.rpartition("@")[2]

    # Reconstruir la URL sin userinfo
    nuevo_netloc = host_port
    nueva_url = urllib.parse.urlunsplit((
        parsed.scheme,
        nuevo_netloc,
        parsed.path,
        parsed.query,
        parsed.fragment
    ))
    return nueva_url


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


# Tests puros de lógica URL (sin skipif de módulo, siempre se ejecutan)
def test_url_sin_userinfo_basico():
    """Prueba de lógica pura: URL estándar con contraseña."""
    resultado = url_sin_userinfo("redis://:s3cr3t@localhost:6379/0")
    assert resultado == "redis://localhost:6379/0"


def test_url_sin_userinfo_ipv6():
    """Prueba de lógica pura: IPv6 con puerto personalizado."""
    resultado = url_sin_userinfo("rediss://:s3cr3t@[::1]:6380/2")
    assert resultado == "rediss://[::1]:6380/2"


def test_url_sin_userinfo_sin_userinfo():
    """Prueba de lógica pura: URL sin userinfo retorna None."""
    resultado = url_sin_userinfo("redis://localhost:6379/0")
    assert resultado is None


# Tests que tocan Redis (se saltan si REDIS_REAL_URL no está definida)
@pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")
def test_ping_y_estado_ok(real):
    assert real.estado() == "ok"


@pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")
def test_revocacion_con_ttl_real(cleanup_jti):
    jti = "zz-test-" + uuid.uuid4().hex
    cleanup_jti.append(jti)
    assert redis_store.jti_revocado(jti) is False
    redis_store.revocar_jti(jti, int(time.time()) + 30)
    assert redis_store.jti_revocado(jti) is True
    assert 1 <= redis_store.cliente().ttl("jwt:revoked:" + jti) <= 30


@pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")
def test_sesion_y_refresh_con_ttl_real(cleanup_jti):
    jti = "zz-test-" + uuid.uuid4().hex
    cleanup_jti.append(jti)
    redis_store.guardar_sesion(jti, {"user_id": 1, "jti_refresh": "r"}, 30)
    redis_store.guardar_refresh(jti, 1, 30)
    assert redis_store.obtener_sesion(jti)["user_id"] == 1 and redis_store.refresh_vigente(jti) is True
    redis_store.borrar_sesion(jti)
    redis_store.borrar_refresh(jti)
    assert redis_store.obtener_sesion(jti) is None and redis_store.refresh_vigente(jti) is False


@pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")
def test_politica_noeviction_configurada(real):
    try:
        politica = real.cliente().config_get("maxmemory-policy").get("maxmemory-policy")
    except redis.ResponseError:
        pytest.skip("CONFIG GET no disponible en este Redis: verificar maxmemory-policy a mano")
    assert politica == "noeviction", f"el Redis de GCP usa {politica}; se recomienda noeviction"


@pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")
def test_sin_contrasena_es_rechazado(real):
    parsed = urllib.parse.urlsplit(URL)

    # Guardar la URL sin userinfo; si retorna None, significa que la URL original no tiene contraseña
    sin_pass = url_sin_userinfo(URL)
    if sin_pass is None:
        pytest.skip("la URL no trae contraseña")

    cliente = redis.Redis.from_url(sin_pass, socket_timeout=2, socket_connect_timeout=2)
    try:
        cliente.ping()
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
    except redis.RedisError:
        raise  # Otro tipo de error
    finally:
        try:
            cliente.close()
        except Exception:
            pass


@pytest.mark.skipif(not URL, reason="define REDIS_REAL_URL para probar contra Redis real")
def test_url_enmascarada_no_filtra_la_contrasena(real):
    clave = urllib.parse.urlsplit(URL).password
    if not clave:
        pytest.skip("la URL no trae contraseña")

    enmascarada = real.url_enmascarada(URL)
    fuga = clave in enmascarada
    assert not fuga, "la contraseña aparece en la URL enmascarada"
