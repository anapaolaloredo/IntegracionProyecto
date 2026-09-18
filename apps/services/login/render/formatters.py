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
