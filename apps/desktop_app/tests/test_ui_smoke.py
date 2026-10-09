"""Pruebas de las pestanas con la interfaz en modo offscreen y APIs falsas
(no tocan la red ni los microservicios)."""

from tests.conftest import esperar
from core.http import ServiceError, SesionExpirada
from ui.crud_base import CrudTab


class Demo(CrudTab):
    def __init__(self, c):
        super().__init__(c, ["ID", "Nombre"])


def test_llenar_tabla_y_seleccion(ctrl, qapp):
    t = Demo(ctrl)
    t.llenar_tabla([["1", "A"], ["2", "B"]], [1, 2])
    t.tabla.selectRow(1)
    assert t.id_seleccionado() == 2


def test_llamar_exito_ejecuta_callback(ctrl, qapp):
    t, vistos = Demo(ctrl), []
    t.llamar("GET", lambda: 41 + 1, vistos.append)
    assert esperar(qapp, lambda: vistos == [42])


def test_llamar_error_de_servicio_muestra_mensaje_sin_cerrar_sesion(ctrl, qapp):
    t = Demo(ctrl)

    def falla():
        raise ServiceError("Stock insuficiente (HTTP 409)", status=409)

    t.llamar("POST", falla, lambda _: None)
    assert esperar(qapp, lambda: "Stock insuficiente" in t.mensaje.text())
    assert not hasattr(ctrl.ventana, "motivo")


def test_llamar_sesion_expirada_intenta_renovar(ctrl, qapp):
    t = Demo(ctrl)

    def vence():
        raise SesionExpirada("expiro", status=401)

    t.llamar("GET", vence, lambda _: None)
    assert esperar(qapp, lambda: ctrl.ventana.renovaciones == 1)
    assert "renovó" in t.mensaje.text()


def test_solo_admin_deshabilita_para_cliente(ctrl_cliente, qapp):
    from PySide6.QtWidgets import QPushButton
    t = Demo(ctrl_cliente)
    b = QPushButton("Borrar")
    t.solo_admin(b)
    t.refrescar_permisos()
    assert not b.isEnabled() and "administrador" in b.toolTip().lower()


def test_admin_habilita(ctrl, qapp):
    from PySide6.QtWidgets import QPushButton
    t = Demo(ctrl)
    b = QPushButton("Borrar")
    t.solo_admin(b)
    t.refrescar_permisos()
    assert b.isEnabled()


def test_invitado_en_seccion_con_sesion_ve_aviso(ctrl_invitado, qapp):
    t = Demo(ctrl_invitado)
    t.refrescar_permisos()
    assert "Inicia sesión" in t.mensaje.text() and not t.tabla.isEnabled()
