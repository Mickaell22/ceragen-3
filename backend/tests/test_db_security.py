"""Módulo security: login con bcrypt, bloqueo temporal, sesiones y permisos."""

import pytest
from conftest import denied
from psycopg import errors

PASSWORD = "correcta-123"


def make_user(db, username, *, admin=False, active=True):
    """Crea un usuario directo como superusuario (bcrypt de costo 4 para que el test sea rápido)."""
    db.execute("RESET ROLE")
    (uid,) = db.execute(
        "INSERT INTO security.user (username, email, password_hash, is_active) "
        "VALUES (%s, %s || '@test.local', public.crypt(%s, public.gen_salt('bf', 4)), %s) RETURNING id",
        (username, username, PASSWORD, active),
    ).fetchone()
    db.execute(
        "INSERT INTO security.user_role (user_id, role_id) "
        "SELECT %s, id FROM security.role WHERE is_admin = %s LIMIT 1",
        (uid, admin),
    )
    return uid


def as_app(db, user_id=None):
    db.execute("SET ROLE ceragen_app")
    db.execute("SELECT set_config('app.user_id', %s, true)", ("" if user_id is None else str(user_id),))


def login(db, username, password, max_attempts=3, lock_minutes=15):
    as_app(db)
    return db.execute(
        "SELECT status, user_id, jti, locked_until, roles "
        "FROM security.fn_login(%s, %s, '10.0.0.1', 60, %s, %s)",
        (username, password, max_attempts, lock_minutes),
    ).fetchone()


def attempts(db, uid):
    db.execute("RESET ROLE")
    return db.execute("SELECT login_attempts FROM security.user WHERE id = %s", (uid,)).fetchone()[0]


def test_app_has_no_direct_access_to_security_tables(db):
    as_app(db)
    for query in (
        "SELECT password_hash FROM security.user",
        "SELECT * FROM security.session",
        "UPDATE security.user SET is_active = true",
        "INSERT INTO security.user_role (user_id, role_id) VALUES (1, 1)",
    ):
        assert denied(db, query), query


def test_login_ok_opens_session_and_logout_revokes_it(db):
    uid = make_user(db, "ana", admin=True)
    status, user_id, jti, _, roles = login(db, "ANA", PASSWORD)  # usuario sin distinguir mayúsculas
    assert (status, user_id) == ("ok", uid)
    assert roles[0]["is_admin"] is True

    assert db.execute("SELECT security.fn_session_user(%s)", (jti,)).fetchone() == (uid,)
    db.execute("SELECT security.fn_logout(%s)", (jti,))
    assert db.execute("SELECT security.fn_session_user(%s)", (jti,)).fetchone() == (None,)


def test_failed_attempts_lock_the_account_temporarily(db):
    uid = make_user(db, "beto")
    assert login(db, "beto", "mala")[0] == "invalid"
    assert attempts(db, uid) == 1
    assert login(db, "beto", "mala")[0] == "invalid"
    status, _, _, locked_until, _ = login(db, "beto", "mala")  # tercer fallo: bloquea
    assert status == "locked" and locked_until is not None

    # Bloqueada, ni la contraseña correcta entra.
    assert login(db, "beto", PASSWORD)[0] == "locked"

    # Vencido el bloqueo, vuelve a entrar y el contador queda en cero.
    db.execute("RESET ROLE")
    db.execute("UPDATE security.user SET locked_until = now() - interval '1 second' WHERE id = %s", (uid,))
    assert login(db, "beto", PASSWORD)[0] == "ok"
    assert attempts(db, uid) == 0


def test_unknown_or_inactive_user_is_just_invalid(db):
    make_user(db, "inactivo", active=False)
    assert login(db, "nadie", PASSWORD)[:3] == ("invalid", None, None)
    assert login(db, "inactivo", PASSWORD)[:3] == ("invalid", None, None)


def test_create_user_hashes_with_bcrypt_and_never_audits_the_hash(db):
    admin = make_user(db, "admin_test", admin=True)
    (role_ids,) = db.execute("SELECT array_agg(id) FROM security.role WHERE NOT is_admin").fetchone()
    as_app(db, admin)
    (new_id,) = db.execute(
        "SELECT security.fn_create_user('carla', 'carla@test.local', %s, %s)", (PASSWORD, role_ids)
    ).fetchone()

    db.execute("RESET ROLE")
    hash_, created_by = db.execute(
        "SELECT password_hash, created_by FROM security.user WHERE id = %s", (new_id,)
    ).fetchone()
    assert hash_.startswith("$2") and PASSWORD not in hash_
    assert created_by == admin  # sale de app.user_id, la API no lo manda

    leaked = db.execute(
        "SELECT count(*) FROM audit.event WHERE table_name = 'security.user' "
        "AND (old_data ? 'password_hash' OR new_data ? 'password_hash')"
    ).fetchone()
    assert leaked == (0,)


def test_only_admins_create_users_and_password_policy_applies(db):
    common = make_user(db, "comun")
    as_app(db, common)
    assert denied(db, "SELECT security.fn_create_user('x1', 'x1@test.local', %s, '{}')", (PASSWORD,))

    admin = make_user(db, "admin_test", admin=True)
    as_app(db, admin)
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute("SELECT security.fn_create_user('x2', 'x2@test.local', 'corta', '{}')")


def test_change_password_requires_current_and_closes_sessions(db):
    uid = make_user(db, "dani")
    jti = login(db, "dani", PASSWORD)[2]

    as_app(db, uid)
    assert db.execute("SELECT security.fn_change_password('mala', 'nueva-clave-1')").fetchone() == (False,)
    assert db.execute("SELECT security.fn_change_password(%s, 'nueva-clave-1')", (PASSWORD,)).fetchone() == (
        True,
    )
    assert db.execute("SELECT security.fn_session_user(%s)", (jti,)).fetchone() == (None,)
    assert login(db, "dani", "nueva-clave-1")[0] == "ok"
