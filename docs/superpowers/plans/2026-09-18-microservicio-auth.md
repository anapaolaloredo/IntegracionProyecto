# Microservicio de Autenticación (`apps/services/login`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un microservicio Flask + Psycopg 3 + PostgreSQL, independiente del monolito, que registra usuarios, autentica con 2FA por correo (SMTP propio/local vía Postfix), y expone sesiones de 30 minutos por token — con respuestas XML (default) o JSON — usando tablas propias (`cuentas`/`personas`/`codigos_verificacion`/`sesiones`), sin tocar el monolito ni su base de datos existente.

**Architecture:** Capas separadas por responsabilidad dentro de `apps/services/login/`: `db/` (conexión + SQL parametrizado), `auth/` (hashing/tokens, sin Flask ni SQL), `mail/` (envío SMTP local), `render/` (serialización XML/JSON), `errors.py` (excepciones de dominio → status HTTP), `service.py` (orquestación de negocio, sin Flask), `app.py` (rutas HTTP + Swagger). La BD tiene 4 tablas propias del microservicio (`cuentas`/`personas`/`codigos_verificacion`/`sesiones`), sin FK hacia ninguna tabla del monolito, siguiendo el mismo patrón de rol de mínimo privilegio que ya usa `apps/services/library_soap_service`.

**Tech Stack:** Python 3, Flask 3, Psycopg 3 (`psycopg[binary]`), python-dotenv, flasgger (Swagger), werkzeug.security (hashing), smtplib (stdlib), PostgreSQL 15, Postfix (OS-level, solo entrega local).

**Spec:** `docs/superpowers/specs/2026-09-18-microservicio-auth-design.md`

## Global Constraints

- Puerto del microservicio: **5000**.
- Todos los endpoints soportan `?format=xml` (default si se omite) y `?format=json`.
- La contraseña y el código 2FA **nunca** se guardan en texto plano — solo hash (`werkzeug.security`).
- Las sesiones expiran a los **30 minutos** exactos desde su creación (vida fija, no deslizante).
- El correo debe ser único y validarse por formato antes de registrar.
- El SMTP del 2FA debe ser **propio y local** a la instancia (Postfix), nunca un proveedor externo (Gmail/SendGrid/etc.); el correo se entrega en un buzón local de la propia instancia.
- El microservicio **nunca** hace llamadas HTTP hacia el monolito, ni el monolito hacia él, y no comparte ninguna tabla con él — solo la misma base de datos física `library`, con tablas propias.
- Los endpoints se documentan con Swagger (flasgger), con ejemplos XML y JSON.

---

## Fase 1 — Base de datos


### Task 1: Tablas propias del microservicio de login

> **Nota (2026-09-18, ya implementada):** la primera versión de esta tarea
> normalizaba la tabla `usuarios` del monolito. Se descartó por costo/tiempo
> — al implementarla apareció `vista_administradores` (dependiente de
> `nombre_usuario`) y además requería actualizar el monolito (antigua
> Fase 2 / Task 3, **eliminada** — el monolito ya no se toca en absoluto).
> Ver la ruling en `.superpowers/sdd/2026-09-18-microservicio-auth/progress.md`.
> Esta sección ya refleja el diseño vigente y lo que quedó commiteado en
> `3d950b3`.

**Files:**
- Create: `data/migrations/2026-09-18_tablas_login.sql`

**Interfaces:**
- Produces: tablas `cuentas` (`id_cuenta, correo, contrasena_hash, rol, fecha_registro`), `personas` (`id_cuenta, nombre, apellido_paterno, apellido_materno`), `codigos_verificacion` (`id_codigo, id_cuenta, codigo_hash, expira_en, usado, creado_en`), `sesiones` (`token, id_cuenta, creada_en, expira_en`); rol `auth_service_user` con sus GRANTs. Estos nombres de tabla/columna son los que usará `db/repository.py` en la Fase 3 — **nota:** ninguna FK apunta a `usuarios` del monolito; estas 4 tablas son completamente independientes.

- [x] **Step 1: Escribir el script de migración** (ya implementado — contenido final, additive-only, sin tocar `usuarios`/vistas del monolito):

```sql
-- =====================================================================
-- Migracion: Tablas propias del microservicio de autenticacion
-- (apps/services/login). Additive-only: no ALTER/DROP on existing tables.
-- Crea un conjunto completamente independiente de tablas de auth
-- que no comparten ni modifican el schema de la aplicacion monolito.
--
-- Ejecutar UNA sola vez contra una base de datos que ya tiene cargado
-- data/library_schema.sql (+ opcionalmente data/library_views.sql y
-- data/library_data.sql). Requiere un rol con privilegio para CREATE ROLE
-- (el rol de aplicacion library_user NO lo tiene): en la instancia GCP,
-- usar el rol postgres (`sudo -u postgres psql -d library -f ...`, mismo
-- patron que ya usa sql/soap_module.sql); en local, el superusuario de tu
-- propio Postgres (p.ej. `psql -d library -f ...` sin -U, si tu usuario de
-- SO ya es superusuario).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Tabla cuentas: Autenticacion independiente del microservicio
--    (username, password, rol - NO toca usuarios del monolito)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cuentas (
    id_cuenta        SERIAL PRIMARY KEY,
    correo           VARCHAR(150) NOT NULL UNIQUE,
    contrasena_hash  VARCHAR(255) NOT NULL,
    rol              VARCHAR(10)  NOT NULL DEFAULT 'cliente'
                         CHECK (rol IN ('admin','cliente')),
    fecha_registro   TIMESTAMP    NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2. Tabla personas: Datos personales (1:1 con cuentas)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personas (
    id_cuenta         INT PRIMARY KEY REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
    nombre            VARCHAR(100) NOT NULL,
    apellido_paterno  VARCHAR(100) NOT NULL,
    apellido_materno  VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------
-- 3. Tablas de funcionalidad: Verificacion y sesiones
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS codigos_verificacion (
    id_codigo    SERIAL PRIMARY KEY,
    id_cuenta    INT NOT NULL REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
    codigo_hash  VARCHAR(255) NOT NULL,
    expira_en    TIMESTAMP NOT NULL,
    usado        BOOLEAN NOT NULL DEFAULT false,
    creado_en    TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_codigos_verificacion_cuenta ON codigos_verificacion (id_cuenta);

CREATE TABLE IF NOT EXISTS sesiones (
    token        VARCHAR(64) PRIMARY KEY,
    id_cuenta    INT NOT NULL REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
    creada_en    TIMESTAMP NOT NULL DEFAULT now(),
    expira_en    TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sesiones_cuenta ON sesiones (id_cuenta);

-- ---------------------------------------------------------------------
-- 4. Rol de minimo privilegio para el microservicio de login
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auth_service_user') THEN
        CREATE ROLE auth_service_user WITH LOGIN PASSWORD 'change-me-auth';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE library TO auth_service_user;
GRANT USAGE ON SCHEMA public TO auth_service_user;

GRANT SELECT, INSERT, UPDATE ON cuentas, personas TO auth_service_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON codigos_verificacion, sesiones TO auth_service_user;

GRANT USAGE, SELECT ON SEQUENCE cuentas_id_cuenta_seq TO auth_service_user;
GRANT USAGE, SELECT ON SEQUENCE codigos_verificacion_id_codigo_seq TO auth_service_user;
```

