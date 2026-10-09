"""Seguridad: usuarios, roles, sesiones, login con bcrypt y bloqueo temporal.

La API no tiene NINGÚN permiso sobre las tablas de security: solo EXECUTE sobre
las funciones de abajo, que son SECURITY DEFINER. Así nunca puede leer un hash.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

from migrations.conventions import AUDIT_COLUMNS, standard_triggers

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Gotcha: `user` es palabra reservada. Calificada (security.user) Postgres la
# acepta sin comillas; sola no. Siempre escribirla con el schema.


def upgrade() -> None:
    op.execute("""
        -- Usuario de la transacción actual (lo fija la API con SET LOCAL app.user_id).
        CREATE FUNCTION core.fn_current_user_id() RETURNS bigint
        LANGUAGE sql STABLE SET search_path = pg_catalog, pg_temp
        AS $$ SELECT nullif(current_setting('app.user_id', true), '')::bigint $$;

        CREATE FUNCTION core.fn_touch() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            NEW.updated_at := now();
            NEW.updated_by := core.fn_current_user_id();
            RETURN NEW;
        END
        $$;

        -- Los hashes nunca llegan a la auditoría. Mismo trigger de 0001, más el filtro.
        CREATE OR REPLACE FUNCTION audit.fn_log_change() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            old_row jsonb := CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) - 'password_hash' END;
            new_row jsonb := CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) - 'password_hash' END;
        BEGIN
            IF old_row = new_row THEN
                RETURN NULL;
            END IF;
            INSERT INTO audit.event (table_name, operation, row_id, user_id, old_data, new_data)
            VALUES (
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
                TG_OP,
                (coalesce(new_row, old_row) ->> 'id')::bigint,
                nullif(current_setting('app.user_id', true), '')::bigint,
                old_row,
                new_row
            );
            RETURN NULL;
        END
        $$;
    """)

    op.execute(f"""
        CREATE TABLE security.user (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            -- ponytail: person_id (FK a core.person) se agrega con el módulo core.
            username        text NOT NULL CHECK (username ~ '^[A-Za-z0-9._-]{{3,50}}$'),
            email           text NOT NULL CHECK (email ~ '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'),
            password_hash   text NOT NULL,
            login_attempts  integer NOT NULL DEFAULT 0 CHECK (login_attempts >= 0),
            locked_until    timestamptz,
            last_login_at   timestamptz,
            {AUDIT_COLUMNS}
        );
        CREATE UNIQUE INDEX user_username_key ON security.user (lower(username));
        CREATE UNIQUE INDEX user_email_key ON security.user (lower(email));

        CREATE TABLE security.role (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name        text NOT NULL,
            description text,
            is_admin    boolean NOT NULL DEFAULT false,
            {AUDIT_COLUMNS}
        );
        CREATE UNIQUE INDEX role_name_key ON security.role (lower(name));

        CREATE TABLE security.user_role (
            id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id  bigint NOT NULL REFERENCES security.user,
            role_id  bigint NOT NULL REFERENCES security.role,
            {AUDIT_COLUMNS},
            UNIQUE (user_id, role_id)
        );
        CREATE INDEX ON security.user_role (role_id);

        -- Una fila por login. Se guarda solo el jti del JWT (para revocarlo), nunca el token.
        CREATE TABLE security.session (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id     bigint NOT NULL REFERENCES security.user,
            jti         uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
            ip          inet,
            created_at  timestamptz NOT NULL DEFAULT now(),
            expires_at  timestamptz NOT NULL,
            revoked_at  timestamptz,
            CHECK (expires_at > created_at)
        );
        CREATE INDEX ON security.session (user_id);

        {standard_triggers("security.user")}
        {standard_triggers("security.role")}
        {standard_triggers("security.user_role")}

        INSERT INTO security.role (name, description, is_admin) VALUES
            ('Administrador', 'Acceso total al sistema', true),
            ('Terapeuta', 'Agenda y atención de pacientes', false),
            ('Recepción', 'Pacientes, facturación y pagos', false);
    """)

    op.execute("""
        -- Login: valida bcrypt, aplica el bloqueo temporal y abre la sesión.
        -- No lanza excepciones a propósito: un RAISE revertiría el contador de
        -- intentos fallidos. Devuelve status = ok | invalid | locked.
        -- La política (intentos, minutos) la manda la API desde su configuración.
        CREATE FUNCTION security.fn_login(
            p_username text, p_password text, p_ip inet,
            p_session_minutes integer, p_max_attempts integer, p_lock_minutes integer,
            OUT status text, OUT user_id bigint, OUT jti uuid, OUT expires_at timestamptz,
            OUT locked_until timestamptz, OUT roles jsonb
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            u security.user;
        BEGIN
            -- FOR UPDATE: dos intentos simultáneos no pueden perder un incremento.
            SELECT * INTO u FROM security.user
            WHERE lower(username) = lower(p_username) AND is_active
            FOR UPDATE;

            IF NOT FOUND THEN
                -- Mismo costo que un bcrypt real: el tiempo de respuesta no
                -- revela si el usuario existe.
                PERFORM public.crypt(p_password, public.gen_salt('bf', 12));
                status := 'invalid';
                RETURN;
            END IF;

            -- ponytail: 'locked' revela que la cuenta existe (fuga aceptada:
            -- sin el aviso el usuario no sabría por qué no entra). Mientras
            -- dura el bloqueo ni se verifica la contraseña ni suma intentos.
            IF u.locked_until > now() THEN
                status := 'locked';
                locked_until := u.locked_until;
                RETURN;
            END IF;

            IF u.password_hash <> public.crypt(p_password, u.password_hash) THEN
                IF u.login_attempts + 1 >= p_max_attempts THEN
                    UPDATE security.user
                    SET login_attempts = 0, locked_until = now() + make_interval(mins => p_lock_minutes)
                    WHERE id = u.id
                    RETURNING security.user.locked_until INTO locked_until;
                    status := 'locked';
                ELSE
                    UPDATE security.user SET login_attempts = login_attempts + 1 WHERE id = u.id;
                    status := 'invalid';
                END IF;
                RETURN;
            END IF;

            UPDATE security.user
            SET login_attempts = 0, locked_until = NULL, last_login_at = now()
            WHERE id = u.id;

            INSERT INTO security.session (user_id, ip, expires_at)
            VALUES (u.id, p_ip, now() + make_interval(mins => p_session_minutes))
            RETURNING security.session.jti, security.session.expires_at INTO jti, expires_at;

            status := 'ok';
            user_id := u.id;
            roles := security.fn_user_roles(u.id);
        END
        $$;

        CREATE FUNCTION security.fn_user_roles(p_user_id bigint) RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            SELECT coalesce(jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name, 'is_admin', r.is_admin)
                                      ORDER BY r.id), '[]'::jsonb)
            FROM security.user_role ur
            JOIN security.role r ON r.id = ur.role_id
            WHERE ur.user_id = p_user_id AND ur.is_active AND r.is_active
        $$;

        -- La API lo llama en cada request: el JWT puede ser válido y la sesión
        -- estar revocada (logout) o el usuario desactivado. NULL = rechazar.
        CREATE FUNCTION security.fn_session_user(p_jti uuid) RETURNS bigint
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            SELECT s.user_id
            FROM security.session s
            JOIN security.user u ON u.id = s.user_id
            WHERE s.jti = p_jti AND s.revoked_at IS NULL AND s.expires_at > now() AND u.is_active
        $$;

        CREATE FUNCTION security.fn_logout(p_jti uuid) RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            UPDATE security.session SET revoked_at = now() WHERE jti = p_jti AND revoked_at IS NULL
        $$;

        CREATE FUNCTION security.fn_check_password_policy(p_password text) RETURNS void
        LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            -- 72: bcrypt ignora lo que pase de 72 bytes.
            IF length(p_password) < 8 OR octet_length(p_password) > 72 THEN
                RAISE EXCEPTION 'la contraseña debe tener entre 8 y 72 caracteres'
                    USING ERRCODE = 'check_violation';
            END IF;
        END
        $$;

        -- Solo un administrador (o las migraciones/semilla, que entran como
        -- ceragen_owner) puede crear usuarios. Defensa en profundidad: la API
        -- también lo valida, pero la base no confía en ella.
        CREATE FUNCTION security.fn_create_user(
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

        -- Cambia la contraseña del usuario de la transacción, exigiendo la actual.
        CREATE FUNCTION security.fn_change_password(p_current text, p_new text) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            uid bigint := core.fn_current_user_id();
        BEGIN
            PERFORM security.fn_check_password_policy(p_new);
            UPDATE security.user
            SET password_hash = public.crypt(p_new, public.gen_salt('bf', 12))
            WHERE id = uid AND password_hash = public.crypt(p_current, password_hash);
            IF NOT FOUND THEN
                RETURN false;
            END IF;
            -- Cierra las demás sesiones: quien robó la contraseña anterior queda afuera.
            UPDATE security.session SET revoked_at = now() WHERE user_id = uid AND revoked_at IS NULL;
            RETURN true;
        END
        $$;

        GRANT EXECUTE ON FUNCTION
            core.fn_current_user_id(),
            security.fn_login(text, text, inet, integer, integer, integer),
            security.fn_session_user(uuid),
            security.fn_logout(uuid),
            security.fn_user_roles(bigint),
            security.fn_create_user(text, text, text, bigint[]),
            security.fn_change_password(text, text)
        TO ceragen_app;
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE security.session, security.user_role, security.role, security.user CASCADE;
        DROP FUNCTION security.fn_login, security.fn_user_roles, security.fn_session_user,
            security.fn_logout, security.fn_check_password_policy, security.fn_create_user,
            security.fn_change_password, core.fn_touch, core.fn_current_user_id;
        DELETE FROM audit.event WHERE table_name LIKE 'security.%';
    """)
    # Vuelve el trigger de auditoría de 0001 (sin el filtro de password_hash).
    op.execute("""
        CREATE OR REPLACE FUNCTION audit.fn_log_change() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            old_row jsonb := CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END;
            new_row jsonb := CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END;
        BEGIN
            IF old_row = new_row THEN
                RETURN NULL;
            END IF;
            INSERT INTO audit.event (table_name, operation, row_id, user_id, old_data, new_data)
            VALUES (
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
                TG_OP,
                (coalesce(new_row, old_row) ->> 'id')::bigint,
                nullif(current_setting('app.user_id', true), '')::bigint,
                old_row,
                new_row
            );
            RETURN NULL;
        END
        $$;
    """)
