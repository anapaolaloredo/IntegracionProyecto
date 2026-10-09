# App de escritorio: CRUD de todos los microservicios, semáforos y radio http/https — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la app PySide6 existente (`apps/desktop_app`) opere los seis microservicios: formularios CRUD para Users, Authors, Pedidos y Pagos (además del CRUD de libros que ya existe), semáforos de estado de los seis servicios (con el estado de Redis que reporta cada `/health`) y un radio button http/https (por defecto http) en la configuración.

**Architecture:** Capa `core/` sin Qt (config, cliente REST genérico con Bearer, wrappers por servicio, health) probada con pytest; capa `ui/` con una clase base `CrudTab` que centraliza hilos, refresh de token, 401/403/409/503 y permisos por rol, y una pestaña por servicio. Las llamadas siguen yendo por `HttpClient` (registro HTTP y log en terminal ya existentes). El rol y el id del usuario salen de `GET /session` (`role_id`, `id_usuario`).

**Tech Stack:** Python 3.12, PySide6 ≥ 6.7, requests, pytest; pruebas de UI con `QT_QPA_PLATFORM=offscreen`.

**Spec:** No hay spec escrito (la usuaria pidió "no escribas spec, solo empieza el plan"). Los requisitos salen del enunciado de la entrega: "app Python TK/GUI con todos los microservicios, semáforos, formularios y operaciones CRUD en todos los microservicios" + "radio button http/https, por defecto http" + decisión de la usuaria: **usar PySide6, la app que ya existe**. Rulings provisionales sin spec.

## Global Constraints

- Se reutiliza `apps/desktop_app` (PySide6). No se introduce Tk ni otra librería de UI.
- Ninguna llamada de red en el hilo de la UI: siempre `ui.async_task.ejecutar`.
- Nunca mostrar un traceback: errores como `ServiceError` con mensaje legible (`ui.common.texto_error`).
- Los JWT nunca se escriben en el registro HTTP de la UI; la contraseña ya se enmascara (`"password"`); extender el enmascarado a `password_actual` y `password_nueva`.
- Puertos por defecto: login 5000, books 5001, users 5002, authors 5003, pedidos 5004, pagos 5005. Esquema por defecto: `http`.
- Roles: `role_id` 1 = admin, 2 = cliente. Un cliente solo ve y edita lo suyo; las acciones solo-admin se deshabilitan (no se ocultan) con tooltip "Solo administradores".
- Autenticación con refresh: un 401 con token intenta `renovar_token` una vez; un 503 o fallo de red **no** cierra la sesión.
- Convención: comentarios en español, nombres en español, como el resto de la app.
- Semáforo: `OK` solo si `/health` responde 200 con `"db": "ok"`; Redis se muestra aparte (`"redis": "ok"|"error"`) y no cambia el color del servicio.
- Sin dependencias nuevas en `requirements.txt` (pytest solo para desarrollo).

## Review Focus

1. Invitado (sin token) abre Pedidos/Pagos/Users: debe ver un aviso "Inicia sesión", no un 401 ni una pantalla rota. (Task 6, 7, 9, 10)
2. Un cliente intenta una acción solo-admin (borrar usuario, crear autor): el botón ya está deshabilitado, y si el servidor responde 403 se muestra el mensaje del servidor. (Task 6)
3. Cambiar el radio a https reescribe las seis URLs; volver a http las regresa; una URL con host y puerto personalizados conserva host y puerto. (Task 2)
4. Redis caído (todos los `/health` dan `redis: error` y las rutas protegidas 503): la app muestra mensajes claros, no cierra la sesión y los semáforos siguen en verde (la BD está bien). (Task 5, 11)
5. Pedido con stock insuficiente (409) o pago de pedido ya pagado (409): el mensaje del servidor llega al usuario tal cual. (Task 4, 9, 10)

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `apps/services/soap/app.py` (mod) | Exponer `id_libro` como atributo del `<book>` |
| `apps/desktop_app/core/config.py` (mod) | 6 URLs, `protocolo`, `aplicar_protocolo`, validación |
| `apps/desktop_app/core/books_api.py` (mod) | `Libro.id_libro` |
| `apps/desktop_app/core/rest_api.py` (nuevo) | `RestApi` + `UsersApi`, `AuthorsApi`, `PedidosApi`, `PagosApi` |
| `apps/desktop_app/core/health.py` (mod) | `comprobar_servicio` genérico con Redis |
| `apps/desktop_app/ui/crud_base.py` (nuevo) | `CrudTab`: hilos, errores, permisos, tabla |
| `apps/desktop_app/ui/users_tab.py` `authors_tab.py` `pedidos_tab.py` `pagos_tab.py` (nuevos) | Una pestaña CRUD por servicio |
| `apps/desktop_app/ui/config_panel.py` (mod) | 6 URLs, radio http/https, probar 6 |
| `apps/desktop_app/ui/main_window.py` (mod) | Pestañas nuevas, 6 semáforos, rol y usuario de la sesión, refresh sin cierre en 503 |
| `apps/desktop_app/main.py` (mod) | Construir los 6 clientes HTTP y las APIs |
| `apps/desktop_app/tests/` (mod/nuevos) | `test_core.py`, `test_rest_api.py`, `test_health.py`, `test_config_https.py`, `test_ui_smoke.py`, `conftest.py` |
| `apps/desktop_app/README.md`, `docs/AI_CHANGELOG.md` (mod) | Uso, túnel SSH, checklist manual |

Entorno de pruebas: `cd apps/desktop_app && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q`. (PySide6 pesa ~200 MB; está bien en este venv local, no se versiona.)

---

### Task 1: Soap expone `id_libro` en el XML

Pedidos y Authors piden `id_libro` numérico, pero el catálogo XML solo trae `isbn`. Sin esto la GUI no puede armar líneas de pedido ni vincular libros a autores sin pedir el id a mano. Es un atributo extra en `<book>`; los clientes XML existentes lo ignoran.

**Files:**
- Modify: `apps/services/soap/app.py` (`BOOK_QUERY`, `book_to_element`)
- Test: `apps/services/soap/tests/test_xml_id.py`

**Interfaces:**
- Produces: cada `<book isbn="…" id_libro="11">`. Los endpoints `/api/libros/temas` y `/catalogo` no cambian.

- [ ] **Step 1: Test que falla**

```python
"""El XML del catalogo expone id_libro como atributo (lo usa la app de escritorio)."""

import os
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")

import app as books


def _libro(**extra):
    base = {"isbn": "123", "title": "T", "publicationYear": 2000, "price": 10, "stock": 3,
            "format": "F", "authors": [], "genres": [], "images": [], "concepts": []}
    base.update(extra)
    return base


def test_book_to_element_incluye_id_libro():
    el = books.book_to_element(_libro(id_libro=11))
    assert el.get("isbn") == "123" and el.get("id_libro") == "11"


def test_book_to_element_sin_id_no_truena():
    el = books.book_to_element(_libro())
    assert el.get("id_libro") is None
    assert ET.tostring(el)  # sigue serializable


def test_query_selecciona_id_libro():
    assert "l.id_libro AS id_libro" in books.BOOK_QUERY
```

- [ ] **Step 2: Verlo fallar** — `cd apps/services/soap && .venv/bin/python -m pytest tests/test_xml_id.py -q` → FAIL.
- [ ] **Step 3: Implementar** — en `BOOK_QUERY` agregar `l.id_libro AS id_libro,` como primera columna del SELECT; en `book_to_element` cambiar la creación del elemento a:

```python
    atributos = {"isbn": book["isbn"]}
    if book.get("id_libro") is not None:
        atributos["id_libro"] = str(book["id_libro"])
    book_el = ET.Element("book", **atributos)
```
- [ ] **Step 4: Correr toda la suite de soap** — `.venv/bin/python -m pytest tests -q` → todas pasan (35 + 3).
- [ ] **Step 5: Commit** — `feat(soap): exponer id_libro como atributo del book en el XML`.

---

### Task 2: Config con seis URLs y radio http/https

**Files:**
- Modify: `apps/desktop_app/core/config.py`
- Test: `apps/desktop_app/tests/test_config_https.py`

