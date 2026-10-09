"""Pantalla de configuracion del servidor: URLs de los seis microservicios, radio http/https,
probar, guardar y restaurar."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                               QSpinBox, QVBoxLayout, QWidget)

from core.config import SERVICIOS, AppConfig, cambiar_esquema, config_dir, normalizar_url, validar_url
from core.health import comprobar_servicio
from core.http import HttpClient
from ui.async_task import ejecutar
from ui.common import TEXTOS, Semaforo, poner_mensaje


class ConfigPanel(QWidget):
    guardada = Signal(object)  # AppConfig

    def __init__(self, config, on_log=None):
        super().__init__()
        self.on_log = on_log
        self.campos = {}
        self.semaforos = {}
        self.textos = {}
        form = QFormLayout()
        prueba = QFormLayout()
        for clave, nombre, puerto in SERVICIOS:
            campo = QLineEdit()
            campo.setPlaceholderText(f"http://IP_DE_LA_INSTANCIA:{puerto}")
            self.campos[clave] = campo
            form.addRow(f"URL microservicio de {nombre}:", campo)
            self.semaforos[clave], self.textos[clave] = Semaforo(), QLabel("Sin probar")
            self.textos[clave].setWordWrap(True)
            prueba.addRow(self._fila(self.semaforos[clave], self.textos[clave], nombre))

        self.radio_http = QRadioButton("http (predeterminado)")
        self.radio_https = QRadioButton("https")
        self.radio_http.setChecked(True)
        self.radio_https.toggled.connect(self._protocolo_cambio)
        nota = QLabel("Al cambiar el protocolo se reescribe el esquema de las seis URLs (host y puerto no cambian). "
                      "https requiere que el servidor tenga certificado; con http el tráfico no va cifrado.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: gray;")
        fila_radio = QHBoxLayout()
        fila_radio.addWidget(self.radio_http)
        fila_radio.addWidget(self.radio_https)
        fila_radio.addStretch()
        capa_proto = QVBoxLayout()
        capa_proto.addLayout(fila_radio)
        capa_proto.addWidget(nota)
        caja_proto = QGroupBox("Protocolo de conexión")
        caja_proto.setLayout(capa_proto)

        self.timeout = QSpinBox(minimum=1, maximum=60, suffix=" s")
        self.intervalo = QSpinBox(minimum=5, maximum=3600, suffix=" s")
        form.addRow("Tiempo de espera por petición:", self.timeout)
        form.addRow("Comprobar estado cada:", self.intervalo)
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
        capa.addWidget(caja_proto)
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

    def _protocolo_cambio(self, https):
        """El radio reescribe el esquema de las seis URLs del formulario (host, puerto y ruta intactos)."""
        esquema = "https" if https else "http"
        for campo in self.campos.values():
            url = normalizar_url(campo.text())
            if url and not validar_url(url):
                campo.setText(cambiar_esquema(url, esquema))

    def cargar(self, config):
        for clave, campo in self.campos.items():
            campo.setText(config.url(clave))
        self.radio_https.blockSignals(True)  # cargar no debe reescribir las URLs guardadas
        (self.radio_https if config.protocolo == "https" else self.radio_http).setChecked(True)
        self.radio_https.blockSignals(False)
        self.timeout.setValue(config.timeout)
        self.intervalo.setValue(config.health_interval)

    def _desde_formulario(self):
        urls = {f"{clave}_url": normalizar_url(campo.text()) for clave, campo in self.campos.items()}
        return AppConfig(**urls, protocolo="https" if self.radio_https.isChecked() else "http",
                         timeout=self.timeout.value(), health_interval=self.intervalo.value())

    def probar(self):
        config = self._desde_formulario()
        errores = config.validar()
        if errores:
            poner_mensaje(self.mensaje, " ".join(errores), error=True)
            return
        self.btn_probar.setEnabled(False)
        poner_mensaje(self.mensaje, "Probando con los valores del formulario (aún sin guardar)…")
        clientes = [(clave, nombre, HttpClient(nombre, config.url(clave), config.timeout, self.on_log))
                    for clave, nombre, _ in SERVICIOS]
        ejecutar(lambda: [comprobar_servicio(http, nombre) for _, nombre, http in clientes],
                 lambda resultados: self._resultado_prueba([c for c, _, _ in clientes], resultados),
                 self._fallo_prueba)

    def _resultado_prueba(self, claves, resultados):
        self.btn_probar.setEnabled(True)
        for clave, r in zip(claves, resultados):
            self.semaforos[clave].set_estado(r.estado)
            redis = f" · Redis: {r.redis}" if r.redis else ""
            self.textos[clave].setText(f"{TEXTOS[r.estado]} — {r.detalle}{redis}")
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
        poner_mensaje(self.mensaje, "Se cargaron los valores predeterminados (http). Presiona Guardar para aplicarlos.")
