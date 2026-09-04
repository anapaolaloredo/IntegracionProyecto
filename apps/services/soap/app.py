"""Microservicio Flask (sin blueprints) para CRUD de libros sobre PostgreSQL.

Fuente de verdad de las tablas: /data/library_schema.sql
Fuente de verdad del formato de salida: /apps/services/soap/library.xml
Acceso a datos exclusivamente con psycopg2 (sin ORM).
"""

import os
from xml.etree import ElementTree as ET

import psycopg2
import psycopg2.errors
import psycopg2.extras
from dotenv import load_dotenv
from flasgger import Swagger
from flask import Flask, Response, request
from flask_cors import CORS

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "library"),
    "user": os.getenv("DB_USER", "library_user"),
    "password": os.getenv("DB_PASSWORD", "library666"),
}

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "*")}})
app.config["SWAGGER"] = {"title": "Library Books API", "uiversion": 3}
Swagger(app)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# json_agg(...) ya devuelve JSON: psycopg2 lo castea a list/dict de Python.
BOOK_QUERY = """
    SELECT
        l.isbn,
        l.titulo AS title,
        l.anio_publicacion AS "publicationYear",
        l.precio AS price,
        l.stock,
        f.nombre_formato AS format,
        COALESCE((
            SELECT json_agg(a.nombre_autor ORDER BY a.nombre_autor)
            FROM libro_autor la JOIN autores a ON a.id_autor = la.id_autor
            WHERE la.id_libro = l.id_libro
        ), '[]') AS authors,
        COALESCE((
            SELECT json_agg(g.nombre_genero ORDER BY g.nombre_genero)
            FROM libro_genero lg JOIN generos g ON g.id_genero = lg.id_genero
            WHERE lg.id_libro = l.id_libro
        ), '[]') AS genres,
        COALESCE((
            SELECT json_agg(json_build_object(
                'url', i.url_imagen, 'cover', i.es_portada, 'alt', i.texto_alternativo
            ) ORDER BY i.orden)
            FROM imagenes_libro i WHERE i.id_libro = l.id_libro
        ), '[]') AS images,
        COALESCE((
            SELECT json_agg(json_build_object(
                'name', c.nombre_concepto, 'definition', lc.definicion
            ))
            FROM libro_concepto lc JOIN conceptos c ON c.id_concepto = lc.id_concepto
            WHERE lc.id_libro = l.id_libro
        ), '[]') AS concepts
    FROM libros l
    JOIN formatos f ON f.id_formato = l.id_formato
"""


def fetch_books(where_clause="", params=None):
    query = BOOK_QUERY + (f" WHERE {where_clause}" if where_clause else "") + " ORDER BY l.titulo"
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or [])
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def book_to_element(book):
    """Convierte un libro (dict) al mismo diseño XML que library.xml."""
    book_el = ET.Element("book", isbn=book["isbn"])
    ET.SubElement(book_el, "title").text = book["title"]

    authors_el = ET.SubElement(book_el, "authors")
    for author in book["authors"]:
        ET.SubElement(authors_el, "author").text = author

    year = book["publicationYear"]
    ET.SubElement(book_el, "publicationYear").text = "" if year is None else str(year)

    genres_el = ET.SubElement(book_el, "genres")
    for genre in book["genres"]:
        ET.SubElement(genres_el, "genre").text = genre

    ET.SubElement(book_el, "price", currency="MXN").text = str(book["price"])
    ET.SubElement(book_el, "stock").text = str(book["stock"])
    ET.SubElement(book_el, "format").text = book["format"]

    images_el = ET.SubElement(book_el, "images")
    for image in book["images"]:
        image_el = ET.SubElement(images_el, "image", cover=str(bool(image["cover"])).lower())
        if image.get("alt"):
            image_el.set("alt", image["alt"])
        image_el.text = image["url"]

    concepts_el = ET.SubElement(book_el, "concepts")
    for concept in book["concepts"]:
        concept_el = ET.SubElement(concepts_el, "concept", name=concept["name"])
        ET.SubElement(concept_el, "definition").text = concept["definition"]

    return book_el


def books_xml_response(books, status=200):
    root = ET.Element("library")
    for book in books:
        root.append(book_to_element(book))
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(body, status=status, mimetype="application/xml")


def error_xml_response(message, status):
    root = ET.Element("error")
    ET.SubElement(root, "message").text = message
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(body, status=status, mimetype="application/xml")


