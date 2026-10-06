"""Contadores en memoria (por proceso) y render en formato Prometheus.
Sin dependencias externas. Nunca recibe secretos: solo nombres y conteos."""

import threading

_lock = threading.Lock()
_contadores = {}      # (nombre, etiquetas ordenadas) -> valor
_observaciones = {}   # nombre -> [suma, cuenta]


def _limpio(valor):
    return str(valor).replace('"', "").replace("\n", " ").replace("\\", "")


def inc(nombre, valor=1, **etiquetas):
    clave = (nombre, tuple(sorted((k, _limpio(v)) for k, v in etiquetas.items())))
    with _lock:
        _contadores[clave] = _contadores.get(clave, 0) + valor


def observar(nombre, segundos):
    with _lock:
        suma_cuenta = _observaciones.setdefault(nombre, [0.0, 0])
        suma_cuenta[0] += segundos
        suma_cuenta[1] += 1


def reiniciar():
    with _lock:
        _contadores.clear()
        _observaciones.clear()


def _etiquetas(servicio, extra=()):
    pares = sorted([("servicio", _limpio(servicio)), *extra])
    return ",".join(f'{k}="{v}"' for k, v in pares)


def render(servicio):
    lineas = []
    with _lock:
        for (nombre, extra), valor in sorted(_contadores.items()):
            lineas.append(f"{nombre}{{{_etiquetas(servicio, extra)}}} {valor}")
        for nombre, (suma, cuenta) in sorted(_observaciones.items()):
            lineas.append(f"{nombre}_sum{{{_etiquetas(servicio)}}} {suma}")
            lineas.append(f"{nombre}_count{{{_etiquetas(servicio)}}} {cuenta}")
    return "\n".join(lineas) + "\n"
