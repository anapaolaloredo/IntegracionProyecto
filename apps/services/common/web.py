"""Utilidades Flask compartidas por los microservicios nuevos."""

import os
from datetime import date, datetime
from decimal import Decimal

from flasgger import Swagger
from flask import jsonify, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS


class ErrorDominio(Exception):
    status = 400


class Invalido(ErrorDominio):
    status = 400


class Prohibido(ErrorDominio):
    status = 403


class NoEncontrado(ErrorDominio):
    status = 404


class Conflicto(ErrorDominio):
    status = 409


class _Proveedor(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def parse_origins(valor):
    origenes = [o.strip() for o in (valor or "*").split(",") if o.strip()]
    return origenes or ["*"]


def configurar_app(app):
    """CORS por CORS_ORIGINS, JSON con fechas ISO y errores de dominio en JSON."""
    CORS(app, origins=parse_origins(os.getenv("CORS_ORIGINS", "*")))
    app.json = _Proveedor(app)

    @app.errorhandler(ErrorDominio)
    def _dominio(err):
        return jsonify({"mensaje": str(err)}), err.status

    @app.errorhandler(404)
    def _no_encontrada(_):
        return jsonify({"mensaje": "Ruta no encontrada"}), 404

    @app.errorhandler(405)
    def _metodo(_):
        return jsonify({"mensaje": "Metodo no permitido"}), 405


def cuerpo_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise Invalido("Se esperaba un cuerpo JSON (objeto).")
    return datos


def crear_swagger(app, titulo):
    app.config["SWAGGER"] = {"title": titulo, "uiversion": 3}
    return Swagger(app, template={"securityDefinitions": {"Bearer": {
        "type": "apiKey", "name": "Authorization", "in": "header",
        "description": "Bearer <JWT de acceso>"}}})