def get_or_create_id(cur, table, id_col, name_col, name):
    cur.execute(f"SELECT {id_col} FROM {table} WHERE {name_col} = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(f"INSERT INTO {table} ({name_col}) VALUES (%s) RETURNING {id_col}", (name,))
    return cur.fetchone()[0]


def guardar_relaciones(cur, id_libro, data):
    for autor in data.get("authors", []):
        id_autor = get_or_create_id(cur, "autores", "id_autor", "nombre_autor", autor)
        cur.execute(
            "INSERT INTO libro_autor (id_libro, id_autor) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (id_libro, id_autor),
        )
    for genero in data.get("genres", []):
        id_genero = get_or_create_id(cur, "generos", "id_genero", "nombre_genero", genero)
        cur.execute(
            "INSERT INTO libro_genero (id_libro, id_genero) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (id_libro, id_genero),
        )
    for orden, imagen in enumerate(data.get("images", [])):
        cur.execute(
            """INSERT INTO imagenes_libro (id_libro, url_imagen, texto_alternativo, orden, es_portada)
               VALUES (%s, %s, %s, %s, %s)""",
            (id_libro, imagen["url"], imagen.get("alt", ""), orden, bool(imagen.get("cover", False))),
        )
    for concepto in data.get("concepts", []):
        id_concepto = get_or_create_id(cur, "conceptos", "id_concepto", "nombre_concepto", concepto["name"])
        cur.execute(
            """INSERT INTO libro_concepto (id_libro, id_concepto, definicion) VALUES (%s, %s, %s)
               ON CONFLICT (id_libro, id_concepto) DO UPDATE SET definicion = EXCLUDED.definicion""",
            (id_libro, id_concepto, concepto.get("definition", "")),
        )


@app.route("/api/libros", methods=["GET"])
def listar_libros():
    """
    Lista todos los libros
    ---
    tags: [Libros]
    produces: [application/xml]
    responses:
      200:
        description: Lista de libros (XML) con autores, generos, imagenes y conceptos
    """
    return books_xml_response(fetch_books())


@app.route("/api/libros/buscar", methods=["GET"])
def buscar_libros():
    """
    Busca libros por atributos (titulo, autor, genero, formato, anio, rango de precio)
    ---
    tags: [Libros]
    produces: [application/xml]
    parameters:
      - {name: titulo, in: query, type: string}
      - {name: autor, in: query, type: string}
      - {name: genero, in: query, type: string}
      - {name: formato, in: query, type: string}
      - {name: anio, in: query, type: integer}
      - {name: precio_min, in: query, type: number}
      - {name: precio_max, in: query, type: number}
    responses:
      200:
        description: Libros (XML) que cumplen los filtros dados
    """
    conditions = []
    params = []

    titulo = request.args.get("titulo")
    if titulo:
        conditions.append("l.titulo ILIKE %s")
        params.append(f"%{titulo}%")

    autor = request.args.get("autor")
    if autor:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM libro_autor la JOIN autores a ON a.id_autor = la.id_autor
                WHERE la.id_libro = l.id_libro AND a.nombre_autor ILIKE %s
            )"""
        )
        params.append(f"%{autor}%")

    genero = request.args.get("genero")
    if genero:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM libro_genero lg JOIN generos g ON g.id_genero = lg.id_genero
                WHERE lg.id_libro = l.id_libro AND g.nombre_genero ILIKE %s
            )"""
        )
        params.append(f"%{genero}%")

    formato = request.args.get("formato")
    if formato:
        conditions.append("f.nombre_formato ILIKE %s")
        params.append(f"%{formato}%")

    anio = request.args.get("anio")
    if anio:
        conditions.append("l.anio_publicacion = %s")
        params.append(anio)

    precio_min = request.args.get("precio_min")
    if precio_min:
        conditions.append("l.precio >= %s")
        params.append(precio_min)

    precio_max = request.args.get("precio_max")
    if precio_max:
        conditions.append("l.precio <= %s")
        params.append(precio_max)

    where_clause = " AND ".join(conditions)
    return books_xml_response(fetch_books(where_clause, params))


@app.route("/api/libros/<isbn>", methods=["GET"])
def obtener_libro(isbn):
    """
    Obtiene un libro por ISBN
    ---
    tags: [Libros]
    produces: [application/xml]
    parameters:
      - {name: isbn, in: path, type: string, required: true}
    responses:
      200:
        description: Libro encontrado (XML)
      404:
        description: Libro no encontrado
    """
    libros = fetch_books("l.isbn = %s", [isbn])
    if not libros:
        return error_xml_response("Libro no encontrado", 404)
    return books_xml_response(libros)


