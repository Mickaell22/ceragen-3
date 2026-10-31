"""Endpoints de gestión de usuarios: permisos (403), alta, conflicto (409), regla de negocio (422)."""

import uuid

import pytest
from conftest import API_PASSWORD
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

ORIGIN = {"Origin": settings.cors_origin_list[0]}


def logged_in(user):
    client = TestClient(app, headers=ORIGIN)
    assert client.post(
        "/auth/login", json={"username": user["username"], "password": API_PASSWORD}
    ).is_success
    return client


@pytest.fixture
def admin(make_api_user):
    return logged_in(make_api_user(admin=True))


def staff_role_id(client):
    return next(r["id"] for r in client.get("/roles").json() if not r["is_admin"])


def test_non_admin_gets_403_with_db_message(make_api_user):
    client = logged_in(make_api_user())
    res = client.get("/users")
    assert res.status_code == 403
    assert res.json() == {"detail": "esta acción requiere un administrador"}


def test_admin_creates_lists_and_updates_a_user(admin, make_api_user):
    username = f"t_{uuid.uuid4().hex[:10]}"
    res = admin.post(
        "/users",
        json={
            "username": username,
            "email": f"{username}@test.local",
            "password": "una-clave-larga",
            "role_ids": [staff_role_id(admin)],
        },
    )
    assert res.status_code == 201
    new_id = res.json()["id"]
    make_api_user.track(new_id)

    listed = next(u for u in admin.get("/users").json() if u["id"] == new_id)
    assert listed["username"] == username and listed["is_active"] is True

    res = admin.put(
        f"/users/{new_id}",
        json={"email": f"{username}@otro.local", "is_active": False, "role_ids": [staff_role_id(admin)]},
    )
    assert res.status_code == 204
    listed = next(u for u in admin.get("/users").json() if u["id"] == new_id)
    assert (listed["email"], listed["is_active"]) == (f"{username}@otro.local", False)


def test_duplicate_username_is_409_without_db_details(admin, make_api_user):
    existing = make_api_user()
    res = admin.post(
        "/users",
        json={
            "username": existing["username"].upper(),  # el índice es case-insensitive
            "email": "otro@test.local",
            "password": "una-clave-larga",
            "role_ids": [staff_role_id(admin)],
        },
    )
    assert res.status_code == 409
    assert res.json() == {"detail": "Ya existe un registro con esos datos"}


def test_unknown_user_is_404(admin):
    assert admin.post("/users/-1/unlock").status_code == 404


def test_bad_email_is_rejected_before_the_db(admin):
    res = admin.put("/users/1", json={"email": "no-es-correo", "is_active": True, "role_ids": [1]})
    assert res.status_code == 422
