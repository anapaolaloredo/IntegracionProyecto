"""Pruebas del nucleo sin interfaz grafica. Uso:
    cd apps/desktop_app && python -m pytest tests -q"""

import pytest

from core import config as config_mod
from core import session_store
from core.books_api import Imagen, Libro, parsear_libros
from core.config import AppConfig, normalizar_url
from core.health import CAIDO, comprobar_libros, comprobar_login
from core.http import HttpClient, ServiceError, construir_url

XML = b"""<?xml version='1.0' encoding='utf-8'?>
<library>
  <book isbn="111"><title>Con todo</title>
    <authors><author>A</author><author>B</author></authors>
    <publicationYear>1999</publicationYear>
    <genres><genre>Novela</genre></genres>
    <price currency="MXN">199.5</price><stock>3</stock><format>Pasta dura</format>
    <images><image cover="false">http://x/2.jpg</image><image cover="true" alt="p">http://x/1.jpg</image></images>
    <concepts><concept name="Tema"><definition>Def</definition></concept></concepts>
  </book>
  <book isbn="222"><title>Sin nada</title><authors/><publicationYear/><genres/>
    <price currency="MXN">0</price><stock>0</stock><format/><images/><concepts/></book>
</library>"""


@pytest.fixture(autouse=True)
def carpeta_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRERIA_CONFIG_DIR", str(tmp_path))


def test_parsea_libro_completo_con_portada_primero():
    libro = parsear_libros(XML)[0]
    assert libro.autores == ["A", "B"] and libro.anio == 1999 and libro.precio == 199.5
    assert libro.imagenes[0].url == "http://x/1.jpg" and libro.imagenes[0].portada
    assert libro.conceptos == [("Tema", "Def")]


def test_parsea_libro_sin_imagen_ni_anio():
    libro = parsear_libros(XML)[1]
    assert libro.imagenes == [] and libro.anio is None and libro.autores == []


def test_xml_ajeno_da_error_legible():
    with pytest.raises(ServiceError):
        parsear_libros(b"<html><body>AirPlay</body></html>")


def test_payload_completo():
    libro = Libro("9", "T", ["A"], 2000, ["G"], 10.0, "MXN", 1, "F", [Imagen("u", True)], [("c", "d")])
    p = libro.a_payload()
    assert p["images"] == [{"url": "u", "cover": True, "alt": ""}]
    assert p["concepts"] == [{"name": "c", "definition": "d"}]


def test_construye_urls_sin_diagonales_dobles():
    assert construir_url("http://h:5001/", "/api/libros") == "http://h:5001/api/libros"
    assert normalizar_url("  http://h:5000/ ") == "http://h:5000"


def test_config_persiste_y_restaura():
    c = AppConfig(login_url="http://34.1.2.3:5000", books_url="http://34.1.2.3:5001", timeout=7, health_interval=60)
    c.save()
    assert AppConfig.load() == c
    assert AppConfig.defaults().login_url == config_mod.DEFAULTS["login_url"]


def test_config_invalida():
    assert AppConfig(login_url="localhost:5000").validar()
    assert AppConfig(books_url="http://h:99999x").validar()
    assert not AppConfig().validar()


def test_config_corrupta_usa_predeterminados(tmp_path):
    (tmp_path / "config.json").write_text("{no es json")
    assert AppConfig.load() == AppConfig.defaults()


def test_sesion_local_guardar_cargar_borrar():
    session_store.guardar("tok", "a@b.c")
    assert session_store.cargar()["token"] == "tok"
    session_store.borrar()
    assert session_store.cargar() is None


def test_puerto_cerrado_es_rojo_y_no_lanza():
    http = HttpClient("Login", "http://127.0.0.1:1", 2)
    assert comprobar_login(http).estado == CAIDO
    assert comprobar_libros(HttpClient("Libros", "http://127.0.0.1:1", 2)).estado == CAIDO


def test_url_invalida_es_error_legible():
    with pytest.raises(ServiceError) as exc:
        HttpClient("Libros", "http://", 2).request("GET", "/api/libros")
    assert exc.value.sin_conexion
