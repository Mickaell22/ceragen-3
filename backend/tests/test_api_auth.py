"""Login, sesión y manejo de errores de la API, contra la base real.

La app corre en proceso (TestClient) conectada como ceragen_app, como en
producción. A diferencia de los tests de base, estos commitean de verdad: el
fixture crea un usuario propio y lo borra al terminar.
"""

import os
import uuid

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

PASSWORD = "clave-de-test-1"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user():
    """Usuario no admin con el rol Recepción. Se borra entero al final (sesiones y auditoría incluidas)."""
    username = f"t_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
        (uid,) = conn.execute(
            "INSERT INTO security.user (username, email, password_hash) "
            "VALUES (%s, %s || '@test.local', public.crypt(%s, public.gen_salt('bf', 4))) RETURNING id",
            (username, username, PASSWORD),
        ).fetchone()
        conn.execute(
            "INSERT INTO security.user_role (user_id, role_id) "
            "SELECT %s, id FROM security.role WHERE NOT is_admin ORDER BY id LIMIT 1",
            (uid,),
        )
        yield {"id": uid, "username": username}
        conn.execute("DELETE FROM security.session WHERE user_id = %s", (uid,))
        conn.execute("DELETE FROM security.user_role WHERE user_id = %s", (uid,))
        conn.execute("DELETE FROM security.user WHERE id = %s", (uid,))
        conn.execute("DELETE FROM audit.event WHERE table_name LIKE 'security.%%' AND row_id = %s", (uid,))


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_me_logout(client, user):
    res = login(client, user["username"], PASSWORD)
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == user["id"] and body["roles"][0]["is_admin"] is False

    me = client.get("/auth/me", headers=bearer(body["access_token"]))
    # /me lee el usuario de app.user_id: si current_user no lo fijara, no lo encontraría.
    assert me.status_code == 200 and me.json()["username"] == user["username"]

    assert client.post("/auth/logout", headers=bearer(body["access_token"])).status_code == 204
    # El JWT sigue firmado y sin vencer, pero la sesión ya no existe en la base.
    assert client.get("/auth/me", headers=bearer(body["access_token"])).status_code == 401


def test_wrong_password_then_lockout(client, user):
    for _ in range(settings.login_max_attempts - 1):
        res = login(client, user["username"], "incorrecta")
        assert res.status_code == 401
        assert res.json()["detail"] == "Usuario o contraseña incorrectos"
    # El último intento permitido bloquea; desde ahí ni la correcta entra.
    assert login(client, user["username"], "incorrecta").status_code == 423
    assert login(client, user["username"], PASSWORD).status_code == 423


def test_unknown_user_gets_same_answer_as_wrong_password(client):
    res = login(client, "no_existe_nadie", PASSWORD)
    assert res.status_code == 401
    assert res.json()["detail"] == "Usuario o contraseña incorrectos"


@pytest.mark.parametrize(
    "token",
    [
        None,
        "no-es-un-jwt",
        # Firma correcta con otro secreto
        jwt.encode({"sub": "1", "jti": str(uuid.uuid4()), "exp": 9999999999}, "x" * 32, algorithm="HS256"),
        # alg none: nunca se acepta
        jwt.encode({"sub": "1", "jti": str(uuid.uuid4()), "exp": 9999999999}, None, algorithm="none"),
    ],
)
def test_bad_tokens_are_rejected(client, token):
    headers = bearer(token) if token else {}
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_valid_signature_but_unknown_session_is_rejected(client):
    token = jwt.encode(
        {"sub": "1", "jti": str(uuid.uuid4()), "exp": 9999999999},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_validation_error_does_not_echo_the_password(client):
    secret = "x" * 300  # supera max_length
    res = login(client, "alguien", secret)
    assert res.status_code == 422
    assert secret not in res.text


def test_unexpected_errors_do_not_leak_details(user, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("detalle interno sensible")

    monkeypatch.setattr("app.auth.jwt.encode", boom)  # falla después de un login correcto
    res = login(TestClient(app, raise_server_exceptions=False), user["username"], PASSWORD)
    assert res.status_code == 500
    assert res.json() == {"detail": "Error interno del servidor"}
