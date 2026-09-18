"""Logica pura de seguridad: hashing de contrasenas y codigos 2FA,
generacion de codigos y tokens de sesion. No importa Flask ni psycopg."""

import secrets
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password):
    return generate_password_hash(password)


def verificar_password(password, password_hash):
    return check_password_hash(password_hash, password)


def generar_codigo():
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_codigo(codigo):
    return generate_password_hash(codigo)


def verificar_codigo(codigo, codigo_hash):
    return check_password_hash(codigo_hash, codigo)


def generar_token():
    return secrets.token_hex(32)