**Interfaces:**
- Produces:
  - `SERVICIOS = (("login", "Login", 5000), ("books", "Libros", 5001), ("users", "Usuarios", 5002), ("authors", "Autores", 5003), ("pedidos", "Pedidos", 5004), ("pagos", "Pagos", 5005))`
  - `AppConfig` campos nuevos: `users_url, authors_url, pedidos_url, pagos_url` (defaults `http://localhost:500x`) y `protocolo: str = "http"`.
  - `AppConfig.url(clave) -> str` (p. ej. `config.url("pedidos")`).
  - `cambiar_esquema(url, esquema) -> str`: reemplaza solo el esquema.
  - `AppConfig.con_protocolo(protocolo) -> AppConfig`: copia con las seis URLs reescritas y `protocolo` fijado.
  - `validar()` revisa las seis URLs y que `protocolo in ("http","https")`.

- [ ] **Step 1: Tests que fallan**

```python
import pytest

from core.config import SERVICIOS, AppConfig, cambiar_esquema


@pytest.fixture(autouse=True)
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRERIA_CONFIG_DIR", str(tmp_path))


def test_defaults_tienen_seis_servicios_en_http():
    c = AppConfig.defaults()
    assert c.protocolo == "http"
    assert [c.url(k) for k, _, _ in SERVICIOS] == [f"http://localhost:{p}" for _, _, p in SERVICIOS]


def test_cambiar_esquema_conserva_host_y_puerto():
    assert cambiar_esquema("http://34.10.20.30:5002", "https") == "https://34.10.20.30:5002"
    assert cambiar_esquema("https://api.ejemplo.mx", "http") == "http://api.ejemplo.mx"
    assert cambiar_esquema("http://h:5000/base", "https") == "https://h:5000/base"


def test_con_protocolo_reescribe_las_seis_urls():
    c = AppConfig.defaults().con_protocolo("https")
    assert c.protocolo == "https"
    assert all(c.url(k).startswith("https://") for k, _, _ in SERVICIOS)
    assert c.con_protocolo("http").url("pagos") == "http://localhost:5005"


def test_validar_rechaza_protocolo_raro_y_url_mala():
    c = AppConfig.defaults()
    c.protocolo = "ftp"
    assert any("protocolo" in e.lower() for e in c.validar())
    c = AppConfig.defaults()
    c.pedidos_url = "pedidos:5004"
    assert any("Pedidos" in e for e in c.validar())


def test_guardar_y_cargar_conserva_protocolo():
    AppConfig.defaults().con_protocolo("https").save()
    c = AppConfig.load()
    assert c.protocolo == "https" and c.url("users").startswith("https://")


def test_config_vieja_sin_claves_nuevas_carga_con_defaults(tmp_path):
    (tmp_path / "config.json").write_text('{"login_url": "http://h:5000", "books_url": "http://h:5001", '
                                          '"timeout": 5, "health_interval": 30}')
    c = AppConfig.load()
    assert c.login_url == "http://h:5000" and c.users_url == "http://localhost:5002" and c.protocolo == "http"
```

- [ ] **Step 2: Fallan** — `pytest tests/test_config_https.py -q`.
- [ ] **Step 3: Implementar** en `core/config.py`: ampliar `DEFAULTS` con `users_url…pagos_url` y `"protocolo": "http"`; agregar `SERVICIOS`; `cambiar_esquema` con `urllib.parse.urlsplit/urlunsplit`; en `AppConfig`: campos nuevos, `url(clave)` → `getattr(self, f"{clave}_url")`, `con_protocolo` usando `dataclasses.replace`, y `validar()` iterando `SERVICIOS` (mensaje `URL de {nombre}: …`) más `if self.protocolo not in ("http","https"): errores.append("El protocolo debe ser http o https.")`. `load()` ya fusiona con DEFAULTS filtrando claves conocidas, no requiere cambio salvo que `DEFAULTS` crezca.
- [ ] **Step 4: Pasan** y `pytest tests -q` completo (los tests viejos de `test_core.py` siguen verdes).
- [ ] **Step 5: Commit** — `feat(desktop): configuracion con seis URLs y protocolo http/https`.

---

### Task 3: `Libro.id_libro` en el parser XML

**Files:** Modify `apps/desktop_app/core/books_api.py`; Test: agregar a `tests/test_core.py`.

**Interfaces:** `Libro.id_libro: int | None = None` (último campo con default, para no romper constructores posicionales existentes); `a_payload()` **no** lo incluye.

- [ ] **Step 1: Tests**

```python
def test_parsea_id_libro_si_viene():
    xml = b"<library><book isbn='1' id_libro='11'><title>T</title><authors/><publicationYear/><genres/>" \
          b"<price currency='MXN'>1</price><stock>1</stock><format>F</format><images/><concepts/></book></library>"
    assert parsear_libros(xml)[0].id_libro == 11


def test_id_libro_ausente_es_none():
    assert parsear_libros(XML)[0].id_libro is None


def test_payload_no_incluye_id_libro():
    libro = Libro("9", "T", id_libro=5)
    assert "id_libro" not in libro.a_payload()
```
- [ ] **Step 2: Fallan.** **Step 3:** agregar el campo al dataclass (después de `conceptos`) y en `parsear_libros`: `id_libro=int(b.get("id_libro")) if (b.get("id_libro") or "").isdigit() else None`. **Step 4:** suite completa verde. **Step 5:** commit `feat(desktop): parsear id_libro del catalogo`.

---

### Task 4: Cliente REST genérico y wrappers de Users, Authors, Pedidos y Pagos

**Files:** Create `apps/desktop_app/core/rest_api.py`; Test: `apps/desktop_app/tests/test_rest_api.py`.

**Interfaces:**
- Consumes: `core.http.HttpClient.request(metodo, ruta, params=, json_body=, headers=) -> Response`, `ServiceError`, `SesionExpirada`, `mensaje_para_status`.
- Produces:

```python
class RestApi:
    def __init__(self, http, obtener_token): ...
    def llamar(self, metodo, ruta, *, body=None, params=None, publico=False, ok=(200, 201), mensajes=None) -> dict | list
class UsersApi(RestApi):    roles(); listar(); obtener(id); crear(correo, nombre, apellido_paterno, apellido_materno, password, rol); actualizar(id, **campos); cambiar_password(id, nueva, actual=None); cambiar_rol(id, rol); eliminar(id)
class AuthorsApi(RestApi):  listar(); obtener(id); crear(nombre); renombrar(id, nombre); eliminar(id); vincular(id_autor, id_libro); desvincular(id_autor, id_libro)
class PedidosApi(RestApi):  crear(lineas); listar(); obtener(id); cambiar_estado(id, estado); eliminar(id)
class PagosApi(RestApi):    registrar(id_pedido, metodo, monto=None); listar(); obtener(id); reembolsar(id)
```

Reglas de `llamar`: sin token y no `publico` → `SesionExpirada("No hay una sesión iniciada…", status=401)` **sin** hacer la petición; con token envía `Authorization: Bearer`; `publico=True` nunca envía token; 2xx en `ok` → JSON (`{}` si el cuerpo no es JSON); 401 con token → `SesionExpirada`; cualquier otro status → `ServiceError(mensaje del servidor + HTTP n, status=n)` (usa `mensaje_para_status`; un `mensajes[status]` explícito tiene prioridad); 503 → `ServiceError` cuyo mensaje contiene "(HTTP 503)" (ya lo da `mensaje_para_status`). Rutas con `urllib.parse.quote` no hace falta (ids enteros).

- [ ] **Step 1: Tests que fallan**

