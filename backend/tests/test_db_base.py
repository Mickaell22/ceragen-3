"""Migración base: permisos de ceragen_app y trigger de auditoría.

Corre como superusuario dentro de UNA transacción que se revierte al final:
cambia de rol con SET ROLE y no deja nada en la base.
"""

import os

import psycopg
import pytest
from psycopg import errors


@pytest.fixture
def db():
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"]) as conn:
        yield conn
        conn.rollback()


def denied(conn, query):
    """True si la consulta falla por falta de permisos (en un savepoint, para seguir usando la conexión)."""
    try:
        with conn.transaction():
            conn.execute(query)
    except errors.InsufficientPrivilege:
        return True
    return False


def test_app_cannot_touch_audit_or_ddl(db):
    db.execute("SET ROLE ceragen_app")
    assert denied(db, "SELECT * FROM audit.event")
    assert denied(db, "INSERT INTO audit.event (table_name, operation) VALUES ('x', 'INSERT')")
    assert denied(db, "CREATE TABLE core.intruder (id int)")
    assert denied(db, "CREATE TABLE public.intruder (id int)")
    assert denied(db, "SELECT audit.fn_enable('audit.event')")


def test_new_functions_are_not_public(db):
    for fn in ("audit.fn_log_change()", "audit.fn_enable(regclass)"):
        row = db.execute("SELECT has_function_privilege('ceragen_app', %s, 'EXECUTE')", (fn,)).fetchone()
        assert row == (False,), fn


def test_audit_trigger_logs_changes_with_user(db):
    db.execute("SET ROLE ceragen_owner")
    db.execute(
        "CREATE TABLE core.audit_probe (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, name text)"
    )
    db.execute("SELECT audit.fn_enable('core.audit_probe')")
    db.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON core.audit_probe TO ceragen_app")

    db.execute("SET ROLE ceragen_app")
    db.execute("SET LOCAL app.user_id = '42'")
    (row_id,) = db.execute("INSERT INTO core.audit_probe (name) VALUES ('a') RETURNING id").fetchone()
    db.execute("UPDATE core.audit_probe SET name = 'b'")
    db.execute("UPDATE core.audit_probe SET name = 'b'")  # sin cambios: no se audita
    db.execute("DELETE FROM core.audit_probe")

    db.execute("RESET ROLE")
    events = db.execute(
        "SELECT operation, row_id, user_id, old_data->>'name', new_data->>'name' "
        "FROM audit.event WHERE table_name = 'core.audit_probe' ORDER BY id"
    ).fetchall()
    assert events == [
        ("INSERT", row_id, 42, None, "a"),
        ("UPDATE", row_id, 42, "a", "b"),
        ("DELETE", row_id, 42, "b", None),
    ]
