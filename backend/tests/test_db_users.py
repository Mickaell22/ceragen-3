"""Gestión de usuarios en la base: solo admins, roles con borrado lógico, siempre un admin activo."""

import pytest
from conftest import denied
from psycopg import errors

PASSWORD = "correcta-123"


def role(db, admin):
    query = "SELECT id FROM security.role WHERE is_admin = %s ORDER BY id LIMIT 1"
    return db.execute(query, (admin,)).fetchone()[0]


def make_user(db, username, role_ids):
    db.execute("RESET ROLE")
    (uid,) = db.execute(
        "INSERT INTO security.user (username, email, password_hash) "
        "VALUES (%s, %s || '@t.local', public.crypt(%s, public.gen_salt('bf', 4))) RETURNING id",
        (username, username, PASSWORD),
    ).fetchone()
    for rid in role_ids:
        db.execute("INSERT INTO security.user_role (user_id, role_id) VALUES (%s, %s)", (uid, rid))
    return uid


def as_app(db, uid):
    db.execute("SET ROLE ceragen_app")
    db.execute("SELECT set_config('app.user_id', %s, true)", (str(uid),))


def test_non_admin_cannot_use_admin_functions(db):
    worker = make_user(db, "t_worker", [role(db, False)])
    as_app(db, worker)
    for query in (
        "SELECT * FROM security.fn_list_users()",
        "SELECT * FROM security.fn_list_roles()",
        "SELECT security.fn_unlock_user(1)",
        "SELECT security.fn_reset_password(1, 'otra-clave-1')",
        "SELECT security.fn_update_user(1, 'x@y.z', true, '{1}')",
    ):
        assert denied(db, query), query


def test_update_roles_is_soft_and_deactivation_closes_sessions(db):
    admin_role, staff_role = role(db, True), role(db, False)
    admin = make_user(db, "t_admin", [admin_role])
    worker = make_user(db, "t_worker", [staff_role])
    db.execute(
        "INSERT INTO security.session (user_id, expires_at) VALUES (%s, now() + interval '1 hour')", (worker,)
    )

    as_app(db, admin)
    db.execute("SELECT security.fn_update_user(%s, 'nuevo@t.local', false, %s)", (worker, [admin_role]))

    db.execute("RESET ROLE")
    rows = db.execute(
        "SELECT role_id, is_active, deleted_by FROM security.user_role WHERE user_id = %s ORDER BY role_id",
        (worker,),
    ).fetchall()
    assert rows == [(admin_role, True, None), (staff_role, False, admin)]  # el rol viejo queda, inactivo
    email, active = db.execute(
        "SELECT email, is_active FROM security.user WHERE id = %s", (worker,)
    ).fetchone()
    assert (email, active) == ("nuevo@t.local", False)
    open_sessions = db.execute(
        "SELECT count(*) FROM security.session WHERE user_id = %s AND revoked_at IS NULL", (worker,)
    ).fetchone()
    assert open_sessions == (0,)

    # Reactivar con el rol original lo vuelve a activar (sin duplicar la fila).
    as_app(db, admin)
    db.execute("SELECT security.fn_update_user(%s, 'nuevo@t.local', true, %s)", (worker, [staff_role]))
    db.execute("RESET ROLE")
    active_roles = db.execute(
        "SELECT role_id FROM security.user_role WHERE user_id = %s AND is_active", (worker,)
    ).fetchall()
    assert active_roles == [(staff_role,)]


def test_there_is_always_an_active_admin(db):
    admin_role, staff_role = role(db, True), role(db, False)
    admin = make_user(db, "t_admin", [admin_role])
    # Deja a t_admin como único admin activo (la transacción se revierte al final).
    db.execute("UPDATE security.user SET is_active = false WHERE id <> %s", (admin,))

    as_app(db, admin)
    with pytest.raises(errors.CheckViolation), db.transaction():  # desactivarse
        db.execute("SELECT security.fn_update_user(%s, 'a@t.local', false, %s)", (admin, [admin_role]))
    with pytest.raises(errors.CheckViolation), db.transaction():  # quitarse el rol admin
        db.execute("SELECT security.fn_update_user(%s, 'a@t.local', true, %s)", (admin, [staff_role]))


def test_reset_password_unlocks_and_closes_sessions(db):
    admin = make_user(db, "t_admin", [role(db, True)])
    worker = make_user(db, "t_worker", [role(db, False)])
    db.execute(
        "UPDATE security.user SET login_attempts = 3, locked_until = now() + interval '1 hour' WHERE id = %s",
        (worker,),
    )
    db.execute(
        "INSERT INTO security.session (user_id, expires_at) VALUES (%s, now() + interval '1 hour')", (worker,)
    )

    as_app(db, admin)
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute("SELECT security.fn_reset_password(%s, 'corta')", (worker,))
    db.execute("SELECT security.fn_reset_password(%s, 'nueva-clave-1')", (worker,))
    status = db.execute(
        "SELECT status FROM security.fn_login('t_worker', 'nueva-clave-1', NULL, 60, 5, 15)"
    ).fetchone()
    assert status == ("ok",)  # desbloqueada y con la clave nueva

    db.execute("RESET ROLE")
    revoked = db.execute(
        "SELECT count(*) FROM security.session WHERE user_id = %s AND revoked_at IS NOT NULL", (worker,)
    ).fetchone()
    assert revoked == (1,)  # la sesión anterior se cerró (la del login de arriba sigue abierta)


def test_missing_user_is_reported(db):
    admin = make_user(db, "t_admin", [role(db, True)])
    as_app(db, admin)
    with pytest.raises(errors.NoDataFound), db.transaction():
        db.execute("SELECT security.fn_unlock_user(-1)")