- [x] **Step 2: Aplicar y verificar** (ya hecho — `cuentas`, `personas`, `codigos_verificacion`, `sesiones` existen; `auth_service_user` creado con sus GRANTs; `usuarios`/`vista_administradores` del monolito confirmados intactos, 30 usuarios semilla sin cambios).

- [x] **Step 3: Commit** (ya hecho — `3d950b3 feat(db): tablas propias del microservicio de login (cuentas/personas/codigos_verificacion/sesiones)`).

---

## Fase 3 — Microservicio `apps/services/login`

### Task 4: Scaffold del proyecto

**Files:**
- Create: `apps/services/login/requirements.txt`
- Create: `apps/services/login/.env.example`
- Create: `apps/services/login/.gitignore`
- Create: `apps/services/login/config/__init__.py`
- Create: `apps/services/login/config/settings.py`
- Create: `apps/services/login/db/__init__.py`
- Create: `apps/services/login/db/connection.py`
- Create: `apps/services/login/auth/__init__.py`
- Create: `apps/services/login/render/__init__.py`
- Create: `apps/services/login/mail/__init__.py`
- Create: `apps/services/login/tests/__init__.py`

**Interfaces:**
- Produces: `config.settings.{DB_CONFIG, PORT, SMTP_HOST, SMTP_PORT, LOCAL_MAILBOX_USER, MAIL_FROM, SESSION_TTL_MINUTES, CODE_TTL_MINUTES}`; `db.connection.get_connection() -> psycopg.Connection`. Usados por Task 5 en adelante.

- [ ] **Step 1: Crear `requirements.txt`**

```
Flask==3.0.3
psycopg[binary]==3.2.3
python-dotenv==1.0.1
flasgger==0.9.7.1
```

- [ ] **Step 2: Crear `.env.example`**

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=library
DB_USER=auth_service_user
DB_PASSWORD=change-me-auth

PORT=5000

# Postfix local (nunca un proveedor externo): el codigo 2FA se entrega en
# el buzon de este usuario del sistema operativo, en la propia instancia.
SMTP_HOST=localhost
SMTP_PORT=25
LOCAL_MAILBOX_USER=change-me-os-user
MAIL_FROM=auth-service@localhost

SESSION_TTL_MINUTES=30
CODE_TTL_MINUTES=5
```

- [ ] **Step 3: Crear `.gitignore` local del servicio**

```
.env
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 4: Crear `config/__init__.py`, `db/__init__.py`, `auth/__init__.py`, `render/__init__.py`, `mail/__init__.py`, `tests/__init__.py`** (todos vacíos)

- [ ] **Step 5: Crear `config/settings.py`**

```python
"""Configuracion del microservicio de login, leida exclusivamente de
variables de entorno (nunca credenciales embebidas en el codigo)."""

import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "library"),
    "user": os.getenv("DB_USER", "auth_service_user"),
    "password": os.getenv("DB_PASSWORD", ""),
}

PORT = int(os.getenv("PORT", "5000"))

# SMTP local (Postfix en la misma instancia). Nunca un proveedor externo.
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
LOCAL_MAILBOX_USER = os.getenv("LOCAL_MAILBOX_USER", "auth-test")
MAIL_FROM = os.getenv("MAIL_FROM", "auth-service@localhost")

SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "30"))
CODE_TTL_MINUTES = int(os.getenv("CODE_TTL_MINUTES", "5"))
```

- [ ] **Step 6: Crear `db/connection.py`**

```python
"""Capa de conexion a PostgreSQL. Unico lugar del modulo que importa
psycopg directamente; el resto del codigo pasa por repository.py."""

import psycopg
from config.settings import DB_CONFIG


def get_connection():
    return psycopg.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
```

- [ ] **Step 7: Verificar que el módulo de configuración carga**

Run: `cd apps/services/login && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: instalación sin errores.

Run: `cd apps/services/login && .venv/bin/python -c "from config.settings import DB_CONFIG, PORT; print(DB_CONFIG, PORT)"`
Expected: imprime el diccionario con `auth_service_user` y `5000` sin lanzar excepción.

- [ ] **Step 8: Commit**

```bash
git add apps/services/login/requirements.txt apps/services/login/.env.example apps/services/login/.gitignore apps/services/login/config apps/services/login/db/__init__.py apps/services/login/db/connection.py apps/services/login/auth/__init__.py apps/services/login/render/__init__.py apps/services/login/mail/__init__.py apps/services/login/tests/__init__.py
git commit -m "feat(login): scaffold del microservicio de autenticacion"
```

---

### Task 5: Capa de acceso a datos (`db/repository.py`)

**Files:**
- Create: `apps/services/login/db/repository.py`
- Create: `apps/services/login/tests/test_repository_manual.py`

**Interfaces:**
- Consumes: `db.connection.get_connection()` (Task 4); tablas `cuentas`/`personas`/`codigos_verificacion`/`sesiones` de Task 1.
- Produces (usadas por `service.py` en Task 10) — nota: las tablas reales son `cuentas`/`id_cuenta`, pero el diccionario devuelto usa la clave `id_usuario` (alias en el propio SQL) para que el resto de las tareas (6-13) no necesiten saber que la tabla se llama `cuentas`:
  - `crear_usuario(correo, contrasena_hash, nombre, apellido_paterno, apellido_materno, rol="cliente") -> int`
  - `obtener_usuario_por_correo(correo) -> dict | None` (claves: `id_usuario, correo, contrasena_hash, rol, nombre`)
  - `guardar_codigo(id_usuario, codigo_hash, expira_en) -> int`
  - `obtener_codigo_vigente(id_usuario) -> dict | None` (claves: `id_codigo, codigo_hash`)
  - `marcar_codigo_usado(id_codigo) -> None`
  - `crear_sesion(token, id_usuario, expira_en) -> None`
  - `obtener_sesion_vigente(token) -> dict | None` (claves: `id_usuario, correo, nombre`)
  - `eliminar_sesion(token) -> None`
  - `verificar_conexion() -> bool`

- [ ] **Step 1: Crear `db/repository.py`**

```python
"""Acceso a datos: unico modulo (junto con connection.py) que ejecuta SQL
directamente. service.py nunca abre una conexion ni escribe SQL.

Las tablas reales son cuentas/personas/codigos_verificacion/sesiones
(independientes del monolito, ver Task 1). Las columnas id_cuenta se
alias-ean como id_usuario en el SQL para que el resto del microservicio
(service.py, app.py) trabaje con ese nombre sin conocer el de la tabla."""

from psycopg.rows import dict_row
from db.connection import get_connection


def crear_usuario(correo, contrasena_hash, nombre, apellido_paterno, apellido_materno, rol="cliente"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cuentas (correo, contrasena_hash, rol) "
                "VALUES (%s, %s, %s) RETURNING id_cuenta",
                (correo, contrasena_hash, rol),
            )
            id_usuario = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO personas (id_cuenta, nombre, apellido_paterno, apellido_materno) "
                "VALUES (%s, %s, %s, %s)",
                (id_usuario, nombre, apellido_paterno, apellido_materno),
            )
        conn.commit()
        return id_usuario


