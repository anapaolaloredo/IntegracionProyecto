# Microservicios JWT (Users, Authors, Pedidos, Pagos) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar `login` y `soap` a JWT HS256 (30 min + refresh token) y agregar los microservicios Users, Authors, Pedidos y Pagos, todos protegidos con `Authorization: Bearer <JWT>` en POST/PUT/PATCH/DELETE.

**Architecture:** Un módulo compartido `apps/services/common` (validación JWT, helpers Flask, conexión psycopg) que importan todos los servicios. Cada servicio nuevo es un Flask sin blueprints con `app.py` + `repository.py` sobre la base `library`. Pedidos y Pagos usan transacciones con `SELECT … FOR UPDATE` sobre la misma base.

**Tech Stack:** Python 3, Flask 3.0.3, flask-cors 4.0.1, psycopg 3 (`psycopg[binary]==3.2.10`) en servicios nuevos y login (soap sigue con psycopg2), PyJWT 2.9.0, flasgger 0.9.7.1, python-dotenv 1.0.1, pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-microservicios-jwt-design.md`

## Global Constraints

- Algoritmo `HS256`; la verificación fija `algorithms=["HS256"]` y exige los claims `exp`, `iat`, `user_id`, `role_id`, `type`.
- `SECRET_KEY` solo desde variable de entorno, sin valor por defecto en código; si falta, el servicio no arranca. Mismo valor en todos los servicios.
- Access token: 30 min (`SESSION_TTL_MINUTES=30`). Refresh token: 7 días (`REFRESH_TTL_DAYS=7`). `type` es `access` o `refresh`; un refresh nunca vale como acceso.
- Roles: `admin` → `role_id=1`, `cliente` → `role_id=2` (la columna `cuentas.rol` conserva `'admin'|'cliente'`; no hay tabla `roles`).
- Token ausente/inválido/expirado → 401. Rol insuficiente → 403.
- POST, PUT, PATCH y DELETE exigen JWT en Users, Authors, Pedidos, Pagos y en soap. GET de catálogo (libros, autores, roles) público; GET de usuarios, pedidos y pagos exigen JWT.
- Servicios nuevos: Flask sin blueprints, solo `psycopg` (v3), respuestas JSON `{"mensaje": ...}` en error, Swagger con flasgger, `.env` por servicio (en `.gitignore`), `.env.example` versionado.
- Puertos: login 5000, soap 5001, users 5002, authors 5003, pedidos 5004, pagos 5005.
- CORS: `CORS_ORIGINS` (lista separada por comas); por defecto `*` para no romper desarrollo; en producción solo los orígenes de los clientes.
- Nunca registrar contraseñas. Los tokens solo se imprimen en `soap` cuando `LOG_TOKENS=true` (por defecto `true`, el profe lo usa para revisar transacciones).
- Tablas de usuarios reales: `cuentas` (id_cuenta, correo, contrasena_hash, rol, fecha_registro) y `personas` (id_cuenta, nombre, apellido_paterno, apellido_materno), definidas en `data/migrations/2026-09-18_tablas_login.sql`. `id_cuenta` es el `user_id` del JWT.
- Tests por servicio, sin base de datos real (se monkeypatchea `repository`), salvo `test_stock_manual.py` de pedidos (requiere `RUN_DB_TESTS=1`).
- Comandos de prueba se ejecutan desde el directorio del servicio: `cd apps/services/<servicio> && .venv/bin/python -m pytest tests -q`.

## Review Focus

1. Token con `alg: none`, firmado con otra clave, o con `user_id` no entero/`role_id` fuera de {1,2} → 401 (Task 1).
2. Refresh usado como acceso, y acceso usado como refresh en `/session/refresh` → 401 (Tasks 1, 2).
3. Header `Authorization` mal formado (`Bearer` sin token, `Token xxx`, minúsculas `bearer`) y cuerpo JSON que no es objeto → 401 / 400 (Tasks 1, 6–9).
4. Pedido con líneas duplicadas del mismo libro, cantidad 0, negativa, decimal o booleana → 400 sin tocar stock; dos pedidos que se disputan el último ejemplar → uno 409 y stock nunca negativo (Task 8).
5. Pagar dos veces el mismo pedido, un pedido ajeno, o uno cancelado/enviado → 409 / 403 y el estado del pedido no cambia (Task 9).

---

## File Structure

```
apps/services/
  common/
    __init__.py
    jwt_auth.py          # crear_token, decodificar, requiere_jwt, roles
    web.py               # ErrorDominio y subclases, configurar_app, cuerpo_json, crear_swagger, parse_origins
    db.py                # get_connection() psycopg v3 desde env
    testing.py           # auth_header() para tests
    tests/conftest.py, tests/test_jwt_auth.py
  login/   (modifica service.py, app.py, config/settings.py, db/repository.py, requirements.txt, .env.example, tests)
  soap/    (modifica app.py, requirements.txt, .env.example, tests/test_auth.py)
  users/   app.py, repository.py, requirements.txt, .env.example, .gitignore, tests/
  authors/ app.py, repository.py, requirements.txt, .env.example, .gitignore, tests/
  pedidos/ app.py, repository.py, transiciones.py, requirements.txt, .env.example, .gitignore, tests/
  pagos/   app.py, repository.py, requirements.txt, .env.example, .gitignore, tests/
  README_JWT.md
data/migrations/2026-10-06_pedidos_pagos.sql
apps/desktop_app/  (core/auth_api.py, core/session_store.py, main.py, ui/main_window.py, tests/test_core.py)
```

---

### Task 1: Módulo compartido `common`

**Files:**
- Create: `apps/services/common/__init__.py` (vacío)
- Create: `apps/services/common/jwt_auth.py`
- Create: `apps/services/common/web.py`
- Create: `apps/services/common/db.py`
- Create: `apps/services/common/testing.py`
- Create: `apps/services/common/tests/conftest.py`
- Test: `apps/services/common/tests/test_jwt_auth.py`

**Interfaces:**
- Produces (`common.jwt_auth`): `ALGORITHM`, `ROLE_ADMIN=1`, `ROLE_USER=2`, `ROLE_IDS={"admin":1,"cliente":2}`, `ROLE_NAMES={1:"admin",2:"cliente"}`, `class TokenInvalido(Exception)`, `obtener_secret() -> str`, `crear_token(user_id:int, role_id:int, tipo:str, ttl_segundos:int) -> str`, `decodificar(token:str, tipo:str="access") -> dict`, `extraer_token(valor_header:str|None) -> str|None`, `requiere_jwt(roles=None, error_response=None, on_event=None)` decorador que deja `g.user_id`, `g.role_id`. `error_response(mensaje, status)` devuelve un Response; `on_event(token, datos, resultado)` con `resultado=None` si pasó o `(status, mensaje)`.
- Produces (`common.web`): `ErrorDominio` (+ `Invalido` 400, `Prohibido` 403, `NoEncontrado` 404, `Conflicto` 409), `parse_origins(valor)->list[str]`, `configurar_app(app)`, `cuerpo_json()->dict`, `crear_swagger(app, titulo)`.
- Produces (`common.db`): `get_connection()`.
- Produces (`common.testing`): `auth_header(user_id=2, role_id=2, tipo="access", ttl=1800) -> dict`.

- [ ] **Step 1: Preparar dependencias y carpeta**

```bash
cd apps/services && mkdir -p common/tests && touch common/__init__.py
login/.venv/bin/pip install PyJWT==2.9.0 flask-cors==4.0.1 pytest
```

- [ ] **Step 2: Escribir `common/tests/conftest.py` y los tests que fallan**

`common/tests/conftest.py`:

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")
```

`common/tests/test_jwt_auth.py`:

```python
import base64
import json
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
    falso = jwt.encode({"user_id": 1, "role_id": 1, "type": "access", "iat": ahora, "exp": ahora + 60},
                       "otra-clave-distinta-de-32-bytes-0123456789", algorithm="HS256")
    with pytest.raises(TokenInvalido):
        decodificar(falso)


def test_alg_none_se_rechaza():
    ahora = int(time.time())
    payload = {"user_id": 1, "role_id": 1, "type": "access", "iat": ahora, "exp": ahora + 60}
    sin_firma = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(payload)}."
    with pytest.raises(TokenInvalido):
        decodificar(sin_firma)


def test_alg_distinto_hs512_se_rechaza():
    ahora = int(time.time())
    token = jwt.encode({"user_id": 1, "role_id": 1, "type": "access", "iat": ahora, "exp": ahora + 60},
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
    token = jwt.encode({"user_id": user_id, "role_id": role_id, "type": "access", "iat": ahora, "exp": ahora + 60},
                       jwt_auth.obtener_secret(), algorithm="HS256")
    with pytest.raises(TokenInvalido):
        decodificar(token)


def test_falta_claim_obligatorio():
    ahora = int(time.time())
    token = jwt.encode({"user_id": 1, "type": "access", "iat": ahora, "exp": ahora + 60},
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
```

- [ ] **Step 3: Verificar que fallan**

Run: `cd apps/services && login/.venv/bin/python -m pytest common/tests -q`
Expected: FAIL (`ImportError: cannot import name 'jwt_auth'`).

- [ ] **Step 4: Implementar `common/jwt_auth.py`**

```python
"""Validacion JWT compartida por todos los microservicios (HS256).

La SECRET_KEY se lee solo del entorno. Los claims obligatorios son
exp, iat, user_id, role_id y type ("access" | "refresh")."""

import os
import time
from functools import wraps

import jwt
from flask import g, jsonify, request

ALGORITHM = "HS256"
ROLE_ADMIN = 1
ROLE_USER = 2
ROLE_IDS = {"admin": ROLE_ADMIN, "cliente": ROLE_USER}
ROLE_NAMES = {valor: nombre for nombre, valor in ROLE_IDS.items()}
_CLAIMS_OBLIGATORIOS = ["exp", "iat", "user_id", "role_id", "type"]


class TokenInvalido(Exception):
    """El token falta, esta mal formado, vencio, o sus claims no son validos."""


def obtener_secret():
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY no esta definida en el entorno")
    return secret


def crear_token(user_id, role_id, tipo, ttl_segundos):
    ahora = int(time.time())
    payload = {"user_id": user_id, "role_id": role_id, "type": tipo,
               "iat": ahora, "exp": ahora + int(ttl_segundos)}
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
    """Exige Authorization: Bearer <JWT de acceso>. `roles` es una lista de
    role_id permitidos (None = cualquier rol valido). Deja g.user_id y g.role_id."""
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
                    resultado = (401, "Token invalido o expirado")
                else:
                    if roles is not None and datos["role_id"] not in roles:
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

- [ ] **Step 5: Implementar `common/web.py`, `common/db.py`, `common/testing.py`**

`common/web.py`:

```python
"""Utilidades Flask compartidas por los microservicios nuevos."""

import os
from datetime import date, datetime
from decimal import Decimal

from flasgger import Swagger
from flask import jsonify, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS


class ErrorDominio(Exception):
    status = 400


class Invalido(ErrorDominio):
    status = 400


class Prohibido(ErrorDominio):
    status = 403


class NoEncontrado(ErrorDominio):
    status = 404


class Conflicto(ErrorDominio):
    status = 409


class _Proveedor(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def parse_origins(valor):
    origenes = [o.strip() for o in (valor or "*").split(",") if o.strip()]
    return origenes or ["*"]


def configurar_app(app):
    """CORS por CORS_ORIGINS, JSON con fechas ISO y errores de dominio en JSON."""
    CORS(app, origins=parse_origins(os.getenv("CORS_ORIGINS", "*")))
    app.json = _Proveedor(app)

    @app.errorhandler(ErrorDominio)
    def _dominio(err):
        return jsonify({"mensaje": str(err)}), err.status

    @app.errorhandler(404)
    def _no_encontrada(_):
        return jsonify({"mensaje": "Ruta no encontrada"}), 404

    @app.errorhandler(405)
    def _metodo(_):
        return jsonify({"mensaje": "Metodo no permitido"}), 405


def cuerpo_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise Invalido("Se esperaba un cuerpo JSON (objeto).")
    return datos


def crear_swagger(app, titulo):
    app.config["SWAGGER"] = {"title": titulo, "uiversion": 3}
    return Swagger(app, template={"securityDefinitions": {"Bearer": {
        "type": "apiKey", "name": "Authorization", "in": "header",
        "description": "Bearer <JWT de acceso>"}}})
```

`common/db.py`:

```python
"""Conexion psycopg 3 a la base `library`, configurada solo por entorno."""

import os

import psycopg


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "library"),
        user=os.getenv("DB_USER", "library_user"),
        password=os.getenv("DB_PASSWORD", ""),
    )
```

`common/testing.py`:

```python
"""Ayudas para las pruebas de los servicios (requiere SECRET_KEY en el entorno)."""

from common.jwt_auth import ROLE_USER, crear_token


def auth_header(user_id=2, role_id=ROLE_USER, tipo="access", ttl=1800):
    return {"Authorization": f"Bearer {crear_token(user_id, role_id, tipo, ttl)}"}
```

- [ ] **Step 6: Verificar que pasan**

Run: `cd apps/services && login/.venv/bin/python -m pytest common/tests -q`
Expected: todos PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/services/common
git commit -m "feat(common): modulo compartido de validacion JWT HS256 y utilidades Flask"
```

---

### Task 2: `login` emite y valida JWT (acceso 30 min + refresh)

**Files:**
- Modify: `apps/services/login/config/settings.py`
- Modify: `apps/services/login/db/repository.py` (agregar `obtener_usuario_por_id`)
- Modify: `apps/services/login/service.py`
- Modify: `apps/services/login/app.py` (`/login/verify`, `/logout`, `/session`, `/session/extend`, nuevo `/session/refresh`, arranque)
- Modify: `apps/services/login/requirements.txt`, `apps/services/login/.env.example`
- Modify: `apps/services/login/tests/test_service_manual.py`
- Create: `apps/services/login/tests/conftest.py`
- Test: `apps/services/login/tests/test_jwt_service.py`