```python
import json

import pytest

from core.http import ServiceError, SesionExpirada
from core.rest_api import AuthorsApi, PagosApi, PedidosApi, RestApi, UsersApi


class Resp:
    def __init__(self, status=200, datos=None, texto=None):
        self.status_code = status
        self.text = texto if texto is not None else (json.dumps(datos) if datos is not None else "")
        self.content = self.text.encode()

    def json(self):
        return json.loads(self.text)


class FakeHttp:
    base_url = "http://fake"

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def request(self, metodo, ruta, *, params=None, json_body=None, headers=None):
        self.llamadas.append((metodo, ruta, params, json_body, headers))
        return self.respuestas.pop(0)


def api(clase, *respuestas, token="TOK"):
    http = FakeHttp(*respuestas)
    return clase(http, lambda: token), http


def test_envia_bearer_y_devuelve_json():
    a, http = api(UsersApi, Resp(200, [{"id_usuario": 1}]))
    assert a.listar() == [{"id_usuario": 1}]
    assert http.llamadas[0][4] == {"Authorization": "Bearer TOK"}


def test_sin_token_no_hace_peticion():
    a, http = api(PedidosApi, token=None)
    with pytest.raises(SesionExpirada):
        a.listar()
    assert http.llamadas == []


def test_publico_no_envia_token_aunque_exista():
    a, http = api(AuthorsApi, Resp(200, []))
    a.listar()
    assert http.llamadas[0][4] is None


def test_401_con_token_es_sesion_expirada():
    a, _ = api(PagosApi, Resp(401, {"mensaje": "Token revocado"}))
    with pytest.raises(SesionExpirada) as e:
        a.listar()
    assert "Token revocado" in str(e.value)


def test_403_y_409_conservan_el_mensaje_del_servidor():
    a, _ = api(UsersApi, Resp(403, {"mensaje": "Rol insuficiente para esta operacion"}))
    with pytest.raises(ServiceError) as e:
        a.eliminar(3)
    assert e.value.status == 403 and "Rol insuficiente" in str(e.value)
    a, _ = api(PedidosApi, Resp(409, {"mensaje": "Stock insuficiente para el libro 11 (disponible 20, pedido 9999)."}))
    with pytest.raises(ServiceError) as e:
        a.crear([{"id_libro": 11, "cantidad": 9999}])
    assert e.value.status == 409 and "Stock insuficiente" in str(e.value)


def test_503_es_error_de_servicio_no_sesion_expirada():
    a, _ = api(UsersApi, Resp(503, {"mensaje": "Servicio de sesiones no disponible."}))
    with pytest.raises(ServiceError) as e:
        a.listar()
    assert not isinstance(e.value, SesionExpirada) and e.value.status == 503


def test_rutas_y_cuerpos_de_users():
    a, http = api(UsersApi, Resp(201, {"id_usuario": 9}), Resp(200, {}), Resp(200, {}), Resp(200, {}), Resp(200, {}))
    a.crear("a@b.mx", "Ana", "Lo", "Mo", "claveSegura1", "cliente")
    a.actualizar(9, nombre="Nuevo")
    a.cambiar_password(9, "otraClave12", actual="claveSegura1")
    a.cambiar_rol(9, "admin")
    a.eliminar(9)
    m = [(c[0], c[1], c[3]) for c in http.llamadas]
    assert m[0] == ("POST", "/api/users", {"correo": "a@b.mx", "nombre": "Ana", "apellido_paterno": "Lo",
                                           "apellido_materno": "Mo", "password": "claveSegura1", "rol": "cliente"})
    assert m[1] == ("PATCH", "/api/users/9", {"nombre": "Nuevo"})
    assert m[2] == ("PATCH", "/api/users/9/password", {"password_nueva": "otraClave12", "password_actual": "claveSegura1"})
    assert m[3] == ("PATCH", "/api/users/9/rol", {"rol": "admin"})
    assert m[4] == ("DELETE", "/api/users/9", None)


def test_cambiar_password_de_otro_no_manda_actual():
    a, http = api(UsersApi, Resp(200, {}))
    a.cambiar_password(4, "nuevaClave12")
    assert http.llamadas[0][3] == {"password_nueva": "nuevaClave12"}


def test_rutas_authors_pedidos_pagos():
    a, http = api(AuthorsApi, Resp(201, {}), Resp(200, {}), Resp(201, {}), Resp(200, {}), Resp(200, {}))
    a.crear("X"); a.renombrar(2, "Y"); a.vincular(2, 11); a.desvincular(2, 11); a.eliminar(2)
    assert [(c[0], c[1]) for c in http.llamadas] == [
        ("POST", "/api/authors"), ("PATCH", "/api/authors/2"), ("POST", "/api/authors/2/books"),
        ("DELETE", "/api/authors/2/books/11"), ("DELETE", "/api/authors/2")]
    assert http.llamadas[2][3] == {"id_libro": 11}
    p, http = api(PedidosApi, Resp(201, {}), Resp(200, {}), Resp(200, {}))
    p.crear([{"id_libro": 11, "cantidad": 2}]); p.cambiar_estado(1, "cancelado"); p.eliminar(1)
    assert [(c[0], c[1]) for c in http.llamadas] == [
        ("POST", "/api/pedidos"), ("PATCH", "/api/pedidos/1/estado"), ("DELETE", "/api/pedidos/1")]
    assert http.llamadas[0][3] == {"lineas": [{"id_libro": 11, "cantidad": 2}]}
    g, http = api(PagosApi, Resp(201, {}), Resp(200, {}))
    g.registrar(1, "tarjeta"); g.reembolsar(1)
    assert http.llamadas[0][3] == {"id_pedido": 1, "metodo": "tarjeta"}
    g, http = api(PagosApi, Resp(201, {}))
    g.registrar(1, "efectivo", monto=398.5)
    assert http.llamadas[0][3] == {"id_pedido": 1, "metodo": "efectivo", "monto": 398.5}
```
- [ ] **Step 2: Fallan.**
- [ ] **Step 3: Implementar `core/rest_api.py`**

```python
"""Cliente REST generico (JSON + Bearer) y un wrapper delgado por microservicio.
Reglas comunes: sin token no se hace la peticion; 401 con token -> SesionExpirada;
cualquier otro error conserva el mensaje del servidor (403, 409, 503...)."""

from core.http import ServiceError, SesionExpirada, mensaje_para_status


class RestApi:
    def __init__(self, http, obtener_token):
        self.http = http
        self.obtener_token = obtener_token  # se consulta en cada llamada: el token cambia

    def llamar(self, metodo, ruta, *, body=None, params=None, publico=False, ok=(200, 201), mensajes=None):
        token = None if publico else self.obtener_token()
        if not publico and not token:
            raise SesionExpirada("No hay una sesión iniciada. Inicia sesión para usar esta función.",
                                 kind="http", status=401)
        headers = {"Authorization": f"Bearer {token}"} if token else None
        resp = self.http.request(metodo, ruta, params=params, json_body=body, headers=headers)
        if resp.status_code in ok:
            try:
                return resp.json()
            except ValueError:
                return {}
        mensaje = (mensajes or {}).get(resp.status_code) or mensaje_para_status(resp)
        if resp.status_code == 401 and token:
            raise SesionExpirada(mensaje, kind="http", status=401)
        raise ServiceError(mensaje, status=resp.status_code)


class UsersApi(RestApi):
    def roles(self):
        return self.llamar("GET", "/api/roles", publico=True)

    def listar(self):
        return self.llamar("GET", "/api/users")

    def obtener(self, id_usuario):
        return self.llamar("GET", f"/api/users/{id_usuario}")

    def crear(self, correo, nombre, apellido_paterno, apellido_materno, password, rol="cliente"):
        return self.llamar("POST", "/api/users", body={
            "correo": correo, "nombre": nombre, "apellido_paterno": apellido_paterno,
            "apellido_materno": apellido_materno, "password": password, "rol": rol})

    def actualizar(self, id_usuario, **campos):
        return self.llamar("PATCH", f"/api/users/{id_usuario}", body=campos)

    def cambiar_password(self, id_usuario, nueva, actual=None):
        body = {"password_nueva": nueva}
        if actual is not None:
            body["password_actual"] = actual
        return self.llamar("PATCH", f"/api/users/{id_usuario}/password", body=body)

    def cambiar_rol(self, id_usuario, rol):
        return self.llamar("PATCH", f"/api/users/{id_usuario}/rol", body={"rol": rol})

    def eliminar(self, id_usuario):
        return self.llamar("DELETE", f"/api/users/{id_usuario}")


class AuthorsApi(RestApi):
    def listar(self):
        return self.llamar("GET", "/api/authors", publico=True)

    def obtener(self, id_autor):
        return self.llamar("GET", f"/api/authors/{id_autor}", publico=True)

    def crear(self, nombre):
        return self.llamar("POST", "/api/authors", body={"nombre_autor": nombre})

    def renombrar(self, id_autor, nombre):
        return self.llamar("PATCH", f"/api/authors/{id_autor}", body={"nombre_autor": nombre})

    def eliminar(self, id_autor):
        return self.llamar("DELETE", f"/api/authors/{id_autor}")

    def vincular(self, id_autor, id_libro):
        return self.llamar("POST", f"/api/authors/{id_autor}/books", body={"id_libro": id_libro})

    def desvincular(self, id_autor, id_libro):
        return self.llamar("DELETE", f"/api/authors/{id_autor}/books/{id_libro}")


class PedidosApi(RestApi):
    def crear(self, lineas):
        return self.llamar("POST", "/api/pedidos", body={"lineas": lineas})

    def listar(self):
        return self.llamar("GET", "/api/pedidos")

    def obtener(self, id_pedido):
        return self.llamar("GET", f"/api/pedidos/{id_pedido}")

    def cambiar_estado(self, id_pedido, estado):
        return self.llamar("PATCH", f"/api/pedidos/{id_pedido}/estado", body={"estado": estado})

    def eliminar(self, id_pedido):
        return self.llamar("DELETE", f"/api/pedidos/{id_pedido}")


class PagosApi(RestApi):
    def registrar(self, id_pedido, metodo, monto=None):
        body = {"id_pedido": id_pedido, "metodo": metodo}
        if monto is not None:
            body["monto"] = monto
        return self.llamar("POST", "/api/pagos", body=body)

    def listar(self):
        return self.llamar("GET", "/api/pagos")

    def obtener(self, id_pago):
        return self.llamar("GET", f"/api/pagos/{id_pago}")

    def reembolsar(self, id_pago):
        return self.llamar("DELETE", f"/api/pagos/{id_pago}")
```
- [ ] **Step 4:** `pytest tests -q` verde. **Step 5:** commit `feat(desktop): cliente REST generico y APIs de users, authors, pedidos y pagos`.

