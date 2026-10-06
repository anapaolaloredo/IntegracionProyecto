"""Ayudas para las pruebas de los servicios (requiere SECRET_KEY en el entorno)."""

import fakeredis

from common import metrics, redis_store
from common.jwt_auth import ROLE_USER, crear_token


def auth_header(user_id=2, role_id=ROLE_USER, tipo="access", ttl=1800):
    return {"Authorization": f"Bearer {crear_token(user_id, role_id, tipo, ttl)}"}


def instalar_redis_falso():
    """Redis en memoria; devuelve el FakeServer para poder apagarlo con redis_caido()."""
    servidor = fakeredis.FakeServer()
    redis_store.configurar_cliente(fakeredis.FakeRedis(server=servidor, decode_responses=True))
    metrics.reiniciar()
    return servidor


def redis_caido(servidor):
    servidor.connected = False


def redis_disponible(servidor):
    servidor.connected = True


def quitar_redis_falso():
    redis_store.reiniciar()
