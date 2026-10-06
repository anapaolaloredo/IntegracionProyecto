from unittest.mock import patch

import pytest

import service
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, crear_token, decodificar
from errors import SesionInvalida

USUARIO = {"id_usuario": 5, "correo": "a@b.co", "rol": "cliente", "nombre": "Ana"}
ADMIN = {"id_usuario": 1, "correo": "r@b.co", "rol": "admin", "nombre": "Root"}


def test_verificar_login_emite_acceso_y_refresh():
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=USUARIO), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado"), \
         patch.object(service, "verificar_codigo", return_value=True):
        tokens = service.verificar_login("a@b.co", "123456")
    acceso = decodificar(tokens["session_token"], "access")
    refresh = decodificar(tokens["refresh_token"], "refresh")
    assert acceso["user_id"] == 5 and acceso["role_id"] == ROLE_USER
    assert acceso["exp"] - acceso["iat"] == 30 * 60
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 3600


def test_admin_recibe_role_id_1():
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=ADMIN), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado"), \
         patch.object(service, "verificar_codigo", return_value=True):
        tokens = service.verificar_login("r@b.co", "123456")
    assert decodificar(tokens["session_token"])["role_id"] == ROLE_ADMIN


def test_consultar_sesion_valida_localmente():
    token = crear_token(5, ROLE_USER, "access", 600)
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        estado = service.consultar_sesion(token)
    assert estado["autenticado"] is True and estado["email"] == "a@b.co"
    assert 590 <= estado["segundos_restantes"] <= 600 and estado["role_id"] == ROLE_USER


@pytest.mark.parametrize("token", [None, "", "basura", "a.b.c"])
def test_consultar_sesion_token_invalido_no_autenticado(token):
    assert service.consultar_sesion(token) == {"autenticado": False}


def test_consultar_sesion_expirado_no_autenticado():
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "access", -5)) == {"autenticado": False}


def test_consultar_sesion_refresh_no_cuenta():
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "refresh", 600)) == {"autenticado": False}


def test_extender_emite_token_nuevo():
    viejo = crear_token(5, ROLE_USER, "access", 60)
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        resp = service.extender_sesion(viejo)
    assert decodificar(resp["session_token"])["user_id"] == 5
    assert 1790 <= resp["segundos_restantes"] <= 1800


def test_extender_con_token_expirado_o_refresh_falla():
    for malo in (crear_token(5, ROLE_USER, "access", -5), crear_token(5, ROLE_USER, "refresh", 600), None):
        with pytest.raises(SesionInvalida):
            service.extender_sesion(malo)


def test_refrescar_canjea_refresh_por_acceso_con_rol_actual():
    refresh = crear_token(5, ROLE_USER, "refresh", 600)
    promovido = dict(USUARIO, rol="admin")
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=promovido):
        resp = service.refrescar_sesion(refresh)
    assert decodificar(resp["session_token"])["role_id"] == ROLE_ADMIN


def test_refrescar_rechaza_un_token_de_acceso():
    with pytest.raises(SesionInvalida):
        service.refrescar_sesion(crear_token(5, ROLE_USER, "access", 600))


def test_refrescar_usuario_borrado_falla():
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=None):
        with pytest.raises(SesionInvalida):
            service.refrescar_sesion(crear_token(5, ROLE_USER, "refresh", 600))


def test_cerrar_sesion_exige_token_valido():
    service.cerrar_sesion(crear_token(5, ROLE_USER, "access", 60))
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion("basura")


def test_rutas_http():
    import app as login_app
    c = login_app.app.test_client()
    assert c.post("/session/extend?format=json").status_code == 401
    assert c.post("/session/refresh?format=json", json={}).status_code == 401
    assert c.post("/session/refresh?format=json", json={"refresh_token": "x"}).status_code == 401
    assert c.post("/logout?format=json").status_code == 401
    assert c.get("/session?format=json").get_json() == {"autenticado": False}
