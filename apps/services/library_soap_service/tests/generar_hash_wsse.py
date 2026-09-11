"""Utilidad de un solo uso: genera el hash que va en SOAP_STATS_PASSWORD_HASH
(.env) a partir de una contrasena en texto plano, para no tener que
escribirla nunca en el archivo de configuracion.

Uso:
    python tests/generar_hash_wsse.py "mi-contrasena"
"""
import sys
from werkzeug.security import generate_password_hash

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python tests/generar_hash_wsse.py <contrasena>")
        raise SystemExit(1)
    print(generate_password_hash(sys.argv[1]))
