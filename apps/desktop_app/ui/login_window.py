"""Ventana de acceso: registro e inicio de sesion con 2FA.

Paso 1: correo + contrasena (POST /login) -> el servicio envia un codigo al
buzon local de la instancia. Paso 2: codigo (POST /login/verify) -> token."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from core.config import validar_url
from ui.async_task import ejecutar
from ui.common import poner_mensaje, texto_error
from ui.config_panel import ConfigPanel


class LoginWindow(QWidget):
    autenticado = Signal(str, str)  # token, email

    def __init__(self, controlador, mensaje_inicial=None, email_inicial=""):
        super().__init__()
        self.c = controlador
        self.setWindowTitle("Librería — Acceso")
        self.resize(460, 420)

        titulo = QLabel("<h2>Librería</h2>Cliente de escritorio de los microservicios")
        titulo.setAlignment(Qt.AlignCenter)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._crear_login(email_inicial), "Iniciar sesión")
        self.tabs.addTab(self._crear_registro(), "Registrarse")

        self.mensaje = QLabel(wordWrap=True)
        self.servidor = QLabel()
        self.servidor.setStyleSheet("color: gray;")
        btn_config = QPushButton("Configuración del servidor…")
        btn_config.clicked.connect(self._abrir_config)
        pie = QHBoxLayout()
        pie.addWidget(self.servidor, 1)
        pie.addWidget(btn_config)

        capa = QVBoxLayout(self)
        capa.addWidget(titulo)
        capa.addWidget(self.tabs)
        capa.addWidget(self.mensaje)
        capa.addLayout(pie)
        self._actualizar_servidor()
        if mensaje_inicial:
            poner_mensaje(self.mensaje, mensaje_inicial, error=True)

    # ---- inicio de sesion (2 pasos) ----
    def _crear_login(self, email_inicial):
        self.pasos = QStackedWidget()

        paso1 = QWidget()
        self.email = QLineEdit(email_inicial, placeholderText="correo@ejemplo.com")
        self.password = QLineEdit(echoMode=QLineEdit.Password)
        self.btn_entrar = QPushButton("Continuar")
        self.btn_entrar.setDefault(True)
        self.btn_entrar.clicked.connect(self._enviar_credenciales)
        self.password.returnPressed.connect(self._enviar_credenciales)
        f1 = QFormLayout(paso1)
        f1.addRow("Correo:", self.email)
        f1.addRow("Contraseña:", self.password)
        f1.addRow(self.btn_entrar)

        paso2 = QWidget()
        self.aviso_codigo = QLabel(wordWrap=True)
        self.codigo = QLineEdit(placeholderText="123456", maxLength=6)
        self.btn_verificar = QPushButton("Verificar código")
        self.btn_verificar.clicked.connect(self._verificar_codigo)
        self.codigo.returnPressed.connect(self._verificar_codigo)
        btn_reenviar = QPushButton("Enviar otro código")
        btn_reenviar.clicked.connect(self._enviar_credenciales)
        btn_volver = QPushButton("Volver")
        btn_volver.clicked.connect(lambda: self.pasos.setCurrentIndex(0))
        otros = QHBoxLayout()
        otros.addWidget(btn_reenviar)
        otros.addWidget(btn_volver)
        f2 = QFormLayout(paso2)
        f2.addRow(self.aviso_codigo)
        f2.addRow("Código:", self.codigo)
        f2.addRow(self.btn_verificar)
        f2.addRow(otros)

        self.pasos.addWidget(paso1)
        self.pasos.addWidget(paso2)
        return self.pasos

    def _enviar_credenciales(self):
        email, password = self.email.text().strip(), self.password.text()
        if not email or not password:
            poner_mensaje(self.mensaje, "Escribe tu correo y contraseña.", error=True)
            return
        self._ocupado(True, "Validando credenciales…")
        ejecutar(lambda: self.c.auth.iniciar_login(email, password), self._codigo_enviado, self._fallo)

    def _codigo_enviado(self, _):
        self._ocupado(False)
        self.aviso_codigo.setText(
            "Tu cuenta aún no está autenticada: falta el segundo paso. Se envió un código de 6 dígitos "
            "(válido 5 minutos) al buzón local de la instancia del servidor. Revísalo en la instancia con:\n"
            "  sudo tail -20 /var/mail/<usuario>")
        self.codigo.clear()
        self.pasos.setCurrentIndex(1)
        self.codigo.setFocus()
        poner_mensaje(self.mensaje, "Credenciales correctas. Falta verificar el código.")

    def _verificar_codigo(self):
        email, codigo = self.email.text().strip(), self.codigo.text().strip()
        if not codigo.isdigit() or len(codigo) != 6:
            poner_mensaje(self.mensaje, "El código debe tener 6 dígitos.", error=True)
            return
        self._ocupado(True, "Verificando código…")
        ejecutar(lambda: self.c.auth.verificar_codigo(email, codigo),
                 lambda token: self.autenticado.emit(token, email), self._fallo)

    # ---- registro ----
    def _crear_registro(self):
        w = QWidget()
        self.r_nombre = QLineEdit()
        self.r_paterno = QLineEdit()
        self.r_materno = QLineEdit()
        self.r_email = QLineEdit(placeholderText="correo@ejemplo.com")
        self.r_password = QLineEdit(echoMode=QLineEdit.Password, placeholderText="mínimo 8 caracteres")
        self.r_confirmar = QLineEdit(echoMode=QLineEdit.Password)
        self.btn_registrar = QPushButton("Crear cuenta")
        self.btn_registrar.clicked.connect(self._registrar)
        f = QFormLayout(w)
        f.addRow("Nombre:", self.r_nombre)
        f.addRow("Apellido paterno:", self.r_paterno)
        f.addRow("Apellido materno:", self.r_materno)
        f.addRow("Correo:", self.r_email)
        f.addRow("Contraseña:", self.r_password)
        f.addRow("Confirmar contraseña:", self.r_confirmar)
        f.addRow(self.btn_registrar)
        return w

    def _registrar(self):
        campos = [self.r_nombre, self.r_paterno, self.r_materno, self.r_email, self.r_password]
        valores = [c.text().strip() for c in campos[:4]] + [self.r_password.text()]
        if not all(valores):
            poner_mensaje(self.mensaje, "Todos los campos del registro son obligatorios.", error=True)
            return
        if self.r_password.text() != self.r_confirmar.text():
            poner_mensaje(self.mensaje, "Las contraseñas no coinciden.", error=True)
            return
        if len(self.r_password.text()) < 8:
            poner_mensaje(self.mensaje, "La contraseña debe tener al menos 8 caracteres.", error=True)
            return
        self._ocupado(True, "Registrando…")
        ejecutar(lambda: self.c.auth.registrar(*valores), self._registrado, self._fallo)

    def _registrado(self, id_usuario):
        self._ocupado(False)
        self.email.setText(self.r_email.text().strip())
        for campo in (self.r_password, self.r_confirmar):
            campo.clear()
        self.tabs.setCurrentIndex(0)
        self.pasos.setCurrentIndex(0)
        self.password.setFocus()
        poner_mensaje(self.mensaje, f"Cuenta creada (id {id_usuario}). Ahora inicia sesión.")

    # ---- comun ----
    def _ocupado(self, ocupado, texto=None):
        for b in (self.btn_entrar, self.btn_verificar, self.btn_registrar):
            b.setEnabled(not ocupado)
        if texto:
            poner_mensaje(self.mensaje, texto)

    def _fallo(self, exc):
        self._ocupado(False)
        poner_mensaje(self.mensaje, texto_error(exc), error=True)

    def _actualizar_servidor(self):
        url = self.c.config.login_url
        self.servidor.setText(f"Login: {url}" + ("" if not validar_url(url) else " (inválida)"))

    def _abrir_config(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Configuración del servidor")
        dialogo.resize(560, 420)
        panel = ConfigPanel(self.c.config, self.c.registro.entrada.emit)
        panel.guardada.connect(self.c.aplicar_config)
        panel.guardada.connect(lambda _: self._actualizar_servidor())
        QVBoxLayout(dialogo).addWidget(panel)
        dialogo.exec()
