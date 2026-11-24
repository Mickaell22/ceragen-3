"""Personas y pacientes en la base: validación de cédula, permisos por pantalla, unicidad."""

import pytest
from conftest import denied, make_cedula
from psycopg import errors


def user_with_role(db, role_name):
    db.execute("RESET ROLE")
    (uid,) = db.execute(
        "INSERT INTO security.user (username, email, password_hash) "
        "VALUES (%s, %s || '@t.local', 'x') RETURNING id",
        (f"t_{role_name.lower()[:6]}", f"t_{role_name.lower()[:6]}"),
    ).fetchone()
    db.execute(
        "INSERT INTO security.user_role (user_id, role_id) SELECT %s, id FROM security.role WHERE name = %s",
        (uid, role_name),
    )
    return uid


def as_app(db, uid):
    db.execute("SET ROLE ceragen_app")
    db.execute("SELECT set_config('app.user_id', %s, true)", (str(uid),))


def valid(db, cedula):
    return db.execute("SELECT core.fn_is_valid_cedula(%s)", (cedula,)).fetchone()[0]


def test_cedula_validation_matches_an_independent_implementation(db):
    for seed in range(0, 3000, 37):
        cedula = make_cedula(seed)
        assert valid(db, cedula), cedula
        wrong = cedula[:9] + str((int(cedula[9]) + 1) % 10)  # dígito verificador cambiado
        assert not valid(db, wrong), wrong
    ok = make_cedula(7)
    for bad in (
        "00" + ok[2:],  # provincia 00
        "25" + ok[2:],  # provincia 25
        ok[:2] + "6" + ok[3:],  # tercer dígito 6 (no es persona natural)
        ok[:9],  # 9 dígitos
        ok + "1",  # 11 dígitos
        ok[:4] + "a" + ok[5:],  # letra
    ):
        assert not valid(db, bad), bad
    assert valid(db, make_cedula(5, province=30))  # ecuatorianos registrados en el exterior


def insert_person(db, identification_type, identification):
    return db.execute(
        "INSERT INTO core.person (identification_type, identification, first_name, last_name) "
        "VALUES (%s, %s, 'Ana', 'Pérez') RETURNING id",
        (identification_type, identification),
    ).fetchone()[0]


def test_identification_check_and_uniqueness(db):
    uid = user_with_role(db, "Recepción")
    as_app(db, uid)
    cedula = make_cedula(101)
    insert_person(db, "cedula", cedula)
    insert_person(db, "ruc", cedula + "001")  # mismo número como RUC: otra identificación
    insert_person(db, "passport", "AB12345")
    for kind, value in (
        ("cedula", cedula[:9] + "0" if cedula[9] != "0" else cedula[:9] + "1"),
        ("ruc", cedula + "002"),
        ("passport", "ab-12"),
    ):
        with pytest.raises(errors.CheckViolation), db.transaction():
            insert_person(db, kind, value)
    with pytest.raises(errors.UniqueViolation), db.transaction():
        insert_person(db, "cedula", cedula)


def test_screen_permission_decides_who_writes(db):
    reception = user_with_role(db, "Recepción")
    as_app(db, reception)
    person = insert_person(db, "cedula", make_cedula(202))
    (patient,) = db.execute(
        "INSERT INTO clinic.patient (person_id, blood_type) VALUES (%s, 'O+') RETURNING id", (person,)
    ).fetchone()
    (allergy,) = db.execute("SELECT id FROM clinic.allergy ORDER BY id LIMIT 1").fetchone()
    db.execute(
        "INSERT INTO clinic.patient_allergy (patient_id, allergy_id) VALUES (%s, %s)", (patient, allergy)
    )

    # Un rol sin la pantalla /patients lee pero no escribe.
    db.execute("RESET ROLE")
    db.execute(
        "DELETE FROM security.menu_role "
        "WHERE role_id = (SELECT id FROM security.role WHERE name = 'Terapeuta')"
    )
    therapist = user_with_role(db, "Terapeuta")
    as_app(db, therapist)
    assert db.execute("SELECT count(*) FROM clinic.patient WHERE id = %s", (patient,)).fetchone() == (1,)
    assert denied(db, "UPDATE clinic.patient SET notes = 'x'")
    assert denied(
        db,
        "INSERT INTO core.person (identification_type, identification, first_name, last_name) "
        "VALUES ('passport', 'ZZ99999', 'a', 'b')",
    )


def test_one_patient_per_person_and_valid_blood_type(db):
    uid = user_with_role(db, "Recepción")
    as_app(db, uid)
    person = insert_person(db, "cedula", make_cedula(303))
    db.execute("INSERT INTO clinic.patient (person_id) VALUES (%s)", (person,))
    with pytest.raises(errors.UniqueViolation), db.transaction():
        db.execute("INSERT INTO clinic.patient (person_id) VALUES (%s)", (person,))
    other = insert_person(db, "cedula", make_cedula(304))
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute("INSERT INTO clinic.patient (person_id, blood_type) VALUES (%s, 'Z+')", (other,))
