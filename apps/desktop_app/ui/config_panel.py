"""Pantalla de configuracion del servidor: modificar, probar, guardar y
restaurar las URLs de los microservicios."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from core.config import AppConfig, config_dir, normalizar_url
from core.health import comprobar_libros, comprobar_login
from core.http import HttpClient
from ui.async_task import ejecutar
from ui.common import TEXTOS, Semaforo, poner_mensaje


class ConfigPanel(QWidget):
    guardada = Signal(object)  # AppConfig

    def __init__(self, config, on_log=None):
        super().__init__()
        self.on_log = on_log
        self.login_url = QLineEdit()
        self.books_url = QLineEdit()
        self.timeout = QSpinBox(minimum=1, maximum=60, suffix=" s")
        self.intervalo = QSpinBox(minimum=5, maximum=3600, suffix=" s")
        self.login_url.setPlaceholderText("http://IP_DE_LA_INSTANCIA:5000")
        self.books_url.setPlaceholderText("http://IP_DE_LA_INSTANCIA:5001")

        form = QFormLayout()
        form.addRow("URL microservicio de Login:", self.login_url)
        form.addRow("URL microservicio de Libros:", self.books_url)
        form.addRow("Tiempo de espera por petición:", self.timeout)
        form.addRow("Comprobar estado cada:", self.intervalo)

        self.sem_login, self.txt_login = Semaforo(), QLabel("Sin probar")
        self.sem_libros, self.txt_libros = Semaforo(), QLabel("Sin probar")
        for t in (self.txt_login, self.txt_libros):
            t.setWordWrap(True)
        prueba = QFormLayout()
        prueba.addRow(self._fila(self.sem_login, self.txt_login, "Login"))
        prueba.addRow(self._fila(self.sem_libros, self.txt_libros, "Libros"))
        caja_prueba = QGroupBox("Resultado de la prueba")
        caja_prueba.setLayout(prueba)

        self.btn_probar = QPushButton("Probar conexión")
        btn_guardar = QPushButton("Guardar")
        btn_restaurar = QPushButton("Restaurar predeterminados")
        self.btn_probar.clicked.connect(self.probar)
        btn_guardar.clicked.connect(self.guardar)
        btn_restaurar.clicked.connect(self.restaurar)
        botones = QHBoxLayout()
        for b in (self.btn_probar, btn_guardar, btn_restaurar):
            botones.addWidget(b)
        botones.addStretch()

        self.mensaje = QLabel(wordWrap=True)
        ruta = QLabel(f"Se guarda en: {config_dir() / 'config.json'}")
        ruta.setStyleSheet("color: gray;")

        capa = QVBoxLayout(self)
        capa.addLayout(form)
        capa.addLayout(botones)
        capa.addWidget(self.mensaje)
        capa.addWidget(caja_prueba)
        capa.addWidget(ruta)
        capa.addStretch()
        self.cargar(config)

    @staticmethod
    def _fila(semaforo, texto, nombre):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(semaforo)
        h.addWidget(QLabel(f"<b>{nombre}:</b>"))
        h.addWidget(texto, 1)
        return w

    def cargar(self, config):
        self.login_url.setText(config.login_url)
        self.books_url.setText(config.books_url)
        self.timeout.setValue(config.timeout)
        self.intervalo.setValue(config.health_interval)

    def _desde_formulario(self):
        return AppConfig(
            login_url=normalizar_url(self.login_url.text()),
            books_url=normalizar_url(self.books_url.text()),
            timeout=self.timeout.value(),
            health_interval=self.intervalo.value(),
        )

    def probar(self):
        config = self._desde_formulario()
        errores = config.validar()
        if errores:
            poner_mensaje(self.mensaje, " ".join(errores), error=True)
            return
        self.btn_probar.setEnabled(False)
        poner_mensaje(self.mensaje, "Probando con los valores del formulario (aún sin guardar)…")
        http_login = HttpClient("Login", config.login_url, config.timeout, self.on_log)
        http_libros = HttpClient("Libros", config.books_url, config.timeout, self.on_log)
        ejecutar(lambda: (comprobar_login(http_login), comprobar_libros(http_libros)),
                 self._resultado_prueba, self._fallo_prueba)

    def _resultado_prueba(self, resultados):
        self.btn_probar.setEnabled(True)
        for (sem, txt), r in zip(((self.sem_login, self.txt_login), (self.sem_libros, self.txt_libros)), resultados):
            sem.set_estado(r.estado)
            txt.setText(f"{TEXTOS[r.estado]} — {r.detalle}")
        poner_mensaje(self.mensaje, "Prueba terminada.")

    def _fallo_prueba(self, exc):
        self.btn_probar.setEnabled(True)
        poner_mensaje(self.mensaje, f"No se pudo probar: {exc}", error=True)

    def guardar(self):
        config = self._desde_formulario()
        errores = config.validar()
        if errores:
            poner_mensaje(self.mensaje, " ".join(errores), error=True)
            return
        try:
            config.save()
        except OSError as exc:
            poner_mensaje(self.mensaje, f"No se pudo guardar la configuración: {exc}", error=True)
            return
        self.cargar(config)
        poner_mensaje(self.mensaje, "Configuración guardada. Se usará en todas las peticiones a partir de ahora.")
        self.guardada.emit(config)

    def restaurar(self):
        self.cargar(AppConfig.defaults())
        poner_mensaje(self.mensaje, "Se cargaron los valores predeterminados. Presiona Guardar para aplicarlos.")
