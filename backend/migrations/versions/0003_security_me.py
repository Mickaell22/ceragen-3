"""security.fn_me(): perfil del usuario de la transacción, para GET /auth/me.

Sin parámetros a propósito: solo devuelve al usuario fijado en app.user_id,
así la API no puede usarla para leer datos de otros usuarios.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION security.fn_me(OUT id bigint, OUT username text, OUT email text, OUT roles jsonb)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            SELECT u.id, u.username, u.email, security.fn_user_roles(u.id)
            FROM security.user u
            WHERE u.id = core.fn_current_user_id() AND u.is_active
        $$;
        GRANT EXECUTE ON FUNCTION security.fn_me() TO ceragen_app;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION security.fn_me()")