---

### Task 5: Health genérico de los seis servicios (con Redis)

**Files:** Modify `apps/desktop_app/core/health.py`; Test: `apps/desktop_app/tests/test_health.py`; ajustar los tests existentes de `comprobar_libros` en `tests/test_core.py` al nuevo contrato.

**Interfaces:**
- `EstadoServicio` gana `redis: str | None = None` (`"ok"`, `"error"` o `None` si el servicio no lo reporta).
- `comprobar_servicio(http, nombre) -> EstadoServicio`: `GET /health?format=json` (login ignora el parámetro excepto para elegir JSON; el resto lo ignora). Regla: 200 + JSON con `db == "ok"` → `OK`; 503 o `db != "ok"` → `DEGRADADO`; JSON inválido/otra cosa → `DEGRADADO` ("¿la URL apunta al microservicio de X?"); `ServiceError` → `CAIDO`. `redis` se copia de `datos.get("redis")` cuando es `"ok"` o `"error"`.
- `comprobar_login` y `comprobar_libros` se conservan como alias (`lambda http: comprobar_servicio(http, "login")`, etc.) por compatibilidad con `config_panel`/`main_window` hasta la Task 11.

- [ ] **Step 1: Tests**

```python
import json

from core.health import CAIDO, DEGRADADO, OK, comprobar_servicio
from core.http import ServiceError


class R:
    def __init__(self, status, datos=None, texto=None):
        self.status_code = status
        self.text = texto if texto is not None else json.dumps(datos)

    def json(self):
        return json.loads(self.text)


class H:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc
        self.llamadas = []

    def request(self, metodo, ruta, **kw):
        self.llamadas.append((metodo, ruta, kw.get("params")))
        if self.exc:
            raise self.exc
        return self.resp


def test_ok_con_db_y_redis():
    h = H(R(200, {"servicio": "users", "status": "ok", "db": "ok", "redis": "ok"}))
    e = comprobar_servicio(h, "Usuarios")
    assert e.estado == OK and e.redis == "ok" and h.llamadas[0][1] == "/health"


def test_redis_error_no_baja_el_semaforo():
    e = comprobar_servicio(H(R(200, {"db": "ok", "redis": "error"})), "Pedidos")
    assert e.estado == OK and e.redis == "error"


def test_bd_caida_es_degradado():
    e = comprobar_servicio(H(R(503, {"db": "error", "redis": "ok"})), "Pagos")
    assert e.estado == DEGRADADO


def test_respuesta_ajena_es_degradado_con_pista():
    e = comprobar_servicio(H(R(200, texto="<html>AirPlay</html>")), "Autores")
    assert e.estado == DEGRADADO and "Autores" in e.detalle


def test_sin_conexion_es_caido():
    e = comprobar_servicio(H(exc=ServiceError("sin conexion", kind="conexion")), "Login")
    assert e.estado == CAIDO and e.redis is None
```
- [ ] **Step 2: Fallan. Step 3: Implementar** (reemplazar las dos funciones viejas por `comprobar_servicio` + alias; conservar la docstring actualizada: ahora el servicio de libros sí tiene `/health`). Ajustar en `tests/test_core.py` los tests de `comprobar_libros`/`comprobar_login` para el nuevo endpoint (`/health`) o eliminarlos si quedan duplicados por `test_health.py`. **Step 4:** suite verde. **Step 5:** commit `feat(desktop): semaforo generico por /health con estado de Redis`.

---

### Task 6: Base de las pestañas CRUD, plomería de rol/usuario y pruebas de UI

Infraestructura que usan las Tasks 7-10. Incluye el cableado en `main.py` y `MainWindow` (sin pestañas nuevas todavía).

**Files:**
- Create: `apps/desktop_app/ui/crud_base.py`, `apps/desktop_app/tests/conftest.py`, `apps/desktop_app/tests/test_ui_smoke.py`
- Modify: `apps/desktop_app/main.py`, `apps/desktop_app/ui/main_window.py`

**Interfaces:**
- Produce en `Controlador` (main.py): `http_users/http_authors/http_pedidos/http_pagos`, `self.users/authors/pedidos/pagos` (`*Api` con `lambda: self.token_sesion`), `self.role_id: int | None`, `self.user_id: int | None`, `es_admin() -> bool` (`role_id == 1`). `_construir_clientes` crea los seis `HttpClient` con `config.url(clave)`. `MainWindow._sesion_ok` y el refresh actualizan `c.role_id = datos.get("role_id")` y `c.user_id = datos.get("id_usuario")`, y llaman `self.refrescar_permisos()` que recorre las pestañas CRUD. Al cerrar sesión / invitado: `role_id = user_id = None`.
- `ui.crud_base.CrudTab(QWidget)`:

```python
class CrudTab(QWidget):
    requiere_sesion = True          # False en Authors (lectura publica)
    def __init__(self, controlador, columnas: list[str]): ...
    # tabla
    def llenar_tabla(self, filas: list[list], ids: list) -> None
    def id_seleccionado(self) -> int | None
    seleccion_cambio = Signal(object)        # id o None
    # llamadas
    def llamar(self, etiqueta: str, funcion, exito, *, botones=None) -> None
    # mensajes
    mensaje: QLabel;  def ok(self, texto); def error(self, texto)
    # permisos
    def es_admin(self) -> bool;  def hay_sesion(self) -> bool
    def solo_admin(self, *widgets) -> None      # registra widgets que se deshabilitan sin ser admin
    def refrescar_permisos(self) -> None        # recalcula enabled/tooltip y muestra el aviso de invitado
    def al_activar(self) -> None                # hook: la ventana lo llama al mostrar la pestaña (recarga)
```
Comportamiento de `llamar(etiqueta, funcion, exito)`: deshabilita los botones registrados, muestra "Enviando {etiqueta}…", corre `ejecutar(funcion, ...)`; en éxito rehabilita y llama `exito(resultado)`; en `SesionExpirada` intenta `ventana.renovar_token(ok=lambda: self.ok("Tu sesión se renovó automáticamente. Repite la operación."), fallo=lambda: ventana.sesion_requerida(str(exc)))` (mismo patrón que `AdminTab._sesion_expirada`); en cualquier otro `ServiceError` muestra `"{etiqueta} falló: {texto_error(exc)}"` sin cerrar sesión (cubre 403, 409, 503). Invitado en una pestaña con `requiere_sesion`: la tabla y el formulario se deshabilitan y `mensaje` dice "Inicia sesión para usar esta sección" con un botón "Iniciar sesión" (llama `ventana.iniciar_sesion()`).

- [ ] **Step 1: `tests/conftest.py`** — fixtures compartidas:

