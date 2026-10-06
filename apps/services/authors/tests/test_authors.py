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
