"""Recuerda localmente la ultima sesion (token + correo).

Recordar el token NO significa que siga valido: al abrir la app siempre se
valida con GET /session y, si el servidor ya no lo reconoce, se descarta."""

import json

from core.config import config_dir


def _archivo():
    return config_dir() / "session.json"


def guardar(token, email):
    carpeta = config_dir()
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(_archivo(), "w", encoding="utf-8") as f:
        json.dump({"token": token, "email": email}, f)


def cargar():
    try:
        with open(_archivo(), encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict) and datos.get("token"):
            return datos
    except (OSError, ValueError):
        pass
    return None


def borrar():
    try:
        _archivo().unlink()
    except OSError:
        pass
