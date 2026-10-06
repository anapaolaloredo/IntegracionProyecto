"""Configuracion del microservicio de login, leida exclusivamente de
variables de entorno (nunca credenciales embebidas en el codigo)."""

import os
from dotenv import load_dotenv

load_dotenv()

import sys
from pathlib import Path

# apps/services contiene el paquete compartido `common`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "library"),
    "user": os.getenv("DB_USER", "auth_service_user"),
    "password": os.getenv("DB_PASSWORD", ""),
}

PORT = int(os.getenv("PORT", "5000"))

# SMTP local (Postfix en la misma instancia). Nunca un proveedor externo.
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
LOCAL_MAILBOX_USER = os.getenv("LOCAL_MAILBOX_USER", "auth-test")
MAIL_FROM = os.getenv("MAIL_FROM", "auth-service@localhost")

SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "30"))
CODE_TTL_MINUTES = int(os.getenv("CODE_TTL_MINUTES", "5"))
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TTL_DAYS", "7"))
