"""Logica de negocio: valida datos, coordina repository/security/mail, y
traduce reglas de negocio a excepciones de dominio. No conoce Flask."""

import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from config.settings import SESSION_TTL_MINUTES, CODE_TTL_MINUTES, REFRESH_TTL_DAYS
from common import redis_store
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


SESSION_TTL = SESSION_TTL_MINUTES * 60
REFRESH_TTL = REFRESH_TTL_DAYS * 86400


def _iso(exp):
    return datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()


def _nuevo_acceso(usuario, jti_refresh, exp_refresh):
    """Emite un JWT de acceso y guarda su sesion en Redis (TTL = vigencia del token).
    Lanza RedisNoDisponible si no puede guardarla: nunca se entrega un token sin sesion."""
    role_id = ROLE_IDS[usuario["rol"]]
    jti = uuid.uuid4().hex
    token = crear_token(usuario["id_usuario"], role_id, "access", SESSION_TTL, jti=jti)
    exp = decodificar(token, "access")["exp"]
    redis_store.guardar_sesion(jti, {
        "user_id": usuario["id_usuario"], "role_id": role_id, "email": usuario["correo"],
        "jti_refresh": jti_refresh, "exp_refresh": exp_refresh}, SESSION_TTL)
    redis_store.registrar_acceso_de_refresh(jti_refresh, jti)
    return {"session_token": token, "expira_en": _iso(exp),
            "segundos_restantes": max(0, exp - int(time.time()))}


def _decodificar_o_none(token, tipo):
    if not token:
        return None
    try:
        return decodificar(token, tipo)
    except TokenInvalido:
        return None


def _sesion_activa(datos):
    """Sesion vigente en Redis para un JWT de acceso ya decodificado, o SesionInvalida."""
    if redis_store.jti_revocado(datos["jti"]):
        raise SesionInvalida("Token de sesion revocado.")
    sesion = redis_store.obtener_sesion(datos["jti"])
    if sesion is None:
        raise SesionInvalida("La sesion no existe o ya expiro.")
    jti_refresh = sesion["jti_refresh"]
    if (redis_store.jti_revocado(jti_refresh) or not redis_store.refresh_vigente(jti_refresh)
            or sesion["exp_refresh"] <= int(time.time())):
        raise SesionInvalida("La sesion de origen ya no es valida.")
    return sesion


def _cerrar_acceso(jti, exp):
    redis_store.revocar_jti(jti, exp)
    redis_store.borrar_sesion(jti)


def verificar_login(email, codigo):
    usuario = repository.obtener_usuario_por_correo(email)
    if not usuario:
        raise CodigoInvalido("Codigo invalido o expirado.")
    pendiente = repository.obtener_codigo_vigente(usuario["id_usuario"])
    if not pendiente or not verificar_codigo(codigo, pendiente["codigo_hash"]):
        raise CodigoInvalido("Codigo invalido o expirado.")
    role_id = ROLE_IDS[usuario["rol"]]
    jti_refresh = uuid.uuid4().hex
    refresh = crear_token(usuario["id_usuario"], role_id, "refresh", REFRESH_TTL, jti=jti_refresh)
    exp_refresh = decodificar(refresh, "refresh")["exp"]
    redis_store.guardar_refresh(jti_refresh, usuario["id_usuario"], REFRESH_TTL)
    acceso = _nuevo_acceso(usuario, jti_refresh, exp_refresh)
    # El codigo se marca usado solo cuando la sesion ya quedo guardada: si Redis falla no se quema.
    repository.marcar_codigo_usado(pendiente["id_codigo"])
    return {"session_token": acceso["session_token"], "refresh_token": refresh}


def cerrar_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        raise SesionInvalida("Token de sesion invalido o expirado.")
    if redis_store.jti_revocado(datos["jti"]):
        raise SesionInvalida("Token de sesion revocado.")
    sesion = redis_store.obtener_sesion(datos["jti"])
    if sesion is None:
        raise SesionInvalida("La sesion no existe o ya expiro.")
    # Todo es idempotente y el token presentado se cierra al final: si algo falla antes,
    # el reintento con el mismo token termina el trabajo.
    jti_refresh = sesion["jti_refresh"]
    redis_store.revocar_jti(jti_refresh, sesion["exp_refresh"])
    exp_hermano = int(time.time()) + SESSION_TTL
    for jti in redis_store.accesos_de_refresh(jti_refresh):
        if jti != datos["jti"]:
            _cerrar_acceso(jti, exp_hermano)  # accesos hermanos vivos de este login
    redis_store.borrar_refresh(jti_refresh)
    redis_store.borrar_accesos_de_refresh(jti_refresh)
    _cerrar_acceso(datos["jti"], datos["exp"])


def consultar_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        return {"autenticado": False}
    try:
        _sesion_activa(datos)
    except SesionInvalida:
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
        "expira_en": _iso(datos["exp"]),
        "segundos_restantes": max(0, datos["exp"] - int(time.time())),
    }


def extender_sesion(token):
    datos = _decodificar_o_none(token, "access")
    if not datos:
        raise SesionInvalida("Token de sesion invalido o expirado.")
    sesion = _sesion_activa(datos)
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    nuevo = _nuevo_acceso(usuario, sesion["jti_refresh"], sesion["exp_refresh"])
    _cerrar_acceso(datos["jti"], datos["exp"])  # el token anterior deja de valer
    return nuevo


def refrescar_sesion(refresh_token):
    datos = _decodificar_o_none(refresh_token, "refresh")
    if not datos:
        raise SesionInvalida("Refresh token invalido o expirado.")
    if redis_store.jti_revocado(datos["jti"]) or not redis_store.refresh_vigente(datos["jti"]):
        raise SesionInvalida("Refresh token revocado o desconocido.")
    usuario = repository.obtener_usuario_por_id(datos["user_id"])
    if not usuario:
        raise SesionInvalida("La cuenta ya no existe.")
    return _nuevo_acceso(usuario, datos["jti"], datos["exp"])


def verificar_salud():
    try:
        return repository.verificar_conexion()
    except Exception:
        return False
