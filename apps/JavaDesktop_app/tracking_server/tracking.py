"""Logica pura del simulador de rastreo (sin Flask ni red), para poder probarla.

El codigo de rastreo se DERIVA del pedido real: LIB-MTY-<anio>-<id_pedido a 6 digitos>.
No se guarda en ninguna base: el servidor lo valida contra GET /api/pedidos/<id>.
"""
import json
import math
import re
import time
from pathlib import Path

REGEX_CODIGO = re.compile(r"^LIB-MTY-(\d{4})-(\d{6})$")
ESTADOS = ["Pedido confirmado", "Preparando pedido", "Pedido enviado", "En ruta de entrega", "Entregado"]

# Fraccion del tiempo total que dura cada fase. El vehiculo SOLO se mueve en "En ruta".
FASES = [("Pedido confirmado", 0.08), ("Preparando pedido", 0.12), ("Pedido enviado", 0.05), ("En ruta de entrega", 0.75)]


def generar_codigo(id_pedido, anio):
    return f"LIB-MTY-{int(anio):04d}-{int(id_pedido):06d}"


def parsear_codigo(codigo):
    """Devuelve (anio, id_pedido) o None si el formato es invalido."""
    m = REGEX_CODIGO.match((codigo or "").strip().upper())
    if not m:
        return None
    id_pedido = int(m.group(2))
    return (int(m.group(1)), id_pedido) if id_pedido > 0 else None


def anio_de_fecha(fecha):
    """Extrae el anio de una fecha en cualquier formato textual (ISO o RFC 822)."""
    m = re.search(r"\b(20\d{2})\b", str(fecha or ""))
    return int(m.group(1)) if m else None


def cargar_rutas(ruta_archivo):
    datos = json.loads(Path(ruta_archivo).read_text(encoding="utf-8"))
    return datos["rutas"]


def elegir_ruta(rutas, id_pedido):
    """Cada pedido recibe siempre la misma ruta, pero pedidos distintos pueden tener rutas distintas."""
    return rutas[id_pedido % len(rutas)]


def _haversine(a, b):
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def distancias_acumuladas(puntos):
    acum = [0.0]
    for i in range(1, len(puntos)):
        acum.append(acum[-1] + _haversine(puntos[i - 1], puntos[i]))
    return acum


def posicion_en_ruta(puntos, acum, fraccion):
    """Punto interpolado a `fraccion` (0..1) de la distancia total; devuelve (lat, lng, indice_tramo)."""
    fraccion = min(max(fraccion, 0.0), 1.0)
    if fraccion >= 1.0 or acum[-1] == 0:
        return puntos[-1][0], puntos[-1][1], len(puntos) - 1
    objetivo = fraccion * acum[-1]
    i = 1
    while acum[i] < objetivo:
        i += 1
    tramo = acum[i] - acum[i - 1]
    t = 0 if tramo == 0 else (objetivo - acum[i - 1]) / tramo
    lat = puntos[i - 1][0] + (puntos[i][0] - puntos[i - 1][0]) * t
    lng = puntos[i - 1][1] + (puntos[i][1] - puntos[i - 1][1]) * t
    return lat, lng, i - 1


def estado_y_avance(transcurrido, duracion):
    """(estado, fraccion_de_ruta_recorrida). Entregado solo cuando termino el tramo en ruta."""
    avance = transcurrido / duracion if duracion > 0 else 1.0
    if avance >= 1.0:
        return "Entregado", 1.0
    acumulado = 0.0
    for nombre, peso in FASES:
        if avance < acumulado + peso:
            if nombre == "En ruta de entrega":
                return nombre, (avance - acumulado) / peso
            return nombre, 0.0
        acumulado += peso
    return "Entregado", 1.0


class Simulador:
    """Un recorrido por pedido. El inicio se fija la primera vez que se consulta y se conserva
    mientras el servidor siga vivo, asi que reconsultar el codigo continua el mismo recorrido."""

    def __init__(self, rutas, duracion_s=120.0, reloj=time.monotonic):
        self.rutas, self.duracion, self.reloj = rutas, duracion_s, reloj
        self._inicios = {}
        self._acum = {}

    def iniciar(self, id_pedido):
        self._inicios.setdefault(id_pedido, self.reloj())
        ruta = elegir_ruta(self.rutas, id_pedido)
        self._acum.setdefault(id_pedido, distancias_acumuladas(ruta["puntos"]))
        return ruta

    def instantanea(self, id_pedido):
        ruta = self.iniciar(id_pedido)
        estado, fraccion = estado_y_avance(self.reloj() - self._inicios[id_pedido], self.duracion)
        lat, lng, idx = posicion_en_ruta(ruta["puntos"], self._acum[id_pedido], fraccion)
        return {"tipo": "posicion", "estado": estado, "lat": round(lat, 6), "lng": round(lng, 6),
                "indice": idx, "progreso": round(fraccion, 4), "entregado": estado == "Entregado"}
