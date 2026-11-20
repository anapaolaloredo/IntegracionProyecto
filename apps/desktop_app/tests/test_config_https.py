import pytest

from core.config import SERVICIOS, AppConfig, cambiar_esquema


@pytest.fixture(autouse=True)
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRERIA_CONFIG_DIR", str(tmp_path))


def test_defaults_tienen_seis_servicios_en_http():
    c = AppConfig.defaults()
    assert c.protocolo == "http"
    assert [c.url(k) for k, _, _ in SERVICIOS] == [f"http://localhost:{p}" for _, _, p in SERVICIOS]


def test_cambiar_esquema_conserva_host_y_puerto():
    assert cambiar_esquema("http://34.10.20.30:5002", "https") == "https://34.10.20.30:5002"
    assert cambiar_esquema("https://api.ejemplo.mx", "http") == "http://api.ejemplo.mx"
    assert cambiar_esquema("http://h:5000/base", "https") == "https://h:5000/base"


def test_con_protocolo_reescribe_las_seis_urls():
    c = AppConfig.defaults().con_protocolo("https")
    assert c.protocolo == "https"
    assert all(c.url(k).startswith("https://") for k, _, _ in SERVICIOS)
    assert c.con_protocolo("http").url("pagos") == "http://localhost:5005"


def test_validar_rechaza_protocolo_raro_y_url_mala():
    c = AppConfig.defaults()
    c.protocolo = "ftp"
    assert any("protocolo" in e.lower() for e in c.validar())
    c = AppConfig.defaults()
    c.pedidos_url = "pedidos:5004"
    assert any("Pedidos" in e for e in c.validar())


def test_guardar_y_cargar_conserva_protocolo():
    AppConfig.defaults().con_protocolo("https").save()
    c = AppConfig.load()
    assert c.protocolo == "https" and c.url("users").startswith("https://")


def test_config_vieja_sin_claves_nuevas_carga_con_defaults(tmp_path):
    (tmp_path / "config.json").write_text('{"login_url": "http://h:5000", "books_url": "http://h:5001", '
                                          '"timeout": 5, "health_interval": 30}')
    c = AppConfig.load()
    assert c.login_url == "http://h:5000" and c.users_url == "http://localhost:5002" and c.protocolo == "http"


def test_gateway_deriva_las_seis_urls_de_un_host():
    c = AppConfig.desde_gateway("http://34.10.20.30:5000/x")
    assert c.gateway and c.host_gateway() == "34.10.20.30"
    assert c.url("login") == "http://34.10.20.30/api/auth"
    assert all(c.url(k) == "http://34.10.20.30" for k in ("books", "users", "authors", "pedidos", "pagos"))
    assert not c.validar()


def test_ruta_salud_directa_y_por_gateway():
    assert AppConfig.defaults().ruta_salud("books") == "/health"
    g = AppConfig.desde_gateway("h")
    assert g.ruta_salud("books") == "/health/libros"
    assert g.ruta_salud("login") == "/health"  # base /api/auth + /health


def test_gateway_se_guarda_y_se_carga():
    AppConfig.desde_gateway("h", "https").save()
    c = AppConfig.load()
    assert c.gateway and c.url("login") == "https://h/api/auth"
