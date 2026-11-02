"""Fragmentos SQL comunes a todas las tablas de negocio (un solo lugar, DRY)."""

# Columnas de auditoría de cada tabla de negocio. created_by se llena solo con
# el usuario de la transacción (SET LOCAL app.user_id, que fija la API).
# ponytail: estas FK no llevan índice; casi nunca se filtra por ellas. Si un
# reporte llega a hacerlo, se indexa esa columna en esa tabla.
AUDIT_COLUMNS = """
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  bigint DEFAULT core.fn_current_user_id() REFERENCES security.user,
    updated_at  timestamptz,
    updated_by  bigint REFERENCES security.user,
    deleted_at  timestamptz,
    deleted_by  bigint REFERENCES security.user,
    is_active   boolean NOT NULL DEFAULT true"""


def standard_triggers(table: str) -> str:
    """updated_at/updated_by automáticos + auditoría genérica."""
    return f"""
        CREATE TRIGGER touch BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION core.fn_touch();
        SELECT audit.fn_enable('{table}');
    """


def catalog_table(table: str, extra_columns: str = "") -> str:
    """Tabla de catálogo: id, name único (sin distinguir mayúsculas), columnas
    propias, auditoría y la regla "solo un administrador escribe" en la base.

    extra_columns va en una sola línea SQL sin comentarios "--" (se le agrega la coma final).
    La API (ceragen_app) puede leer, insertar y actualizar; nunca borrar (se
    desactiva con is_active). El trigger admin_only corta cualquier escritura
    de un usuario que no sea admin, aunque llegue por fuera de la API.
    """
    short = table.split(".")[1]
    extra = f"{extra_columns.strip().rstrip(',')}," if extra_columns.strip() else ""
    return f"""
        CREATE TABLE {table} (
            id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name  text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 100),
            {extra}
            {AUDIT_COLUMNS}
        );
        CREATE UNIQUE INDEX {short}_name_key ON {table} (lower(btrim(name)));
        CREATE TRIGGER admin_only BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION core.fn_admin_only();
        {standard_triggers(table)}
        GRANT SELECT, INSERT, UPDATE ON {table} TO ceragen_app;
    """
