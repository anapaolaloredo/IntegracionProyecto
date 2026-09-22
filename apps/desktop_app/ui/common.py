"""Utilidades compartidas por las pantallas: mensajes de error legibles,
semaforo de estado y registro de peticiones HTTP."""

import json
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from core.health import CAIDO, DEGRADADO, OK
from core.http import ServiceError

COLORES = {OK: "#2e7d32", DEGRADADO: "#f9a825", CAIDO: "#c62828", None: "#9e9e9e"}
TEXTOS = {OK: "Funcionando", DEGRADADO: "Degradado", CAIDO: "Sin conexión", None: "Sin comprobar"}
ESTILO_ERROR = "color: #c62828;"
ESTILO_OK = "color: #2e7d32;"


def texto_error(exc):
    """Nunca un traceback: ServiceError ya trae un mensaje para el usuario."""
    if isinstance(exc, ServiceError):
        return str(exc)
    return f"Ocurrió un error inesperado ({exc.__class__.__name__}: {exc})."


def mostrar_error(padre, titulo, exc):
    QMessageBox.warning(padre, titulo, texto_error(exc))


def poner_mensaje(etiqueta, texto, error=False):
    etiqueta.setStyleSheet(ESTILO_ERROR if error else ESTILO_OK)
    etiqueta.setText(texto)


class Semaforo(QLabel):
    def __init__(self, tamano=14):
        super().__init__()
        self.tamano = tamano
        self.setFixedSize(tamano, tamano)
        self.set_estado(None)

    def set_estado(self, estado):
        self.setStyleSheet(f"background: {COLORES[estado]}; border-radius: {self.tamano // 2}px;")
        self.setToolTip(TEXTOS[estado])


class RegistroHttp(QObject):
    """Puente thread-safe: HttpClient llama emit() desde hilos del pool y la
    senal se entrega en el hilo de la UI."""
    entrada = Signal(dict)


class RegistroHttpWidget(QWidget):
    def __init__(self, registro):
        super().__init__()
        self.texto = QPlainTextEdit(readOnly=True)
        self.texto.setMaximumBlockCount(600)
        self.texto.setPlaceholderText("Aquí aparece cada petición HTTP: método, URL, cuerpo enviado y status.")
        limpiar = QPushButton("Limpiar registro")
        limpiar.clicked.connect(self.texto.clear)
        barra = QHBoxLayout()
        barra.addStretch()
        barra.addWidget(limpiar)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(4, 4, 4, 4)
        capa.addWidget(self.texto)
        capa.addLayout(barra)
        registro.entrada.connect(self.agregar)

    def agregar(self, e):
        hora = datetime.now().strftime("%H:%M:%S")
        url = e["url"]
        if e.get("params"):
            url += "?" + "&".join(f"{k}={v}" for k, v in e["params"].items())
        resultado = f"→ {e['status']}" if e.get("status") else f"→ SIN RESPUESTA: {e.get('error')}"
        lineas = [f"{hora}  [{e['servicio']}]  {e['metodo']} {url}  {resultado}  ({e['ms']} ms)"]
        if e.get("body") is not None:
            cuerpo = json.dumps(e["body"], ensure_ascii=False)
            if "password" in e["body"]:
                cuerpo = json.dumps({**e["body"], "password": "********"}, ensure_ascii=False)
            lineas.append("          cuerpo enviado: " + (cuerpo if len(cuerpo) < 700 else cuerpo[:700] + "…"))
        self.texto.appendPlainText("\n".join(lineas))
