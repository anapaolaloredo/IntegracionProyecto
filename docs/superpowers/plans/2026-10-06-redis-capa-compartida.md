# Redis como capa compartida (Sub-proyecto A: backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar Redis a los servicios `login`, `soap` (books), `users`, `authors`, `pedidos` y `pagos` para sesiones y refresh tokens con TTL, revocación de JWT por `jti`, caché pública del catálogo, métricas y `/health`, manteniendo PostgreSQL como fuente de datos.

**Architecture:** Un módulo común `apps/services/common/redis_store.py` (cliente único desde `REDIS_URL`, timeouts, helpers *fail-closed* para sesión/revocación/autorización y *fail-open* para caché) más `common/metrics.py` y `common/ops.py` (`/metrics`, `/health`). `requiere_jwt` verifica la revocación en Redis tras validar el JWT. `login` guarda sesión y refresh en Redis; `soap` cachea sus GET públicos y los invalida tras escrituras exitosas.

**Tech Stack:** Python 3, Flask 3.0.3, redis-py (`redis>=5,<6`), PyJWT 2.9.0, fakeredis (`fakeredis>=2.23,<3`, solo pruebas), pytest, Docker Compose (solo despliegue de Redis).

**Spec:** No hay spec escrito (el usuario pidió pasar directo al plan). El diseño aprobado en el chat es la sección *Design (approved in chat)* de este documento; los ejecutores deben tratarla como la fuente de verdad.

## Design (approved in chat)

1. **Capa común** `common/redis_store.py`: conexión desde `REDIS_URL` (`redis://:password@host:6379/0`; `rediss://` para TLS), `socket_timeout` y `socket_connect_timeout` de 2 s, `health_check_interval=30`, contraseña nunca en logs. Dos modos: **fail-closed** (sesión, revocación, autorización → `RedisNoDisponible` → los servicios responden 503 y NO aceptan el token) y **fail-open** (solo caché → se lee de PostgreSQL y se cuenta el error).
2. **Revocación:** todo JWT lleva `jti`. `requiere_jwt` consulta `jwt:revoked:<jti>` tras validar la firma. Token revocado → 401. Revocar = `SET jwt:revoked:<jti> 1 EX <vida restante del token>`. Solo se consulta donde ya se exige JWT; `/register`, `/login`, `/login/verify`, `/health`, `/metrics` y los GET del catálogo no exigen JWT ni consultan revocación.
3. **Login:** `session:<jti_acceso>` (JSON con user_id, role_id, email, jti_refresh, exp_refresh; TTL = vigencia del JWT de acceso, 30 min) y `refresh:<jti_refresh>` (TTL 7 días). `/session` y `/session/extend` leen Redis; `extend` emite un access nuevo y revoca el anterior; `/session/refresh` exige que el refresh exista en Redis; `/logout` borra sesión y refresh y revoca ambos `jti`.
4. **Caché del catálogo (soap):** `books:list:<hash de ruta+filtros>` y `books:<isbn>`, TTL 60 s (`BOOKS_CACHE_TTL`); solo se cachean respuestas 200. Cualquier POST, PUT, PATCH o DELETE exitoso sobre `/api/libros*` invalida `books:*`; `pedidos` también invalida `books:*` al cancelar un pedido (cambia stock).
5. **TTL coherentes y secreto:** una sola fuente de constantes (`SESSION_TTL_MINUTES=30`, `REFRESH_TTL_DAYS=7`, `BOOKS_CACHE_TTL=60`); el TTL de la clave de revocación es la vida restante del token. El secreto se lee de `JWT_SECRET_KEY` con `SECRET_KEY` como alias; se mantienen las reglas (≥ 32 caracteres, no `change-me…`).
6. **Operación:** `GET /metrics` (formato Prometheus, contadores en memoria por proceso) y `GET /health` con `{"status","db","redis"}` en cada servicio (`status` depende solo de la BD para no romper los semáforos actuales del cliente, que miran `db == "ok"`; `redis` es `ok|error|no_configurado`).
7. **Despliegue:** el Redis de producción es el que el usuario ya tiene en su instancia de GCP, y **los servicios corren en esa misma instancia**: `REDIS_URL=redis://:<password>@localhost:6379/0`, Redis escuchando solo en `127.0.0.1` y **sin abrir el puerto 6379 en el firewall de GCP**. Los servicios solo necesitan `REDIS_URL` (en los seis `.env.example`). `apps/services/docker-compose.yml` queda como **opcional para desarrollo local** (Redis con contraseña y `noeviction`). La guía documenta requisitos del Redis de GCP: `bind 127.0.0.1` (sin exponerlo), `requirepass`, `maxmemory-policy noeviction` (una memoria llena debe hacer fallar las escrituras —fail-closed— en vez de expulsar claves de revocación) y no abrir el puerto 6379 en el firewall; `rediss://` solo si Redis se mueve a otra máquina.
8. **Fuera de alcance:** rate limiting, locks distribuidos, rotación de refresh tokens, cliente de escritorio (sub-proyecto B), TLS en Flask. "Coordinar tareas temporales" se interpreta como las claves con TTL de arriba.

## Global Constraints

- Redis es opcional **solo** para lecturas cacheadas. Sesión, revocación y autorización fallan cerrado: Redis caído → 503 (nunca aceptar un token sin poder comprobar su revocación, nunca emitir tokens sin poder guardar la sesión).
- Todos los JWT (acceso y refresh) llevan `jti` (uuid4 hex); `jti` es claim obligatorio. HS256 fijo, claims `exp`, `iat`, `user_id`, `role_id`, `type`, `jti`.
- Acceso 30 min (`SESSION_TTL_MINUTES=30`), refresh 7 días (`REFRESH_TTL_DAYS=7`), caché 60 s (`BOOKS_CACHE_TTL=60`). `noeviction` en Redis.
- Claves exactas: `jwt:revoked:<jti>`, `session:<jti_acceso>`, `refresh:<jti_refresh>`, `books:list:<hash>`, `books:<isbn>`.
- Secreto: `JWT_SECRET_KEY` (alias `SECRET_KEY`), ≥ 32 caracteres, nunca `change-me…`, nunca en código.
- No registrar contraseñas ni la contraseña de `REDIS_URL` (enmascarar como `redis://:***@host:6379/0`); tokens solo en soap con `LOG_TOKENS=true` (excepción ya acordada).
- Endpoints públicos que NO deben exigir JWT ni Redis: `POST /register`, `POST /login`, `POST /login/verify` (este sí escribe en Redis para crear la sesión), `GET /health`, `GET /metrics`, `GET /api/libros*`, `GET /api/authors*`, `GET /api/roles`.
- 401 token ausente/inválido/revocado; 403 rol insuficiente; 503 Redis no disponible (rutas protegidas y login/verify/session/extend/refresh/logout).
- Servicios nuevos: Flask sin blueprints, solo `psycopg` v3; soap sigue con psycopg2. CORS por `CORS_ORIGINS`.
- Las pruebas unitarias usan `fakeredis`. El usuario tiene un Redis en su GCP, pero **ningún ejecutor se conecta a él por iniciativa propia**: la verificación contra el Redis real (Task 8) solo se corre cuando el usuario lo autoriza y entrega `REDIS_REAL_URL` en el entorno en ese momento (nunca se guarda en archivos ni se imprime). Sin esa autorización, el reporte final debe decir que no se verificó contra un Redis real. No conectar a ninguna base de datos real ni ejecutar `psql`.
- Comandos de prueba se ejecutan desde el directorio del servicio: `cd apps/services/<servicio> && .venv/bin/python -m pytest tests -q`; `common`: `cd apps/services && login/.venv/bin/python -m pytest common/tests -q`.
- Venvs: `login/.venv` y `soap/.venv` ya existen; para `users`, `authors`, `pedidos`, `pagos` crear `.venv` si falta: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest "fakeredis>=2.23,<3"`. Nunca hacer `git add` de `.venv`, `.env` ni `.superpowers`.

## Review Focus

1. Redis caído: toda ruta protegida responde 503 (nunca 200 ni un 401 "válido") y las rutas públicas (`/register`, `/login`, `/health`, GET del catálogo) siguen funcionando (Tasks 2–6).
2. Un `jti` revocado da 401 en **todos** los servicios y un token cerrado con `/logout` no sirve en `/session`, `/session/extend` ni en otros servicios; el refresh de una sesión cerrada o desconocido en Redis da 401 (Tasks 2, 3).
3. La caché se invalida tras toda escritura exitosa (POST/PUT/PATCH/DELETE) y NO tras una fallida (4xx); un pedido cancelado invalida `books:*` (Tasks 4, 6).
4. Si Redis falla en `POST /login/verify`, el código 2FA no se "quema" y no se devuelve ningún token (Task 3).
5. La contraseña de `REDIS_URL` no aparece en logs, excepciones, `/health` ni `/metrics` (Tasks 1, 7).

---

## File Structure

```
apps/services/
  common/
    metrics.py            # contadores en memoria + render Prometheus          (nuevo)
    redis_store.py        # cliente, helpers fail-closed y fail-open           (nuevo)
    ops.py                # registrar_operacion(app, servicio, db_check, health)(nuevo)
    jwt_auth.py           # jti, JWT_SECRET_KEY, revocacion en requiere_jwt     (modifica)
    web.py                # handler 503 para RedisNoDisponible                  (modifica)
    db.py                 # ping()                                              (modifica)
    testing.py            # fakeredis helpers                                   (modifica)
    requirements-test.txt # pytest, fakeredis                                   (nuevo)
    tests/                # test_metrics.py, test_redis_store.py, test_ops.py, test_jwt_auth.py (modifica)
  login/    service.py, app.py, errors.py (sin cambios), requirements.txt, .env.example, tests/
  soap/     app.py, requirements.txt, .env.example, tests/conftest.py (nuevo), tests/test_cache_redis.py (nuevo)
  users/ authors/ pedidos/ pagos/   app.py, requirements.txt, .env.example, tests/conftest.py, tests/test_redis.py (nuevo)
  docker-compose.yml, redis.env.example   (nuevos)
  README_JWT.md, docs/AI_CHANGELOG.md     (modifican)
