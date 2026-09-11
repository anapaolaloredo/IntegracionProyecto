"""Construccion y lectura MANUAL del SOAP Envelope con xml.etree.

No se usa Spyne/Zeep/suds del lado del servidor: este archivo es, a
proposito, el unico lugar donde se conocen los namespaces SOAP y se arma
el sobre a mano, tal como pide el ejercicio guiado (Parte 6, punto 11).
"""

from xml.etree import ElementTree as ET

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS = "urn:udem:iac:library-classifier"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"

ET.register_namespace("soap", SOAP_NS)
ET.register_namespace("tns", TNS)
ET.register_namespace("wsse", WSSE_NS)


def qname(ns, tag):
    return f"{{{ns}}}{tag}"


# Alias interno usado dentro de este modulo.
_q = qname


class EnvelopeInvalidoError(Exception):
    """El XML recibido no es un SOAP Envelope valido (mal formado o
    estructura incorrecta). Se traduce siempre a un SOAP Fault de cliente,
    y NUNCA dispara una consulta a PostgreSQL."""


def parse_envelope(raw_bytes):
    """Parsea el POST recibido y devuelve (header_element_o_None, body_element).

    Nunca ejecuta SQL: solo XML. Cualquier problema de formato termina en
    EnvelopeInvalidoError (-> SOAP Fault de cliente, sin tocar la base).
    """
    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError as exc:
        raise EnvelopeInvalidoError(f"XML mal formado: {exc}") from exc

    if root.tag != _q(SOAP_NS, "Envelope"):
        raise EnvelopeInvalidoError("La raiz del documento debe ser soap:Envelope.")

    body = root.find(_q(SOAP_NS, "Body"))
    if body is None:
        raise EnvelopeInvalidoError("El Envelope no contiene soap:Body.")

    header = root.find(_q(SOAP_NS, "Header"))
    return header, body


def get_operation_element(body):
    """Body debe contener exactamente un elemento hijo: la operacion pedida."""
    hijos = list(body)
    if len(hijos) != 1:
        raise EnvelopeInvalidoError("soap:Body debe contener exactamente una operacion.")
    return hijos[0]


def operation_name(operation_element):
    """Nombre local de la operacion (sin namespace), p.ej. 'RegistrarClasificacion'."""
    tag = operation_element.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def read_text(parent, campo, ns=TNS, required=True, default=None):
    el = parent.find(_q(ns, campo))
    if el is None or el.text is None or el.text.strip() == "":
        if required:
            raise EnvelopeInvalidoError(f"Falta el campo obligatorio '{campo}'.")
        return default
    return el.text.strip()


def build_element(tag, ns=TNS):
    return ET.Element(_q(ns, tag))


def add_child(parent, tag, text=None, ns=TNS):
    """Crea <tns:tag>text</tns:tag> bajo parent. ElementTree escapa el
    texto automaticamente (&, <, > etc.), por lo que nunca se concatena
    XML a mano con valores del usuario."""
    child = ET.SubElement(parent, _q(ns, tag))
    if text is not None:
        child.text = str(text)
    return child


def build_response_envelope(response_element):
    """Envuelve response_element (p.ej. <tns:RegistrarClasificacionResponse>)
    en un soap:Envelope/soap:Body y devuelve los bytes XML listos para el
    cuerpo HTTP de la respuesta."""
    envelope = ET.Element(_q(SOAP_NS, "Envelope"))
    body = ET.SubElement(envelope, _q(SOAP_NS, "Body"))
    body.append(response_element)
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
