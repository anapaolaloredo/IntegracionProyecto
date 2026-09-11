"""Configuracion del modulo SOAP, leida exclusivamente de variables de
entorno (nunca credenciales embebidas en el codigo)."""

import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "library"),
    # Rol de minimo privilegio creado en sql/soap_module.sql, distinto del
    # dueno de la base de datos.
    "user": os.getenv("DB_USER", "soap_service_user"),
    "password": os.getenv("DB_PASSWORD", ""),
}

PORT = int(os.getenv("PORT", "5002"))

# URL publica del propio servicio, usada solo para mostrarla en el WSDL
# servido dinamicamente (ver app.py) cuando corre detras de la instancia
# en la nube (distinta de localhost).
SOAP_PUBLIC_URL = os.getenv("SOAP_PUBLIC_URL", f"http://localhost:{PORT}/soap")

# ---- WS-Security (UsernameToken) para ObtenerEstadisticasPorModelo ----
# La contrasena NUNCA se guarda en texto plano: SOAP_STATS_PASSWORD_HASH es
# un hash generado con werkzeug.security.generate_password_hash (ver
# tests/generar_hash_wsse.py). El cliente sigue enviando la contrasena en
# texto plano dentro del UsernameToken (PasswordText); ver soap/security.py
# y el README para la justificacion de esta decision.
SOAP_STATS_USERNAME = os.getenv("SOAP_STATS_USERNAME", "stats-client")
SOAP_STATS_PASSWORD_HASH = os.getenv("SOAP_STATS_PASSWORD_HASH", "")
