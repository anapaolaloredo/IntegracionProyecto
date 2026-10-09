"""Configuracion del servidor: URLs de los microservicios y tiempos.

Se guarda como JSON en la carpeta de configuracion del usuario (fuera del
codigo fuente) para que persista entre ejecuciones:
  - Windows: %APPDATA%/LibreriaEscritorio/config.json
  - macOS:   ~/Library/Application Support/LibreriaEscritorio/config.json
La variable LIBRERIA_CONFIG_DIR permite usar otra carpeta (pruebas)."""

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from dataclasses import replace
from urllib.parse import urlparse, urlsplit, urlunsplit

# (clave, nombre legible, puerto por defecto) de los seis microservicios
SERVICIOS = (
    ("login", "Login", 5000),
    ("books", "Libros", 5001),
    ("users", "Usuarios", 5002),
    ("authors", "Autores", 5003),
    ("pedidos", "Pedidos", 5004),
    ("pagos", "Pagos", 5005),
)

DEFAULTS = {
    **{f"{clave}_url": f"http://localhost:{puerto}" for clave, _, puerto in SERVICIOS},
    "protocolo": "http",
    "timeout": 5,
    "health_interval": 30,
}


def config_dir():
    override = os.getenv("LIBRERIA_CONFIG_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "LibreriaEscritorio"


def normalizar_url(url):
    """Quita espacios y la diagonal final: 'http://h:5001/' -> 'http://h:5001'."""
    return (url or "").strip().rstrip("/")


def cambiar_esquema(url, esquema):
    """'http://h:5002' + 'https' -> 'https://h:5002' (host, puerto y ruta intactos)."""
    partes = urlsplit(url)
    return urlunsplit((esquema, partes.netloc, partes.path, partes.query, partes.fragment))


def validar_url(url):
    """Regresa un mensaje de error o None si la URL base es usable."""
    partes = urlparse(url)
    if partes.scheme not in ("http", "https"):
        return "debe iniciar con http:// o https://"
    if not partes.hostname:
        return "le falta el host (p. ej. http://34.10.20.30:5001)"
    try:
        partes.port
    except ValueError:
        return "el puerto no es un numero valido"
    return None


@dataclass
class AppConfig:
    login_url: str = DEFAULTS["login_url"]
    books_url: str = DEFAULTS["books_url"]
    users_url: str = DEFAULTS["users_url"]
    authors_url: str = DEFAULTS["authors_url"]
    pedidos_url: str = DEFAULTS["pedidos_url"]
    pagos_url: str = DEFAULTS["pagos_url"]
    protocolo: str = DEFAULTS["protocolo"]
    timeout: int = DEFAULTS["timeout"]
    health_interval: int = DEFAULTS["health_interval"]

    @classmethod
    def defaults(cls):
        return cls()

    @classmethod
    def load(cls):
        """Lee el archivo; si no existe o esta corrupto usa los predeterminados."""
        datos = dict(DEFAULTS)
        try:
            with open(config_dir() / "config.json", encoding="utf-8") as f:
                guardado = json.load(f)
            if isinstance(guardado, dict):
                datos.update({k: v for k, v in guardado.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
        config = cls(**datos)
        if config.validar():
            return cls.defaults()
        return config

    def url(self, clave):
        return getattr(self, f"{clave}_url")

    def con_protocolo(self, protocolo):
        """Copia con el esquema de las seis URLs reescrito (host y puerto intactos)."""
        nuevas = {f"{clave}_url": cambiar_esquema(self.url(clave), protocolo) for clave, _, _ in SERVICIOS}
        return replace(self, protocolo=protocolo, **nuevas)

    def validar(self):
        """Lista de errores legibles; vacia si la configuracion es valida."""
        errores = []
        for clave, nombre, _ in SERVICIOS:
            error = validar_url(self.url(clave))
            if error:
                errores.append(f"URL de {nombre}: {error}.")
        if self.protocolo not in ("http", "https"):
            errores.append("El protocolo debe ser http o https.")
        if not isinstance(self.timeout, int) or not 1 <= self.timeout <= 60:
            errores.append("El tiempo de espera debe estar entre 1 y 60 segundos.")
        if not isinstance(self.health_interval, int) or not 5 <= self.health_interval <= 3600:
            errores.append("El intervalo de comprobacion debe estar entre 5 y 3600 segundos.")
        return errores

    def save(self):
        carpeta = config_dir()
        carpeta.mkdir(parents=True, exist_ok=True)
        with open(carpeta / "config.json", "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
