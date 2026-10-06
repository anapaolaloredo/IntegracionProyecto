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
