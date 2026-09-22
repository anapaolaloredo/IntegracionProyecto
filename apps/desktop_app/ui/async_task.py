"""Ejecuta llamadas HTTP fuera del hilo de la interfaz para que la ventana
nunca se congele, y entrega el resultado (o la excepcion) en el hilo
principal de Qt."""

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal


class _Senales(QObject):
    ok = Signal(object)
    error = Signal(object)


class _Tarea(QRunnable):
    def __init__(self, funcion, senales):
        super().__init__()
        self.funcion = funcion
        self.senales = senales

    def run(self):
        try:
            resultado = self.funcion()
        except Exception as exc:  # se reporta a la UI, nunca revienta el hilo
            self.senales.error.emit(exc)
        else:
            self.senales.ok.emit(resultado)


_vivas = set()


def ejecutar(funcion, al_terminar, al_fallar):
    """funcion() corre en un hilo del pool; al_terminar/al_fallar en el hilo de la UI.
    _Senales se crea aqui (hilo principal), por eso la conexion en cola entrega ahi."""
    senales = _Senales()
    _vivas.add(senales)

    def terminar(resultado):
        _vivas.discard(senales)
        al_terminar(resultado)

    def fallar(exc):
        _vivas.discard(senales)
        al_fallar(exc)

    senales.ok.connect(terminar, Qt.QueuedConnection)
    senales.error.connect(fallar, Qt.QueuedConnection)
    QThreadPool.globalInstance().start(_Tarea(funcion, senales))
