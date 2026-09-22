"""Administracion de libros: GET, POST, PUT y DELETE contra el microservicio.
Cada operacion se confirma contra el servidor y luego se refresca el catalogo."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from core.books_api import Imagen, Libro
from ui.async_task import ejecutar
from ui.common import poner_mensaje, texto_error


class AdminTab(QWidget):
    catalogo_cambio = Signal()

    def __init__(self, controlador):
        super().__init__()
        self.c = controlador
        self.isbn = QLineEdit(placeholderText="obligatorio")
        self.titulo = QLineEdit(placeholderText="obligatorio")
        self.anio = QLineEdit(placeholderText="opcional, p. ej. 2004")
        self.precio = QLineEdit(placeholderText="obligatorio, p. ej. 349.90")
        self.stock = QLineEdit(placeholderText="obligatorio, entero")
        self.formato = QLineEdit(placeholderText="obligatorio, p. ej. Pasta blanda")
        self.autores = QLineEdit(placeholderText="separados por coma")
        self.generos = QLineEdit(placeholderText="separados por coma")
        self.imagenes = QPlainTextEdit(placeholderText="Una URL por línea. La primera es la portada.")
        self.conceptos = QPlainTextEdit(placeholderText="Uno por línea →  Nombre: definición")
        for caja in (self.imagenes, self.conceptos):
            caja.setFixedHeight(80)

        form = QFormLayout()
        form.addRow("ISBN:", self.isbn)
        form.addRow("Título:", self.titulo)
        form.addRow("Año:", self.anio)
        form.addRow("Precio (MXN):", self.precio)
        form.addRow("Existencia:", self.stock)
        form.addRow("Formato:", self.formato)
        form.addRow("Autor(es):", self.autores)
        form.addRow("Género / Categoría:", self.generos)
        form.addRow("Imágenes:", self.imagenes)
        form.addRow("Conceptos:", self.conceptos)
        caja = QGroupBox("Datos del libro")
        caja.setLayout(form)

        self.botones = {
            "GET": QPushButton("Cargar por ISBN (GET)"),
            "POST": QPushButton("Crear (POST)"),
            "PUT": QPushButton("Actualizar completo (PUT)"),
            "DELETE": QPushButton("Eliminar (DELETE)"),
        }
        self.botones["GET"].clicked.connect(self.cargar_por_isbn)
        self.botones["POST"].clicked.connect(self.crear)
        self.botones["PUT"].clicked.connect(self.actualizar)
        self.botones["DELETE"].clicked.connect(self.eliminar)
        self.botones["DELETE"].setStyleSheet("color: #c62828;")
        limpiar = QPushButton("Limpiar formulario")
        limpiar.clicked.connect(self.limpiar)
        barra = QHBoxLayout()
        for b in self.botones.values():
            barra.addWidget(b)
        barra.addWidget(limpiar)

        ayuda = QLabel("PUT envía la representación completa del libro (todos los campos del formulario, "
                       "incluidas listas de autores, géneros, imágenes y conceptos, que se reemplazan). "
                       "El cuerpo exacto enviado aparece en el registro HTTP de abajo.")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: gray;")
        self.mensaje = QLabel(wordWrap=True)

        capa = QVBoxLayout(self)
        capa.addWidget(caja)
        capa.addLayout(barra)
        capa.addWidget(self.mensaje)
        capa.addWidget(ayuda)
        capa.addStretch()

    # ---- formulario <-> Libro ----
    def cargar_libro(self, libro):
        self.isbn.setText(libro.isbn)
        self.titulo.setText(libro.titulo)
        self.anio.setText(str(libro.anio) if libro.anio else "")
        self.precio.setText(f"{libro.precio:.2f}")
        self.stock.setText(str(libro.stock))
        self.formato.setText(libro.formato)
        self.autores.setText(", ".join(libro.autores))
        self.generos.setText(", ".join(libro.generos))
        self.imagenes.setPlainText("\n".join(i.url for i in libro.imagenes))
        self.conceptos.setPlainText("\n".join(f"{n}: {d}" for n, d in libro.conceptos))

    def limpiar(self):
        for campo in (self.isbn, self.titulo, self.anio, self.precio, self.stock, self.formato,
                      self.autores, self.generos, self.imagenes, self.conceptos):
            campo.clear()
        self.mensaje.clear()

    def _libro_del_formulario(self):
        """Valida y construye el Libro; lanza ValueError con un mensaje claro."""
        faltan = [n for n, c in (("ISBN", self.isbn), ("Título", self.titulo), ("Precio", self.precio),
                                 ("Existencia", self.stock), ("Formato", self.formato)) if not c.text().strip()]
        if faltan:
            raise ValueError("Faltan campos obligatorios: " + ", ".join(faltan) + ".")
        try:
            precio = float(self.precio.text().replace(",", ""))
            stock = int(self.stock.text())
            anio = int(self.anio.text()) if self.anio.text().strip() else None
        except ValueError:
            raise ValueError("Precio debe ser número; existencia y año deben ser enteros.")
        if precio < 0 or stock < 0:
            raise ValueError("Precio y existencia no pueden ser negativos.")
        separar = lambda t: [x.strip() for x in t.split(",") if x.strip()]  # noqa: E731
        urls = [u.strip() for u in self.imagenes.toPlainText().splitlines() if u.strip()]
        conceptos = []
        for linea in self.conceptos.toPlainText().splitlines():
            if linea.strip():
                nombre, _, definicion = linea.partition(":")
                conceptos.append((nombre.strip(), definicion.strip()))
        return Libro(isbn=self.isbn.text().strip(), titulo=self.titulo.text().strip(), anio=anio,
                     precio=precio, stock=stock, formato=self.formato.text().strip(),
                     autores=separar(self.autores.text()), generos=separar(self.generos.text()),
                     imagenes=[Imagen(url=u, portada=(i == 0)) for i, u in enumerate(urls)],
                     conceptos=conceptos)

    # ---- operaciones ----
    def _ejecutar(self, metodo, funcion, exito):
        for b in self.botones.values():
            b.setEnabled(False)
        poner_mensaje(self.mensaje, f"Enviando {metodo} al microservicio de libros…")

        def listo(resultado):
            self._habilitar()
            exito(resultado)

        def fallo(exc):
            self._habilitar()
            poner_mensaje(self.mensaje, f"{metodo} falló: {texto_error(exc)}", error=True)

        ejecutar(funcion, listo, fallo)

    def _habilitar(self):
        for b in self.botones.values():
            b.setEnabled(True)

    def cargar_por_isbn(self):
        isbn = self.isbn.text().strip()
        if not isbn:
            poner_mensaje(self.mensaje, "Escribe el ISBN a cargar.", error=True)
            return

        def exito(libro):
            self.cargar_libro(libro)
            poner_mensaje(self.mensaje, f"GET correcto: se cargó «{libro.titulo}».")

        self._ejecutar("GET", lambda: self.c.libros.obtener(isbn), exito)

    def crear(self):
        try:
            libro = self._libro_del_formulario()
        except ValueError as exc:
            poner_mensaje(self.mensaje, str(exc), error=True)
            return

        def exito(creado):
            self.cargar_libro(creado)
            poner_mensaje(self.mensaje, f"POST correcto (201): se creó «{creado.titulo}». El catálogo se actualizó.")
            self.catalogo_cambio.emit()

        self._ejecutar("POST", lambda: self.c.libros.crear(libro), exito)

    def actualizar(self):
        try:
            libro = self._libro_del_formulario()
        except ValueError as exc:
            poner_mensaje(self.mensaje, str(exc), error=True)
            return

        def exito(actualizado):
            self.cargar_libro(actualizado)
            poner_mensaje(self.mensaje, f"PUT correcto (200): «{actualizado.titulo}» quedó actualizado. "
                                        "El catálogo se actualizó.")
            self.catalogo_cambio.emit()

        self._ejecutar("PUT", lambda: self.c.libros.actualizar(libro.isbn, libro), exito)

    def eliminar(self):
        isbn = self.isbn.text().strip()
        if not isbn:
            poner_mensaje(self.mensaje, "Escribe el ISBN del libro a eliminar.", error=True)
            return
        titulo = self.titulo.text().strip() or "(sin título en el formulario)"
        respuesta = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar definitivamente el libro con ISBN {isbn}?\n{titulo}\n\nEsta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if respuesta != QMessageBox.Yes:
            poner_mensaje(self.mensaje, "Eliminación cancelada.")
            return

        def exito(_):
            poner_mensaje(self.mensaje, f"DELETE correcto (200): se eliminó el libro {isbn}. El catálogo se actualizó.")
            self.catalogo_cambio.emit()

        self._ejecutar("DELETE", lambda: self.c.libros.eliminar(isbn), exito)
