"""Base: extensiones, schemas por módulo, permisos por defecto y auditoría genérica.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- bcrypt para contraseñas (día 6)
        CREATE EXTENSION IF NOT EXISTS btree_gist; -- EXCLUDE de citas que se pisan

        -- Postgres da EXECUTE a PUBLIC en toda función nueva. Se corta de raíz:
        -- cada función que la API pueda llamar se concede explícitamente.
        ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

        CREATE SCHEMA security;
        CREATE SCHEMA core;
        CREATE SCHEMA clinic;
        CREATE SCHEMA billing;
        CREATE SCHEMA audit;

        -- USAGE solo deja "ver" el schema; los permisos sobre cada tabla y
        -- función se dan en la migración que la crea. audit queda fuera.
        GRANT USAGE ON SCHEMA security, core, clinic, billing TO ceragen_app;

        CREATE TABLE audit.event (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            table_name  text NOT NULL,
            operation   text NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
            row_id      bigint,
            -- ponytail: sin FK a security.user a propósito; la auditoría nunca
            -- debe bloquear una escritura y los usuarios no se borran físicamente.
            user_id     bigint,
            old_data    jsonb,
            new_data    jsonb
        );
        CREATE INDEX ON audit.event (table_name, row_id);

        -- Trigger genérico. SECURITY DEFINER: escribe en audit.event aunque quien
        -- dispara (ceragen_app) no tenga permisos sobre audit. search_path fijo
        -- para que nadie pueda colar objetos propios con el mismo nombre.
        CREATE FUNCTION audit.fn_log_change() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            old_row jsonb := CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END;
            new_row jsonb := CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END;
        BEGIN
            IF old_row = new_row THEN
                RETURN NULL;  -- UPDATE sin cambios reales: no ensucia la auditoría
            END IF;
            INSERT INTO audit.event (table_name, operation, row_id, user_id, old_data, new_data)
            VALUES (
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
                TG_OP,
                (coalesce(new_row, old_row) ->> 'id')::bigint,
                -- La API fija SET LOCAL app.user_id en cada transacción (día 7).
                nullif(current_setting('app.user_id', true), '')::bigint,
                old_row,
                new_row
            );
            RETURN NULL;
        END
        $$;

        -- Activa la auditoría en una tabla: SELECT audit.fn_enable('clinic.patient');
        CREATE FUNCTION audit.fn_enable(tbl regclass) RETURNS void
        LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            EXECUTE format(
                'CREATE TRIGGER audit_log AFTER INSERT OR UPDATE OR DELETE ON %s '
                'FOR EACH ROW EXECUTE FUNCTION audit.fn_log_change()', tbl);
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DROP SCHEMA audit, billing, clinic, core, security CASCADE;
        ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
        DROP EXTENSION IF EXISTS btree_gist;
        DROP EXTENSION IF EXISTS pgcrypto;
    """)
