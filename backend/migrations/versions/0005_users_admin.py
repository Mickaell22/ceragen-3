"""Gestión de usuarios y roles (solo administradores).

La regla "solo un administrador" vive aquí, en security.fn_require_admin(), y
la usan todas las funciones de gestión. La API no la duplica: traduce el
insufficient_privilege de la base a un 403.

Invariante: siempre queda al menos un administrador activo. Sin eso, un admin
podría desactivarse o quitarse el rol y nadie podría volver a gestionar usuarios.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

FN_CREATE_USER_0002 = """
    CREATE OR REPLACE FUNCTION security.fn_create_user(
        p_username text, p_email text, p_password text, p_role_ids bigint[]
    ) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
    AS $$
    DECLARE
        new_id bigint;
    BEGIN
        IF session_user <> 'ceragen_owner' AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(security.fn_user_roles(core.fn_current_user_id())) r
            WHERE (r ->> 'is_admin')::boolean
        ) THEN
            RAISE EXCEPTION 'solo un administrador puede crear usuarios'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        PERFORM security.fn_check_password_policy(p_password);
        INSERT INTO security.user (username, email, password_hash)
        VALUES (p_username, p_email, public.crypt(p_password, public.gen_salt('bf', 12)))
        RETURNING id INTO new_id;
        INSERT INTO security.user_role (user_id, role_id)
        SELECT new_id, unnest(p_role_ids);
        RETURN new_id;
    END
    $$;
