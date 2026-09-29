"""Pruebas de la proteccion de escritura. Uso:
    cd apps/services/soap && .venv/bin/python -m pytest tests -q
No requieren PostgreSQL ni login: la consulta a login se simula."""

import pytest

import app as books


@pytest.fixture
def cliente():
    books.app.config["TESTING"] = True
    return books.app.test_client()


def _login_responde(monkeypatch, valor):
    def falso(token):
        if isinstance(valor, Exception):
            raise valor
        return valor
    monkeypatch.setattr(books, "sesion_valida", falso)


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/libros"),
    ("put", "/api/libros/123"),
    ("delete", "/api/libros/123"),
])
def test_escritura_sin_token_da_401(cliente, metodo, ruta):
    assert getattr(cliente, metodo)(ruta, json={}).status_code == 401


def test_token_invalido_da_401(cliente, monkeypatch):
    _login_responde(monkeypatch, False)
    resp = cliente.delete("/api/libros/123", headers={"Authorization": "Bearer malo"})
    assert resp.status_code == 401


def test_login_caido_rechaza_con_503(cliente, monkeypatch):
    _login_responde(monkeypatch, OSError("sin conexion"))
    resp = cliente.delete("/api/libros/123", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 503


def test_token_valido_pasa_a_la_vista(cliente, monkeypatch):
    _login_responde(monkeypatch, True)
    # Cuerpo vacio: la vista responde 400 de validacion, prueba de que el decorador dejo pasar.
    resp = cliente.post("/api/libros", json={}, headers={"Authorization": "Bearer ok"})
    assert resp.status_code not in (401, 503)


@pytest.mark.parametrize("ruta", ["/api/libros", "/api/libros/123", "/api/libros/catalogo"])
def test_lecturas_no_piden_token(cliente, monkeypatch, ruta):
    monkeypatch.setattr(books, "fetch_books", lambda *a, **k: [])
    monkeypatch.setattr(books, "get_connection", lambda: (_ for _ in ()).throw(RuntimeError("sin bd")))
    try:
        resp = cliente.get(ruta)
    except RuntimeError:
        return  # llego a la base de datos: no hubo bloqueo por autenticacion
    assert resp.status_code not in (401, 503)
