"""Cliente del microservicio de login. Siempre pide ?format=json.

Flujo de autenticacion (2FA, como ya existe en el servicio):
  POST /register -> POST /login (envia codigo al buzon de la instancia)
  -> POST /login/verify (codigo) -> session_token
Sesion: GET /session, POST /session/extend, POST /logout."""

from core.http import ServiceError, SesionExpirada, mensaje_para_status


class AuthApi:
    def __init__(self, http):
        self.http = http

    def _llamar(self, metodo, ruta, *, token=None, body=None, ok=(200,), mensajes=None):
        headers = {"Authorization": f"Bearer {token}"} if token else None
        resp = self.http.request(metodo, ruta, params={"format": "json"}, json_body=body, headers=headers)
        if resp.status_code in ok:
            try:
                return resp.json()
            except ValueError:
                raise ServiceError(
                    f"El servicio en {self.http.base_url} respondió algo que no es JSON. "
                    "¿La URL apunta al microservicio de login?", kind="respuesta", status=resp.status_code)
        mensaje = (mensajes or {}).get(resp.status_code) or mensaje_para_status(resp)
        clase = SesionExpirada if resp.status_code == 401 and token else ServiceError
        raise clase(mensaje, status=resp.status_code)

    def registrar(self, nombre, apellido_paterno, apellido_materno, email, password):
        datos = self._llamar("POST", "/register", ok=(201,), body={
            "nombre": nombre, "apellido_paterno": apellido_paterno,
            "apellido_materno": apellido_materno, "email": email, "password": password,
        }, mensajes={409: "Ese correo ya está registrado. Inicia sesión o usa otro correo."})
        return datos["id_usuario"]

    def iniciar_login(self, email, password):
        self._llamar("POST", "/login", body={"email": email, "password": password},
                     mensajes={401: "Correo o contraseña incorrectos."})

    def verificar_codigo(self, email, codigo):
        datos = self._llamar("POST", "/login/verify", body={"email": email, "codigo": codigo},
                             mensajes={401: "El código es incorrecto o ya expiró (dura 5 minutos). "
                                            "Revísalo o solicita uno nuevo."})
        return datos["session_token"]

    def consultar_sesion(self, token):
        return self._llamar("GET", "/session", token=token)

    def extender_sesion(self, token):
        return self._llamar("POST", "/session/extend", token=token,
                            mensajes={401: "Tu sesión expiró o ya no es válida. Inicia sesión de nuevo."})

    def cerrar_sesion(self, token):
        return self._llamar("POST", "/logout", token=token,
                            mensajes={401: "La sesión ya había expirado en el servidor."})
