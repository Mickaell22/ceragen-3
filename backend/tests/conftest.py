"""Fixtures comunes. Cada test corre como superusuario dentro de UNA
transacción que se revierte al final: cambia de rol con SET ROLE y no deja
nada en la base."""

import os

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