```

---

### Task 1: Capa Redis común (`metrics`, `redis_store`, `ops`, `testing`)

**Files:**
- Create: `apps/services/common/metrics.py`, `redis_store.py`, `ops.py`, `requirements-test.txt`
- Modify: `apps/services/common/testing.py`, `apps/services/common/db.py`, `apps/services/common/tests/conftest.py`
- Test: `apps/services/common/tests/test_metrics.py`, `test_redis_store.py`, `test_ops.py`

**Interfaces:**
- Produces (`common.metrics`): `inc(nombre, valor=1, **etiquetas)`, `observar(nombre, segundos)`, `reiniciar()`, `render(servicio) -> str`.
- Produces (`common.redis_store`): `class RedisNoDisponible(Exception)`; constantes `SESSION_TTL_SEGUNDOS`, `REFRESH_TTL_SEGUNDOS`, `CACHE_TTL_SEGUNDOS`; `configurar_cliente(c)`, `reiniciar()`, `cliente()`, `url_enmascarada(url=None) -> str`, `estado() -> "ok"|"error"|"no_configurado"`; fail-closed: `jti_revocado(jti) -> bool`, `revocar_jti(jti, exp)`, `guardar_sesion(jti, datos:dict, ttl)`, `obtener_sesion(jti) -> dict|None`, `borrar_sesion(jti)`, `guardar_refresh(jti, user_id, ttl)`, `refresh_vigente(jti) -> bool`, `borrar_refresh(jti)`; fail-open: `cache_get(clave) -> str|None`, `cache_set(clave, valor, ttl=None)`, `cache_invalidar_libros()`.
- Produces (`common.ops`): `registrar_operacion(app, servicio, db_check=None, health=True)` agrega `GET /metrics` y (si `health`) `GET /health`.
- Produces (`common.db`): `ping() -> bool`.
- Produces (`common.testing`): `instalar_redis_falso() -> FakeServer`, `redis_caido(servidor)`, `redis_disponible(servidor)`, `quitar_redis_falso()`; `auth_header` sin cambios de firma.

- [ ] **Step 1: Dependencias de prueba**

```bash
cd apps/services
printf 'pytest\nfakeredis>=2.23,<3\n' > common/requirements-test.txt
login/.venv/bin/pip install "redis>=5,<6" -r common/requirements-test.txt
```

- [ ] **Step 2: Tests que fallan**

`common/tests/conftest.py` (reemplazar):

```python
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")


@pytest.fixture(autouse=True)
def redis_falso():
    """Redis en memoria para cada prueba; el valor es el FakeServer (testing.redis_caido lo apaga)."""
    from common import testing
    servidor = testing.instalar_redis_falso()
    yield servidor
    testing.quitar_redis_falso()
```

`common/tests/test_metrics.py`:

```python
from common import metrics


def test_inc_y_render_con_etiquetas():
    metrics.reiniciar()
    metrics.inc("cache_hits_total")
    metrics.inc("cache_hits_total")
    metrics.inc("jwt_rejected_total", motivo="revocado")
    texto = metrics.render("books")
    assert 'cache_hits_total{servicio="books"} 2' in texto
    assert 'jwt_rejected_total{motivo="revocado",servicio="books"} 1' in texto


def test_observar_genera_sum_y_count():
    metrics.reiniciar()
    metrics.observar("redis_latency_seconds", 0.5)
    metrics.observar("redis_latency_seconds", 1.5)
    texto = metrics.render("x")
    assert 'redis_latency_seconds_sum{servicio="x"} 2.0' in texto
    assert 'redis_latency_seconds_count{servicio="x"} 2' in texto


def test_etiquetas_no_pueden_romper_el_formato():
    metrics.reiniciar()
    metrics.inc("m", motivo='a"b\nc')
    assert 'm{motivo="ab c",servicio="s"} 1' in metrics.render("s")
```

`common/tests/test_redis_store.py`:

```python
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
```

`common/tests/test_ops.py`:

```python
from flask import Flask

from common import metrics, ops, testing
from common.redis_store import RedisNoDisponible
from common.web import configurar_app


def _cliente(db_check=None, health=True):
    app = Flask(__name__)
    ops.registrar_operacion(app, "demo", db_check=db_check, health=health)
    return app.test_client()


def test_metrics_publico_en_formato_prometheus():
    metrics.reiniciar()
    metrics.inc("cache_hits_total")
    resp = _cliente().get("/metrics")
    assert resp.status_code == 200 and resp.mimetype == "text/plain"
    assert 'cache_hits_total{servicio="demo"} 1' in resp.get_data(as_text=True)


def test_health_ok_con_bd_y_redis():
    resp = _cliente(db_check=lambda: True).get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"servicio": "demo", "status": "ok", "db": "ok", "redis": "ok"}


def test_health_bd_caida_da_503():
    resp = _cliente(db_check=lambda: False).get("/health")
    assert resp.status_code == 503 and resp.get_json()["status"] == "error"


def test_health_bd_que_lanza_excepcion_da_503():
    def boom():
        raise RuntimeError("sin bd")
    assert _cliente(db_check=boom).get("/health").status_code == 503


def test_health_redis_caido_no_cambia_status_pero_lo_informa(redis_falso):
    testing.redis_caido(redis_falso)
    cuerpo = _cliente(db_check=lambda: True).get("/health").get_json()
    assert cuerpo["status"] == "ok" and cuerpo["redis"] == "error"


def test_health_sin_db_check():
    assert _cliente().get("/health").get_json()["db"] == "no_aplica"


def test_health_puede_omitirse():
    assert _cliente(health=False).get("/health").status_code == 404


def test_configurar_app_traduce_redis_no_disponible_a_503():
    app = Flask(__name__)
    configurar_app(app)

    @app.route("/x")
    def x():
        raise RedisNoDisponible("caido")

    resp = app.test_client().get("/x")
    assert resp.status_code == 503 and "mensaje" in resp.get_json()
```

(El último test depende de la Task 2; se escribe aquí pero se vuelve verde en la Task 2. Marcarlo con `pytest.mark.xfail(strict=False, reason="task 2")` hasta entonces NO está permitido: déjalo fallar y continúa; la Task 2 lo deja en verde.)

- [ ] **Step 3: Verificar que fallan**

Run: `cd apps/services && login/.venv/bin/python -m pytest common/tests/test_metrics.py common/tests/test_redis_store.py common/tests/test_ops.py -q`
Expected: FAIL (`ImportError: cannot import name 'metrics'`).

- [ ] **Step 4: `common/metrics.py`**

```python
"""Contadores en memoria (por proceso) y render en formato Prometheus.
Sin dependencias externas. Nunca recibe secretos: solo nombres y conteos."""

import threading

_lock = threading.Lock()
_contadores = {}      # (nombre, etiquetas ordenadas) -> valor
_observaciones = {}   # nombre -> [suma, cuenta]


def _limpio(valor):
    return str(valor).replace('"', "").replace("\n", " ").replace("\\", "")


def inc(nombre, valor=1, **etiquetas):
    clave = (nombre, tuple(sorted((k, _limpio(v)) for k, v in etiquetas.items())))
    with _lock:
        _contadores[clave] = _contadores.get(clave, 0) + valor


def observar(nombre, segundos):
    with _lock:
        suma_cuenta = _observaciones.setdefault(nombre, [0.0, 0])
        suma_cuenta[0] += segundos
        suma_cuenta[1] += 1


def reiniciar():
    with _lock:
        _contadores.clear()
        _observaciones.clear()


def _etiquetas(servicio, extra=()):
    pares = sorted([("servicio", _limpio(servicio)), *extra])
    return ",".join(f'{k}="{v}"' for k, v in pares)


def render(servicio):
    lineas = []
    with _lock:
        for (nombre, extra), valor in sorted(_contadores.items()):
            lineas.append(f"{nombre}{{{_etiquetas(servicio, extra)}}} {valor}")
        for nombre, (suma, cuenta) in sorted(_observaciones.items()):
            lineas.append(f"{nombre}_sum{{{_etiquetas(servicio)}}} {suma}")
            lineas.append(f"{nombre}_count{{{_etiquetas(servicio)}}} {cuenta}")
    return "\n".join(lineas) + "\n"
