"""Tarea 1 (trabajo en casa): demuestra ObtenerEstadisticasPorModelo
protegida con WS-Security UsernameToken, con credenciales correctas e
incorrectas.

Uso:
    python tests/wsse_demo.py <URL_BASE> <usuario> <password_correcta>
"""
import sys
import urllib.request
import urllib.error

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5002/soap"
USUARIO = sys.argv[2] if len(sys.argv) > 2 else "stats-client"
PASSWORD_OK = sys.argv[3] if len(sys.argv) > 3 else "cambia-esto"


def envelope_con_wsse(usuario, password):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="urn:udem:iac:library-classifier"
               xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
  <soap:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>{usuario}</wsse:Username>
        <wsse:Password Type="PasswordText">{password}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <tns:ObtenerEstadisticasPorModeloRequest/>
  </soap:Body>
</soap:Envelope>"""


def enviar(xml, titulo):
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")
    print("--- Solicitud ---")
    print(xml)
    req = urllib.request.Request(
        URL, data=xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            cuerpo = resp.read().decode("utf-8")
            print(f"--- Respuesta (HTTP {resp.status}) ---\n{cuerpo}")
            return resp.status
    except urllib.error.HTTPError as err:
        cuerpo = err.read().decode("utf-8")
        print(f"--- Respuesta (HTTP {err.code}) ---\n{cuerpo}")
        return err.code


if __name__ == "__main__":
    status_ok = enviar(envelope_con_wsse(USUARIO, PASSWORD_OK), "Credenciales correctas")
    print(f"Esperado: 200 | Obtenido: {status_ok}")

    status_bad = enviar(envelope_con_wsse(USUARIO, "password-incorrecta"), "Credenciales incorrectas")
    print(f"Esperado: 401 (SOAP Fault de autenticacion) | Obtenido: {status_bad}")
