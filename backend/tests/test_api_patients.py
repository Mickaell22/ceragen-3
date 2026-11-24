"""Pacientes y clientes por la API: alta, edición, relaciones, permisos y mensajes de error."""

import os
import uuid

import psycopg
import pytest
from conftest import API_PASSWORD, make_cedula
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
def seed():
    """Número base aleatorio para cédulas únicas por test."""
    return uuid.uuid4().int % 900_000 + 50_000


@pytest.fixture
def cleanup(make_api_user):
    """Borra personas, clientes y pacientes creados en el test. Corre antes que el borrado
    de los usuarios (dependen de make_api_user), que figuran como created_by."""
    created_by: list[int] = []
    yield created_by
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
        conn.execute("SET session_replication_role = replica")
        persons = [
            r[0] for r in conn.execute("SELECT id FROM core.person WHERE created_by = ANY(%s)", (created_by,))
        ]
        patients = [
            r[0] for r in conn.execute("SELECT id FROM clinic.patient WHERE person_id = ANY(%s)", (persons,))
        ]
        for table in ("clinic.patient_allergy", "clinic.patient_disease"):
            conn.execute(f"DELETE FROM {table} WHERE patient_id = ANY(%s)", (patients,))  # noqa: S608
        conn.execute("DELETE FROM clinic.patient WHERE id = ANY(%s)", (patients,))
        conn.execute("DELETE FROM core.client WHERE person_id = ANY(%s)", (persons,))
        conn.execute("DELETE FROM core.person WHERE id = ANY(%s)", (persons,))
        conn.execute(
            "DELETE FROM audit.event WHERE table_name IN ('core.person', 'core.client', 'clinic.patient', "
            "'clinic.patient_allergy', 'clinic.patient_disease') AND user_id = ANY(%s)",
            (created_by,),
        )


@pytest.fixture
def reception(make_api_user, cleanup):
    user = make_api_user()  # rol Recepción (primer rol no admin): tiene la pantalla /patients
    cleanup.append(user["id"])
    return logged_in(user)


def person(cedula, **extra):
    return {
        "identification_type": "cedula",
        "identification": cedula,
        "first_name": "Lucía",
        "last_name": "Zambrano",
        **extra,
    }


def ids_of(client, key):
    return [row["id"] for row in client.get(f"/catalogs/{key}").json()][:2]


def test_create_read_update_patient_with_links(reception, seed):
    allergies, diseases = ids_of(reception, "allergies"), ids_of(reception, "diseases")
    res = reception.post(
        "/patients",
        json={
            "person": person(make_cedula(seed), phone="0991234567"),
            "blood_type": "O+",
            "allergy_ids": allergies,
            "disease_ids": diseases[:1],
        },
    )
    assert res.status_code == 201, res.text
    pid = res.json()["id"]

    got = reception.get(f"/patients/{pid}").json()
    assert got["person"]["first_name"] == "Lucía" and got["blood_type"] == "O+"
    assert got["allergy_ids"] == sorted(allergies) and got["disease_ids"] == diseases[:1]

    # Quita una alergia, cambia la enfermedad y el teléfono.
    res = reception.put(
        f"/patients/{pid}",
        json={
            "person": person(make_cedula(seed), phone="0987654321"),
            "blood_type": "A-",
            "allergy_ids": allergies[:1],
            "disease_ids": diseases[1:2],
        },
    )
    assert res.status_code == 204, res.text
    got = reception.get(f"/patients/{pid}").json()
    assert got["allergy_ids"] == allergies[:1] and got["disease_ids"] == diseases[1:2]
    assert got["person"]["phone"] == "0987654321"

    rows = reception.get("/patients", params={"q": make_cedula(seed)}).json()
    assert [r["id"] for r in rows] == [pid] and rows[0]["full_name"] == "Zambrano Lucía"


def test_client_pays_for_patient_and_person_is_reused(reception, seed):
    parent = person(make_cedula(seed + 1), first_name="Mario")
    client_id = reception.post("/clients", json={"person": parent}).json()["id"]
    res = reception.post("/patients", json={"person": person(make_cedula(seed + 2)), "client_id": client_id})
    assert res.status_code == 201
    row = reception.get("/patients", params={"q": make_cedula(seed + 2)}).json()[0]
    assert row["client_name"] == "Zambrano Mario"
    detail = reception.get(f"/patients/{row['id']}").json()
    assert detail["client"] == {
        "id": client_id,
        "full_name": "Zambrano Mario",
        "identification": make_cedula(seed + 1),
        "is_active": True,
    }

    # El padre también se vuelve paciente: misma persona, no se duplica.
    res = reception.post("/patients", json={"person": parent})
    assert res.status_code == 201
    assert reception.post("/patients", json={"person": parent}).json() == {
        "detail": "Esa persona ya está registrada como paciente"
    }


def test_invalid_cedula_has_a_friendly_message(reception, seed):
    good = make_cedula(seed)
    bad = good[:9] + str((int(good[9]) + 1) % 10)
    res = reception.post("/patients", json={"person": person(bad)})
    assert res.status_code == 422
    assert res.json() == {"detail": "La identificación no es válida"}


def test_role_without_the_screen_gets_403(make_api_user, cleanup, seed):
    # Rol sin menú /patients: se crea uno sin pantallas asignadas.
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
        conn.execute("SET session_replication_role = replica")
        (role_id,) = conn.execute(
            "INSERT INTO security.role (name) VALUES (%s) RETURNING id", (f"t_rol_{seed}",)
        ).fetchone()
        user = make_api_user()
        conn.execute("UPDATE security.user_role SET role_id = %s WHERE user_id = %s", (role_id, user["id"]))
    try:
        client = logged_in(user)
        assert client.get("/patients").status_code == 200  # leer, sí
        res = client.post("/patients", json={"person": person(make_cedula(seed))})
        assert res.status_code == 403
        assert res.json() == {"detail": "no tienes permiso para modificar estos datos"}
    finally:
        with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
            conn.execute("SET session_replication_role = replica")
            conn.execute("DELETE FROM security.user_role WHERE role_id = %s", (role_id,))
            conn.execute("DELETE FROM security.role WHERE id = %s", (role_id,))
            conn.execute(
                "DELETE FROM audit.event WHERE table_name = 'security.role' AND row_id = %s", (role_id,)
            )