@app.route("/api/libros", methods=["POST"])
def crear_libro():
    """
    Crea un libro nuevo
    ---
    tags: [Libros]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [isbn, title, price, stock, format]
          properties:
            isbn: {type: string}
            title: {type: string}
            publicationYear: {type: integer}
            price: {type: number}
            stock: {type: integer}
            format: {type: string}
            authors: {type: array, items: {type: string}}
            genres: {type: array, items: {type: string}}
            images:
              type: array
              items:
                type: object
                properties:
                  url: {type: string}
                  cover: {type: boolean}
                  alt: {type: string}
            concepts:
              type: array
              items:
                type: object
                properties:
                  name: {type: string}
                  definition: {type: string}
    produces: [application/xml]
    responses:
      201:
        description: Libro creado (XML)
      400:
        description: Datos invalidos
      409:
        description: El ISBN ya existe
    """
    data = request.get_json(force=True, silent=True) or {}
    requeridos = ["isbn", "title", "price", "stock", "format"]
    faltantes = [campo for campo in requeridos if data.get(campo) is None]
    if faltantes:
        return error_xml_response(f"Campos requeridos faltantes: {', '.join(faltantes)}", 400)

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                id_formato = get_or_create_id(cur, "formatos", "id_formato", "nombre_formato", data["format"])
                cur.execute(
                    """INSERT INTO libros (isbn, titulo, anio_publicacion, precio, stock, id_formato)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_libro""",
                    (data["isbn"], data["title"], data.get("publicationYear"), data["price"], data["stock"], id_formato),
                )
                id_libro = cur.fetchone()[0]
                guardar_relaciones(cur, id_libro, data)
    except psycopg2.errors.UniqueViolation:
        return error_xml_response("Ya existe un libro con ese ISBN", 409)
    finally:
        conn.close()

    return books_xml_response(fetch_books("l.isbn = %s", [data["isbn"]]), 201)


@app.route("/api/libros/<isbn>", methods=["PUT"])
def actualizar_libro(isbn):
    """
    Actualiza un libro existente (datos propios y sus relaciones)
    ---
    tags: [Libros]
    parameters:
      - {name: isbn, in: path, type: string, required: true}
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title: {type: string}
            publicationYear: {type: integer}
            price: {type: number}
            stock: {type: integer}
            format: {type: string}
            authors: {type: array, items: {type: string}}
            genres: {type: array, items: {type: string}}
            images: {type: array, items: {type: object}}
            concepts: {type: array, items: {type: object}}
    produces: [application/xml]
    responses:
      200:
        description: Libro actualizado (XML)
      404:
        description: Libro no encontrado
    """
    data = request.get_json(force=True, silent=True) or {}

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id_libro, titulo, anio_publicacion, precio, stock, id_formato "
                    "FROM libros WHERE isbn = %s",
                    (isbn,),
                )
                row = cur.fetchone()
                if not row:
                    return error_xml_response("Libro no encontrado", 404)
                id_libro, titulo_act, anio_act, precio_act, stock_act, id_formato_act = row

                if "format" in data:
                    id_formato_act = get_or_create_id(cur, "formatos", "id_formato", "nombre_formato", data["format"])

                cur.execute(
                    """UPDATE libros SET titulo = %s, anio_publicacion = %s, precio = %s,
                       stock = %s, id_formato = %s WHERE id_libro = %s""",
                    (
                        data.get("title", titulo_act),
                        data.get("publicationYear", anio_act),
                        data.get("price", precio_act),
                        data.get("stock", stock_act),
                        id_formato_act,
                        id_libro,
                    ),
                )

                if "authors" in data:
                    cur.execute("DELETE FROM libro_autor WHERE id_libro = %s", (id_libro,))
                if "genres" in data:
                    cur.execute("DELETE FROM libro_genero WHERE id_libro = %s", (id_libro,))
                if "images" in data:
                    cur.execute("DELETE FROM imagenes_libro WHERE id_libro = %s", (id_libro,))
                if "concepts" in data:
                    cur.execute("DELETE FROM libro_concepto WHERE id_libro = %s", (id_libro,))

                guardar_relaciones(cur, id_libro, data)
    finally:
        conn.close()

    return books_xml_response(fetch_books("l.isbn = %s", [isbn]))


@app.route("/api/libros/<isbn>", methods=["DELETE"])
def eliminar_libro(isbn):
    """
    Elimina un libro por ISBN
    ---
    tags: [Libros]
    produces: [application/xml]
    parameters:
      - {name: isbn, in: path, type: string, required: true}
    responses:
      200:
        description: Libro eliminado (XML)
      404:
        description: Libro no encontrado
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM libros WHERE isbn = %s RETURNING id_libro", (isbn,))
                if cur.fetchone() is None:
                    return error_xml_response("Libro no encontrado", 404)
    finally:
        conn.close()

    root = ET.Element("result")
    ET.SubElement(root, "message").text = "Libro eliminado"
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(body, status=200, mimetype="application/xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)), debug=True)
