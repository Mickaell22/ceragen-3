"""Módulos y menús por rol. El sidebar del front se arma con security.fn_my_menus().

Un módulo agrupa menús (es el subtítulo del sidebar); un menú es una pantalla.
El rol administrador ve todos los menús activos sin necesitar menu_role.
Cada pantalla nueva agrega su fila de menú en la migración que la crea.

Ocultar un menú NO es control de acceso: cada endpoint de la API valida sus
propios permisos. Esto solo decide qué se muestra.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

from migrations.conventions import AUDIT_COLUMNS, standard_triggers

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE security.module (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name        text NOT NULL,
            sort_order  integer NOT NULL DEFAULT 0,
            {AUDIT_COLUMNS}
        );
        CREATE UNIQUE INDEX module_name_key ON security.module (lower(name));

        -- ponytail: sin menús anidados (parent_id) a propósito; un nivel de
        -- módulo + pantalla alcanza para el sidebar. Si hace falta un submenú,
        -- se agrega parent_id y se arma el árbol en fn_my_menus.
        CREATE TABLE security.menu (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            module_id   bigint NOT NULL REFERENCES security.module,
            name        text NOT NULL,
            path        text NOT NULL UNIQUE CHECK (path ~ '^/[a-z0-9/-]*$'),
            -- Nombre de un ícono de Tabler (layout-dashboard, users, ...).
            icon        text NOT NULL CHECK (icon ~ '^[a-z0-9-]+$'),
            sort_order  integer NOT NULL DEFAULT 0,
            {AUDIT_COLUMNS}
        );
        CREATE INDEX ON security.menu (module_id);

        CREATE TABLE security.menu_role (
            id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            menu_id  bigint NOT NULL REFERENCES security.menu,
            role_id  bigint NOT NULL REFERENCES security.role,
            {AUDIT_COLUMNS},
            UNIQUE (menu_id, role_id)
        );
        CREATE INDEX ON security.menu_role (role_id);

        {standard_triggers("security.module")}
        {standard_triggers("security.menu")}
        {standard_triggers("security.menu_role")}

        -- Menús del usuario de la transacción, agrupados por módulo y ordenados.
        -- Sin parámetros, igual que fn_me: la API no puede pedir los de otro usuario.
        CREATE FUNCTION security.fn_my_menus() RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            WITH me AS (
                SELECT core.fn_current_user_id() AS uid
            ),
            my_roles AS (
                SELECT r.id, r.is_admin
                FROM me
                JOIN security.user u ON u.id = me.uid AND u.is_active
                JOIN security.user_role ur ON ur.user_id = u.id AND ur.is_active
                JOIN security.role r ON r.id = ur.role_id AND r.is_active
            ),
            visible AS (
                SELECT mo.id AS module_id, mo.name AS module, mo.sort_order AS module_order,
                       m.name, m.path, m.icon, m.sort_order, m.id
                FROM security.menu m
                JOIN security.module mo ON mo.id = m.module_id AND mo.is_active
                WHERE m.is_active AND (
                    EXISTS (SELECT 1 FROM my_roles WHERE is_admin)
                    OR EXISTS (
                        SELECT 1 FROM security.menu_role mr
                        JOIN my_roles r ON r.id = mr.role_id
                        WHERE mr.menu_id = m.id AND mr.is_active
                    )
                )
            ),
            grouped AS (
                SELECT module_id, module, module_order,
                       jsonb_agg(jsonb_build_object('name', name, 'path', path, 'icon', icon)
                                 ORDER BY sort_order, id) AS menus
                FROM visible
                GROUP BY module_id, module, module_order
            )
            SELECT coalesce(jsonb_agg(jsonb_build_object('module', module, 'menus', menus)
                                      ORDER BY module_order, module_id), '[]'::jsonb)
            FROM grouped
        $$;
        GRANT EXECUTE ON FUNCTION security.fn_my_menus() TO ceragen_app;

        INSERT INTO security.module (name, sort_order) VALUES ('General', 1);
        INSERT INTO security.menu (module_id, name, path, icon, sort_order)
        SELECT id, 'Inicio', '/', 'layout-dashboard', 1 FROM security.module WHERE name = 'General';
        INSERT INTO security.menu_role (menu_id, role_id)
        SELECT m.id, r.id FROM security.menu m, security.role r
        WHERE m.path = '/' AND NOT r.is_admin;
    """)


def downgrade() -> None:
    op.execute("""
        DROP FUNCTION security.fn_my_menus();
        DROP TABLE security.menu_role, security.menu, security.module;
        DELETE FROM audit.event
        WHERE table_name IN ('security.module', 'security.menu', 'security.menu_role');
    """)
