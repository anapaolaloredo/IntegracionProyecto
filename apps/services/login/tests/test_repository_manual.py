"""Prueba manual de repository.py contra una base de datos real (requiere
que data/migrations/2026-09-18_tablas_login.sql ya este aplicado).
No usa ningun framework de pruebas: son asserts planos sobre datos que la
propia prueba crea y limpia.

Uso:
    cd apps/services/login && python tests/test_repository_manual.py
"""
from datetime import datetime, timedelta, timezone

from db import repository
from db.connection import get_connection

CORREO_PRUEBA = "repo.prueba@correo.test"


def limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cuentas WHERE correo = %s", (CORREO_PRUEBA,))
        conn.commit()


def main():
    limpiar()

    id_usuario = repository.crear_usuario(
        CORREO_PRUEBA, "hash-de-prueba", "Ana", "Loredo", "Moreno"
    )
    assert isinstance(id_usuario, int)
    print(f"crear_usuario OK -> id_usuario={id_usuario}")

    usuario = repository.obtener_usuario_por_correo(CORREO_PRUEBA)
    assert usuario is not None
    assert usuario["nombre"] == "Ana"
    print("obtener_usuario_por_correo OK")

    expira_en = datetime.now(timezone.utc) + timedelta(minutes=5)
    id_codigo = repository.guardar_codigo(id_usuario, "codigo-hash", expira_en)
    vigente = repository.obtener_codigo_vigente(id_usuario)
    assert vigente["id_codigo"] == id_codigo
    print("guardar_codigo / obtener_codigo_vigente OK")

    repository.marcar_codigo_usado(id_codigo)
    assert repository.obtener_codigo_vigente(id_usuario) is None
    print("marcar_codigo_usado OK")

    token = "token-de-prueba-1234"
    expira_sesion = datetime.now(timezone.utc) + timedelta(minutes=30)
    repository.crear_sesion(token, id_usuario, expira_sesion)
    sesion = repository.obtener_sesion_vigente(token)
    assert sesion["correo"] == CORREO_PRUEBA
    print("crear_sesion / obtener_sesion_vigente OK")

    repository.eliminar_sesion(token)
    assert repository.obtener_sesion_vigente(token) is None
    print("eliminar_sesion OK")

    assert repository.verificar_conexion() is True
    print("verificar_conexion OK")

    limpiar()
    print("\nTODAS LAS PRUEBAS DE repository.py PASARON")


if __name__ == "__main__":
    main()
