"""Panel principal: pestanas separadas para Sesion y perfil, Catalogo,
Administracion, Estado de los servicios y Configuracion, mas el registro
HTTP. Aqui viven los temporizadores de salud y de expiracion de sesion."""

from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDockWidget, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from core.health import comprobar_libros, comprobar_login
from core.http import SesionExpirada
from ui.admin_tab import AdminTab
from ui.async_task import ejecutar
from ui.catalog_tab import CatalogTab
from ui.common import TEXTOS, RegistroHttpWidget, Semaforo, poner_mensaje, texto_error
from ui.config_panel import ConfigPanel

AVISO_SEGUNDOS = 5 * 60  # advertir cuando falten 5 minutos o menos


def formato_restante(segundos):
    m, s = divmod(max(0, int(segundos)), 60)
    return f"{m:02d}:{s:02d}"


class SessionTab(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.correo = QLabel("—")
        self.nombre = QLabel("—")
        self.id_usuario = QLabel("—")
        self.expira = QLabel("—")
        self.restante = QLabel("—")
        self.restante.setStyleSheet("font-size: 18px; font-weight: bold;")
        form = QFormLayout()
        form.addRow("Correo:", self.correo)
        form.addRow("Nombre:", self.nombre)
        form.addRow("ID de usuario:", self.id_usuario)
        form.addRow("La sesión expira a las:", self.expira)
        form.addRow("Tiempo restante:", self.restante)
        caja = QGroupBox("Sesión y perfil (GET /session)")
        caja.setLayout(form)

        btn_actualizar = QPushButton("Actualizar datos")
        self.btn_extender = QPushButton("Extender sesión (+30 min)")
        btn_salir = QPushButton("Cerrar sesión")
        btn_actualizar.clicked.connect(ventana.sincronizar_sesion)
        self.btn_extender.clicked.connect(ventana.extender_sesion)
        btn_salir.clicked.connect(ventana.cerrar_sesion)
        barra = QHBoxLayout()
        for b in (btn_actualizar, self.btn_extender, btn_salir):
            barra.addWidget(b)
        barra.addStretch()

        nota = QLabel("La sesión dura 30 minutos en el servidor. Recordar la sesión en este equipo no la mantiene "
                      "activa: al abrir la aplicación se valida contra el servidor.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: gray;")
        self.mensaje = QLabel(wordWrap=True)
        capa = QVBoxLayout(self)
        capa.addWidget(caja)
        capa.addLayout(barra)
        capa.addWidget(self.mensaje)
        capa.addWidget(nota)
        capa.addStretch()

    def mostrar_datos(self, datos):
        self.correo.setText(datos.get("email", "—"))
        self.nombre.setText(datos.get("nombre", "—"))
        self.id_usuario.setText(str(datos.get("id_usuario", "—")))


class TarjetaEstado(QGroupBox):
    def __init__(self, titulo):
        super().__init__(titulo)
        self.semaforo = Semaforo(28)
        self.estado = QLabel("Sin comprobar")
        self.estado.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.detalle = QLabel(wordWrap=True)
        self.hora = QLabel("Última comprobación: —")
        self.hora.setStyleSheet("color: gray;")
        arriba = QHBoxLayout()
        arriba.addWidget(self.semaforo)
        arriba.addWidget(self.estado, 1)
        capa = QVBoxLayout(self)
        capa.addLayout(arriba)
        capa.addWidget(self.detalle)
        capa.addWidget(self.hora)

    def mostrar(self, resultado, url):
        self.semaforo.set_estado(resultado.estado)
        self.estado.setText(TEXTOS[resultado.estado])
        self.detalle.setText(f"{resultado.detalle}\n{url}")
        self.hora.setText("Última comprobación: " + resultado.comprobado.strftime("%d/%m/%Y %H:%M:%S"))


class StatusTab(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.login = TarjetaEstado("Microservicio de Login")
        self.libros = TarjetaEstado("Microservicio de Libros")
        self.btn = QPushButton("Comprobar ahora")
        self.btn.clicked.connect(ventana.comprobar_salud)
        self.intervalo = QLabel()
        self.intervalo.setStyleSheet("color: gray;")
        leyenda = QLabel("🟢 funcionando con base de datos    🟡 responde pero degradado / BD no disponible    "
                         "🔴 inaccesible, error de conexión o sin respuesta")
        leyenda.setWordWrap(True)
        tarjetas = QHBoxLayout()
        tarjetas.addWidget(self.login)
        tarjetas.addWidget(self.libros)
        barra = QHBoxLayout()
        barra.addWidget(self.btn)
        barra.addWidget(self.intervalo, 1)
        capa = QVBoxLayout(self)
        capa.addLayout(tarjetas)
        capa.addLayout(barra)
        capa.addWidget(leyenda)
        capa.addStretch()


class MainWindow(QMainWindow):
    def __init__(self, controlador, token, email):
        super().__init__()
        self.c = controlador
        self.token = token
        self.email = email
        self.restantes = None
        self.avisado = False
        self.salud_en_curso = False
        self.saliendo = False
        self.setWindowTitle(f"Librería — {email}")
        self.resize(1250, 820)

        # Aviso de expiracion (oculto hasta que falten <= 5 min)
        self.banner = QWidget()
        self.banner.setStyleSheet("background: #fff3cd; color: #664d03;")
        self.banner_texto = QLabel()
        btn_ext = QPushButton("Extender sesión")
        btn_ext.clicked.connect(self.extender_sesion)
        hb = QHBoxLayout(self.banner)
        hb.addWidget(self.banner_texto, 1)
        hb.addWidget(btn_ext)
        self.banner.hide()

        self.sesion = SessionTab(self)
        self.catalogo = CatalogTab(controlador)
        self.admin = AdminTab(controlador)
        self.estado = StatusTab(self)
        self.config = ConfigPanel(controlador.config, controlador.registro.entrada.emit)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.sesion, "Sesión y perfil")
        self.tabs.addTab(self.catalogo, "Catálogo de libros")
        self.tabs.addTab(self.admin, "Administración de libros")
        self.tabs.addTab(self.estado, "Estado de los servicios")
        self.tabs.addTab(self.config, "Configuración del servidor")
        self.catalogo.editar.connect(self._editar_en_admin)
        self.admin.catalogo_cambio.connect(self.catalogo.recargar)
        self.config.guardada.connect(self._config_guardada)

        centro = QWidget()
        vc = QVBoxLayout(centro)
        vc.setContentsMargins(0, 0, 0, 0)
        vc.addWidget(self.banner)
        vc.addWidget(self.tabs)
        self.setCentralWidget(centro)

        dock = QDockWidget("Registro de peticiones HTTP", self)
        dock.setWidget(RegistroHttpWidget(controlador.registro))
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.resizeDocks([dock], [170], Qt.Vertical)

        # Barra de estado: mini semaforos + tiempo de sesion
        self.sb_login, self.sb_libros = Semaforo(), Semaforo()
        self.sb_sesion = QLabel()
        barra = self.statusBar()
        for w in (self.sb_login, QLabel("Login"), self.sb_libros, QLabel("Libros")):
            barra.addWidget(w)
        barra.addPermanentWidget(self.sb_sesion)

        self.reloj = QTimer(self, interval=1000, timeout=self._tic)
        self.timer_salud = QTimer(self, timeout=self._tic_salud)
        self._aplicar_intervalo()
        self.reloj.start()

        self.sincronizar_sesion()
        self.comprobar_salud()
        self.catalogo.ver_todo()

    # ---- sesion ----
    def sincronizar_sesion(self):
        token = self.token
        ejecutar(lambda: self.c.auth.consultar_sesion(token), self._sesion_ok, self._sesion_error)

    def _sesion_ok(self, datos):
        if not datos.get("autenticado"):
            self.cerrar_sesion(motivo="Tu sesión expiró o ya no es válida en el servidor. Inicia sesión de nuevo.",
                               avisar_servidor=False)
            return
        self.sesion.mostrar_datos(datos)
        self._set_restantes(datos.get("segundos_restantes"))
        poner_mensaje(self.sesion.mensaje, "Sesión válida en el servidor.")

    def _sesion_error(self, exc):
        # Sin conexion con login no se cierra la sesion: se reintenta en el siguiente ciclo
        poner_mensaje(self.sesion.mensaje, "No se pudo consultar la sesión: " + texto_error(exc), error=True)

    def _set_restantes(self, segundos):
        if segundos is None:
            return
        self.restantes = int(segundos)
        self.expira_en = datetime.now() + timedelta(seconds=self.restantes)
        self.sesion.expira.setText(self.expira_en.strftime("%H:%M:%S"))
        if self.restantes > AVISO_SEGUNDOS:
            self.avisado = False
            self.banner.hide()
        self._pintar_restante()
        self._revisar_aviso()

    def _revisar_aviso(self):
        if self.restantes is not None and self.restantes <= AVISO_SEGUNDOS and not self.avisado:
            self.avisado = True
            self.banner.show()

    def _tic(self):
        if self.restantes is None:
            return
        self.restantes = max(0, int((self.expira_en - datetime.now()).total_seconds()))
        self._pintar_restante()
        self._revisar_aviso()
        if self.restantes == 0:
            self.restantes = None
            self.sincronizar_sesion()  # el servidor confirma la expiracion

    def _pintar_restante(self):
        texto = formato_restante(self.restantes)
        self.sesion.restante.setText(texto)
        self.sb_sesion.setText(f"Sesión: {texto}")
        cerca = self.restantes <= AVISO_SEGUNDOS
        color = " color: #c62828;" if cerca else ""
        self.sesion.restante.setStyleSheet("font-size: 18px; font-weight: bold;" + color)
        self.banner_texto.setText(f"⚠️  Tu sesión expira en {texto}. Extiéndela para no perder el acceso.")

    def extender_sesion(self):
        token = self.token
        self.sesion.btn_extender.setEnabled(False)

        def ok(datos):
            self.sesion.btn_extender.setEnabled(True)
            self._set_restantes(datos.get("segundos_restantes"))
            poner_mensaje(self.sesion.mensaje, "Sesión extendida 30 minutos a partir de ahora.")

        def fallo(exc):
            self.sesion.btn_extender.setEnabled(True)
            if isinstance(exc, SesionExpirada):
                self.cerrar_sesion(motivo=str(exc), avisar_servidor=False)
            else:
                poner_mensaje(self.sesion.mensaje, "No se pudo extender la sesión: " + texto_error(exc), error=True)

        ejecutar(lambda: self.c.auth.extender_sesion(token), ok, fallo)

    def cerrar_sesion(self, motivo=None, avisar_servidor=True):
        if self.saliendo:
            return
        self.saliendo = True
        self.reloj.stop()
        self.timer_salud.stop()
        if avisar_servidor:
            token = self.token
            # Si el servidor no responde, igual se cierra localmente
            ejecutar(lambda: self.c.auth.cerrar_sesion(token),
                     lambda _: self.c.sesion_cerrada(self, "Sesión cerrada correctamente.", error=False),
                     lambda exc: self.c.sesion_cerrada(
                         self, "Se cerró la sesión en este equipo. Aviso del servidor: " + texto_error(exc)))
        else:
            self.c.sesion_cerrada(self, motivo)

    # ---- salud ----
    def _aplicar_intervalo(self):
        segundos = self.c.config.health_interval
        self.timer_salud.start(segundos * 1000)
        self.estado.intervalo.setText(f"Comprobación automática cada {segundos} s mientras la aplicación está abierta.")

    def _tic_salud(self):
        self.comprobar_salud()
        self.sincronizar_sesion()

    def comprobar_salud(self):
        if self.salud_en_curso:
            return
        self.salud_en_curso = True
        self.estado.btn.setEnabled(False)
        http_login, http_libros = self.c.http_login, self.c.http_libros
        ejecutar(lambda: (comprobar_login(http_login), comprobar_libros(http_libros)),
                 self._salud_ok, self._salud_error)

    def _salud_ok(self, resultados):
        self.salud_en_curso = False
        self.estado.btn.setEnabled(True)
        login, libros = resultados
        self.estado.login.mostrar(login, self.c.config.login_url)
        self.estado.libros.mostrar(libros, self.c.config.books_url)
        self.sb_login.set_estado(login.estado)
        self.sb_libros.set_estado(libros.estado)

    def _salud_error(self, exc):
        self.salud_en_curso = False
        self.estado.btn.setEnabled(True)
        self.statusBar().showMessage("No se pudo comprobar el estado: " + texto_error(exc), 8000)

    # ---- otros ----
    def _editar_en_admin(self, libro):
        self.admin.cargar_libro(libro)
        self.tabs.setCurrentWidget(self.admin)

    def _config_guardada(self, config):
        self.c.aplicar_config(config)
        self._aplicar_intervalo()
        self.comprobar_salud()
        self.sincronizar_sesion()
        self.catalogo.recargar()

    def closeEvent(self, evento):
        self.reloj.stop()
        self.timer_salud.stop()
        super().closeEvent(evento)
