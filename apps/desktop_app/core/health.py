"""Semaforo de estado de los microservicios.

  OK        (verde)    responde y tiene acceso a su base de datos
  DEGRADADO (amarillo) responde por HTTP pero con error (p. ej. 503 BD caida)
  CAIDO     (rojo)     sin conexion, timeout o URL invalida

Login usa su GET /health. El servicio de libros no tiene /health, asi que
se usa una consulta ligera que si toca la base de datos
(GET /api/libros/temas?isbn=<inexistente>): 200 = BD accesible."""

from dataclasses import dataclass
from datetime import datetime

from core.http import ServiceError

OK, DEGRADADO, CAIDO = "ok", "degradado", "caido"


@dataclass
class EstadoServicio:
    estado: str
    detalle: str
    comprobado: datetime


def _ahora():
    return datetime.now()


def comprobar_login(http):
    try:
        resp = http.request("GET", "/health", params={"format": "json"})
    except ServiceError as exc:
        return EstadoServicio(CAIDO, str(exc), _ahora())
    try:
        datos = resp.json()
    except ValueError:
        datos = None
    if resp.status_code == 200 and isinstance(datos, dict) and datos.get("db") == "ok":
        return EstadoServicio(OK, "Servicio y base de datos funcionando.", _ahora())
    if resp.status_code == 503:
        return EstadoServicio(DEGRADADO, "El servicio responde, pero su base de datos no está disponible (HTTP 503).",
                              _ahora())
    return EstadoServicio(DEGRADADO, f"Respondió HTTP {resp.status_code} con una respuesta inesperada. "
                                     "¿La URL apunta al microservicio de login?", _ahora())


def comprobar_libros(http):
    try:
        resp = http.request("GET", "/api/libros/temas", params={"isbn": "__healthcheck__"})
    except ServiceError as exc:
        return EstadoServicio(CAIDO, str(exc), _ahora())
    if resp.status_code == 200 and b"<library" in resp.content:
        return EstadoServicio(OK, "Servicio y base de datos funcionando.", _ahora())
    if resp.status_code >= 500:
        return EstadoServicio(DEGRADADO, f"El servicio responde, pero falló al consultar su base de datos "
                                         f"(HTTP {resp.status_code}).", _ahora())
    return EstadoServicio(DEGRADADO, f"Respondió HTTP {resp.status_code} con una respuesta inesperada. "
                                     "¿La URL apunta al microservicio de libros?", _ahora())
