"""Capa Redis compartida. PostgreSQL sigue siendo la fuente de datos; Redis guarda estado
temporal (sesiones, refresh tokens, jti revocados) y cache publica del catalogo.

Dos modos de uso:
- fail-closed (sesion, revocacion, autorizacion): cualquier fallo de Redis lanza
  RedisNoDisponible; el llamador responde 503 y NO acepta/emite tokens.
- fail-open (cache): el fallo se traga y se cuenta en metricas; el llamador va a PostgreSQL.

La contraseña de REDIS_URL nunca se registra: usar url_enmascarada()."""

import json
import os
import re
import threading
import time

import redis

from common import metrics

SESSION_TTL_SEGUNDOS = int(os.getenv("SESSION_TTL_MINUTES", "30")) * 60
REFRESH_TTL_SEGUNDOS = int(os.getenv("REFRESH_TTL_DAYS", "7")) * 86400
CACHE_TTL_SEGUNDOS = int(os.getenv("BOOKS_CACHE_TTL", "60"))
REDIS_TIMEOUT = float(os.getenv("REDIS_TIMEOUT", "2"))

PREFIJO_REVOCADO = "jwt:revoked:"
PREFIJO_SESION = "session:"
PREFIJO_REFRESH = "refresh:"
PREFIJO_ACCESOS = "refresh_access:"


class RedisNoDisponible(Exception):
    """Redis no esta configurado o no responde (los mensajes nunca incluyen la URL completa)."""


_cliente = None
_lock = threading.Lock()


def configurar_cliente(cliente):
    """Inyecta un cliente (pruebas)."""
    global _cliente
    with _lock:
        _cliente = cliente


def reiniciar():
    global _cliente
    with _lock:
        _cliente = None


def url_enmascarada(url=None):
    url = url if url is not None else os.getenv("REDIS_URL", "")
    return re.sub(r"(://[^:/@]*):[^@]*@", r"\1:***@", url)


def cliente():
    global _cliente
    with _lock:
        if _cliente is None:
            url = os.getenv("REDIS_URL")
            if not url:
                raise RedisNoDisponible("REDIS_URL no esta definida")
            _cliente = redis.Redis.from_url(
                url, decode_responses=True, socket_timeout=REDIS_TIMEOUT,
                socket_connect_timeout=REDIS_TIMEOUT, health_check_interval=30, retry_on_timeout=True)
        return _cliente


def estado():
    with _lock:
        sin_cliente = _cliente is None
    if sin_cliente and not os.getenv("REDIS_URL"):
        return "no_configurado"
    try:
        return "ok" if cliente().ping() else "error"
    except (RedisNoDisponible, redis.RedisError):
        return "error"


def _cerrado(operacion, fn):
    inicio = time.perf_counter()
    try:
        return fn(cliente())
    except RedisNoDisponible:
        metrics.inc("redis_errors_total", operacion=operacion)
        raise
    except redis.RedisError as exc:
        metrics.inc("redis_errors_total", operacion=operacion)
        raise RedisNoDisponible("Redis no disponible") from exc
    finally:
        metrics.observar("redis_latency_seconds", time.perf_counter() - inicio)


# ---- revocacion (fail-closed) ----
def jti_revocado(jti):
    metrics.inc("jwt_revocation_checks_total")
    return bool(_cerrado("jti_revocado", lambda c: c.exists(PREFIJO_REVOCADO + jti)))


def revocar_jti(jti, exp):
    ttl = max(1, int(exp) - int(time.time()))
    _cerrado("revocar_jti", lambda c: c.set(PREFIJO_REVOCADO + jti, "1", ex=ttl))


# ---- sesiones y refresh tokens (fail-closed) ----
def guardar_sesion(jti, datos, ttl):
    _cerrado("guardar_sesion", lambda c: c.set(PREFIJO_SESION + jti, json.dumps(datos), ex=int(ttl)))


def obtener_sesion(jti):
    valor = _cerrado("obtener_sesion", lambda c: c.get(PREFIJO_SESION + jti))
    return json.loads(valor) if valor else None


def borrar_sesion(jti):
    _cerrado("borrar_sesion", lambda c: c.delete(PREFIJO_SESION + jti))


def guardar_refresh(jti, user_id, ttl):
    _cerrado("guardar_refresh", lambda c: c.set(PREFIJO_REFRESH + jti, str(user_id), ex=int(ttl)))


def refresh_vigente(jti):
    return bool(_cerrado("refresh_vigente", lambda c: c.exists(PREFIJO_REFRESH + jti)))


def borrar_refresh(jti):
    _cerrado("borrar_refresh", lambda c: c.delete(PREFIJO_REFRESH + jti))


def registrar_acceso_de_refresh(jti_refresh, jti_acceso, ttl=None):
    """Anota que jti_acceso fue emitido bajo jti_refresh (para revocarlos todos en el logout)."""
    clave = PREFIJO_ACCESOS + jti_refresh
    ttl = int(ttl or REFRESH_TTL_SEGUNDOS)

    def op(c):
        c.sadd(clave, jti_acceso)
        c.expire(clave, ttl)
    _cerrado("registrar_acceso_de_refresh", op)


def accesos_de_refresh(jti_refresh):
    miembros = _cerrado("accesos_de_refresh", lambda c: c.smembers(PREFIJO_ACCESOS + jti_refresh))
    return list(miembros or [])


def borrar_accesos_de_refresh(jti_refresh):
    _cerrado("borrar_accesos_de_refresh", lambda c: c.delete(PREFIJO_ACCESOS + jti_refresh))


# ---- cache publica (fail-open) ----
def cache_get(clave):
    try:
        valor = cliente().get(clave)
    except (RedisNoDisponible, redis.RedisError):
        metrics.inc("redis_errors_total", operacion="cache_get")
        return None
    metrics.inc("cache_hits_total" if valor is not None else "cache_misses_total")
    return valor


def cache_set(clave, valor, ttl=None):
    try:
        cliente().set(clave, valor, ex=int(ttl or CACHE_TTL_SEGUNDOS))
    except (RedisNoDisponible, redis.RedisError):
        metrics.inc("redis_errors_total", operacion="cache_set")


def cache_invalidar_libros():
    try:
        c = cliente()
        claves = list(c.scan_iter(match="books:*", count=200))
        if claves:
            c.unlink(*claves)
        metrics.inc("cache_invalidations_total")
    except (RedisNoDisponible, redis.RedisError):
        metrics.inc("redis_errors_total", operacion="cache_invalidar")
