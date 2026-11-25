"""Historial médico por la API: el terapeuta escribe y lee, recepción recibe 403."""

import os

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


def with_role(make_api_user, role):
    user = make_api_user()
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
        conn.execute(
            "UPDATE security.user_role SET role_id = (SELECT id FROM security.role WHERE name = %s) "
            "WHERE user_id = %s",
            (role, user["id"]),
        )
    return user


@pytest.fixture
def patient(make_api_user):
    """Paciente creado directo en la base; se borra con su historial antes que los usuarios."""
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:
        conn.execute("SET session_replication_role = replica")  # preparación: sin guards de pantalla
        (person,) = conn.execute(
            "INSERT INTO core.person (identification_type, identification, first_name, last_name) "
            "VALUES ('cedula', %s, 'Ana', 'Ruiz') RETURNING id",
            (make_cedula(os.getpid() % 900_000 + 1000),),
        ).fetchone()
        (pid,) = conn.execute(
            "INSERT INTO clinic.patient (person_id) VALUES (%s) RETURNING id", (person,)
        ).fetchone()
        yield pid
        entries = [
            r[0] for r in conn.execute("SELECT id FROM clinic.medical_history WHERE patient_id = %s", (pid,))
        ]
        conn.execute("DELETE FROM clinic.medical_history WHERE patient_id = %s", (pid,))
        conn.execute("DELETE FROM clinic.patient WHERE id = %s", (pid,))
        conn.execute("DELETE FROM core.person WHERE id = %s", (person,))
        conn.execute(
            "DELETE FROM audit.event WHERE (table_name = 'clinic.medical_history' AND row_id = ANY(%s)) "
            "OR (table_name = 'clinic.patient' AND row_id = %s) "
            "OR (table_name = 'core.person' AND row_id = %s)",
            (entries, pid, person),
        )


def test_therapist_flow_and_reception_forbidden(make_api_user, patient):
    therapist = logged_in(with_role(make_api_user, "Terapeuta"))
    res = therapist.post(
        f"/patients/{patient}/history", json={"reason": "Evaluación inicial", "diagnosis": "Lumbalgia"}
    )
    assert res.status_code == 201, res.text
    entry = res.json()["id"]

    history = therapist.get(f"/patients/{patient}/history").json()
    assert [(h["id"], h["reason"], h["diagnosis"]) for h in history] == [
        (entry, "Evaluación inicial", "Lumbalgia")
    ]

    res = therapist.put(
        f"/history/{entry}",
        json={"recorded_on": history[0]["recorded_on"], "reason": "Evaluación inicial", "is_active": False},
    )
    assert res.status_code == 204
    assert therapist.get(f"/patients/{patient}/history").json()[0]["is_active"] is False

    reception = logged_in(with_role(make_api_user, "Recepción"))
    res = reception.get(f"/patients/{patient}/history")
    assert res.status_code == 403
    assert res.json() == {"detail": "no tienes permiso para ver el historial médico"}


def test_other_therapist_cannot_correct_and_future_date_is_422(make_api_user, patient):
    author = logged_in(with_role(make_api_user, "Terapeuta"))
    entry = author.post(f"/patients/{patient}/history", json={"reason": "Control"}).json()["id"]
    other = logged_in(with_role(make_api_user, "Terapeuta"))
    res = other.put(f"/history/{entry}", json={"recorded_on": "2026-01-01", "reason": "cambio"})
    assert res.status_code == 403
    assert res.json() == {"detail": "solo el autor puede corregir esta entrada"}

    res = author.post(f"/patients/{patient}/history", json={"reason": "x", "recorded_on": "2999-01-01"})
    assert res.status_code == 422
    assert res.json() == {"detail": "La fecha no puede ser futura"}