```python
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeVentana:
    invitado = False

    def __init__(self):
        self.pidio_login = 0
        self.renovaciones = 0

    def iniciar_sesion(self):
        self.pidio_login += 1

    def sesion_requerida(self, motivo):
        self.motivo = motivo

    def renovar_token(self, ok, fallo):
        self.renovaciones += 1
        ok()


class FakeControlador:
    """Controlador minimo para las pestañas: APIs falsas que registran llamadas."""

    def __init__(self, role_id=1, user_id=1, token="TOK"):
        self.role_id, self.user_id, self.token_sesion = role_id, user_id, token
        self.ventana = FakeVentana()
        self.llamadas = []

    def es_admin(self):
        return self.role_id == 1


@pytest.fixture
def ctrl(qapp):
    return FakeControlador()


@pytest.fixture
def ctrl_cliente(qapp):
    return FakeControlador(role_id=2, user_id=7)


@pytest.fixture
def ctrl_invitado(qapp):
    c = FakeControlador(role_id=None, user_id=None, token=None)
    c.ventana.invitado = True
    return c


def esperar(qapp, condicion, ms=2000):
    """Procesa eventos hasta que condicion() sea verdadera (los hilos del pool entregan por señales)."""
    import time
    fin = time.monotonic() + ms / 1000
    while time.monotonic() < fin:
        qapp.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return False
```
- [ ] **Step 2: Tests de `CrudTab`** en `tests/test_ui_smoke.py` (sección base):

```python
from conftest import esperar
from core.http import ServiceError, SesionExpirada
from ui.crud_base import CrudTab


class Demo(CrudTab):
    def __init__(self, c):
        super().__init__(c, ["ID", "Nombre"])


def test_llenar_tabla_y_seleccion(ctrl, qapp):
    t = Demo(ctrl)
    t.llenar_tabla([["1", "A"], ["2", "B"]], [1, 2])
    t.tabla.selectRow(1)
    assert t.id_seleccionado() == 2


def test_llamar_exito_ejecuta_callback(ctrl, qapp):
    t, vistos = Demo(ctrl), []
    t.llamar("GET", lambda: 41 + 1, vistos.append)
    assert esperar(qapp, lambda: vistos == [42])


def test_llamar_error_de_servicio_muestra_mensaje_sin_cerrar_sesion(ctrl, qapp):
    t = Demo(ctrl)

    def falla():
        raise ServiceError("Stock insuficiente (HTTP 409)", status=409)

    t.llamar("POST", falla, lambda _: None)
    assert esperar(qapp, lambda: "Stock insuficiente" in t.mensaje.text())
    assert not hasattr(ctrl.ventana, "motivo")


def test_llamar_sesion_expirada_intenta_renovar(ctrl, qapp):
    t = Demo(ctrl)

    def vence():
        raise SesionExpirada("expiro", status=401)

    t.llamar("GET", vence, lambda _: None)
    assert esperar(qapp, lambda: ctrl.ventana.renovaciones == 1)
    assert "renovó" in t.mensaje.text()


def test_solo_admin_deshabilita_para_cliente(ctrl_cliente, qapp):
    t = Demo(ctrl_cliente)
    from PySide6.QtWidgets import QPushButton
    b = QPushButton("Borrar")
    t.solo_admin(b)
    t.refrescar_permisos()
    assert not b.isEnabled() and "administrador" in b.toolTip().lower()


def test_admin_habilita(ctrl, qapp):
    t = Demo(ctrl)
    from PySide6.QtWidgets import QPushButton
    b = QPushButton("Borrar")
    t.solo_admin(b)
    t.refrescar_permisos()
    assert b.isEnabled()


def test_invitado_en_seccion_con_sesion_ve_aviso(ctrl_invitado, qapp):
    t = Demo(ctrl_invitado)
    t.refrescar_permisos()
    assert "Inicia sesión" in t.mensaje.text() and not t.tabla.isEnabled()
```
- [ ] **Step 3: Fallan. Step 4: Implementar `ui/crud_base.py`** con el comportamiento descrito (tabla `QTableWidget` de solo lectura, selección de fila completa, una sola fila; `mensaje` `QLabel(wordWrap=True)`; botón de login para invitado; usar `poner_mensaje` de `ui.common`). `es_admin()` delega en `self.c.es_admin()`; `hay_sesion()` = `bool(self.c.token_sesion)`.
- [ ] **Step 5: Cableado** (`main.py`): `import` de las cuatro APIs; en `_construir_clientes` crear los 6 `HttpClient("Usuarios", config.url("users"), …)` etc. y las APIs; `role_id = user_id = None` en `__init__`; `es_admin()`; poner en `None` en `mostrar_invitado`/`sesion_cerrada`. En `MainWindow`: en `_sesion_ok` y en los dos `ok` de refresh/extend, `self._guardar_identidad(datos)`; `refrescar_permisos()` recorre `self.crud_tabs` (lista vacía por ahora; las Tasks 7-10 la llenan). Test de humo: `MainWindow` no se instancia aquí (requiere red); se prueba en Task 11.
- [ ] **Step 6:** `QT_QPA_PLATFORM=offscreen pytest tests -q` verde. **Step 7:** commit `feat(desktop): base CrudTab, rol y usuario de la sesion y cliente de los seis servicios`.

---

### Task 7: Pestaña Usuarios (`ui/users_tab.py`)

**Files:** Create `apps/desktop_app/ui/users_tab.py`; Test: sección en `tests/test_ui_smoke.py`.

**Interfaces:** `class UsersTab(CrudTab)` con `UsersTab(controlador)`; usa `controlador.users` (`UsersApi`). Columnas: `ID, Correo, Nombre, Apellido paterno, Apellido materno, Rol`.

**Comportamiento:**
- `al_activar()` y botón **Recargar**: admin → `users.listar()`; cliente → `[users.obtener(c.user_id)]` (un solo renglón, el propio).
- Formulario: `correo, nombre, apellido_paterno, apellido_materno` (QLineEdit), `password` (QLineEdit, modo Password), `password_actual` (solo visible/relevante cuando el usuario edita **su propia** cuenta), `rol` (QComboBox `cliente`/`admin`).
- Seleccionar un renglón carga el formulario (no carga contraseñas).
- Botones: **Crear** (solo admin; exige correo, nombre, apellidos y password ≥ 8 → `users.crear`), **Guardar cambios** (`users.actualizar(id, correo=…, nombre=…, apellido_paterno=…, apellido_materno=…)` — PATCH con los 4 campos del formulario; propio o admin), **Cambiar contraseña** (nueva ≥ 8; si el id seleccionado es el propio exige `password_actual`; si es de otro y es admin no lo manda), **Cambiar rol** (solo admin → `users.cambiar_rol`), **Eliminar** (solo admin, con `QMessageBox.question`), **Limpiar**.
- `solo_admin(crear, cambiar_rol, eliminar, rol)`. Validaciones locales muestran `self.error(...)` sin llamar a la red.
- Tras crear/guardar/eliminar: `ok("…")` y recargar la tabla.

- [ ] **Step 1: Tests** (con `FakeUsers` que registra llamadas y devuelve datos):

