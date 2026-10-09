"""Pedidos (servicio pedidos, :5004): crear con lineas, ver, cancelar, enviar (admin) y eliminar (admin)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from core.http import ServiceError
from ui.crud_base import CrudTab

COLUMNAS = ["ID", "Fecha", "Estado", "Total", "Cuenta"]


class PedidosTab(CrudTab):
    pedido_cambio = Signal()  # un pedido se creo/cambio/elimino: el stock y los pagos pueden haber cambiado

    def __init__(self, controlador):
        super().__init__(controlador, COLUMNAS)
        self._lineas = {}  # id_libro -> [titulo, cantidad]
        self.combo_libro = QComboBox()
        self.cantidad = QSpinBox(minimum=1, maximum=9999)
        self.btn_agregar = QPushButton("Agregar línea")
        self.btn_quitar = QPushButton("Quitar línea seleccionada")
        self.tabla_lineas = QTableWidget(0, 2)
        self.tabla_lineas.setHorizontalHeaderLabels(["Libro", "Cantidad"])
        self.tabla_lineas.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_lineas.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_lineas.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_lineas.setMaximumHeight(130)
        self.btn_crear = QPushButton("Crear pedido (POST)")
        nuevo = QVBoxLayout()
        fila = QHBoxLayout()
        fila.addWidget(self.combo_libro, 1)
        fila.addWidget(QLabel("Cantidad:"))
        fila.addWidget(self.cantidad)
        fila.addWidget(self.btn_agregar)
        nuevo.addLayout(fila)
        nuevo.addWidget(self.tabla_lineas)
        pie = QHBoxLayout()
        pie.addWidget(self.btn_quitar)
        pie.addStretch()
        pie.addWidget(self.btn_crear)
        nuevo.addLayout(pie)
        caja_nuevo = QGroupBox("Nuevo pedido")
        caja_nuevo.setLayout(nuevo)

        self.detalle = QPlainTextEdit(readOnly=True)
        self.detalle.setPlaceholderText("Selecciona un pedido para ver sus líneas.")
        self.detalle.setMaximumHeight(120)

        self.btn_recargar = QPushButton("Recargar (GET)")
        self.btn_cancelar = QPushButton("Cancelar pedido (PATCH)")
        self.btn_enviar = QPushButton("Marcar enviado (PATCH)")
        self.btn_eliminar = QPushButton("Eliminar cancelado (DELETE)")
        self.btn_eliminar.setStyleSheet("color: #c62828;")
        self.registrar(self.btn_recargar, self.btn_agregar, self.btn_quitar, self.btn_crear, self.btn_cancelar)
        self.solo_admin(self.btn_enviar, self.btn_eliminar)
        self.btn_recargar.clicked.connect(self.recargar)
        self.btn_agregar.clicked.connect(self.agregar_linea)
        self.btn_quitar.clicked.connect(self.quitar_linea)
        self.btn_crear.clicked.connect(self.crear)
        self.btn_cancelar.clicked.connect(lambda: self.cambiar_estado("cancelado"))
        self.btn_enviar.clicked.connect(lambda: self.cambiar_estado("enviado"))
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.seleccion_cambio.connect(self._seleccion)

        barra = QHBoxLayout()
        for b in (self.btn_recargar, self.btn_cancelar, self.btn_enviar, self.btn_eliminar):
            barra.addWidget(b)
        capa = QVBoxLayout(self)
        capa.addWidget(self.tabla, 1)
        capa.addLayout(barra)
        capa.addWidget(self.detalle)
        capa.addWidget(caja_nuevo)
        capa.addWidget(self.mensaje)
        capa.addWidget(self.btn_login)
        self.refrescar_permisos()

    # ---- lectura ----
    def al_activar(self):
        self.recargar()

    def recargar(self):
        if not self.hay_sesion():
            self.refrescar_permisos()
            return

        def cargar():
            pedidos = self.c.pedidos.listar()
            try:
                libros = self.c.libros.listar()
            except ServiceError:
                libros = []
            return pedidos, libros

        self.llamar("GET", cargar, self._mostrar)

    def _mostrar(self, resultado):
        pedidos, libros = resultado
        self.llenar_tabla([[p["id_pedido"], p.get("fecha_creacion"), p.get("estado"), p.get("total"), p.get("id_cuenta")]
                           for p in pedidos], [p["id_pedido"] for p in pedidos])
        actual = self.combo_libro.currentData()
        self.combo_libro.clear()
        for libro in libros:
            if libro.id_libro is not None:
                self.combo_libro.addItem(f"{libro.titulo} — {libro.isbn} (stock {libro.stock})", libro.id_libro)
        indice = self.combo_libro.findData(actual)
        if indice >= 0:
            self.combo_libro.setCurrentIndex(indice)
        self.ok(f"{len(pedidos)} pedido(s).")

    def _seleccion(self, id_pedido):
        self.detalle.clear()
        if id_pedido is None:
            return
        self.llamar("GET", lambda: self.c.pedidos.obtener(id_pedido), self._detalle)

    def _detalle(self, p):
        lineas = [f"  {l.get('cantidad')} x {l.get('titulo') or l.get('id_libro')} ({l.get('isbn', '')}) "
                  f"a ${l.get('precio_unitario')}" for l in p.get("lineas", [])]
        self.detalle.setPlainText(f"Pedido {p.get('id_pedido')} — {p.get('estado')} — total ${p.get('total')}\n"
                                  + "\n".join(lineas))
        self.ok("Detalle cargado.")

    # ---- lineas del pedido nuevo ----
    def agregar_linea(self):
        id_libro = self.combo_libro.currentData()
        if id_libro is None:
            self.error("No hay libros disponibles para agregar (recarga el catálogo).")
            return
        titulo = self.combo_libro.currentText().split(" — ")[0]
        actual = self._lineas.get(id_libro, [titulo, 0])
        self._lineas[id_libro] = [titulo, actual[1] + self.cantidad.value()]
        self._pintar_lineas()

    def quitar_linea(self):
        fila = self.tabla_lineas.currentRow()
        if fila < 0:
            self.error("Selecciona la línea a quitar.")
            return
        del self._lineas[list(self._lineas)[fila]]
        self._pintar_lineas()

    def _pintar_lineas(self):
        self.tabla_lineas.setRowCount(len(self._lineas))
        for i, (titulo, cantidad) in enumerate(self._lineas.values()):
            self.tabla_lineas.setItem(i, 0, QTableWidgetItem(titulo))
            self.tabla_lineas.setItem(i, 1, QTableWidgetItem(str(cantidad)))

    # ---- escrituras ----
    def crear(self):
        if not self._lineas:
            self.error("Agrega al menos una línea al pedido.")
            return
        lineas = [{"id_libro": i, "cantidad": c[1]} for i, c in self._lineas.items()]

        def exito(p):
            self._lineas.clear()
            self._pintar_lineas()
            self.ok(f"POST correcto (201): pedido {p.get('id_pedido')} creado; el stock se descontó.")
            self.recargar()
            self.pedido_cambio.emit()

        self.llamar("POST", lambda: self.c.pedidos.crear(lineas), exito)

    def cambiar_estado(self, estado):
        id_pedido = self.id_seleccionado()
        if id_pedido is None:
            self.error("Selecciona un pedido de la tabla.")
            return

        def exito(_):
            self.ok(f"PATCH correcto (200): pedido {id_pedido} -> {estado}.")
            self.recargar()
            self.pedido_cambio.emit()

        self.llamar("PATCH", lambda: self.c.pedidos.cambiar_estado(id_pedido, estado), exito)

    def eliminar(self):
        id_pedido = self.id_seleccionado()
        if id_pedido is None:
            self.error("Selecciona un pedido de la tabla.")
            return
        r = QMessageBox.question(self, "Confirmar eliminación",
                                 f"¿Eliminar el pedido {id_pedido}? Solo se pueden eliminar pedidos cancelados.",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            self.ok("Eliminación cancelada.")
            return

        def exito(_):
            self.ok(f"DELETE correcto (200): pedido {id_pedido} eliminado.")
            self.detalle.clear()
            self.recargar()
            self.pedido_cambio.emit()

        self.llamar("DELETE", lambda: self.c.pedidos.eliminar(id_pedido), exito)
