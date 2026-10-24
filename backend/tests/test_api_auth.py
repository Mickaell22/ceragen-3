"""Login, sesión en cookie httpOnly, CSRF y manejo de errores de la API, contra la base real.

La app corre en proceso (TestClient) conectada como ceragen_app, como en
producción. TestClient guarda las cookies igual que un navegador. A diferencia
de los tests de base, estos commitean de verdad: el fixture crea un usuario
propio y lo borra al terminar.
"""

import os
import uuid

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE
from app.config import settings
from app.main import app

PASSWORD = "clave-de-test-1"
ORIGIN = {"Origin": settings.cors_origin_list[0]}  # como lo mandaría el navegador desde el front


@pytest.fixture
def client():
    return TestClient(app, headers=ORIGIN)


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


def forged(secret):
    return jwt.encode({"sub": "1", "jti": str(uuid.uuid4()), "exp": 9999999999}, secret, algorithm="HS256")


def test_login_sets_httponly_cookie_and_never_returns_the_token(client, user):
    res = login(client, user["username"], PASSWORD)
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == user["id"] and body["roles"][0]["is_admin"] is False
    assert "access_token" not in body

    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie and f"SameSite={settings.cookie_samesite}" in cookie


def test_me_and_logout_with_cookie(client, user):
    login(client, user["username"], PASSWORD)
    token = client.cookies[COOKIE]

    me = client.get("/auth/me")
    # /me lee el usuario de app.user_id: si current_user no lo fijara, no lo encontraría.
    assert me.status_code == 200 and me.json()["username"] == user["username"]

    assert client.post("/auth/logout").status_code == 204
    assert COOKIE not in client.cookies  # el navegador la borra

    # Aunque alguien hubiera guardado el token, la sesión ya no existe en la base.
    client.cookies.set(COOKIE, token)
    assert client.get("/auth/me").status_code == 401


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
        forged("x" * 32),  # firma correcta con otro secreto
        jwt.encode({"sub": "1", "jti": str(uuid.uuid4()), "exp": 9999999999}, None, algorithm="none"),
        forged(settings.jwt_secret.get_secret_value()),  # firma válida pero sesión inexistente
    ],
)
def test_bad_tokens_are_rejected(client, token):
    if token:
        client.cookies.set(COOKIE, token)
    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {}])
def test_csrf_writes_with_cookie_need_our_origin(user, headers):
    victim = TestClient(app, headers=ORIGIN)
    login(victim, user["username"], PASSWORD)
    # Sitio ajeno, o petición sin Origin, que llega con la cookie de la víctima.
    attacker = TestClient(app)
    attacker.cookies.set(COOKIE, victim.cookies[COOKIE])
    res = attacker.post("/auth/logout", headers=headers)
    assert res.status_code == 403
    assert victim.get("/auth/me").status_code == 200  # la sesión sigue viva


def test_login_csrf_from_foreign_origin_is_rejected(user):
    res = TestClient(app).post(
        "/auth/login",
        json={"username": user["username"], "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403


def test_validation_error_does_not_echo_the_password(client):
    secret = "x" * 300  # supera max_length
    res = login(client, "alguien", secret)
    assert res.status_code == 422
    assert secret not in res.text


def test_unexpected_errors_do_not_leak_details(user, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("detalle interno sensible")

    monkeypatch.setattr("app.auth.jwt.encode", boom)  # falla después de un login correcto
    res = login(TestClient(app, headers=ORIGIN, raise_server_exceptions=False), user["username"], PASSWORD)
    assert res.status_code == 500
    assert res.json() == {"detail": "Error interno del servidor"}
