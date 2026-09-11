"""Plan de pruebas (Parte 9 del ejercicio guiado) ejecutado contra una
instancia real del servicio (por defecto http://localhost:5002/soap).

No usa ningun framework de pruebas para mantener las dependencias al
minimo: son peticiones HTTP planas con urllib (stdlib), mostrando el
Envelope de solicitud, el de respuesta y el resultado esperado vs obtenido
de cada caso, para poder pegarlos tal cual como evidencia en el reporte.

Uso:
    python tests/pruebas_manuales.py [URL_BASE]
"""
import sys
import urllib.request
import urllib.error

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5002/soap"

CORREO_PRUEBA = "ana.prueba@udem.edu"
ISBN_PRUEBA = None  # se completa en tiempo de ejecucion con un ISBN real
ID_CONCEPTO_PRUEBA = None


def enviar(envelope_xml, titulo):
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")
    print("--- Solicitud ---")
    print(envelope_xml.strip())
    req = urllib.request.Request(
        URL, data=envelope_xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            cuerpo = resp.read().decode("utf-8")
            print(f"--- Respuesta (HTTP {resp.status}) ---")
            print(cuerpo)
            return resp.status, cuerpo
    except urllib.error.HTTPError as err:
        cuerpo = err.read().decode("utf-8")
        print(f"--- Respuesta (HTTP {err.code}) ---")
        print(cuerpo)
        return err.code, cuerpo


def envelope(cuerpo_operacion):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="urn:udem:iac:library-classifier">
  <soap:Body>
    {cuerpo_operacion}
  </soap:Body>
</soap:Envelope>"""


def p01_obtener_conceptos_pendientes():
    op = f"""<tns:ObtenerConceptosPendientesRequest>
      <tns:correoClasificador>{CORREO_PRUEBA}</tns:correoClasificador>
    </tns:ObtenerConceptosPendientesRequest>"""
    status, cuerpo = enviar(envelope(op), "P01 - Obtener conceptos pendientes")
    ok = status == 200 and "conceptoPendiente" in cuerpo
    print(f"Resultado esperado: Lista valida | Obtenido: HTTP {status} | Estado: {'PASA' if ok else 'FALLA'}")
    return cuerpo


def p02_registrar_clasificacion(isbn, id_concepto, modelo="IaaS"):
    op = f"""<tns:RegistrarClasificacionRequest>
      <tns:nombre>Ana</tns:nombre>
      <tns:apellido>Prueba</tns:apellido>
      <tns:correo>{CORREO_PRUEBA}</tns:correo>
      <tns:isbn>{isbn}</tns:isbn>
      <tns:idConcepto>{id_concepto}</tns:idConcepto>
      <tns:modeloCloud>{modelo}</tns:modeloCloud>
      <tns:origenCliente>pruebas-manuales</tns:origenCliente>
    </tns:RegistrarClasificacionRequest>"""
    status, cuerpo = enviar(envelope(op), f"P02 - Registrar clasificacion ({modelo})")
    ok = status == 200 and "idClasificacion" in cuerpo
    print(f"Resultado esperado: Registro exitoso | Obtenido: HTTP {status} | Estado: {'PASA' if ok else 'FALLA'}")


def n01_repetir_clasificacion(isbn, id_concepto):
    op = f"""<tns:RegistrarClasificacionRequest>
      <tns:nombre>Ana</tns:nombre>
      <tns:apellido>Prueba</tns:apellido>
      <tns:correo>{CORREO_PRUEBA}</tns:correo>
      <tns:isbn>{isbn}</tns:isbn>
      <tns:idConcepto>{id_concepto}</tns:idConcepto>
      <tns:modeloCloud>IaaS</tns:modeloCloud>
    </tns:RegistrarClasificacionRequest>"""
    status, _ = enviar(envelope(op), "N01 - Repetir clasificacion (duplicado)")
    ok = status == 409
    print(f"Resultado esperado: SOAP Fault 409 | Obtenido: HTTP {status} | Estado: {'PASA' if ok else 'FALLA'}")


def n02_concepto_inexistente(isbn):
    op = f"""<tns:RegistrarClasificacionRequest>
      <tns:nombre>Ana</tns:nombre>
      <tns:apellido>Prueba</tns:apellido>
      <tns:correo>{CORREO_PRUEBA}</tns:correo>
      <tns:isbn>{isbn}</tns:isbn>
      <tns:idConcepto>999999</tns:idConcepto>
      <tns:modeloCloud>PaaS</tns:modeloCloud>
    </tns:RegistrarClasificacionRequest>"""
    status, _ = enviar(envelope(op), "N02 - Concepto inexistente")
    ok = status == 404
    print(f"Resultado esperado: SOAP Fault | Obtenido: HTTP {status} | Estado: {'PASA' if ok else 'FALLA'}")


def n03_modelo_invalido(isbn, id_concepto):
    op = f"""<tns:RegistrarClasificacionRequest>
      <tns:nombre>Ana</tns:nombre>
      <tns:apellido>Prueba</tns:apellido>
      <tns:correo>{CORREO_PRUEBA}</tns:correo>
      <tns:isbn>{isbn}</tns:isbn>
      <tns:idConcepto>{id_concepto}</tns:idConcepto>
      <tns:modeloCloud>NoEsUnModelo</tns:modeloCloud>
    </tns:RegistrarClasificacionRequest>"""
    status, _ = enviar(envelope(op), "N03 - Modelo Cloud invalido")
    ok = status == 400
    print(f"Resultado esperado: SOAP Fault | Obtenido: HTTP {status} | Estado: {'PASA' if ok else 'FALLA'}")


def extra_xml_invalido():
    status, _ = enviar("<esto>no es un sobre soap</esto>", "EXTRA - XML invalido (no es un Envelope)")
    ok = status == 400
    print(f"Resultado esperado: SOAP Fault de cliente | Obtenido: HTTP {status} | Estado: {'PASA' if ok else 'FALLA'}")


def extra_progreso_usuario():
    op = f"""<tns:ObtenerProgresoUsuarioRequest>
      <tns:correo>{CORREO_PRUEBA}</tns:correo>
    </tns:ObtenerProgresoUsuarioRequest>"""
    enviar(envelope(op), "EXTRA - Obtener progreso de usuario")


if __name__ == "__main__":
    # Uso: python tests/pruebas_manuales.py <URL_BASE> <isbn> <id_concepto>
    isbn = sys.argv[2] if len(sys.argv) > 2 else None
    id_concepto = sys.argv[3] if len(sys.argv) > 3 else None
    if not isbn or not id_concepto:
        print("Uso: python tests/pruebas_manuales.py <URL_BASE> <isbn> <id_concepto>")
        raise SystemExit(1)

    p01_obtener_conceptos_pendientes()
    p02_registrar_clasificacion(isbn, id_concepto, modelo="IaaS")
    n01_repetir_clasificacion(isbn, id_concepto)
    n02_concepto_inexistente(isbn)
    n03_modelo_invalido(isbn, id_concepto)
    extra_xml_invalido()
    extra_progreso_usuario()
