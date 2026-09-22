"""Catalogo remoto: lista, busqueda y detalle de libros con sus imagenes.
Todo se obtiene del microservicio de libros, nunca de la base de datos."""

import html

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextBrowser,
                               QVBoxLayout, QWidget)

from ui.async_task import ejecutar
from ui.common import poner_mensaje, texto_error

COLUMNAS = ["ISBN", "Título", "Autor(es)", "Género / Categoría", "Año", "Precio", "Existencia", "Formato", "Imagen"]


def descargar_imagen(url, timeout):
    # Las portadas vienen de servidores externos (con redirecciones): se les da
    # mas margen que a los microservicios para no marcarlas como rotas.
    resp = requests.get(url, timeout=(max(timeout, 8), 20))
    resp.raise_for_status()
    return resp.content


class VisorImagenes(QWidget):
    """Muestra una imagen a la vez con anterior/siguiente; indica cuando no hay."""

    def __init__(self, controlador):
        super().__init__()
        self.c = controlador
        self.imagenes = []
        self.indice = 0
        self.cache = {}
        self.imagen = QLabel(alignment=Qt.AlignCenter)
        self.imagen.setFixedSize(170, 235)
        self.imagen.setStyleSheet("border: 1px solid #bbb; color: gray;")
        self.imagen.setWordWrap(True)
        self.anterior = QPushButton("◀")
        self.siguiente = QPushButton("▶")
        self.contador = QLabel(alignment=Qt.AlignCenter)
        self.anterior.clicked.connect(lambda: self._mover(-1))
        self.siguiente.clicked.connect(lambda: self._mover(1))
        nav = QHBoxLayout()
        nav.addWidget(self.anterior)
        nav.addWidget(self.contador, 1)
        nav.addWidget(self.siguiente)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addWidget(self.imagen)
        capa.addLayout(nav)
        self.mostrar([])

    def mostrar(self, imagenes):
        self.imagenes = imagenes
        self.indice = 0
        self._pintar()

    def _mover(self, paso):
        if self.imagenes:
            self.indice = (self.indice + paso) % len(self.imagenes)
            self._pintar()

    def _pintar(self):
        varias = len(self.imagenes) > 1
        self.anterior.setEnabled(varias)
        self.siguiente.setEnabled(varias)
        if not self.imagenes:
            self.imagen.setPixmap(QPixmap())
            self.imagen.setText("📷\nEste libro no tiene imagen")
            self.contador.setText("0 imágenes")
            return
        img = self.imagenes[self.indice]
        etiqueta = " (portada)" if img.portada else ""
        self.contador.setText(f"{self.indice + 1} de {len(self.imagenes)}{etiqueta}")
        self.imagen.setToolTip(img.alt or img.url)
        if img.url in self.cache:
            self._poner(img.url, self.cache[img.url])
            return
        self.imagen.setPixmap(QPixmap())
        self.imagen.setText("Cargando imagen…")
        url = img.url
        ejecutar(lambda: descargar_imagen(url, self.c.config.timeout),
                 lambda datos: self._descargada(url, datos), lambda exc: self._descargada(url, None))

    def _descargada(self, url, datos):
        pixmap = QPixmap()
        if datos is None or not pixmap.loadFromData(datos):
            pixmap = None
        self.cache[url] = pixmap
        if self.imagenes and self.imagenes[self.indice].url == url:
            self._poner(url, pixmap)

    def _poner(self, url, pixmap):
        if pixmap is None:
            self.imagen.setPixmap(QPixmap())
            self.imagen.setText(f"No se pudo cargar la imagen\n\n{url}")
        else:
            self.imagen.setPixmap(pixmap.scaled(self.imagen.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class CatalogTab(QWidget):
    editar = Signal(object)  # Libro

    def __init__(self, controlador):
        super().__init__()
        self.c = controlador
        self.ultima_consulta = None
        self.seq_detalle = 0
        self.seq_consulta = 0
        self.libro_actual = None

        self.f_isbn = QLineEdit(placeholderText="exacto")
        self.f_titulo = QLineEdit()
        self.f_autor = QLineEdit()
        self.f_anio = QLineEdit(placeholderText="p. ej. 1967")
        self.f_min = QLineEdit(placeholderText="0")
        self.f_max = QLineEdit(placeholderText="999")
        btn_buscar = QPushButton("Buscar")
        btn_todo = QPushButton("Ver todo")
        btn_buscar.clicked.connect(self.buscar)
        btn_todo.clicked.connect(self.ver_todo)
        for campo in (self.f_isbn, self.f_titulo, self.f_autor, self.f_anio, self.f_min, self.f_max):
            campo.returnPressed.connect(self.buscar)
        g = QGridLayout()
        g.addWidget(QLabel("ISBN:"), 0, 0)
        g.addWidget(self.f_isbn, 0, 1)
        g.addWidget(QLabel("Título:"), 0, 2)
        g.addWidget(self.f_titulo, 0, 3)
        g.addWidget(QLabel("Autor:"), 0, 4)
        g.addWidget(self.f_autor, 0, 5)
        g.addWidget(QLabel("Año:"), 1, 0)
        g.addWidget(self.f_anio, 1, 1)
        g.addWidget(QLabel("Precio mín:"), 1, 2)
        g.addWidget(self.f_min, 1, 3)
        g.addWidget(QLabel("Precio máx:"), 1, 4)
        g.addWidget(self.f_max, 1, 5)
        g.addWidget(btn_buscar, 0, 6)
        g.addWidget(btn_todo, 1, 6)
        filtros = QGroupBox("Búsqueda")
        filtros.setLayout(g)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.itemSelectionChanged.connect(self._seleccion)

        self.visor = VisorImagenes(controlador)
        self.detalle = QTextBrowser(openExternalLinks=False)
        self.detalle.setPlaceholderText("Selecciona un libro para ver su detalle (GET /api/libros/{isbn}).")
        self.btn_editar = QPushButton("Editar en Administración")
        self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(lambda: self.libro_actual and self.editar.emit(self.libro_actual))
        panel = QWidget()
        pd = QVBoxLayout(panel)
        pd.addWidget(self.visor, 0, Qt.AlignHCenter)
        pd.addWidget(self.detalle, 1)
        pd.addWidget(self.btn_editar)

        division = QSplitter()
        division.addWidget(self.tabla)
        division.addWidget(panel)
        division.setStretchFactor(0, 3)
        division.setStretchFactor(1, 2)

        self.mensaje = QLabel(wordWrap=True)
        capa = QVBoxLayout(self)
        capa.addWidget(filtros)
        capa.addWidget(self.mensaje)
        capa.addWidget(division, 1)

    # ---- consultas ----
    def ver_todo(self):
        for campo in (self.f_isbn, self.f_titulo, self.f_autor, self.f_anio, self.f_min, self.f_max):
            campo.clear()
        self._consultar(("todo", None), "Catálogo completo")

    def buscar(self):
        isbn = self.f_isbn.text().strip()
        if isbn:
            self._consultar(("isbn", isbn), f"ISBN {isbn}")
            return
        try:
            anio = int(self.f_anio.text()) if self.f_anio.text().strip() else None
            pmin = float(self.f_min.text()) if self.f_min.text().strip() else None
            pmax = float(self.f_max.text()) if self.f_max.text().strip() else None
        except ValueError:
            poner_mensaje(self.mensaje, "Año debe ser entero y los precios deben ser números.", error=True)
            return
        if pmin is not None and pmax is not None and pmin > pmax:
            poner_mensaje(self.mensaje, "El precio mínimo no puede ser mayor que el máximo.", error=True)
            return
        filtros = {"titulo": self.f_titulo.text().strip(), "autor": self.f_autor.text().strip(),
                   "anio": anio, "precio_min": pmin, "precio_max": pmax}
        if not any(v not in (None, "") for v in filtros.values()):
            self.ver_todo()
            return
        self._consultar(("filtros", filtros), "Resultados de la búsqueda")

    def recargar(self):
        self._consultar(*(self.ultima_consulta or (("todo", None), "Catálogo completo")))

    def _consultar(self, consulta, titulo):
        self.ultima_consulta = (consulta, titulo)
        tipo, valor = consulta
        if tipo == "isbn":
            funcion = lambda: [self.c.libros.obtener(valor)]  # noqa: E731
        elif tipo == "filtros":
            funcion = lambda: self.c.libros.buscar(**valor)  # noqa: E731
        else:
            funcion = self.c.libros.listar
        self.seq_consulta += 1
        seq = self.seq_consulta  # solo la consulta mas reciente pinta resultados
        poner_mensaje(self.mensaje, "Consultando el microservicio de libros…")
        ejecutar(funcion, lambda libros: seq == self.seq_consulta and self._pintar_tabla(libros, titulo),
                 lambda exc: seq == self.seq_consulta and self._fallo_consulta(exc))

    def _fallo_consulta(self, exc):
        poner_mensaje(self.mensaje, texto_error(exc), error=True)

    def _pintar_tabla(self, libros, titulo):
        self.tabla.setRowCount(0)
        for libro in libros:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = [libro.isbn, libro.titulo, ", ".join(libro.autores) or "—", ", ".join(libro.generos) or "—",
                       str(libro.anio) if libro.anio else "—", f"${libro.precio:,.2f} {libro.moneda}",
                       str(libro.stock), libro.formato or "—",
                       f"{len(libro.imagenes)} imagen(es)" if libro.imagenes else "Sin imagen"]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if col in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(fila, col, item)
        self.tabla.resizeColumnsToContents()
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        poner_mensaje(self.mensaje, f"{titulo}: {len(libros)} libro(s).")

    # ---- detalle ----
    def _seleccion(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        isbn = self.tabla.item(filas[0].row(), 0).text()
        self.seq_detalle += 1
        seq = self.seq_detalle
        self.detalle.setHtml(f"<i>Consultando detalle de {html.escape(isbn)}…</i>")
        ejecutar(lambda: self.c.libros.obtener(isbn),
                 lambda libro: seq == self.seq_detalle and self._pintar_detalle(libro),
                 lambda exc: seq == self.seq_detalle and self._fallo_detalle(exc))

    def _fallo_detalle(self, exc):
        self.libro_actual = None
        self.btn_editar.setEnabled(False)
        self.visor.mostrar([])
        self.detalle.setHtml(f"<p style='color:#c62828'>{html.escape(texto_error(exc))}</p>")

    def _pintar_detalle(self, libro):
        self.libro_actual = libro
        self.btn_editar.setEnabled(True)
        self.visor.mostrar(libro.imagenes)
        e = html.escape
        filas = [("ISBN", libro.isbn), ("Autor(es)", ", ".join(libro.autores) or "—"),
                 ("Género / Categoría", ", ".join(libro.generos) or "—"), ("Año", libro.anio or "—"),
                 ("Precio", f"${libro.precio:,.2f} {libro.moneda}"), ("Existencia", libro.stock),
                 ("Formato", libro.formato or "—")]
        tabla = "".join(f"<tr><td><b>{e(k)}:</b></td><td>{e(str(v))}</td></tr>" for k, v in filas)
        conceptos = "".join(f"<li><b>{e(n)}</b>: {e(d)}</li>" for n, d in libro.conceptos) \
            or "<li><i>El servicio no tiene conceptos asociados a este libro.</i></li>"
        self.detalle.setHtml(f"<h3>{e(libro.titulo)}</h3><table>{tabla}</table>"
                             f"<h4>Conceptos y definiciones</h4><ul>{conceptos}</ul>")
