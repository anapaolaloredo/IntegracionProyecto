"""Ayudas para las pruebas de los servicios (requiere SECRET_KEY en el entorno)."""

from common.jwt_auth import ROLE_USER, crear_token


def auth_header(user_id=2, role_id=ROLE_USER, tipo="access", ttl=1800):
    return {"Authorization": f"Bearer {crear_token(user_id, role_id, tipo, ttl)}"}
