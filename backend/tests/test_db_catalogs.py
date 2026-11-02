"""Catálogos en la base: solo admin escribe, nunca se borra, nombre único y borrado lógico con rastro."""

import pytest
from conftest import denied
from psycopg import errors


def user_with_role(db, admin):
    db.execute("RESET ROLE")
    (uid,) = db.execute(
        "INSERT INTO security.user (username, email, password_hash) "
        "VALUES (%s, %s || '@t.local', 'x') RETURNING id",
        (f"t_admin_{admin}", f"t_admin_{admin}"),
    ).fetchone()
    db.execute(
        "INSERT INTO security.user_role (user_id, role_id) "
        "SELECT %s, id FROM security.role WHERE is_admin = %s ORDER BY id LIMIT 1",
        (uid, admin),
    )
    return uid


def as_app(db, uid):
    db.execute("SET ROLE ceragen_app")
    db.execute("SELECT set_config('app.user_id', %s, true)", (str(uid),))


def test_staff_reads_but_cannot_write(db):
    staff = user_with_role(db, admin=False)
    as_app(db, staff)
    assert db.execute("SELECT count(*) FROM billing.tax").fetchone()[0] >= 1
    assert denied(db, "INSERT INTO billing.tax (name, percentage) VALUES ('t_x', 5)")
    assert denied(db, "UPDATE billing.tax SET percentage = 1")


def test_admin_writes_and_soft_delete_leaves_a_trace(db):
    admin = user_with_role(db, admin=True)
    as_app(db, admin)
    (tid,) = db.execute(
        "INSERT INTO billing.tax (name, percentage) VALUES ('t_iva', 5) RETURNING id"
    ).fetchone()
    db.execute("UPDATE billing.tax SET is_active = false WHERE id = %s", (tid,))
    assert denied(db, "DELETE FROM billing.tax WHERE name = 't_iva'")  # sin DELETE ni para admins

    db.execute("RESET ROLE")
    row = db.execute(
        "SELECT created_by, deleted_by, deleted_at IS NOT NULL FROM billing.tax WHERE id = %s", (tid,)
    ).fetchone()
    assert row == (admin, admin, True)

    as_app(db, admin)
    db.execute("UPDATE billing.tax SET is_active = true WHERE id = %s", (tid,))
    db.execute("RESET ROLE")
    assert db.execute("SELECT deleted_by, deleted_at FROM billing.tax WHERE id = %s", (tid,)).fetchone() == (
        None,
        None,
    )


def test_name_is_unique_ignoring_case_and_spaces(db):
    admin = user_with_role(db, admin=True)
    as_app(db, admin)
    with pytest.raises(errors.UniqueViolation), db.transaction():
        db.execute("INSERT INTO core.gender (name) VALUES ('  masculino ')")


def test_checks_reject_bad_values(db):
    admin = user_with_role(db, admin=True)
    as_app(db, admin)
    for query in (
        "INSERT INTO billing.tax (name, percentage) VALUES ('t_mal', 101)",
        "INSERT INTO core.gender (name) VALUES ('   ')",
    ):
        with pytest.raises(errors.CheckViolation), db.transaction():
            db.execute(query)