**Interfaces:**
- Consumes: `common.jwt_auth` (`crear_token`, `decodificar`, `TokenInvalido`, `ROLE_IDS`).
- Produces: `service.verificar_login(email, codigo) -> {"session_token", "refresh_token"}`; `service.consultar_sesion(token) -> dict` (`autenticado`, y si es True: `id_usuario`, `email`, `nombre`, `role_id`, `expira_en`, `segundos_restantes`); `service.extender_sesion(token) -> {"session_token","expira_en","segundos_restantes"}`; `service.refrescar_sesion(refresh_token) -> mismo formato`; `service.cerrar_sesion(token) -> None`; `repository.obtener_usuario_por_id(id_usuario) -> dict|None` con claves `id_usuario, correo, rol, nombre`.
- Endpoints: `POST /login/verify` → `{session_token, refresh_token}`; `GET /session`; `POST /session/extend` (Bearer access); `POST /session/refresh` (cuerpo `{"refresh_token": "..."}`); `POST /logout`.

- [ ] **Step 1: Dependencias y conftest**

Agregar a `login/requirements.txt` la línea `PyJWT==2.9.0`. Agregar a `login/.env.example`:

```
# Mismo valor en TODOS los servicios (login, soap, users, authors, pedidos, pagos)
SECRET_KEY=change-me-same-value-in-every-service
REFRESH_TTL_DAYS=7
```

En `login/config/settings.py`, después de `load_dotenv()` agregar:

```python
import sys
from pathlib import Path

# apps/services contiene el paquete compartido `common`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
```

y al final del archivo:

```python
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TTL_DAYS", "7"))
```

`login/tests/conftest.py`:

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")
```

```bash
cd apps/services/login && .venv/bin/pip install -r requirements.txt pytest flask-cors
```

- [ ] **Step 2: Escribir los tests que fallan** — `login/tests/test_jwt_service.py`

```python
from unittest.mock import patch

import pytest

import service
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, crear_token, decodificar
from errors import SesionInvalida

USUARIO = {"id_usuario": 5, "correo": "a@b.co", "rol": "cliente", "nombre": "Ana"}
ADMIN = {"id_usuario": 1, "correo": "r@b.co", "rol": "admin", "nombre": "Root"}


def test_verificar_login_emite_acceso_y_refresh():
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=USUARIO), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado"), \
         patch.object(service, "verificar_codigo", return_value=True):
        tokens = service.verificar_login("a@b.co", "123456")
    acceso = decodificar(tokens["session_token"], "access")
    refresh = decodificar(tokens["refresh_token"], "refresh")
    assert acceso["user_id"] == 5 and acceso["role_id"] == ROLE_USER
    assert acceso["exp"] - acceso["iat"] == 30 * 60
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 3600


def test_admin_recibe_role_id_1():
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=ADMIN), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado"), \
         patch.object(service, "verificar_codigo", return_value=True):
        tokens = service.verificar_login("r@b.co", "123456")
    assert decodificar(tokens["session_token"])["role_id"] == ROLE_ADMIN


def test_consultar_sesion_valida_localmente():
    token = crear_token(5, ROLE_USER, "access", 600)
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        estado = service.consultar_sesion(token)
    assert estado["autenticado"] is True and estado["email"] == "a@b.co"
    assert 590 <= estado["segundos_restantes"] <= 600 and estado["role_id"] == ROLE_USER


@pytest.mark.parametrize("token", [None, "", "basura", "a.b.c"])
def test_consultar_sesion_token_invalido_no_autenticado(token):
    assert service.consultar_sesion(token) == {"autenticado": False}


def test_consultar_sesion_expirado_no_autenticado():
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "access", -5)) == {"autenticado": False}


def test_consultar_sesion_refresh_no_cuenta():
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "refresh", 600)) == {"autenticado": False}


def test_extender_emite_token_nuevo():
    viejo = crear_token(5, ROLE_USER, "access", 60)
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        resp = service.extender_sesion(viejo)
    assert decodificar(resp["session_token"])["user_id"] == 5
    assert 1790 <= resp["segundos_restantes"] <= 1800


def test_extender_con_token_expirado_o_refresh_falla():
    for malo in (crear_token(5, ROLE_USER, "access", -5), crear_token(5, ROLE_USER, "refresh", 600), None):
        with pytest.raises(SesionInvalida):
            service.extender_sesion(malo)


def test_refrescar_canjea_refresh_por_acceso_con_rol_actual():
    refresh = crear_token(5, ROLE_USER, "refresh", 600)
    promovido = dict(USUARIO, rol="admin")
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=promovido):
        resp = service.refrescar_sesion(refresh)
    assert decodificar(resp["session_token"])["role_id"] == ROLE_ADMIN


def test_refrescar_rechaza_un_token_de_acceso():
    with pytest.raises(SesionInvalida):
        service.refrescar_sesion(crear_token(5, ROLE_USER, "access", 600))


def test_refrescar_usuario_borrado_falla():
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=None):
        with pytest.raises(SesionInvalida):
            service.refrescar_sesion(crear_token(5, ROLE_USER, "refresh", 600))


def test_cerrar_sesion_exige_token_valido():
    service.cerrar_sesion(crear_token(5, ROLE_USER, "access", 60))
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion("basura")


def test_rutas_http():
    import app as login_app
    c = login_app.app.test_client()
    assert c.post("/session/extend?format=json").status_code == 401
    assert c.post("/session/refresh?format=json", json={}).status_code == 401
    assert c.post("/session/refresh?format=json", json={"refresh_token": "x"}).status_code == 401
    assert c.post("/logout?format=json").status_code == 401
    assert c.get("/session?format=json").get_json() == {"autenticado": False}
```

- [ ] **Step 3: Verificar que fallan**

Run: `cd apps/services/login && .venv/bin/python -m pytest tests/test_jwt_service.py -q`
Expected: FAIL (`verificar_login` devuelve un token opaco, `refrescar_sesion` no existe).

- [ ] **Step 4: `repository.obtener_usuario_por_id`**

Agregar a `login/db/repository.py` después de `obtener_usuario_por_correo`:

```python
def obtener_usuario_por_id(id_usuario):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT c.id_cuenta AS id_usuario, c.correo, c.rol, p.nombre "
                "FROM cuentas c JOIN personas p ON p.id_cuenta = c.id_cuenta "
                "WHERE c.id_cuenta = %s",
                (id_usuario,),
            )
            return cur.fetchone()
```

(Las funciones de sesión opaca — `crear_sesion`, `obtener_sesion_vigente`, `extender_sesion`, `eliminar_sesion` — quedan sin uso; no se borran para no tocar `test_repository_manual.py`.)

- [ ] **Step 5: Reescribir las funciones de sesión en `login/service.py`**

Reemplazar los imports de `config.settings`/`auth.security` y las funciones `verificar_login`, `cerrar_sesion`, `consultar_sesion`, `extender_sesion` por:

```python
import time
from datetime import datetime, timedelta, timezone

from config.settings import SESSION_TTL_MINUTES, CODE_TTL_MINUTES, REFRESH_TTL_DAYS
from common.jwt_auth import ROLE_IDS, TokenInvalido, crear_token, decodificar
```

(quitar `generar_token` del import de `auth.security`), y:

```python
def _emitir_acceso(usuario):
    role_id = ROLE_IDS[usuario["rol"]]
    token = crear_token(usuario["id_usuario"], role_id, "access", SESSION_TTL_MINUTES * 60)
    return token, decodificar(token, "access")["exp"]


def _datos_acceso(usuario):
    token, exp = _emitir_acceso(usuario)
    return {
        "session_token": token,
        "expira_en": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
        "segundos_restantes": max(0, exp - int(time.time())),
    }


def _decodificar_o_none(token, tipo):
    if not token:
        return None
    try:
        return decodificar(token, tipo)
    except TokenInvalido:
        return None


def verificar_login(email, codigo):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario:
        raise CodigoInvalido("Codigo invalido o expirado.")
    pendiente = repository.obtener_codigo_vigente(usuario["id_usuario"])
    if not pendiente or not verificar_codigo(codigo, pendiente["codigo_hash"]):
        raise CodigoInvalido("Codigo invalido o expirado.")
    repository.marcar_codigo_usado(pendiente["id_codigo"])
    role_id = ROLE_IDS[usuario["rol"]]
    return {
        "session_token": crear_token(usuario["id_usuario"], role_id, "access", SESSION_TTL_MINUTES * 60),
        "refresh_token": crear_token(usuario["id_usuario"], role_id, "refresh", REFRESH_TTL_DAYS * 86400),
    }


def cerrar_sesion(token):
    # JWT sin estado: el token vive hasta expirar; aqui solo se valida.
    if not _decodificar_o_none(token, "access"):
        raise SesionInvalida("Token de sesion invalido o expirado.")


def consultar_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
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
        "expira_en": datetime.fromtimestamp(datos["exp"], tz=timezone.utc).isoformat(),
        "segundos_restantes": max(0, datos["exp"] - int(time.time())),
    }


def extender_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        raise SesionInvalida("Token de sesion invalido o expirado.")
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    return _datos_acceso(usuario)


def refrescar_sesion(refresh_token):
    datos = _decodificar_o_none(refresh_token, "refresh")
    if not datos:
        raise SesionInvalida("Refresh token invalido o expirado.")
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    return _datos_acceso(usuario)
```

Eliminar los imports ya sin uso (`timedelta` sigue siéndolo para `iniciar_login`; verificar con `python -m pyflakes service.py` o a ojo).

- [ ] **Step 6: Rutas y arranque en `login/app.py`**

Al inicio, después de `from config.settings import PORT` agregar `from common import jwt_auth` y, después de crear `app`, `jwt_auth.obtener_secret()  # falla al arrancar si no hay SECRET_KEY`.

`/login/verify`: reemplazar las dos últimas líneas del cuerpo por:

```python
    datos = request.get_json(force=True, silent=True) or {}
    tokens = service.verificar_login(datos.get("email"), datos.get("codigo"))
    return responder("sesion", tokens)
```

y en su docstring cambiar la respuesta 200 a `"Sesion creada. JSON: {\\"session_token\\": \\"<JWT 30 min>\\", \\"refresh_token\\": \\"<JWT 7 dias>\\"}"`.

Agregar después de `/session/extend`:

```python
@app.route("/session/refresh", methods=["POST"])
def session_refresh():
    """
    Canjea un refresh token por un nuevo JWT de acceso (30 min).
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
      - in: body
        name: body
        schema:
          type: object
          required: [refresh_token]
          properties:
            refresh_token: {type: string}
    responses:
      200:
        description: "JSON: {\\"session_token\\": \\"...\\", \\"expira_en\\": \\"...\\", \\"segundos_restantes\\": 1800}"
      401:
        description: Refresh token invalido o expirado
    """
    datos = request.get_json(force=True, silent=True) or {}
    return responder("sesion", service.refrescar_sesion(datos.get("refresh_token")))
```

En el docstring de `/session/extend` indicar que ahora devuelve un `session_token` nuevo (el anterior sigue valiendo hasta expirar).

- [ ] **Step 7: Actualizar el test manual `login/tests/test_service_manual.py`**

Reemplazar desde `token = service.verificar_login(...)` hasta antes de `assert service.verificar_salud() is True` por:

```python
        tokens = service.verificar_login(CORREO_PRUEBA, codigo_capturado["valor"])
        token = tokens["session_token"]
        assert tokens["refresh_token"]
        print("verificar_login OK -> JWT de acceso y refresh emitidos")

        estado = service.consultar_sesion(token)
        assert estado["autenticado"] is True
        assert estado["email"] == CORREO_PRUEBA
        assert 0 < estado["segundos_restantes"] <= 30 * 60
        print("consultar_sesion(token valido) OK")

        extendida = service.extender_sesion(token)
        assert extendida["segundos_restantes"] >= estado["segundos_restantes"]
        print("extender_sesion OK")

        renovada = service.refrescar_sesion(tokens["refresh_token"])
        assert renovada["session_token"]
        print("refrescar_sesion OK")

        service.cerrar_sesion(token)
        print("cerrar_sesion OK (JWT sin estado: el token vive hasta expirar)")

        try:
            service.cerrar_sesion("token-basura")
            raise AssertionError("Debio lanzar SesionInvalida")
        except SesionInvalida:
            print("cerrar_sesion con token invalido OK")

```

- [ ] **Step 8: Verificar**

Run: `cd apps/services/login && .venv/bin/python -m pytest tests/test_jwt_service.py tests/test_security.py tests/test_formatters.py tests/test_sender.py -q`
Expected: PASS. (Los `*_manual.py` requieren BD real y no se ejecutan con pytest.)

- [ ] **Step 9: Commit**

```bash
git add apps/services/login
git commit -m "feat(login): emitir JWT HS256 de acceso (30 min) y refresh token; /session/refresh"
```

---

### Task 3: `soap` valida JWT localmente

**Files:**
- Modify: `apps/services/soap/app.py` (imports líneas 9-22, constantes líneas 33-38, `sesion_valida`/`requiere_sesion` líneas ~268-300)
- Modify: `apps/services/soap/requirements.txt`, `apps/services/soap/.env.example`
- Test: `apps/services/soap/tests/test_auth.py` (reemplazar)

**Interfaces:**
- Consumes: `common.jwt_auth.requiere_jwt`, `common.web.parse_origins`.
- Produces: decorador `requiere_sesion` (mismo nombre, mismas rutas decoradas), `LOG_TOKENS`.

- [ ] **Step 1: Reescribir `soap/tests/test_auth.py` (falla primero)**

