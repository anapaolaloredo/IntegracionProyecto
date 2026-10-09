"""Cliente REST generico (JSON + Bearer) y un wrapper delgado por microservicio.
Reglas comunes: sin token no se hace la peticion; 401 con token -> SesionExpirada;
cualquier otro error conserva el mensaje del servidor (403, 409, 503...)."""

from core.http import ServiceError, SesionExpirada, mensaje_para_status


class RestApi:
    def __init__(self, http, obtener_token):
        self.http = http
        self.obtener_token = obtener_token  # se consulta en cada llamada: el token cambia

    def llamar(self, metodo, ruta, *, body=None, params=None, publico=False, ok=(200, 201), mensajes=None):
        token = None if publico else self.obtener_token()
        if not publico and not token:
            raise SesionExpirada("No hay una sesión iniciada. Inicia sesión para usar esta función.",
                                 kind="http", status=401)
        headers = {"Authorization": f"Bearer {token}"} if token else None
        resp = self.http.request(metodo, ruta, params=params, json_body=body, headers=headers)
        if resp.status_code in ok:
            try:
                return resp.json()
            except ValueError:
                return {}
        mensaje = (mensajes or {}).get(resp.status_code) or mensaje_para_status(resp)
        if resp.status_code == 401 and token:
            raise SesionExpirada(mensaje, kind="http", status=401)
        raise ServiceError(mensaje, status=resp.status_code)


class UsersApi(RestApi):
    def roles(self):
        return self.llamar("GET", "/api/roles", publico=True)

    def listar(self):
        return self.llamar("GET", "/api/users")

    def obtener(self, id_usuario):
        return self.llamar("GET", f"/api/users/{id_usuario}")

    def crear(self, correo, nombre, apellido_paterno, apellido_materno, password, rol="cliente"):
        return self.llamar("POST", "/api/users", body={
            "correo": correo, "nombre": nombre, "apellido_paterno": apellido_paterno,
            "apellido_materno": apellido_materno, "password": password, "rol": rol})

    def actualizar(self, id_usuario, **campos):
        return self.llamar("PATCH", f"/api/users/{id_usuario}", body=campos)

    def cambiar_password(self, id_usuario, nueva, actual=None):
        body = {"password_nueva": nueva}
        if actual is not None:
            body["password_actual"] = actual
        return self.llamar("PATCH", f"/api/users/{id_usuario}/password", body=body)

    def cambiar_rol(self, id_usuario, rol):
        return self.llamar("PATCH", f"/api/users/{id_usuario}/rol", body={"rol": rol})

    def eliminar(self, id_usuario):
        return self.llamar("DELETE", f"/api/users/{id_usuario}")


class AuthorsApi(RestApi):
    def listar(self):
        return self.llamar("GET", "/api/authors", publico=True)

    def obtener(self, id_autor):
        return self.llamar("GET", f"/api/authors/{id_autor}", publico=True)

    def crear(self, nombre):
        return self.llamar("POST", "/api/authors", body={"nombre_autor": nombre})

    def renombrar(self, id_autor, nombre):
        return self.llamar("PATCH", f"/api/authors/{id_autor}", body={"nombre_autor": nombre})

    def eliminar(self, id_autor):
        return self.llamar("DELETE", f"/api/authors/{id_autor}")

    def vincular(self, id_autor, id_libro):
        return self.llamar("POST", f"/api/authors/{id_autor}/books", body={"id_libro": id_libro})

    def desvincular(self, id_autor, id_libro):
        return self.llamar("DELETE", f"/api/authors/{id_autor}/books/{id_libro}")


class PedidosApi(RestApi):
    def crear(self, lineas):
        return self.llamar("POST", "/api/pedidos", body={"lineas": lineas})

    def listar(self):
        return self.llamar("GET", "/api/pedidos")

    def obtener(self, id_pedido):
        return self.llamar("GET", f"/api/pedidos/{id_pedido}")

    def cambiar_estado(self, id_pedido, estado):
        return self.llamar("PATCH", f"/api/pedidos/{id_pedido}/estado", body={"estado": estado})

    def eliminar(self, id_pedido):
        return self.llamar("DELETE", f"/api/pedidos/{id_pedido}")


class PagosApi(RestApi):
    def registrar(self, id_pedido, metodo, monto=None):
        body = {"id_pedido": id_pedido, "metodo": metodo}
        if monto is not None:
            body["monto"] = monto
        return self.llamar("POST", "/api/pagos", body=body)

    def listar(self):
        return self.llamar("GET", "/api/pagos")

    def obtener(self, id_pago):
        return self.llamar("GET", f"/api/pagos/{id_pago}")

    def reembolsar(self, id_pago):
        return self.llamar("DELETE", f"/api/pagos/{id_pago}")
