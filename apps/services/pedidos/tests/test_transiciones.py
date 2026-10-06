import pytest

import transiciones
from common.web import Conflicto, Prohibido


def test_dueno_cancela_pendiente():
    transiciones.validar("pendiente", "cancelado", es_admin=False, es_dueno=True)


def test_admin_cancela_pendiente_ajeno():
    transiciones.validar("pendiente", "cancelado", es_admin=True, es_dueno=False)


def test_solo_admin_marca_enviado():
    transiciones.validar("pagado", "enviado", es_admin=True, es_dueno=False)
    with pytest.raises(Prohibido):
        transiciones.validar("pagado", "enviado", es_admin=False, es_dueno=True)


def test_pedido_ajeno_prohibido():
    with pytest.raises(Prohibido):
        transiciones.validar("pendiente", "cancelado", es_admin=False, es_dueno=False)


@pytest.mark.parametrize("actual,nuevo", [
    ("pendiente", "pagado"), ("pendiente", "enviado"), ("pagado", "cancelado"),
    ("enviado", "cancelado"), ("cancelado", "pendiente"), ("pagado", "pendiente"),
    ("pendiente", "pendiente"), ("pendiente", "inventado"),
])
def test_transiciones_no_permitidas(actual, nuevo):
    with pytest.raises(Conflicto):
        transiciones.validar(actual, nuevo, es_admin=True, es_dueno=True)