```

- [ ] **Step 5: `common/redis_store.py`**

```python
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
```

- [ ] **Step 6: `common/ops.py`, `common/db.py`, `common/testing.py`**

`common/ops.py`:

```python
"""Endpoints operativos publicos: GET /metrics (Prometheus) y GET /health."""

from flask import Response, jsonify

from common import metrics, redis_store


def registrar_operacion(app, servicio, db_check=None, health=True):
    @app.route("/metrics", methods=["GET"])
    def _metrics():
        return Response(metrics.render(servicio), mimetype="text/plain")

    if not health:
        return

    @app.route("/health", methods=["GET"])
    def _health():
        if db_check is None:
            db = "no_aplica"
        else:
            try:
                db = "ok" if db_check() else "error"
            except Exception:
                db = "error"
        cuerpo = {"servicio": servicio, "status": "error" if db == "error" else "ok",
                  "db": db, "redis": redis_store.estado()}
        return jsonify(cuerpo), (503 if db == "error" else 200)
```

Agregar al final de `common/db.py`:

```python
def ping():
    """True si PostgreSQL responde a SELECT 1 (para /health)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        return cur.fetchone()[0] == 1
```

`common/testing.py` (reemplazar):

```python
"""Ayudas para las pruebas de los servicios (requiere SECRET_KEY en el entorno)."""

import fakeredis

from common import metrics, redis_store
from common.jwt_auth import ROLE_USER, crear_token


def auth_header(user_id=2, role_id=ROLE_USER, tipo="access", ttl=1800):
    return {"Authorization": f"Bearer {crear_token(user_id, role_id, tipo, ttl)}"}


def instalar_redis_falso():
    """Redis en memoria; devuelve el FakeServer para poder apagarlo con redis_caido()."""
    servidor = fakeredis.FakeServer()
    redis_store.configurar_cliente(fakeredis.FakeRedis(server=servidor, decode_responses=True))
    metrics.reiniciar()
    return servidor


def redis_caido(servidor):
    servidor.connected = False


def redis_disponible(servidor):
    servidor.connected = True


def quitar_redis_falso():
    redis_store.reiniciar()
```

- [ ] **Step 7: Verificar**

Run: `cd apps/services && login/.venv/bin/python -m pytest common/tests -q`
Expected: todo PASS excepto `test_configurar_app_traduce_redis_no_disponible_a_503` (se arregla en la Task 2).

- [ ] **Step 8: Commit**

```bash
git add apps/services/common
git commit -m "feat(common): capa Redis compartida (revocacion, sesiones, cache), metricas y /health"
```

---

### Task 2: `jti`, `JWT_SECRET_KEY` y revocación en `requiere_jwt` (+ fake Redis en todas las suites)

**Files:**
- Modify: `apps/services/common/jwt_auth.py` (reemplazo completo), `apps/services/common/web.py`
- Modify: `apps/services/common/tests/test_jwt_auth.py`
- Modify (conftest con fixture `redis_falso`): `apps/services/login/tests/conftest.py`, `users/tests/conftest.py`, `authors/tests/conftest.py`, `pedidos/tests/conftest.py`, `pagos/tests/conftest.py`
- Create: `apps/services/soap/tests/conftest.py`
- Modify (deps): `apps/services/{login,soap,users,authors,pedidos,pagos}/requirements.txt`

**Interfaces:**
- Consumes: `common.redis_store` (`jti_revocado`, `RedisNoDisponible`), `common.metrics`.
- Produces: `crear_token(user_id, role_id, tipo, ttl_segundos, jti=None) -> str` (jti por defecto uuid4 hex); `decodificar` exige `jti`; `obtener_secret()` lee `JWT_SECRET_KEY` y, si no existe, `SECRET_KEY`; `requiere_jwt` responde 401 (revocado), 503 (Redis caído), sin cambios para 401/403 previos. `common.web.configurar_app` registra el handler 503 de `RedisNoDisponible`.

- [ ] **Step 1: Dependencias y venvs**

Agregar la línea `redis>=5,<6` a los seis `requirements.txt`. Instalar en cada venv (crear los que falten):

```bash
cd apps/services
for s in login soap; do $s/.venv/bin/pip install "redis>=5,<6" -r common/requirements-test.txt; done
for s in users authors pedidos pagos; do
  [ -d $s/.venv ] || python3 -m venv $s/.venv
  $s/.venv/bin/pip install -r $s/requirements.txt -r common/requirements-test.txt
done
```

- [ ] **Step 2: Fixture `redis_falso` en los conftest**

Agregar al final de cada `conftest.py` de `login`, `users`, `authors`, `pedidos`, `pagos` (y crear `soap/tests/conftest.py` con el encabezado completo):

```python
import pytest


@pytest.fixture(autouse=True)
def redis_falso():
    from common import testing
    servidor = testing.instalar_redis_falso()
    yield servidor
    testing.quitar_redis_falso()
```

`soap/tests/conftest.py` completo:

```python
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")


@pytest.fixture(autouse=True)
def redis_falso():
    from common import testing
    servidor = testing.instalar_redis_falso()
    yield servidor
    testing.quitar_redis_falso()
```

- [ ] **Step 3: Tests que fallan** — agregar al final de `common/tests/test_jwt_auth.py`

Primero, en los cinco tests que construyen el payload a mano (`test_firma_con_otra_clave_se_rechaza`, `test_alg_none_se_rechaza`, `test_alg_distinto_hs512_se_rechaza`, `test_claims_invalidos_se_rechazan`, `test_falta_claim_obligatorio`) agregar `"jti": "abc123"` al diccionario del payload para que cada uno siga aislando su causa. Luego agregar:

```python
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
```

(Si el archivo no importa ya `os`, `jwt`, `Flask`, `jsonify`, agregarlos al encabezado.)

- [ ] **Step 4: Verificar que fallan**

Run: `cd apps/services && login/.venv/bin/python -m pytest common/tests/test_jwt_auth.py -q`
Expected: FAIL (`crear_token()` no acepta `jti`, sin claim `jti`, sin revocación).

- [ ] **Step 5: Reemplazar `common/jwt_auth.py`**

```python
"""Validacion JWT compartida por todos los microservicios (HS256).

