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



class FakeCursor:
    """Mismo cursor falso que tests/test_libros_db.py: fetchone devuelve la fila configurada."""

    def __init__(self, row=None):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return self.row


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self, *a, **k):
        return self._cursor

    def close(self):
        pass


def _ConexionOk():
    return FakeConn(FakeCursor(row=(1, "T", 2000, 10, 5, 1)))


def test_redis_url_invalida_no_rompe_lecturas_ni_escrituras(c, monkeypatch):
    redis_store.reiniciar()
    monkeypatch.setenv("REDIS_URL", "redis://:s3cr/etPart@localhost:6379/0")
    monkeypatch.setattr(books, "_db_ok", lambda: True)
    monkeypatch.setattr(books, "get_connection", lambda: _ConexionOk())
    monkeypatch.setattr(books, "guardar_relaciones", lambda *a, **k: None)
    assert c.get("/api/libros").status_code == 200
    # la autorizacion es fail-closed: sin Redis valido responde 503, nunca 500
    assert c.put("/api/libros/123", json={"title": "N"}, headers=_admin()).status_code == 503
    # con la autorizacion superada, la invalidacion (fail-open) no convierte la escritura en 500
    monkeypatch.setattr(redis_store, "jti_revocado", lambda jti: False)
    assert c.put("/api/libros/123", json={"title": "N"}, headers=_admin()).status_code == 200
    assert c.get("/health").get_json()["redis"] == "error"
