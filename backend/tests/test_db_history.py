"""Historial médico en la base: lectura protegida, solo el autor corrige, nunca se borra."""

import pytest
from conftest import denied, make_cedula
from psycopg import errors


def user_with_role(db, role_name, suffix=""):
    db.execute("RESET ROLE")
    username = f"t_{role_name.lower()[:6]}{suffix}"
    (uid,) = db.execute(
        "INSERT INTO security.user (username, email, password_hash) "
        "VALUES (%s, %s || '@t.local', 'x') RETURNING id",
        (username, username),
    ).fetchone()
    db.execute(
        "INSERT INTO security.user_role (user_id, role_id) SELECT %s, id FROM security.role WHERE name = %s",
        (uid, role_name),
    )
    return uid


def as_app(db, uid):
    db.execute("SET ROLE ceragen_app")
    db.execute("SELECT set_config('app.user_id', %s, true)", (str(uid),))


def make_patient(db):
    """Preparación como superusuario: salta los guards de pantalla (no es lo que se prueba)."""
    db.execute("RESET ROLE")
    db.execute("SET LOCAL session_replication_role = replica")
    (person,) = db.execute(
        "INSERT INTO core.person (identification_type, identification, first_name, last_name) "
        "VALUES ('cedula', %s, 'Ana', 'Ruiz') RETURNING id",
        (make_cedula(777),),
    ).fetchone()
    (patient,) = db.execute(
        "INSERT INTO clinic.patient (person_id) VALUES (%s) RETURNING id", (person,)
    ).fetchone()
    db.execute("SET LOCAL session_replication_role = origin")
    return patient


def add_entry(db, patient, reason="Dolor lumbar"):
    return db.execute(
        "INSERT INTO clinic.medical_history (patient_id, reason) VALUES (%s, %s) RETURNING id",
        (patient, reason),
    ).fetchone()[0]


def test_reception_cannot_read_or_write_history(db):
    patient = make_patient(db)
    reception = user_with_role(db, "Recepción")
    as_app(db, reception)
    assert denied(db, "SELECT reason FROM clinic.medical_history")  # ni siquiera directo
    assert denied(db, "SELECT * FROM clinic.fn_patient_history(%s)", (patient,))
    assert denied(db, "INSERT INTO clinic.medical_history (patient_id, reason) VALUES (%s, 'x')", (patient,))


def test_therapist_writes_reads_and_only_author_corrects(db):
    patient = make_patient(db)
    author = user_with_role(db, "Terapeuta", "1")
    other = user_with_role(db, "Terapeuta", "2")

    as_app(db, author)
    entry = add_entry(db, patient)
    rows = db.execute("SELECT reason, author_id FROM clinic.fn_patient_history(%s)", (patient,)).fetchall()
    assert rows == [("Dolor lumbar", author)]

    as_app(db, other)
    assert denied(db, "UPDATE clinic.medical_history SET reason = 'cambio' WHERE id = %s", (entry,))
    assert denied(db, "DELETE FROM clinic.medical_history WHERE id = %s", (entry,))

    as_app(db, author)
    db.execute("UPDATE clinic.medical_history SET reason = 'Lumbalgia aguda' WHERE id = %s", (entry,))
    db.execute("RESET ROLE")
    (old,) = db.execute(
        "SELECT old_data->>'reason' FROM audit.event WHERE table_name = 'clinic.medical_history' "
        "AND row_id = %s AND operation = 'UPDATE'",
        (entry,),
    ).fetchone()
    assert old == "Dolor lumbar"  # la corrección no borra lo que decía antes


def test_future_date_is_rejected(db):
    patient = make_patient(db)
    therapist = user_with_role(db, "Terapeuta")
    as_app(db, therapist)
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute(
            "INSERT INTO clinic.medical_history (patient_id, reason, recorded_on) "
            "VALUES (%s, 'x', current_date + 1)",
            (patient,),
        )