El secreto se lee solo del entorno (JWT_SECRET_KEY, con SECRET_KEY como alias). Claims
obligatorios: exp, iat, user_id, role_id, type ("access" | "refresh") y jti. Tras validar la
firma, requiere_jwt consulta la lista de revocacion en Redis (fail-closed: Redis caido -> 503)."""

import os
import time
import uuid
from functools import wraps

import jwt
from flask import g, jsonify, request

from common import metrics, redis_store

ALGORITHM = "HS256"
ROLE_ADMIN = 1
ROLE_USER = 2
ROLE_IDS = {"admin": ROLE_ADMIN, "cliente": ROLE_USER}
ROLE_NAMES = {valor: nombre for nombre, valor in ROLE_IDS.items()}
_CLAIMS_OBLIGATORIOS = ["exp", "iat", "user_id", "role_id", "type", "jti"]


class TokenInvalido(Exception):
    """El token falta, esta mal formado, vencio, o sus claims no son validos."""


def obtener_secret():
    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY (o SECRET_KEY) no esta definida en el entorno")
    if secret.lower().startswith("change-me") or len(secret) < 32:
        raise RuntimeError(
            "El secreto JWT no es valido: debe tener al menos 32 caracteres y no ser el valor de ejemplo"
        )
    return secret


def crear_token(user_id, role_id, tipo, ttl_segundos, jti=None):
    ahora = int(time.time())
    payload = {"user_id": user_id, "role_id": role_id, "type": tipo,
               "iat": ahora, "exp": ahora + int(ttl_segundos), "jti": jti or uuid.uuid4().hex}
    return jwt.encode(payload, obtener_secret(), algorithm=ALGORITHM)


def decodificar(token, tipo="access"):
    try:
        datos = jwt.decode(token, obtener_secret(), algorithms=[ALGORITHM],
                           options={"require": _CLAIMS_OBLIGATORIOS})
    except jwt.PyJWTError as exc:
        raise TokenInvalido(str(exc)) from exc
    if datos["type"] != tipo:
        raise TokenInvalido("tipo de token incorrecto")
    if type(datos["user_id"]) is not int or type(datos["role_id"]) is not int \
            or datos["role_id"] not in tuple(ROLE_NAMES):
        raise TokenInvalido("claims invalidos")
    if not isinstance(datos["jti"], str) or not datos["jti"]:
        raise TokenInvalido("jti invalido")
    return datos


def extraer_token(valor_header):
    partes = (valor_header or "").split()
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1]
    return None


def _error_json(mensaje, status):
    respuesta = jsonify({"mensaje": mensaje})
    respuesta.status_code = status
    return respuesta


def requiere_jwt(roles=None, error_response=None, on_event=None):
    """Exige Authorization: Bearer <JWT de acceso> no revocado. `roles` es una lista de
    role_id permitidos (None = cualquier rol valido). Deja g.user_id y g.role_id.
    Orden: firma/claims (401) -> revocacion en Redis (401 revocado | 503 Redis caido) -> rol (403)."""
    responder_error = error_response or _error_json

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            token = extraer_token(request.headers.get("Authorization"))
            datos = None
            resultado = None
            if not token:
                resultado = (401, "Se requiere Authorization: Bearer <token>")
            else:
                try:
                    datos = decodificar(token, "access")
                except TokenInvalido:
                    metrics.inc("jwt_rejected_total", motivo="invalido")
                    resultado = (401, "Token invalido o expirado")
                else:
                    try:
                        revocado = redis_store.jti_revocado(datos["jti"])
                    except redis_store.RedisNoDisponible:
                        resultado = (503, "Servicio de autorizacion no disponible")
                    else:
                        if revocado:
                            metrics.inc("jwt_rejected_total", motivo="revocado")
                            resultado = (401, "Token revocado")
                        elif roles is not None and datos["role_id"] not in roles:
                            resultado = (403, "Rol insuficiente para esta operacion")
            if on_event:
                on_event(token, datos, resultado)
            if resultado:
                return responder_error(resultado[1], resultado[0])
            g.user_id = datos["user_id"]
            g.role_id = datos["role_id"]
            return vista(*args, **kwargs)
        return envoltura
    return decorador
```

- [ ] **Step 6: Handler 503 en `common/web.py`**

En `configurar_app`, junto a los otros `errorhandler`, agregar (e importar `from common.redis_store import RedisNoDisponible` arriba):

```python
    @app.errorhandler(RedisNoDisponible)
    def _redis_no_disponible(_):
        return jsonify({"mensaje": "Servicio de autorizacion no disponible. Intenta de nuevo en unos minutos."}), 503
```

- [ ] **Step 7: Verificar todas las suites (deben seguir verdes)**

```bash
cd apps/services && login/.venv/bin/python -m pytest common/tests -q
for s in login soap users authors pedidos pagos; do (cd $s && .venv/bin/python -m pytest tests -q 2>&1 | tail -2); done
```
Expected: `common` todo PASS (incluye el test de la Task 1); en login, `test_jwt_service.py` puede seguir verde porque todavía no se tocó `login/service.py`; users/authors/pedidos/pagos/soap PASS (los tokens de prueba traen `jti` y el fake Redis responde "no revocado"). Si una suite falla por un token armado a mano sin `jti`, agregar el `jti` a ese token (no relajar la validación).

- [ ] **Step 8: Commit**

```bash
git add apps/services
git commit -m "feat(common): jti obligatorio, JWT_SECRET_KEY y revocacion en Redis dentro de requiere_jwt"
```

---

### Task 3: `login` guarda sesión y refresh en Redis, `/logout` revoca

**Files:**
- Modify: `apps/services/login/service.py`, `apps/services/login/app.py`, `apps/services/login/.env.example`
- Replace: `apps/services/login/tests/test_jwt_service.py`
- Create: `apps/services/login/tests/test_redis_sessions.py`

**Interfaces:**
- Consumes: `common.redis_store` (todas las fail-closed), `common.jwt_auth.crear_token(..., jti=)`, `common.ops.registrar_operacion`.
- Produces: `service.verificar_login(email, codigo) -> {"session_token","refresh_token"}`; `consultar_sesion`, `extender_sesion`, `refrescar_sesion` (devuelven `{"session_token","expira_en","segundos_restantes"}` salvo `consultar_sesion`), `cerrar_sesion(token) -> None`. Redis caído → `RedisNoDisponible` (app.py → 503). `/health` → `{"status","db","redis"}`. `GET /metrics`.
- Datos en Redis: `session:<jti_acceso>` = `{"user_id","role_id","email","jti_refresh","exp_refresh"}`; `refresh:<jti_refresh>` = user_id.

- [ ] **Step 1: Reemplazar `login/tests/test_jwt_service.py`**

```python
from unittest.mock import patch

import pytest

import service
from common import redis_store
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, crear_token, decodificar
from errors import SesionInvalida

USUARIO = {"id_usuario": 5, "correo": "a@b.co", "rol": "cliente", "nombre": "Ana"}
ADMIN = {"id_usuario": 1, "correo": "r@b.co", "rol": "admin", "nombre": "Root"}


def _login(usuario=USUARIO):
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=usuario), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado"), \
         patch.object(service, "verificar_codigo", return_value=True):
        return service.verificar_login(usuario["correo"], "123456")


def test_verificar_login_emite_acceso_y_refresh_con_ttl():
    tokens = _login()
    acceso = decodificar(tokens["session_token"], "access")
    refresh = decodificar(tokens["refresh_token"], "refresh")
    assert acceso["user_id"] == 5 and acceso["role_id"] == ROLE_USER
    assert acceso["exp"] - acceso["iat"] == 30 * 60
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 3600
    assert acceso["jti"] != refresh["jti"]


def test_verificar_login_guarda_sesion_y_refresh_en_redis():
    tokens = _login()
    acceso = decodificar(tokens["session_token"])
    refresh = decodificar(tokens["refresh_token"], "refresh")
    sesion = redis_store.obtener_sesion(acceso["jti"])
    assert sesion["user_id"] == 5 and sesion["email"] == "a@b.co"
    assert sesion["jti_refresh"] == refresh["jti"] and sesion["exp_refresh"] == refresh["exp"]
    assert redis_store.refresh_vigente(refresh["jti"]) is True
    assert 1790 <= redis_store.cliente().ttl(f"session:{acceso['jti']}") <= 1800
    assert redis_store.cliente().ttl(f"refresh:{refresh['jti']}") > 604000


def test_admin_recibe_role_id_1():
    assert decodificar(_login(ADMIN)["session_token"])["role_id"] == ROLE_ADMIN


def test_consultar_sesion_valida():
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        estado = service.consultar_sesion(tokens["session_token"])
    assert estado["autenticado"] is True and estado["email"] == "a@b.co" and estado["role_id"] == ROLE_USER
    assert 1790 <= estado["segundos_restantes"] <= 1800


@pytest.mark.parametrize("token", [None, "", "basura", "a.b.c"])
def test_consultar_sesion_token_invalido_no_autenticado(token):
    assert service.consultar_sesion(token) == {"autenticado": False}


def test_consultar_sesion_expirado_o_refresh_no_autenticado():
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "access", -5)) == {"autenticado": False}
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "refresh", 600)) == {"autenticado": False}


def test_consultar_sesion_jwt_valido_sin_sesion_en_redis_no_autenticado():
    # firma correcta pero la sesion no existe (nunca se creo o ya expiro en Redis)
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "access", 600)) == {"autenticado": False}


def test_extender_emite_token_nuevo_y_revoca_el_anterior():
    tokens = _login()
    viejo = decodificar(tokens["session_token"])
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        resp = service.extender_sesion(tokens["session_token"])
    nuevo = decodificar(resp["session_token"])
    assert nuevo["jti"] != viejo["jti"] and 1790 <= resp["segundos_restantes"] <= 1800
    assert redis_store.jti_revocado(viejo["jti"]) is True
    assert redis_store.obtener_sesion(viejo["jti"]) is None
    assert redis_store.obtener_sesion(nuevo["jti"])["jti_refresh"] == \
        decodificar(tokens["refresh_token"], "refresh")["jti"]


def test_extender_con_token_expirado_refresh_o_revocado_falla():
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        service.extender_sesion(tokens["session_token"])
        for malo in (crear_token(5, ROLE_USER, "access", -5), tokens["refresh_token"], None,
                     tokens["session_token"]):  # el ultimo ya fue revocado por el extend anterior
            with pytest.raises(SesionInvalida):
                service.extender_sesion(malo)


def test_refrescar_canjea_refresh_por_acceso_con_rol_actual():
    tokens = _login()
    promovido = dict(USUARIO, rol="admin")
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=promovido):
        resp = service.refrescar_sesion(tokens["refresh_token"])
    assert decodificar(resp["session_token"])["role_id"] == ROLE_ADMIN


def test_refrescar_rechaza_acceso_y_refresh_desconocido():
    with pytest.raises(SesionInvalida):
        service.refrescar_sesion(crear_token(5, ROLE_USER, "access", 600))
    with pytest.raises(SesionInvalida):  # firma valida pero no esta en Redis
        service.refrescar_sesion(crear_token(5, ROLE_USER, "refresh", 600))


def test_refrescar_usuario_borrado_falla():
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=None):
        with pytest.raises(SesionInvalida):
            service.refrescar_sesion(tokens["refresh_token"])


def test_logout_borra_sesion_y_refresh_y_revoca_ambos():
    tokens = _login()
    acceso = decodificar(tokens["session_token"])
    refresh = decodificar(tokens["refresh_token"], "refresh")
    service.cerrar_sesion(tokens["session_token"])
    assert redis_store.obtener_sesion(acceso["jti"]) is None
    assert redis_store.refresh_vigente(refresh["jti"]) is False
    assert redis_store.jti_revocado(acceso["jti"]) is True
    assert redis_store.jti_revocado(refresh["jti"]) is True


def test_token_cerrado_ya_no_sirve_para_nada():
    tokens = _login()
    service.cerrar_sesion(tokens["session_token"])
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        assert service.consultar_sesion(tokens["session_token"]) == {"autenticado": False}
        with pytest.raises(SesionInvalida):
            service.extender_sesion(tokens["session_token"])
        with pytest.raises(SesionInvalida):
            service.refrescar_sesion(tokens["refresh_token"])
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion(tokens["session_token"])


def test_cerrar_sesion_exige_token_valido():
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion("basura")
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion(None)
```

- [ ] **Step 2: Tests de rutas y de Redis caído** — `login/tests/test_redis_sessions.py`

```python
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
```

(En `test_la_contrasena...`, `redis_falso` ya inyectó un cliente, así que `estado()` no abre conexión real.)

- [ ] **Step 3: Verificar que fallan**

Run: `cd apps/services/login && .venv/bin/python -m pytest tests/test_jwt_service.py tests/test_redis_sessions.py -q`
Expected: FAIL (service sigue sin usar Redis; `/metrics` no existe).

- [ ] **Step 4: `login/service.py`** — reemplazar las funciones de sesión

Cambiar los imports a:

```python
import time
import uuid
from datetime import datetime, timedelta, timezone

from config.settings import SESSION_TTL_MINUTES, CODE_TTL_MINUTES, REFRESH_TTL_DAYS
from common import redis_store
from common.jwt_auth import ROLE_IDS, TokenInvalido, crear_token, decodificar
```

(conservar el resto de imports del archivo) y reemplazar `_emitir_acceso`, `_datos_acceso`, `verificar_login`, `cerrar_sesion`, `consultar_sesion`, `extender_sesion` y `refrescar_sesion` por:

```python
SESSION_TTL = SESSION_TTL_MINUTES * 60
REFRESH_TTL = REFRESH_TTL_DAYS * 86400


def _iso(exp):
    return datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()


def _nuevo_acceso(usuario, jti_refresh, exp_refresh):
    """Emite un JWT de acceso y guarda su sesion en Redis (TTL = vigencia del token).
    Lanza RedisNoDisponible si no puede guardarla: nunca se entrega un token sin sesion."""
    role_id = ROLE_IDS[usuario["rol"]]
    jti = uuid.uuid4().hex
    token = crear_token(usuario["id_usuario"], role_id, "access", SESSION_TTL, jti=jti)
    exp = decodificar(token, "access")["exp"]
    redis_store.guardar_sesion(jti, {
        "user_id": usuario["id_usuario"], "role_id": role_id, "email": usuario["correo"],
        "jti_refresh": jti_refresh, "exp_refresh": exp_refresh}, SESSION_TTL)
    return {"session_token": token, "expira_en": _iso(exp),
            "segundos_restantes": max(0, exp - int(time.time()))}


def _decodificar_o_none(token, tipo):
    if not token:
        return None
    try:
        return decodificar(token, tipo)
    except TokenInvalido:
        return None


def _sesion_activa(datos):
    """Sesion vigente en Redis para un JWT de acceso ya decodificado, o SesionInvalida."""
    if redis_store.jti_revocado(datos["jti"]):
        raise SesionInvalida("Token de sesion revocado.")
    sesion = redis_store.obtener_sesion(datos["jti"])
    if sesion is None:
        raise SesionInvalida("La sesion no existe o ya expiro.")
    return sesion


def _cerrar_acceso(jti, exp):
    redis_store.revocar_jti(jti, exp)
    redis_store.borrar_sesion(jti)


def verificar_login(email, codigo):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario:
        raise CodigoInvalido("Codigo invalido o expirado.")
    pendiente = repository.obtener_codigo_vigente(usuario["id_usuario"])
    if not pendiente or not verificar_codigo(codigo, pendiente["codigo_hash"]):
        raise CodigoInvalido("Codigo invalido o expirado.")
    role_id = ROLE_IDS[usuario["rol"]]
    jti_refresh = uuid.uuid4().hex
    refresh = crear_token(usuario["id_usuario"], role_id, "refresh", REFRESH_TTL, jti=jti_refresh)
    exp_refresh = decodificar(refresh, "refresh")["exp"]
    redis_store.guardar_refresh(jti_refresh, usuario["id_usuario"], REFRESH_TTL)
    acceso = _nuevo_acceso(usuario, jti_refresh, exp_refresh)
    # El codigo se marca usado solo cuando la sesion ya quedo guardada: si Redis falla no se quema.
    repository.marcar_codigo_usado(pendiente["id_codigo"])
    return {"session_token": acceso["session_token"], "refresh_token": refresh}


def cerrar_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        raise SesionInvalida("Token de sesion invalido o expirado.")
    sesion = _sesion_activa(datos)
    redis_store.borrar_refresh(sesion["jti_refresh"])
    redis_store.revocar_jti(sesion["jti_refresh"], sesion["exp_refresh"])
    _cerrar_acceso(datos["jti"], datos["exp"])


def consultar_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        return {"autenticado": False}
    try:
        _sesion_activa(datos)
    except SesionInvalida:
        return {"autenticado": False}
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        return {"autenticado": False}
    return {
        "autenticado": True,
        "id_usuario": usuario["id_usuario"],
        "email": usuario["correo"],
        "nombre": usuario["nombre"],
        "role_id": datos["role_id"],
        "expira_en": _iso(datos["exp"]),
        "segundos_restantes": max(0, datos["exp"] - int(time.time())),
    }


def extender_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        raise SesionInvalida("Token de sesion invalido o expirado.")
    sesion = _sesion_activa(datos)
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    nuevo = _nuevo_acceso(usuario, sesion["jti_refresh"], sesion["exp_refresh"])
    _cerrar_acceso(datos["jti"], datos["exp"])  # el token anterior deja de valer
    return nuevo


def refrescar_sesion(refresh_token):
    datos = _decodificar_o_none(refresh_token, "refresh")
    if not datos:
        raise SesionInvalida("Refresh token invalido o expirado.")
    if redis_store.jti_revocado(datos["jti"]) or not redis_store.refresh_vigente(datos["jti"]):
        raise SesionInvalida("Refresh token revocado o desconocido.")
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    return _nuevo_acceso(usuario, datos["jti"], datos["exp"])
```

Borrar las funciones antiguas `_emitir_acceso`/`_datos_acceso` y cualquier import que quede sin uso (`ROLE_IDS`, `timedelta` se siguen usando).

- [ ] **Step 5: `login/app.py`**

Agregar imports y registro operativo; handler 503; `/health` con `redis`:

```python
from common import jwt_auth, redis_store
from common.ops import registrar_operacion
```

Después de `jwt_auth.obtener_secret()  # ...` agregar:

```python
registrar_operacion(app, "login", health=False)  # /metrics; /health propio (usa formato XML/JSON)
```

Junto al handler de `ErrorDominio` agregar:

```python
@app.errorhandler(redis_store.RedisNoDisponible)
def manejar_redis_no_disponible(_):
    return responder("error", {"mensaje": "Servicio de sesiones no disponible. Intenta de nuevo en unos minutos."},
                     status=503)
```

Reemplazar el cuerpo de `health()` (después del docstring) por:

```python
    db_ok = service.verificar_salud()
    cuerpo = {"status": "ok" if db_ok else "error", "db": "ok" if db_ok else "error",
              "redis": redis_store.estado()}
    return responder("salud", cuerpo, status=200 if db_ok else 503)
```

Actualizar los docstrings de `/logout` ("Cierra la sesión: borra sesión y refresh en Redis y revoca el JWT") y `/session/extend` ("emite un token nuevo y revoca el anterior"). En `login/.env.example` reemplazar `SECRET_KEY=` por `JWT_SECRET_KEY=` (mismo valor de ejemplo, comentario "mínimo 32 caracteres; alias SECRET_KEY") y agregar:

```
# Redis compartido (sesiones, refresh tokens y revocacion de JWT). Mismo valor en todos los servicios.
REDIS_URL=redis://:change-me-redis-password@localhost:6379/0
REDIS_TIMEOUT=2
```

- [ ] **Step 6: Verificar**

Run: `cd apps/services/login && .venv/bin/python -m pytest tests/test_jwt_service.py tests/test_redis_sessions.py tests/test_security.py tests/test_formatters.py tests/test_sender.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/services/login
git commit -m "feat(login): sesion y refresh token en Redis con TTL; /logout revoca el JWT; /health y /metrics"
```

---

### Task 4: `soap` (books): caché de lecturas, invalidación, `/health` y `/metrics`

**Files:**
- Modify: `apps/services/soap/app.py`, `apps/services/soap/.env.example`
- Create: `apps/services/soap/tests/test_cache_redis.py`

**Interfaces:**
- Consumes: `common.redis_store` (`cache_get`, `cache_set`, `cache_invalidar_libros`), `common.ops.registrar_operacion`.
- Produces: decorador `cacheado(clave_fn)`; claves `books:list:<hash>` y `books:<isbn>`; header `X-Cache: HIT|MISS`; hook `after_request` que invalida `books:*` tras POST/PUT/PATCH/DELETE exitosos sobre `/api/libros*`; `GET /health`, `GET /metrics`.

- [ ] **Step 1: Tests que fallan** — `soap/tests/test_cache_redis.py`

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")

import pytest

import app as books
from common import redis_store, testing
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, crear_token

LIBRO = {"isbn": "123", "title": "T", "publicationYear": 2000, "price": 10, "stock": 3,
         "format": "Pasta", "authors": ["A"], "genres": ["G"], "images": [], "concepts": []}


@pytest.fixture
def c(monkeypatch):
    books.app.config["TESTING"] = True
    llamadas = {"n": 0}

    def fetch(where_clause="", params=None):
        llamadas["n"] += 1
        return [dict(LIBRO)]

    monkeypatch.setattr(books, "fetch_books", fetch)
    cliente = books.app.test_client()
    cliente.llamadas = llamadas
    return cliente


def _admin():
    return {"Authorization": f"Bearer {crear_token(1, ROLE_ADMIN, 'access', 600)}"}


def test_get_lista_segunda_vez_sale_de_cache(c):
    r1 = c.get("/api/libros")
    r2 = c.get("/api/libros")
    assert (r1.headers["X-Cache"], r2.headers["X-Cache"]) == ("MISS", "HIT")
    assert c.llamadas["n"] == 1 and r1.get_data() == r2.get_data()
    assert r2.mimetype == "application/xml"


def test_get_isbn_usa_clave_books_isbn_con_ttl_corto(c):
    c.get("/api/libros/123")
    assert redis_store.cache_get("books:123") is not None
    assert 0 < redis_store.cliente().ttl("books:123") <= redis_store.CACHE_TTL_SEGUNDOS
    assert c.get("/api/libros/123").headers["X-Cache"] == "HIT"


def test_clave_de_lista_depende_de_los_filtros(c):
    c.get("/api/libros/buscar?titulo=a")
    r = c.get("/api/libros/buscar?titulo=b")
    assert r.headers["X-Cache"] == "MISS"
    claves = redis_store.cliente().keys("books:list:*")
    assert len(claves) == 2


def test_no_se_cachean_errores(c, monkeypatch):
    monkeypatch.setattr(books, "fetch_books", lambda *a, **k: [])
    assert c.get("/api/libros/999").status_code == 404
    assert redis_store.cache_get("books:999") is None


def test_redis_caido_las_lecturas_siguen_funcionando_desde_postgres(c, redis_falso):
    testing.redis_caido(redis_falso)
    r = c.get("/api/libros")
    assert r.status_code == 200 and r.headers["X-Cache"] == "MISS"
    assert c.get("/api/libros/123").status_code == 200
    assert c.llamadas["n"] == 2  # sin cache: cada lectura va a la BD


def test_invalida_despues_de_put_exitoso(c, monkeypatch):
    c.get("/api/libros"); c.get("/api/libros/123")
    assert redis_store.cliente().keys("books:*")
    monkeypatch.setattr(books, "get_connection", lambda: _ConexionOk())
    monkeypatch.setattr(books, "guardar_relaciones", lambda *a, **k: None)
    resp = c.put("/api/libros/123", json={"title": "N"}, headers=_admin())
    assert resp.status_code == 200
    assert redis_store.cliente().keys("books:*") == []


def test_no_invalida_si_la_escritura_falla(c):
    c.get("/api/libros")
    assert c.put("/api/libros/123", json={}, headers={}).status_code == 401
    assert c.post("/api/libros", json={}, headers={"Authorization": f"Bearer {crear_token(1, ROLE_USER, 'access', 60)}"}).status_code == 403
    assert redis_store.cliente().keys("books:list:*")


def test_invalida_despues_de_delete_exitoso(c, monkeypatch):
    c.get("/api/libros/123")
    monkeypatch.setattr(books, "get_connection", lambda: _ConexionOk())
    resp = c.delete("/api/libros/123", headers=_admin())
    assert resp.status_code == 200
    assert redis_store.cliente().keys("books:*") == []


def test_token_revocado_da_401_en_escrituras(c):
    token = crear_token(1, ROLE_ADMIN, "access", 600, jti="r1")
    redis_store.revocar_jti("r1", 9999999999)
    assert c.delete("/api/libros/123", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_redis_caido_escrituras_dan_503_xml(c, redis_falso):
    token = crear_token(1, ROLE_ADMIN, "access", 600)
    testing.redis_caido(redis_falso)
    resp = c.post("/api/libros", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503 and resp.mimetype == "application/xml"


def test_health_y_metrics(c, monkeypatch):
    monkeypatch.setattr(books, "_db_ok", lambda: True)
    h = c.get("/health").get_json()
    assert h["status"] == "ok" and h["redis"] == "ok"
    c.get("/api/libros"); c.get("/api/libros")
    texto = c.get("/metrics").get_data(as_text=True)
    assert "cache_hits_total" in texto and "cache_misses_total" in texto


class _Cur:
    """Cursor falso: SELECT devuelve una fila de libro; DELETE/UPDATE 'afectan' una fila."""
    rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        pass

    def fetchone(self):
        return (1, "T", 2000, 10, 5, 1)

    def fetchall(self):
        return []


class _ConexionOk:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self, *a, **k):
        return _Cur()

    def close(self):
        pass

    def commit(self):
        pass
```

Nota para el implementador: el cursor falso debe reproducir lo que ya usa `tests/test_libros_db.py` (`FakeCursor`/`FakeConn`); si esos fakes sirven tal cual para PUT/DELETE exitosos, **reutilízalos** en vez de `_Cur`/`_ConexionOk` (importándolos de `tests.test_libros_db` o copiándolos), ajustando `test_invalida_despues_de_put/delete` para que el PUT/DELETE llegue a responder 200.

- [ ] **Step 2: Verificar que fallan**

Run: `cd apps/services/soap && .venv/bin/python -m pytest tests/test_cache_redis.py -q`
Expected: FAIL (`X-Cache` ausente, sin invalidación, `_db_ok`/`/health` inexistentes).

- [ ] **Step 3: Implementar en `soap/app.py`**

Imports (re-agregar `json`, `wraps` y `hashlib` que se habían quitado/no existen):

```python
import hashlib
import json
from functools import wraps
```
y
```python
from common import redis_store  # noqa: E402
from common.ops import registrar_operacion  # noqa: E402
```
(en el mismo bloque donde ya se importa `jwt_auth`).

Después de la definición de `get_connection()` agregar:

```python
def _db_ok():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
    finally:
        conn.close()


registrar_operacion(app, "books", db_check=lambda: _db_ok())  # GET /health y GET /metrics (publicos)
```

Antes de la primera ruta (`listar_libros`) agregar:

```python
# ---- cache publica en Redis (fail-open: sin Redis se lee de PostgreSQL) ----
def _clave_lista():
    filtros = "&".join(f"{k}={v}" for k, v in sorted(request.args.items(multi=True)))
    huella = hashlib.sha1(f"{request.path}?{filtros}".encode("utf-8")).hexdigest()[:16]
    return f"books:list:{huella}"


def cacheado(clave_fn):
    """Cachea respuestas 200 de un GET publico en Redis con TTL corto (BOOKS_CACHE_TTL)."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            clave = clave_fn(**kwargs)
            guardado = redis_store.cache_get(clave)
            if guardado is not None:
                datos = json.loads(guardado)
                resp = Response(datos["body"], status=200, mimetype=datos["mimetype"])
                resp.headers["X-Cache"] = "HIT"
                return resp
            resp = vista(*args, **kwargs)
            if resp.status_code == 200:
                redis_store.cache_set(clave, json.dumps({"body": resp.get_data(as_text=True),
                                                         "mimetype": resp.mimetype}))
            resp.headers["X-Cache"] = "MISS"
            return resp
        return envoltura
    return decorador


