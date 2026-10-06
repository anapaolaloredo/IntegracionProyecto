import pytest

import app as users_app
from common.jwt_auth import ROLE_ADMIN, ROLE_USER
from common.testing import auth_header

FILA = {"id_usuario": 2, "correo": "a@b.co", "rol": "cliente", "fecha_registro": None,
        "nombre": "Ana", "apellido_paterno": "L", "apellido_materno": "M"}
ADMIN = auth_header(1, ROLE_ADMIN)
USER2 = auth_header(2, ROLE_USER)
USER3 = auth_header(3, ROLE_USER)


@pytest.fixture
def c(monkeypatch):
    users_app.app.config["TESTING"] = True
    r = users_app.repository
    monkeypatch.setattr(r, "listar", lambda: [dict(FILA)])
    monkeypatch.setattr(r, "obtener", lambda i: dict(FILA, id_usuario=i) if i != 99 else None)
    return users_app.app.test_client()


def test_roles_es_publico(c):
    assert c.get("/api/roles").get_json() == [
        {"role_id": 1, "nombre": "admin"}, {"role_id": 2, "nombre": "cliente"}]


@pytest.mark.parametrize("metodo,ruta", [
    ("post", "/api/users"), ("put", "/api/users/2"), ("patch", "/api/users/2"),
    ("delete", "/api/users/2"), ("patch", "/api/users/2/password"), ("patch", "/api/users/2/rol"),
])
def test_escrituras_sin_token_401(c, metodo, ruta):
    assert getattr(c, metodo)(ruta, json={}).status_code == 401


def test_lecturas_de_usuarios_exigen_jwt(c):
    assert c.get("/api/users").status_code == 401
    assert c.get("/api/users/2").status_code == 401


def test_listar_solo_admin(c):
    assert c.get("/api/users", headers=USER2).status_code == 403
    resp = c.get("/api/users", headers=ADMIN)
    assert resp.status_code == 200
    assert all("contrasena_hash" not in u for u in resp.get_json())
    assert resp.get_json()[0]["role_id"] == 2


def test_ver_usuario_propio_o_admin_pero_no_ajeno(c):
    assert c.get("/api/users/2", headers=USER2).status_code == 200
    assert c.get("/api/users/2", headers=USER3).status_code == 403
    assert c.get("/api/users/2", headers=ADMIN).status_code == 200
    assert c.get("/api/users/99", headers=ADMIN).status_code == 404


def test_crear_solo_admin_y_guarda_hash(c, monkeypatch):
    capturado = {}

    def crear(correo, hash_, rol, nombre, ap, am):
        capturado.update(hash=hash_, rol=rol)
        return 10

    monkeypatch.setattr(users_app.repository, "crear", crear)
    cuerpo = {"correo": "n@b.co", "password": "secreta123", "nombre": "N",
              "apellido_paterno": "P", "apellido_materno": "M"}
    assert c.post("/api/users", json=cuerpo, headers=USER2).status_code == 403
    resp = c.post("/api/users", json=cuerpo, headers=ADMIN)
    assert resp.status_code == 201 and resp.get_json()["id_usuario"] == 10
    assert capturado["hash"] != "secreta123" and capturado["rol"] == "cliente"


@pytest.mark.parametrize("cambio", [
    {"correo": "malo"}, {"password": "corta"}, {"rol": "dios"}, {"nombre": ""}, {"nombre": 5},
])
def test_crear_valida_campos(c, cambio):
    cuerpo = {"correo": "n@b.co", "password": "secreta123", "nombre": "N",
              "apellido_paterno": "P", "apellido_materno": "M", **cambio}
    assert c.post("/api/users", json=cuerpo, headers=ADMIN).status_code == 400


def test_cuerpo_no_objeto_da_400(c):
    assert c.post("/api/users", data="[1]", content_type="application/json", headers=ADMIN).status_code == 400


def test_actualizar_propio_ajeno_y_vacio(c, monkeypatch):
    monkeypatch.setattr(users_app.repository, "actualizar", lambda i, campos: True)
    assert c.patch("/api/users/2", json={"nombre": "Nuevo"}, headers=USER2).status_code == 200
    assert c.patch("/api/users/2", json={"nombre": "Nuevo"}, headers=USER3).status_code == 403
    assert c.patch("/api/users/2", json={}, headers=USER2).status_code == 400
    assert c.put("/api/users/2", json={"nombre": "x"}, headers=USER2).status_code == 400  # PUT exige todos


def test_password_propio_requiere_actual(c, monkeypatch):
    from werkzeug.security import generate_password_hash
    guardado = {}
    monkeypatch.setattr(users_app.repository, "obtener_hash", lambda i: generate_password_hash("vieja12345"))
    monkeypatch.setattr(users_app.repository, "cambiar_password",
                        lambda i, h: guardado.setdefault("h", h) or True)
    mala = {"password_actual": "equivocada", "password_nueva": "nueva12345"}
    assert c.patch("/api/users/2/password", json=mala, headers=USER2).status_code == 403
    buena = {"password_actual": "vieja12345", "password_nueva": "nueva12345"}
    assert c.patch("/api/users/2/password", json=buena, headers=USER2).status_code == 200
    assert guardado["h"] != "nueva12345"
    assert c.patch("/api/users/2/password", json=buena, headers=USER3).status_code == 403


def test_admin_resetea_password_ajeno_sin_actual(c, monkeypatch):
    monkeypatch.setattr(users_app.repository, "cambiar_password", lambda i, h: True)
    assert c.patch("/api/users/2/password", json={"password_nueva": "nueva12345"},
                   headers=ADMIN).status_code == 200


def test_cambiar_rol_y_eliminar_solo_admin(c, monkeypatch):
    monkeypatch.setattr(users_app.repository, "cambiar_rol", lambda i, r: True)
    monkeypatch.setattr(users_app.repository, "eliminar", lambda i: i != 99)
    assert c.patch("/api/users/2/rol", json={"rol": "admin"}, headers=USER2).status_code == 403
    assert c.patch("/api/users/2/rol", json={"rol": "admin"}, headers=ADMIN).status_code == 200
    assert c.patch("/api/users/2/rol", json={"rol": "dios"}, headers=ADMIN).status_code == 400
    assert c.delete("/api/users/2", headers=USER2).status_code == 403
    assert c.delete("/api/users/2", headers=ADMIN).status_code == 200
    assert c.delete("/api/users/99", headers=ADMIN).status_code == 404
