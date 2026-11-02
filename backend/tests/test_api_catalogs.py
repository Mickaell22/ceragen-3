"""Endpoints genéricos de catálogos: metadatos, lectura para todos, escritura solo admin."""

import os
import uuid

import psycopg
import pytest
from conftest import API_PASSWORD
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

ORIGIN = {"Origin": settings.cors_origin_list[0]}


def logged_in(user):
    client = TestClient(app, headers=ORIGIN)
    res = client.post("/auth/login", json={"username": user["username"], "password": API_PASSWORD})
    assert res.is_success
    return client


@pytest.fixture
def names(make_api_user):
    """Prefijo único para lo que creen los tests. Se borra antes que los usuarios
    (por depender de make_api_user), que figuran como created_by."""
    prefix = f"t_{uuid.uuid4().hex[:8]}"
    yield prefix
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
        # Limpieza de mantenimiento: salta los triggers (admin_only, auditoría) de esta conexión.
        conn.execute("SET session_replication_role = replica")
        for tbl in ("billing.tax", "core.gender"):
            ids = [r[0] for r in conn.execute(f"SELECT id FROM {tbl} WHERE name LIKE %s", (prefix + "%",))]  # noqa: S608
            conn.execute(f"DELETE FROM {tbl} WHERE id = ANY(%s)", (ids,))  # noqa: S608
            conn.execute("DELETE FROM audit.event WHERE table_name = %s AND row_id = ANY(%s)", (tbl, ids))


@pytest.fixture
def admin(make_api_user):
    return logged_in(make_api_user(admin=True))


@pytest.fixture
def staff(make_api_user):
    return logged_in(make_api_user())


def test_metadata_describes_every_catalog(staff):
    meta = {c["key"]: c for c in staff.get("/catalogs").json()}
    assert {"genders", "marital-statuses", "therapy-types", "taxes", "payment-methods"} <= meta.keys()
    assert [f["type"] for f in meta["taxes"]["fields"]] == ["text", "percent"]


def test_staff_can_read_but_not_write(staff, names):
    assert staff.get("/catalogs/taxes").status_code == 200
    res = staff.post("/catalogs/taxes", json={"name": names, "percentage": 5})
    assert res.status_code == 403


def test_admin_creates_updates_and_deactivates(admin, names):
    res = admin.post("/catalogs/taxes", json={"name": f"{names} IVA", "percentage": "12.50"})
    assert res.status_code == 201
    tax_id = res.json()["id"]

    res = admin.put(
        f"/catalogs/taxes/{tax_id}", json={"name": f"{names} IVA", "percentage": 8, "is_active": False}
    )
    assert res.status_code == 204
    item = next(t for t in admin.get("/catalogs/taxes").json() if t["id"] == tax_id)
    assert item["is_active"] is False and float(item["percentage"]) == 8


def test_duplicate_is_409_and_invalid_percent_is_422(admin, names):
    assert admin.post("/catalogs/genders", json={"name": names}).status_code == 201
    res = admin.post("/catalogs/genders", json={"name": names.upper()})
    assert res.status_code == 409
    assert admin.post("/catalogs/taxes", json={"name": names, "percentage": 150}).status_code == 422


def test_update_missing_item_is_404(admin):
    res = admin.put("/catalogs/genders/999999999", json={"name": "x", "is_active": True})
    assert res.status_code == 404
