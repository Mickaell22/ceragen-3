"""Catálogos generales: géneros, estados civiles, tipos de terapia, impuestos y
métodos de pago. Patrón que repiten los catálogos de los días siguientes
(ver migrations.conventions.catalog_table).

También extiende core.fn_touch: desactivar o reactivar una fila (is_active)
llena o limpia deleted_at/deleted_by solo, en todas las tablas de negocio.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

from migrations.conventions import catalog_table

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CATALOGS = (
    "core.gender",
    "core.marital_status",
    "clinic.therapy_type",
    "billing.tax",
    "billing.payment_method",
)

TOUCH_0002 = """
    CREATE OR REPLACE FUNCTION core.fn_touch() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
    AS $$
    BEGIN
        NEW.updated_at := now();
        NEW.updated_by := core.fn_current_user_id();
        RETURN NEW;
    END
    $$;
"""


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION core.fn_touch() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            NEW.updated_at := now();
            NEW.updated_by := core.fn_current_user_id();
            -- Borrado lógico: el cambio de is_active deja rastro de quién y cuándo.
            IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
                NEW.deleted_at := CASE WHEN NEW.is_active THEN NULL ELSE now() END;
                NEW.deleted_by := CASE WHEN NEW.is_active THEN NULL ELSE core.fn_current_user_id() END;
            END IF;
            RETURN NEW;
        END
        $$;

        -- Trigger de sentencia para tablas que solo un administrador puede modificar.
        -- SECURITY DEFINER para poder llamar a fn_require_admin (la API no tiene EXECUTE);
        -- fn_require_admin mira session_user, que no cambia: sigue siendo ceragen_app.
        CREATE FUNCTION core.fn_admin_only() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $$
        BEGIN
            PERFORM security.fn_require_admin();
            RETURN NULL;
        END
        $$;
    """)

    op.execute(catalog_table("core.gender"))
    op.execute(catalog_table("core.marital_status"))
    op.execute(catalog_table("clinic.therapy_type", "description text CHECK (length(description) <= 500)"))
    op.execute(
        catalog_table(
            "billing.tax",
            "percentage numeric(5,2) NOT NULL CHECK (percentage BETWEEN 0 AND 100)",
        )
    )
    # requires_reference: número de transacción o voucher; requires_proof: foto del comprobante.
    op.execute(
        catalog_table(
            "billing.payment_method",
            "requires_reference boolean NOT NULL DEFAULT false, "
            "requires_proof boolean NOT NULL DEFAULT false",
        )
    )

    op.execute("""
        INSERT INTO core.gender (name) VALUES ('Masculino'), ('Femenino'), ('Otro');
        INSERT INTO core.marital_status (name) VALUES
            ('Soltero/a'), ('Casado/a'), ('Divorciado/a'), ('Viudo/a'), ('Unión de hecho');
        INSERT INTO clinic.therapy_type (name, description) VALUES
            ('Fisioterapia', 'Rehabilitación física y del movimiento'),
            ('Terapia de lenguaje', 'Trastornos del habla, voz y deglución'),
            ('Terapia ocupacional', 'Autonomía en actividades de la vida diaria');
        INSERT INTO billing.tax (name, percentage) VALUES ('IVA 15%', 15), ('IVA 0%', 0);
        INSERT INTO billing.payment_method (name, requires_reference, requires_proof) VALUES
            ('Efectivo', false, false),
            ('Transferencia', true, true),
            ('Tarjeta', true, false);

        INSERT INTO security.module (name, sort_order) VALUES ('Catálogos', 80);
        INSERT INTO security.menu (module_id, name, path, icon, sort_order)
        SELECT m.id, c.name, c.path, c.icon, c.ord
        FROM security.module m,
             (VALUES ('Géneros', '/catalogs/genders', 'gender-bigender', 1),
                     ('Estados civiles', '/catalogs/marital-statuses', 'heart-handshake', 2),
                     ('Tipos de terapia', '/catalogs/therapy-types', 'stethoscope', 3),
                     ('Impuestos', '/catalogs/taxes', 'receipt-tax', 4),
                     ('Métodos de pago', '/catalogs/payment-methods', 'credit-card', 5))
             AS c(name, path, icon, ord)
        WHERE m.name = 'Catálogos';
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM security.menu WHERE path LIKE '/catalogs/%';
        DELETE FROM security.module WHERE name = 'Catálogos';
    """)
    op.execute(f"DROP TABLE {', '.join(CATALOGS)}")
    op.execute(f"""
        DELETE FROM audit.event WHERE table_name IN ({", ".join(f"'{t}'" for t in CATALOGS)});
        DROP FUNCTION core.fn_admin_only();
        {TOUCH_0002}
    """)
