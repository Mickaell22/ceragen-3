import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.auth import COOKIE
from app.auth import router as auth_router
from app.config import settings
from app.db.session import engine
from app.users import router as users_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Ceragen API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def csrf_origin_check(request: Request, call_next):
    """CSRF: la sesión viaja en una cookie que el navegador manda sola, así que una
    escritura con cookie solo se acepta si Origin es uno de los nuestros (los mismos
    de CORS, o la propia API para /docs). Los navegadores siempre mandan Origin en
    POST; si falta, no es un navegador y no se acepta la cookie.
    El login también se valida (login CSRF: entrar a la víctima en la cuenta del atacante).
    """
    if request.method in UNSAFE_METHODS and (COOKIE in request.cookies or request.url.path == "/auth/login"):
        origin = request.headers.get("origin")
        own = f"{request.url.scheme}://{request.url.netloc}"
        if origin is None and COOKIE not in request.cookies:
            pass  # login sin cookie desde un cliente que no es navegador (curl, scripts)
        elif origin not in settings.cors_origin_list and origin != own:
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Cualquier error no previsto: el detalle va al log, al cliente solo un mensaje genérico."""
    logger.exception("error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Error interno del servidor"}, status_code=500)


# Errores que la base lanza a propósito (reglas de negocio) y su respuesta HTTP.
# sqlstate -> (status, mensaje fijo o None para usar el de la base).
DB_ERRORS = {
    "42501": (403, None),  # insufficient_privilege: fn_require_admin
    "P0002": (404, None),  # no_data_found: el registro no existe
    "23505": (409, "Ya existe un registro con esos datos"),  # unique_violation
    "23503": (409, "Hace referencia a un registro que no existe"),  # foreign_key_violation
    "23514": (422, None),  # check_violation: regla de negocio o CHECK
}


@app.exception_handler(DBAPIError)
async def db_error(request: Request, exc: DBAPIError) -> JSONResponse:
    """Errores de negocio de la base -> 4xx con un mensaje para el usuario. El resto -> 500 genérico.

    Los mensajes de nuestras funciones (RAISE ... USING ERRCODE) están pensados para mostrarse.
    Los de un CHECK o índice de Postgres nombran tablas y constraints: esos no se reenvían.
    """
    diag = getattr(exc.orig, "diag", None)
    mapped = DB_ERRORS.get(getattr(diag, "sqlstate", None) or "")
    if mapped is None:
        return await unhandled_error(request, exc)
    code, fixed = mapped
    message = fixed or (diag.message_primary if diag.constraint_name is None else "Datos inválidos")
    return JSONResponse({"detail": message}, status_code=code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """El 422 por defecto devuelve el valor recibido (input), que puede ser una contraseña.
    Se responde solo dónde está el error y por qué."""
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


@app.get("/health")
def health() -> JSONResponse:
    """Liveness + conectividad con la base. Lo usan Docker y Railway."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("health: base de datos no disponible")
        return JSONResponse({"status": "error", "db": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ok", "db": "ok"})
