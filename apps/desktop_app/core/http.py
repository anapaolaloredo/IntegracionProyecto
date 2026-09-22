"""Cliente HTTP comun: construye URLs, aplica el timeout y convierte los
fallos de red en ServiceError con mensajes comprensibles (nunca un
traceback). Cada peticion se reporta a un callback para el registro HTTP."""

import json
import time
import xml.etree.ElementTree as ET

import requests
import urllib3.util.connection

# Los microservicios escuchan en IPv4 (0.0.0.0 / IP publica de la instancia).
# En redes donde la ruta IPv6 se cuelga, requests agotaria el timeout antes de
# probar IPv4; forzar IPv4 evita esos falsos "sin conexion".
urllib3.util.connection.HAS_IPV6 = False


class ServiceError(Exception):
    """Error presentable al usuario. kind: conexion | timeout | url | http | respuesta."""

    def __init__(self, mensaje, kind="http", status=None):
        super().__init__(mensaje)
        self.kind = kind
        self.status = status

    @property
    def sin_conexion(self):
        return self.kind in ("conexion", "timeout", "url")


class SesionExpirada(ServiceError):
    """El servidor rechazo el token (401): hay que volver a iniciar sesion."""


MENSAJES_STATUS = {
    400: "El servicio rechazó los datos enviados.",
    401: "No autorizado.",
    403: "Acceso denegado por el servidor. ¿La URL apunta al microservicio correcto? "
         "(En macOS, localhost:5000 es AirPlay; revisa Configuración del servidor)",
    404: "No se encontró el recurso solicitado.",
    405: "El servidor no admite esta operación en esa URL (¿URL o puerto incorrecto?).",
    409: "El recurso ya existe.",
}


def construir_url(base, ruta):
    return base.rstrip("/") + "/" + ruta.lstrip("/")


def mensaje_del_servidor(resp):
    """Extrae el mensaje de error del cuerpo JSON ({mensaje}) o XML (<message>/<mensaje>)."""
    texto = resp.text or ""
    try:
        datos = json.loads(texto)
        if isinstance(datos, dict):
            return datos.get("mensaje") or datos.get("message")
    except ValueError:
        pass
    try:
        raiz = ET.fromstring(texto)
        for etiqueta in ("message", "mensaje"):
            nodo = raiz.find(f".//{etiqueta}")
            if nodo is not None and nodo.text:
                return nodo.text
    except ET.ParseError:
        pass
    return None


def mensaje_para_status(resp):
    servidor = mensaje_del_servidor(resp)
    if servidor:
        return f"{servidor} (HTTP {resp.status_code})"
    if resp.status_code >= 500:
        return f"El servicio tuvo un error interno (HTTP {resp.status_code}). Puede que su base de datos no esté disponible."
    generico = MENSAJES_STATUS.get(resp.status_code, "Respuesta inesperada del servicio.")
    return f"{generico} (HTTP {resp.status_code})"


class HttpClient:
    def __init__(self, nombre_servicio, base_url, timeout, on_log=None):
        self.nombre_servicio = nombre_servicio
        self.base_url = base_url
        self.timeout = timeout
        self.on_log = on_log

    def request(self, metodo, ruta, *, params=None, json_body=None, headers=None):
        """Hace la peticion y regresa el Response sin importar el status.
        Solo lanza ServiceError cuando no hubo respuesta HTTP."""
        url = construir_url(self.base_url, ruta)
        inicio = time.monotonic()
        entrada = {"servicio": self.nombre_servicio, "metodo": metodo, "url": url,
                   "params": params, "body": json_body}
        try:
            resp = requests.request(metodo, url, params=params, json=json_body,
                                    headers=headers, timeout=self.timeout)
        except requests.exceptions.Timeout:
            error = ServiceError(
                f"El servicio de {self.nombre_servicio} no respondió en {self.timeout} s ({self.base_url}).",
                kind="timeout")
        except (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema,
                requests.exceptions.InvalidSchema):
            error = ServiceError(
                f"La URL configurada para {self.nombre_servicio} no es válida: {self.base_url}", kind="url")
        except requests.exceptions.ConnectionError:
            error = ServiceError(
                f"No se pudo conectar con el servicio de {self.nombre_servicio} en {self.base_url}. "
                "Verifica que esté encendido y que la URL/puerto en Configuración sean correctos.",
                kind="conexion")
        except requests.exceptions.RequestException as exc:
            error = ServiceError(f"Falló la comunicación con {self.nombre_servicio}: {exc.__class__.__name__}",
                                 kind="conexion")
        else:
            self._log(entrada, inicio, status=resp.status_code)
            return resp
        self._log(entrada, inicio, error=str(error))
        raise error

    def _log(self, entrada, inicio, status=None, error=None):
        if self.on_log:
            entrada.update(status=status, error=error, ms=int((time.monotonic() - inicio) * 1000))
            self.on_log(entrada)
