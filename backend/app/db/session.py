"""Conexión de la API a la base (rol ceragen_app) y transacción por request."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Connection, create_engine

from app.config import settings

# Railway y compose entregan postgresql://; SQLAlchemy necesita saber que el driver es psycopg 3.
_url = settings.database_url.get_secret_value().replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(_url, pool_pre_ping=True)


def get_db() -> Iterator[Connection]:
    """Una transacción por request: commit si el endpoint termina bien; si lanza,
    el commit no corre y cerrar la conexión hace rollback."""
    with engine.connect() as conn:
        yield conn
        conn.commit()


# scope="function": el commit corre ANTES de enviar la respuesta. Con el default
# corre después, y un commit fallido llegaría al cliente como un 200.
# FastAPI cachea la dependencia: current_user y el endpoint comparten conexión
# (y el SET LOCAL app.user_id).
Db = Annotated[Connection, Depends(get_db, scope="function")]
