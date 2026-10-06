import time

import pytest

from common import metrics, redis_store, testing
from common.redis_store import RedisNoDisponible


def test_revocar_y_consultar_jti():
    assert redis_store.jti_revocado("abc") is False
    redis_store.revocar_jti("abc", int(time.time()) + 100)
    assert redis_store.jti_revocado("abc") is True


def test_revocacion_tiene_ttl_igual_a_la_vida_restante():
    redis_store.revocar_jti("abc", int(time.time()) + 100)
    assert 95 <= redis_store.cliente().ttl("jwt:revoked:abc") <= 100


def test_revocar_token_ya_vencido_usa_ttl_minimo_de_1():
    redis_store.revocar_jti("viejo", int(time.time()) - 50)
    assert 1 <= redis_store.cliente().ttl("jwt:revoked:viejo") <= 2


def test_sesion_ida_vuelta_con_ttl_y_borrado():
    redis_store.guardar_sesion("j1", {"user_id": 5, "jti_refresh": "r1"}, 1800)
    assert redis_store.obtener_sesion("j1") == {"user_id": 5, "jti_refresh": "r1"}
    assert 1790 <= redis_store.cliente().ttl("session:j1") <= 1800
    redis_store.borrar_sesion("j1")
    assert redis_store.obtener_sesion("j1") is None


def test_refresh_ida_vuelta_con_ttl_y_borrado():
    assert redis_store.refresh_vigente("r1") is False
    redis_store.guardar_refresh("r1", 5, 604800)
    assert redis_store.refresh_vigente("r1") is True
    assert 604790 <= redis_store.cliente().ttl("refresh:r1") <= 604800
    redis_store.borrar_refresh("r1")
    assert redis_store.refresh_vigente("r1") is False


@pytest.mark.parametrize("llamada", [
    lambda: redis_store.jti_revocado("a"),
    lambda: redis_store.revocar_jti("a", int(time.time()) + 10),
    lambda: redis_store.guardar_sesion("a", {"x": 1}, 10),
    lambda: redis_store.obtener_sesion("a"),
    lambda: redis_store.borrar_sesion("a"),
    lambda: redis_store.guardar_refresh("a", 1, 10),
    lambda: redis_store.refresh_vigente("a"),
    lambda: redis_store.borrar_refresh("a"),
])
def test_operaciones_de_sesion_fallan_cerrado_si_redis_cae(redis_falso, llamada):
    testing.redis_caido(redis_falso)
    with pytest.raises(RedisNoDisponible):
        llamada()


def test_redis_caido_cuenta_errores_en_metricas(redis_falso):
    testing.redis_caido(redis_falso)
    with pytest.raises(RedisNoDisponible):
        redis_store.jti_revocado("a")
    assert "redis_errors_total" in metrics.render("t")


def test_sin_redis_url_falla_cerrado(monkeypatch):
    redis_store.reiniciar()
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RedisNoDisponible):
        redis_store.jti_revocado("a")
    assert redis_store.estado() == "no_configurado"


def test_cache_get_set_y_ttl_por_defecto():
    assert redis_store.cache_get("books:123") is None
    redis_store.cache_set("books:123", "{}")
    assert redis_store.cache_get("books:123") == "{}"
    assert 55 <= redis_store.cliente().ttl("books:123") <= redis_store.CACHE_TTL_SEGUNDOS


def test_cache_cuenta_hits_y_misses():
    metrics.reiniciar()
    redis_store.cache_get("books:x")
    redis_store.cache_set("books:x", "v")
    redis_store.cache_get("books:x")
    texto = metrics.render("t")
    assert "cache_misses_total" in texto and "cache_hits_total" in texto


def test_cache_invalidar_libros_borra_solo_books():
    redis_store.cache_set("books:1", "a")
    redis_store.cache_set("books:list:abc", "b")
    redis_store.guardar_sesion("j", {"a": 1}, 100)
    redis_store.cache_invalidar_libros()
    assert redis_store.cache_get("books:1") is None
    assert redis_store.cache_get("books:list:abc") is None
    assert redis_store.obtener_sesion("j") == {"a": 1}


def test_cache_falla_abierto_si_redis_cae(redis_falso):
    testing.redis_caido(redis_falso)
    assert redis_store.cache_get("books:1") is None      # sin excepcion
    redis_store.cache_set("books:1", "x")                 # sin excepcion
    redis_store.cache_invalidar_libros()                  # sin excepcion
    assert "redis_errors_total" in metrics.render("t")


def test_estado_ok_y_error(redis_falso):
    assert redis_store.estado() == "ok"
    testing.redis_caido(redis_falso)
    assert redis_store.estado() == "error"


def test_url_enmascarada_oculta_la_contrasena():
    assert redis_store.url_enmascarada("redis://:s3cr3t@host:6379/0") == "redis://:***@host:6379/0"
    assert redis_store.url_enmascarada("redis://user:s3cr3t@host:6379/0") == "redis://user:***@host:6379/0"
    assert "s3cr3t" not in redis_store.url_enmascarada("rediss://:s3cr3t@h/0")
