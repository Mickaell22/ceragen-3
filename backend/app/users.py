"""Gestión de usuarios. Solo administradores: lo exige la base (security.fn_require_admin)
y el handler de main.py traduce su error a 403. Aquí no se repite la regla."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import Auth, Role
from app.db.session import Db

router = APIRouter(tags=["users"])

# Misma regla que el CHECK de security.user.email (sin sumar email-validator como dependencia).
Email = Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    locked_until: datetime | None
    last_login_at: datetime | None
    roles: list[Role]


class RoleOut(Role):
    description: str | None


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9._-]{3,50}$")
    email: Email
    password: str = Field(min_length=8, max_length=72)
    role_ids: list[int] = Field(min_length=1)


class UserUpdate(BaseModel):
    email: Email
    is_active: bool
    role_ids: list[int] = Field(min_length=1)


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=72)


class Created(BaseModel):
    id: int


@router.get("/users")
def list_users(_: Auth, db: Db) -> list[UserOut]:
    return [UserOut(**r) for r in db.execute(text("SELECT * FROM security.fn_list_users()")).mappings()]


@router.get("/roles")
def list_roles(_: Auth, db: Db) -> list[RoleOut]:
    return [RoleOut(**r) for r in db.execute(text("SELECT * FROM security.fn_list_roles()")).mappings()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: Auth, db: Db) -> Created:
    new_id = db.execute(
        text("SELECT security.fn_create_user(:u, :e, :p, CAST(:r AS bigint[]))"),
        {"u": body.username, "e": body.email, "p": body.password, "r": body.role_ids},
    ).scalar_one()
    return Created(id=new_id)


@router.put("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_user(user_id: int, body: UserUpdate, _: Auth, db: Db) -> None:
    db.execute(
        text("SELECT security.fn_update_user(:id, :e, :a, CAST(:r AS bigint[]))"),
        {"id": user_id, "e": body.email, "a": body.is_active, "r": body.role_ids},
    )


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, body: PasswordReset, _: Auth, db: Db) -> None:
    db.execute(text("SELECT security.fn_reset_password(:id, :p)"), {"id": user_id, "p": body.password})


@router.post("/users/{user_id}/unlock", status_code=status.HTTP_204_NO_CONTENT)
def unlock_user(user_id: int, _: Auth, db: Db) -> None:
    db.execute(text("SELECT security.fn_unlock_user(:id)"), {"id": user_id})
