"""Fixtures comunes. Cada test corre como superusuario dentro de UNA
transacción que se revierte al final: cambia de rol con SET ROLE y no deja
nada en la base."""

import os
import uuid

import psycopg
import pytest
from psycopg import errors


@pytest.fixture
def db():
    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"]) as conn:
        yield conn
        conn.rollback()


def denied(conn, query, params=None):
    """True si la consulta falla por falta de permisos (en un savepoint, para seguir usando la conexión)."""
    try:
        with conn.transaction():
            conn.execute(query, params)
    except errors.InsufficientPrivilege:
        return True
    return False


API_PASSWORD = "clave-de-test-1"


@pytest.fixture
def make_api_user():
    """Fábrica de usuarios reales (commiteados) para los tests de la API.

    make_api_user(admin=False) -> {"id", "username"}. track(id) registra usuarios
    creados por la propia API. Al final se borran todos, con sesiones y auditoría.
    """
    created: list[int] = []

    with psycopg.connect(os.environ["DATABASE_ADMIN_URL"], autocommit=True) as conn:

        def make(admin=False):
            username = f"t_{uuid.uuid4().hex[:10]}"
            (uid,) = conn.execute(
                "INSERT INTO security.user (username, email, password_hash) "
                "VALUES (%s, %s || '@test.local', public.crypt(%s, public.gen_salt('bf', 4))) RETURNING id",
                (username, username, API_PASSWORD),
            ).fetchone()
            conn.execute(
                "INSERT INTO security.user_role (user_id, role_id) "
                "SELECT %s, id FROM security.role WHERE is_admin = %s ORDER BY id LIMIT 1",
                (uid, admin),
            )
            created.append(uid)
            return {"id": uid, "username": username}

        make.track = created.append
        yield make

        # Al revés: un usuario creado por la API tiene created_by apuntando al admin que lo creó.
        for uid in reversed(created):
            conn.execute("DELETE FROM security.session WHERE user_id = %s", (uid,))
            conn.execute(
                "DELETE FROM audit.event WHERE table_name = 'security.user_role' "
                "AND (new_data->>'user_id')::bigint = %s",
                (uid,),
            )
            conn.execute("DELETE FROM security.user_role WHERE user_id = %s", (uid,))
            conn.execute("DELETE FROM security.user WHERE id = %s", (uid,))
            conn.execute("DELETE FROM audit.event WHERE table_name = 'security.user' AND row_id = %s", (uid,))
