import os

from alembic import context
from sqlalchemy import create_engine

# Las migraciones corren como ceragen_owner, nunca como la API ni el superusuario.
url = os.environ["DATABASE_OWNER_URL"]
# Railway y compose entregan postgresql://; SQLAlchemy necesita saber que el driver es psycopg 3.
url = url.replace("postgresql://", "postgresql+psycopg://", 1)

with create_engine(url).connect() as connection:
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()
