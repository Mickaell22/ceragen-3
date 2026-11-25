"""Historial médico. Los permisos los impone la base: leer y escribir exigen la
pantalla /medical-history (fn_patient_history, menu_guard) y corregir una
entrada, ser su autor (trigger author_only). La API solo traduce a 403."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import Auth
from app.db.session import Db

router = APIRouter(tags=["medical-history"])


class EntryIn(BaseModel):
    recorded_on: date | None = None  # None: hoy (lo pone la base)
    reason: Annotated[str, Field(min_length=1, max_length=300, pattern=r"\S")]
    diagnosis: str | None = Field(default=None, max_length=2000)
    treatment: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)


class EntryUpdate(EntryIn):
    recorded_on: date
    is_active: bool = True


class EntryOut(BaseModel):
    id: int
    recorded_on: date
    reason: str
    diagnosis: str | None
    treatment: str | None
    notes: str | None
    author: str | None
    author_id: int | None
    created_at: datetime
    updated_at: datetime | None
    is_active: bool


class Created(BaseModel):
    id: int


@router.get("/patients/{patient_id}/history")
def list_history(patient_id: int, _: Auth, db: Db) -> list[EntryOut]:
    rows = db.execute(text("SELECT * FROM clinic.fn_patient_history(:p)"), {"p": patient_id}).mappings()
    return [EntryOut(**r) for r in rows]


@router.post("/patients/{patient_id}/history", status_code=status.HTTP_201_CREATED)
def add_entry(patient_id: int, body: EntryIn, _: Auth, db: Db) -> Created:
    entry_id = db.execute(
        text(
            "INSERT INTO clinic.medical_history "
            "(patient_id, recorded_on, reason, diagnosis, treatment, notes) "
            "VALUES (:p, coalesce(:recorded_on, current_date), :reason, :diagnosis, :treatment, :notes) "
            "RETURNING id"
        ),
        {"p": patient_id, **body.model_dump()},
    ).scalar_one()
    return Created(id=entry_id)


@router.put("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_entry(entry_id: int, body: EntryUpdate, _: Auth, db: Db) -> None:
    res = db.execute(
        text(
            "UPDATE clinic.medical_history SET recorded_on = :recorded_on, reason = :reason, "
            "diagnosis = :diagnosis, treatment = :treatment, notes = :notes, is_active = :is_active "
            "WHERE id = :id"
        ),
        {"id": entry_id, **body.model_dump()},
    )
    if res.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La entrada no existe")
