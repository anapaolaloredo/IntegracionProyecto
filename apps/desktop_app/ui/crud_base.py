"""Base de las pestanas CRUD (Usuarios, Autores, Pedidos, Pagos): tabla, hilos,
errores del servidor (401/403/409/503) y permisos por rol en un solo lugar.

Las subclases arman su propio layout con self.tabla, self.mensaje y self.btn_login."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QWidget

from core.http import SesionExpirada
from ui.async_task import ejecutar
from ui.common import poner_mensaje, texto_error


class CrudTab(QWidget):
    requiere_sesion = True  # False en Autores: la lectura es publica
    seleccion_cambio = Signal(object)  # id del renglon seleccionado, o None

    def __init__(self, controlador, columnas):
        super().__init__()
        self.c = controlador
        self._ids = []
        self._botones = []      # se deshabilitan mientras corre una llamada o no hay sesion
        self._solo_admin = []   # ademas exigen rol admin
        self.tabla = QTableWidget(0, len(columnas))
        self.tabla.setHorizontalHeaderLabels(columnas)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.itemSelectionChanged.connect(lambda: self.seleccion_cambio.emit(self.id_seleccionado()))
        self.mensaje = QLabel(wordWrap=True)
        self.btn_login = QPushButton("Iniciar sesión")
        self.btn_login.clicked.connect(lambda: self.c.ventana.iniciar_sesion())
        self.btn_login.hide()

    # ---- tabla ----
    def llenar_tabla(self, filas, ids):
        self.tabla.clearSelection()
        self.tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, valor in enumerate(fila):
                self.tabla.setItem(i, j, QTableWidgetItem("" if valor is None else str(valor)))
        self._ids = list(ids)

    def id_seleccionado(self):
        filas = {i.row() for i in self.tabla.selectedIndexes()}
        if len(filas) != 1:
            return None
        fila = filas.pop()
        return self._ids[fila] if fila < len(self._ids) else None

    # ---- mensajes ----
    def ok(self, texto):
        poner_mensaje(self.mensaje, texto)

    def error(self, texto):
        poner_mensaje(self.mensaje, texto, error=True)

    # ---- permisos ----
    def es_admin(self):
        return self.c.es_admin()

    def hay_sesion(self):
        return bool(self.c.token_sesion)

    def registrar(self, *botones):
        self._botones.extend(botones)

    def solo_admin(self, *widgets):
        self._solo_admin.extend(widgets)

    def refrescar_permisos(self):
        sesion = self.hay_sesion() or not self.requiere_sesion
        self.tabla.setEnabled(sesion)
        self.btn_login.setVisible(not sesion)
        if not sesion:
            self.error("Inicia sesión para usar esta sección.")
        admin = self.es_admin()
        for b in self._botones:
            b.setEnabled(sesion)
        for w in self._solo_admin:
            w.setEnabled(sesion and admin)
            w.setToolTip("" if admin else "Solo administradores")

    def al_activar(self):
        """La ventana lo llama al mostrar la pestana: las subclases recargan sus datos."""

    # ---- llamadas ----
    def llamar(self, etiqueta, funcion, exito):
        for w in self._botones + self._solo_admin:
            w.setEnabled(False)
        poner_mensaje(self.mensaje, f"Enviando {etiqueta}…")

        def listo(resultado):
            self.refrescar_permisos()
            exito(resultado)

        def fallo(exc):
            self.refrescar_permisos()
            if isinstance(exc, SesionExpirada):
                self._sesion_expirada(exc)
                return
            self.error(f"{etiqueta} falló: {texto_error(exc)}")

        ejecutar(funcion, listo, fallo)

    def _sesion_expirada(self, exc):
        ventana = self.c.ventana
        if getattr(ventana, "invitado", True) or not hasattr(ventana, "renovar_token"):
            ventana.sesion_requerida(str(exc))
            return
        ventana.renovar_token(
            lambda: self.ok("Tu sesión se renovó automáticamente. Repite la operación."),
            lambda: ventana.sesion_requerida(str(exc)))
