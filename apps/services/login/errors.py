"""Excepciones de dominio. Cada una lleva su status HTTP; app.py las
traduce a una respuesta XML/JSON con render.formatters.responder."""


class ErrorDominio(Exception):
    status = 400


class CamposFaltantes(ErrorDominio):
    status = 400


class EmailInvalido(ErrorDominio):
    status = 400


class PasswordDebil(ErrorDominio):
    status = 400


class EmailDuplicado(ErrorDominio):
    status = 409


class CredencialesInvalidas(ErrorDominio):
    status = 401


class CodigoInvalido(ErrorDominio):
    status = 401


class SesionInvalida(ErrorDominio):
    status = 401
