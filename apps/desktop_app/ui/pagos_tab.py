"""Pagos (servicio pagos, :5005): pagar un pedido pendiente (lo deja 'pagado') y reembolsar (admin)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from core.http import ServiceError, SesionExpirada
from ui.crud_base import CrudTab

COLUMNAS = ["ID pago", "Pedido", "Método", "Monto", "Fecha", "Cuenta"]
METODOS = ("tarjeta", "transferencia", "efectivo")


def parsear_monto(texto):
    """'' -> None (el servidor usa el total); '100,50' o '1,000.50' -> float; otra cosa -> ValueError."""
    texto = texto.strip()
    if not texto:
        return None
    texto = texto.replace(",", "") if "." in texto else texto.replace(",", ".")
    try:
        valor = float(texto)
    except ValueError:
        raise ValueError("El monto debe ser un número mayor que cero (o déjalo vacío para pagar el total).")
    if valor <= 0:
        raise ValueError("El monto debe ser un número mayor que cero (o déjalo vacío para pagar el total).")
    return valor


class PagosTab(CrudTab):
    pago_cambio = Signal()  # un pago se registro/reembolso: el estado de los pedidos cambio

    def __init__(self, controlador):
        super().__init__(controlador, COLUMNAS)
        self.combo_pedido = QComboBox()
        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(METODOS)
        self.monto = QLineEdit(placeholderText="vacío = total del pedido")
        form = QFormLayout()
        form.addRow("Pedido pendiente:", self.combo_pedido)
        form.addRow("Método de pago:", self.combo_metodo)
        form.addRow("Monto (opcional):", self.monto)
        caja = QGroupBox("Registrar pago")
        caja.setLayout(form)

        self.detalle = QPlainTextEdit(readOnly=True)
        self.detalle.setPlaceholderText("Selecciona un pago para ver su detalle.")
        self.detalle.setMaximumHeight(90)

        self.btn_recargar = QPushButton("Recargar (GET)")
        self.btn_pagar = QPushButton("Registrar pago (POST)")
        self.btn_reembolsar = QPushButton("Reembolsar (DELETE)")
        self.btn_reembolsar.setStyleSheet("color: #c62828;")
        self.registrar(self.btn_recargar, self.btn_pagar)
        self.solo_admin(self.btn_reembolsar)
        self.btn_recargar.clicked.connect(self.recargar)
        self.btn_pagar.clicked.connect(self.pagar)
        self.btn_reembolsar.clicked.connect(self.reembolsar)
        self.seleccion_cambio.connect(self._seleccion)

        barra = QHBoxLayout()
        for b in (self.btn_recargar, self.btn_pagar, self.btn_reembolsar):
            barra.addWidget(b)
        capa = QVBoxLayout(self)
        capa.addWidget(self.tabla, 1)
        capa.addWidget(self.detalle)
        capa.addWidget(caja)
        capa.addLayout(barra)
        capa.addWidget(self.mensaje)
        capa.addWidget(self.btn_login)
        self.refrescar_permisos()

    def refrescar_permisos(self):
        super().refrescar_permisos()
        if self.hay_sesion() and self.combo_pedido.count() == 0:
            self.btn_pagar.setEnabled(False)
            self.btn_pagar.setToolTip("No hay pedidos pendientes por pagar")
        else:
            self.btn_pagar.setToolTip("")

    # ---- lectura ----
    def al_activar(self):
        self.recargar()

    def recargar(self):
        if not self.hay_sesion():
            self.refrescar_permisos()
            return

        def cargar():
            pagos = self.c.pagos.listar()
            try:
                pedidos = self.c.pedidos.listar()
            except SesionExpirada:
                raise
            except ServiceError:
                pedidos = []  # sin el servicio de pedidos igual se ven los pagos
            return pagos, [p for p in pedidos if p.get("estado") == "pendiente"]

        self.llamar("GET", cargar, self._mostrar)

    def _mostrar(self, resultado):
        pagos, pendientes = resultado
        self.llenar_tabla([[p["id_pago"], p.get("id_pedido"), p.get("metodo"), p.get("monto"), p.get("fecha_pago"),
                            p.get("id_cuenta")] for p in pagos], [p["id_pago"] for p in pagos])
        self.combo_pedido.clear()
        for p in pendientes:
            self.combo_pedido.addItem(f"#{p['id_pedido']} — total ${p.get('total')}", p["id_pedido"])
        self.refrescar_permisos()
        self.ok(f"{len(pagos)} pago(s); {len(pendientes)} pedido(s) pendiente(s) por pagar.")

    def _seleccion(self, id_pago):
        self.detalle.clear()
        if id_pago is None:
            return

        def exito(p):
            self.detalle.setPlainText(f"Pago {p.get('id_pago')} del pedido {p.get('id_pedido')}: "
                                      f"{p.get('metodo')} ${p.get('monto')} el {p.get('fecha_pago')}")

        self.llamar("GET", lambda: self.c.pagos.obtener(id_pago), exito)

    # ---- escrituras ----
    def pagar(self):
        id_pedido = self.combo_pedido.currentData()
        if id_pedido is None:
            self.error("No hay pedidos pendientes por pagar.")
            return
        try:
            monto = parsear_monto(self.monto.text())
        except ValueError as exc:
            self.error(str(exc))
            return
        metodo = self.combo_metodo.currentText()

        def exito(p):
            self.monto.clear()
            self.ok(f"POST correcto (201): pago {p.get('id_pago')} registrado; el pedido {id_pedido} quedó pagado.")
            self.recargar()
            self.pago_cambio.emit()

        self.llamar("POST", lambda: self.c.pagos.registrar(id_pedido, metodo, monto), exito)

    def reembolsar(self):
        id_pago = self.id_seleccionado()
        if id_pago is None:
            self.error("Selecciona un pago de la tabla.")
            return
        r = QMessageBox.question(self, "Confirmar reembolso",
                                 f"¿Reembolsar el pago {id_pago}? El pedido volverá a 'pendiente'.",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            self.ok("Reembolso cancelado.")
            return

        def exito(_):
            self.ok(f"DELETE correcto (200): pago {id_pago} reembolsado; el pedido volvió a pendiente.")
            self.detalle.clear()
            self.recargar()
            self.pago_cambio.emit()

        self.llamar("DELETE", lambda: self.c.pagos.reembolsar(id_pago), exito)