@app.after_request
def invalidar_cache_tras_escrituras(resp):
    """Cualquier POST/PUT/PATCH/DELETE exitoso sobre /api/libros* invalida books:*."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/libros") \
            and resp.status_code < 400:
        redis_store.cache_invalidar_libros()
    return resp
```

Decorar las rutas GET (debajo de `@app.route(...)`, encima de la función): `listar_libros`, `buscar_libros`, `listar_temas_libros`, `listar_catalogo_libros` con `@cacheado(lambda **_: _clave_lista())`, y `obtener_libro` con `@cacheado(lambda isbn: f"books:{isbn}")`.

Los decoradores `requiere_sesion`/`requiere_admin` no cambian (ya incluyen la revocación y el 503). Agregar a `soap/.env.example`: `JWT_SECRET_KEY` (reemplaza `SECRET_KEY`), `REDIS_URL=redis://:change-me-redis-password@localhost:6379/0`, `REDIS_TIMEOUT=2`, `BOOKS_CACHE_TTL=60`.

- [ ] **Step 4: Verificar**

Run: `cd apps/services/soap && .venv/bin/python -m pytest tests -q`
Expected: PASS (incluye las suites anteriores de soap).

- [ ] **Step 5: Commit**

```bash
git add apps/services/soap
git commit -m "feat(soap): cache Redis de lecturas publicas con invalidacion tras escrituras, /health y /metrics"
```

---

### Task 5: Users y Authors — Redis, `/health`, `/metrics`

**Files:**
- Modify: `apps/services/users/app.py`, `apps/services/authors/app.py`, ambos `.env.example`
- Create: `apps/services/users/tests/test_redis.py`, `apps/services/authors/tests/test_redis.py`

**Interfaces:**
- Consumes: `common.ops.registrar_operacion`, `common.db.ping`, la revocación ya integrada en `requiere_jwt`.
- Produces: `GET /health` (`{"servicio","status","db","redis"}`) y `GET /metrics` en ambos servicios.

- [ ] **Step 1: Tests que fallan**

`users/tests/test_redis.py`:

```python
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
```

`authors/tests/test_redis.py`: igual cambiando `users_app`→`authors_app` (`import app as authors_app`), servicio `"authors"`, y rutas: protegida `POST /api/authors` (503 / 401 revocado con `json={"nombre_autor": "X"}`), pública `GET /api/authors` (debe seguir 200 con Redis caído, con `monkeypatch.setattr(authors_app.repository, "listar", lambda: [])`).

- [ ] **Step 2: Verificar que fallan**

Run: `cd apps/services/users && .venv/bin/python -m pytest tests/test_redis.py -q` (y lo mismo en authors) → FAIL (`/health` 404).

- [ ] **Step 3: Implementar**

En `users/app.py` y `authors/app.py` agregar `from common import db as common_db` y `from common.ops import registrar_operacion` en el bloque de imports `# noqa: E402`, y después de `crear_swagger(app, ...)`:

```python
registrar_operacion(app, "users", db_check=lambda: common_db.ping())  # en authors: "authors"
```

(`lambda` resuelve `common_db.ping` en cada llamada, por eso los tests pueden parchear `common.db.ping`.) En ambos `.env.example`: `JWT_SECRET_KEY` (reemplaza `SECRET_KEY`) y `REDIS_URL=redis://:change-me-redis-password@localhost:6379/0`, `REDIS_TIMEOUT=2`.

- [ ] **Step 4: Verificar**

Run: `for s in users authors; do (cd apps/services/$s && .venv/bin/python -m pytest tests -q); done`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/services/users apps/services/authors
git commit -m "feat(users,authors): /health y /metrics con estado de Redis y REDIS_URL"
```

---

### Task 6: Pedidos y Pagos — Redis, `/health`, `/metrics`, invalidación de caché por stock

**Files:**
- Modify: `apps/services/pedidos/app.py`, `apps/services/pagos/app.py`, ambos `.env.example`
- Create: `apps/services/pedidos/tests/test_redis.py`, `apps/services/pagos/tests/test_redis.py`

**Interfaces:**
- Consumes: `common.ops.registrar_operacion`, `common.db.ping`, `common.redis_store.cache_invalidar_libros`.
- Produces: `GET /health`, `GET /metrics`; `pedidos` llama `redis_store.cache_invalidar_libros()` (best-effort, fail-open) tras crear un pedido y tras cancelar uno con éxito (cambia `libros.stock`); `pagos` no invalida (no toca stock).

- [ ] **Step 1: Tests que fallan**

`pedidos/tests/test_redis.py`:

```python
import time

import app as pedidos_app
from common import redis_store, testing
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, decodificar
from common.testing import auth_header
from common.web import Conflicto

USER = auth_header(2, ROLE_USER)
PEDIDO = {"id_pedido": 10, "id_cuenta": 2, "estado": "pendiente", "total": 5.0, "fecha_creacion": None,
          "lineas": []}


def _c():
    pedidos_app.app.config["TESTING"] = True
    return pedidos_app.app.test_client()


def test_token_revocado_da_401():
    jti = decodificar(USER["Authorization"].split()[1])["jti"]
    redis_store.revocar_jti(jti, int(time.time()) + 60)
    assert _c().post("/api/pedidos", json={}, headers=USER).status_code == 401


def test_redis_caido_rutas_protegidas_503_y_health_informa(redis_falso, monkeypatch):
    monkeypatch.setattr("common.db.ping", lambda: True)
    c = _c()
    testing.redis_caido(redis_falso)
    assert c.get("/api/pedidos", headers=USER).status_code == 503
    assert c.post("/api/pedidos", json={"lineas": [{"id_libro": 1, "cantidad": 1}]}, headers=USER).status_code == 503
    h = c.get("/health")
    assert h.status_code == 200 and h.get_json()["redis"] == "error"


def test_crear_pedido_invalida_cache_del_catalogo(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pedidos_app.repository, "crear", lambda *a: 11)
    monkeypatch.setattr(pedidos_app.repository, "obtener", lambda i: dict(PEDIDO, id_pedido=i))
    monkeypatch.setattr(pedidos_app.redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    resp = _c().post("/api/pedidos", json={"lineas": [{"id_libro": 1, "cantidad": 1}]}, headers=USER)
    assert resp.status_code == 201 and llamadas == [1]


def test_crear_pedido_fallido_no_invalida(monkeypatch):
    llamadas = []

    def sin_stock(*a):
        raise Conflicto("Stock insuficiente")

    monkeypatch.setattr(pedidos_app.repository, "crear", sin_stock)
    monkeypatch.setattr(pedidos_app.redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    resp = _c().post("/api/pedidos", json={"lineas": [{"id_libro": 1, "cantidad": 1}]}, headers=USER)
    assert resp.status_code == 409 and llamadas == []


def test_cancelar_invalida_pero_enviar_no(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pedidos_app.repository, "cambiar_estado", lambda *a: None)
    monkeypatch.setattr(pedidos_app.redis_store, "cache_invalidar_libros", lambda: llamadas.append(1))
    c = _c()
    assert c.patch("/api/pedidos/10/estado", json={"estado": "cancelado"}, headers=USER).status_code == 200
    assert llamadas == [1]
    assert c.patch("/api/pedidos/10/estado", json={"estado": "enviado"},
                   headers=auth_header(1, ROLE_ADMIN)).status_code == 200
    assert llamadas == [1]


def test_invalidar_cache_con_redis_caido_no_rompe_el_pedido(redis_falso, monkeypatch):
    # la invalidacion es fail-open, pero con Redis caido requiere_jwt ya devuelve 503 antes:
    # se prueba la funcion directamente
    testing.redis_caido(redis_falso)
    redis_store.cache_invalidar_libros()  # no lanza
```

`pagos/tests/test_redis.py`: mismo patrón con `pagos_app`: revocado → `POST /api/pagos` 401; Redis caído → `GET /api/pagos` y `POST /api/pagos` 503 y `/health` 200 con `redis == "error"` y `servicio == "pagos"`; y un test `test_pago_no_invalida_cache` que parchea `pagos_app.repository.registrar` (devuelve un dict de pago) y verifica que `redis_store.cache_invalidar_libros` parcheado NO se llama (usar `monkeypatch.setattr(redis_store, "cache_invalidar_libros", ...)` sobre el módulo `common.redis_store`).

- [ ] **Step 2: Verificar que fallan**

Run: `for s in pedidos pagos; do (cd apps/services/$s && .venv/bin/python -m pytest tests/test_redis.py -q); done` → FAIL.

- [ ] **Step 3: Implementar**

`pedidos/app.py`: imports `from common import db as common_db, redis_store` (junto a `jwt_auth`) y `from common.ops import registrar_operacion`; después de `crear_swagger(...)`: `registrar_operacion(app, "pedidos", db_check=lambda: common_db.ping())`. En `crear_pedido`, después de `id_pedido = repository.crear(g.user_id, items)` y antes del `return`: `redis_store.cache_invalidar_libros()  # el stock cambio: el catalogo cacheado queda viejo`. En `cambiar_estado`, después de `repository.cambiar_estado(...)`: `if nuevo == "cancelado": redis_store.cache_invalidar_libros()  # devuelve stock`.

`pagos/app.py`: `from common import db as common_db`, `from common.ops import registrar_operacion`, y `registrar_operacion(app, "pagos", db_check=lambda: common_db.ping())`.

Ambos `.env.example`: `JWT_SECRET_KEY` (reemplaza `SECRET_KEY`), `REDIS_URL=redis://:change-me-redis-password@localhost:6379/0`, `REDIS_TIMEOUT=2`.

- [ ] **Step 4: Verificar**

Run: `for s in pedidos pagos; do (cd apps/services/$s && .venv/bin/python -m pytest tests -q); done`
Expected: PASS (los tests `*_manual.py` quedan SKIPPED).

- [ ] **Step 5: Commit**

```bash
git add apps/services/pedidos apps/services/pagos
git commit -m "feat(pedidos,pagos): /health y /metrics con Redis; pedidos invalida la cache del catalogo al cambiar stock"
```

---

### Task 7: Despliegue de Redis, documentación y verificación final

**Files:**
- Create: `apps/services/docker-compose.yml`, `apps/services/redis.env.example`
- Modify: `apps/services/README_JWT.md`, `docs/AI_CHANGELOG.md`

- [ ] **Step 1: `apps/services/docker-compose.yml`**

```yaml
# SOLO DESARROLLO LOCAL. En produccion se usa el Redis de GCP (REDIS_URL en cada servicio).
# Redis compartido por login, soap (books), users, authors, pedidos y pagos.
# Uso:  cp redis.env.example .env   (editar REDIS_PASSWORD)   &&   docker compose up -d redis
# noeviction: si la memoria se llena, las ESCRITURAS fallan (los servicios responden 503, fail-closed)
# en vez de expulsar claves de revocacion o sesiones.
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:?define REDIS_PASSWORD en .env}",
              "--appendonly", "no", "--maxmemory", "256mb", "--maxmemory-policy", "noeviction"]
    ports:
      - "127.0.0.1:6379:6379"
    environment:
      REDIS_PASSWORD: ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a \"$$REDIS_PASSWORD\" --no-auth-warning ping | grep PONG"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped
```

`apps/services/redis.env.example`:

```
# Contraseña de Redis (la misma que va en REDIS_URL de cada servicio). Cámbiala.
REDIS_PASSWORD=change-me-redis-password
```

Verificar que `.env` esté ignorado (`git check-ignore apps/services/.env`); si no, agregar `apps/services/.env` al `.gitignore` raíz.

- [ ] **Step 2: Actualizar `README_JWT.md`**

Agregar una sección **Redis** con: (a) tabla de claves (`jwt:revoked:<jti>`, `session:<jti>`, `refresh:<jti>`, `books:list:<hash>`, `books:<isbn>`) con su TTL; (b) modos de fallo (fail-closed → 503 / fail-open caché) y qué endpoints siguen públicos con Redis caído; (c) variables `REDIS_URL` (formato `redis://:password@host:6379/0`, `rediss://` para TLS), `REDIS_TIMEOUT`, `BOOKS_CACHE_TTL`, `JWT_SECRET_KEY` (alias `SECRET_KEY`); (d) Redis en producción = el de GCP (`REDIS_URL=redis://:<password>@<host-interno>:6379/0`; los servicios corren en la misma instancia, así que `localhost`; requisitos: `bind 127.0.0.1`, `requirepass`, `noeviction`, NO abrir 6379 en el firewall de GCP; `rediss://` solo si algún día Redis queda en otra máquina) y, solo para desarrollo local, `docker compose up -d redis` o `brew install redis && redis-server --requirepass <password> --maxmemory 256mb --maxmemory-policy noeviction`; (e) `/health` (`{"status","db","redis"}`) y `/metrics` (lista de métricas: `cache_hits_total`, `cache_misses_total`, `cache_invalidations_total`, `redis_errors_total`, `redis_latency_seconds_sum/count`, `jwt_revocation_checks_total`, `jwt_rejected_total`) y la advertencia de que `/metrics` es público y conviene restringirlo en el proxy; (f) el caso de caché obsoleta: el stock cambiado por `pedidos` invalida `books:*`, pero un cambio hecho directo en PostgreSQL se verá tras ≤ `BOOKS_CACHE_TTL` s; (g) corregir las frases que dicen que el logout es sin estado y que `SECRET_KEY` es el nombre de la variable. Dejar explícito si la verificación contra el Redis real de GCP (Task 8) se hizo o no; sin ella, la verificación fue solo con fakeredis.

- [ ] **Step 3: Entrada en `docs/AI_CHANGELOG.md`**

Leer el formato existente (`tail -40 docs/AI_CHANGELOG.md`) y agregar una entrada fechada 2026-10-06 con: capa Redis común, revocación por `jti`, sesiones/refresh en Redis, caché de catálogo, `/health` y `/metrics`, `JWT_SECRET_KEY`, compose de Redis, y la nota de verificación solo con fakeredis.

- [ ] **Step 4: Verificación completa**

```bash
cd apps/services
login/.venv/bin/python -m pytest common/tests -q
for s in login soap users authors pedidos pagos; do (cd $s && .venv/bin/python -m pytest tests -q) || echo "FALLO $s"; done
grep -rn "REDIS_URL" */.env.example | wc -l        # esperado: 6
grep -rln "SuperSecreta\|redis://:[A-Za-z0-9]" --include=*.py . | grep -v tests || true   # sin contraseñas reales en codigo
```
Expected: todas las suites PASS (los `*_manual.py` fuera de pytest o SKIPPED), 6 `REDIS_URL`, ninguna contraseña real en código fuente. Reportar los conteos exactos por suite. **No** arrancar los servicios ni conectarse a ninguna base de datos ni a un Redis real salvo lo que autorice la Task 8; decir explícitamente qué verificación quedó pendiente.

- [ ] **Step 5: Commit**

```bash
git add apps/services/docker-compose.yml apps/services/redis.env.example apps/services/README_JWT.md docs/AI_CHANGELOG.md
git commit -m "docs(redis): compose de Redis protegido, guia de operacion y entrada de changelog"
```

---

---

### Task 8: Verificación contra el Redis real de GCP (opcional, solo con autorización del usuario)

**Files:**
- Create: `apps/services/common/tests/test_redis_real.py`

**Interfaces:**
- Consumes: `common.redis_store`; variable de entorno `REDIS_REAL_URL` (la entrega el usuario en el momento; no se guarda en archivos, no se imprime, no se commitea).
- Produces: pruebas que se SALTAN salvo que `REDIS_REAL_URL` esté definida; usan solo claves temporales con prefijo `zz-test:<uuid>:` y `jti` aleatorios, y las borran al terminar. No tocan `books:*` ni `session:*` reales.

- [ ] **Step 1: Escribir las pruebas (se saltan por defecto)**

```python
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
```

(`test_politica_noeviction_configurada` puede fallar si el proveedor deshabilita `CONFIG`, p. ej. Memorystore: en ese caso marcarlo `pytest.skip` con el motivo y reportarlo.)

- [ ] **Step 2: Verificar que se saltan sin autorización**

Run: `cd apps/services && login/.venv/bin/python -m pytest common/tests/test_redis_real.py -q`
Expected: todos SKIPPED.

- [ ] **Step 3: Ejecutarlas contra GCP solo si el usuario autoriza**

Como Redis solo escucha en `localhost` de la instancia de GCP, estas pruebas **no se pueden correr desde la Mac**: se corren **en la instancia**, tras desplegar la rama, con `REDIS_REAL_URL=redis://:<password>@localhost:6379/0 .venv/bin/python -m pytest common/tests/test_redis_real.py -q`. El controlador no las ejecuta; deja el comando exacto al usuario (que lo corre con `! ...` o por SSH) y reporta que quedan pendientes hasta que el usuario pegue el resultado. Nunca imprimir la URL.

- [ ] **Step 4: Commit**

```bash
git add apps/services/common/tests/test_redis_real.py
git commit -m "test(common): pruebas opcionales contra el Redis real (se saltan sin REDIS_REAL_URL)"
```

---

## Self-Review

**Cobertura del diseño aprobado:** capa común y modos fail-closed/open (Task 1) · `jti`, `JWT_SECRET_KEY` y revocación `jwt:revoked:<jti>` en cada servicio vía `requiere_jwt` (Task 2; Tasks 5–6 la prueban en users/authors/pedidos/pagos y Task 4 en soap) · login con `session:`/`refresh:`, extend que revoca, refresh que exige Redis y `/logout` que borra y revoca (Task 3) · caché `books:list:`/`books:<isbn>` con TTL 60 s e invalidación tras escrituras exitosas + invalidación desde pedidos (Tasks 4, 6) · timeouts/autenticación/reconexión (Task 1: `socket_timeout`, `health_check_interval`, `retry_on_timeout`, contraseña en URL, `rediss://`) · métricas y `/health` (Tasks 1, 3–6) · despliegue y `REDIS_URL` en los seis `.env.example` (Tasks 2–7) · endpoints públicos intactos (Review Focus 1 y tests de rutas públicas con Redis caído).

**Ajuste del plan respecto al diseño:** `jwt_auth.crear_token` ganó el parámetro `jti` (necesario para que login enlace sesión y refresh); `/health` de login conserva `status` dependiente solo de la BD (el cliente actual mira `db == "ok"`).

**Placeholders:** el único punto abierto es la nota de la Task 4 Step 1 sobre reutilizar los fakes existentes de `test_libros_db.py`; es una instrucción concreta, no un hueco.

**Consistencia de tipos:** `redis_store.guardar_sesion(jti, datos, ttl)`, `obtener_sesion(jti) -> dict|None`, `revocar_jti(jti, exp)`, `jti_revocado(jti) -> bool`, `guardar_refresh(jti, user_id, ttl)`, `refresh_vigente(jti)`, `cache_get/cache_set/cache_invalidar_libros` se usan con las mismas firmas en `jwt_auth`, `login/service.py`, `soap/app.py` y `pedidos/app.py`; los datos de sesión (`user_id, role_id, email, jti_refresh, exp_refresh`) coinciden entre `_nuevo_acceso`, `cerrar_sesion`, `extender_sesion` y los tests.
