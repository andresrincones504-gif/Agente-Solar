"""Contraseñas con bcrypt directo, compatibles con los hashes que generaba passlib."""
from app.core.security import get_password_hash, verify_password

# Hash generado con passlib (CryptContext bcrypt) para "clave-de-prueba"
HASH_PASSLIB = "$2b$12$plljW0WnzR8.pBZ6q3ilhO3Ab1XwM6w0gjmxpi.o6l1RSeZA9/Geq"


def test_las_contrasenas_guardadas_con_passlib_siguen_funcionando():
    assert verify_password("clave-de-prueba", HASH_PASSLIB)
    assert not verify_password("otra-clave", HASH_PASSLIB)


def test_hash_nuevo_y_verificacion():
    h = get_password_hash("Señal-123")
    assert h.startswith("$2b$") and h != get_password_hash("Señal-123")  # sal distinta cada vez
    assert verify_password("Señal-123", h)
    assert not verify_password("señal-123", h)


def test_hash_invalido_no_lanza_error():
    assert verify_password("x", "") is False
    assert verify_password("x", "no-es-un-hash") is False


def test_contrasena_larga_usa_los_primeros_72_bytes():
    larga = "a" * 100
    assert verify_password(larga, get_password_hash(larga))
