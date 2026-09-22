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
from ui.async_task import ejecutar
from ui.common import RegistroHttp, texto_error
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


class Controlador:
    """Mantiene la configuracion, los clientes HTTP y la sesion; decide que
    ventana se muestra."""

    def __init__(self):
        self.config = AppConfig.load()
        self.registro = RegistroHttp()
        self.ventana = None
        self._construir_clientes()

    def _construir_clientes(self):
        log = self.registro.entrada.emit
        self.http_login = HttpClient("Login", self.config.login_url, self.config.timeout, log)
        self.http_libros = HttpClient("Libros", self.config.books_url, self.config.timeout, log)
        self.auth = AuthApi(self.http_login)
        self.libros = BooksApi(self.http_libros)

    def aplicar_config(self, config):
        self.config = config
        self._construir_clientes()

    def iniciar(self):
        guardada = session_store.cargar()
        if not guardada:
            self.mostrar_login()
            return
        self.mostrar_login(email=guardada.get("email", ""))
        login = self.ventana
        login.mensaje.setText("Validando la sesión guardada con el servidor…")
        token = guardada["token"]

        def fallo(exc):
            if self.ventana is login:
                self.mostrar_login("No se pudo validar la sesión guardada: " + texto_error(exc),
                                   guardada.get("email", ""))

        ejecutar(lambda: self.auth.consultar_sesion(token),
                 lambda datos: self._validada(datos, guardada, login), fallo)

    def _validada(self, datos, guardada, login):
        if self.ventana is not login:
            return  # el usuario ya inicio sesion manualmente mientras se validaba
        if datos.get("autenticado"):
            self.sesion_iniciada(guardada["token"], guardada.get("email") or datos.get("email", ""))
        else:
            session_store.borrar()
            self.mostrar_login("Tu sesión guardada ya no es válida en el servidor (expiró o se cerró). "
                               "Inicia sesión de nuevo.", guardada.get("email", ""))

    def _cambiar_ventana(self, nueva):
        anterior, self.ventana = self.ventana, nueva
        nueva.show()
        if anterior is not None:
            anterior.close()
            anterior.deleteLater()

    def mostrar_login(self, mensaje=None, email=""):
        login = LoginWindow(self, mensaje, email)
        login.autenticado.connect(self.sesion_iniciada)
        self._cambiar_ventana(login)

    def sesion_iniciada(self, token, email):
        try:
            session_store.guardar(token, email)
        except OSError:
            pass  # sin disco la app funciona igual; solo no recordara la sesion
        self._cambiar_ventana(MainWindow(self, token, email))

    def sesion_cerrada(self, ventana, motivo=None, error=True):
        if ventana is not self.ventana:
            return
        session_store.borrar()
        self.mostrar_login(motivo)
        if motivo and not error:
            self.ventana.mensaje.setStyleSheet("color: #2e7d32;")


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