"""


def upgrade() -> None:
    op.execute("""
        -- Corta la operación si el usuario de la transacción no es admin. Las
        -- migraciones y la semilla (sesión ceragen_owner) pasan siempre.
        CREATE FUNCTION security.fn_require_admin() RETURNS void
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            IF session_user = 'ceragen_owner' THEN
                RETURN;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(security.fn_user_roles(core.fn_current_user_id())) r
                WHERE (r ->> 'is_admin')::boolean
            ) THEN
                RAISE EXCEPTION 'esta acción requiere un administrador'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
        END
        $$;

        -- Falla si la operación dejó al sistema sin ningún admin activo.
        CREATE FUNCTION security.fn_assert_admin_remains() RETURNS void
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM security.user u
                JOIN security.user_role ur ON ur.user_id = u.id AND ur.is_active
                JOIN security.role r ON r.id = ur.role_id AND r.is_active AND r.is_admin
                WHERE u.is_active
            ) THEN
                RAISE EXCEPTION 'debe quedar al menos un administrador activo'
                    USING ERRCODE = 'check_violation';
            END IF;
        END
        $$;

        -- Deja los roles del usuario exactamente en p_role_ids. Borrado lógico:
        -- los que salen quedan con is_active = false (la auditoría conserva quién y cuándo).
        CREATE FUNCTION security.fn_set_user_roles(p_user_id bigint, p_role_ids bigint[]) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            UPDATE security.user_role
            SET is_active = false, deleted_at = now(), deleted_by = core.fn_current_user_id()
            WHERE user_id = p_user_id AND is_active AND role_id <> ALL (p_role_ids);

            INSERT INTO security.user_role (user_id, role_id)
            SELECT p_user_id, rid FROM unnest(p_role_ids) AS rid
            ON CONFLICT (user_id, role_id) DO UPDATE
            SET is_active = true, deleted_at = NULL, deleted_by = NULL
            WHERE NOT security.user_role.is_active;
        END
        $$;
    """)

    # Misma firma que en 0002; ahora usa las funciones comunes de arriba.
    op.execute("""
        CREATE OR REPLACE FUNCTION security.fn_create_user(
            p_username text, p_email text, p_password text, p_role_ids bigint[]
        ) RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            new_id bigint;
        BEGIN
            PERFORM security.fn_require_admin();
            PERFORM security.fn_check_password_policy(p_password);
            INSERT INTO security.user (username, email, password_hash)
            VALUES (p_username, p_email, public.crypt(p_password, public.gen_salt('bf', 12)))
            RETURNING id INTO new_id;
            PERFORM security.fn_set_user_roles(new_id, p_role_ids);
            RETURN new_id;
        END
        $$;
    """)

    op.execute("""
        CREATE FUNCTION security.fn_list_users() RETURNS TABLE (
            id bigint, username text, email text, is_active boolean,
            locked_until timestamptz, last_login_at timestamptz, roles jsonb
        )
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            PERFORM security.fn_require_admin();
            RETURN QUERY
            SELECT u.id, u.username, u.email, u.is_active,
                   CASE WHEN u.locked_until > now() THEN u.locked_until END,
                   u.last_login_at, security.fn_user_roles(u.id)
            FROM security.user u
            ORDER BY u.username;
        END
        $$;

        CREATE FUNCTION security.fn_list_roles() RETURNS TABLE (
            id bigint, name text, description text, is_admin boolean
        )
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            PERFORM security.fn_require_admin();
            RETURN QUERY
            SELECT r.id, r.name, r.description, r.is_admin FROM security.role r
            WHERE r.is_active ORDER BY r.id;
        END
        $$;

        -- Edita correo, estado y roles. Desactivar a alguien cierra sus sesiones.
        CREATE FUNCTION security.fn_update_user(
            p_user_id bigint, p_email text, p_is_active boolean, p_role_ids bigint[]
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            PERFORM security.fn_require_admin();

            UPDATE security.user
            SET email = p_email,
                is_active = p_is_active,
                deleted_at = CASE WHEN p_is_active THEN NULL ELSE coalesce(deleted_at, now()) END,
                deleted_by = CASE WHEN p_is_active THEN NULL
                                  ELSE coalesce(deleted_by, core.fn_current_user_id()) END
            WHERE id = p_user_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'el usuario no existe' USING ERRCODE = 'no_data_found';
            END IF;

            PERFORM security.fn_set_user_roles(p_user_id, p_role_ids);

            IF NOT p_is_active THEN
                UPDATE security.session SET revoked_at = now()
                WHERE user_id = p_user_id AND revoked_at IS NULL;
            END IF;

            PERFORM security.fn_assert_admin_remains();
        END
        $$;

        -- El admin fija una contraseña nueva (usuario que la olvidó). También
        -- desbloquea la cuenta y cierra las sesiones abiertas.
        CREATE FUNCTION security.fn_reset_password(p_user_id bigint, p_password text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            PERFORM security.fn_require_admin();
            PERFORM security.fn_check_password_policy(p_password);
            UPDATE security.user
            SET password_hash = public.crypt(p_password, public.gen_salt('bf', 12)),
                login_attempts = 0, locked_until = NULL
            WHERE id = p_user_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'el usuario no existe' USING ERRCODE = 'no_data_found';
            END IF;
            UPDATE security.session SET revoked_at = now()
            WHERE user_id = p_user_id AND revoked_at IS NULL;
        END
        $$;

        CREATE FUNCTION security.fn_unlock_user(p_user_id bigint) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            PERFORM security.fn_require_admin();
            UPDATE security.user SET login_attempts = 0, locked_until = NULL WHERE id = p_user_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'el usuario no existe' USING ERRCODE = 'no_data_found';
            END IF;
        END
        $$;

        GRANT EXECUTE ON FUNCTION
            security.fn_list_users(),
            security.fn_list_roles(),
            security.fn_update_user(bigint, text, boolean, bigint[]),
            security.fn_reset_password(bigint, text),
            security.fn_unlock_user(bigint)
        TO ceragen_app;

        -- Pantalla de usuarios: solo admins (no se asigna menu_role a nadie).
        INSERT INTO security.module (name, sort_order) VALUES ('Administración', 90);
        INSERT INTO security.menu (module_id, name, path, icon, sort_order)
        SELECT id, 'Usuarios', '/users', 'users', 1 FROM security.module WHERE name = 'Administración';
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM security.menu WHERE path = '/users';
        DELETE FROM security.module WHERE name = 'Administración';
        DROP FUNCTION security.fn_list_users(), security.fn_list_roles(),
            security.fn_update_user(bigint, text, boolean, bigint[]),
            security.fn_reset_password(bigint, text), security.fn_unlock_user(bigint);
    """)
    op.execute(FN_CREATE_USER_0002)
    op.execute("""
        DROP FUNCTION security.fn_set_user_roles(bigint, bigint[]),
            security.fn_assert_admin_remains(), security.fn_require_admin();
    """)
