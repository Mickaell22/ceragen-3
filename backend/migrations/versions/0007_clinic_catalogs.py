"""Catálogos clínicos: tipos de enfermedad, enfermedades y alergias.

Primer catálogo con una referencia a otro (enfermedad -> tipo de enfermedad).
La FK lleva su índice: Postgres no lo crea solo.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

from migrations.conventions import catalog_table

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLES = ("clinic.allergy", "clinic.disease", "clinic.disease_type")


def upgrade() -> None:
    op.execute(catalog_table("clinic.disease_type"))
    op.execute(
        catalog_table(
            "clinic.disease",
            "disease_type_id bigint NOT NULL REFERENCES clinic.disease_type",
        )
    )
    op.execute("CREATE INDEX ON clinic.disease (disease_type_id)")
    op.execute(catalog_table("clinic.allergy", "description text CHECK (length(description) <= 500)"))

    op.execute("""
        INSERT INTO clinic.disease_type (name) VALUES
            ('Neurológica'), ('Musculoesquelética'), ('Respiratoria'), ('Cardiovascular'), ('Metabólica');

        INSERT INTO clinic.disease (name, disease_type_id)
        SELECT d.name, t.id
        FROM (VALUES ('Accidente cerebrovascular', 'Neurológica'),
                     ('Parálisis cerebral', 'Neurológica'),
                     ('Lumbalgia', 'Musculoesquelética'),
                     ('Artrosis', 'Musculoesquelética'),
                     ('Escoliosis', 'Musculoesquelética'),
                     ('Asma', 'Respiratoria'),
                     ('Hipertensión arterial', 'Cardiovascular'),
                     ('Diabetes tipo 2', 'Metabólica')) AS d(name, type_name)
        JOIN clinic.disease_type t ON t.name = d.type_name;

        INSERT INTO clinic.allergy (name, description) VALUES
            ('Penicilina', 'Antibiótico betalactámico'),
            ('Ibuprofeno', 'Antiinflamatorio no esteroideo'),
            ('Látex', 'Guantes y material de curación'),
            ('Polen', NULL),
            ('Mariscos', NULL);

        INSERT INTO security.menu (module_id, name, path, icon, sort_order)
        SELECT m.id, c.name, c.path, c.icon, c.ord
        FROM security.module m,
             (VALUES ('Tipos de enfermedad', '/catalogs/disease-types', 'category', 6),
                     ('Enfermedades', '/catalogs/diseases', 'virus', 7),
                     ('Alergias', '/catalogs/allergies', 'alert-triangle', 8))
             AS c(name, path, icon, ord)
        WHERE m.name = 'Catálogos';
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM security.menu
        WHERE path IN ('/catalogs/disease-types', '/catalogs/diseases', '/catalogs/allergies');
    """)
    op.execute(f"DROP TABLE {', '.join(TABLES)}")
    op.execute(f"DELETE FROM audit.event WHERE table_name IN ({', '.join(f"'{t}'" for t in TABLES)})")