```python
"""Pruebas de la proteccion de escritura con JWT. Uso:
    cd apps/services/soap && .venv/bin/python -m pytest tests -q
No requieren PostgreSQL ni login: el JWT se valida localmente."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")

import pytest

import app as books
from common.jwt_auth import crear_token


@pytest.fixture
def cliente():
    books.app.config["TESTING"] = True
    return books.app.test_client()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/libros"),
    ("put", "/api/libros/123"),
    ("delete", "/api/libros/123"),
])
def test_escritura_sin_token_da_401(cliente, metodo, ruta):
    assert getattr(cliente, metodo)(ruta, json={}).status_code == 401


@pytest.mark.parametrize("encabezado", ["Bearer", "Token abc", "Bearer a b", ""])
def test_encabezado_mal_formado_da_401(cliente, encabezado):
    resp = cliente.delete("/api/libros/123", headers={"Authorization": encabezado})
    assert resp.status_code == 401


def test_token_invalido_da_401(cliente):
    assert cliente.delete("/api/libros/123", headers=_h("malo")).status_code == 401


def test_token_expirado_da_401(cliente):
    assert cliente.delete("/api/libros/123", headers=_h(crear_token(1, 2, "access", -5))).status_code == 401


def test_refresh_token_no_sirve_como_acceso(cliente):
    assert cliente.delete("/api/libros/123", headers=_h(crear_token(1, 2, "refresh", 600))).status_code == 401


def test_token_valido_pasa_a_la_vista(cliente):
    # Cuerpo vacio: la vista responde 400 de validacion, prueba de que el decorador dejo pasar.
    resp = cliente.post("/api/libros", json={}, headers=_h(crear_token(1, 2, "access", 600)))
    assert resp.status_code not in (401, 403, 503)


def test_error_sigue_siendo_xml(cliente):
    resp = cliente.post("/api/libros", json={})
    assert resp.mimetype == "application/xml" and b"<error>" in resp.data


def test_log_no_incluye_token_si_log_tokens_false(cliente, monkeypatch, capsys):
    monkeypatch.setattr(books, "LOG_TOKENS", False)
    token = crear_token(1, 2, "access", 600)
    cliente.delete("/api/libros/123", headers=_h(token))
    assert token not in capsys.readouterr().out


def test_log_incluye_token_si_log_tokens_true(cliente, monkeypatch, capsys):
    monkeypatch.setattr(books, "LOG_TOKENS", True)
    token = crear_token(1, 2, "access", 600)
    cliente.delete("/api/libros/123", headers=_h(token))
    assert token in capsys.readouterr().out


@pytest.mark.parametrize("ruta", ["/api/libros", "/api/libros/123", "/api/libros/catalogo"])
def test_lecturas_no_piden_token(cliente, monkeypatch, ruta):
    monkeypatch.setattr(books, "fetch_books", lambda *a, **k: [])
    monkeypatch.setattr(books, "get_connection", lambda: (_ for _ in ()).throw(RuntimeError("sin bd")))
    try:
        resp = cliente.get(ruta)
    except RuntimeError:
        return  # llego a la base de datos: no hubo bloqueo por autenticacion
    assert resp.status_code not in (401, 403, 503)
```

- [ ] **Step 2: Dependencias y verificar que falla**

Agregar `PyJWT==2.9.0` a `soap/requirements.txt`; en `soap/.env.example` quitar `LOGIN_URL` y `LOGIN_TIMEOUT` (y su comentario) y agregar:

```
# Mismo valor en TODOS los servicios
SECRET_KEY=change-me-same-value-in-every-service
# true = imprime el token Bearer en el log de cada escritura (evidencia para revision)
LOG_TOKENS=true
```

Run: `cd apps/services/soap && .venv/bin/pip install -r requirements.txt pytest && .venv/bin/python -m pytest tests -q`
Expected: FAIL (`ImportError: LOG_TOKENS` / `crear_token` no valida contra login).

- [ ] **Step 3: Modificar `soap/app.py`**

1. Imports: eliminar `import urllib.error` y `import urllib.request` (verificar con `grep -n "urllib" app.py` que no se usen en otro lado), y bajo `from flask_cors import CORS` agregar:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import jwt_auth  # noqa: E402
from common.web import parse_origins  # noqa: E402
```

2. Reemplazar el bloque `LOGIN_URL`/`LOGIN_TIMEOUT` y la línea `CORS(...)` por:

```python
LOG_TOKENS = os.getenv("LOG_TOKENS", "true").lower() == "true"
jwt_auth.obtener_secret()  # el servicio no arranca sin SECRET_KEY

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": parse_origins(os.getenv("CORS_ORIGINS", "*"))}})
```

(mantener las líneas `app.config["SWAGGER"]` y `Swagger(...)`; cambiar la descripción del esquema Bearer a `"JWT de acceso emitido por el servicio login: Bearer <session_token>"`).

3. Eliminar `sesion_valida` y reemplazar `requiere_sesion` completo por:

```python
def _registrar_acceso(token, datos, resultado):
    ruta = f"{request.method} {request.path}"
    if resultado:
        estado = f"{resultado[0]} {resultado[1]}"
    else:
        estado = f"JWT valido (user_id={datos['user_id']}, role_id={datos['role_id']})"
    mostrado = (f"Bearer {token}" if token else "(ausente)") if LOG_TOKENS else \
        ("(presente)" if token else "(ausente)")
    print(f"[BOOKS] {ruta}  |  Authorization: {mostrado} -> {estado}", flush=True)


# Protege las operaciones de escritura con un JWT de acceso valido (cualquier rol,
# igual que antes). Las lecturas (GET) no lo usan y siguen publicas.
requiere_sesion = jwt_auth.requiere_jwt(error_response=error_xml_response, on_event=_registrar_acceso)
```

`error_xml_response(message, status)` ya existe con esa firma.

- [ ] **Step 4: Verificar**

Run: `cd apps/services/soap && .venv/bin/python -m pytest tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/services/soap
git commit -m "feat(soap): validar JWT localmente, LOG_TOKENS y CORS_ORIGINS por entorno"
```

---

### Task 4: Cliente de escritorio con refresh token

**Files:**
- Modify: `apps/desktop_app/core/auth_api.py`
- Modify: `apps/desktop_app/core/session_store.py`
- Modify: `apps/desktop_app/main.py` (`iniciar`, `sesion_iniciada`)
- Modify: `apps/desktop_app/ui/main_window.py` (`_sesion_ok`, `extender_sesion`; nuevos `_guardar_token`, `_intentar_refresh`)
- Test: `apps/desktop_app/tests/test_core.py` (agregar tests al final)

**Interfaces:**
- Consumes: `POST /session/refresh` con `{"refresh_token"}` y respuestas de `/login/verify` (`session_token`, `refresh_token`) y `/session/extend` (`session_token` nuevo).
- Produces: `AuthApi.refresh_token` (atributo), `AuthApi.refrescar(refresh_token) -> dict`, `session_store.guardar(token, email, refresh_token=None)`.

- [ ] **Step 1: Tests que fallan** — agregar al final de `tests/test_core.py`

```python
def test_session_store_guarda_refresh_token():
    session_store.guardar("tok", "a@b.c", "ref")
    datos = session_store.cargar()
    assert datos["token"] == "tok" and datos["refresh_token"] == "ref"
    session_store.borrar()


def test_session_store_sin_refresh_sigue_funcionando():
    session_store.guardar("tok", "a@b.c")
    assert session_store.cargar().get("refresh_token") is None
    session_store.borrar()


def test_auth_guarda_refresh_al_verificar_y_refresca():
    from core.auth_api import AuthApi

    class Http:
        def __init__(self):
            self.llamadas = []

        def request(self, metodo, ruta, **kw):
            self.llamadas.append((metodo, ruta, kw.get("json_body")))
            if ruta == "/login/verify":
                return _Resp(200, {"session_token": "acc", "refresh_token": "ref"})
            return _Resp(200, {"session_token": "nuevo", "segundos_restantes": 1800})

        base_url = "http://x"

    http = Http()
    auth = AuthApi(http)
    assert auth.verificar_codigo("a@b.c", "123456") == "acc"
    assert auth.refresh_token == "ref"
    assert auth.refrescar("ref")["session_token"] == "nuevo"
    assert ("POST", "/session/refresh", {"refresh_token": "ref"}) in http.llamadas
```

Nota: usar la clase `_Resp` que ya existe en el archivo (`def _api(resp, ...)` la utiliza). Si su constructor no acepta `(status, json)`, revisar su definición y adaptar la llamada (`grep -n "class _Resp" -A12 tests/test_core.py`).

- [ ] **Step 2: Verificar que fallan**

Run: `cd apps/desktop_app && python -m pytest tests -q`
Expected: los 3 tests nuevos FAIL.

- [ ] **Step 3: `session_store.py`**

Reemplazar `guardar`:

```python
def guardar(token, email, refresh_token=None):
    carpeta = config_dir()
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(_archivo(), "w", encoding="utf-8") as f:
        json.dump({"token": token, "email": email, "refresh_token": refresh_token}, f)
```

Actualizar el docstring: "(token + refresh token + correo)".

- [ ] **Step 4: `auth_api.py`**

En `AuthApi.__init__` agregar `self.refresh_token = None`. Reemplazar `verificar_codigo` para guardar el refresh:

```python
    def verificar_codigo(self, email, codigo):
        datos = self._llamar("POST", "/login/verify", body={"email": email, "codigo": codigo},
                             mensajes={401: "El código es incorrecto o ya expiró (dura 5 minutos). "
                                            "Revísalo o solicita uno nuevo."})
        self.refresh_token = datos.get("refresh_token")
        return datos["session_token"]
```

Agregar tras `extender_sesion`:

```python
    def refrescar(self, refresh_token):
        return self._llamar("POST", "/session/refresh", body={"refresh_token": refresh_token},
                            mensajes={401: "Tu sesión expiró. Inicia sesión de nuevo."})
```

- [ ] **Step 5: `main.py`**

En `iniciar`, antes de `self.sesion_iniciada(...)`:

```python
            self.auth.refresh_token = guardada.get("refresh_token")
```

En `sesion_iniciada`, cambiar la llamada a `session_store.guardar(token, email, self.auth.refresh_token)`.

- [ ] **Step 6: `ui/main_window.py`**

Agregar `from core import session_store` a los imports. Reemplazar `_sesion_ok` (primeras líneas) y `extender_sesion` y agregar los dos métodos nuevos:

```python
    def _sesion_ok(self, datos):
        if not datos.get("autenticado"):
            self._intentar_refresh()
            return
        self.sesion.mostrar_datos(datos)
        self._set_restantes(datos.get("segundos_restantes"))
        poner_mensaje(self.sesion.mensaje, "Sesión válida en el servidor.")

    def _guardar_token(self, nuevo):
        self.token = nuevo
        self.c.token_sesion = nuevo
        try:
            session_store.guardar(nuevo, self.email, self.c.auth.refresh_token)
        except OSError:
            pass  # sin disco la app funciona igual

    def _intentar_refresh(self):
        motivo = "Tu sesión expiró o ya no es válida en el servidor. Inicia sesión de nuevo."
        refresh = self.c.auth.refresh_token
        if not refresh:
            self.cerrar_sesion(motivo=motivo, avisar_servidor=False)
            return

        def ok(datos):
            self._guardar_token(datos["session_token"])
            self._set_restantes(datos.get("segundos_restantes"))
            poner_mensaje(self.sesion.mensaje, "Sesión renovada automáticamente.")

        ejecutar(lambda: self.c.auth.refrescar(refresh), ok,
                 lambda exc: self.cerrar_sesion(motivo=motivo, avisar_servidor=False))

    def extender_sesion(self):
        token = self.token
        self.sesion.btn_extender.setEnabled(False)

        def ok(datos):
            self.sesion.btn_extender.setEnabled(True)
            if datos.get("session_token"):
                self._guardar_token(datos["session_token"])
            self._set_restantes(datos.get("segundos_restantes"))
            poner_mensaje(self.sesion.mensaje, "Sesión extendida 30 minutos a partir de ahora.")

        def fallo(exc):
            self.sesion.btn_extender.setEnabled(True)
            if isinstance(exc, SesionExpirada):
                self._intentar_refresh()
            else:
                poner_mensaje(self.sesion.mensaje, "No se pudo extender la sesión: " + texto_error(exc), error=True)

        ejecutar(lambda: self.c.auth.extender_sesion(token), ok, fallo)
```

(Mantener intactos los métodos vecinos; el texto "30 minutos" sigue siendo correcto.)

- [ ] **Step 7: Verificar**

Run: `cd apps/desktop_app && python -m pytest tests -q`
Expected: PASS (incluye los 3 nuevos y los existentes).

- [ ] **Step 8: Commit**

```bash
git add apps/desktop_app
git commit -m "feat(desktop): usar refresh token y renovar el JWT al extender o expirar la sesion"
```

---

### Task 5: Migración de Pedidos y Pagos

**Files:**
- Create: `data/migrations/2026-10-06_pedidos_pagos.sql`

**Interfaces:**
- Produces: tablas `pedidos(id_pedido, id_cuenta, estado, total, fecha_creacion)`, `lineas_pedido(id_linea, id_pedido, id_libro, cantidad, precio_unitario)`, `pagos(id_pago, id_pedido, monto, metodo, fecha_pago)` y permisos para `library_user` sobre ellas, `cuentas`, `personas`, `libros`, `autores`, `libro_autor`.

- [ ] **Step 1: Escribir la migración**

```sql
-- =====================================================================
-- Migracion: tablas de Pedidos y Pagos (apps/services/pedidos y pagos).
-- Additive-only. Requiere data/library_schema.sql y
-- data/migrations/2026-09-18_tablas_login.sql ya aplicados.
-- Ejecutar: psql -d library -f data/migrations/2026-10-06_pedidos_pagos.sql
-- =====================================================================

CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido       SERIAL PRIMARY KEY,
    id_cuenta       INT NOT NULL REFERENCES cuentas(id_cuenta),
    estado          VARCHAR(12) NOT NULL DEFAULT 'pendiente'
                        CHECK (estado IN ('pendiente','pagado','enviado','cancelado')),
    total           NUMERIC(10,2) NOT NULL CHECK (total >= 0),
    fecha_creacion  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pedidos_cuenta ON pedidos (id_cuenta);

CREATE TABLE IF NOT EXISTS lineas_pedido (
    id_linea         SERIAL PRIMARY KEY,
    id_pedido        INT NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    id_libro         INT NOT NULL REFERENCES libros(id_libro),
    cantidad         INT NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    UNIQUE (id_pedido, id_libro)
);

