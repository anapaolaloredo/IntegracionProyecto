"""Envio del codigo 2FA por SMTP LOCAL (Postfix corriendo en la misma
instancia, sin relay externo). Ver README_POSTFIX.md para la
configuracion de Postfix en la instancia de GCP."""

import smtplib
from email.message import EmailMessage

from config.settings import SMTP_HOST, SMTP_PORT, LOCAL_MAILBOX_USER, MAIL_FROM


def enviar_codigo(correo_destinatario, codigo):
    mensaje = EmailMessage()
    mensaje["Subject"] = f"Codigo de verificacion para {correo_destinatario}"
    mensaje["From"] = MAIL_FROM
    mensaje["To"] = f"{LOCAL_MAILBOX_USER}@localhost"
    mensaje.set_content(
        f"Cuenta: {correo_destinatario}\n"
        f"Codigo de verificacion: {codigo}\n"
        f"Este codigo expira en unos minutos."
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.send_message(mensaje)
