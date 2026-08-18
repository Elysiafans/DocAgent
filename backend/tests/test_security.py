from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_token_roundtrip():
    token = create_access_token("42")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