CREATE TABLE IF NOT EXISTS pagos (
    id_pago     SERIAL PRIMARY KEY,
    id_pedido   INT NOT NULL REFERENCES pedidos(id_pedido),
    monto       NUMERIC(10,2) NOT NULL CHECK (monto > 0),
    metodo      VARCHAR(20) NOT NULL CHECK (metodo IN ('tarjeta','transferencia','efectivo')),
    fecha_pago  TIMESTAMP NOT NULL DEFAULT now()
);
-- Un pedido se paga una sola vez (respaldo de la validacion de estado).
CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_pedido ON pagos (id_pedido);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'library_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON pedidos, lineas_pedido, pagos,
              cuentas, personas, autores, libro_autor TO library_user;
        GRANT SELECT, UPDATE ON libros TO library_user;
        GRANT SELECT ON libros, formatos TO library_user;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO library_user;
    END IF;
END $$;
```

- [ ] **Step 2: Aplicar y comprobar**

Run: `psql -d library -f data/migrations/2026-10-06_pedidos_pagos.sql && psql -d library -c "\dt pedidos lineas_pedido pagos"`
Expected: las tres tablas listadas. Si `psql` no está disponible localmente, anotar en el reporte que la migración quedó escrita y pendiente de aplicar (los tests unitarios no la necesitan).

- [ ] **Step 3: Commit**

```bash
git add data/migrations/2026-10-06_pedidos_pagos.sql
git commit -m "feat(db): migracion de tablas pedidos, lineas_pedido y pagos"
```

---

### Task 6: Servicio Users (puerto 5002)

**Files:**
- Create: `apps/services/users/app.py`, `repository.py`, `requirements.txt`, `.env.example`, `.gitignore`
- Create: `apps/services/users/tests/conftest.py`
- Test: `apps/services/users/tests/test_users.py`

**Interfaces:**
- Consumes: `common.jwt_auth` (`requiere_jwt`, `ROLE_ADMIN`, `ROLE_IDS`), `common.web`, `common.db`.
- Produces: `repository.listar() -> list[dict]`, `obtener(id) -> dict|None`, `obtener_hash(id) -> str|None`, `crear(correo, hash, rol, nombre, ap, am) -> int`, `actualizar(id, campos:dict) -> bool`, `cambiar_password(id, hash) -> bool`, `cambiar_rol(id, rol) -> bool`, `eliminar(id) -> bool`. Endpoints: `GET /api/roles` (público), `GET/POST /api/users`, `GET/PUT/PATCH/DELETE /api/users/<id>`, `PATCH /api/users/<id>/password`, `PATCH /api/users/<id>/rol`. Los usuarios se devuelven con `id_usuario, correo, rol, role_id, fecha_registro, nombre, apellido_paterno, apellido_materno` y **nunca** `contrasena_hash`.

- [ ] **Step 1: Estructura y entorno**

```bash
cd apps/services && mkdir -p users/tests && cp login/.gitignore users/.gitignore
cd users && python3 -m venv .venv
printf 'Flask==3.0.3\nflask-cors==4.0.1\npsycopg[binary]==3.2.10\npython-dotenv==1.0.1\nflasgger==0.9.7.1\nPyJWT==2.9.0\n' > requirements.txt
.venv/bin/pip install -r requirements.txt pytest
cat > .env.example <<'EOF'
DB_HOST=localhost
DB_PORT=5432
DB_NAME=library
DB_USER=library_user
DB_PASSWORD=change-me
# Mismo valor en TODOS los servicios
SECRET_KEY=change-me-same-value-in-every-service
# Orígenes de los clientes, separados por comas (en produccion NO usar *)
CORS_ORIGINS=*
PORT=5002
EOF
```

`users/tests/conftest.py` (mismo contenido que el de login, Task 2 Step 1).

- [ ] **Step 2: Tests que fallan** — `users/tests/test_users.py`

```python
import pytest

import app as users_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header

FILA = {"id_usuario": 2, "correo": "a@b.co", "rol": "cliente", "fecha_registro": None,
        "nombre": "Ana", "apellido_paterno": "L", "apellido_materno": "M"}
ADMIN = auth_header(1, ROLE_ADMIN)
USER2 = auth_header(2, ROLE_USER)
USER3 = auth_header(3, ROLE_USER)


@pytest.fixture
def c(monkeypatch):
    users_app.app.config["TESTING"] = True
    r = users_app.repository
    monkeypatch.setattr(r, "listar", lambda: [dict(FILA)])
    monkeypatch.setattr(r, "obtener", lambda i: dict(FILA, id_usuario=i) if i != 99 else None)
    return users_app.app.test_client()


def test_roles_es_publico(c):
    assert c.get("/api/roles").get_json() == [
        {"role_id": 1, "nombre": "admin"}, {"role_id": 2, "nombre": "cliente"}]


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/users"), ("put", "/api/users/2"), ("patch", "/api/users/2"),
    ("delete", "/api/users/2"), ("patch", "/api/users/2/password"), ("patch", "/api/users/2/rol"),
])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


def test_lecturas_de_usuarios_exigen_jwt(c):
    assert c.get("/api/users").status_code == 401
    assert c.get("/api/users/2").status_code == 401


def test_listar_solo_admin(c):
    assert c.get("/api/users", headers=USER2).status_code == 403
    resp = c.get("/api/users", headers=ADMIN)
    assert resp.status_code == 200
    assert all("contrasena_hash" not in u for u in resp.get_json())
    assert resp.get_json()[0]["role_id"] == 2


def test_ver_usuario_propio_o_admin_pero_no_ajeno(c):
    assert c.get("/api/users/2", headers=USER2).status_code == 200
    assert c.get("/api/users/2", headers=USER3).status_code == 403
    assert c.get("/api/users/2", headers=ADMIN).status_code == 200
    assert c.get("/api/users/99", headers=ADMIN).status_code == 404


def test_crear_solo_admin_y_guarda_hash(c, monkeypatch):
    capturado = {}

    def crear(correo, hash_, rol, nombre, ap, am):
        capturado.update(hash=hash_, rol=rol)
        return 10

    monkeypatch.setattr(users_app.repository, "crear", crear)
    cuerpo = {"correo": "n@b.co", "password": "secreta123", "nombre": "N",
              "apellido_paterno": "P", "apellido_materno": "M"}
    assert c.post("/api/users", json=cuerpo, headers=USER2).status_code == 403
    resp = c.post("/api/users", json=cuerpo, headers=ADMIN)
    assert resp.status_code == 201 and resp.get_json()["id_usuario"] == 10
    assert capturado["hash"] != "secreta123" and capturado["rol"] == "cliente"


@pytest.mark.parametrize("cambio", [
    {"correo": "malo"}, {"password": "corta"}, {"rol": "dios"}, {"nombre": ""}, {"nombre": 5},
])
def test_crear_valida_campos(c, cambio):
    cuerpo = {"correo": "n@b.co", "password": "secreta123", "nombre": "N",
              "apellido_paterno": "P", "apellido_materno": "M", **cambio}
    assert c.post("/api/users", json=cuerpo, headers=ADMIN).status_code == 400


def test_cuerpo_no_objeto_da_400(c):
    assert c.post("/api/users", data="[1]", content_type="application/json", headers=ADMIN).status_code == 400


def test_actualizar_propio_ajeno_y_vacio(c, monkeypatch):
    monkeypatch.setattr(users_app.repository, "actualizar", lambda i, campos: True)
    assert c.patch("/api/users/2", json={"nombre": "Nuevo"}, headers=USER2).status_code == 200
    assert c.patch("/api/users/2", json={"nombre": "Nuevo"}, headers=USER3).status_code == 403
    assert c.patch("/api/users/2", json={}, headers=USER2).status_code == 400
    assert c.put("/api/users/2", json={"nombre": "x"}, headers=USER2).status_code == 400  # PUT exige todos


def test_password_propio_requiere_actual(c, monkeypatch):
    from werkzeug.security import generate_password_hash
    guardado = {}
    monkeypatch.setattr(users_app.repository, "obtener_hash", lambda i: generate_password_hash("vieja12345"))
    monkeypatch.setattr(users_app.repository, "cambiar_password",
                        lambda i, h: guardado.setdefault("h", h) or True)
    mala = {"password_actual": "equivocada", "password_nueva": "nueva12345"}
    assert c.patch("/api/users/2/password", json=mala, headers=USER2).status_code == 403
    buena = {"password_actual": "vieja12345", "password_nueva": "nueva12345"}
    assert c.patch("/api/users/2/password", json=buena, headers=USER2).status_code == 200
    assert guardado["h"] != "nueva12345"
    assert c.patch("/api/users/2/password", json=buena, headers=USER3).status_code == 403


def test_admin_resetea_password_ajeno_sin_actual(c, monkeypatch):
    monkeypatch.setattr(users_app.repository, "cambiar_password", lambda i, h: True)
    assert c.patch("/api/users/2/password", json={"password_nueva": "nueva12345"},
                   headers=ADMIN).status_code == 200


def test_cambiar_rol_y_eliminar_solo_admin(c, monkeypatch):
    monkeypatch.setattr(users_app.repository, "cambiar_rol", lambda i, r: True)
    monkeypatch.setattr(users_app.repository, "eliminar", lambda i: True)
    assert c.patch("/api/users/2/rol", json={"rol": "admin"}, headers=USER2).status_code == 403
    assert c.patch("/api/users/2/rol", json={"rol": "admin"}, headers=ADMIN).status_code == 200
    assert c.patch("/api/users/2/rol", json={"rol": "dios"}, headers=ADMIN).status_code == 400
    assert c.delete("/api/users/2", headers=USER2).status_code == 403
    assert c.delete("/api/users/2", headers=ADMIN).status_code == 200
    assert c.delete("/api/users/99", headers=ADMIN).status_code == 404
```

- [ ] **Step 3: Verificar que fallan**

Run: `cd apps/services/users && .venv/bin/python -m pytest tests -q`
Expected: FAIL (`ModuleNotFoundError: app`).

- [ ] **Step 4: `users/repository.py`**

```python
"""Acceso a datos de usuarios: cuentas + personas (las mismas tablas de login).
Nunca selecciona contrasena_hash salvo en obtener_hash."""

from psycopg import errors
from psycopg.rows import dict_row

from common.db import get_connection
from common.web import Conflicto

_COLUMNAS = ("c.id_cuenta AS id_usuario, c.correo, c.rol, c.fecha_registro, "
             "p.nombre, p.apellido_paterno, p.apellido_materno")
_FROM = "FROM cuentas c JOIN personas p ON p.id_cuenta = c.id_cuenta"
_CAMPOS_PERSONA = ("nombre", "apellido_paterno", "apellido_materno")


def listar():
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNAS} {_FROM} ORDER BY c.id_cuenta")
        return cur.fetchall()


def obtener(id_usuario):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLUMNAS} {_FROM} WHERE c.id_cuenta = %s", (id_usuario,))
        return cur.fetchone()


def obtener_hash(id_usuario):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT contrasena_hash FROM cuentas WHERE id_cuenta = %s", (id_usuario,))
        fila = cur.fetchone()
        return fila[0] if fila else None


def crear(correo, contrasena_hash, rol, nombre, apellido_paterno, apellido_materno):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cuentas (correo, contrasena_hash, rol) VALUES (%s, %s, %s) "
                        "RETURNING id_cuenta", (correo, contrasena_hash, rol))
            id_usuario = cur.fetchone()[0]
            cur.execute("INSERT INTO personas (id_cuenta, nombre, apellido_paterno, apellido_materno) "
                        "VALUES (%s, %s, %s, %s)", (id_usuario, nombre, apellido_paterno, apellido_materno))
            return id_usuario
    except errors.UniqueViolation:
        raise Conflicto("Ese correo ya esta registrado.")


def actualizar(id_usuario, campos):
    """campos: subconjunto de correo/nombre/apellido_paterno/apellido_materno. True si el usuario existe."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            existe = False
            if "correo" in campos:
                cur.execute("UPDATE cuentas SET correo = %s WHERE id_cuenta = %s",
                            (campos["correo"], id_usuario))
                existe = cur.rowcount == 1
            personales = {k: v for k, v in campos.items() if k in _CAMPOS_PERSONA}
            if personales:
                sets = ", ".join(f"{k} = %s" for k in personales)  # claves en lista blanca
                cur.execute(f"UPDATE personas SET {sets} WHERE id_cuenta = %s",
                            (*personales.values(), id_usuario))
                existe = existe or cur.rowcount == 1
            return existe
    except errors.UniqueViolation:
        raise Conflicto("Ese correo ya esta registrado.")


def cambiar_password(id_usuario, contrasena_hash):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cuentas SET contrasena_hash = %s WHERE id_cuenta = %s",
                    (contrasena_hash, id_usuario))
        return cur.rowcount == 1


def cambiar_rol(id_usuario, rol):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cuentas SET rol = %s WHERE id_cuenta = %s", (rol, id_usuario))
        return cur.rowcount == 1


def eliminar(id_usuario):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM cuentas WHERE id_cuenta = %s", (id_usuario,))
            return cur.rowcount == 1
    except errors.ForeignKeyViolation:
        raise Conflicto("El usuario tiene pedidos y no se puede eliminar.")
```

- [ ] **Step 5: `users/app.py`**

```python
"""Microservicio Users (Flask sin blueprints): usuarios, roles, correos y contrasenas.
Opera sobre cuentas/personas, las mismas tablas que usa login."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, g, jsonify  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

import repository  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, ROLE_IDS, ROLE_NAMES, requiere_jwt  # noqa: E402
from common.web import (Invalido, NoEncontrado, Prohibido, configurar_app,  # noqa: E402
                        crear_swagger, cuerpo_json)

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Users API")

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CAMPOS_PERFIL = ("correo", "nombre", "apellido_paterno", "apellido_materno")


def _es_admin():
    return g.role_id == ROLE_ADMIN


def _solo_propio_o_admin(id_usuario):
    if not _es_admin() and g.user_id != id_usuario:
        raise Prohibido("Solo puedes acceder a tu propio usuario.")


