"""Personas, clientes y pacientes.

- core.person: datos de identidad, con la cédula ecuatoriana validada en la base.
- core.client: quien paga (puede ser distinto del paciente: un padre que paga
  la terapia del hijo). Es una persona.
- clinic.patient: quien recibe la terapia. client_id NULL = se paga solo.
- clinic.patient_allergy / patient_disease: alergias y enfermedades del paciente.

Permisos por pantalla: escribir en estas tablas exige tener asignado el menú de
la pantalla (o ser admin). Lo impone la base con security.fn_require_menu, así
la regla vive en un solo lugar y vale aunque se escriba por fuera de la API.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

from migrations.conventions import AUDIT_COLUMNS, standard_triggers

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLES = ("clinic.patient_disease", "clinic.patient_allergy", "clinic.patient", "core.client", "core.person")


def menu_guard(table: str, path: str) -> str:
    """Solo quien tiene el menú `path` (o es admin) puede escribir en `table`."""
    return f"""
        CREATE TRIGGER menu_guard BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION core.fn_menu_guard('{path}');
    """


def upgrade() -> None:
    op.execute("""
        -- Cédula ecuatoriana (módulo 10). IMMUTABLE para poder usarla en CHECK.
        -- Provincia 01-24 o 30 (ecuatorianos registrados en el exterior);
        -- tercer dígito < 6 (persona natural).
        CREATE FUNCTION core.fn_is_valid_cedula(p text) RETURNS boolean
        LANGUAGE plpgsql IMMUTABLE STRICT SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            total int := 0;
            digit int;
        BEGIN
            IF p !~ '^[0-9]{10}$'
               OR substr(p, 1, 2)::int NOT BETWEEN 1 AND 24 AND substr(p, 1, 2) <> '30'
               OR substr(p, 3, 1)::int >= 6 THEN
                RETURN false;
            END IF;
            FOR i IN 1..9 LOOP
                digit := substr(p, i, 1)::int * CASE WHEN i % 2 = 1 THEN 2 ELSE 1 END;
                total := total + CASE WHEN digit > 9 THEN digit - 9 ELSE digit END;
            END LOOP;
            RETURN (10 - total % 10) % 10 = substr(p, 10, 1)::int;
        END
        $$;
        GRANT EXECUTE ON FUNCTION core.fn_is_valid_cedula(text) TO ceragen_app;

        -- ¿El usuario de la transacción tiene la pantalla `p_path`? Admin: siempre.
        CREATE FUNCTION security.fn_has_menu(p_path text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM jsonb_array_elements(security.fn_user_roles(core.fn_current_user_id())) r
                WHERE (r ->> 'is_admin')::boolean
            ) OR EXISTS (
                SELECT 1
                FROM security.user_role ur
                JOIN security.role r ON r.id = ur.role_id AND r.is_active
                JOIN security.menu_role mr ON mr.role_id = r.id AND mr.is_active
                JOIN security.menu m ON m.id = mr.menu_id AND m.is_active
                WHERE ur.user_id = core.fn_current_user_id() AND ur.is_active AND m.path = p_path
            )
        $$;

        -- Trigger de sentencia: corta la escritura si no tiene la pantalla.
        -- ceragen_owner (migraciones, semilla) pasa siempre.
        CREATE FUNCTION core.fn_menu_guard() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            IF session_user <> 'ceragen_owner' AND NOT security.fn_has_menu(TG_ARGV[0]) THEN
                RAISE EXCEPTION 'no tienes permiso para modificar estos datos'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NULL;
        END
        $$;
    """)

    op.execute(f"""
        CREATE TABLE core.person (
            id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            identification_type  text NOT NULL CHECK (identification_type IN ('cedula', 'ruc', 'passport')),
            identification       text NOT NULL,
            first_name           text NOT NULL CHECK (length(btrim(first_name)) BETWEEN 1 AND 100),
            last_name            text NOT NULL CHECK (length(btrim(last_name)) BETWEEN 1 AND 100),
            birth_date           date CHECK (birth_date BETWEEN '1900-01-01' AND current_date),
            gender_id            bigint REFERENCES core.gender,
            marital_status_id    bigint REFERENCES core.marital_status,
            email                text CHECK (email ~ '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'),
            phone                text CHECK (phone ~ '^\\+?[0-9 -]{{7,20}}$'),
            address              text CHECK (length(address) <= 300),
            {AUDIT_COLUMNS},
            -- ponytail: el RUC solo se valida en formato (13 dígitos terminados
            -- en 001). Validar el dígito verificador exige tres algoritmos
            -- distintos (natural, pública, privada); si hace falta, va aquí.
            CONSTRAINT person_identification_check CHECK (CASE identification_type
                WHEN 'cedula' THEN core.fn_is_valid_cedula(identification)
                WHEN 'ruc' THEN identification ~ '^[0-9]{{10}}001$'
                ELSE identification ~ '^[A-Z0-9]{{5,20}}$'
            END),
            UNIQUE (identification_type, identification)
        );
        CREATE INDEX ON core.person (gender_id);
        CREATE INDEX ON core.person (marital_status_id);
        -- Búsqueda por apellido y nombre (listas y autocompletar).
        CREATE INDEX person_name_idx ON core.person (lower(last_name), lower(first_name));

        CREATE TABLE core.client (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id  bigint NOT NULL UNIQUE REFERENCES core.person,
            {AUDIT_COLUMNS}
        );

        CREATE TABLE clinic.patient (
            id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id                bigint NOT NULL UNIQUE REFERENCES core.person,
            client_id                bigint REFERENCES core.client,
            blood_type               text CHECK (blood_type IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
            emergency_contact_name   text CHECK (length(emergency_contact_name) <= 200),
            emergency_contact_phone  text CHECK (emergency_contact_phone ~ '^\\+?[0-9 -]{{7,20}}$'),
            notes                    text CHECK (length(notes) <= 2000),
            {AUDIT_COLUMNS}
        );
        CREATE INDEX ON clinic.patient (client_id);

        CREATE TABLE clinic.patient_allergy (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_id  bigint NOT NULL REFERENCES clinic.patient,
            allergy_id  bigint NOT NULL REFERENCES clinic.allergy,
            {AUDIT_COLUMNS},
            UNIQUE (patient_id, allergy_id)
        );
        CREATE INDEX ON clinic.patient_allergy (allergy_id);

        CREATE TABLE clinic.patient_disease (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_id  bigint NOT NULL REFERENCES clinic.patient,
            disease_id  bigint NOT NULL REFERENCES clinic.disease,
            {AUDIT_COLUMNS},
            UNIQUE (patient_id, disease_id)
        );
        CREATE INDEX ON clinic.patient_disease (disease_id);
    """)

    # Todas las escrituras de este módulo (personas y clientes incluidos) las
    # hace quien tiene la pantalla de pacientes. Sin DELETE: borrado lógico.
    for table in TABLES:
        op.execute(standard_triggers(table) + menu_guard(table, "/patients"))
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO ceragen_app")

    op.execute("""
        INSERT INTO security.module (name, sort_order) VALUES ('Clínica', 10);
        INSERT INTO security.menu (module_id, name, path, icon, sort_order)
        SELECT id, 'Pacientes', '/patients', 'users-group', 1 FROM security.module WHERE name = 'Clínica';
        -- Recepción registra y edita pacientes; el terapeuta también (alergias, enfermedades).
        INSERT INTO security.menu_role (menu_id, role_id)
        SELECT m.id, r.id FROM security.menu m, security.role r
        WHERE m.path = '/patients' AND r.name IN ('Recepción', 'Terapeuta');
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM security.menu_role
        WHERE menu_id IN (SELECT id FROM security.menu WHERE path = '/patients');
        DELETE FROM security.menu WHERE path = '/patients';
        DELETE FROM security.module WHERE name = 'Clínica';
    """)
    op.execute(f"DROP TABLE {', '.join(TABLES)}")
    op.execute(f"DELETE FROM audit.event WHERE table_name IN ({', '.join(f"'{t}'" for t in TABLES)})")
    op.execute("""
        DROP FUNCTION core.fn_menu_guard(), security.fn_has_menu(text), core.fn_is_valid_cedula(text);
    """)
