"""Prueba manual de service.py de punta a punta, contra la BD real y con
mail.sender.enviar_codigo mockeado (no depende de Postfix). Requiere la
migracion de Task 1 ya aplicada.

Uso:
    cd apps/services/login && python tests/test_service_manual.py
"""
from unittest.mock import patch

import service
from errors import CredencialesInvalidas, CodigoInvalido, SesionInvalida
from db.connection import get_connection
from auth.security import generar_codigo

CORREO_PRUEBA = "service.prueba@correo.test"


def limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cuentas WHERE correo = %s", (CORREO_PRUEBA,))
        conn.commit()


def main():
    limpiar()
    codigo_capturado = {}

    def enviar_codigo_falso(correo, codigo):
        codigo_capturado["valor"] = codigo

    with patch("service.enviar_codigo", side_effect=enviar_codigo_falso):
        id_usuario = service.registrar("Ana", "Loredo", "Moreno", CORREO_PRUEBA, "password123")
        assert isinstance(id_usuario, int)
        print("registrar OK")

        service.iniciar_login(CORREO_PRUEBA, "password123")
        assert "valor" in codigo_capturado
        print(f"iniciar_login OK -> codigo capturado {codigo_capturado['valor']}")

        try:
            service.iniciar_login(CORREO_PRUEBA, "contrasena-incorrecta")
            raise AssertionError("Debio lanzar CredencialesInvalidas")
        except CredencialesInvalidas:
            print("iniciar_login rechaza password incorrecta OK")

        try:
            service.verificar_login(CORREO_PRUEBA, "000000")
            raise AssertionError("Debio lanzar CodigoInvalido")
        except CodigoInvalido:
            print("verificar_login rechaza codigo incorrecto OK")

        token = service.verificar_login(CORREO_PRUEBA, codigo_capturado["valor"])
        assert isinstance(token, str) and len(token) == 64
        print("verificar_login OK -> token de sesion creado")

        estado = service.consultar_sesion(token)
        assert estado["autenticado"] is True
        assert estado["email"] == CORREO_PRUEBA
        print("consultar_sesion(token valido) OK")

        service.cerrar_sesion(token)
        estado_tras_logout = service.consultar_sesion(token)
        assert estado_tras_logout["autenticado"] is False
        print("cerrar_sesion OK")

        try:
            service.cerrar_sesion(token)
            raise AssertionError("Debio lanzar SesionInvalida")
        except SesionInvalida:
            print("cerrar_sesion sobre token ya cerrado OK")

    assert service.verificar_salud() is True
    print("verificar_salud OK")

    limpiar()
    print("\nTODAS LAS PRUEBAS DE service.py PASARON")


if __name__ == "__main__":
    main()
