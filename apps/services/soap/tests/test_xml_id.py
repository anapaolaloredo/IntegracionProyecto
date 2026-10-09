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
    assert ET.tostring(el)


def test_query_selecciona_id_libro():
    assert "l.id_libro AS id_libro" in books.BOOK_QUERY