```python
class FakeUsers:
    def __init__(self):
        self.calls = []
        self.datos = [
            {"id_usuario": 1, "correo": "a@x.mx", "nombre": "Ana", "apellido_paterno": "L", "apellido_materno": "M",
             "rol": "admin", "role_id": 1},
            {"id_usuario": 7, "correo": "c@x.mx", "nombre": "Cli", "apellido_paterno": "P", "apellido_materno": "Q",
             "rol": "cliente", "role_id": 2}]

    def listar(self):
        self.calls.append(("listar",)); return self.datos

    def obtener(self, i):
        self.calls.append(("obtener", i)); return next(u for u in self.datos if u["id_usuario"] == i)

    def crear(self, *a):
        self.calls.append(("crear",) + a); return {"id_usuario": 9}

    def actualizar(self, i, **c):
        self.calls.append(("actualizar", i, c)); return {}

    def cambiar_password(self, i, nueva, actual=None):
        self.calls.append(("password", i, nueva, actual)); return {}

    def cambiar_rol(self, i, rol):
        self.calls.append(("rol", i, rol)); return {}

    def eliminar(self, i):
        self.calls.append(("eliminar", i)); return {}


def test_admin_lista_todos(ctrl, qapp):
    from ui.users_tab import UsersTab
    ctrl.users = FakeUsers()
    t = UsersTab(ctrl); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 2)


def test_cliente_ve_solo_su_renglon_y_botones_admin_deshabilitados(ctrl_cliente, qapp):
    from ui.users_tab import UsersTab
    ctrl_cliente.users = FakeUsers()
    t = UsersTab(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    assert ctrl_cliente.users.calls[0] == ("obtener", 7)
    assert not t.btn_crear.isEnabled() and not t.btn_eliminar.isEnabled() and not t.btn_rol.isEnabled()


def test_crear_valida_password_corta_sin_llamar_a_la_red(ctrl, qapp):
    from ui.users_tab import UsersTab
    ctrl.users = FakeUsers()
    t = UsersTab(ctrl)
    t.correo.setText("n@x.mx"); t.nombre.setText("N"); t.ap_paterno.setText("A"); t.ap_materno.setText("B")
    t.password.setText("corta")
    t.btn_crear.click()
    assert "8 caracteres" in t.mensaje.text() and not [c for c in ctrl.users.calls if c[0] == "crear"]


def test_crear_envia_los_campos(ctrl, qapp):
    from ui.users_tab import UsersTab
    ctrl.users = FakeUsers()
    t = UsersTab(ctrl)
    t.correo.setText("n@x.mx"); t.nombre.setText("N"); t.ap_paterno.setText("A"); t.ap_materno.setText("B")
    t.password.setText("claveSegura1"); t.rol.setCurrentText("cliente")
    t.btn_crear.click()
    assert esperar(qapp, lambda: ("crear", "n@x.mx", "N", "A", "B", "claveSegura1", "cliente") in ctrl.users.calls)


def test_cambiar_password_propio_exige_actual(ctrl_cliente, qapp):
    from ui.users_tab import UsersTab
    ctrl_cliente.users = FakeUsers()
    t = UsersTab(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    t.tabla.selectRow(0)
    t.password.setText("nuevaClave12")
    t.btn_password.click()
    assert "contraseña actual" in t.mensaje.text().lower()
    t.password_actual.setText("viejaClave12")
    t.btn_password.click()
    assert esperar(qapp, lambda: ("password", 7, "nuevaClave12", "viejaClave12") in ctrl_cliente.users.calls)
```
- [ ] **Step 2-4:** fallan → implementar → verde. **Step 5:** registrar la pestaña en `MainWindow.crud_tabs` se hace en Task 11; aquí solo el módulo. Commit `feat(desktop): pestana CRUD de usuarios`.

---

### Task 8: Pestaña Autores (`ui/authors_tab.py`)

**Files:** Create `apps/desktop_app/ui/authors_tab.py`; Test: sección en `tests/test_ui_smoke.py`.

**Interfaces:** `class AuthorsTab(CrudTab)` con `requiere_sesion = False` (la lectura es pública); usa `controlador.authors` (`AuthorsApi`) y `controlador.libros` (`BooksApi`, solo `listar()` para el combo de libros). Columnas: `ID, Autor`.

