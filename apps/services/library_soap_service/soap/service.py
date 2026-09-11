"""Logica de negocio del servicio SOAP: recibe el elemento de operacion ya
parseado, valida, llama a la capa de datos (db/repository.py) y construye
el elemento de respuesta. No conoce HTTP ni el Envelope completo (eso vive
en app.py y soap/envelope.py) — separacion de responsabilidades pedida en
la estructura del proyecto (soap/service.py vs soap/envelope.py)."""

from soap.envelope import TNS, read_text, build_element, add_child
from soap.faults import ValidacionFault, NoEncontradoFault, ConflictoFault
from soap.security import verify_username_token
from db import repository

MODELOS_PERMITIDOS = ("IaaS", "PaaS", "SaaS", "FaaS")


def leer_cliente_info(header_element):
    """Header opcional <tns:ClienteInfo><tns:tipoCliente/><tns:identificador/></tns:ClienteInfo>
    presente en cualquier operacion, usado unicamente para contabilizar
    peticiones por tipo de cliente (Parte 1, requisito de scope). No
    afecta la logica de negocio de la operacion en si."""
    if header_element is None:
        return None, None
    cliente_info = header_element.find(f"{{{TNS}}}ClienteInfo")
    if cliente_info is None:
        return None, None
    tipo_cliente = read_text(cliente_info, "tipoCliente", required=False)
    identificador = read_text(cliente_info, "identificador", required=False)
    return tipo_cliente, identificador


def _obtener_conceptos_pendientes(request_el):
    correo = read_text(request_el, "correoClasificador")

    pendientes = repository.obtener_conceptos_pendientes(correo)

    response = build_element("ObtenerConceptosPendientesResponse")
    for item in pendientes:
        concepto_el = add_child(response, "conceptoPendiente")
        # add_child normalmente agrega texto; aqui se usa como contenedor
        # y se le agregan sus propios hijos con la misma funcion.
        add_child(concepto_el, "isbn", item["isbn"])
        add_child(concepto_el, "tituloLibro", item["titulo_libro"])
        add_child(concepto_el, "idConcepto", item["id_concepto"])
        add_child(concepto_el, "nombreConcepto", item["nombre_concepto"])
        add_child(concepto_el, "definicion", item["definicion"])
        add_child(concepto_el, "categorias", item.get("categorias") or "")
    return response


def _registrar_clasificacion(request_el, origen_cliente_header):
    nombre = read_text(request_el, "nombre")
    apellido = read_text(request_el, "apellido")
    correo = read_text(request_el, "correo")
    isbn = read_text(request_el, "isbn")
    id_concepto_txt = read_text(request_el, "idConcepto")
    modelo_cloud = read_text(request_el, "modeloCloud")
    origen_cliente = read_text(request_el, "origenCliente", required=False) or origen_cliente_header

    if modelo_cloud not in MODELOS_PERMITIDOS:
        raise ValidacionFault(
            f"modeloCloud '{modelo_cloud}' invalido. Valores permitidos: {', '.join(MODELOS_PERMITIDOS)}."
        )
    try:
        id_concepto = int(id_concepto_txt)
    except ValueError:
        raise ValidacionFault("idConcepto debe ser un entero.")

    try:
        id_clasificacion = repository.registrar_clasificacion(
            nombre, apellido, correo, isbn, id_concepto, modelo_cloud, origen_cliente
        )
    except repository.RegistroDuplicadoError as exc:
        raise ConflictoFault(str(exc))
    except repository.RecursoNoEncontradoError as exc:
        raise NoEncontradoFault(str(exc))

    response = build_element("RegistrarClasificacionResponse")
    add_child(response, "idClasificacion", id_clasificacion)
    add_child(response, "mensaje", "Clasificacion registrada correctamente.")
    return response


def _obtener_progreso_usuario(request_el):
    correo = read_text(request_el, "correo")
    progreso = repository.obtener_progreso_usuario(correo)

    response = build_element("ObtenerProgresoUsuarioResponse")
    add_child(response, "totalConceptos", progreso["totalConceptos"])
    add_child(response, "totalClasificados", progreso["totalClasificados"])
    add_child(response, "totalPendientes", progreso["totalPendientes"])
    return response


def _obtener_estadisticas_por_modelo(header_element):
    # Operacion protegida con WS-Security (Tarea 1).
    verify_username_token(header_element)

    estadisticas = repository.obtener_estadisticas_por_modelo()
    response = build_element("ObtenerEstadisticasPorModeloResponse")
    for item in estadisticas:
        estadistica_el = add_child(response, "estadistica")
        add_child(estadistica_el, "modeloCloud", item["modeloCloud"])
        add_child(estadistica_el, "total", item["total"])
    return response


# Estilo document/literal "envuelto": el nombre del elemento hijo de
# soap:Body (p.ej. <tns:RegistrarClasificacionRequest>) identifica la
# operacion. Por eso las claves llevan el sufijo "Request", tal como se
# definieron los elementos en el XSD del WSDL.
OPERACIONES = {
    "ObtenerConceptosPendientesRequest": lambda req, header: _obtener_conceptos_pendientes(req),
    "RegistrarClasificacionRequest": lambda req, header: _registrar_clasificacion(
        req, leer_cliente_info(header)[0]
    ),
    "ObtenerProgresoUsuarioRequest": lambda req, header: _obtener_progreso_usuario(req),
    "ObtenerEstadisticasPorModeloRequest": lambda req, header: _obtener_estadisticas_por_modelo(header),
}


def dispatch(nombre_elemento, request_el, header_element):
    """Unico punto de entrada usado por app.py. `nombre_elemento` es el
    nombre local (sin namespace) del elemento hijo de soap:Body, resuelto
    en soap/envelope.py."""
    handler = OPERACIONES.get(nombre_elemento)
    if handler is None:
        raise ValidacionFault(f"Operacion '{nombre_elemento}' no soportada.")
    return handler(request_el, header_element)
