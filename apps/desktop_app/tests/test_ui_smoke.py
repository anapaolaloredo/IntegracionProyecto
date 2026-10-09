"""Pruebas de las pestanas con la interfaz en modo offscreen y APIs falsas
(no tocan la red ni los microservicios)."""

from tests.conftest import esperar
from core.http import ServiceError, SesionExpirada
from ui.crud_base import CrudTab


class Demo(CrudTab):
    def __init__(self, c):
        super().__init__(c, ["ID", "Nombre"])


def test_llenar_tabla_y_seleccion(ctrl, qapp):
    t = Demo(ctrl)
    t.llenar_tabla([["1", "A"], ["2", "B"]], [1, 2])
    t.tabla.selectRow(1)
    assert t.id_seleccionado() == 2


def test_llamar_exito_ejecuta_callback(ctrl, qapp):
    t, vistos = Demo(ctrl), []
    t.llamar("GET", lambda: 41 + 1, vistos.append)
    assert esperar(qapp, lambda: vistos == [42])


def test_llamar_error_de_servicio_muestra_mensaje_sin_cerrar_sesion(ctrl, qapp):
    t = Demo(ctrl)

    def falla():
        raise ServiceError("Stock insuficiente (HTTP 409)", status=409)

    t.llamar("POST", falla, lambda _: None)
    assert esperar(qapp, lambda: "Stock insuficiente" in t.mensaje.text())
    assert not hasattr(ctrl.ventana, "motivo")


def test_llamar_sesion_expirada_intenta_renovar(ctrl, qapp):
    t = Demo(ctrl)

    def vence():
        raise SesionExpirada("expiro", status=401)

    t.llamar("GET", vence, lambda _: None)
    assert esperar(qapp, lambda: ctrl.ventana.renovaciones == 1)
    assert "renovó" in t.mensaje.text()


def test_solo_admin_deshabilita_para_cliente(ctrl_cliente, qapp):
    from PySide6.QtWidgets import QPushButton
    t = Demo(ctrl_cliente)
    b = QPushButton("Borrar")
    t.solo_admin(b)
    t.refrescar_permisos()
    assert not b.isEnabled() and "administrador" in b.toolTip().lower()


def test_admin_habilita(ctrl, qapp):
    from PySide6.QtWidgets import QPushButton
    t = Demo(ctrl)
    b = QPushButton("Borrar")
    t.solo_admin(b)
    t.refrescar_permisos()
    assert b.isEnabled()


def test_invitado_en_seccion_con_sesion_ve_aviso(ctrl_invitado, qapp):
    t = Demo(ctrl_invitado)
    t.refrescar_permisos()
    assert "Inicia sesión" in t.mensaje.text() and not t.tabla.isEnabled()


# ---------------------------------------------------------------- Usuarios
class FakeUsers:
    def __init__(self):
        self.calls = []
        self.datos = [
            {"id_usuario": 1, "correo": "a@x.mx", "nombre": "Ana", "apellido_paterno": "L", "apellido_materno": "M",
             "rol": "admin", "role_id": 1},
            {"id_usuario": 7, "correo": "c@x.mx", "nombre": "Cli", "apellido_paterno": "P", "apellido_materno": "Q",
             "rol": "cliente", "role_id": 2}]

    def listar(self):
        self.calls.append(("listar",))
        return self.datos

    def obtener(self, i):
        self.calls.append(("obtener", i))
        return next(u for u in self.datos if u["id_usuario"] == i)

    def crear(self, *a):
        self.calls.append(("crear",) + a)
        return {"id_usuario": 9}

    def actualizar(self, i, **c):
        self.calls.append(("actualizar", i, c))
        return {}

    def cambiar_password(self, i, nueva, actual=None):
        self.calls.append(("password", i, nueva, actual))
        return {}

    def cambiar_rol(self, i, rol):
        self.calls.append(("rol", i, rol))
        return {}

    def eliminar(self, i):
        self.calls.append(("eliminar", i))
        return {}


def _tabu(c):
    from ui.users_tab import UsersTab
    c.users = FakeUsers()
    return UsersTab(c)


def test_admin_lista_todos(ctrl, qapp):
    t = _tabu(ctrl)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 2)


def test_cliente_ve_solo_su_renglon_y_botones_admin_deshabilitados(ctrl_cliente, qapp):
    t = _tabu(ctrl_cliente)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    assert ctrl_cliente.users.calls[0] == ("obtener", 7)
    assert not t.btn_crear.isEnabled() and not t.btn_eliminar.isEnabled() and not t.btn_rol.isEnabled()


