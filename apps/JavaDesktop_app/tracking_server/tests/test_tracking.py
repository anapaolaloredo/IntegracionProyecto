import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import app as servidor
import tracking

RUTAS = tracking.cargar_rutas(Path(__file__).resolve().parent.parent / "data" / "rutas_monterrey.json")


def test_codigo_ida_y_vuelta():
    assert tracking.generar_codigo(125, 2026) == "LIB-MTY-2026-000125"
    assert tracking.parsear_codigo("lib-mty-2026-000125") == (2026, 125)


@pytest.mark.parametrize("malo", ["", None, "LIB-MTY-2026-125", "XXX-MTY-2026-000125", "LIB-MTY-2026-000000"])
def test_codigo_invalido(malo):
    assert tracking.parsear_codigo(malo) is None


def test_pedidos_distintos_rutas_distintas():
    assert len({tracking.elegir_ruta(RUTAS, i)["destino"] for i in range(len(RUTAS))}) == len(RUTAS)


def test_entregado_solo_al_final_de_la_ruta():
    t = [0]
    sim = tracking.Simulador(RUTAS, 100, reloj=lambda: t[0])
    sim.iniciar(7)
    vistos = []
    for t[0] in (0, 10, 22, 30, 60, 99, 100):
        vistos.append(sim.instantanea(7))
    assert [v["estado"] for v in vistos] == ["Pedido confirmado", "Preparando pedido", "Pedido enviado",
                                            "En ruta de entrega", "En ruta de entrega", "En ruta de entrega", "Entregado"]
    # Parado antes de salir, avanza durante la ruta y termina en el ultimo punto.
    assert vistos[0]["progreso"] == vistos[2]["progreso"] == 0
    assert vistos[3]["progreso"] < vistos[4]["progreso"] < vistos[5]["progreso"] < 1
    ruta = tracking.elegir_ruta(RUTAS, 7)["puntos"]
    assert (vistos[-1]["lat"], vistos[-1]["lng"]) == tuple(round(c, 6) for c in ruta[-1])


def test_reconsultar_continua_el_mismo_recorrido():
    t = [0]
    sim = tracking.Simulador(RUTAS, 100, reloj=lambda: t[0])
    sim.iniciar(3)
    t[0] = 60
    a = sim.instantanea(3)
    sim.iniciar(3)  # segunda conexion con el mismo codigo
    assert sim.instantanea(3) == a


class _Resp:
    def __init__(self, status, cuerpo=None):
        self.status_code, self._c = status, cuerpo or {}

    def json(self):
        return self._c


def _con_pedidos(monkeypatch, resp):
    monkeypatch.setattr(servidor.requests, "get", lambda *a, **k: resp)


def test_acceso_pedido_ajeno_prohibido(monkeypatch):
    _con_pedidos(monkeypatch, _Resp(403))
    assert servidor.validar_acceso("tok", "LIB-MTY-2026-000005") == (None, "Ese pedido no te pertenece.")


def test_acceso_token_invalido(monkeypatch):
    _con_pedidos(monkeypatch, _Resp(401))
    assert servidor.validar_acceso("tok", "LIB-MTY-2026-000005")[0] is None


def test_acceso_sin_token_no_llama_a_pedidos(monkeypatch):
    monkeypatch.setattr(servidor.requests, "get", lambda *a, **k: pytest.fail("no debia llamar"))
    assert servidor.validar_acceso("", "LIB-MTY-2026-000005")[0] is None


def test_pedido_pendiente_no_se_rastrea(monkeypatch):
    _con_pedidos(monkeypatch, _Resp(200, {"estado": "pendiente", "fecha_creacion": "2026-11-05"}))
    assert servidor.validar_acceso("tok", "LIB-MTY-2026-000005")[0] is None


def test_pedido_pagado_ok_y_anio_incorrecto(monkeypatch):
    _con_pedidos(monkeypatch, _Resp(200, {"estado": "pagado", "fecha_creacion": "Thu, 05 Nov 2026 10:00:00 GMT"}))
    assert servidor.validar_acceso("tok", "LIB-MTY-2026-000005") == (5, None)
    assert servidor.validar_acceso("tok", "LIB-MTY-2025-000005")[0] is None
