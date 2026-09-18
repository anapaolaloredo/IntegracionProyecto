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
