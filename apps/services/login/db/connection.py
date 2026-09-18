"""Capa de conexion a PostgreSQL. Unico lugar del modulo que importa
psycopg directamente; el resto del codigo pasa por repository.py."""

import psycopg
from config.settings import DB_CONFIG


def get_connection():
    return psycopg.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
