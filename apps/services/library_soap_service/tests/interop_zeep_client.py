"""Tarea 4 (trabajo en casa): interoperabilidad.

Este cliente NO construye el Envelope a mano (a diferencia del resto del
proyecto): usa `zeep`, que LEE el WSDL publicado y genera dinamicamente
las llamadas, demostrando que un consumidor que no conoce la
implementacion interna del servidor (Flask + xml.etree) puede invocarlo
igualmente, siempre que respete el contrato.

Instalar solo para esta prueba (no es dependencia del servicio):
    pip install zeep

Uso:
    python tests/interop_zeep_client.py <WSDL_URL> <isbn> <id_concepto>
"""
import sys

from zeep import Client

WSDL_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5002/soap?wsdl"


def main():
    if len(sys.argv) < 4:
        print("Uso: python tests/interop_zeep_client.py <WSDL_URL> <isbn> <id_concepto>")
        raise SystemExit(1)
    isbn = sys.argv[2]
    id_concepto = int(sys.argv[3])

    cliente = Client(WSDL_URL)

    print("=== ObtenerConceptosPendientes (via zeep) ===")
    pendientes = cliente.service.ObtenerConceptosPendientes(correoClasificador="interop.zeep@udem.edu")
    print(pendientes)

    print("\n=== RegistrarClasificacion (via zeep) ===")
    resultado = cliente.service.RegistrarClasificacion(
        nombre="Interop",
        apellido="Zeep",
        correo="interop.zeep@udem.edu",
        isbn=isbn,
        idConcepto=id_concepto,
        modeloCloud="FaaS",
        origenCliente="zeep-python",
    )
    print(resultado)


if __name__ == "__main__":
    main()