**Comportamiento:**
- `al_activar()`/**Recargar**: `authors.listar()` (sin token, funciona como invitado).
- Seleccionar un autor: `authors.obtener(id)` → llena `nombre` y la lista de sus libros (`QListWidget`, texto `titulo (isbn)`, data = `id_libro`; el JSON de `GET /api/authors/{id}` trae `libros: [{id_libro, isbn?, titulo?}]`, usar las claves que existan y mostrar `Libro {id_libro}` si no hay título).
- Formulario: `nombre` (QLineEdit); combo `libro` poblado con `libros.listar()` (texto `titulo — isbn`, data `id_libro`; ignorar libros con `id_libro is None`).
- Botones (todos **solo admin**, deshabilitados para cliente/invitado): **Crear**, **Renombrar**, **Eliminar** (confirmación; el 409 "tiene libros asociados" se muestra tal cual), **Vincular libro** (`authors.vincular(id, id_libro)`), **Desvincular libro** (libro seleccionado en la lista del autor).
- `nombre` obligatorio, máximo 150 caracteres (validación local).

- [ ] **Step 1: Tests**

```python
class FakeAuthors:
    def __init__(self):
        self.calls = []

    def listar(self):
        self.calls.append(("listar",)); return [{"id_autor": 2, "nombre_autor": "Borges"}]

    def obtener(self, i):
        self.calls.append(("obtener", i))
        return {"id_autor": i, "nombre_autor": "Borges", "libros": [{"id_libro": 11, "titulo": "El aleph"}]}

    def crear(self, n):
        self.calls.append(("crear", n)); return {"id_autor": 3}

    def renombrar(self, i, n):
        self.calls.append(("renombrar", i, n)); return {}

    def eliminar(self, i):
        self.calls.append(("eliminar", i)); return {}

    def vincular(self, a, l):
        self.calls.append(("vincular", a, l)); return {}

    def desvincular(self, a, l):
        self.calls.append(("desvincular", a, l)); return {}


class FakeLibros:
    def listar(self):
        from core.books_api import Libro
        return [Libro("978", "El aleph", id_libro=11), Libro("979", "Sin id")]


def _tab(c):
    from ui.authors_tab import AuthorsTab
    c.authors, c.libros = FakeAuthors(), FakeLibros()
    return AuthorsTab(c)


def test_invitado_puede_listar_autores(ctrl_invitado, qapp):
    t = _tab(ctrl_invitado); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    assert "Inicia sesión" not in t.mensaje.text()
    assert not t.btn_crear.isEnabled()


def test_seleccionar_autor_muestra_sus_libros(ctrl, qapp):
    t = _tab(ctrl); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    t.tabla.selectRow(0)
    assert esperar(qapp, lambda: t.lista_libros.count() == 1)
    assert t.nombre.text() == "Borges"


def test_combo_ignora_libros_sin_id(ctrl, qapp):
    t = _tab(ctrl); t.al_activar()
    assert esperar(qapp, lambda: t.combo_libro.count() == 1)


def test_vincular_envia_ids(ctrl, qapp):
    t = _tab(ctrl); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1 and t.combo_libro.count() == 1)
    t.tabla.selectRow(0)
    assert esperar(qapp, lambda: t.lista_libros.count() == 1)
    t.btn_vincular.click()
    assert esperar(qapp, lambda: ("vincular", 2, 11) in ctrl.authors.calls)


def test_nombre_vacio_o_largo_no_llama_a_la_red(ctrl, qapp):
    t = _tab(ctrl)
    t.btn_crear.click()
    t.nombre.setText("x" * 151); t.btn_crear.click()
    assert not [c for c in ctrl.authors.calls if c[0] == "crear"]
```
- [ ] **Step 2-4** fallan → implementar → verde. **Step 5:** commit `feat(desktop): pestana CRUD de autores`.

---

### Task 9: Pestaña Pedidos (`ui/pedidos_tab.py`)

**Files:** Create `apps/desktop_app/ui/pedidos_tab.py`; Test: sección en `tests/test_ui_smoke.py`.

**Interfaces:** `class PedidosTab(CrudTab)`; usa `controlador.pedidos` (`PedidosApi`) y `controlador.libros` (`listar()`). Columnas: `ID, Fecha, Estado, Total, Cuenta`. Emite `pedido_cambio = Signal()` cuando crea/cambia/elimina (la ventana lo conecta a `PagosTab.al_activar` y al refresco del catálogo, porque el stock cambia).

**Comportamiento:**
- **Recargar**: `pedidos.listar()` (admin ve todos, cliente los suyos; el servidor decide).
- **Nuevo pedido** (grupo): combo de libros (`titulo — isbn (stock N)`, data `id_libro`, solo libros con id), `QSpinBox` cantidad (1–9999), botón **Agregar línea**, tabla de líneas (Libro, Cantidad, Quitar), botón **Crear pedido** → `pedidos.crear([{"id_libro":…, "cantidad":…}])`. Sin líneas: error local "Agrega al menos una línea". Líneas repetidas del mismo libro se acumulan en la tabla.
- **Detalle** del renglón seleccionado: `pedidos.obtener(id)` → tabla/texto de líneas con precio unitario y total.
- Acciones sobre el seleccionado: **Cancelar pedido** (`cambiar_estado(id, "cancelado")`, dueño o admin), **Marcar enviado** (solo admin, `"enviado"`), **Eliminar** (solo admin, confirma; solo cancelados — el 409 se muestra tal cual).
- El 409 de stock insuficiente se muestra con el texto del servidor.
- Tras cualquier cambio: recargar tabla y emitir `pedido_cambio`.

- [ ] **Step 1: Tests**

```python
class FakePedidos:
    def __init__(self):
        self.calls = []

    def listar(self):
        self.calls.append(("listar",))
        return [{"id_pedido": 1, "fecha_creacion": "2026-10-09T16:21:17", "estado": "pendiente",
                 "total": 598.5, "id_cuenta": 7}]

    def obtener(self, i):
        self.calls.append(("obtener", i))
        return {"id_pedido": i, "estado": "pendiente", "total": 598.5, "id_cuenta": 7,
                "lineas": [{"id_libro": 11, "isbn": "978", "titulo": "El aleph", "cantidad": 3,
                            "precio_unitario": 199.5}]}

    def crear(self, lineas):
        self.calls.append(("crear", lineas)); return {"id_pedido": 2}

    def cambiar_estado(self, i, e):
        self.calls.append(("estado", i, e)); return {}

    def eliminar(self, i):
        self.calls.append(("eliminar", i)); return {}


def _tabp(c):
    from ui.pedidos_tab import PedidosTab
    c.pedidos, c.libros = FakePedidos(), FakeLibros()
    return PedidosTab(c)


def test_invitado_ve_aviso_de_sesion(ctrl_invitado, qapp):
    t = _tabp(ctrl_invitado); t.refrescar_permisos()
    assert "Inicia sesión" in t.mensaje.text() and not t.btn_crear.isEnabled()


def test_crear_pedido_acumula_lineas_repetidas(ctrl_cliente, qapp):
    t = _tabp(ctrl_cliente)
    assert esperar(qapp, lambda: t.combo_libro.count() == 1)
    t.cantidad.setValue(2); t.btn_agregar.click()
    t.cantidad.setValue(3); t.btn_agregar.click()
    assert t.tabla_lineas.rowCount() == 1
    t.btn_crear.click()
    assert esperar(qapp, lambda: ("crear", [{"id_libro": 11, "cantidad": 5}]) in ctrl_cliente.pedidos.calls)


def test_crear_sin_lineas_no_llama_a_la_red(ctrl_cliente, qapp):
    t = _tabp(ctrl_cliente)
    t.btn_crear.click()
    assert "al menos una línea" in t.mensaje.text() and not [c for c in ctrl_cliente.pedidos.calls if c[0] == "crear"]


def test_cliente_no_puede_enviar_ni_eliminar(ctrl_cliente, qapp):
    t = _tabp(ctrl_cliente); t.refrescar_permisos()
    assert not t.btn_enviar.isEnabled() and not t.btn_eliminar.isEnabled() and t.btn_cancelar.isEnabled()


def test_cancelar_envia_estado_cancelado_y_emite_senal(ctrl_cliente, qapp):
    t = _tabp(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    vistos = []
    t.pedido_cambio.connect(lambda: vistos.append(1))
    t.tabla.selectRow(0)
    t.btn_cancelar.click()
    assert esperar(qapp, lambda: ("estado", 1, "cancelado") in ctrl_cliente.pedidos.calls and vistos)
```
- [ ] **Step 2-4** → implementar. **Step 5:** commit `feat(desktop): pestana CRUD de pedidos con lineas`.

---

### Task 10: Pestaña Pagos (`ui/pagos_tab.py`)

**Files:** Create `apps/desktop_app/ui/pagos_tab.py`; Test: sección en `tests/test_ui_smoke.py`.

**Interfaces:** `class PagosTab(CrudTab)`; usa `controlador.pagos` (`PagosApi`) y `controlador.pedidos` (`listar()` para el combo). Columnas: `ID pago, Pedido, Método, Monto, Fecha`. Emite `pago_cambio = Signal()` (la ventana lo conecta a la recarga de Pedidos).

**Comportamiento:**
- **Recargar**: `pagos.listar()`; además repuebla el combo de pedidos con los de `estado == "pendiente"` (`#id — total $X`, data `id_pedido`).
- **Registrar pago**: combo pedido, combo método (`tarjeta`, `transferencia`, `efectivo`), `monto` opcional (`QLineEdit`, vacío = el servidor usa el total; si se escribe debe ser número > 0 con "," o "." decimal) → `pagos.registrar(id_pedido, metodo, monto)`. Sin pedidos pendientes: botón deshabilitado y texto "No hay pedidos pendientes".
- Seleccionar un pago: `pagos.obtener(id)` y mostrar detalle.
- **Reembolsar** (solo admin, confirma) → `pagos.reembolsar(id)`; el 409 "ya enviado" se muestra tal cual.
- Tras pagar/reembolsar: recargar y emitir `pago_cambio`.

- [ ] **Step 1: Tests**

```python
class FakePagos:
    def __init__(self):
        self.calls = []

    def listar(self):
        self.calls.append(("listar",))
        return [{"id_pago": 1, "id_pedido": 1, "metodo": "tarjeta", "monto": 598.5,
                 "fecha_pago": "2026-10-09T16:21:18", "id_cuenta": 7}]

    def obtener(self, i):
        self.calls.append(("obtener", i)); return self.listar()[0]

    def registrar(self, p, m, monto=None):
        self.calls.append(("registrar", p, m, monto)); return {"id_pago": 2}

    def reembolsar(self, i):
        self.calls.append(("reembolsar", i)); return {}


class FakePedidosParaPagos:
    def listar(self):
        return [{"id_pedido": 4, "estado": "pendiente", "total": 100.0},
                {"id_pedido": 5, "estado": "enviado", "total": 50.0}]


def _tabg(c):
    from ui.pagos_tab import PagosTab
    c.pagos, c.pedidos = FakePagos(), FakePedidosParaPagos()
    return PagosTab(c)


def test_combo_solo_pedidos_pendientes(ctrl_cliente, qapp):
    t = _tabg(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.combo_pedido.count() == 1)
    assert t.combo_pedido.currentData() == 4


def test_registrar_sin_monto_no_lo_envia(ctrl_cliente, qapp):
    t = _tabg(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.combo_pedido.count() == 1)
    t.combo_metodo.setCurrentText("efectivo"); t.btn_pagar.click()
    assert esperar(qapp, lambda: ("registrar", 4, "efectivo", None) in ctrl_cliente.pagos.calls)


def test_monto_invalido_no_llama_a_la_red(ctrl_cliente, qapp):
    t = _tabg(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.combo_pedido.count() == 1)
    t.monto.setText("abc"); t.btn_pagar.click()
    assert "monto" in t.mensaje.text().lower() and not [c for c in ctrl_cliente.pagos.calls if c[0] == "registrar"]


def test_monto_con_coma_decimal(ctrl_cliente, qapp):
    t = _tabg(ctrl_cliente); t.al_activar()
    assert esperar(qapp, lambda: t.combo_pedido.count() == 1)
    t.monto.setText("100,50"); t.btn_pagar.click()
    assert esperar(qapp, lambda: ("registrar", 4, "tarjeta", 100.5) in ctrl_cliente.pagos.calls)


def test_reembolsar_solo_admin(ctrl_cliente, ctrl, qapp):
    assert not _tabg(ctrl_cliente).btn_reembolsar.isEnabled() or True  # se evalua tras refrescar_permisos
    t = _tabg(ctrl_cliente); t.refrescar_permisos()
    assert not t.btn_reembolsar.isEnabled()
    t2 = _tabg(ctrl); t2.refrescar_permisos()
    assert t2.btn_reembolsar.isEnabled()
```
(El primer `assert … or True` de `test_reembolsar_solo_admin` es ruido: el implementador debe quitarlo al transcribir.)
- [ ] **Step 2-4** → implementar. **Step 5:** commit `feat(desktop): pestana CRUD de pagos`.

---

### Task 11: Semáforos de los seis servicios, configuración https y ensamblado de la ventana

**Files:** Modify `apps/desktop_app/ui/config_panel.py`, `apps/desktop_app/ui/main_window.py`, `apps/desktop_app/ui/common.py` (enmascarar `password_actual`/`password_nueva`), `apps/desktop_app/main.py` (pasar config completa); Test: secciones en `tests/test_ui_smoke.py`.

**Comportamiento requerido:**
1. **ConfigPanel**: seis `QLineEdit` (Login, Libros, Usuarios, Autores, Pedidos, Pagos) con su semáforo/texto de prueba cada uno; **radio buttons** `http` (marcado por defecto) y `https` en un grupo "Protocolo"; al cambiar el radio se reescriben **en el formulario** las seis URLs con `cambiar_esquema` (host/puerto intactos) y una nota "https requiere que el servidor tenga certificado; con http el tráfico no va cifrado"; **Probar conexión** prueba las seis con `comprobar_servicio`; **Guardar** valida con `AppConfig.validar()`, persiste (incluye `protocolo`) y emite `guardada`; **Restaurar** vuelve a los defaults (http). Si el usuario edita a mano una URL con otro esquema que el radio, el radio no se toca pero Guardar acepta las URLs tal cual (el campo `protocolo` refleja el radio).
2. **StatusTab**: seis `TarjetaEstado` en rejilla 3×2 (Login, Libros, Usuarios, Autores, Pedidos, Pagos) con semáforo, texto, detalle y línea **"Redis: ok/error/—"**; un resumen "Redis compartido": 🟢 si todos los que responden reportan `ok`, 🟡 si alguno reporta `error`, ⚪ si ninguno responde. Barra de estado: seis mini-semáforos con etiqueta corta.
3. **MainWindow**: pestañas nuevas en este orden: Catálogo, Administración de libros, **Usuarios, Autores, Pedidos, Pagos**, Sesión y perfil, Estado, Configuración. `self.crud_tabs = [users, authors, pedidos, pagos]`; `refrescar_permisos()` los recorre; al cambiar de pestaña se llama `al_activar()` de la nueva (carga datos). Conexiones: `pedidos.pedido_cambio → pagos.al_activar` y `catalogo.recargar`; `pagos.pago_cambio → pedidos.al_activar`; `admin.catalogo_cambio → catalogo.recargar` (ya existe). `comprobar_salud` ahora comprueba los seis con `comprobar_servicio` en un solo hilo (puede ser en serie; son llamadas con timeout corto).
4. **Refresh sin cierre falso**: en `_intentar_refresh`, si `refrescar` falla con `ServiceError` cuyo `status` es 401 (`SesionExpirada`) o 403 → cierra sesión como hoy; si falla por conexión/timeout/503 → **no** cierra: `poner_mensaje(..., "No se pudo renovar la sesión (servicio no disponible). Se reintentará.", error=True)`.
5. `ui/common.RegistroHttpWidget.agregar` enmascara también `password_actual` y `password_nueva` (hoy solo `password`).
6. `Controlador.aplicar_config` reconstruye los seis clientes (ya lo hace `_construir_clientes`) y el `MainWindow` recarga las pestañas visibles.

- [ ] **Step 1: Tests**

```python
def test_radio_https_reescribe_las_seis_urls(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRERIA_CONFIG_DIR", str(tmp_path))
    from core.config import SERVICIOS, AppConfig
    from ui.config_panel import ConfigPanel
    p = ConfigPanel(AppConfig.defaults())
    assert p.radio_http.isChecked()
    p.radio_https.setChecked(True)
    assert all(p.campos[k].text().startswith("https://") for k, _, _ in SERVICIOS)
    p.radio_http.setChecked(True)
    assert p.campos["pagos"].text() == "http://localhost:5005"


def test_guardar_persiste_protocolo_https(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRERIA_CONFIG_DIR", str(tmp_path))
    from core.config import AppConfig
    from ui.config_panel import ConfigPanel
    p = ConfigPanel(AppConfig.defaults())
    p.radio_https.setChecked(True)
    p.guardar()
    assert AppConfig.load().protocolo == "https"


def test_password_se_enmascara_en_el_registro(qapp):
    from ui.common import RegistroHttp, RegistroHttpWidget
    reg = RegistroHttp(); w = RegistroHttpWidget(reg)
    w.agregar({"servicio": "Usuarios", "metodo": "PATCH", "url": "http://h/api/users/1/password", "params": None,
               "body": {"password_nueva": "secreta12", "password_actual": "vieja1234"}, "status": 200, "ms": 5})
    texto = w.texto.toPlainText()
    assert "secreta12" not in texto and "vieja1234" not in texto


def test_tarjeta_estado_muestra_redis(qapp):
    from datetime import datetime
    from core.health import OK, EstadoServicio
    from ui.main_window import TarjetaEstado
    t = TarjetaEstado("Usuarios")
    t.mostrar(EstadoServicio(OK, "Servicio y base de datos funcionando.", datetime.now(), redis="error"), "http://h:5002")
    assert "Redis: error" in t.redis.text()
```
Más una prueba de `MainWindow` con `Controlador` falso solo si resulta viable offscreen sin red (el implementador decide; si no, se cubre con la checklist manual de la Task 12 y se dice explícitamente en el reporte).
- [ ] **Step 2-4** → implementar. **Step 5:** `python -m py_compile` de todos los módulos y suite completa verde. **Step 6:** commit `feat(desktop): semaforos de los seis servicios, radio http/https y pestanas CRUD en la ventana`.

---

### Task 12: Documentación y checklist manual

**Files:** Modify `apps/desktop_app/README.md`, `docs/AI_CHANGELOG.md`.

- [ ] **Step 1:** README: instalación (`pip install -r requirements.txt`), cómo apuntar a la GCP (Configuración → URLs) y alternativa con **túnel SSH** de los seis puertos (`ssh -L 5000:localhost:5000 -L 5001:localhost:5001 -L 5002:localhost:5002 -L 5003:localhost:5003 -L 5004:localhost:5004 -L 5005:localhost:5005 usuario@IP`), radio http/https y cuándo pasar a https, qué ve cada rol, mapa pestaña → servicio → endpoints.
- [ ] **Step 2: Checklist manual para evidencias (con la GCP arriba)**, en el README, numerada: (1) semáforos en verde y Redis ok; (2) apagar un servicio (`pkill -f "authors/app.py"` o detener su proceso) → rojo; (3) login admin → CRUD de usuario, autor, pedido, pago, libro; (4) login cliente → botones admin deshabilitados, 403 visible si se fuerza; (5) crear pedido con stock insuficiente → 409 legible; (6) logout → pestañas piden login; (7) radio https → URLs reescritas; (8) Redis detenido → mensajes 503 claros y sesión intacta.
- [ ] **Step 3:** `docs/AI_CHANGELOG.md` con entrada de esta rama (qué se agregó, qué NO se verificó: la UI solo se probó offscreen, nunca contra los servicios reales).
- [ ] **Step 4:** commit `docs(desktop): README con los seis servicios, radio https y checklist de evidencias`.

---

## Self-Review

**Spec coverage** (enunciado de la entrega): CRUD en todos los microservicios → Tasks 4, 7-10 (+ libros ya existente); semáforos → Tasks 5, 11; formularios → 7-10; radio http/https default http → 2, 11; "hacer uso de todos los microservicios" → 6 (clientes) y 11 (ventana); Redis visible en la app → 5, 11; evidencias → 12.
**Placeholders:** ninguno de `TBD/TODO`; las Tasks 7-11 dan comportamiento exacto, interfaces y pruebas completas pero **no** el código de layout Qt (decisión consciente: el layout es mecánico y las pruebas fijan nombres de widgets y comportamiento). Eso es un ruling de este plan, no un hueco.
**Consistencia de nombres:** `CrudTab.llamar/ok/error/solo_admin/refrescar_permisos/al_activar`, `Controlador.es_admin/role_id/user_id`, `AppConfig.url/con_protocolo`, `cambiar_esquema`, `comprobar_servicio`, `EstadoServicio.redis`, `Libro.id_libro`, nombres de widgets usados en las pruebas (`btn_crear`, `btn_eliminar`, `btn_rol`, `btn_password`, `password_actual`, `combo_libro`, `lista_libros`, `btn_vincular`, `btn_agregar`, `cantidad`, `tabla_lineas`, `btn_enviar`, `btn_cancelar`, `combo_pedido`, `combo_metodo`, `monto`, `btn_pagar`, `btn_reembolsar`, `radio_http`, `radio_https`, `campos[clave]`, `TarjetaEstado.redis`) deben respetarse tal cual.
**Riesgos que el plan NO resuelve:** no hay forma de probar la UI contra los servicios reales desde el entorno de desarrollo (los servicios corren en la GCP); la validación real es la checklist manual de la Task 12.
