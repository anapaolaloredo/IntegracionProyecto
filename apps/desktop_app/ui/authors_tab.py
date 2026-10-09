"""Autores (servicio authors, :5003): lectura publica; el admin crea, renombra, elimina y
vincula/desvincula libros."""

from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)
from PySide6.QtCore import Qt

from core.http import ServiceError
from ui.crud_base import CrudTab


class AuthorsTab(CrudTab):
    requiere_sesion = False

    def __init__(self, controlador):
        super().__init__(controlador, ["ID", "Autor"])
        self.nombre = QLineEdit(placeholderText="nombre del autor (máx. 150)")
        self.combo_libro = QComboBox()
        self.lista_libros = QListWidget()

        form = QFormLayout()
        form.addRow("Nombre:", self.nombre)
        caja = QGroupBox("Autor")
        caja.setLayout(form)
        libros = QVBoxLayout()
        libros.addWidget(QLabel("Libros del autor seleccionado:"))
        libros.addWidget(self.lista_libros)
        fila = QHBoxLayout()
        fila.addWidget(self.combo_libro, 1)
        self.btn_vincular = QPushButton("Vincular libro (POST)")
        self.btn_desvincular = QPushButton("Desvincular seleccionado (DELETE)")
        fila.addWidget(self.btn_vincular)
        fila.addWidget(self.btn_desvincular)
        libros.addLayout(fila)
        caja_libros = QGroupBox("Relación autor-libro")
        caja_libros.setLayout(libros)

        self.btn_recargar = QPushButton("Recargar (GET)")
        self.btn_crear = QPushButton("Crear (POST)")
        self.btn_renombrar = QPushButton("Renombrar (PATCH)")
        self.btn_eliminar = QPushButton("Eliminar (DELETE)")
        self.btn_eliminar.setStyleSheet("color: #c62828;")
        self.registrar(self.btn_recargar)
        self.solo_admin(self.btn_crear, self.btn_renombrar, self.btn_eliminar, self.btn_vincular, self.btn_desvincular)
        self.btn_recargar.clicked.connect(self.recargar)
        self.btn_crear.clicked.connect(self.crear)
        self.btn_renombrar.clicked.connect(self.renombrar)
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_vincular.clicked.connect(self.vincular)
        self.btn_desvincular.clicked.connect(self.desvincular)
        self.seleccion_cambio.connect(self._seleccion)

        barra = QHBoxLayout()
        for b in (self.btn_recargar, self.btn_crear, self.btn_renombrar, self.btn_eliminar):
            barra.addWidget(b)
        capa = QVBoxLayout(self)
        capa.addWidget(self.tabla, 1)
        capa.addWidget(caja)
        capa.addLayout(barra)
        capa.addWidget(caja_libros)
        capa.addWidget(self.mensaje)
        capa.addWidget(self.btn_login)
        self.refrescar_permisos()

    # ---- lectura ----
    def al_activar(self):
        self.recargar()

    def recargar(self):
        def cargar():
            autores = self.c.authors.listar()
            try:
                libros = self.c.libros.listar()
            except ServiceError:
                libros = []  # el catalogo caido no debe impedir ver a los autores
            return autores, libros

        self.llamar("GET", cargar, self._mostrar)

    def _mostrar(self, resultado):
        autores, libros = resultado
        self.llenar_tabla([[a["id_autor"], a["nombre_autor"]] for a in autores], [a["id_autor"] for a in autores])
        self.combo_libro.clear()
        for libro in libros:
            if libro.id_libro is not None:
                self.combo_libro.addItem(f"{libro.titulo} — {libro.isbn}", libro.id_libro)
        self.ok(f"{len(autores)} autor(es).")

    def _seleccion(self, id_autor):
        self.lista_libros.clear()
        if id_autor is None:
            return
        self.llamar("GET", lambda: self.c.authors.obtener(id_autor), self._detalle)

    def _detalle(self, autor):
        self.nombre.setText(autor.get("nombre_autor", ""))
        self.lista_libros.clear()
        for libro in autor.get("libros", []):
            titulo = libro.get("titulo") or f"Libro {libro.get('id_libro')}"
            isbn = f" ({libro['isbn']})" if libro.get("isbn") else ""
            item = QListWidgetItem(titulo + isbn)
            item.setData(Qt.UserRole, libro.get("id_libro"))
            self.lista_libros.addItem(item)

    # ---- escrituras ----
    def _nombre_valido(self):
        nombre = self.nombre.text().strip()
        if not nombre or len(nombre) > 150:
            self.error("El nombre del autor es obligatorio y admite máximo 150 caracteres.")
            return None
        return nombre

    def _seleccionado_o_error(self):
        id_autor = self.id_seleccionado()
        if id_autor is None:
            self.error("Selecciona un autor de la tabla.")
        return id_autor

    def crear(self):
        nombre = self._nombre_valido()
        if nombre is None:
            return

        def exito(r):
            self.ok(f"POST correcto (201): autor {r.get('id_autor')} creado.")
            self.recargar()

        self.llamar("POST", lambda: self.c.authors.crear(nombre), exito)

    def renombrar(self):
        id_autor = self._seleccionado_o_error()
        nombre = self._nombre_valido() if id_autor is not None else None
        if id_autor is None or nombre is None:
            return

        def exito(_):
            self.ok(f"PATCH correcto (200): autor {id_autor} renombrado.")
            self.recargar()

        self.llamar("PATCH", lambda: self.c.authors.renombrar(id_autor, nombre), exito)

    def eliminar(self):
        id_autor = self._seleccionado_o_error()
        if id_autor is None:
            return
        r = QMessageBox.question(self, "Confirmar eliminación",
                                 f"¿Eliminar al autor {id_autor}? (Debe estar sin libros asociados.)",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            self.ok("Eliminación cancelada.")
            return

        def exito(_):
            self.ok(f"DELETE correcto (200): autor {id_autor} eliminado.")
            self.nombre.clear()
            self.lista_libros.clear()
            self.recargar()

        self.llamar("DELETE", lambda: self.c.authors.eliminar(id_autor), exito)

    def vincular(self):
        id_autor = self._seleccionado_o_error()
        id_libro = self.combo_libro.currentData()
        if id_autor is None:
            return
        if id_libro is None:
            self.error("Elige un libro del combo (solo aparecen libros con id).")
            return

        def exito(_):
            self.ok(f"POST correcto (201): libro {id_libro} vinculado al autor {id_autor}.")
            self._seleccion(id_autor)

        self.llamar("POST", lambda: self.c.authors.vincular(id_autor, id_libro), exito)

    def desvincular(self):
        id_autor = self._seleccionado_o_error()
        item = self.lista_libros.currentItem()
        if id_autor is None:
            return
        if item is None or item.data(Qt.UserRole) is None:
            self.error("Selecciona en la lista el libro a desvincular.")
            return
        id_libro = item.data(Qt.UserRole)

        def exito(_):
            self.ok(f"DELETE correcto (200): libro {id_libro} desvinculado del autor {id_autor}.")
            self._seleccion(id_autor)

        self.llamar("DELETE", lambda: self.c.authors.desvincular(id_autor, id_libro), exito)
