import json

import pytest

from core.http import ServiceError, SesionExpirada
from core.rest_api import AuthorsApi, PagosApi, PedidosApi, UsersApi


class Resp:
    def __init__(self, status=200, datos=None, texto=None):
        self.status_code = status
        self.text = texto if texto is not None else (json.dumps(datos) if datos is not None else "")
        self.content = self.text.encode()

    def json(self):
        return json.loads(self.text)


class FakeHttp:
    base_url = "http://fake"

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def request(self, metodo, ruta, *, params=None, json_body=None, headers=None):
        self.llamadas.append((metodo, ruta, params, json_body, headers))
        return self.respuestas.pop(0)


def api(clase, *respuestas, token="TOK"):
    http = FakeHttp(*respuestas)
    return clase(http, lambda: token), http


def test_envia_bearer_y_devuelve_json():
    a, http = api(UsersApi, Resp(200, [{"id_usuario": 1}]))
    assert a.listar() == [{"id_usuario": 1}]
    assert http.llamadas[0][4] == {"Authorization": "Bearer TOK"}


def test_sin_token_no_hace_peticion():
    a, http = api(PedidosApi, token=None)
    with pytest.raises(SesionExpirada):
        a.listar()
    assert http.llamadas == []


def test_publico_no_envia_token_aunque_exista():
    a, http = api(AuthorsApi, Resp(200, []))
    a.listar()
    assert http.llamadas[0][4] is None


def test_401_con_token_es_sesion_expirada():
    a, _ = api(PagosApi, Resp(401, {"mensaje": "Token revocado"}))
    with pytest.raises(SesionExpirada) as e:
        a.listar()
    assert "Token revocado" in str(e.value)


def test_403_y_409_conservan_el_mensaje_del_servidor():
    a, _ = api(UsersApi, Resp(403, {"mensaje": "Rol insuficiente para esta operacion"}))
    with pytest.raises(ServiceError) as e:
        a.eliminar(3)
    assert e.value.status == 403 and "Rol insuficiente" in str(e.value)
    a, _ = api(PedidosApi, Resp(409, {"mensaje": "Stock insuficiente para el libro 11 (disponible 20, pedido 9999)."}))
    with pytest.raises(ServiceError) as e:
        a.crear([{"id_libro": 11, "cantidad": 9999}])
    assert e.value.status == 409 and "Stock insuficiente" in str(e.value)


def test_503_es_error_de_servicio_no_sesion_expirada():
    a, _ = api(UsersApi, Resp(503, {"mensaje": "Servicio de sesiones no disponible."}))
    with pytest.raises(ServiceError) as e:
        a.listar()
    assert not isinstance(e.value, SesionExpirada) and e.value.status == 503


def test_rutas_y_cuerpos_de_users():
    a, http = api(UsersApi, Resp(201, {"id_usuario": 9}), Resp(200, {}), Resp(200, {}), Resp(200, {}), Resp(200, {}))
    a.crear("a@b.mx", "Ana", "Lo", "Mo", "claveSegura1", "cliente")
    a.actualizar(9, nombre="Nuevo")
    a.cambiar_password(9, "otraClave12", actual="claveSegura1")
    a.cambiar_rol(9, "admin")
    a.eliminar(9)
    m = [(c[0], c[1], c[3]) for c in http.llamadas]
    assert m[0] == ("POST", "/api/users", {"correo": "a@b.mx", "nombre": "Ana", "apellido_paterno": "Lo",
                                           "apellido_materno": "Mo", "password": "claveSegura1", "rol": "cliente"})
    assert m[1] == ("PATCH", "/api/users/9", {"nombre": "Nuevo"})
    assert m[2] == ("PATCH", "/api/users/9/password", {"password_nueva": "otraClave12", "password_actual": "claveSegura1"})
    assert m[3] == ("PATCH", "/api/users/9/rol", {"rol": "admin"})
    assert m[4] == ("DELETE", "/api/users/9", None)


def test_cambiar_password_de_otro_no_manda_actual():
    a, http = api(UsersApi, Resp(200, {}))
    a.cambiar_password(4, "nuevaClave12")
    assert http.llamadas[0][3] == {"password_nueva": "nuevaClave12"}


def test_rutas_authors_pedidos_pagos():
    a, http = api(AuthorsApi, Resp(201, {}), Resp(200, {}), Resp(201, {}), Resp(200, {}), Resp(200, {}))
    a.crear("X"); a.renombrar(2, "Y"); a.vincular(2, 11); a.desvincular(2, 11); a.eliminar(2)
    assert [(c[0], c[1]) for c in http.llamadas] == [
        ("POST", "/api/authors"), ("PATCH", "/api/authors/2"), ("POST", "/api/authors/2/books"),
        ("DELETE", "/api/authors/2/books/11"), ("DELETE", "/api/authors/2")]
    assert http.llamadas[2][3] == {"id_libro": 11}
    p, http = api(PedidosApi, Resp(201, {}), Resp(200, {}), Resp(200, {}))
    p.crear([{"id_libro": 11, "cantidad": 2}]); p.cambiar_estado(1, "cancelado"); p.eliminar(1)
    assert [(c[0], c[1]) for c in http.llamadas] == [
        ("POST", "/api/pedidos"), ("PATCH", "/api/pedidos/1/estado"), ("DELETE", "/api/pedidos/1")]
    assert http.llamadas[0][3] == {"lineas": [{"id_libro": 11, "cantidad": 2}]}
    g, http = api(PagosApi, Resp(201, {}), Resp(200, {}))
    g.registrar(1, "tarjeta"); g.reembolsar(1)
    assert http.llamadas[0][3] == {"id_pedido": 1, "metodo": "tarjeta"}
    g, http = api(PagosApi, Resp(201, {}))
    g.registrar(1, "efectivo", monto=398.5)
    assert http.llamadas[0][3] == {"id_pedido": 1, "metodo": "efectivo", "monto": 398.5}
