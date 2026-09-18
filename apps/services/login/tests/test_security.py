"""Pruebas puras de auth/security.py (sin BD, sin red). Asserts planos.

Uso:
    cd apps/services/login && python tests/test_security.py
"""
from auth.security import (
    hash_password, verificar_password,
    generar_codigo, hash_codigo, verificar_codigo,
    generar_token,
)


def main():
    hash_pw = hash_password("miPassword123")
    assert hash_pw != "miPassword123"
    assert verificar_password("miPassword123", hash_pw) is True
    assert verificar_password("otraCosa", hash_pw) is False
    print("hash_password / verificar_password OK")

    codigo = generar_codigo()
    assert len(codigo) == 6
    assert codigo.isdigit()
    print(f"generar_codigo OK -> {codigo}")

    hash_c = hash_codigo(codigo)
    assert hash_c != codigo
    assert verificar_codigo(codigo, hash_c) is True
    assert verificar_codigo("000000" if codigo != "000000" else "111111", hash_c) is False
    print("hash_codigo / verificar_codigo OK")

    token_a = generar_token()
    token_b = generar_token()
    assert len(token_a) == 64
    assert token_a != token_b
    print("generar_token OK")

    print("\nTODAS LAS PRUEBAS DE security.py PASARON")


if __name__ == "__main__":
    main()
