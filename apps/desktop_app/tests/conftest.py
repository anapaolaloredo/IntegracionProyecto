import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeVentana:
    invitado = False

    def __init__(self):
        self.pidio_login = 0
        self.renovaciones = 0

    def iniciar_sesion(self):
        self.pidio_login += 1

    def sesion_requerida(self, motivo):
        self.motivo = motivo

    def renovar_token(self, ok, fallo):
        self.renovaciones += 1
        ok()


class FakeControlador:
    """Controlador minimo para las pestanas: las APIs falsas se asignan en cada prueba."""

    def __init__(self, role_id=1, user_id=1, token="TOK"):
        self.role_id, self.user_id, self.token_sesion = role_id, user_id, token
        self.ventana = FakeVentana()

    def es_admin(self):
        return self.role_id == 1


@pytest.fixture
def ctrl(qapp):
    return FakeControlador()


@pytest.fixture
def ctrl_cliente(qapp):
    return FakeControlador(role_id=2, user_id=7)


@pytest.fixture
def ctrl_invitado(qapp):
    c = FakeControlador(role_id=None, user_id=None, token=None)
    c.ventana.invitado = True
    return c


def esperar(qapp, condicion, ms=3000):
    """Procesa eventos hasta que condicion() sea verdadera (los hilos entregan por senales)."""
    fin = time.monotonic() + ms / 1000
    while time.monotonic() < fin:
        qapp.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return False
