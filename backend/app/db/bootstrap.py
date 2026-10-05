"""Crea los roles de la base y deja a ceragen_owner como dueño. Idempotente.

Es lo único que corre con el superusuario: los roles son objetos del cluster
y Alembic (que corre como ceragen_owner) no puede crearlos. Si el rol ya
existe, se le resincroniza la contraseña con la del entorno (sirve para rotarla).
"""

import os
import sys

import psycopg
from psycopg import sql

OWNER, APP = "ceragen_owner", "ceragen_app"


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"bootstrap: falta la variable {name}")
    return value


def main() -> None:
    passwords = {OWNER: env("DB_OWNER_PASSWORD"), APP: env("DB_APP_PASSWORD")}

    with psycopg.connect(env("DATABASE_ADMIN_URL"), autocommit=True) as conn:
        db = sql.Identifier(conn.info.dbname)
        for role, password in passwords.items():
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = sql.SQL("ALTER" if exists else "CREATE")
            conn.execute(
                sql.SQL("{} ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                    verb, sql.Identifier(role), sql.Literal(password)
                )
            )
        # Dueño de la base = dueño del schema public (pg_database_owner) y puede
        # crear schemas y extensiones confiables (pgcrypto, btree_gist).
        conn.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(db, sql.Identifier(OWNER)))
        # Nadie más se conecta salvo los roles del sistema y los superusuarios.
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(db))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(db, sql.Identifier(APP)))

    print("bootstrap: roles listos")


if __name__ == "__main__":
    main()
