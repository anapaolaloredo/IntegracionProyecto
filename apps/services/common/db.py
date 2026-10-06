"""Conexion psycopg 3 a la base `library`, configurada solo por entorno."""

import os

import psycopg


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "library"),
        user=os.getenv("DB_USER", "library_user"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def ping():
    """True si PostgreSQL responde a SELECT 1 (para /health)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        return cur.fetchone()[0] == 1