def _usuario_o_404(id_usuario):
    usuario = repository.obtener(id_usuario)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado.")
    return usuario


def _publico(usuario):
    usuario = dict(usuario)
    usuario["role_id"] = ROLE_IDS[usuario["rol"]]
    return usuario


def _texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise Invalido(f"El campo {campo} debe ser texto no vacio.")
    return valor.strip()


def _validar_perfil(datos, parcial):
    limpio = {}
    for campo in CAMPOS_PERFIL:
        if campo not in datos:
            if not parcial:
                raise Invalido(f"El campo {campo} es obligatorio.")
            continue
        limpio[campo] = _texto(datos[campo], campo)
    if "correo" in limpio and not REGEX_EMAIL.match(limpio["correo"]):
        raise Invalido("El correo no tiene un formato valido.")
    if parcial and not limpio:
        raise Invalido("No se envio ningun campo para actualizar.")
    return limpio


def _validar_password(valor, campo="password"):
    if not isinstance(valor, str) or len(valor) < 8:
        raise Invalido(f"{campo} debe tener al menos 8 caracteres.")
    return valor


def _validar_rol(valor):
    if valor not in ROLE_IDS:
        raise Invalido("rol debe ser 'admin' o 'cliente'.")
    return valor


@app.route("/api/roles", methods=["GET"])
def listar_roles():
    """Lista los roles disponibles (publico).
    ---
    responses:
      200:
        description: "[{role_id, nombre}]"
    """
    return jsonify([{"role_id": rid, "nombre": nombre} for rid, nombre in ROLE_NAMES.items()])


@app.route("/api/users", methods=["GET"])
@requiere_jwt(roles=[ROLE_ADMIN])
def listar_usuarios():
    """Lista todos los usuarios (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Lista de usuarios}
      401: {description: Token ausente o invalido}
      403: {description: Rol insuficiente}
    """
    return jsonify([_publico(u) for u in repository.listar()])


@app.route("/api/users/<int:id_usuario>", methods=["GET"])
@requiere_jwt()
def ver_usuario(id_usuario):
    """Ve un usuario (el propio o cualquiera si eres admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Usuario}
      403: {description: Usuario ajeno}
      404: {description: No existe}
    """
    _solo_propio_o_admin(id_usuario)
    return jsonify(_publico(_usuario_o_404(id_usuario)))


@app.route("/api/users", methods=["POST"])
@requiere_jwt(roles=[ROLE_ADMIN])
def crear_usuario():
    """Crea un usuario (solo admin). La contrasena se guarda con hash.
    ---
    security:
      - Bearer: []
    responses:
      201: {description: Creado}
      400: {description: Datos invalidos}
      409: {description: Correo duplicado}
    """
    datos = cuerpo_json()
    perfil = _validar_perfil(datos, parcial=False)
    password = _validar_password(datos.get("password"))
    rol = _validar_rol(datos.get("rol", "cliente"))
    id_usuario = repository.crear(perfil["correo"], generate_password_hash(password), rol,
                                  perfil["nombre"], perfil["apellido_paterno"], perfil["apellido_materno"])
    return jsonify({"id_usuario": id_usuario}), 201


@app.route("/api/users/<int:id_usuario>", methods=["PUT", "PATCH"])
@requiere_jwt()
def actualizar_usuario(id_usuario):
    """Actualiza el perfil. PUT exige todos los campos; PATCH acepta un subconjunto.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Actualizado}
      400: {description: Datos invalidos}
      403: {description: Usuario ajeno}
      404: {description: No existe}
    """
    from flask import request
    _solo_propio_o_admin(id_usuario)
    campos = _validar_perfil(cuerpo_json(), parcial=request.method == "PATCH")
    if not repository.actualizar(id_usuario, campos):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify(_publico(_usuario_o_404(id_usuario)))


@app.route("/api/users/<int:id_usuario>/password", methods=["PATCH"])
@requiere_jwt()
def cambiar_password(id_usuario):
    """Cambia la contrasena. El propio usuario debe enviar password_actual; un admin puede resetear la de otros.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Contrasena cambiada}
      400: {description: Datos invalidos}
      403: {description: Usuario ajeno o contrasena actual incorrecta}
      404: {description: No existe}
    """
    _solo_propio_o_admin(id_usuario)
    datos = cuerpo_json()
    nueva = _validar_password(datos.get("password_nueva"), "password_nueva")
    if g.user_id == id_usuario:
        actual = repository.obtener_hash(id_usuario)
        if actual is None:
            raise NoEncontrado("Usuario no encontrado.")
        if not isinstance(datos.get("password_actual"), str) or not check_password_hash(actual, datos["password_actual"]):
            raise Prohibido("La contrasena actual es incorrecta.")
    if not repository.cambiar_password(id_usuario, generate_password_hash(nueva)):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify({"mensaje": "Contrasena actualizada."})


@app.route("/api/users/<int:id_usuario>/rol", methods=["PATCH"])
@requiere_jwt(roles=[ROLE_ADMIN])
def cambiar_rol(id_usuario):
    """Cambia el rol (solo admin). El nuevo rol aplica al siguiente JWT que se emita.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Rol cambiado}
      400: {description: Rol invalido}
      404: {description: No existe}
    """
    rol = _validar_rol(cuerpo_json().get("rol"))
    if not repository.cambiar_rol(id_usuario, rol):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify({"id_usuario": id_usuario, "rol": rol, "role_id": ROLE_IDS[rol]})


@app.route("/api/users/<int:id_usuario>", methods=["DELETE"])
@requiere_jwt(roles=[ROLE_ADMIN])
def eliminar_usuario(id_usuario):
    """Elimina un usuario (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Eliminado}
      404: {description: No existe}
      409: {description: Tiene pedidos}
    """
    if not repository.eliminar(id_usuario):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify({"mensaje": "Usuario eliminado."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5002")))
```

Nota para el implementador: mover `from flask import request` al import superior (`from flask import Flask, g, jsonify, request`) y borrar la importación local dentro de `actualizar_usuario`.

- [ ] **Step 6: Verificar**

Run: `cd apps/services/users && .venv/bin/python -m pytest tests -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/services/users
git commit -m "feat(users): microservicio de usuarios, roles y contrasenas protegido con JWT"
```

---

### Task 7: Servicio Authors (puerto 5003)

**Files:**
- Create: `apps/services/authors/app.py`, `repository.py`, `requirements.txt`, `.env.example`, `.gitignore`, `tests/conftest.py`
- Test: `apps/services/authors/tests/test_authors.py`

**Interfaces:**
- Consumes: `common.*`.
- Produces: `repository.listar() -> list[dict]` (`id_autor, nombre_autor`), `obtener(id) -> dict|None` (con `libros: [{id_libro, isbn, titulo}]`), `crear(nombre) -> int`, `renombrar(id, nombre) -> bool`, `eliminar(id) -> bool`, `vincular(id_autor, id_libro) -> bool` (True si se creó), `desvincular(id_autor, id_libro) -> bool`. Endpoints: `GET /api/authors`, `GET /api/authors/<id>` (públicos); `POST /api/authors`, `PUT|PATCH /api/authors/<id>`, `DELETE /api/authors/<id>`, `POST /api/authors/<id>/books`, `DELETE /api/authors/<id>/books/<id_libro>` (solo admin).

- [ ] **Step 1: Estructura y entorno** — igual que Task 6 Step 1 cambiando la carpeta a `authors` y `PORT=5003`; `tests/conftest.py` idéntico.

- [ ] **Step 2: Tests que fallan** — `authors/tests/test_authors.py`

```python
import pytest

import app as authors_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header
from common.web import Conflicto

ADMIN = auth_header(1, ROLE_ADMIN)
USER = auth_header(2, ROLE_USER)


@pytest.fixture
def c(monkeypatch):
    authors_app.app.config["TESTING"] = True
    r = authors_app.repository
    monkeypatch.setattr(r, "listar", lambda: [{"id_autor": 1, "nombre_autor": "Borges"}])
    monkeypatch.setattr(r, "obtener", lambda i: {"id_autor": i, "nombre_autor": "Borges", "libros": []}
                        if i != 99 else None)
    return authors_app.app.test_client()


def test_lecturas_son_publicas(c):
    assert c.get("/api/authors").status_code == 200
    resp = c.get("/api/authors/1")
    assert resp.status_code == 200 and resp.get_json()["libros"] == []
    assert c.get("/api/authors/99").status_code == 404


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/authors"), ("put", "/api/authors/1"), ("patch", "/api/authors/1"),
    ("delete", "/api/authors/1"), ("post", "/api/authors/1/books"), ("delete", "/api/authors/1/books/2"),
])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/authors"), ("put", "/api/authors/1"), ("delete", "/api/authors/1"),
    ("post", "/api/authors/1/books"), ("delete", "/api/authors/1/books/2"),
])
def test_escrituras_con_rol_user_403(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={"nombre_autor": "X", "id_libro": 2}, headers=USER).status_code == 403


def test_crear_autor(c, monkeypatch):
    monkeypatch.setattr(authors_app.repository, "crear", lambda n: 7)
    resp = c.post("/api/authors", json={"nombre_autor": "  Cortázar "}, headers=ADMIN)
    assert resp.status_code == 201 and resp.get_json() == {"id_autor": 7, "nombre_autor": "Cortázar"}
    assert c.post("/api/authors", json={"nombre_autor": ""}, headers=ADMIN).status_code == 400
    assert c.post("/api/authors", json={}, headers=ADMIN).status_code == 400


def test_crear_autor_duplicado_409(c, monkeypatch):
    def duplicado(n):
        raise Conflicto("El autor ya existe.")
    monkeypatch.setattr(authors_app.repository, "crear", duplicado)
    assert c.post("/api/authors", json={"nombre_autor": "Borges"}, headers=ADMIN).status_code == 409


def test_renombrar_y_eliminar(c, monkeypatch):
    monkeypatch.setattr(authors_app.repository, "renombrar", lambda i, n: i != 99)
    monkeypatch.setattr(authors_app.repository, "eliminar", lambda i: i != 99)
    assert c.put("/api/authors/1", json={"nombre_autor": "Nuevo"}, headers=ADMIN).status_code == 200
    assert c.patch("/api/authors/99", json={"nombre_autor": "Nuevo"}, headers=ADMIN).status_code == 404
    assert c.delete("/api/authors/1", headers=ADMIN).status_code == 200
    assert c.delete("/api/authors/99", headers=ADMIN).status_code == 404


def test_vincular_y_desvincular_libro(c, monkeypatch):
    monkeypatch.setattr(authors_app.repository, "vincular", lambda a, l: True)
    monkeypatch.setattr(authors_app.repository, "desvincular", lambda a, l: l != 99)
    assert c.post("/api/authors/1/books", json={"id_libro": 2}, headers=ADMIN).status_code == 201
    assert c.post("/api/authors/1/books", json={"id_libro": "2"}, headers=ADMIN).status_code == 400
    assert c.post("/api/authors/1/books", json={"id_libro": True}, headers=ADMIN).status_code == 400
    assert c.delete("/api/authors/1/books/2", headers=ADMIN).status_code == 200
    assert c.delete("/api/authors/1/books/99", headers=ADMIN).status_code == 404
```

- [ ] **Step 3: Verificar que fallan**

Run: `cd apps/services/authors && .venv/bin/python -m pytest tests -q` → FAIL (`ModuleNotFoundError: app`).

- [ ] **Step 4: `authors/repository.py`**

```python
"""Acceso a datos de autores y su relacion con libros (autores, libro_autor)."""

from psycopg import errors
from psycopg.rows import dict_row

from common.db import get_connection
from common.web import Conflicto, NoEncontrado


def listar():
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_autor, nombre_autor FROM autores ORDER BY nombre_autor")
        return cur.fetchall()


def obtener(id_autor):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_autor, nombre_autor FROM autores WHERE id_autor = %s", (id_autor,))
        autor = cur.fetchone()
        if not autor:
            return None
        cur.execute("SELECT l.id_libro, l.isbn, l.titulo FROM libro_autor la "
                    "JOIN libros l ON l.id_libro = la.id_libro "
                    "WHERE la.id_autor = %s ORDER BY l.titulo", (id_autor,))
        autor["libros"] = cur.fetchall()
        return autor


def crear(nombre):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO autores (nombre_autor) VALUES (%s) RETURNING id_autor", (nombre,))
            return cur.fetchone()[0]
    except errors.UniqueViolation:
        raise Conflicto("El autor ya existe.")


def renombrar(id_autor, nombre):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE autores SET nombre_autor = %s WHERE id_autor = %s", (nombre, id_autor))
            return cur.rowcount == 1
    except errors.UniqueViolation:
        raise Conflicto("Ya existe un autor con ese nombre.")


def eliminar(id_autor):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM autores WHERE id_autor = %s", (id_autor,))
            return cur.rowcount == 1
    except errors.ForeignKeyViolation:
        raise Conflicto("El autor tiene libros asociados; desvinculalos primero.")


def vincular(id_autor, id_libro):
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO libro_autor (id_libro, id_autor) VALUES (%s, %s) "
                        "ON CONFLICT DO NOTHING", (id_libro, id_autor))
            return cur.rowcount == 1
    except errors.ForeignKeyViolation:
        raise NoEncontrado("El autor o el libro no existe.")


def desvincular(id_autor, id_libro):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM libro_autor WHERE id_autor = %s AND id_libro = %s", (id_autor, id_libro))
        return cur.rowcount == 1
