"""Microservicio Pagos (Flask sin blueprints): registra pagos y pasa el pedido a 'pagado'."""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, g, jsonify  # noqa: E402

import repository  # noqa: E402
from common import db as common_db, jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, requiere_jwt  # noqa: E402
from common.ops import registrar_operacion  # noqa: E402
from common.web import (Invalido, NoEncontrado, Prohibido, configurar_app,  # noqa: E402
                        crear_swagger, cuerpo_json)

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Pagos API")
registrar_operacion(app, "pagos", db_check=lambda: common_db.ping())

METODOS = ("tarjeta", "transferencia", "efectivo")


def _es_admin():
    return g.role_id == ROLE_ADMIN


def _monto_opcional(valor):
    if valor is None:
        return None
    if type(valor) not in (int, float) or valor <= 0:
        raise Invalido("monto debe ser un numero positivo.")
    return Decimal(str(valor))


@app.route("/api/pagos", methods=["POST"])
@requiere_jwt()
def registrar_pago():
    """Registra el pago de un pedido pendiente y lo marca como pagado (misma transaccion).
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [id_pedido, metodo]
          properties:
            id_pedido: {type: integer}
            metodo: {type: string, enum: [tarjeta, transferencia, efectivo]}
            monto: {type: number, description: "Opcional; si se envia debe igualar el total"}
    responses:
      201: {description: Pago registrado}
      400: {description: Datos invalidos}
      403: {description: Pedido ajeno}
      404: {description: Pedido inexistente}
      409: {description: Pedido no pendiente, ya pagado o monto distinto}
    """
    datos = cuerpo_json()
    id_pedido, metodo = datos.get("id_pedido"), datos.get("metodo")
    if type(id_pedido) is not int or id_pedido <= 0:
        raise Invalido("id_pedido debe ser un entero positivo.")
    if metodo not in METODOS:
        raise Invalido("metodo debe ser tarjeta, transferencia o efectivo.")
    monto = _monto_opcional(datos.get("monto"))
    pago = repository.registrar(id_pedido, g.user_id, _es_admin(), metodo, monto)
    return jsonify(pago), 201


@app.route("/api/pagos", methods=["GET"])
@requiere_jwt()
def listar_pagos():
    """Lista pagos: un usuario ve los de sus pedidos, un admin ve todos.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Lista de pagos}
    """
    return jsonify(repository.listar(None if _es_admin() else g.user_id))


@app.route("/api/pagos/<int:id_pago>", methods=["GET"])
@requiere_jwt()
def ver_pago(id_pago):
    """Un pago (de un pedido propio o admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Pago}
      403: {description: Pago ajeno}
      404: {description: No existe}
    """
    pago = repository.obtener(id_pago)
    if not pago:
        raise NoEncontrado("Pago no encontrado.")
    if not _es_admin() and pago["id_cuenta"] != g.user_id:
        raise Prohibido("El pago no te pertenece.")
    return jsonify(pago)


@app.route("/api/pagos/<int:id_pago>", methods=["DELETE"])
@requiere_jwt(roles=[ROLE_ADMIN])
def reembolsar_pago(id_pago):
    """Reembolsa un pago (solo admin): borra el pago y el pedido vuelve a pendiente.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Reembolsado}
      404: {description: No existe}
      409: {description: El pedido ya fue enviado o cancelado}
    """
    repository.reembolsar(id_pago)
    return jsonify({"mensaje": "Pago reembolsado; el pedido volvio a pendiente."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5005")))
