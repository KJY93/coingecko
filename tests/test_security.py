import jwt
from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_access_token

def test_password_hash_and_verify():
    password_raw = "somedummypassword"
    fake_password = "fakepassword"
    hashed = get_password_hash(password_raw)
    assert hashed != password_raw
    assert verify_password(password_raw, hashed)
    assert not verify_password(fake_password, hashed)

def test_create_access_token():
    token = create_access_token({ "sub": "alice" })
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "alice"
    assert "exp" in payload