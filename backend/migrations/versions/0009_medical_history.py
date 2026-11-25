"""Historial médico: entradas clínicas por paciente.

Es información sensible, así que se protege también la LECTURA, no solo la
escritura: la API no tiene SELECT sobre la tabla. Lee con
clinic.fn_patient_history(), que exige la pantalla /medical-history (o admin).
Escribir exige la misma pantalla (trigger menu_guard). Una entrada solo la
corrige su autor (o un admin); la auditoría guarda el texto anterior. No se
borra: se anula con is_active = false.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

from migrations.conventions import AUDIT_COLUMNS, standard_triggers

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE clinic.medical_history (
            id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_id   bigint NOT NULL REFERENCES clinic.patient,
            recorded_on  date NOT NULL DEFAULT current_date CHECK (recorded_on <= current_date),
            reason       text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 300),
            diagnosis    text CHECK (length(diagnosis) <= 2000),
            treatment    text CHECK (length(treatment) <= 2000),
            notes        text CHECK (length(notes) <= 4000),
            {AUDIT_COLUMNS}
        );
        CREATE INDEX ON clinic.medical_history (patient_id, recorded_on DESC);
        {standard_triggers("clinic.medical_history")}
        CREATE TRIGGER menu_guard BEFORE INSERT OR UPDATE OR DELETE ON clinic.medical_history
            FOR EACH STATEMENT EXECUTE FUNCTION core.fn_menu_guard('/medical-history');
        -- Sin SELECT: la lectura va por fn_patient_history. RETURNING en el INSERT
        -- necesitaría SELECT sobre la columna id: se concede solo esa.
        GRANT INSERT (patient_id, recorded_on, reason, diagnosis, treatment, notes),
              UPDATE (recorded_on, reason, diagnosis, treatment, notes, is_active),
              SELECT (id)
            ON clinic.medical_history TO ceragen_app;

        -- Solo el autor corrige su entrada; un admin puede corregir cualquiera.
        CREATE FUNCTION clinic.fn_history_author_only() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            IF session_user <> 'ceragen_owner'
               AND OLD.created_by IS DISTINCT FROM core.fn_current_user_id()
               AND NOT EXISTS (
                   SELECT 1 FROM jsonb_array_elements(security.fn_user_roles(core.fn_current_user_id())) r
                   WHERE (r ->> 'is_admin')::boolean
               ) THEN
                RAISE EXCEPTION 'solo el autor puede corregir esta entrada'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER author_only BEFORE UPDATE ON clinic.medical_history
            FOR EACH ROW EXECUTE FUNCTION clinic.fn_history_author_only();

        -- Historial de un paciente, de lo más reciente a lo más antiguo, con el autor.
        CREATE FUNCTION clinic.fn_patient_history(p_patient_id bigint) RETURNS TABLE (
            id bigint, recorded_on date, reason text, diagnosis text, treatment text, notes text,
            author text, author_id bigint, created_at timestamptz, updated_at timestamptz, is_active boolean
        )
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            IF NOT security.fn_has_menu('/medical-history') THEN
                RAISE EXCEPTION 'no tienes permiso para ver el historial médico'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN QUERY
            SELECT h.id, h.recorded_on, h.reason, h.diagnosis, h.treatment, h.notes,
                   u.username, h.created_by, h.created_at, h.updated_at, h.is_active
            FROM clinic.medical_history h
            LEFT JOIN security.user u ON u.id = h.created_by
            WHERE h.patient_id = p_patient_id
            ORDER BY h.recorded_on DESC, h.id DESC;
        END
        $$;
        GRANT EXECUTE ON FUNCTION clinic.fn_patient_history(bigint) TO ceragen_app;

        INSERT INTO security.menu (module_id, name, path, icon, sort_order)
        SELECT id, 'Historial médico', '/medical-history', 'notes', 2
        FROM security.module WHERE name = 'Clínica';
        -- Solo el terapeuta (y el admin): recepción no ve datos clínicos.
        INSERT INTO security.menu_role (menu_id, role_id)
        SELECT m.id, r.id FROM security.menu m, security.role r
        WHERE m.path = '/medical-history' AND r.name = 'Terapeuta';
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM security.menu_role
        WHERE menu_id IN (SELECT id FROM security.menu WHERE path = '/medical-history');
        DELETE FROM security.menu WHERE path = '/medical-history';
        DROP TABLE clinic.medical_history;
        DROP FUNCTION clinic.fn_patient_history(bigint), clinic.fn_history_author_only();
        DELETE FROM audit.event WHERE table_name = 'clinic.medical_history';
    """)
