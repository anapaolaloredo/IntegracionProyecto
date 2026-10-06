"""Reglas puras de cambio de estado de un pedido. El paso pendiente -> pagado
no existe aqui: lo hace el servicio de pagos al registrar el pago."""

from common.web import Conflicto, Prohibido

PERMITIDAS = {("pendiente", "cancelado"), ("pagado", "enviado")}


def validar(actual, nuevo, es_admin, es_dueno):
    if not (es_admin or es_dueno):
        raise Prohibido("El pedido no te pertenece.")
    if (actual, nuevo) not in PERMITIDAS:
        raise Conflicto(f"Transicion no permitida: {actual} -> {nuevo}. "
                        "(El pago de un pedido lo registra el servicio de pagos.)")
    if nuevo == "enviado" and not es_admin:
        raise Prohibido("Solo un administrador puede marcar un pedido como enviado.")
