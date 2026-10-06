"""Microservicio Pedidos (Flask sin blueprints): pedidos, lineas, stock y estados."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, g, jsonify  # noqa: E402

import repository  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, requiere_jwt  # noqa: E402
from common.web import (Invalido, NoEncontrado, Prohibido, configurar_app,  # noqa: E402
                        crear_swagger, cuerpo_json)

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Pedidos API")


def _es_admin():
    return g.role_id == ROLE_ADMIN


def _entero_positivo(valor):
    return type(valor) is int and valor > 0


def _parsear_lineas(datos):
    """Valida y fusiona lineas repetidas del mismo libro. Regresa [(id_libro, cantidad)] ordenado."""
    lineas = datos.get("lineas")
    if not isinstance(lineas, list) or not lineas:
        raise Invalido("lineas debe ser una lista no vacia.")
    acumulado = {}
    for linea in lineas:
        if not isinstance(linea, dict):
            raise Invalido("Cada linea debe ser un objeto {id_libro, cantidad}.")
        id_libro, cantidad = linea.get("id_libro"), linea.get("cantidad")
        if not _entero_positivo(id_libro) or not _entero_positivo(cantidad):
            raise Invalido("id_libro y cantidad deben ser enteros positivos.")
        acumulado[id_libro] = acumulado.get(id_libro, 0) + cantidad
    return sorted(acumulado.items())


def _pedido_visible(id_pedido):
    pedido = repository.obtener(id_pedido)
    if not pedido:
        raise NoEncontrado("Pedido no encontrado.")
    if not _es_admin() and pedido["id_cuenta"] != g.user_id:
        raise Prohibido("El pedido no te pertenece.")
    return pedido


@app.route("/api/pedidos", methods=["POST"])
@requiere_jwt()
def crear_pedido():
    """Crea un pedido y descuenta el stock en una transaccion.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [lineas]
          properties:
            lineas:
              type: array
              items: {type: object, properties: {id_libro: {type: integer}, cantidad: {type: integer}}}
    responses:
      201: {description: Pedido creado}
      400: {description: Lineas invalidas}
      404: {description: Libro inexistente}
      409: {description: Stock insuficiente}
    """
    items = _parsear_lineas(cuerpo_json())
    id_pedido = repository.crear(g.user_id, items)
    return jsonify(repository.obtener(id_pedido)), 201


@app.route("/api/pedidos", methods=["GET"])
@requiere_jwt()
def listar_pedidos():
    """Lista pedidos: un usuario ve los suyos, un admin ve todos.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Lista de pedidos}
    """
    return jsonify(repository.listar(None if _es_admin() else g.user_id))


@app.route("/api/pedidos/<int:id_pedido>", methods=["GET"])
@requiere_jwt()
def ver_pedido(id_pedido):
    """Un pedido con sus lineas (propio o admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Pedido}
      403: {description: Pedido ajeno}
      404: {description: No existe}
    """
    return jsonify(_pedido_visible(id_pedido))


@app.route("/api/pedidos/<int:id_pedido>/estado", methods=["PATCH", "PUT"])
@requiere_jwt()
def cambiar_estado(id_pedido):
    """Cambia el estado: pendiente->cancelado (dueno o admin), pagado->enviado (admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Estado cambiado}
      400: {description: Estado invalido}
      403: {description: Sin permiso}
      409: {description: Transicion no permitida}
    """
    nuevo = cuerpo_json().get("estado")
    if not isinstance(nuevo, str):
        raise Invalido("estado debe ser texto.")
    repository.cambiar_estado(id_pedido, nuevo, g.user_id, _es_admin())
    return jsonify({"id_pedido": id_pedido, "estado": nuevo})


@app.route("/api/pedidos/<int:id_pedido>", methods=["DELETE"])
@requiere_jwt(roles=[ROLE_ADMIN])
def eliminar_pedido(id_pedido):
    """Elimina un pedido cancelado (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Eliminado}
      404: {description: No existe}
      409: {description: El pedido no esta cancelado}
    """
    repository.eliminar(id_pedido)
    return jsonify({"mensaje": "Pedido eliminado."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5004")))
