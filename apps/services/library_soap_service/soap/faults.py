"""SOAP Fault (Parte 7 del ejercicio guiado).

Principio seguido: el Fault que ve el cliente nunca incluye stack traces,
SQL, rutas de archivos ni contraseñas. Ese detalle tecnico se registra
solo en el log del servidor (ver app.py, logger.exception) y aqui se
construye una version "segura" para el cliente.
"""

from xml.etree import ElementTree as ET
from soap.envelope import SOAP_NS, qname as _q, add_child


class SoapFault(Exception):
    """Clase base. `codigo` es un identificador corto y estable que la
    GUI puede usar para decidir el mensaje al usuario sin parsear texto
    libre (ver Parte 8, integracion de escritorio)."""

    faultcode = "soap:Client"
    http_status = 400

    def __init__(self, mensaje, codigo):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class XmlInvalidoFault(SoapFault):
    """XML mal formado o Envelope con estructura incorrecta. No se ejecuta
    SQL antes de llegar aqui (ver envelope.py)."""
    http_status = 400

    def __init__(self, mensaje):
        super().__init__(mensaje, "XML_INVALIDO")


class ValidacionFault(SoapFault):
    """Campo obligatorio faltante o modelo Cloud fuera de IaaS/PaaS/SaaS/FaaS."""
    http_status = 400

    def __init__(self, mensaje):
        super().__init__(mensaje, "VALIDACION")


class NoEncontradoFault(SoapFault):
    """Concepto o libro (ISBN) inexistente."""
    http_status = 404

    def __init__(self, mensaje):
        super().__init__(mensaje, "NO_ENCONTRADO")


class ConflictoFault(SoapFault):
    """Clasificacion duplicada."""
    http_status = 409

    def __init__(self, mensaje):
        super().__init__(mensaje, "CLASIFICACION_DUPLICADA")


class AutenticacionFault(SoapFault):
    """WS-Security UsernameToken ausente o invalido."""
    faultcode = "soap:Client"
    http_status = 401

    def __init__(self, mensaje="Autenticacion fallida."):
        super().__init__(mensaje, "AUTENTICACION_FALLIDA")


class ServidorFault(SoapFault):
    """Fallo interno (p.ej. PostgreSQL no disponible). El mensaje mostrado
    al cliente es genérico a propósito; el detalle técnico se registra
    solo en el log del servidor, nunca se envía en la respuesta."""
    faultcode = "soap:Server"
    http_status = 500

    def __init__(self, mensaje="Ocurrio un error interno en el servicio."):
        super().__init__(mensaje, "ERROR_SERVIDOR")


def build_fault_envelope(fault: SoapFault):
    """Construye el soap:Envelope/soap:Body/soap:Fault de respuesta."""
    envelope = ET.Element(_q(SOAP_NS, "Envelope"))
    body = ET.SubElement(envelope, _q(SOAP_NS, "Body"))
    fault_el = ET.SubElement(body, _q(SOAP_NS, "Fault"))

    ET.SubElement(fault_el, "faultcode").text = fault.faultcode
    ET.SubElement(fault_el, "faultstring").text = fault.mensaje

    detail = ET.SubElement(fault_el, "detail")
    add_child(detail, "codigo", fault.codigo)

    body_bytes = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
    return body_bytes, fault.http_status
