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
