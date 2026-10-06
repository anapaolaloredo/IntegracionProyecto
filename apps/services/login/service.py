"""Logica de negocio: valida datos, coordina repository/security/mail, y
traduce reglas de negocio a excepciones de dominio. No conoce Flask."""

import re
import time
from datetime import datetime, timedelta, timezone

from config.settings import SESSION_TTL_MINUTES, CODE_TTL_MINUTES, REFRESH_TTL_DAYS
from common.jwt_auth import ROLE_IDS, TokenInvalido, crear_token, decodificar
from db import repository
from auth.security import (
    hash_password, verificar_password,
    generar_codigo, hash_codigo, verificar_codigo,
)
from mail.sender import enviar_codigo
from errors import (
    CamposFaltantes, EmailInvalido, PasswordDebil, EmailDuplicado,
    CredencialesInvalidas, CodigoInvalido, SesionInvalida,
)

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def registrar(nombre, apellido_paterno, apellido_materno, email, password):
    if not all([nombre, apellido_paterno, apellido_materno, email, password]):
        raise CamposFaltantes("Todos los campos son obligatorios.")
    if not REGEX_EMAIL.match(email):
        raise EmailInvalido("El correo no tiene un formato valido.")
    if len(password) < 8:
        raise PasswordDebil("La contrasena debe tener al menos 8 caracteres.")
    if repository.obtener_usuario_por_correo(email):
        raise EmailDuplicado("Ese correo ya esta registrado.")
    return repository.crear_usuario(
        email, hash_password(password), nombre, apellido_paterno, apellido_materno
    )


def iniciar_login(email, password):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario or not verificar_password(password, usuario["contrasena_hash"]):
        raise CredencialesInvalidas("Credenciales invalidas.")
    codigo = generar_codigo()
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
    repository.guardar_codigo(usuario["id_usuario"], hash_codigo(codigo), expira_en)
    enviar_codigo(email, codigo)


def _emitir_acceso(usuario):
    role_id = ROLE_IDS[usuario["rol"]]
    token = crear_token(usuario["id_usuario"], role_id, "access", SESSION_TTL_MINUTES * 60)
    return token, decodificar(token, "access")["exp"]


def _datos_acceso(usuario):
    token, exp = _emitir_acceso(usuario)
    return {
        "session_token": token,
        "expira_en": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
        "segundos_restantes": max(0, exp - int(time.time())),
    }


def _decodificar_o_none(token, tipo):
    if not token:
        return None
    try:
        return decodificar(token, tipo)
    except TokenInvalido:
        return None


def verificar_login(email, codigo):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario:
        raise CodigoInvalido("Codigo invalido o expirado.")
    pendiente = repository.obtener_codigo_vigente(usuario["id_usuario"])
    if not pendiente or not verificar_codigo(codigo, pendiente["codigo_hash"]):
        raise CodigoInvalido("Codigo invalido o expirado.")
    repository.marcar_codigo_usado(pendiente["id_codigo"])
    role_id = ROLE_IDS[usuario["rol"]]
    return {
        "session_token": crear_token(usuario["id_usuario"], role_id, "access", SESSION_TTL_MINUTES * 60),
        "refresh_token": crear_token(usuario["id_usuario"], role_id, "refresh", REFRESH_TTL_DAYS * 86400),
    }


def cerrar_sesion(token):
    # JWT sin estado: el token vive hasta expirar; aqui solo se valida.
    if not _decodificar_o_none(token, "access"):
        raise SesionInvalida("Token de sesion invalido o expirado.")


def consultar_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        return {"autenticado": False}
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        return {"autenticado": False}
    return {
        "autenticado": True,
        "id_usuario": usuario["id_usuario"],
        "email": usuario["correo"],
        "nombre": usuario["nombre"],
        "role_id": datos["role_id"],
        "expira_en": datetime.fromtimestamp(datos["exp"], tz=timezone.utc).isoformat(),
        "segundos_restantes": max(0, datos["exp"] - int(time.time())),
    }


def extender_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        raise SesionInvalida("Token de sesion invalido o expirado.")
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    return _datos_acceso(usuario)


def refrescar_sesion(refresh_token):
    datos = _decodificar_o_none(refresh_token, "refresh")
    if not datos:
        raise SesionInvalida("Refresh token invalido o expirado.")
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    return _datos_acceso(usuario)


def verificar_salud():
    try:
        return repository.verificar_conexion()
    except Exception:
        return False
