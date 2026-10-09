"""Usuarios (servicio users, :5002): el admin administra a todos; el cliente solo ve y edita su cuenta."""

from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox,
                               QPushButton, QVBoxLayout)

from ui.crud_base import CrudTab

COLUMNAS = ["ID", "Correo", "Nombre", "Apellido paterno", "Apellido materno", "Rol"]


class UsersTab(CrudTab):
    def __init__(self, controlador):
        super().__init__(controlador, COLUMNAS)
        self._usuarios = {}
        self.correo = QLineEdit(placeholderText="correo@ejemplo.com")
        self.nombre = QLineEdit()
        self.ap_paterno = QLineEdit()
        self.ap_materno = QLineEdit()
        self.password = QLineEdit(placeholderText="mínimo 8 caracteres (crear / nueva contraseña)")
        self.password.setEchoMode(QLineEdit.Password)
        self.password_actual = QLineEdit(placeholderText="solo al cambiar TU contraseña")
        self.password_actual.setEchoMode(QLineEdit.Password)
        self.rol = QComboBox()
        self.rol.addItems(["cliente", "admin"])

        form = QFormLayout()
        for etiqueta, campo in (("Correo:", self.correo), ("Nombre:", self.nombre),
                                ("Apellido paterno:", self.ap_paterno), ("Apellido materno:", self.ap_materno),
                                ("Contraseña (nueva):", self.password), ("Contraseña actual:", self.password_actual),
                                ("Rol:", self.rol)):
            form.addRow(etiqueta, campo)
        caja = QGroupBox("Datos del usuario")
        caja.setLayout(form)

        self.btn_recargar = QPushButton("Recargar (GET)")
        self.btn_crear = QPushButton("Crear (POST)")
        self.btn_guardar = QPushButton("Guardar cambios (PATCH)")
        self.btn_password = QPushButton("Cambiar contraseña (PATCH)")
        self.btn_rol = QPushButton("Cambiar rol (PATCH)")
        self.btn_eliminar = QPushButton("Eliminar (DELETE)")
        self.btn_eliminar.setStyleSheet("color: #c62828;")
        self.btn_limpiar = QPushButton("Limpiar")
        self.registrar(self.btn_recargar, self.btn_guardar, self.btn_password, self.btn_limpiar)
        self.solo_admin(self.btn_crear, self.btn_rol, self.btn_eliminar, self.rol)
        self.btn_recargar.clicked.connect(self.recargar)
        self.btn_crear.clicked.connect(self.crear)
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_password.clicked.connect(self.cambiar_password)
        self.btn_rol.clicked.connect(self.cambiar_rol)
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_limpiar.clicked.connect(self.limpiar)
        self.seleccion_cambio.connect(self._cargar_seleccion)

        barra = QHBoxLayout()
        for b in (self.btn_recargar, self.btn_crear, self.btn_guardar, self.btn_password, self.btn_rol,
                  self.btn_eliminar, self.btn_limpiar):
            barra.addWidget(b)
        capa = QVBoxLayout(self)
        capa.addWidget(self.tabla, 1)
        capa.addWidget(caja)
        capa.addLayout(barra)
        capa.addWidget(self.mensaje)
        capa.addWidget(self.btn_login)
        self.refrescar_permisos()

    # ---- lectura ----
    def al_activar(self):
        self.recargar()

    def recargar(self):
        if not self.hay_sesion():
            self.refrescar_permisos()
            return
        users = lambda: self.c.users  # noqa: E731 - las APIs se reconstruyen al guardar la configuracion
        if self.es_admin():
            funcion = lambda: users().listar()  # noqa: E731
        elif self.c.user_id is not None:
            uid = self.c.user_id
            funcion = lambda: [users().obtener(uid)]  # noqa: E731
        else:
            self.error("Aún no se conoce tu usuario; espera a que la sesión se valide y recarga.")
            return
        self.llamar("GET", funcion, self._mostrar)

    def _mostrar(self, usuarios):
        self._usuarios = {u["id_usuario"]: u for u in usuarios}
        self.llenar_tabla([[u["id_usuario"], u.get("correo"), u.get("nombre"), u.get("apellido_paterno"),
                            u.get("apellido_materno"), u.get("rol")] for u in usuarios],
                          [u["id_usuario"] for u in usuarios])
        self.ok(f"{len(usuarios)} usuario(s).")

    def _cargar_seleccion(self, id_usuario):
        u = self._usuarios.get(id_usuario)
        if not u:
            return
        self.correo.setText(u.get("correo", ""))
        self.nombre.setText(u.get("nombre", ""))
        self.ap_paterno.setText(u.get("apellido_paterno", ""))
        self.ap_materno.setText(u.get("apellido_materno", ""))
        self.rol.setCurrentText(u.get("rol", "cliente"))
        self.password.clear()
        self.password_actual.clear()

    def limpiar(self):
        for campo in (self.correo, self.nombre, self.ap_paterno, self.ap_materno, self.password, self.password_actual):
            campo.clear()
        self.tabla.clearSelection()
        self.mensaje.clear()

    # ---- validaciones ----
    def _perfil(self):
        valores = {"correo": self.correo.text().strip(), "nombre": self.nombre.text().strip(),
                   "apellido_paterno": self.ap_paterno.text().strip(), "apellido_materno": self.ap_materno.text().strip()}
        faltan = [k for k, v in valores.items() if not v]
        if faltan:
            raise ValueError("Faltan campos obligatorios: " + ", ".join(faltan) + ".")
        return valores

    def _password_nueva(self):
        nueva = self.password.text()
        if len(nueva) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return nueva

    def _seleccionado_o_error(self):
        id_usuario = self.id_seleccionado()
        if id_usuario is None:
            self.error("Selecciona un usuario de la tabla.")
        return id_usuario

    # ---- escrituras ----
    def crear(self):
        try:
            p = self._perfil()
            clave = self._password_nueva()
        except ValueError as exc:
            self.error(str(exc))
            return

        def exito(r):
            self.ok(f"POST correcto (201): usuario {r.get('id_usuario')} creado.")
            self.recargar()

        self.llamar("POST", lambda: self.c.users.crear(p["correo"], p["nombre"], p["apellido_paterno"],
                                                       p["apellido_materno"], clave, self.rol.currentText()), exito)

    def guardar(self):
        id_usuario = self._seleccionado_o_error()
        if id_usuario is None:
            return
        try:
            p = self._perfil()
        except ValueError as exc:
            self.error(str(exc))
            return

        def exito(_):
            self.ok(f"PATCH correcto (200): usuario {id_usuario} actualizado.")
            self.recargar()

        self.llamar("PATCH", lambda: self.c.users.actualizar(id_usuario, **p), exito)

    def cambiar_password(self):
        id_usuario = self._seleccionado_o_error()
        if id_usuario is None:
            return
        try:
            nueva = self._password_nueva()
        except ValueError as exc:
            self.error(str(exc))
            return
        propio = id_usuario == self.c.user_id
        actual = self.password_actual.text() if propio else None
        if propio and not actual:
            self.error("Para cambiar tu propia contraseña escribe la contraseña actual.")
            return

        def exito(_):
            self.password.clear()
            self.password_actual.clear()
            self.ok(f"PATCH correcto (200): contraseña del usuario {id_usuario} actualizada.")

        self.llamar("PATCH", lambda: self.c.users.cambiar_password(id_usuario, nueva, actual), exito)

    def cambiar_rol(self):
        id_usuario = self._seleccionado_o_error()
        if id_usuario is None:
            return
        rol = self.rol.currentText()

        def exito(_):
            self.ok(f"PATCH correcto (200): usuario {id_usuario} ahora es {rol} (aplica a su siguiente sesión).")
            self.recargar()

        self.llamar("PATCH", lambda: self.c.users.cambiar_rol(id_usuario, rol), exito)

    def eliminar(self):
        id_usuario = self._seleccionado_o_error()
        if id_usuario is None:
            return
        r = QMessageBox.question(self, "Confirmar eliminación",
                                 f"¿Eliminar definitivamente al usuario {id_usuario}?\nEsta acción no se puede deshacer.",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            self.ok("Eliminación cancelada.")
            return

        def exito(_):
            self.ok(f"DELETE correcto (200): usuario {id_usuario} eliminado.")
            self.limpiar()
            self.recargar()

        self.llamar("DELETE", lambda: self.c.users.eliminar(id_usuario), exito)
