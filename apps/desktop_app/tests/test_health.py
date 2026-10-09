import json

from core.health import CAIDO, DEGRADADO, OK, comprobar_servicio
from core.http import ServiceError


class R:
    def __init__(self, status, datos=None, texto=None):
        self.status_code = status
        self.text = texto if texto is not None else json.dumps(datos)

    def json(self):
        return json.loads(self.text)


class H:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc
        self.llamadas = []

    def request(self, metodo, ruta, **kw):
        self.llamadas.append((metodo, ruta, kw.get("params")))
        if self.exc:
            raise self.exc
        return self.resp


def test_ok_con_db_y_redis():
    h = H(R(200, {"servicio": "users", "status": "ok", "db": "ok", "redis": "ok"}))
    e = comprobar_servicio(h, "Usuarios")
    assert e.estado == OK and e.redis == "ok" and h.llamadas[0][1] == "/health"


def test_redis_error_no_baja_el_semaforo():
    e = comprobar_servicio(H(R(200, {"db": "ok", "redis": "error"})), "Pedidos")
    assert e.estado == OK and e.redis == "error"


def test_bd_caida_es_degradado():
    e = comprobar_servicio(H(R(503, {"db": "error", "redis": "ok"})), "Pagos")
    assert e.estado == DEGRADADO


def test_respuesta_ajena_es_degradado_con_pista():
    e = comprobar_servicio(H(R(200, texto="<html>AirPlay</html>")), "Autores")
    assert e.estado == DEGRADADO and "Autores" in e.detalle


def test_sin_conexion_es_caido():
    e = comprobar_servicio(H(exc=ServiceError("sin conexion", kind="conexion")), "Login")
    assert e.estado == CAIDO and e.redis is None
