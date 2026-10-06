"""Validacion JWT compartida por todos los microservicios (HS256).

La SECRET_KEY se lee solo del entorno. Los claims obligatorios son
exp, iat, user_id, role_id y type ("access" | "refresh")."""

import os
import time
from functools import wraps

import jwt
from flask import g, jsonify, request

ALGORITHM = "HS256"
ROLE_ADMIN = 1
ROLE_USER = 2
ROLE_IDS = {"admin": ROLE_ADMIN, "cliente": ROLE_USER}
ROLE_NAMES = {valor: nombre for nombre, valor in ROLE_IDS.items()}
_CLAIMS_OBLIGATORIOS = ["exp", "iat", "user_id", "role_id", "type"]


class TokenInvalido(Exception):
    """El token falta, esta mal formado, vencio, o sus claims no son validos."""


def obtener_secret():
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY no esta definida en el entorno")
    if secret.lower().startswith("change-me") or len(secret) < 32:
        raise RuntimeError(
            "SECRET_KEY no es valida: debe tener al menos 32 caracteres y no ser el valor de ejemplo"
        )
    return secret


def crear_token(user_id, role_id, tipo, ttl_segundos):
    ahora = int(time.time())
    payload = {"user_id": user_id, "role_id": role_id, "type": tipo,
               "iat": ahora, "exp": ahora + int(ttl_segundos)}
    return jwt.encode(payload, obtener_secret(), algorithm=ALGORITHM)


def decodificar(token, tipo="access"):
    try:
        datos = jwt.decode(token, obtener_secret(), algorithms=[ALGORITHM],
                           options={"require": _CLAIMS_OBLIGATORIOS})
    except jwt.PyJWTError as exc:
        raise TokenInvalido(str(exc)) from exc
    if datos["type"] != tipo:
        raise TokenInvalido("tipo de token incorrecto")
    if type(datos["user_id"]) is not int or type(datos["role_id"]) is not int \
            or datos["role_id"] not in tuple(ROLE_NAMES):
        raise TokenInvalido("claims invalidos")
    return datos


def extraer_token(valor_header):
    partes = (valor_header or "").split()
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1]
    return None


def _error_json(mensaje, status):
    respuesta = jsonify({"mensaje": mensaje})
    respuesta.status_code = status
    return respuesta


def requiere_jwt(roles=None, error_response=None, on_event=None):
    """Exige Authorization: Bearer <JWT de acceso>. `roles` es una lista de
    role_id permitidos (None = cualquier rol valido). Deja g.user_id y g.role_id."""
    responder_error = error_response or _error_json

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            token = extraer_token(request.headers.get("Authorization"))
            datos = None
            resultado = None
            if not token:
                resultado = (401, "Se requiere Authorization: Bearer <token>")
            else:
                try:
                    datos = decodificar(token, "access")
                except TokenInvalido:
                    resultado = (401, "Token invalido o expirado")
                else:
                    if roles is not None and datos["role_id"] not in roles:
                        resultado = (403, "Rol insuficiente para esta operacion")
            if on_event:
                on_event(token, datos, resultado)
            if resultado:
                return responder_error(resultado[1], resultado[0])
            g.user_id = datos["user_id"]
            g.role_id = datos["role_id"]
            return vista(*args, **kwargs)
        return envoltura
    return decorador
