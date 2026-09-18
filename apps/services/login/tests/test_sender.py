"""Prueba de mail/sender.py. No abre una conexion SMTP real: reemplaza
smtplib.SMTP por un doble de prueba para verificar que el mensaje se arma
y se envia correctamente, sin depender de que Postfix este activo en esta
maquina. La entrega real se valida por separado en README_POSTFIX.md y en
el script end-to-end de la Fase 4.

Uso:
    cd apps/services/login && python tests/test_sender.py
"""
from unittest.mock import patch, MagicMock

from mail.sender import enviar_codigo


def main():
    with patch("mail.sender.smtplib.SMTP") as smtp_mock:
        instancia = MagicMock()
        smtp_mock.return_value.__enter__.return_value = instancia

        enviar_codigo("destinatario@correo.test", "123456")

        assert smtp_mock.called
        instancia.send_message.assert_called_once()
        mensaje_enviado = instancia.send_message.call_args[0][0]
        assert "123456" in mensaje_enviado.get_content()
        assert "destinatario@correo.test" in mensaje_enviado.get_content()
        print("enviar_codigo OK (SMTP simulado)")

    print("\nTODAS LAS PRUEBAS DE sender.py PASARON")


if __name__ == "__main__":
    main()
