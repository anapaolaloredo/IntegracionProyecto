from flask import Flask

from common import metrics, ops, testing
from common.redis_store import RedisNoDisponible
from common.web import configurar_app


def _cliente(db_check=None, health=True):
    app = Flask(__name__)
    ops.registrar_operacion(app, "demo", db_check=db_check, health=health)
    return app.test_client()


def test_metrics_publico_en_formato_prometheus():
    metrics.reiniciar()
    metrics.inc("cache_hits_total")
    resp = _cliente().get("/metrics")
    assert resp.status_code == 200 and resp.mimetype == "text/plain"
    assert 'cache_hits_total{servicio="demo"} 1' in resp.get_data(as_text=True)


def test_health_ok_con_bd_y_redis():
    resp = _cliente(db_check=lambda: True).get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"servicio": "demo", "status": "ok", "db": "ok", "redis": "ok"}


def test_health_bd_caida_da_503():
    resp = _cliente(db_check=lambda: False).get("/health")
    assert resp.status_code == 503 and resp.get_json()["status"] == "error"


def test_health_bd_que_lanza_excepcion_da_503():
    def boom():
        raise RuntimeError("sin bd")
    assert _cliente(db_check=boom).get("/health").status_code == 503


def test_health_redis_caido_no_cambia_status_pero_lo_informa(redis_falso):
    testing.redis_caido(redis_falso)
    cuerpo = _cliente(db_check=lambda: True).get("/health").get_json()
    assert cuerpo["status"] == "ok" and cuerpo["redis"] == "error"


def test_health_sin_db_check():
    assert _cliente().get("/health").get_json()["db"] == "no_aplica"


def test_health_puede_omitirse():
    assert _cliente(health=False).get("/health").status_code == 404


def test_configurar_app_traduce_redis_no_disponible_a_503():
    app = Flask(__name__)
    configurar_app(app)

    @app.route("/x")
    def x():
        raise RedisNoDisponible("caido")

    resp = app.test_client().get("/x")
    assert resp.status_code == 503 and "mensaje" in resp.get_json()
