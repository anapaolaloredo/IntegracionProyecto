"""Capa de conexion a PostgreSQL. Unico lugar del modulo que importa
psycopg2 directamente; el resto del codigo pasa por repository.py."""

import psycopg2
from config.settings import DB_CONFIG


def get_connection():
    return psycopg2.connect(**DB_CONFIG)