def test_crear_valida_password_corta_sin_llamar_a_la_red(ctrl, qapp):
    t = _tabu(ctrl)
    t.correo.setText("n@x.mx"); t.nombre.setText("N"); t.ap_paterno.setText("A"); t.ap_materno.setText("B")
    t.password.setText("corta")
    t.btn_crear.click()
    assert "8 caracteres" in t.mensaje.text() and not [c for c in ctrl.users.calls if c[0] == "crear"]


def test_crear_envia_los_campos(ctrl, qapp):
    t = _tabu(ctrl)
    t.correo.setText("n@x.mx"); t.nombre.setText("N"); t.ap_paterno.setText("A"); t.ap_materno.setText("B")
    t.password.setText("claveSegura1"); t.rol.setCurrentText("cliente")
    t.btn_crear.click()
    assert esperar(qapp, lambda: ("crear", "n@x.mx", "N", "A", "B", "claveSegura1", "cliente") in ctrl.users.calls)


def test_cambiar_password_propio_exige_actual(ctrl_cliente, qapp):
    t = _tabu(ctrl_cliente)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    t.tabla.selectRow(0)
    t.password.setText("nuevaClave12")
    t.btn_password.click()
    assert "contraseña actual" in t.mensaje.text().lower()
    t.password_actual.setText("viejaClave12")
    t.btn_password.click()
    assert esperar(qapp, lambda: ("password", 7, "nuevaClave12", "viejaClave12") in ctrl_cliente.users.calls)


def test_admin_cambia_password_de_otro_sin_actual(ctrl, qapp):
    t = _tabu(ctrl)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 2)
    t.tabla.selectRow(1)  # usuario 7, distinto del admin (user_id=1)
    t.password.setText("resetClave12")
    t.btn_password.click()
    assert esperar(qapp, lambda: ("password", 7, "resetClave12", None) in ctrl.users.calls)


# ----------------------------------------------------------------- Autores
class FakeAuthors:
    def __init__(self):
        self.calls = []

    def listar(self):
        self.calls.append(("listar",))
        return [{"id_autor": 2, "nombre_autor": "Borges"}]

    def obtener(self, i):
        self.calls.append(("obtener", i))
        return {"id_autor": i, "nombre_autor": "Borges", "libros": [{"id_libro": 11, "titulo": "El aleph"}]}

    def crear(self, n):
        self.calls.append(("crear", n))
        return {"id_autor": 3}

    def renombrar(self, i, n):
        self.calls.append(("renombrar", i, n))
        return {}

    def eliminar(self, i):
        self.calls.append(("eliminar", i))
        return {}

    def vincular(self, a, lib):
        self.calls.append(("vincular", a, lib))
        return {}

    def desvincular(self, a, lib):
        self.calls.append(("desvincular", a, lib))
        return {}


class FakeLibros:
    def listar(self):
        from core.books_api import Libro
        return [Libro("978", "El aleph", id_libro=11), Libro("979", "Sin id")]


def _taba(c):
    from ui.authors_tab import AuthorsTab
    c.authors, c.libros = FakeAuthors(), FakeLibros()
    return AuthorsTab(c)


def test_invitado_puede_listar_autores(ctrl_invitado, qapp):
    t = _taba(ctrl_invitado)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    assert "Inicia sesión" not in t.mensaje.text()
    assert not t.btn_crear.isEnabled()


def test_seleccionar_autor_muestra_sus_libros(ctrl, qapp):
    t = _taba(ctrl)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1)
    t.tabla.selectRow(0)
    assert esperar(qapp, lambda: t.lista_libros.count() == 1)
    assert t.nombre.text() == "Borges"


def test_combo_ignora_libros_sin_id(ctrl, qapp):
    t = _taba(ctrl)
    t.al_activar()
    assert esperar(qapp, lambda: t.combo_libro.count() == 1)


def test_vincular_envia_ids(ctrl, qapp):
    t = _taba(ctrl)
    t.al_activar()
    assert esperar(qapp, lambda: t.tabla.rowCount() == 1 and t.combo_libro.count() == 1)
    t.tabla.selectRow(0)
    assert esperar(qapp, lambda: t.lista_libros.count() == 1)
    t.btn_vincular.click()
    assert esperar(qapp, lambda: ("vincular", 2, 11) in ctrl.authors.calls)


def test_nombre_vacio_o_largo_no_llama_a_la_red(ctrl, qapp):
    t = _taba(ctrl)
    t.btn_crear.click()
    t.nombre.setText("x" * 151)
    t.btn_crear.click()
    assert not [c for c in ctrl.authors.calls if c[0] == "crear"]
