"""Logica de negocio: valida datos, coordina repository/security/mail, y
traduce reglas de negocio a excepciones de dominio. No conoce Flask."""

import re
from datetime import datetime, timedelta, timezone

from config.settings import SESSION_TTL_MINUTES, CODE_TTL_MINUTES
from db import repository
from auth.security import (
    hash_password, verificar_password,
    generar_codigo, hash_codigo, verificar_codigo,
    generar_token,
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


def verificar_login(email, codigo):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario:
        raise CodigoInvalido("Codigo invalido o expirado.")
    pendiente = repository.obtener_codigo_vigente(usuario["id_usuario"])
    if not pendiente or not verificar_codigo(codigo, pendiente["codigo_hash"]):
        raise CodigoInvalido("Codigo invalido o expirado.")
    repository.marcar_codigo_usado(pendiente["id_codigo"])
    token = generar_token()
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)
    repository.crear_sesion(token, usuario["id_usuario"], expira_en)
    return token


def cerrar_sesion(token):
    if not token or not repository.obtener_sesion_vigente(token):
        raise SesionInvalida("Token de sesion invalido o inexistente.")
    repository.eliminar_sesion(token)


def consultar_sesion(token):
    if not token:
        return {"autenticado": False}
    sesion = repository.obtener_sesion_vigente(token)
    if not sesion:
        return {"autenticado": False}
    return {
        "autenticado": True,
        "id_usuario": sesion["id_usuario"],
        "email": sesion["correo"],
        "nombre": sesion["nombre"],
        "expira_en": sesion["expira_en"].isoformat(),
        "segundos_restantes": sesion["segundos_restantes"],
    }


def extender_sesion(token):
    if not token or not repository.obtener_sesion_vigente(token):
        raise SesionInvalida("Token de sesion invalido o expirado.")
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)
    repository.extender_sesion(token, expira_en)
    sesion = repository.obtener_sesion_vigente(token)
    return {
        "expira_en": sesion["expira_en"].isoformat(),
        "segundos_restantes": sesion["segundos_restantes"],
    }


def verificar_salud():
    try:
        return repository.verificar_conexion()
    except Exception:
        return False
