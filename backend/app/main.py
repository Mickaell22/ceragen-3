import logging

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Ceragen API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> JSONResponse:
    """Liveness + conectividad con la base. Lo usan Docker y Railway."""
    try:
        with psycopg.connect(settings.database_url.get_secret_value(), connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        # El detalle va al log, nunca al cliente.
        logger.exception("health: base de datos no disponible")
        return JSONResponse({"status": "error", "db": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ok", "db": "ok"})
