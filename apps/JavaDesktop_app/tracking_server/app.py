"""Servidor de rastreo GPS simulado: Flask + Flask-Sock.

Protocolo (WebSocket en /ws/rastreo):
  1. El cliente envia UN primer mensaje JSON: {"token": "<JWT>", "codigo": "LIB-MTY-2026-000125"}
     (el token va en el mensaje y no en la URL para que no quede en logs de acceso).
  2. El servidor NO valida el JWT por su cuenta: reenvia el token a GET {PEDIDOS_URL}/api/pedidos/<id>.
     Asi se reutiliza la firma, la expiracion, la revocacion en Redis y la regla "el pedido es tuyo"
     que ya implementa el microservicio pedidos (401 / 403 / 404 se traducen a mensajes de error).
  3. Si el pedido es valido y esta pagado, transmite {"tipo":"inicio",...} y luego una
     {"tipo":"posicion",...} por segundo hasta "Entregado".
"""
import json
import os
import time
from pathlib import Path

import requests
from flask import Flask, jsonify
from flask_sock import Sock

import tracking

PEDIDOS_URL = os.getenv("PEDIDOS_URL", "http://127.0.0.1:5004").rstrip("/")
DURACION_S = float(os.getenv("SIM_DURACION_S", "120"))
INTERVALO_S = float(os.getenv("SIM_INTERVALO_S", "1"))
RUTAS = tracking.cargar_rutas(Path(__file__).parent / "data" / "rutas_monterrey.json")
ESTADOS_PAGADOS = {"pagado", "enviado"}

app = Flask(__name__)
sock = Sock(app)
simulador = tracking.Simulador(RUTAS, DURACION_S)


def validar_acceso(token, codigo):
    """Devuelve (id_pedido, None) si el usuario puede rastrear ese codigo, o (None, mensaje)."""
    if not token or not isinstance(token, str):
        return None, "Falta el token JWT."
    parsed = tracking.parsear_codigo(codigo)
    if not parsed:
        return None, "Codigo de rastreo invalido. Formato: LIB-MTY-AAAA-NNNNNN."
    anio, id_pedido = parsed
    try:
        r = requests.get(f"{PEDIDOS_URL}/api/pedidos/{id_pedido}",
                         headers={"Authorization": f"Bearer {token}"}, timeout=8)
    except requests.RequestException:
        return None, "No se pudo consultar el servicio de pedidos."
    if r.status_code == 401:
        return None, "Sesion invalida o expirada."
    if r.status_code == 403:
        return None, "Ese pedido no te pertenece."
    if r.status_code == 404:
        return None, "El pedido no existe."
    if r.status_code != 200:
        return None, f"Pedidos respondio {r.status_code}."
    pedido = r.json()
    if tracking.anio_de_fecha(pedido.get("fecha_creacion")) not in (None, anio):
        return None, "El codigo no corresponde a ese pedido."
    if pedido.get("estado") not in ESTADOS_PAGADOS:
        return None, f"El pedido esta '{pedido.get('estado')}': solo se rastrean pedidos pagados."
    return id_pedido, None


@sock.route("/ws/rastreo")
def rastreo(ws):
    try:
        inicial = json.loads(ws.receive(timeout=15) or "{}")
    except (ValueError, TypeError):
        inicial = {}
    id_pedido, error = validar_acceso(inicial.get("token"), inicial.get("codigo"))
    if error:
        ws.send(json.dumps({"tipo": "error", "mensaje": error}))
        return
    ruta = simulador.iniciar(id_pedido)
    ws.send(json.dumps({"tipo": "inicio", "codigo": inicial["codigo"].strip().upper(), "id_pedido": id_pedido,
                        "destino": ruta["destino"], "ruta": ruta["puntos"], "estados": tracking.ESTADOS}))
    while True:
        punto = simulador.instantanea(id_pedido)
        ws.send(json.dumps(punto))
        if punto["entregado"]:
            return
        time.sleep(INTERVALO_S)


@app.route("/health")
def health():
    return jsonify({"servicio": "tracking", "estado": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5006")), threaded=True)
