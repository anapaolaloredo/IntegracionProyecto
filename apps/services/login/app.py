"""Rutas HTTP del microservicio de login. Traduce excepciones de dominio
a respuestas XML/JSON con el status correcto; no contiene reglas de
negocio (eso vive en service.py)."""

from flask import Flask, request
from flasgger import Swagger

from config.settings import PORT
import service
from errors import ErrorDominio
from render.formatters import responder

app = Flask(__name__)
app.config["SWAGGER"] = {"title": "Microservicio de Autenticacion", "uiversion": 3}
Swagger(app)


def _token_de_header():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None


@app.errorhandler(ErrorDominio)
def manejar_error_dominio(err):
    return responder("error", {"mensaje": str(err)}, status=err.status)


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
    Verifica el codigo 2FA y crea la sesion (valida 30 minutos).
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
        description: "Sesion creada. XML: <sesion><session_token>...</session_token></sesion>. JSON: {\\"session_token\\": \\"...\\"}"
      401:
        description: Codigo invalido o expirado
    """
    datos = request.get_json(force=True, silent=True) or {}
    token = service.verificar_login(datos.get("email"), datos.get("codigo"))
    return responder("sesion", {"session_token": token})


@app.route("/logout", methods=["POST"])
def logout():
    """
    Cierra la sesion asociada al token del header Authorization.
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
        description: "Siempre 200. XML: <sesion><autenticado>true</autenticado>...</sesion>. JSON: {\\"autenticado\\": false}"
    """
    return responder("sesion", service.consultar_sesion(_token_de_header()))


@app.route("/session/extend", methods=["POST"])
def session_extend():
    """
    Extiende la sesion del token dado otros SESSION_TTL_MINUTES (30) a partir de ahora.
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
        description: "Sesion extendida. JSON: {\\"expira_en\\": \\"...\\", \\"segundos_restantes\\": 1800}"
      401:
        description: Token invalido, expirado o ausente
    """
    return responder("sesion", service.extender_sesion(_token_de_header()))


@app.route("/health", methods=["GET"])
def health():
    """
    Verifica el estado del microservicio y de PostgreSQL.
    ---
    parameters:
      - in: query
        name: format
        type: string
        enum: [xml, json]
        default: xml
    responses:
      200:
        description: "Servicio saludable. JSON: {\\"status\\": \\"ok\\", \\"db\\": \\"ok\\"}"
      503:
        description: PostgreSQL no responde
    """
    if service.verificar_salud():
        return responder("salud", {"status": "ok", "db": "ok"})
    return responder("salud", {"status": "error", "db": "error"}, status=503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
