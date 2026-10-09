"""Crea el usuario administrador de la demo si no existe. Idempotente.

Corre como ceragen_owner, el único autorizado a crear usuarios sin ser admin
(ver security.fn_create_user). Si el usuario ya existe no toca su contraseña.
"""

import psycopg

from app.db.bootstrap import env


def main() -> None:
    username = env("SEED_ADMIN_USERNAME")
    with psycopg.connect(env("DATABASE_OWNER_URL")) as conn:
        exists = conn.execute(
            "SELECT 1 FROM security.user WHERE lower(username) = lower(%s)", (username,)
        ).fetchone()
        if exists:
            print(f"seed: el usuario {username} ya existe")
            return
        conn.execute(
            "SELECT security.fn_create_user(%s, %s, %s, ARRAY(SELECT id FROM security.role WHERE is_admin))",
            (username, env("SEED_ADMIN_EMAIL"), env("SEED_ADMIN_PASSWORD")),
        )
    print(f"seed: usuario {username} creado")


if __name__ == "__main__":
    main()
