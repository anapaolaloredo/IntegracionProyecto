import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-de-32-bytes-o-mas-0123456789")


@pytest.fixture(autouse=True)
def redis_falso():
    from common import testing
    servidor = testing.instalar_redis_falso()
    yield servidor
    testing.quitar_redis_falso()