def obtener_usuario_por_correo(correo):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT c.id_cuenta AS id_usuario, c.correo, c.contrasena_hash, c.rol, p.nombre "
                "FROM cuentas c JOIN personas p ON p.id_cuenta = c.id_cuenta "
                "WHERE c.correo = %s",
                (correo,),
            )
            return cur.fetchone()


def guardar_codigo(id_usuario, codigo_hash, expira_en):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO codigos_verificacion (id_cuenta, codigo_hash, expira_en) "
                "VALUES (%s, %s, %s) RETURNING id_codigo",
                (id_usuario, codigo_hash, expira_en),
            )
            id_codigo = cur.fetchone()[0]
        conn.commit()
        return id_codigo


def obtener_codigo_vigente(id_usuario):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id_codigo, codigo_hash FROM codigos_verificacion "
                "WHERE id_cuenta = %s AND usado = false AND expira_en > now() "
                "ORDER BY creado_en DESC LIMIT 1",
                (id_usuario,),
            )
            return cur.fetchone()


def marcar_codigo_usado(id_codigo):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE codigos_verificacion SET usado = true WHERE id_codigo = %s",
                (id_codigo,),
            )
        conn.commit()


def crear_sesion(token, id_usuario, expira_en):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sesiones (token, id_cuenta, expira_en) VALUES (%s, %s, %s)",
                (token, id_usuario, expira_en),
            )
        conn.commit()


def obtener_sesion_vigente(token):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT s.id_cuenta AS id_usuario, c.correo, p.nombre "
                "FROM sesiones s "
                "JOIN cuentas c ON c.id_cuenta = s.id_cuenta "
                "JOIN personas p ON p.id_cuenta = s.id_cuenta "
                "WHERE s.token = %s AND s.expira_en > now()",
                (token,),
            )
            return cur.fetchone()


def eliminar_sesion(token):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sesiones WHERE token = %s", (token,))
        conn.commit()


def verificar_conexion():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
```

- [ ] **Step 2: Configurar `.env` local para pruebas** (no se commitea)

Run: `cd apps/services/login && cp .env.example .env` y editar `DB_PASSWORD=change-me-auth`, `LOCAL_MAILBOX_USER=<tu usuario de macOS, ej. whoami>`.

Run: `psql -U library_user -d library -c "ALTER ROLE auth_service_user WITH PASSWORD 'change-me-auth';"` (por si la migración de Task 1 se aplicó con otra contraseña local).

- [ ] **Step 3: Escribir la prueba manual de integración**

```python
"""Prueba manual de repository.py contra una base de datos real (requiere
que data/migrations/2026-09-18_tablas_login.sql ya este aplicado).
No usa ningun framework de pruebas: son asserts planos sobre datos que la
propia prueba crea y limpia.

Uso:
    cd apps/services/login && python tests/test_repository_manual.py
"""
from datetime import datetime, timedelta, timezone

from db import repository
from db.connection import get_connection

CORREO_PRUEBA = "repo.prueba@correo.test"


def limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cuentas WHERE correo = %s", (CORREO_PRUEBA,))
        conn.commit()


def main():
    limpiar()

    id_usuario = repository.crear_usuario(
        CORREO_PRUEBA, "hash-de-prueba", "Ana", "Loredo", "Moreno"
    )
    assert isinstance(id_usuario, int)
    print(f"crear_usuario OK -> id_usuario={id_usuario}")

    usuario = repository.obtener_usuario_por_correo(CORREO_PRUEBA)
    assert usuario is not None
    assert usuario["nombre"] == "Ana"
    print("obtener_usuario_por_correo OK")

    expira_en = datetime.now(timezone.utc) + timedelta(minutes=5)
    id_codigo = repository.guardar_codigo(id_usuario, "codigo-hash", expira_en)
    vigente = repository.obtener_codigo_vigente(id_usuario)
    assert vigente["id_codigo"] == id_codigo
    print("guardar_codigo / obtener_codigo_vigente OK")

    repository.marcar_codigo_usado(id_codigo)
    assert repository.obtener_codigo_vigente(id_usuario) is None
    print("marcar_codigo_usado OK")

    token = "token-de-prueba-1234"
    expira_sesion = datetime.now(timezone.utc) + timedelta(minutes=30)
    repository.crear_sesion(token, id_usuario, expira_sesion)
    sesion = repository.obtener_sesion_vigente(token)
    assert sesion["correo"] == CORREO_PRUEBA
    print("crear_sesion / obtener_sesion_vigente OK")

    repository.eliminar_sesion(token)
    assert repository.obtener_sesion_vigente(token) is None
    print("eliminar_sesion OK")

    assert repository.verificar_conexion() is True
    print("verificar_conexion OK")

    limpiar()
    print("\nTODAS LAS PRUEBAS DE repository.py PASARON")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar la prueba**

Run: `cd apps/services/login && .venv/bin/python tests/test_repository_manual.py`
Expected: imprime cada "OK" y termina con `TODAS LAS PRUEBAS DE repository.py PASARON`, sin `AssertionError` ni excepción.

- [ ] **Step 5: Commit**

```bash
git add apps/services/login/db/repository.py apps/services/login/tests/test_repository_manual.py
git commit -m "feat(login): capa de acceso a datos (repository.py)"
```

---


### Task 6: Seguridad pura (`auth/security.py`)

**Files:**
- Create: `apps/services/login/auth/security.py`
- Create: `apps/services/login/tests/test_security.py`

**Interfaces:**
- Produces (usadas por `service.py` en Task 10): `hash_password(password) -> str`, `verificar_password(password, password_hash) -> bool`, `generar_codigo() -> str` (6 dígitos), `hash_codigo(codigo) -> str`, `verificar_codigo(codigo, codigo_hash) -> bool`, `generar_token() -> str` (64 caracteres hex).

- [ ] **Step 1: Escribir la prueba (falla porque el módulo no existe)**

```python
"""Pruebas puras de auth/security.py (sin BD, sin red). Asserts planos.

Uso:
    cd apps/services/login && python tests/test_security.py
"""
from auth.security import (
    hash_password, verificar_password,
    generar_codigo, hash_codigo, verificar_codigo,
    generar_token,
)


def main():
    hash_pw = hash_password("miPassword123")
    assert hash_pw != "miPassword123"
    assert verificar_password("miPassword123", hash_pw) is True
    assert verificar_password("otraCosa", hash_pw) is False
    print("hash_password / verificar_password OK")

    codigo = generar_codigo()
    assert len(codigo) == 6
    assert codigo.isdigit()
    print(f"generar_codigo OK -> {codigo}")

    hash_c = hash_codigo(codigo)
    assert hash_c != codigo
    assert verificar_codigo(codigo, hash_c) is True
    assert verificar_codigo("000000" if codigo != "000000" else "111111", hash_c) is False
    print("hash_codigo / verificar_codigo OK")

    token_a = generar_token()
    token_b = generar_token()
    assert len(token_a) == 64
    assert token_a != token_b
    print("generar_token OK")

    print("\nTODAS LAS PRUEBAS DE security.py PASARON")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `cd apps/services/login && .venv/bin/python tests/test_security.py`
Expected: `ModuleNotFoundError: No module named 'auth.security'`

- [ ] **Step 3: Implementar `auth/security.py`**

```python
"""Logica pura de seguridad: hashing de contrasenas y codigos 2FA,
generacion de codigos y tokens de sesion. No importa Flask ni psycopg."""

