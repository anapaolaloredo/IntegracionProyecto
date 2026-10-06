"""Microservicio Authors (Flask sin blueprints): autores y su relacion con libros.
Lecturas publicas; toda escritura exige JWT con rol admin."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, jsonify  # noqa: E402

import repository  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, requiere_jwt  # noqa: E402
from common.web import Invalido, NoEncontrado, configurar_app, crear_swagger, cuerpo_json  # noqa: E402

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Authors API")

solo_admin = requiere_jwt(roles=[ROLE_ADMIN])


def _nombre(datos):
    nombre = datos.get("nombre_autor")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 150:
        raise Invalido("nombre_autor debe ser texto no vacio de maximo 150 caracteres.")
    return nombre.strip()


def _entero_positivo(valor):
    return type(valor) is int and valor > 0


@app.route("/api/authors", methods=["GET"])
def listar_autores():
    """Lista los autores (publico).
    ---
    responses:
      200: {description: "[{id_autor, nombre_autor}]"}
    """
    return jsonify(repository.listar())


@app.route("/api/authors/<int:id_autor>", methods=["GET"])
def ver_autor(id_autor):
    """Un autor con sus libros (publico).
    ---
    responses:
      200: {description: Autor con libros}
      404: {description: No existe}
    """
    autor = repository.obtener(id_autor)
    if not autor:
        raise NoEncontrado("Autor no encontrado.")
    return jsonify(autor)


@app.route("/api/authors", methods=["POST"])
@solo_admin
def crear_autor():
    """Crea un autor (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      201: {description: Creado}
      400: {description: Datos invalidos}
      409: {description: Ya existe}
    """
    nombre = _nombre(cuerpo_json())
    return jsonify({"id_autor": repository.crear(nombre), "nombre_autor": nombre}), 201


@app.route("/api/authors/<int:id_autor>", methods=["PUT", "PATCH"])
@solo_admin
def renombrar_autor(id_autor):
    """Renombra un autor (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Actualizado}
      404: {description: No existe}
      409: {description: Nombre duplicado}
    """
    nombre = _nombre(cuerpo_json())
    if not repository.renombrar(id_autor, nombre):
        raise NoEncontrado("Autor no encontrado.")
    return jsonify({"id_autor": id_autor, "nombre_autor": nombre})


@app.route("/api/authors/<int:id_autor>", methods=["DELETE"])
@solo_admin
def eliminar_autor(id_autor):
    """Elimina un autor sin libros (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Eliminado}
      404: {description: No existe}
      409: {description: Tiene libros asociados}
    """
    if not repository.eliminar(id_autor):
        raise NoEncontrado("Autor no encontrado.")
    return jsonify({"mensaje": "Autor eliminado."})


@app.route("/api/authors/<int:id_autor>/books", methods=["POST"])
@solo_admin
def vincular_libro(id_autor):
    """Asocia un libro al autor (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      201: {description: Vinculado}
      400: {description: id_libro invalido}
      404: {description: Autor o libro inexistente}
    """
    id_libro = cuerpo_json().get("id_libro")
    if not _entero_positivo(id_libro):
        raise Invalido("id_libro debe ser un entero positivo.")
    repository.vincular(id_autor, id_libro)
    return jsonify({"id_autor": id_autor, "id_libro": id_libro}), 201


@app.route("/api/authors/<int:id_autor>/books/<int:id_libro>", methods=["DELETE"])
@solo_admin
def desvincular_libro(id_autor, id_libro):
    """Quita la relacion autor-libro (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Desvinculado}
      404: {description: La relacion no existe}
    """
    if not repository.desvincular(id_autor, id_libro):
        raise NoEncontrado("La relacion autor-libro no existe.")
    return jsonify({"mensaje": "Relacion eliminada."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5003")))
