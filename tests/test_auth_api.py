from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError
from main import app
from app.core.security import get_current_user

client = TestClient(app)

def test_register_success(mocker):
    mocker.patch("app.api.auth.create_user")
    response = client.post("/auth/register", json = { "username": "iamgroot", "password": "iamgroot", "email": "iamgroot@example.com" })
    body = response.json()
    assert response.status_code == 201
    assert "username" in body
    assert "email" in body
    assert "password" not in body
    assert "hashed_password" not in body

def test_register_duplicate(mocker):
    mocker.patch("app.api.auth.create_user", side_effect=DuplicateKeyError("duplicate user"))
    response = client.post("/auth/register", json = { "username": "iamgroot", "password": "iamgroot", "email": "iamgroot@example.com" })
    assert response.status_code == 409
    assert response.json()["detail"] == "username has already been taken"

def test_login_success(mocker):
    fake_user = { "username": "alice", "email": "alice@example.com", "hashed_password": "fakehash" }
    mocker.patch("app.api.auth.get_user_by_username", return_value=fake_user)
    mocker.patch("app.api.auth.verify_password", return_value=True)
    response = client.post("/auth/login", data={"username": "alice", "password": "hunter2"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

def test_login_wrong_password(mocker):
    fake_user = { "username": "alice", "email": "alice@example.com", "hashed_password": "fakehash" }
    mocker.patch("app.api.auth.get_user_by_username", return_value=fake_user)
    mocker.patch("app.api.auth.verify_password", return_value=False)
    # here the OAuth2PasswordRequestForm requires username and password (not optional)
    response = client.post("/auth/login", data={"username": "alice", "password": "hunter2"})
    assert response.status_code == 401
    assert response.json()["detail"] == "user is not authorized"

def test_login_user_not_found(mocker):
    mocker.patch("app.api.auth.get_user_by_username", return_value=None)
    response = client.post("/auth/login", data={"username": "alice", "password": "hunter2"})
    assert response.status_code == 401
    assert response.json()["detail"] == "user is not authorized"

def test_account_with_auth(override_auth):
    response = client.get("/auth/account")
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["email"] == "alice@example.com"

def test_account_without_auth():
    response = client.get("/auth/account")
    assert response.status_code == 401