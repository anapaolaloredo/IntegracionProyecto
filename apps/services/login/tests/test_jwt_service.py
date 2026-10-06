from unittest.mock import patch

import pytest

import service
from common import redis_store
from common.jwt_auth import ROLE_ADMIN, ROLE_USER, crear_token, decodificar
from errors import SesionInvalida

USUARIO = {"id_usuario": 5, "correo": "a@b.co", "rol": "cliente", "nombre": "Ana"}
ADMIN = {"id_usuario": 1, "correo": "r@b.co", "rol": "admin", "nombre": "Root"}


def _login(usuario=USUARIO):
    pendiente = {"id_codigo": 1, "codigo_hash": "h"}
    with patch.object(service.repository, "obtener_usuario_por_correo", return_value=usuario), \
         patch.object(service.repository, "obtener_codigo_vigente", return_value=pendiente), \
         patch.object(service.repository, "marcar_codigo_usado"), \
         patch.object(service, "verificar_codigo", return_value=True):
        return service.verificar_login(usuario["correo"], "123456")


def test_verificar_login_emite_acceso_y_refresh_con_ttl():
    tokens = _login()
    acceso = decodificar(tokens["session_token"], "access")
    refresh = decodificar(tokens["refresh_token"], "refresh")
    assert acceso["user_id"] == 5 and acceso["role_id"] == ROLE_USER
    assert acceso["exp"] - acceso["iat"] == 30 * 60
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 3600
    assert acceso["jti"] != refresh["jti"]


def test_verificar_login_guarda_sesion_y_refresh_en_redis():
    tokens = _login()
    acceso = decodificar(tokens["session_token"])
    refresh = decodificar(tokens["refresh_token"], "refresh")
    sesion = redis_store.obtener_sesion(acceso["jti"])
    assert sesion["user_id"] == 5 and sesion["email"] == "a@b.co"
    assert sesion["jti_refresh"] == refresh["jti"] and sesion["exp_refresh"] == refresh["exp"]
    assert redis_store.refresh_vigente(refresh["jti"]) is True
    assert 1790 <= redis_store.cliente().ttl(f"session:{acceso['jti']}") <= 1800
    assert redis_store.cliente().ttl(f"refresh:{refresh['jti']}") > 604000


def test_admin_recibe_role_id_1():
    assert decodificar(_login(ADMIN)["session_token"])["role_id"] == ROLE_ADMIN


def test_consultar_sesion_valida():
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        estado = service.consultar_sesion(tokens["session_token"])
    assert estado["autenticado"] is True and estado["email"] == "a@b.co" and estado["role_id"] == ROLE_USER
    assert 1790 <= estado["segundos_restantes"] <= 1800


@pytest.mark.parametrize("token", [None, "", "basura", "a.b.c"])
def test_consultar_sesion_token_invalido_no_autenticado(token):
    assert service.consultar_sesion(token) == {"autenticado": False}


def test_consultar_sesion_expirado_o_refresh_no_autenticado():
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "access", -5)) == {"autenticado": False}
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "refresh", 600)) == {"autenticado": False}


def test_consultar_sesion_jwt_valido_sin_sesion_en_redis_no_autenticado():
    # firma correcta pero la sesion no existe (nunca se creo o ya expiro en Redis)
    assert service.consultar_sesion(crear_token(5, ROLE_USER, "access", 600)) == {"autenticado": False}


def test_extender_emite_token_nuevo_y_revoca_el_anterior():
    tokens = _login()
    viejo = decodificar(tokens["session_token"])
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        resp = service.extender_sesion(tokens["session_token"])
    nuevo = decodificar(resp["session_token"])
    assert nuevo["jti"] != viejo["jti"] and 1790 <= resp["segundos_restantes"] <= 1800
    assert redis_store.jti_revocado(viejo["jti"]) is True
    assert redis_store.obtener_sesion(viejo["jti"]) is None
    assert redis_store.obtener_sesion(nuevo["jti"])["jti_refresh"] == \
        decodificar(tokens["refresh_token"], "refresh")["jti"]


def test_extender_con_token_expirado_refresh_o_revocado_falla():
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        service.extender_sesion(tokens["session_token"])
        for malo in (crear_token(5, ROLE_USER, "access", -5), tokens["refresh_token"], None,
                     tokens["session_token"]):  # el ultimo ya fue revocado por el extend anterior
            with pytest.raises(SesionInvalida):
                service.extender_sesion(malo)


def test_refrescar_canjea_refresh_por_acceso_con_rol_actual():
    tokens = _login()
    promovido = dict(USUARIO, rol="admin")
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=promovido):
        resp = service.refrescar_sesion(tokens["refresh_token"])
    assert decodificar(resp["session_token"])["role_id"] == ROLE_ADMIN


def test_refrescar_rechaza_acceso_y_refresh_desconocido():
    with pytest.raises(SesionInvalida):
        service.refrescar_sesion(crear_token(5, ROLE_USER, "access", 600))
    with pytest.raises(SesionInvalida):  # firma valida pero no esta en Redis
        service.refrescar_sesion(crear_token(5, ROLE_USER, "refresh", 600))


def test_refrescar_usuario_borrado_falla():
    tokens = _login()
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=None):
        with pytest.raises(SesionInvalida):
            service.refrescar_sesion(tokens["refresh_token"])


def test_logout_borra_sesion_y_refresh_y_revoca_ambos():
    tokens = _login()
    acceso = decodificar(tokens["session_token"])
    refresh = decodificar(tokens["refresh_token"], "refresh")
    service.cerrar_sesion(tokens["session_token"])
    assert redis_store.obtener_sesion(acceso["jti"]) is None
    assert redis_store.refresh_vigente(refresh["jti"]) is False
    assert redis_store.jti_revocado(acceso["jti"]) is True
    assert redis_store.jti_revocado(refresh["jti"]) is True


def test_token_cerrado_ya_no_sirve_para_nada():
    tokens = _login()
    service.cerrar_sesion(tokens["session_token"])
    with patch.object(service.repository, "obtener_usuario_por_id", return_value=USUARIO):
        assert service.consultar_sesion(tokens["session_token"]) == {"autenticado": False}
        with pytest.raises(SesionInvalida):
            service.extender_sesion(tokens["session_token"])
        with pytest.raises(SesionInvalida):
            service.refrescar_sesion(tokens["refresh_token"])
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion(tokens["session_token"])


def test_cerrar_sesion_exige_token_valido():
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion("basura")
    with pytest.raises(SesionInvalida):
        service.cerrar_sesion(None)
