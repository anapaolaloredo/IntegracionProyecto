import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")
