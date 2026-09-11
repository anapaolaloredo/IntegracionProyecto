"""Modulo SOAP independiente para clasificar el catalogo de la libreria
(Cloud: IaaS/PaaS/SaaS/FaaS). No modifica el monolito Node.js; comparte la
base de datos con un rol propio de minimo privilegio (ver sql/soap_module.sql).

Endpoint unico HTTP POST /soap que recibe un SOAP Envelope, y GET /soap?wsdl
que sirve el contrato. Es el unico archivo que conecta HTTP con la logica
SOAP; toda la construccion/lectura de XML vive en soap/envelope.py y
soap/faults.py.
"""

import logging
import os

from flask import Flask, Response, request

from config.settings import PORT
from soap.envelope import EnvelopeInvalidoError, parse_envelope, get_operation_element, operation_name, build_response_envelope
from soap.faults import SoapFault, XmlInvalidoFault, ServidorFault, build_fault_envelope
from soap.service import dispatch, leer_cliente_info
from db import repository

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

WSDL_PATH = os.path.join(os.path.dirname(__file__), "wsdl", "library-classifier.wsdl")


@app.route("/soap", methods=["GET"])
def obtener_wsdl():
    """Publica el contrato: GET /soap?wsdl (convencion habitual de SOAP)."""
    if "wsdl" not in request.args:
        return Response("Use POST para invocar operaciones o GET ?wsdl para el contrato.", status=400)
    with open(WSDL_PATH, "rb") as f:
        contenido = f.read()
    return Response(contenido, mimetype="text/xml")


@app.route("/soap", methods=["POST"])
def procesar_envelope():
    raw = request.get_data()

    try:
        header, body = parse_envelope(raw)
    except EnvelopeInvalidoError as exc:
        # XML invalido: se responde SOAP Fault de cliente y NO se ejecuta SQL.
        xml, status = build_fault_envelope(XmlInvalidoFault(str(exc)))
        return Response(xml, status=status, mimetype="text/xml")

    try:
        operacion_el = get_operation_element(body)
        nombre = operation_name(operacion_el)

        # Contabiliza al cliente (si mando el header opcional ClienteInfo)
        # antes de ejecutar la operacion, para reflejar tambien los intentos.
        tipo_cliente, identificador = leer_cliente_info(header)
        if tipo_cliente and identificador:
            repository.registrar_cliente_servido(tipo_cliente, identificador)

        respuesta_el = dispatch(nombre, operacion_el, header)
        xml = build_response_envelope(respuesta_el)
        return Response(xml, status=200, mimetype="text/xml")

    except EnvelopeInvalidoError as exc:
        xml, status = build_fault_envelope(XmlInvalidoFault(str(exc)))
        return Response(xml, status=status, mimetype="text/xml")

    except SoapFault as fault:
        xml, status = build_fault_envelope(fault)
        return Response(xml, status=status, mimetype="text/xml")

    except Exception:
        # Fallo no anticipado (p.ej. PostgreSQL caido): se registra el detalle
        # tecnico SOLO en el log del servidor; el cliente recibe un Fault
        # generico (Parte 7: "no exponer stack traces, contraseñas, rutas
        # internas o consultas SQL").
        app.logger.exception("Error interno procesando una peticion SOAP")
        xml, status = build_fault_envelope(ServidorFault())
        return Response(xml, status=status, mimetype="text/xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
