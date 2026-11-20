"""Prueba de estres con Locust para los microservicios soap (5001) y users (5002).

Uso rapido (GUI):  locust -f locustfile.py   ->  http://localhost:8089
Variables de entorno opcionales:
  HOST_IP      IP del servidor                 (por defecto 136.80.175.191)
  LOCUST_TOKEN JWT de admin para las rutas protegidas y las escrituras de libros.
               Sin el, solo se prueban las rutas publicas.
"""

import os
import random
import uuid
import xml.etree.ElementTree as ET

from locust import HttpUser, between, events, task

IP = os.getenv("HOST_IP", "136.80.175.191")
TOKEN = os.getenv("LOCUST_TOKEN", "")
AUTH = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

ISBNS = []  # se llena al iniciar con los ISBN reales del catalogo


@events.test_start.add_listener
def cargar_isbns(environment, **_):
    """Lee los ISBN existentes para pedir libros que si existen."""
    import requests
    try:
        r = requests.get(f"http://{IP}:5001/api/libros/catalogo", timeout=15)
        ISBNS[:] = [b.get("isbn") for b in ET.fromstring(r.content).iter("book")]
    except Exception as e:
        print(f"No se pudieron cargar ISBN del catalogo: {e}")


class SoapUser(HttpUser):
    """Libros: todos los endpoints de http://IP:5001 (respuestas XML)."""
    host = f"http://{IP}:5001"
    weight = 1
    wait_time = between(0.5, 2)

    @task(5)
    def listar_libros(self):
        self.client.get("/api/libros", name="GET /api/libros")

    @task(5)
    def catalogo(self):
        self.client.get("/api/libros/catalogo", name="GET /api/libros/catalogo")

    @task(3)
    def temas(self):
        self.client.get("/api/libros/temas", name="GET /api/libros/temas")

    @task(4)
    def buscar(self):
        params = random.choice([
            {"titulo": "a"}, {"autor": "a"}, {"genero": "a"}, {"formato": "a"},
            {"anio": 2000}, {"precio_min": 100, "precio_max": 500},
        ])
        self.client.get("/api/libros/buscar", params=params, name="GET /api/libros/buscar")

    @task(4)
    def libro_por_isbn(self):
        if ISBNS:
            self.client.get(f"/api/libros/{random.choice(ISBNS)}", name="GET /api/libros/[isbn]")

    @task(1)
    def libro_inexistente(self):
        with self.client.get("/api/libros/0000000000000", name="GET /api/libros/[isbn] (404)",
                             catch_response=True) as r:
            r.success() if r.status_code == 404 else r.failure(f"esperado 404, vino {r.status_code}")

    @task(1)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(1)
    def metrics(self):
        self.client.get("/metrics", name="GET /metrics")

    @task(1)
    def crud_libro(self):
        """POST -> PUT -> DELETE de un libro propio de la prueba (requiere LOCUST_TOKEN de admin)."""
        if not TOKEN:
            return
        isbn = uuid.uuid4().hex[:13]
        self.client.post("/api/libros", headers=AUTH, name="POST /api/libros", json={
            "isbn": isbn, "title": "Libro de prueba Locust", "price": 99.9,
            "stock": 5, "format": "Tapa blanda", "publicationYear": 2024})
        self.client.put(f"/api/libros/{isbn}", headers=AUTH, name="PUT /api/libros/[isbn]",
                        json={"price": 120, "stock": 3})
        self.client.delete(f"/api/libros/{isbn}", headers=AUTH, name="DELETE /api/libros/[isbn]")


class UsersUser(HttpUser):
    """Users: http://IP:5002 y http://IP:5002?format=json, mas sus endpoints reales."""
    host = f"http://{IP}:5002"
    weight = 1
    wait_time = between(0.5, 2)

    def _raiz(self, path, name):
        # El servicio no define "/": un 404 es la respuesta esperada y lo contamos como exito.
        with self.client.get(path, name=name, catch_response=True) as r:
            r.success() if r.status_code in (200, 404) else r.failure(f"HTTP {r.status_code}")

    @task(2)
    def raiz(self):
        self._raiz("/", "GET /")

    @task(2)
    def raiz_json(self):
        self._raiz("/?format=json", "GET /?format=json")

    @task(5)
    def roles(self):
        self.client.get("/api/roles", name="GET /api/roles")

    @task(2)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(1)
    def metrics(self):
        self.client.get("/metrics", name="GET /metrics")

    @task(3)
    def sin_token(self):
        """Ruta protegida sin token: debe responder 401."""
        with self.client.get("/api/users", name="GET /api/users (sin token, 401)",
                             catch_response=True) as r:
            r.success() if r.status_code == 401 else r.failure(f"esperado 401, vino {r.status_code}")

    @task(4)
    def listar_usuarios(self):
        if TOKEN:
            self.client.get("/api/users", headers=AUTH, name="GET /api/users")

    @task(3)
    def ver_usuario(self):
        if TOKEN:
            with self.client.get(f"/api/users/{random.randint(1, 30)}", headers=AUTH,
                                 name="GET /api/users/[id]", catch_response=True) as r:
                r.success() if r.status_code in (200, 404) else r.failure(f"HTTP {r.status_code}")