```

- [ ] **Step 5: `authors/app.py`**

```python
"""Microservicio Authors (Flask sin blueprints): autores y su relacion con libros.
Lecturas publicas; toda escritura exige JWT con rol admin."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, jsonify  # noqa: E402

import repository  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, requiere_jwt  # noqa: E402
from common.web import Invalido, NoEncontrado, configurar_app, crear_swagger, cuerpo_json  # noqa: E402

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Authors API")

solo_admin = requiere_jwt(roles=[ROLE_ADMIN])


def _nombre(datos):
    nombre = datos.get("nombre_autor")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 150:
        raise Invalido("nombre_autor debe ser texto no vacio de maximo 150 caracteres.")
    return nombre.strip()


def _entero_positivo(valor):
    return type(valor) is int and valor > 0


@app.route("/api/authors", methods=["GET"])
def listar_autores():
    """Lista los autores (publico).
    ---
    responses:
      200: {description: "[{id_autor, nombre_autor}]"}
    """
    return jsonify(repository.listar())


@app.route("/api/authors/<int:id_autor>", methods=["GET"])
def ver_autor(id_autor):
    """Un autor con sus libros (publico).
    ---
    responses:
      200: {description: Autor con libros}
      404: {description: No existe}
    """
    autor = repository.obtener(id_autor)
    if not autor:
        raise NoEncontrado("Autor no encontrado.")
    return jsonify(autor)


@app.route("/api/authors", methods=["POST"])
@solo_admin
def crear_autor():
    """Crea un autor (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      201: {description: Creado}
      400: {description: Datos invalidos}
      409: {description: Ya existe}
    """
    nombre = _nombre(cuerpo_json())
    return jsonify({"id_autor": repository.crear(nombre), "nombre_autor": nombre}), 201


@app.route("/api/authors/<int:id_autor>", methods=["PUT", "PATCH"])
@solo_admin
def renombrar_autor(id_autor):
    """Renombra un autor (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Actualizado}
      404: {description: No existe}
      409: {description: Nombre duplicado}
    """
    nombre = _nombre(cuerpo_json())
    if not repository.renombrar(id_autor, nombre):
        raise NoEncontrado("Autor no encontrado.")
    return jsonify({"id_autor": id_autor, "nombre_autor": nombre})


@app.route("/api/authors/<int:id_autor>", methods=["DELETE"])
@solo_admin
def eliminar_autor(id_autor):
    """Elimina un autor sin libros (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Eliminado}
      404: {description: No existe}
      409: {description: Tiene libros asociados}
    """
    if not repository.eliminar(id_autor):
        raise NoEncontrado("Autor no encontrado.")
    return jsonify({"mensaje": "Autor eliminado."})


@app.route("/api/authors/<int:id_autor>/books", methods=["POST"])
@solo_admin
def vincular_libro(id_autor):
    """Asocia un libro al autor (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      201: {description: Vinculado}
      400: {description: id_libro invalido}
      404: {description: Autor o libro inexistente}
    """
    id_libro = cuerpo_json().get("id_libro")
    if not _entero_positivo(id_libro):
        raise Invalido("id_libro debe ser un entero positivo.")
    repository.vincular(id_autor, id_libro)
    return jsonify({"id_autor": id_autor, "id_libro": id_libro}), 201


@app.route("/api/authors/<int:id_autor>/books/<int:id_libro>", methods=["DELETE"])
@solo_admin
def desvincular_libro(id_autor, id_libro):
    """Quita la relacion autor-libro (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Desvinculado}
      404: {description: La relacion no existe}
    """
    if not repository.desvincular(id_autor, id_libro):
        raise NoEncontrado("La relacion autor-libro no existe.")
    return jsonify({"mensaje": "Relacion eliminada."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5003")))
```

- [ ] **Step 6: Verificar** — `cd apps/services/authors && .venv/bin/python -m pytest tests -q` → PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/services/authors
git commit -m "feat(authors): microservicio de autores y relacion con libros protegido con JWT"
```

---

### Task 8: Servicio Pedidos (puerto 5004)

**Files:**
- Create: `apps/services/pedidos/app.py`, `repository.py`, `transiciones.py`, `requirements.txt`, `.env.example`, `.gitignore`, `tests/conftest.py`
- Test: `apps/services/pedidos/tests/test_transiciones.py`, `test_pedidos.py`, `test_stock_manual.py`

**Interfaces:**
- Consumes: `common.*`; tablas de Task 5.
- Produces: `transiciones.validar(actual, nuevo, es_admin, es_dueno)` (lanza `Prohibido`/`Conflicto`); `repository.crear(id_cuenta, items) -> int` con `items=[(id_libro, cantidad), ...]` ya sin duplicados; `listar(id_cuenta=None)`, `obtener(id_pedido)` (con `lineas`), `cambiar_estado(id_pedido, nuevo, id_actor, es_admin) -> None`, `eliminar(id_pedido) -> None`. Endpoints: `POST /api/pedidos`, `GET /api/pedidos`, `GET /api/pedidos/<id>`, `PATCH|PUT /api/pedidos/<id>/estado`, `DELETE /api/pedidos/<id>` (admin).

- [ ] **Step 1: Estructura y entorno** — como Task 6 Step 1 con carpeta `pedidos`, `PORT=5004`; `tests/conftest.py` idéntico.

- [ ] **Step 2: Tests de transiciones (fallan)** — `tests/test_transiciones.py`

```python
import pytest

import transiciones
from common.web import Conflicto, Prohibido


def test_dueno_cancela_pendiente():
    transiciones.validar("pendiente", "cancelado", es_admin=False, es_dueno=True)


def test_admin_cancela_pendiente_ajeno():
    transiciones.validar("pendiente", "cancelado", es_admin=True, es_dueno=False)


def test_solo_admin_marca_enviado():
    transiciones.validar("pagado", "enviado", es_admin=True, es_dueno=False)
    with pytest.raises(Prohibido):
        transiciones.validar("pagado", "enviado", es_admin=False, es_dueno=True)


def test_pedido_ajeno_prohibido():
    with pytest.raises(Prohibido):
        transiciones.validar("pendiente", "cancelado", es_admin=False, es_dueno=False)


@pytest.mark.parametrize("actual,nuevo", [
    ("pendiente", "pagado"), ("pendiente", "enviado"), ("pagado", "cancelado"),
    ("enviado", "cancelado"), ("cancelado", "pendiente"), ("pagado", "pendiente"),
    ("pendiente", "pendiente"), ("pendiente", "inventado"),
])
def test_transiciones_no_permitidas(actual, nuevo):
    with pytest.raises(Conflicto):
        transiciones.validar(actual, nuevo, es_admin=True, es_dueno=True)
```

- [ ] **Step 3: Implementar `pedidos/transiciones.py`**

```python
"""Reglas puras de cambio de estado de un pedido. El paso pendiente -> pagado
no existe aqui: lo hace el servicio de pagos al registrar el pago."""

from common.web import Conflicto, Prohibido

PERMITIDAS = {("pendiente", "cancelado"), ("pagado", "enviado")}


def validar(actual, nuevo, es_admin, es_dueno):
    if not (es_admin or es_dueno):
        raise Prohibido("El pedido no te pertenece.")
    if (actual, nuevo) not in PERMITIDAS:
        raise Conflicto(f"Transicion no permitida: {actual} -> {nuevo}. "
                        "(El pago de un pedido lo registra el servicio de pagos.)")
    if nuevo == "enviado" and not es_admin:
        raise Prohibido("Solo un administrador puede marcar un pedido como enviado.")
```

Run: `cd apps/services/pedidos && .venv/bin/python -m pytest tests/test_transiciones.py -q` → PASS.

- [ ] **Step 4: Tests HTTP (fallan)** — `tests/test_pedidos.py`

```python
import pytest

import app as pedidos_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header

ADMIN = auth_header(1, ROLE_ADMIN)
USER2 = auth_header(2, ROLE_USER)
USER3 = auth_header(3, ROLE_USER)
PEDIDO = {"id_pedido": 10, "id_cuenta": 2, "estado": "pendiente", "total": 100.0, "fecha_creacion": None,
          "lineas": []}


@pytest.fixture
def c(monkeypatch):
    pedidos_app.app.config["TESTING"] = True
    r = pedidos_app.repository
    monkeypatch.setattr(r, "obtener", lambda i: dict(PEDIDO) if i == 10 else None)
    return pedidos_app.app.test_client()


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/pedidos"), ("patch", "/api/pedidos/10/estado"),
    ("put", "/api/pedidos/10/estado"), ("delete", "/api/pedidos/10"),
])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


def test_lecturas_exigen_jwt(c):
    assert c.get("/api/pedidos").status_code == 401
    assert c.get("/api/pedidos/10").status_code == 401


def test_crear_pedido_fusiona_lineas_duplicadas(c, monkeypatch):
    visto = {}

    def crear(id_cuenta, items):
        visto.update(id_cuenta=id_cuenta, items=items)
        return 11

    monkeypatch.setattr(pedidos_app.repository, "crear", crear)
    monkeypatch.setattr(pedidos_app.repository, "obtener", lambda i: dict(PEDIDO, id_pedido=i))
    cuerpo = {"lineas": [{"id_libro": 5, "cantidad": 1}, {"id_libro": 5, "cantidad": 2},
                         {"id_libro": 3, "cantidad": 4}]}
    resp = c.post("/api/pedidos", json=cuerpo, headers=USER2)
    assert resp.status_code == 201 and resp.get_json()["id_pedido"] == 11
    assert visto == {"id_cuenta": 2, "items": [(3, 4), (5, 3)]}


@pytest.mark.parametrize("lineas", [
    [], None, "x", [{}], [{"id_libro": 1}], [{"id_libro": 1, "cantidad": 0}],
    [{"id_libro": 1, "cantidad": -2}], [{"id_libro": 1, "cantidad": 1.5}],
    [{"id_libro": 1, "cantidad": True}], [{"id_libro": "1", "cantidad": 1}], [7],
])
def test_crear_pedido_rechaza_lineas_invalidas(c, monkeypatch, lineas):
    llamado = []
    monkeypatch.setattr(pedidos_app.repository, "crear", lambda *a: llamado.append(a))
    assert c.post("/api/pedidos", json={"lineas": lineas}, headers=USER2).status_code == 400
    assert not llamado  # no se toco el stock


def test_listar_user_ve_solo_lo_suyo_y_admin_todo(c, monkeypatch):
    pedidos = []
    monkeypatch.setattr(pedidos_app.repository, "listar", lambda id_cuenta=None: pedidos.append(id_cuenta) or [])
    c.get("/api/pedidos", headers=USER2)
    c.get("/api/pedidos", headers=ADMIN)
    assert pedidos == [2, None]


def test_ver_pedido_ajeno_403_y_propio_200(c):
    assert c.get("/api/pedidos/10", headers=USER2).status_code == 200
    assert c.get("/api/pedidos/10", headers=USER3).status_code == 403
    assert c.get("/api/pedidos/10", headers=ADMIN).status_code == 200
    assert c.get("/api/pedidos/99", headers=ADMIN).status_code == 404


def test_cambiar_estado_invoca_repositorio_con_actor(c, monkeypatch):
    visto = []
    monkeypatch.setattr(pedidos_app.repository, "cambiar_estado", lambda *a: visto.append(a))
    resp = c.patch("/api/pedidos/10/estado", json={"estado": "cancelado"}, headers=USER2)
    assert resp.status_code == 200 and visto == [(10, "cancelado", 2, False)]
    assert c.put("/api/pedidos/10/estado", json={"estado": "enviado"}, headers=ADMIN).status_code == 200
    assert c.patch("/api/pedidos/10/estado", json={"estado": 5}, headers=USER2).status_code == 400


def test_eliminar_solo_admin(c, monkeypatch):
    monkeypatch.setattr(pedidos_app.repository, "eliminar", lambda i: None)
    assert c.delete("/api/pedidos/10", headers=USER2).status_code == 403
    assert c.delete("/api/pedidos/10", headers=ADMIN).status_code == 200
```

- [ ] **Step 5: `pedidos/repository.py`**

```python
"""Acceso a datos de pedidos. Toda operacion que toca stock corre en UNA
transaccion con SELECT ... FOR UPDATE sobre las filas de libros / pedidos."""

from psycopg.rows import dict_row

import transiciones
from common.db import get_connection
from common.web import Conflicto, NoEncontrado


def crear(id_cuenta, items):
    """items: [(id_libro, cantidad)] sin ids repetidos. Descuenta stock o hace rollback."""
    ids = [id_libro for id_libro, _ in items]
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Orden por id: dos pedidos concurrentes bloquean en el mismo orden (sin deadlock).
        cur.execute("SELECT id_libro, precio, stock FROM libros WHERE id_libro = ANY(%s) "
                    "ORDER BY id_libro FOR UPDATE", (ids,))
        libros = {fila["id_libro"]: fila for fila in cur.fetchall()}
        total = 0
        for id_libro, cantidad in items:
            libro = libros.get(id_libro)
            if libro is None:
                raise NoEncontrado(f"El libro {id_libro} no existe.")
            if libro["stock"] < cantidad:
                raise Conflicto(f"Stock insuficiente para el libro {id_libro} "
                                f"(disponible {libro['stock']}, pedido {cantidad}).")
            total += libro["precio"] * cantidad
        cur.execute("INSERT INTO pedidos (id_cuenta, total) VALUES (%s, %s) RETURNING id_pedido",
                    (id_cuenta, total))
        id_pedido = cur.fetchone()["id_pedido"]
        for id_libro, cantidad in items:
            cur.execute("INSERT INTO lineas_pedido (id_pedido, id_libro, cantidad, precio_unitario) "
                        "VALUES (%s, %s, %s, %s)", (id_pedido, id_libro, cantidad, libros[id_libro]["precio"]))
            cur.execute("UPDATE libros SET stock = stock - %s WHERE id_libro = %s", (cantidad, id_libro))
        return id_pedido


def listar(id_cuenta=None):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        consulta = "SELECT id_pedido, id_cuenta, estado, total, fecha_creacion FROM pedidos"
        if id_cuenta is None:
            cur.execute(consulta + " ORDER BY id_pedido DESC")
        else:
            cur.execute(consulta + " WHERE id_cuenta = %s ORDER BY id_pedido DESC", (id_cuenta,))
        return cur.fetchall()


def obtener(id_pedido):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_pedido, id_cuenta, estado, total, fecha_creacion FROM pedidos "
                    "WHERE id_pedido = %s", (id_pedido,))
        pedido = cur.fetchone()
        if not pedido:
            return None
        cur.execute("SELECT lp.id_libro, l.isbn, l.titulo, lp.cantidad, lp.precio_unitario "
                    "FROM lineas_pedido lp JOIN libros l ON l.id_libro = lp.id_libro "
                    "WHERE lp.id_pedido = %s ORDER BY lp.id_linea", (id_pedido,))
        pedido["lineas"] = cur.fetchall()
        return pedido


def cambiar_estado(id_pedido, nuevo, id_actor, es_admin):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id_cuenta, estado FROM pedidos WHERE id_pedido = %s FOR UPDATE", (id_pedido,))
        pedido = cur.fetchone()
        if not pedido:
            raise NoEncontrado("Pedido no encontrado.")
        transiciones.validar(pedido["estado"], nuevo, es_admin, pedido["id_cuenta"] == id_actor)
        if nuevo == "cancelado":  # devuelve el stock
            cur.execute("UPDATE libros l SET stock = l.stock + lp.cantidad FROM lineas_pedido lp "
                        "WHERE lp.id_pedido = %s AND l.id_libro = lp.id_libro", (id_pedido,))
        cur.execute("UPDATE pedidos SET estado = %s WHERE id_pedido = %s", (nuevo, id_pedido))


def eliminar(id_pedido):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pedidos WHERE id_pedido = %s AND estado = 'cancelado'", (id_pedido,))
        if cur.rowcount == 1:
            return
        cur.execute("SELECT estado FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        fila = cur.fetchone()
        if not fila:
            raise NoEncontrado("Pedido no encontrado.")
        raise Conflicto(f"Solo se pueden eliminar pedidos cancelados (este esta {fila[0]}).")
```

- [ ] **Step 6: `pedidos/app.py`**

```python
"""Microservicio Pedidos (Flask sin blueprints): pedidos, lineas, stock y estados."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, g, jsonify  # noqa: E402

import repository  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, requiere_jwt  # noqa: E402
from common.web import (Invalido, NoEncontrado, Prohibido, configurar_app,  # noqa: E402
                        crear_swagger, cuerpo_json)

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Pedidos API")


def _es_admin():
    return g.role_id == ROLE_ADMIN


def _entero_positivo(valor):
    return type(valor) is int and valor > 0


def _parsear_lineas(datos):
    """Valida y fusiona lineas repetidas del mismo libro. Regresa [(id_libro, cantidad)] ordenado."""
    lineas = datos.get("lineas")
    if not isinstance(lineas, list) or not lineas:
        raise Invalido("lineas debe ser una lista no vacia.")
    acumulado = {}
    for linea in lineas:
        if not isinstance(linea, dict):
            raise Invalido("Cada linea debe ser un objeto {id_libro, cantidad}.")
        id_libro, cantidad = linea.get("id_libro"), linea.get("cantidad")
        if not _entero_positivo(id_libro) or not _entero_positivo(cantidad):
            raise Invalido("id_libro y cantidad deben ser enteros positivos.")
        acumulado[id_libro] = acumulado.get(id_libro, 0) + cantidad
    return sorted(acumulado.items())


def _pedido_visible(id_pedido):
    pedido = repository.obtener(id_pedido)
    if not pedido:
        raise NoEncontrado("Pedido no encontrado.")
    if not _es_admin() and pedido["id_cuenta"] != g.user_id:
        raise Prohibido("El pedido no te pertenece.")
    return pedido


@app.route("/api/pedidos", methods=["POST"])
@requiere_jwt()
def crear_pedido():
    """Crea un pedido y descuenta el stock en una transaccion.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [lineas]
          properties:
            lineas:
              type: array
              items: {type: object, properties: {id_libro: {type: integer}, cantidad: {type: integer}}}
    responses:
      201: {description: Pedido creado}
      400: {description: Lineas invalidas}
      404: {description: Libro inexistente}
      409: {description: Stock insuficiente}
    """
    items = _parsear_lineas(cuerpo_json())
    id_pedido = repository.crear(g.user_id, items)
    return jsonify(repository.obtener(id_pedido)), 201


@app.route("/api/pedidos", methods=["GET"])
@requiere_jwt()
def listar_pedidos():
    """Lista pedidos: un usuario ve los suyos, un admin ve todos.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Lista de pedidos}
    """
    return jsonify(repository.listar(None if _es_admin() else g.user_id))


@app.route("/api/pedidos/<int:id_pedido>", methods=["GET"])
@requiere_jwt()
def ver_pedido(id_pedido):
    """Un pedido con sus lineas (propio o admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Pedido}
      403: {description: Pedido ajeno}
      404: {description: No existe}
    """
    return jsonify(_pedido_visible(id_pedido))


@app.route("/api/pedidos/<int:id_pedido>/estado", methods=["PATCH", "PUT"])
@requiere_jwt()
def cambiar_estado(id_pedido):
    """Cambia el estado: pendiente->cancelado (dueno o admin), pagado->enviado (admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Estado cambiado}
      400: {description: Estado invalido}
      403: {description: Sin permiso}
      409: {description: Transicion no permitida}
    """
    nuevo = cuerpo_json().get("estado")
    if not isinstance(nuevo, str):
        raise Invalido("estado debe ser texto.")
    repository.cambiar_estado(id_pedido, nuevo, g.user_id, _es_admin())
    return jsonify({"id_pedido": id_pedido, "estado": nuevo})


@app.route("/api/pedidos/<int:id_pedido>", methods=["DELETE"])
@requiere_jwt(roles=[ROLE_ADMIN])
def eliminar_pedido(id_pedido):
    """Elimina un pedido cancelado (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Eliminado}
      404: {description: No existe}
      409: {description: El pedido no esta cancelado}
    """
    repository.eliminar(id_pedido)
    return jsonify({"mensaje": "Pedido eliminado."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5004")))
```

- [ ] **Step 7: Prueba manual de stock/concurrencia** — `tests/test_stock_manual.py`

```python
"""Prueba contra la BD real (requiere la migracion de pedidos aplicada y .env con DB_*):
    cd apps/services/pedidos && RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_stock_manual.py -q -s
Crea un libro y una cuenta temporales y los borra al terminar."""

import os
import threading
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="requiere BD real (RUN_DB_TESTS=1)")

import repository  # noqa: E402
from common.db import get_connection  # noqa: E402
from common.web import Conflicto  # noqa: E402


@pytest.fixture
def escenario():
    sufijo = uuid.uuid4().hex[:8]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id_formato FROM formatos LIMIT 1")
        id_formato = cur.fetchone()[0]
        cur.execute("INSERT INTO libros (isbn, titulo, precio, stock, id_formato) "
                    "VALUES (%s, %s, 10, 1, %s) RETURNING id_libro", (sufijo.ljust(13, "0")[:13], "T-" + sufijo, id_formato))
        id_libro = cur.fetchone()[0]
        cur.execute("INSERT INTO cuentas (correo, contrasena_hash, rol) VALUES (%s, 'x', 'cliente') "
                    "RETURNING id_cuenta", (f"t{sufijo}@test.co",))
        id_cuenta = cur.fetchone()[0]
    yield id_cuenta, id_libro
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pedidos WHERE id_cuenta = %s", (id_cuenta,))
        cur.execute("DELETE FROM cuentas WHERE id_cuenta = %s", (id_cuenta,))
        cur.execute("DELETE FROM libros WHERE id_libro = %s", (id_libro,))


def _stock(id_libro):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT stock FROM libros WHERE id_libro = %s", (id_libro,))
        return cur.fetchone()[0]


def test_stock_insuficiente_hace_rollback(escenario):
    id_cuenta, id_libro = escenario
    with pytest.raises(Conflicto):
        repository.crear(id_cuenta, [(id_libro, 2)])
    assert _stock(id_libro) == 1
    assert repository.listar(id_cuenta) == []


def test_cancelar_devuelve_stock(escenario):
    id_cuenta, id_libro = escenario
    id_pedido = repository.crear(id_cuenta, [(id_libro, 1)])
    assert _stock(id_libro) == 0
    repository.cambiar_estado(id_pedido, "cancelado", id_cuenta, False)
    assert _stock(id_libro) == 1


def test_dos_pedidos_concurrentes_por_el_ultimo_ejemplar(escenario):
    id_cuenta, id_libro = escenario
    resultados = []

    def intentar():
        try:
            resultados.append(repository.crear(id_cuenta, [(id_libro, 1)]))
        except Conflicto as exc:
            resultados.append(exc)

    hilos = [threading.Thread(target=intentar) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sum(isinstance(r, int) for r in resultados) == 1
    assert sum(isinstance(r, Conflicto) for r in resultados) == 1
    assert _stock(id_libro) == 0
```

- [ ] **Step 8: Verificar**

Run: `cd apps/services/pedidos && .venv/bin/python -m pytest tests -q`
Expected: PASS (el test manual queda SKIPPED). Si la BD local tiene la migración: `RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_stock_manual.py -q -s` → PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/services/pedidos
git commit -m "feat(pedidos): microservicio de pedidos con stock transaccional protegido con JWT"
```

---

### Task 9: Servicio Pagos (puerto 5005)

**Files:**
- Create: `apps/services/pagos/app.py`, `repository.py`, `requirements.txt`, `.env.example`, `.gitignore`, `tests/conftest.py`
- Test: `apps/services/pagos/tests/test_pagos.py`, `test_pagos_manual.py`

**Interfaces:**
- Consumes: `common.*`; tablas `pedidos`, `pagos`.
- Produces: `repository.registrar(id_pedido, id_actor, es_admin, metodo, monto) -> dict` (`id_pago, id_pedido, monto, metodo, fecha_pago`), `listar(id_cuenta=None)`, `obtener(id_pago) -> dict|None` (incluye `id_cuenta` del pedido), `reembolsar(id_pago) -> None`. Endpoints: `POST /api/pagos`, `GET /api/pagos`, `GET /api/pagos/<id>`, `DELETE /api/pagos/<id>` (admin, reembolso). Los pagos no se editan: `PUT/PATCH` → 405.

- [ ] **Step 1: Estructura y entorno** — como Task 6 Step 1 con carpeta `pagos`, `PORT=5005`; `tests/conftest.py` idéntico.

- [ ] **Step 2: Tests que fallan** — `tests/test_pagos.py`

```python
import pytest

import app as pagos_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header

ADMIN = auth_header(1, ROLE_ADMIN)
USER2 = auth_header(2, ROLE_USER)
USER3 = auth_header(3, ROLE_USER)
PAGO = {"id_pago": 4, "id_pedido": 10, "id_cuenta": 2, "monto": 100.0, "metodo": "tarjeta", "fecha_pago": None}


@pytest.fixture
def c(monkeypatch):
    pagos_app.app.config["TESTING"] = True
    monkeypatch.setattr(pagos_app.repository, "obtener", lambda i: dict(PAGO) if i == 4 else None)
    return pagos_app.app.test_client()


@pytest.mark.parametrize("metodo,ruta", [("post", "/api/pagos"), ("delete", "/api/pagos/4")])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


def test_pagos_no_se_editan(c):
    assert c.put("/api/pagos/4", json={}, headers=ADMIN).status_code == 405
    assert c.patch("/api/pagos/4", json={}, headers=ADMIN).status_code == 405


def test_lecturas_exigen_jwt(c):
    assert c.get("/api/pagos").status_code == 401
    assert c.get("/api/pagos/4").status_code == 401


def test_registrar_pago_pasa_actor_y_metodo(c, monkeypatch):
    visto = []
    monkeypatch.setattr(pagos_app.repository, "registrar",
                        lambda *a: visto.append(a) or dict(PAGO))
    resp = c.post("/api/pagos", json={"id_pedido": 10, "metodo": "tarjeta"}, headers=USER2)
    assert resp.status_code == 201
    assert visto == [(10, 2, False, "tarjeta", None)]


def test_registrar_pago_con_monto_decimal(c, monkeypatch):
    from decimal import Decimal
    visto = []
    monkeypatch.setattr(pagos_app.repository, "registrar", lambda *a: visto.append(a) or dict(PAGO))
    c.post("/api/pagos", json={"id_pedido": 10, "metodo": "efectivo", "monto": 99.9}, headers=USER2)
    assert visto[0][4] == Decimal("99.9")


@pytest.mark.parametrize("cuerpo", [
    {}, {"metodo": "tarjeta"}, {"id_pedido": 10}, {"id_pedido": "10", "metodo": "tarjeta"},
    {"id_pedido": True, "metodo": "tarjeta"}, {"id_pedido": 10, "metodo": "bitcoin"},
    {"id_pedido": 10, "metodo": "tarjeta", "monto": "mucho"},
    {"id_pedido": 10, "metodo": "tarjeta", "monto": -5}, {"id_pedido": 10, "metodo": "tarjeta", "monto": True},
])
def test_registrar_pago_valida(c, monkeypatch, cuerpo):
    llamado = []
    monkeypatch.setattr(pagos_app.repository, "registrar", lambda *a: llamado.append(a))
    assert c.post("/api/pagos", json=cuerpo, headers=USER2).status_code == 400
    assert not llamado


def test_listar_user_solo_suyos_admin_todos(c, monkeypatch):
    vistos = []
    monkeypatch.setattr(pagos_app.repository, "listar", lambda id_cuenta=None: vistos.append(id_cuenta) or [])
    c.get("/api/pagos", headers=USER2)
    c.get("/api/pagos", headers=ADMIN)
    assert vistos == [2, None]


def test_ver_pago_ajeno_403(c):
    assert c.get("/api/pagos/4", headers=USER2).status_code == 200
    assert c.get("/api/pagos/4", headers=USER3).status_code == 403
    assert c.get("/api/pagos/4", headers=ADMIN).status_code == 200
    assert c.get("/api/pagos/99", headers=ADMIN).status_code == 404


def test_reembolso_solo_admin(c, monkeypatch):
    monkeypatch.setattr(pagos_app.repository, "reembolsar", lambda i: None)
    assert c.delete("/api/pagos/4", headers=USER2).status_code == 403
    assert c.delete("/api/pagos/4", headers=ADMIN).status_code == 200
```

- [ ] **Step 3: Verificar que fallan** — `cd apps/services/pagos && .venv/bin/python -m pytest tests -q` → FAIL (`ModuleNotFoundError: app`).

- [ ] **Step 4: `pagos/repository.py`**

```python
"""Acceso a datos de pagos. Registrar y reembolsar actualizan pedidos.estado en
la MISMA transaccion (misma base `library`), con el pedido bloqueado FOR UPDATE."""

from decimal import Decimal

from psycopg import errors
from psycopg.rows import dict_row

from common.db import get_connection
from common.web import Conflicto, NoEncontrado, Prohibido


def registrar(id_pedido, id_actor, es_admin, metodo, monto):
    try:
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id_cuenta, estado, total FROM pedidos WHERE id_pedido = %s FOR UPDATE",
                        (id_pedido,))
            pedido = cur.fetchone()
            if not pedido:
                raise NoEncontrado("Pedido no encontrado.")
            if pedido["id_cuenta"] != id_actor and not es_admin:
                raise Prohibido("El pedido no te pertenece.")
            if pedido["estado"] != "pendiente":
                raise Conflicto(f"El pedido esta {pedido['estado']}; solo se pagan pedidos pendientes.")
            if monto is not None and Decimal(monto) != pedido["total"]:
                raise Conflicto(f"El monto no coincide con el total del pedido ({pedido['total']}).")
            cur.execute("INSERT INTO pagos (id_pedido, monto, metodo) VALUES (%s, %s, %s) "
                        "RETURNING id_pago, id_pedido, monto, metodo, fecha_pago",
                        (id_pedido, pedido["total"], metodo))
            pago = cur.fetchone()
            cur.execute("UPDATE pedidos SET estado = 'pagado' WHERE id_pedido = %s", (id_pedido,))
            return pago
    except errors.UniqueViolation:
        raise Conflicto("El pedido ya tiene un pago registrado.")


_SELECT = ("SELECT pg.id_pago, pg.id_pedido, p.id_cuenta, pg.monto, pg.metodo, pg.fecha_pago "
           "FROM pagos pg JOIN pedidos p ON p.id_pedido = pg.id_pedido")


def listar(id_cuenta=None):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if id_cuenta is None:
            cur.execute(_SELECT + " ORDER BY pg.id_pago DESC")
        else:
            cur.execute(_SELECT + " WHERE p.id_cuenta = %s ORDER BY pg.id_pago DESC", (id_cuenta,))
        return cur.fetchall()


def obtener(id_pago):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SELECT + " WHERE pg.id_pago = %s", (id_pago,))
        return cur.fetchone()


def reembolsar(id_pago):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT pg.id_pedido, p.estado FROM pagos pg JOIN pedidos p ON p.id_pedido = pg.id_pedido "
                    "WHERE pg.id_pago = %s FOR UPDATE OF p", (id_pago,))
        fila = cur.fetchone()
        if not fila:
            raise NoEncontrado("Pago no encontrado.")
        if fila["estado"] != "pagado":
            raise Conflicto(f"No se puede reembolsar: el pedido esta {fila['estado']}.")
        cur.execute("DELETE FROM pagos WHERE id_pago = %s", (id_pago,))
        cur.execute("UPDATE pedidos SET estado = 'pendiente' WHERE id_pedido = %s", (fila["id_pedido"],))
```

- [ ] **Step 5: `pagos/app.py`**

```python
"""Microservicio Pagos (Flask sin blueprints): registra pagos y pasa el pedido a 'pagado'."""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, g, jsonify  # noqa: E402

import repository  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, requiere_jwt  # noqa: E402
from common.web import (Invalido, NoEncontrado, Prohibido, configurar_app,  # noqa: E402
                        crear_swagger, cuerpo_json)

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Pagos API")

METODOS = ("tarjeta", "transferencia", "efectivo")


def _es_admin():
    return g.role_id == ROLE_ADMIN


def _monto_opcional(valor):
    if valor is None:
        return None
    if type(valor) not in (int, float) or valor <= 0:
        raise Invalido("monto debe ser un numero positivo.")
    return Decimal(str(valor))


@app.route("/api/pagos", methods=["POST"])
@requiere_jwt()
def registrar_pago():
    """Registra el pago de un pedido pendiente y lo marca como pagado (misma transaccion).
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [id_pedido, metodo]
          properties:
            id_pedido: {type: integer}
            metodo: {type: string, enum: [tarjeta, transferencia, efectivo]}
            monto: {type: number, description: "Opcional; si se envia debe igualar el total"}
    responses:
      201: {description: Pago registrado}
      400: {description: Datos invalidos}
      403: {description: Pedido ajeno}
      404: {description: Pedido inexistente}
      409: {description: Pedido no pendiente, ya pagado o monto distinto}
    """
    datos = cuerpo_json()
    id_pedido, metodo = datos.get("id_pedido"), datos.get("metodo")
    if type(id_pedido) is not int or id_pedido <= 0:
        raise Invalido("id_pedido debe ser un entero positivo.")
    if metodo not in METODOS:
        raise Invalido("metodo debe ser tarjeta, transferencia o efectivo.")
    monto = _monto_opcional(datos.get("monto"))
    pago = repository.registrar(id_pedido, g.user_id, _es_admin(), metodo, monto)
    return jsonify(pago), 201


@app.route("/api/pagos", methods=["GET"])
@requiere_jwt()
def listar_pagos():
    """Lista pagos: un usuario ve los de sus pedidos, un admin ve todos.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Lista de pagos}
    """
    return jsonify(repository.listar(None if _es_admin() else g.user_id))


@app.route("/api/pagos/<int:id_pago>", methods=["GET"])
@requiere_jwt()
def ver_pago(id_pago):
    """Un pago (de un pedido propio o admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Pago}
      403: {description: Pago ajeno}
      404: {description: No existe}
    """
    pago = repository.obtener(id_pago)
    if not pago:
        raise NoEncontrado("Pago no encontrado.")
    if not _es_admin() and pago["id_cuenta"] != g.user_id:
        raise Prohibido("El pago no te pertenece.")
    return jsonify(pago)


@app.route("/api/pagos/<int:id_pago>", methods=["DELETE"])
@requiere_jwt(roles=[ROLE_ADMIN])
def reembolsar_pago(id_pago):
    """Reembolsa un pago (solo admin): borra el pago y el pedido vuelve a pendiente.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Reembolsado}
      404: {description: No existe}
      409: {description: El pedido ya fue enviado o cancelado}
    """
    repository.reembolsar(id_pago)
    return jsonify({"mensaje": "Pago reembolsado; el pedido volvio a pendiente."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5005")))
```

- [ ] **Step 6: Prueba manual contra BD** — `tests/test_pagos_manual.py`

```python
"""Contra la BD real (migracion aplicada):
    cd apps/services/pagos && RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_pagos_manual.py -q -s"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="requiere BD real (RUN_DB_TESTS=1)")

import repository  # noqa: E402
from common.db import get_connection  # noqa: E402
from common.web import Conflicto, Prohibido  # noqa: E402


@pytest.fixture
def pedido():
    sufijo = uuid.uuid4().hex[:8]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO cuentas (correo, contrasena_hash, rol) VALUES (%s, 'x', 'cliente') "
                    "RETURNING id_cuenta", (f"p{sufijo}@test.co",))
        id_cuenta = cur.fetchone()[0]
        cur.execute("INSERT INTO pedidos (id_cuenta, total) VALUES (%s, 50) RETURNING id_pedido", (id_cuenta,))
        id_pedido = cur.fetchone()[0]
    yield id_cuenta, id_pedido
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pagos WHERE id_pedido = %s", (id_pedido,))
        cur.execute("DELETE FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        cur.execute("DELETE FROM cuentas WHERE id_cuenta = %s", (id_cuenta,))


def _estado(id_pedido):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT estado FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        return cur.fetchone()[0]


def test_pago_marca_pedido_pagado_y_no_se_paga_dos_veces(pedido):
    id_cuenta, id_pedido = pedido
    pago = repository.registrar(id_pedido, id_cuenta, False, "tarjeta", None)
    assert pago["monto"] == 50 and _estado(id_pedido) == "pagado"
    with pytest.raises(Conflicto):
        repository.registrar(id_pedido, id_cuenta, False, "tarjeta", None)
    assert _estado(id_pedido) == "pagado"


def test_pedido_ajeno_prohibido_y_monto_distinto_conflicto(pedido):
    id_cuenta, id_pedido = pedido
    with pytest.raises(Prohibido):
        repository.registrar(id_pedido, id_cuenta + 100000, False, "tarjeta", None)
    from decimal import Decimal
    with pytest.raises(Conflicto):
        repository.registrar(id_pedido, id_cuenta, False, "tarjeta", Decimal("49.99"))
    assert _estado(id_pedido) == "pendiente"


def test_reembolso_devuelve_pedido_a_pendiente(pedido):
    id_cuenta, id_pedido = pedido
    pago = repository.registrar(id_pedido, id_cuenta, False, "efectivo", None)
    repository.reembolsar(pago["id_pago"])
    assert _estado(id_pedido) == "pendiente"
```

- [ ] **Step 7: Verificar**

Run: `cd apps/services/pagos && .venv/bin/python -m pytest tests -q` → PASS (manual SKIPPED). Con BD: `RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_pagos_manual.py -q -s` → PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/services/pagos
git commit -m "feat(pagos): microservicio de pagos que actualiza el estado del pedido, protegido con JWT"
```

---

### Task 10: Documentación y verificación de punta a punta

**Files:**
- Create: `apps/services/README_JWT.md`
- Modify: `docs/AI_CHANGELOG.md` (agregar entrada al final)

- [ ] **Step 1: Escribir `apps/services/README_JWT.md`** con: tabla de servicios y puertos; variables de entorno por servicio (`SECRET_KEY` idéntica en todos, `CORS_ORIGINS`, `DB_*`, `REFRESH_TTL_DAYS`, `LOG_TOKENS`); cómo correr cada servicio (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python app.py`); el orden de migraciones (`library_schema.sql` → `2026-09-18_tablas_login.sql` → `2026-10-06_pedidos_pagos.sql`); nota de que HTTPS se termina en un proxy inverso (nginx/balanceador) delante de los servicios y que en producción `CORS_ORIGINS` debe listar solo los clientes; y la guía de humo con curl:

```bash
# 1) login (2FA): POST /register, POST /login, POST /login/verify?format=json  -> session_token + refresh_token
TOKEN=<session_token>
curl -s -X POST localhost:5004/api/pedidos -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"lineas":[{"id_libro":1,"cantidad":1}]}'                  # 201 (sin token: 401)
curl -s -X POST localhost:5005/api/pagos -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"id_pedido":<id>,"metodo":"tarjeta"}'                     # 201, pedido -> pagado
curl -s -X POST localhost:5003/api/authors -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"nombre_autor":"X"}'  # 403 con rol cliente
curl -s -X POST localhost:5000/session/refresh?format=json -H "Content-Type: application/json" \
     -d '{"refresh_token":"<refresh_token>"}'                       # nuevo session_token
```

- [ ] **Step 2: Entrada en `docs/AI_CHANGELOG.md`** (leer el formato existente con `tail -30 docs/AI_CHANGELOG.md` y respetarlo): resumen de JWT, servicios nuevos y migración, con fecha 2026-10-06.

- [ ] **Step 3: Verificación completa**

```bash
cd apps/services && login/.venv/bin/python -m pytest common/tests -q
for s in login soap users authors pedidos pagos; do (cd $s && .venv/bin/python -m pytest tests -q) || echo "FALLO $s"; done
(cd ../desktop_app && python -m pytest tests -q)
```

Expected: todo PASS (los `*_manual.py` quedan SKIPPED o fuera de pytest).

- [ ] **Step 4: Humo real (si hay BD y Postfix local)** — levantar login, soap y los cuatro servicios con la misma `SECRET_KEY`, ejecutar los `curl` del README y confirmar: sin token → 401, rol `cliente` en ruta admin → 403, pedido y pago correctos, refresh emite un token nuevo. Si no hay entorno disponible, reportarlo explícitamente como no verificado.

- [ ] **Step 5: Commit**

```bash
git add apps/services/README_JWT.md docs/AI_CHANGELOG.md
git commit -m "docs: guia de microservicios JWT y entrada en el changelog"
```

---

## Self-Review

**Spec coverage:** módulo `common` y claims (Task 1) · login JWT 30 min + refresh + `/session/refresh` + logout sin estado (2) · soap local + `LOG_TOKENS` + `CORS_ORIGINS` (3) · cliente de escritorio con refresh (4) · tablas pedidos/pagos y permisos (5) · Users con roles admin/cliente y `role_id` (6) · Authors con relación `libro_autor` (7) · Pedidos con stock transaccional y estados (8) · Pagos que actualizan `pedidos.estado` en la misma transacción (9) · docs, HTTPS vía proxy y CORS de producción (10). La confirmación de `cuentas/personas` quedó resuelta: existen en `2026-09-18_tablas_login.sql`.

**Decisiones del plan que se apartan del spec (para revisar):**
- `GET /session` y `/session/extend` consultan la BD solo para devolver `email`/`nombre` y comprobar que la cuenta sigue existiendo; la validez del token sí es local.
- El índice de admin único existe en `usuarios` pero **no** en `cuentas` (que es lo que usa login), así que no hay restricción de un solo admin que conservar.
- `soap` mantiene "cualquier JWT válido puede escribir libros" (comportamiento actual); no se agrega verificación de rol ahí.
- `POST /api/users` es solo admin; el alta pública sigue siendo `POST /register` de login.

**Placeholders:** ninguno; las únicas indicaciones abiertas son adaptar el constructor de `_Resp` en el test de escritorio (Task 4 Step 1) y mover el import de `request` en Users (Task 6 Step 5), ambas con instrucción exacta.

**Consistencia de tipos:** `crear_token(user_id, role_id, tipo, ttl_segundos)`, `decodificar(token, tipo)`, `requiere_jwt(roles, error_response, on_event)`, `repository.crear/ listar/ obtener/ cambiar_estado/ registrar` usados con las mismas firmas en tests y apps.
