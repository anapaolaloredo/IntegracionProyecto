"""Semaforo de estado de los microservicios.

  OK        (verde)    responde y tiene acceso a su base de datos
  DEGRADADO (amarillo) responde por HTTP pero con error (p. ej. 503 BD caida)
  CAIDO     (rojo)     sin conexion, timeout o URL invalida

Los seis servicios exponen GET /health con {"db": "ok"|"error", "redis": "ok"|"error"}.
El color depende solo de la base de datos (fuente principal de datos); el estado de
Redis se reporta aparte porque las lecturas publicas funcionan sin el."""

from dataclasses import dataclass
from datetime import datetime

from core.http import ServiceError

OK, DEGRADADO, CAIDO = "ok", "degradado", "caido"


@dataclass
class EstadoServicio:
    estado: str
    detalle: str
    comprobado: datetime
    redis: str | None = None  # "ok" | "error" | None (el servicio no lo reporta o no respondio)


def _ahora():
    return datetime.now()


def comprobar_servicio(http, nombre):
    try:
        resp = http.request("GET", "/health", params={"format": "json"})
    except ServiceError as exc:
        return EstadoServicio(CAIDO, str(exc), _ahora())
    try:
        datos = resp.json()
    except ValueError:
        datos = None
    if not isinstance(datos, dict):
        return EstadoServicio(DEGRADADO, f"Respondió HTTP {resp.status_code} con una respuesta inesperada. "
                                         f"¿La URL apunta al microservicio de {nombre}?", _ahora())
    redis = datos.get("redis") if datos.get("redis") in ("ok", "error") else None
    if resp.status_code == 200 and datos.get("db") == "ok":
        return EstadoServicio(OK, "Servicio y base de datos funcionando.", _ahora(), redis)
    if resp.status_code == 503 or datos.get("db") == "error":
        return EstadoServicio(DEGRADADO, "El servicio responde, pero su base de datos no está disponible "
                                         f"(HTTP {resp.status_code}).", _ahora(), redis)
    return EstadoServicio(DEGRADADO, f"Respondió HTTP {resp.status_code} con una respuesta inesperada. "
                                     f"¿La URL apunta al microservicio de {nombre}?", _ahora(), redis)


def comprobar_login(http):
    return comprobar_servicio(http, "Login")


def comprobar_libros(http):
    return comprobar_servicio(http, "Libros")
