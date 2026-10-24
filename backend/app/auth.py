"""Login con JWT en cookie httpOnly. La base valida contraseñas y sesiones; la API solo firma y
verifica tokens. El token nunca llega a JavaScript: un XSS no puede robarlo."""

import ipaddress
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import settings
from app.db.session import Db

ALGORITHM = "HS256"
COOKIE = "ceragen_session"

router = APIRouter(prefix="/auth", tags=["auth"])
INVALID_TOKEN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")


@dataclass(frozen=True)
class CurrentUser:
    id: int
    jti: UUID


def current_user(request: Request, db: Db) -> CurrentUser:
    """Exige un JWT válido Y una sesión viva en la base (logout o usuario desactivado lo invalidan).

    Fija app.user_id en la transacción del request: la auditoría y created_by lo leen de ahí.
    """
    token = request.cookies.get(COOKIE)
    if not token:
        raise INVALID_TOKEN
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],  # fijo: nunca aceptar el algoritmo que diga el token
            options={"require": ["sub", "jti", "exp"]},
        )
        user = CurrentUser(id=int(claims["sub"]), jti=UUID(claims["jti"]))
    except (jwt.InvalidTokenError, ValueError) as err:
        raise INVALID_TOKEN from err

    owner = db.execute(text("SELECT security.fn_session_user(:jti)"), {"jti": user.jti}).scalar()
    if owner != user.id:
        raise INVALID_TOKEN
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user.id)})
    return user


Auth = Annotated[CurrentUser, Depends(current_user)]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class Role(BaseModel):
    id: int
    name: str
    is_admin: bool


class LoginOut(BaseModel):
    expires_at: datetime
    user_id: int
    roles: list[Role]


class Me(BaseModel):
    id: int
    username: str
    email: str
    roles: list[Role]


def client_ip(request: Request) -> str | None:
    """IP del cliente, o None si no es una IP (socket unix, cliente de tests): la columna es inet."""
    try:
        return str(ipaddress.ip_address(request.client.host)) if request.client else None
    except ValueError:
        return None


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Db) -> LoginOut:
    # ponytail: detrás del proxy de Railway client.host es el proxy, salvo que
    # uvicorn confíe en él (FORWARDED_ALLOW_IPS). Solo se usa para registrar la sesión.
    ip = client_ip(request)
    row = (
        db.execute(
            text(
                "SELECT status, user_id, jti, expires_at, locked_until, roles "
                "FROM security.fn_login(:u, :p, CAST(:ip AS inet), :minutes, :attempts, :lock)"
            ),
            {
                "u": body.username,
                "p": body.password,
                "ip": ip,
                "minutes": settings.jwt_expire_minutes,
                "attempts": settings.login_max_attempts,
                "lock": settings.login_lock_minutes,
            },
        )
        .mappings()
        .one()
    )

    if row["status"] == "locked":
        # Un HTTPException haría rollback del request y se perdería el bloqueo: commit antes.
        db.commit()
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"Cuenta bloqueada temporalmente hasta {row['locked_until'].isoformat()}",
        )
    if row["status"] != "ok":
        db.commit()  # mismo motivo: el intento fallido tiene que quedar contado
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    token = jwt.encode(
        {"sub": str(row["user_id"]), "jti": str(row["jti"]), "exp": row["expires_at"]},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return LoginOut(expires_at=row["expires_at"], user_id=row["user_id"], roles=row["roles"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: Auth, db: Db, response: Response) -> None:
    db.execute(text("SELECT security.fn_logout(:jti)"), {"jti": user.jti})
    # Mismos atributos que al crearla; si no, el navegador no la reconoce y no la borra.
    response.delete_cookie(
        COOKIE, httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite
    )


@router.get("/me")
def me(user: Auth, db: Db) -> Me:
    row = db.execute(text("SELECT id, username, email, roles FROM security.fn_me()")).mappings().one()
    return Me(**row)