import secrets
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password):
    return generate_password_hash(password)


def verificar_password(password, password_hash):
    return check_password_hash(password_hash, password)


def generar_codigo():
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_codigo(codigo):
    return generate_password_hash(codigo)


def verificar_codigo(codigo, codigo_hash):
    return check_password_hash(codigo_hash, codigo)


def generar_token():
    return secrets.token_hex(32)
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `cd apps/services/login && .venv/bin/python tests/test_security.py`
Expected: `TODAS LAS PRUEBAS DE security.py PASARON`

- [ ] **Step 5: Commit**

```bash
git add apps/services/login/auth/security.py apps/services/login/tests/test_security.py
git commit -m "feat(login): hashing de passwords/codigos y generacion de tokens"
```

---

### Task 7: Serialización XML/JSON (`render/formatters.py`)

**Files:**
- Create: `apps/services/login/render/formatters.py`
- Create: `apps/services/login/tests/test_formatters.py`

**Interfaces:**
- Consumes: Flask (Task 4's `requirements.txt` ya lo incluye).
- Produces (usadas por `app.py` en Task 11): `formato_solicitado() -> str` (lee `request.args`), `dict_a_xml(raiz, datos) -> str`, `responder(raiz, datos, status=200) -> flask.Response`.

- [ ] **Step 1: Escribir la prueba (falla porque el módulo no existe)**

```python
"""Pruebas de render/formatters.py. dict_a_xml es pura (no necesita
contexto de Flask); responder() se prueba dentro de un request_context de
Flask, sin levantar un servidor real.

Uso:
    cd apps/services/login && python tests/test_formatters.py
"""
from flask import Flask

from render.formatters import dict_a_xml, formato_solicitado, responder

app = Flask(__name__)


def main():
    xml = dict_a_xml("usuario", {"id_usuario": 1, "activo": True})
    assert xml == "<usuario><id_usuario>1</id_usuario><activo>true</activo></usuario>"
    print("dict_a_xml OK")

    with app.test_request_context("/login?format=json"):
        assert formato_solicitado() == "json"
        resp = responder("login", {"pendiente_verificacion": True}, status=200)
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/json")
        print("responder(json) OK")

    with app.test_request_context("/login"):
        assert formato_solicitado() == "xml"
        resp = responder("login", {"pendiente_verificacion": True}, status=200)
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/xml")
        assert b"<login>" in resp.data
        print("responder(xml, default) OK")

    print("\nTODAS LAS PRUEBAS DE formatters.py PASARON")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `cd apps/services/login && .venv/bin/python tests/test_formatters.py`
Expected: `ModuleNotFoundError: No module named 'render.formatters'`

- [ ] **Step 3: Implementar `render/formatters.py`**

```python
"""Serializacion de respuestas en XML (formato por defecto) o JSON segun
?format=. Unico modulo que sabe construir el Response de Flask."""

from xml.etree.ElementTree import Element, SubElement, tostring
from flask import jsonify, request, Response


def _agregar_nodo(padre, clave, valor):
    nodo = SubElement(padre, clave)
    if isinstance(valor, dict):
        for k, v in valor.items():
            _agregar_nodo(nodo, k, v)
    elif isinstance(valor, bool):
        nodo.text = "true" if valor else "false"
    elif valor is None:
        nodo.text = ""
    else:
        nodo.text = str(valor)


def dict_a_xml(raiz, datos):
    elemento_raiz = Element(raiz)
    for clave, valor in datos.items():
        _agregar_nodo(elemento_raiz, clave, valor)
    return tostring(elemento_raiz, encoding="unicode")


def formato_solicitado():
    return request.args.get("format", "xml").lower()


def responder(raiz, datos, status=200):
    if formato_solicitado() == "json":
        respuesta = jsonify(datos)
        respuesta.status_code = status
        return respuesta
    xml = dict_a_xml(raiz, datos)
    return Response(xml, status=status, mimetype="application/xml")
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `cd apps/services/login && .venv/bin/python tests/test_formatters.py`
Expected: `TODAS LAS PRUEBAS DE formatters.py PASARON`

- [ ] **Step 5: Commit**

```bash
git add apps/services/login/render/formatters.py apps/services/login/tests/test_formatters.py
git commit -m "feat(login): serializacion de respuestas XML/JSON"
```

---

### Task 8: Excepciones de dominio (`errors.py`)

**Files:**
- Create: `apps/services/login/errors.py`

**Interfaces:**
- Produces (usadas por `service.py` en Task 10 y `app.py` en Task 11): `ErrorDominio` (base, atributo `.status`), y subclases `CamposFaltantes` (400), `EmailInvalido` (400), `PasswordDebil` (400), `EmailDuplicado` (409), `CredencialesInvalidas` (401), `CodigoInvalido` (401), `SesionInvalida` (401).

- [ ] **Step 1: Crear `errors.py`**

```python
"""Excepciones de dominio. Cada una lleva su status HTTP; app.py las
traduce a una respuesta XML/JSON con render.formatters.responder."""


class ErrorDominio(Exception):
    status = 400


class CamposFaltantes(ErrorDominio):
    status = 400


class EmailInvalido(ErrorDominio):
    status = 400


class PasswordDebil(ErrorDominio):
    status = 400


class EmailDuplicado(ErrorDominio):
    status = 409


class CredencialesInvalidas(ErrorDominio):
    status = 401


class CodigoInvalido(ErrorDominio):
    status = 401


class SesionInvalida(ErrorDominio):
    status = 401
```

- [ ] **Step 2: Verificar que cada subclase expone `.status` correctamente**

Run:
```bash
cd apps/services/login && .venv/bin/python -c "
from errors import CamposFaltantes, EmailDuplicado, CredencialesInvalidas
assert CamposFaltantes('x').status == 400
assert EmailDuplicado('x').status == 409
assert CredencialesInvalidas('x').status == 401
print('errors.py OK')
"
```
Expected: `errors.py OK`

- [ ] **Step 3: Commit**

```bash
git add apps/services/login/errors.py
git commit -m "feat(login): excepciones de dominio con status HTTP"
```

---

### Task 9: Envío del código 2FA por SMTP local (`mail/sender.py`) + Postfix

**Files:**
- Create: `apps/services/login/mail/sender.py`
- Create: `apps/services/login/tests/test_sender.py`
- Create: `apps/services/login/README_POSTFIX.md`

**Interfaces:**
- Consumes: `config.settings.{SMTP_HOST, SMTP_PORT, LOCAL_MAILBOX_USER, MAIL_FROM}` (Task 4).
- Produces (usada por `service.py` en Task 10): `enviar_codigo(correo_destinatario, codigo) -> None`.

- [ ] **Step 1: Escribir la prueba (con `smtplib.SMTP` simulado, sin necesitar Postfix corriendo)**

```python
"""Prueba de mail/sender.py. No abre una conexion SMTP real: reemplaza
smtplib.SMTP por un doble de prueba para verificar que el mensaje se arma
y se envia correctamente, sin depender de que Postfix este activo en esta
maquina. La entrega real se valida por separado en README_POSTFIX.md y en
el script end-to-end de la Fase 4.

Uso:
    cd apps/services/login && python tests/test_sender.py
"""
from unittest.mock import patch, MagicMock

from mail.sender import enviar_codigo


def main():
    with patch("mail.sender.smtplib.SMTP") as smtp_mock:
        instancia = MagicMock()
        smtp_mock.return_value.__enter__.return_value = instancia

        enviar_codigo("destinatario@correo.test", "123456")

        assert smtp_mock.called
        instancia.send_message.assert_called_once()
        mensaje_enviado = instancia.send_message.call_args[0][0]
        assert "123456" in mensaje_enviado.get_content()
        assert "destinatario@correo.test" in mensaje_enviado.get_content()
        print("enviar_codigo OK (SMTP simulado)")

    print("\nTODAS LAS PRUEBAS DE sender.py PASARON")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `cd apps/services/login && .venv/bin/python tests/test_sender.py`
Expected: `ModuleNotFoundError: No module named 'mail.sender'`

- [ ] **Step 3: Implementar `mail/sender.py`**

```python
"""Envio del codigo 2FA por SMTP LOCAL (Postfix corriendo en la misma
instancia, sin relay externo). Ver README_POSTFIX.md para la
configuracion de Postfix en la instancia de GCP."""

import smtplib
from email.message import EmailMessage

from config.settings import SMTP_HOST, SMTP_PORT, LOCAL_MAILBOX_USER, MAIL_FROM


def enviar_codigo(correo_destinatario, codigo):
    mensaje = EmailMessage()
    mensaje["Subject"] = f"Codigo de verificacion para {correo_destinatario}"
    mensaje["From"] = MAIL_FROM
    mensaje["To"] = f"{LOCAL_MAILBOX_USER}@localhost"
    mensaje.set_content(
        f"Cuenta: {correo_destinatario}\n"
        f"Codigo de verificacion: {codigo}\n"
        f"Este codigo expira en unos minutos."
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.send_message(mensaje)
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `cd apps/services/login && .venv/bin/python tests/test_sender.py`
Expected: `TODAS LAS PRUEBAS DE sender.py PASARON`

- [ ] **Step 5: Documentar la configuración real de Postfix (para la instancia de GCP)**

```markdown
# Postfix local para el 2FA (apps/services/login)

Este microservicio NUNCA usa un proveedor SMTP externo (Gmail, SendGrid,
etc.). El correo del 2FA lo entrega Postfix, instalado y corriendo en la
misma instancia de GCP, y se queda dentro de la instancia (buzon local del
usuario del sistema operativo) — no sale a internet.

## Instalar y configurar (una sola vez, en la instancia GCP — Rocky/RHEL)

```bash
sudo dnf install -y postfix mailx
sudo postconf -e 'inet_interfaces = loopback-only'
sudo postconf -e 'mydestination = localhost.localdomain, localhost, $myhostname'
sudo systemctl enable --now postfix
```

`inet_interfaces = loopback-only` asegura que Postfix solo escucha en
`localhost` (nunca acepta conexiones desde fuera de la instancia).
`mydestination` hace que Postfix entregue localmente cualquier correo
dirigido a esos dominios, en vez de intentar relay externo.

## Configurar el microservicio

En `apps/services/login/.env`:

```
SMTP_HOST=localhost
SMTP_PORT=25
LOCAL_MAILBOX_USER=<usuario de Linux con el que hiciste SSH, ej. output de `whoami`>
```

## Verificar que la entrega local funciona

```bash
echo "prueba manual" | mail -s "Prueba Postfix" "$(whoami)@localhost"
mail   # lista el correo entrante; abre el mensaje "Prueba Postfix"
```

Si `mail` te muestra el mensaje que acabas de mandarte, Postfix está listo
para que `mail/sender.py` le entregue los códigos 2FA.
```

- [ ] **Step 6: Commit**

```bash
git add apps/services/login/mail/sender.py apps/services/login/tests/test_sender.py apps/services/login/README_POSTFIX.md
git commit -m "feat(login): envio de codigo 2FA por SMTP local (Postfix) + guia de configuracion"
```

---

### Task 10: Orquestación de negocio (`service.py`)

**Files:**
- Create: `apps/services/login/service.py`

**Interfaces:**
- Consumes: `db.repository.*` (Task 5), `auth.security.*` (Task 6), `mail.sender.enviar_codigo` (Task 9), `errors.*` (Task 8), `config.settings.{SESSION_TTL_MINUTES, CODE_TTL_MINUTES}` (Task 4).
- Produces (usadas por `app.py` en Task 11): `registrar(nombre, apellido_paterno, apellido_materno, email, password) -> int`, `iniciar_login(email, password) -> None`, `verificar_login(email, codigo) -> str` (token), `cerrar_sesion(token) -> None`, `consultar_sesion(token) -> dict`, `verificar_salud() -> bool`.

- [ ] **Step 1: Crear `service.py`**

```python
"""Logica de negocio: valida datos, coordina repository/security/mail, y
traduce reglas de negocio a excepciones de dominio. No conoce Flask."""

import re
from datetime import datetime, timedelta, timezone

from config.settings import SESSION_TTL_MINUTES, CODE_TTL_MINUTES
from db import repository
from auth.security import (
    hash_password, verificar_password,
    generar_codigo, hash_codigo, verificar_codigo,
    generar_token,
)
from mail.sender import enviar_codigo
from errors import (
    CamposFaltantes, EmailInvalido, PasswordDebil, EmailDuplicado,
    CredencialesInvalidas, CodigoInvalido, SesionInvalida,
)

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def registrar(nombre, apellido_paterno, apellido_materno, email, password):
    if not all([nombre, apellido_paterno, apellido_materno, email, password]):
        raise CamposFaltantes("Todos los campos son obligatorios.")
    if not REGEX_EMAIL.match(email):
        raise EmailInvalido("El correo no tiene un formato valido.")
    if len(password) < 8:
        raise PasswordDebil("La contrasena debe tener al menos 8 caracteres.")
    if repository.obtener_usuario_por_correo(email):
        raise EmailDuplicado("Ese correo ya esta registrado.")
    return repository.crear_usuario(
        email, hash_password(password), nombre, apellido_paterno, apellido_materno
    )


def iniciar_login(email, password):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario or not verificar_password(password, usuario["contrasena_hash"]):
        raise CredencialesInvalidas("Credenciales invalidas.")
    codigo = generar_codigo()
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
    repository.guardar_codigo(usuario["id_usuario"], hash_codigo(codigo), expira_en)
    enviar_codigo(email, codigo)


def verificar_login(email, codigo):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario:
        raise CodigoInvalido("Codigo invalido o expirado.")
    pendiente = repository.obtener_codigo_vigente(usuario["id_usuario"])
    if not pendiente or not verificar_codigo(codigo, pendiente["codigo_hash"]):
        raise CodigoInvalido("Codigo invalido o expirado.")
    repository.marcar_codigo_usado(pendiente["id_codigo"])
    token = generar_token()
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)
    repository.crear_sesion(token, usuario["id_usuario"], expira_en)
    return token


def cerrar_sesion(token):
    if not token or not repository.obtener_sesion_vigente(token):
        raise SesionInvalida("Token de sesion invalido o inexistente.")
    repository.eliminar_sesion(token)


def consultar_sesion(token):
    if not token:
        return {"autenticado": False}
    sesion = repository.obtener_sesion_vigente(token)
    if not sesion:
        return {"autenticado": False}
    return {
        "autenticado": True,
        "id_usuario": sesion["id_usuario"],
        "email": sesion["correo"],
        "nombre": sesion["nombre"],
    }


def verificar_salud():
    try:
        return repository.verificar_conexion()
    except Exception:
        return False
```

- [ ] **Step 2: Prueba manual de orquestación completa (registro → login → verify → session → logout)**

```python
"""Prueba manual de service.py de punta a punta, contra la BD real y con
mail.sender.enviar_codigo mockeado (no depende de Postfix). Requiere la
migracion de Task 1 ya aplicada.

Uso:
    cd apps/services/login && python tests/test_service_manual.py
"""
from unittest.mock import patch

import service
from errors import CredencialesInvalidas, CodigoInvalido, SesionInvalida
from db.connection import get_connection
from auth.security import generar_codigo

CORREO_PRUEBA = "service.prueba@correo.test"


def limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cuentas WHERE correo = %s", (CORREO_PRUEBA,))
        conn.commit()


def main():
    limpiar()
    codigo_capturado = {}

    def enviar_codigo_falso(correo, codigo):
        codigo_capturado["valor"] = codigo

    with patch("service.enviar_codigo", side_effect=enviar_codigo_falso):
        id_usuario = service.registrar("Ana", "Loredo", "Moreno", CORREO_PRUEBA, "password123")
        assert isinstance(id_usuario, int)
        print("registrar OK")

        service.iniciar_login(CORREO_PRUEBA, "password123")
        assert "valor" in codigo_capturado
        print(f"iniciar_login OK -> codigo capturado {codigo_capturado['valor']}")

        try:
            service.iniciar_login(CORREO_PRUEBA, "contrasena-incorrecta")
            raise AssertionError("Debio lanzar CredencialesInvalidas")
        except CredencialesInvalidas:
            print("iniciar_login rechaza password incorrecta OK")

        try:
            service.verificar_login(CORREO_PRUEBA, "000000")
            raise AssertionError("Debio lanzar CodigoInvalido")
        except CodigoInvalido:
            print("verificar_login rechaza codigo incorrecto OK")

        token = service.verificar_login(CORREO_PRUEBA, codigo_capturado["valor"])
        assert isinstance(token, str) and len(token) == 64
        print("verificar_login OK -> token de sesion creado")

        estado = service.consultar_sesion(token)
        assert estado["autenticado"] is True
        assert estado["email"] == CORREO_PRUEBA
        print("consultar_sesion(token valido) OK")

        service.cerrar_sesion(token)
        estado_tras_logout = service.consultar_sesion(token)
        assert estado_tras_logout["autenticado"] is False
        print("cerrar_sesion OK")

        try:
            service.cerrar_sesion(token)
            raise AssertionError("Debio lanzar SesionInvalida")
        except SesionInvalida:
            print("cerrar_sesion sobre token ya cerrado OK")

    assert service.verificar_salud() is True
    print("verificar_salud OK")

    limpiar()
    print("\nTODAS LAS PRUEBAS DE service.py PASARON")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Ejecutar la prueba**

Run: `cd apps/services/login && .venv/bin/python tests/test_service_manual.py`
Expected: cada paso imprime "OK" y termina con `TODAS LAS PRUEBAS DE service.py PASARON`.

- [ ] **Step 4: Commit**

```bash
git add apps/services/login/service.py apps/services/login/tests/test_service_manual.py
git commit -m "feat(login): orquestacion de negocio (registro, login 2FA, sesiones)"
```

---

### Task 11: Rutas HTTP y Swagger (`app.py`)

**Files:**
- Create: `apps/services/login/app.py`

**Interfaces:**
- Consumes: `service.*` (Task 10), `errors.ErrorDominio` (Task 8), `render.formatters.responder` (Task 7), `config.settings.PORT` (Task 4).
- Produces: servidor Flask con las 6 rutas del contrato (sección 4 del spec).

- [ ] **Step 1: Crear `app.py`**

```python
"""Rutas HTTP del microservicio de login. Traduce excepciones de dominio
a respuestas XML/JSON con el status correcto; no contiene reglas de
negocio (eso vive en service.py)."""

from flask import Flask, request
from flasgger import Swagger

from config.settings import PORT
import service
from errors import ErrorDominio
from render.formatters import responder

app = Flask(__name__)
app.config["SWAGGER"] = {"title": "Microservicio de Autenticacion", "uiversion": 3}
Swagger(app)


def _token_de_header():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None


@app.errorhandler(ErrorDominio)
def manejar_error_dominio(err):
    return responder("error", {"mensaje": str(err)}, status=err.status)


@app.route("/register", methods=["POST"])
def register():
    """
    Registra un nuevo usuario.
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
          required: [nombre, apellido_paterno, apellido_materno, email, password]
          properties:
            nombre: {type: string, example: Ana}
            apellido_paterno: {type: string, example: Loredo}
            apellido_materno: {type: string, example: Moreno}
            email: {type: string, example: ana@correo.test}
            password: {type: string, example: password123}
    responses:
      201:
        description: "Usuario creado. XML: <usuario><id_usuario>7</id_usuario></usuario>. JSON: {\"id_usuario\": 7}"
      400:
        description: Datos invalidos o faltantes
      409:
        description: El correo ya esta registrado
    """
    datos = request.get_json(force=True, silent=True) or {}
    id_usuario = service.registrar(
        datos.get("nombre"), datos.get("apellido_paterno"),
        datos.get("apellido_materno"), datos.get("email"), datos.get("password"),
    )
    return responder("usuario", {"id_usuario": id_usuario}, status=201)


@app.route("/login", methods=["POST"])
def login():
    """
    Valida credenciales y envia el codigo 2FA al buzon local de la instancia.
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
          required: [email, password]
          properties:
            email: {type: string}
            password: {type: string}
    responses:
      200:
        description: "Codigo enviado. XML: <login><pendiente_verificacion>true</pendiente_verificacion></login>. JSON: {\"pendiente_verificacion\": true}"
      401:
        description: Credenciales invalidas
    """
    datos = request.get_json(force=True, silent=True) or {}
    service.iniciar_login(datos.get("email"), datos.get("password"))
    return responder("login", {"pendiente_verificacion": True})


@app.route("/login/verify", methods=["POST"])
def login_verify():
    """
    Verifica el codigo 2FA y crea la sesion (valida 30 minutos).
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
          required: [email, codigo]
          properties:
            email: {type: string}
            codigo: {type: string, example: "123456"}
    responses:
      200:
        description: "Sesion creada. XML: <sesion><session_token>...</session_token></sesion>. JSON: {\"session_token\": \"...\"}"
      401:
        description: Codigo invalido o expirado
    """
    datos = request.get_json(force=True, silent=True) or {}
    token = service.verificar_login(datos.get("email"), datos.get("codigo"))
    return responder("sesion", {"session_token": token})


@app.route("/logout", methods=["POST"])
def logout():
    """
    Cierra la sesion asociada al token del header Authorization.
    ---
    parameters:
      - in: header
        name: Authorization
        type: string
        required: true
        description: "Bearer <session_token>"
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: Sesion cerrada
      401:
        description: Token invalido, expirado o ausente
    """
    service.cerrar_sesion(_token_de_header())
    return responder("logout", {"mensaje": "Sesion cerrada."})


@app.route("/session", methods=["GET"])
def session_status():
    """
    Consulta si existe una sesion autenticada para el token dado.
    ---
    parameters:
      - in: header
        name: Authorization
        type: string
        required: false
        description: "Bearer <session_token>"
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: "Siempre 200. XML: <sesion><autenticado>true</autenticado>...</sesion>. JSON: {\"autenticado\": false}"
    """
    return responder("sesion", service.consultar_sesion(_token_de_header()))


@app.route("/health", methods=["GET"])
def health():
    """
    Verifica el estado del microservicio y de PostgreSQL.
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: "Servicio saludable. JSON: {\"status\": \"ok\", \"db\": \"ok\"}"
      503:
        description: PostgreSQL no responde
    """
    if service.verificar_salud():
        return responder("salud", {"status": "ok", "db": "ok"})
    return responder("salud", {"status": "error", "db": "error"}, status=503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
```

- [ ] **Step 2: Levantar el servicio localmente**

Run: `cd apps/services/login && .venv/bin/python app.py`
Expected: `* Running on http://0.0.0.0:5000` sin excepciones al arrancar (déjalo corriendo en esa terminal para los siguientes pasos).

- [ ] **Step 3: Probar `/health` en XML y JSON**

Run: `curl -s http://localhost:5000/health`
Expected: `<salud><status>ok</status><db>ok</db></salud>`

Run: `curl -s "http://localhost:5000/health?format=json"`
Expected: `{"db":"ok","status":"ok"}`

- [ ] **Step 4: Probar el flujo completo con curl (registro → login → verify → session → logout → session)**

Run:
```bash
curl -s -X POST "http://localhost:5000/register?format=json" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Ana","apellido_paterno":"Loredo","apellido_materno":"Moreno","email":"curl.prueba@correo.test","password":"password123"}'
```
Expected: `HTTP 201`, `{"id_usuario": N}`.

Run:
```bash
curl -s -X POST "http://localhost:5000/login?format=json" \
  -H "Content-Type: application/json" \
  -d '{"email":"curl.prueba@correo.test","password":"password123"}'
```
Expected: `{"pendiente_verificacion": true}`.

Run (leer el código real del buzón local, requiere Postfix configurado — ver `README_POSTFIX.md`; si Postfix aún no está activo en esta máquina, tomar el código directo de la tabla para esta prueba puntual):

Run: `psql -U auth_service_user -d library -c "SELECT codigo_hash FROM codigos_verificacion ORDER BY creado_en DESC LIMIT 1;"` — esto solo confirma que se guardó un hash; el código en texto plano solo existe en el correo. Con Postfix activo:

Run: `mail` (leer el correo, copiar el código de 6 dígitos del cuerpo)

Run:
```bash
curl -s -X POST "http://localhost:5000/login/verify?format=json" \
  -H "Content-Type: application/json" \
  -d '{"email":"curl.prueba@correo.test","codigo":"<codigo-leido-del-correo>"}'
```
Expected: `{"session_token": "<64 caracteres hex>"}`. Guardar ese token en una variable: `TOKEN=<lo-que-devolvio>`.

Run: `curl -s "http://localhost:5000/session?format=json" -H "Authorization: Bearer $TOKEN"`
Expected: `{"autenticado": true, "id_usuario": N, "email": "curl.prueba@correo.test", "nombre": "Ana"}`.

Run: `curl -s -X POST "http://localhost:5000/logout?format=json" -H "Authorization: Bearer $TOKEN"`
Expected: `{"mensaje": "Sesion cerrada."}`.

Run: `curl -s "http://localhost:5000/session?format=json" -H "Authorization: Bearer $TOKEN"`
Expected: `{"autenticado": false}`.

Repetir la misma secuencia sin `?format=json` (o con `?format=xml`) y confirmar que cada respuesta viene envuelta en las mismas etiquetas XML de `app.py`.

- [ ] **Step 5: Probar Swagger**

Run: `curl -s http://localhost:5000/apidocs/ -o /dev/null -w "%{http_code}\n"`
Expected: `200`

Abrir `http://localhost:5000/apidocs/` en el navegador y confirmar que aparecen los 6 endpoints documentados.

- [ ] **Step 6: Commit**

```bash
git add apps/services/login/app.py
git commit -m "feat(login): rutas HTTP con 2FA, sesiones de 30 min y Swagger"
```

---

## Fase 4 — Validación end-to-end y documentación

### Task 12: Script de pruebas manuales de punta a punta

**Files:**
- Create: `apps/services/login/tests/pruebas_manuales.py`

**Interfaces:**
- Consumes: el servicio corriendo (Task 11) vía HTTP; sin importar módulos internos (usa `urllib` como el script análogo de `library_soap_service`).

- [ ] **Step 1: Escribir el script**

```python
"""Plan de pruebas ejecutado contra una instancia real del microservicio
de login (por defecto http://localhost:5000). No usa ningun framework de
pruebas (mismo criterio que library_soap_service/tests/pruebas_manuales.py):
son peticiones HTTP planas con urllib (stdlib), probando cada endpoint en
XML y en JSON, mostrando lo esperado vs lo obtenido.

El paso de 2FA requiere leer el codigo real del buzon local de la
instancia (`mail`, ver README_POSTFIX.md) y pegarlo cuando el script lo
pida por stdin.

Uso:
    python tests/pruebas_manuales.py [URL_BASE]
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"


def solicitar(metodo, ruta, cuerpo=None, headers=None, formato="json"):
    url = f"{URL}{ruta}?format={formato}"
    data = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    encabezados = {"Content-Type": "application/json"}
    encabezados.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=encabezados, method=metodo)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


def verificar(nombre, condicion, detalle):
    estado = "PASA" if condicion else "FALLA"
    print(f"[{estado}] {nombre} -> {detalle}")
    return condicion


def main():
    correo = f"e2e.{uuid.uuid4().hex[:8]}@correo.test"
    password = "password123"
    resultados = []

    for formato in ("json", "xml"):
        print(f"\n{'=' * 70}\nFORMATO: {formato}\n{'=' * 70}")

        status, cuerpo = solicitar("GET", "/health", formato=formato)
        resultados.append(verificar("GET /health", status == 200, f"HTTP {status} | {cuerpo}"))

        status, cuerpo = solicitar(
            "POST", "/register",
            {"nombre": "Ana", "apellido_paterno": "Loredo", "apellido_materno": "Moreno",
             "email": f"{formato}.{correo}", "password": password},
            formato=formato,
        )
        resultados.append(verificar("POST /register", status == 201, f"HTTP {status} | {cuerpo}"))

        status, cuerpo = solicitar(
            "POST", "/login",
            {"email": f"{formato}.{correo}", "password": password},
            formato=formato,
        )
        resultados.append(verificar("POST /login", status == 200, f"HTTP {status} | {cuerpo}"))

        codigo = input(
            f"\nRevisa el buzon local (`mail`) y escribe el codigo 2FA "
            f"recibido para {formato}.{correo}: "
        ).strip()

        status, cuerpo = solicitar(
            "POST", "/login/verify",
            {"email": f"{formato}.{correo}", "codigo": codigo},
            formato=formato,
        )
        ok_verify = status == 200
        resultados.append(verificar("POST /login/verify", ok_verify, f"HTTP {status} | {cuerpo}"))

        token = None
        if ok_verify:
            if formato == "json":
                token = json.loads(cuerpo)["session_token"]
            else:
                inicio = cuerpo.index("<session_token>") + len("<session_token>")
                fin = cuerpo.index("</session_token>")
                token = cuerpo[inicio:fin]

        encabezado_auth = {"Authorization": f"Bearer {token}"} if token else {}

        status, cuerpo = solicitar("GET", "/session", headers=encabezado_auth, formato=formato)
        resultados.append(verificar(
            "GET /session (autenticado)",
            status == 200 and "true" in cuerpo.lower(),
            f"HTTP {status} | {cuerpo}",
        ))

        status, cuerpo = solicitar("POST", "/logout", headers=encabezado_auth, formato=formato)
        resultados.append(verificar("POST /logout", status == 200, f"HTTP {status} | {cuerpo}"))

        status, cuerpo = solicitar("GET", "/session", headers=encabezado_auth, formato=formato)
        resultados.append(verificar(
            "GET /session (tras logout)",
            status == 200 and "false" in cuerpo.lower(),
            f"HTTP {status} | {cuerpo}",
        ))

    print(f"\n{'=' * 70}\nRESUMEN: {sum(resultados)}/{len(resultados)} pruebas PASARON\n{'=' * 70}")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar contra la instancia real (local o GCP) con el servicio y Postfix corriendo**

Run: `cd apps/services/login && .venv/bin/python tests/pruebas_manuales.py`
Expected: para cada paso, el script pide leer el correo del buzón local (`mail`) y pegar el código; al final imprime `RESUMEN: N/N pruebas PASARON` con las 14 verificaciones (7 por formato) en `PASA`.

- [ ] **Step 3: Commit**

```bash
git add apps/services/login/tests/pruebas_manuales.py
git commit -m "test(login): script de validacion end-to-end (XML y JSON, 2FA real)"
```

---

### Task 13: README del microservicio

**Files:**
- Create: `apps/services/login/README.md`

**Interfaces:**
- Ninguna (documentación).

- [ ] **Step 1: Escribir `README.md`**

```markdown
# apps/services/login

Microservicio independiente de autenticación y gestión básica de usuarios
para la librería en línea. Se integra por base de datos con el monolito
(`apps/web-monolito01`), **sin llamadas HTTP hacia/desde él**.

## Arquitectura

```
Cliente (curl / Postman, sin interfaz grafica)
   │
   ▼
HTTP  (XML por defecto, JSON con ?format=json)
   │
   ▼
apps/services/login (Flask)
   │  app.py             → rutas HTTP + Swagger + errores → status
   │  service.py         → reglas de negocio (registro, 2FA, sesiones)
   │  db/repository.py   → SQL parametrizado
   │  auth/security.py   → hashing de passwords/codigos, tokens
   │  mail/sender.py     → SMTP local (Postfix), nunca externo
   │  render/formatters.py → serializacion XML/JSON
   ▼
PostgreSQL (rol auth_service_user, minimo privilegio)
   - Lee/escribe: usuarios, personas, codigos_verificacion, sesiones

En paralelo, el monolito Node.js sigue leyendo/escribiendo usuarios+personas
con su propio rol (library_user); ninguno de los dos llama al otro.
```

## Endpoints

| Método | Ruta | Función |
|---|---|---|
| POST | `/register` | Registrar un nuevo usuario |
| POST | `/login` | Validar credenciales y enviar código 2FA por correo local |
| POST | `/login/verify` | Verificar el código 2FA y crear la sesión (30 min) |
| POST | `/logout` | Cerrar la sesión |
| GET | `/session` | Consultar si existe una sesión autenticada |
| GET | `/health` | Verificar el estado del microservicio y de PostgreSQL |

Todos soportan `?format=xml` (default) y `?format=json`.

## Configuración

```bash
cp .env.example .env
# editar DB_PASSWORD y LOCAL_MAILBOX_USER
```

Ver `README_POSTFIX.md` para configurar el servidor SMTP local (Postfix)
que entrega los códigos 2FA — requisito: SMTP propio de la instancia,
nunca un proveedor externo.

## Ejecutar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

El servicio queda en `http://localhost:5000`. Documentación interactiva en
`http://localhost:5000/apidocs/`.

## Probar

```bash
.venv/bin/python tests/test_security.py
.venv/bin/python tests/test_formatters.py
.venv/bin/python tests/test_sender.py
.venv/bin/python tests/test_repository_manual.py       # requiere Postgres con la migracion aplicada
.venv/bin/python tests/test_service_manual.py            # requiere Postgres con la migracion aplicada
.venv/bin/python tests/pruebas_manuales.py                # end-to-end real, requiere el servicio + Postfix corriendo
```

## Migración de base de datos requerida

Antes de correr este servicio, aplicar una sola vez:

```bash
psql -U library_user -d library -f ../../../data/migrations/2026-09-18_normalizar_usuarios.sql
```
```

- [ ] **Step 2: Verificar enlaces relativos del README**

Run: `cd apps/services/login && ls ../../../data/migrations/2026-09-18_normalizar_usuarios.sql`
Expected: el archivo existe (creado en Task 1).

- [ ] **Step 3: Commit**

```bash
git add apps/services/login/README.md
git commit -m "docs(login): README del microservicio de autenticacion"
```

---

## Cobertura del spec

- Registro con nombre/apellidos/email/password, email único y validado, password hasheada → Tasks 1, 6, 10.
- Login + 2FA por correo (SMTP propio, local) → Tasks 9, 10, 11.
- Sesión de 30 min por token propio, `/session`, `/logout` → Tasks 5, 10, 11.
- `/health` con verificación real de Postgres → Tasks 5, 10, 11.
- XML default / `?format=json` en todos los endpoints → Task 7, 11.
- Puerto 5000, rol de BD de mínimo privilegio → Tasks 1, 4, 11.
- Swagger con ejemplos XML y JSON → Task 11.
- Monolito no se toca (tablas propias, sin FK ni cambios en `usuarios`) → Task 1.
- Validación real desde la instancia, sin interfaz gráfica → Task 12.
