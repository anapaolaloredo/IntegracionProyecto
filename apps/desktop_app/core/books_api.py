"""Cliente del microservicio de libros (REST con respuestas XML).

Rutas existentes del servicio (no se renombran):
  GET    /api/libros               catalogo completo
  GET    /api/libros/buscar        filtros: titulo, autor, genero, formato, anio, precio_min, precio_max
  GET    /api/libros/<isbn>        detalle (incluye conceptos)
  POST   /api/libros               crear
  PUT    /api/libros/<isbn>        actualizar
  DELETE /api/libros/<isbn>        eliminar"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import quote

from core.http import ServiceError, mensaje_para_status


@dataclass
class Imagen:
    url: str
    portada: bool = False
    alt: str = ""


@dataclass
class Libro:
    isbn: str
    titulo: str
    autores: list = field(default_factory=list)
    anio: int | None = None
    generos: list = field(default_factory=list)
    precio: float = 0.0
    moneda: str = "MXN"
    stock: int = 0
    formato: str = ""
    imagenes: list = field(default_factory=list)
    conceptos: list = field(default_factory=list)  # [(nombre, definicion)]

    def a_payload(self):
        """Representacion completa que se envia en POST y PUT."""
        return {
            "isbn": self.isbn,
            "title": self.titulo,
            "publicationYear": self.anio,
            "price": self.precio,
            "stock": self.stock,
            "format": self.formato,
            "authors": self.autores,
            "genres": self.generos,
            "images": [{"url": i.url, "cover": i.portada, "alt": i.alt} for i in self.imagenes],
            "concepts": [{"name": n, "definition": d} for n, d in self.conceptos],
        }


def _texto(nodo, etiqueta, defecto=""):
    hijo = nodo.find(etiqueta)
    return (hijo.text or defecto) if hijo is not None else defecto


def parsear_libros(xml_bytes):
    try:
        raiz = ET.fromstring(xml_bytes)
    except ET.ParseError:
        raise ServiceError("El servicio de libros respondió un XML inválido. "
                           "¿La URL apunta al microservicio de libros?", kind="respuesta")
    if raiz.tag != "library":
        raise ServiceError("La respuesta no es un catálogo de libros. "
                           "¿La URL apunta al microservicio de libros?", kind="respuesta")
    libros = []
    for b in raiz.findall("book"):
        anio = _texto(b, "publicationYear")
        precio = b.find("price")
        imagenes = [Imagen(url=(i.text or "").strip(), portada=i.get("cover") == "true", alt=i.get("alt", ""))
                    for i in b.findall("images/image") if (i.text or "").strip()]
        imagenes.sort(key=lambda i: not i.portada)
        libros.append(Libro(
            isbn=b.get("isbn", ""),
            titulo=_texto(b, "title"),
            autores=[a.text for a in b.findall("authors/author") if a.text],
            anio=int(anio) if anio.strip().lstrip("-").isdigit() else None,
            generos=[g.text for g in b.findall("genres/genre") if g.text],
            precio=float(precio.text) if precio is not None and precio.text else 0.0,
            moneda=precio.get("currency", "MXN") if precio is not None else "MXN",
            stock=int(_texto(b, "stock", "0") or 0),
            formato=_texto(b, "format"),
            imagenes=imagenes,
            conceptos=[(c.get("name", ""), _texto(c, "definition")) for c in b.findall("concepts/concept")],
        ))
    return libros


class BooksApi:
    def __init__(self, http):
        self.http = http

    def _libros(self, resp, ok=(200,), mensajes=None):
        if resp.status_code in ok:
            return parsear_libros(resp.content)
        mensaje = (mensajes or {}).get(resp.status_code) or mensaje_para_status(resp)
        raise ServiceError(mensaje, status=resp.status_code)

    @staticmethod
    def _ruta_isbn(isbn):
        return "/api/libros/" + quote(isbn.strip(), safe="")

    def listar(self):
        return self._libros(self.http.request("GET", "/api/libros"))

    def buscar(self, **filtros):
        params = {k: v for k, v in filtros.items() if v not in (None, "")}
        return self._libros(self.http.request("GET", "/api/libros/buscar", params=params))

    def obtener(self, isbn):
        resp = self.http.request("GET", self._ruta_isbn(isbn))
        libros = self._libros(resp, mensajes={404: f"No existe un libro con ISBN {isbn} (HTTP 404)."})
        if not libros:
            raise ServiceError(f"No existe un libro con ISBN {isbn}.", status=404)
        return libros[0]

    def crear(self, libro):
        resp = self.http.request("POST", "/api/libros", json_body=libro.a_payload())
        return self._libros(resp, ok=(201,), mensajes={
            409: f"Ya existe un libro con ISBN {libro.isbn} (HTTP 409). Usa otro ISBN o actualiza el existente."})[0]

    def actualizar(self, isbn, libro):
        payload = libro.a_payload()
        payload.pop("isbn")  # el ISBN va en la URL; el servicio no lo modifica
        resp = self.http.request("PUT", self._ruta_isbn(isbn), json_body=payload)
        return self._libros(resp, mensajes={404: f"No existe un libro con ISBN {isbn} (HTTP 404)."})[0]

    def eliminar(self, isbn):
        resp = self.http.request("DELETE", self._ruta_isbn(isbn))
        if resp.status_code != 200:
            mensajes = {404: f"No existe un libro con ISBN {isbn} (HTTP 404)."}
            raise ServiceError(mensajes.get(resp.status_code) or mensaje_para_status(resp), status=resp.status_code)
