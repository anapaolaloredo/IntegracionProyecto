"""Punto de entrada de la aplicacion de escritorio.

Uso:
    cd apps/desktop_app
    python -m venv .venv && source .venv/bin/activate   (Windows: .venv\\Scripts\\activate)
    pip install -r requirements.txt
    python main.py"""

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from core import session_store
from core.auth_api import AuthApi
from core.books_api import BooksApi
from core.config import AppConfig
from core.http import HttpClient
from ui.common import RegistroHttp, poner_mensaje, texto_error
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


class Controlador:
    """Mantiene la configuracion, los clientes HTTP y la sesion; decide que
    ventana se muestra."""

    def __init__(self):
        self.config = AppConfig.load()
        self.registro = RegistroHttp()
        self.ventana = None
        self.token_sesion = None
        self._construir_clientes()

    def _construir_clientes(self):
        log = self.registro.entrada.emit
        self.http_login = HttpClient("Login", self.config.login_url, self.config.timeout, log)
        self.http_libros = HttpClient("Libros", self.config.books_url, self.config.timeout, log)
        self.auth = AuthApi(self.http_login)
        self.libros = BooksApi(self.http_libros, lambda: self.token_sesion)

    def aplicar_config(self, config):
        self.config = config
        self._construir_clientes()

    def iniciar(self):
        """El catalogo es publico: sin sesion guardada se abre como invitado. Con una sesion
        guardada se abre con su token y la propia ventana la valida contra el servidor."""
        guardada = session_store.cargar()
        if guardada:
            self.sesion_iniciada(guardada["token"], guardada.get("email", ""))
        else:
            self.mostrar_invitado()

    def _cambiar_ventana(self, nueva):
        anterior, self.ventana = self.ventana, nueva
        nueva.show()
        if anterior is not None:
            anterior.close()
            anterior.deleteLater()

    def mostrar_login(self, mensaje=None, email=""):
        login = LoginWindow(self, mensaje, email)
        login.autenticado.connect(self.sesion_iniciada)
        login.invitado.connect(self.mostrar_invitado)
        self._cambiar_ventana(login)

    def mostrar_invitado(self, mensaje=None, error=True):
        """Ventana principal sin sesion: solo lecturas publicas."""
        self.token_sesion = None
        self._cambiar_ventana(MainWindow(self, None, None))
        if mensaje:
            poner_mensaje(self.ventana.sesion.mensaje, mensaje, error=error)

    def pedir_login(self, mensaje=None):
        self.mostrar_login(mensaje)

    def sesion_iniciada(self, token, email):
        self.token_sesion = token
        try:
            session_store.guardar(token, email)
        except OSError:
            pass  # sin disco la app funciona igual; solo no recordara la sesion
        self._cambiar_ventana(MainWindow(self, token, email))

    def sesion_cerrada(self, ventana, motivo=None, error=True):
        if ventana is not self.ventana:
            return
        session_store.borrar()
        self.mostrar_invitado(motivo, error)


def manejador_global(tipo, valor, tb):
    """Ultima red de seguridad: registra el traceback en consola y muestra un
    mensaje comprensible en lugar de cerrar la aplicacion."""
    traceback.print_exception(tipo, valor, tb)
    if QApplication.instance():
        QMessageBox.critical(None, "Error inesperado",
                             "Ocurrió un error inesperado, pero la aplicación sigue abierta.\n\n"
                             f"Detalle: {texto_error(valor)}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Librería Escritorio")
    sys.excepthook = manejador_global
    controlador = Controlador()
    controlador.iniciar()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
