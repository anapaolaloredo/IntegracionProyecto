"""Microservicio Users (Flask sin blueprints): usuarios, roles, correos y contrasenas.
Opera sobre cuentas/personas, las mismas tablas que usa login."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from flask import Flask, g, jsonify, request  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

import repository  # noqa: E402
from common import db as common_db  # noqa: E402
from common import jwt_auth  # noqa: E402
from common.jwt_auth import ROLE_ADMIN, ROLE_IDS, ROLE_NAMES, requiere_jwt  # noqa: E402
from common.ops import registrar_operacion  # noqa: E402
from common.web import (Invalido, NoEncontrado, Prohibido, configurar_app,  # noqa: E402
                        crear_swagger, cuerpo_json)

jwt_auth.obtener_secret()  # no arranca sin SECRET_KEY

app = Flask(__name__)
configurar_app(app)
crear_swagger(app, "Users API")
registrar_operacion(app, "users", db_check=lambda: common_db.ping())

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CAMPOS_PERFIL = ("correo", "nombre", "apellido_paterno", "apellido_materno")


def _es_admin():
    return g.role_id == ROLE_ADMIN


def _solo_propio_o_admin(id_usuario):
    if not _es_admin() and g.user_id != id_usuario:
        raise Prohibido("Solo puedes acceder a tu propio usuario.")


def _usuario_o_404(id_usuario):
    usuario = repository.obtener(id_usuario)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado.")
    return usuario


def _publico(usuario):
    usuario = dict(usuario)
    usuario["role_id"] = ROLE_IDS[usuario["rol"]]
    return usuario


def _texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise Invalido(f"El campo {campo} debe ser texto no vacio.")
    return valor.strip()


def _validar_perfil(datos, parcial):
    limpio = {}
    for campo in CAMPOS_PERFIL:
        if campo not in datos:
            if not parcial:
                raise Invalido(f"El campo {campo} es obligatorio.")
            continue
        limpio[campo] = _texto(datos[campo], campo)
    if "correo" in limpio and not REGEX_EMAIL.match(limpio["correo"]):
        raise Invalido("El correo no tiene un formato valido.")
    if parcial and not limpio:
        raise Invalido("No se envio ningun campo para actualizar.")
    return limpio


def _validar_password(valor, campo="password"):
    if not isinstance(valor, str) or len(valor) < 8:
        raise Invalido(f"{campo} debe tener al menos 8 caracteres.")
    return valor


def _validar_rol(valor):
    if valor not in ROLE_IDS:
        raise Invalido("rol debe ser 'admin' o 'cliente'.")
    return valor


@app.route("/api/roles", methods=["GET"])
def listar_roles():
    """Lista los roles disponibles (publico).
    ---
    responses:
      200:
        description: "[{role_id, nombre}]"
    """
    return jsonify([{"role_id": rid, "nombre": nombre} for rid, nombre in ROLE_NAMES.items()])


@app.route("/api/users", methods=["GET"])
@requiere_jwt(roles=[ROLE_ADMIN])
def listar_usuarios():
    """Lista todos los usuarios (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Lista de usuarios}
      401: {description: Token ausente o invalido}
      403: {description: Rol insuficiente}
    """
    return jsonify([_publico(u) for u in repository.listar()])


@app.route("/api/users/<int:id_usuario>", methods=["GET"])
@requiere_jwt()
def ver_usuario(id_usuario):
    """Ve un usuario (el propio o cualquiera si eres admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Usuario}
      403: {description: Usuario ajeno}
      404: {description: No existe}
    """
    _solo_propio_o_admin(id_usuario)
    return jsonify(_publico(_usuario_o_404(id_usuario)))


@app.route("/api/users", methods=["POST"])
@requiere_jwt(roles=[ROLE_ADMIN])
def crear_usuario():
    """Crea un usuario (solo admin). La contrasena se guarda con hash.
    ---
    security:
      - Bearer: []
    responses:
      201: {description: Creado}
      400: {description: Datos invalidos}
      409: {description: Correo duplicado}
    """
    datos = cuerpo_json()
    perfil = _validar_perfil(datos, parcial=False)
    password = _validar_password(datos.get("password"))
    rol = _validar_rol(datos.get("rol", "cliente"))
    id_usuario = repository.crear(perfil["correo"], generate_password_hash(password), rol,
                                  perfil["nombre"], perfil["apellido_paterno"], perfil["apellido_materno"])
    return jsonify({"id_usuario": id_usuario}), 201


@app.route("/api/users/<int:id_usuario>", methods=["PUT", "PATCH"])
@requiere_jwt()
def actualizar_usuario(id_usuario):
    """Actualiza el perfil. PUT exige todos los campos; PATCH acepta un subconjunto.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Actualizado}
      400: {description: Datos invalidos}
      403: {description: Usuario ajeno}
      404: {description: No existe}
    """
    _solo_propio_o_admin(id_usuario)
    campos = _validar_perfil(cuerpo_json(), parcial=request.method == "PATCH")
    if not repository.actualizar(id_usuario, campos):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify(_publico(_usuario_o_404(id_usuario)))


@app.route("/api/users/<int:id_usuario>/password", methods=["PATCH"])
@requiere_jwt()
def cambiar_password(id_usuario):
    """Cambia la contrasena. El propio usuario debe enviar password_actual; un admin puede resetear la de otros.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Contrasena cambiada}
      400: {description: Datos invalidos}
      403: {description: Usuario ajeno o contrasena actual incorrecta}
      404: {description: No existe}
    """
    _solo_propio_o_admin(id_usuario)
    datos = cuerpo_json()
    nueva = _validar_password(datos.get("password_nueva"), "password_nueva")
    if g.user_id == id_usuario:
        actual = repository.obtener_hash(id_usuario)
        if actual is None:
            raise NoEncontrado("Usuario no encontrado.")
        if not isinstance(datos.get("password_actual"), str) or not check_password_hash(actual, datos["password_actual"]):
            raise Prohibido("La contrasena actual es incorrecta.")
    if not repository.cambiar_password(id_usuario, generate_password_hash(nueva)):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify({"mensaje": "Contrasena actualizada."})


@app.route("/api/users/<int:id_usuario>/rol", methods=["PATCH"])
@requiere_jwt(roles=[ROLE_ADMIN])
def cambiar_rol(id_usuario):
    """Cambia el rol (solo admin). El nuevo rol aplica al siguiente JWT que se emita.
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Rol cambiado}
      400: {description: Rol invalido}
      404: {description: No existe}
    """
    rol = _validar_rol(cuerpo_json().get("rol"))
    if not repository.cambiar_rol(id_usuario, rol):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify({"id_usuario": id_usuario, "rol": rol, "role_id": ROLE_IDS[rol]})


@app.route("/api/users/<int:id_usuario>", methods=["DELETE"])
@requiere_jwt(roles=[ROLE_ADMIN])
def eliminar_usuario(id_usuario):
    """Elimina un usuario (solo admin).
    ---
    security:
      - Bearer: []
    responses:
      200: {description: Eliminado}
      404: {description: No existe}
      409: {description: Tiene pedidos}
    """
    if not repository.eliminar(id_usuario):
        raise NoEncontrado("Usuario no encontrado.")
    return jsonify({"mensaje": "Usuario eliminado."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5002")))
