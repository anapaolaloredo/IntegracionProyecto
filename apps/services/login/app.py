"""Rutas HTTP del microservicio de login. Traduce excepciones de dominio
a respuestas XML/JSON con el status correcto; no contiene reglas de
negocio (eso vive en service.py)."""

from flask import Flask, request
from flasgger import Swagger

from config.settings import PORT
from common import jwt_auth, redis_store
from common.ops import registrar_operacion
import service
from errors import ErrorDominio
from render.formatters import responder

app = Flask(__name__)
app.config["SWAGGER"] = {"title": "Microservicio de Autenticacion", "uiversion": 3}
Swagger(app)
jwt_auth.obtener_secret()  # falla al arrancar si no hay SECRET_KEY
registrar_operacion(app, "login", health=False)  # /metrics; /health propio (usa formato XML/JSON)


def _token_de_header():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None


@app.errorhandler(ErrorDominio)
def manejar_error_dominio(err):
    return responder("error", {"mensaje": str(err)}, status=err.status)


@app.errorhandler(redis_store.RedisNoDisponible)
def manejar_redis_no_disponible(_):
    return responder("error", {"mensaje": "Servicio de sesiones no disponible. Intenta de nuevo en unos minutos."},
                     status=503)


@app.route("/register", methods=["POST"])
def register():
    """
    Registra un nuevo usuario.
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
      - in: body
        name: body
        schema:
          type: object
          required: [nombre, apellido_paterno, apellido_materno, email, password]
          properties:
            nombre: {type: string, example: Ana}
            apellido_paterno: {type: string, example: Loredo}
            apellido_materno: {type: string, example: Moreno}
            email: {type: string, example: ana@correo.test}
            password: {type: string, example: password123}
    responses:
      201:
        description: "Usuario creado. XML: <usuario><id_usuario>7</id_usuario></usuario>. JSON: {\\"id_usuario\\": 7}"
      400:
        description: Datos invalidos o faltantes
      409:
        description: El correo ya esta registrado
    """
    datos = request.get_json(force=True, silent=True) or {}
    id_usuario = service.registrar(
        datos.get("nombre"), datos.get("apellido_paterno"),
        datos.get("apellido_materno"), datos.get("email"), datos.get("password"),
    )
    return responder("usuario", {"id_usuario": id_usuario}, status=201)


@app.route("/login", methods=["POST"])
def login():
    """
    Valida credenciales y envia el codigo 2FA al buzon local de la instancia.
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
      - in: body
        name: body
        schema:
          type: object
          required: [email, password]
          properties:
            email: {type: string}
            password: {type: string}
    responses:
      200:
        description: "Codigo enviado. XML: <login><pendiente_verificacion>true</pendiente_verificacion></login>. JSON: {\\"pendiente_verificacion\\": true}"
      401:
        description: Credenciales invalidas
    """
    datos = request.get_json(force=True, silent=True) or {}
    service.iniciar_login(datos.get("email"), datos.get("password"))
    return responder("login", {"pendiente_verificacion": True})


@app.route("/login/verify", methods=["POST"])
def login_verify():
    """
    Verifica el codigo 2FA y emite un JWT de acceso (30 minutos) y un refresh token (7 dias).
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
      - in: body
        name: body
        schema:
          type: object
          required: [email, codigo]
          properties:
            email: {type: string}
            codigo: {type: string, example: "123456"}
    responses:
      200:
        description: "Sesion creada. JSON: {\\"session_token\\": \\"<JWT 30 min>\\", \\"refresh_token\\": \\"<JWT 7 dias>\\"}"
      401:
        description: Codigo invalido o expirado
    """
    datos = request.get_json(force=True, silent=True) or {}
    tokens = service.verificar_login(datos.get("email"), datos.get("codigo"))
    return responder("sesion", tokens)


@app.route("/logout", methods=["POST"])
def logout():
    """
    Cierra la sesion: borra sesion y refresh en Redis y revoca el JWT.
    ---
    parameters:
      - in: header
        name: Authorization
        type: string
        required: true
        description: "Bearer <session_token>"
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: Sesion cerrada
      401:
        description: Token invalido, expirado o ausente
    """
    service.cerrar_sesion(_token_de_header())
    return responder("logout", {"mensaje": "Sesion cerrada."})


@app.route("/session", methods=["GET"])
def session_status():
    """
    Consulta si existe una sesion autenticada para el token dado.
    ---
    parameters:
      - in: header
        name: Authorization
        type: string
        required: false
        description: "Bearer <session_token>"
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: "200 (503 si Redis no esta disponible). XML: <sesion><autenticado>true</autenticado>...</sesion>. JSON: {\\"autenticado\\": false}"
    """
    return responder("sesion", service.consultar_sesion(_token_de_header()))


@app.route("/session/extend", methods=["POST"])
def session_extend():
    """
    Emite un session_token (JWT) nuevo de SESSION_TTL_MINUTES (30) a partir de ahora y revoca el anterior.
    ---
    parameters:
      - in: header
        name: Authorization
        type: string
        required: true
        description: "Bearer <session_token>"
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: "Sesion extendida. JSON: {\\"session_token\\": \\"...\\", \\"expira_en\\": \\"...\\", \\"segundos_restantes\\": 1800}"
      401:
        description: Token invalido, expirado o ausente
    """
    return responder("sesion", service.extender_sesion(_token_de_header()))


@app.route("/session/refresh", methods=["POST"])
def session_refresh():
    """
    Canjea un refresh token por un nuevo JWT de acceso (30 min).
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
      - in: body
        name: body
        schema:
          type: object
          required: [refresh_token]
          properties:
            refresh_token: {type: string}
    responses:
      200:
        description: "JSON: {\\"session_token\\": \\"...\\", \\"expira_en\\": \\"...\\", \\"segundos_restantes\\": 1800}"
      401:
        description: Refresh token invalido o expirado
    """
    datos = request.get_json(force=True, silent=True) or {}
    return responder("sesion", service.refrescar_sesion(datos.get("refresh_token")))


@app.route("/health", methods=["GET"])
def health():
    """
    Verifica el estado del microservicio, de PostgreSQL y de Redis.
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: "Servicio saludable. JSON: {\\"status\\": \\"ok\\", \\"db\\": \\"ok\\", \\"redis\\": \\"ok\\"}"
      503:
        description: PostgreSQL no responde
    """
    db_ok = service.verificar_salud()
    cuerpo = {"status": "ok" if db_ok else "error", "db": "ok" if db_ok else "error",
              "redis": redis_store.estado()}
    return responder("salud", cuerpo, status=200 if db_ok else 503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
