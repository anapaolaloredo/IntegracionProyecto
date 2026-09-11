"""WS-Security minimo (UsernameToken) para proteger operaciones sensibles.

Decision de ingenieria (Tarea 1, trabajo en casa):
  Necesidad: ObtenerEstadisticasPorModelo agrega datos de negocio del
    catalogo completo (no es informacion "publica" por operacion) y debe
    quedar restringida a un cliente autenticado.
  Decision: WS-Security UsernameToken con PasswordText, verificado contra
    un hash (werkzeug pbkdf2) guardado en variables de entorno.
  Justificacion: la alternativa "estandar" de WS-Security, PasswordDigest,
    exige que el servidor pueda recalcular
    Base64(SHA1(nonce + created + password)), lo que en la practica obliga
    a guardar la contraseña en texto plano (o reversible) del lado del
    servidor. Eso contradice la instruccion explicita de no guardar
    contraseñas en texto plano. Se prefiere PasswordText + hash irreversible
    en el servidor, aceptando la limitacion de abajo.
  Ventajas: no hay contraseña en texto plano en el servidor; el mecanismo
    vive en el Header SOAP (no en la logica de negocio del Body), por lo
    que se puede aplicar a nuevas operaciones sin tocarlas.
  Limitaciones: PasswordText viaja en texto plano en el request; en este
    ejercicio academico el transporte es HTTP simple. En un despliegue
    real este mecanismo debe combinarse obligatoriamente con HTTPS/TLS
    para proteger la contraseña en transito.
"""

from werkzeug.security import check_password_hash

from soap.envelope import WSSE_NS, qname
from soap.faults import AutenticacionFault
from config.settings import SOAP_STATS_USERNAME, SOAP_STATS_PASSWORD_HASH


def verify_username_token(header_element):
    """header_element es el <soap:Header> ya parseado (o None). Lanza
    AutenticacionFault si el UsernameToken no esta presente o es invalido."""
    if header_element is None:
        raise AutenticacionFault("Esta operacion requiere WS-Security UsernameToken en soap:Header.")

    security = header_element.find(qname(WSSE_NS, "Security"))
    if security is None:
        raise AutenticacionFault("Falta el elemento wsse:Security en el Header.")

    token = security.find(qname(WSSE_NS, "UsernameToken"))
    if token is None:
        raise AutenticacionFault("Falta wsse:UsernameToken.")

    username_el = token.find(qname(WSSE_NS, "Username"))
    password_el = token.find(qname(WSSE_NS, "Password"))
    if username_el is None or password_el is None or not username_el.text or not password_el.text:
        raise AutenticacionFault("UsernameToken incompleto.")

    username = username_el.text.strip()
    password = password_el.text.strip()

    if not SOAP_STATS_PASSWORD_HASH:
        # Servicio mal configurado (falta variable de entorno): se trata
        # como fallo de autenticacion, sin filtrar el motivo exacto al cliente.
        raise AutenticacionFault()

    credenciales_validas = (
        username == SOAP_STATS_USERNAME
        and check_password_hash(SOAP_STATS_PASSWORD_HASH, password)
    )
    if not credenciales_validas:
        raise AutenticacionFault()
