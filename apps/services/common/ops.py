"""Endpoints operativos publicos: GET /metrics (Prometheus) y GET /health."""

from flask import Response, jsonify

from common import metrics, redis_store


def registrar_operacion(app, servicio, db_check=None, health=True):
    @app.route("/metrics", methods=["GET"])
    def _metrics():
        return Response(metrics.render(servicio), mimetype="text/plain")

    if not health:
        return

    @app.route("/health", methods=["GET"])
    def _health():
        if db_check is None:
            db = "no_aplica"
        else:
            try:
                db = "ok" if db_check() else "error"
            except Exception:
                db = "error"
        cuerpo = {"servicio": servicio, "status": "error" if db == "error" else "ok",
                  "db": db, "redis": redis_store.estado()}
        return jsonify(cuerpo), (503 if db == "error" else 200)
