FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# INSTALL_DEV=true solo para la imagen de tests (pytest); la de producción no lo trae.
ARG INSTALL_DEV=false
COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Usuario sin privilegios dentro del contenedor
RUN useradd --create-home --uid 1000 appuser
USER appuser

# Railway inyecta PORT; en local se usa 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
