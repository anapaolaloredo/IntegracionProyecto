"""Pruebas de PUT/DELETE de libros con conexion falsa (sin PostgreSQL)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")

import psycopg2.errors
import pytest

import app as books
from common.jwt_auth import crear_token


class FakeCursor:
    def __init__(self, sql_log, fail_on=None, row=None):
        self.sql_log, self.fail_on, self.row = sql_log, fail_on, row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql_log.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise psycopg2.errors.ForeignKeyViolation()

    def fetchone(self):
        return self.row


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *a):
        return False  # como psycopg2: hace rollback y propaga

    def cursor(self, *a, **k):
        return self._cursor

    def close(self):
        pass


@pytest.fixture
def cliente():
    books.app.config["TESTING"] = True
    return books.app.test_client()


def _h(role_id=2):
    return {"Authorization": f"Bearer {crear_token(1, role_id, 'access', 600)}"}


def test_put_bloquea_la_fila_con_for_update(cliente, monkeypatch):
    log = []
    cur = FakeCursor(log, row=(1, "T", 2000, 10, 5, 1))
    monkeypatch.setattr(books, "get_connection", lambda: FakeConn(cur))
    monkeypatch.setattr(books, "guardar_relaciones", lambda *a, **k: None)
    monkeypatch.setattr(books, "fetch_books", lambda *a, **k: [])
    resp = cliente.put("/api/libros/123", json={"title": "N"}, headers=_h())
    assert resp.status_code == 200
    selects = [s for s in log if s.lstrip().upper().startswith("SELECT")]
    assert selects and "FOR UPDATE" in selects[0]


def test_delete_con_pedidos_da_409_xml(cliente, monkeypatch):
    cur = FakeCursor([], fail_on="DELETE FROM libros")
    monkeypatch.setattr(books, "get_connection", lambda: FakeConn(cur))
    resp = cliente.delete("/api/libros/123", headers=_h(1))
    assert resp.status_code == 409
    assert resp.mimetype == "application/xml"
    assert b"pedidos asociados" in resp.data


def test_dato_demasiado_largo_da_400_xml_y_no_500(cliente, monkeypatch):
    class Cur(FakeCursor):
        def execute(self, sql, params=None):
            if "INSERT INTO libros" in sql:
                raise psycopg2.errors.StringDataRightTruncation()

        def fetchone(self):
            return (1,)

    monkeypatch.setattr(books, "get_connection", lambda: FakeConn(Cur([])))
    monkeypatch.setattr(books, "get_or_create_id", lambda *a, **k: 1)
    resp = cliente.post("/api/libros", json={"isbn": "x" * 30, "title": "T", "price": 1, "stock": 1, "format": "f"},
                        headers=_h(1))
    assert resp.status_code == 400 and resp.mimetype == "application/xml"
    assert b"13 caracteres" in resp.data
