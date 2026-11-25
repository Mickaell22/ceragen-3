"""Pacientes y clientes (quien paga). Ambos son personas de core.person.

Escribir exige la pantalla /patients (o ser admin): lo impone la base con el
trigger menu_guard y el handler de main.py lo traduce a 403. Las relaciones
(alergias, enfermedades) se sincronizan con borrado lógico.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from app.auth import Auth
from app.db.session import Db

router = APIRouter(tags=["patients"])

Phone = Annotated[str, Field(pattern=r"^\+?[0-9 -]{7,20}$")]
Email = Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Name = Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")]
BloodType = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class PersonIn(BaseModel):
    # La validez de la cédula y el formato del RUC/pasaporte los decide la base (CHECK).
    identification_type: Literal["cedula", "ruc", "passport"]
    identification: str = Field(min_length=5, max_length=20)
    first_name: Name
    last_name: Name
    birth_date: date | None = None
    gender_id: int | None = None
    marital_status_id: int | None = None
    email: Email | None = None
    phone: Phone | None = None
    address: str | None = Field(default=None, max_length=300)


class PersonOut(PersonIn):
    id: int


class PatientIn(BaseModel):
    person: PersonIn
    client_id: int | None = None  # None: el paciente se paga solo
    blood_type: BloodType | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=200)
    emergency_contact_phone: Phone | None = None
    notes: str | None = Field(default=None, max_length=2000)
    allergy_ids: list[int] = []
    disease_ids: list[int] = []


class PatientUpdate(PatientIn):
    is_active: bool = True


class PatientRow(BaseModel):
    id: int
    full_name: str
    identification: str
    phone: str | None
    client_name: str | None
    is_active: bool


class ClientRow(BaseModel):
    id: int
    full_name: str
    identification: str
    is_active: bool


class PatientOut(BaseModel):
    id: int
    person: PersonOut
    client_id: int | None
    client: ClientRow | None  # para mostrarlo en el formulario sin otra consulta
    blood_type: BloodType | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    notes: str | None
    allergy_ids: list[int]
    disease_ids: list[int]
    is_active: bool


class ClientIn(BaseModel):
    person: PersonIn


class Created(BaseModel):
    id: int


PERSON_FIELDS = tuple(PersonIn.model_fields)


def upsert_person(db: Connection, person: PersonIn) -> int:
    """Crea la persona o, si su identificación ya existe, actualiza sus datos.

    Así una misma persona puede ser cliente y paciente sin duplicarse.
    """
    cols = ", ".join(PERSON_FIELDS)
    params = ", ".join(f":{f}" for f in PERSON_FIELDS)
    updates = ", ".join(f"{f} = EXCLUDED.{f}" for f in PERSON_FIELDS[2:])
    data = person.model_dump()
    data["identification"] = data["identification"].strip().upper()
    return db.execute(
        text(
            f"INSERT INTO core.person ({cols}) VALUES ({params}) "  # noqa: S608 (columnas fijas del modelo)
            f"ON CONFLICT (identification_type, identification) DO UPDATE SET {updates} RETURNING id"
        ),
        data,
    ).scalar_one()


# Únicas tablas de relación que sync_links acepta: el SQL se arma con estos nombres, nunca con el request.
LINK_TABLES = {"clinic.patient_allergy": "allergy_id", "clinic.patient_disease": "disease_id"}


def sync_links(db: Connection, table: str, patient_id: int, ids: list[int]) -> None:
    """Deja activas exactamente las filas del paciente con esos ids; las demás se desactivan."""
    col = LINK_TABLES[table]
    params = {"p": patient_id, "ids": ids}
    off = f"UPDATE {table} SET is_active = false WHERE patient_id = :p AND is_active AND {col} <> ALL(:ids)"  # noqa: S608
    on = (
        f"INSERT INTO {table} (patient_id, {col}) SELECT :p, unnest(CAST(:ids AS bigint[])) "  # noqa: S608
        f"ON CONFLICT (patient_id, {col}) DO UPDATE SET is_active = true WHERE NOT {table}.is_active"
    )
    db.execute(text(off), params)
    db.execute(text(on), params)


PATIENT_FIELDS = ("client_id", "blood_type", "emergency_contact_name", "emergency_contact_phone", "notes")


def save_links(db: Connection, patient_id: int, body: PatientIn) -> None:
    sync_links(db, "clinic.patient_allergy", patient_id, body.allergy_ids)
    sync_links(db, "clinic.patient_disease", patient_id, body.disease_ids)


@router.get("/patients")
def list_patients(
    _: Auth,
    db: Db,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[PatientRow]:
    """Búsqueda por nombre, apellido o identificación."""
    rows = db.execute(
        text("""
            SELECT pa.id, pe.last_name || ' ' || pe.first_name AS full_name, pe.identification, pe.phone,
                   cp.last_name || ' ' || cp.first_name AS client_name, pa.is_active
            FROM clinic.patient pa
            JOIN core.person pe ON pe.id = pa.person_id
            LEFT JOIN core.client c ON c.id = pa.client_id
            LEFT JOIN core.person cp ON cp.id = c.person_id
            WHERE :q = '' OR pe.identification ILIKE :like
               OR (pe.last_name || ' ' || pe.first_name) ILIKE :like
               OR (pe.first_name || ' ' || pe.last_name) ILIKE :like
            ORDER BY pa.is_active DESC, lower(pe.last_name), lower(pe.first_name)
            LIMIT :limit
        """),
        {"q": q.strip(), "like": f"%{q.strip()}%", "limit": limit},
    ).mappings()
    return [PatientRow(**r) for r in rows]


@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, _: Auth, db: Db) -> PatientOut:
    row = (
        db.execute(
            text("""
                SELECT pa.*, to_jsonb(pe) AS person,
                       (SELECT jsonb_build_object(
                                   'id', c.id, 'full_name', cp.last_name || ' ' || cp.first_name,
                                   'identification', cp.identification, 'is_active', c.is_active)
                        FROM core.client c JOIN core.person cp ON cp.id = c.person_id
                        WHERE c.id = pa.client_id) AS client,
                       ARRAY(SELECT allergy_id FROM clinic.patient_allergy
                             WHERE patient_id = pa.id AND is_active ORDER BY allergy_id) AS allergy_ids,
                       ARRAY(SELECT disease_id FROM clinic.patient_disease
                             WHERE patient_id = pa.id AND is_active ORDER BY disease_id) AS disease_ids
                FROM clinic.patient pa JOIN core.person pe ON pe.id = pa.person_id
                WHERE pa.id = :id
            """),
            {"id": patient_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El paciente no existe")
    return PatientOut(**row)


@router.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(body: PatientIn, _: Auth, db: Db) -> Created:
    person_id = upsert_person(db, body.person)
    patient_id = db.execute(
        text(
            "INSERT INTO clinic.patient (person_id, client_id, blood_type, emergency_contact_name, "
            "emergency_contact_phone, notes) VALUES (:person_id, :client_id, :blood_type, "
            ":emergency_contact_name, :emergency_contact_phone, :notes) RETURNING id"
        ),
        {"person_id": person_id, **body.model_dump(include=set(PATIENT_FIELDS))},
    ).scalar_one()
    save_links(db, patient_id, body)
    return Created(id=patient_id)


@router.put("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_patient(patient_id: int, body: PatientUpdate, _: Auth, db: Db) -> None:
    person_id = db.execute(
        text(
            "UPDATE clinic.patient SET client_id = :client_id, blood_type = :blood_type, "
            "emergency_contact_name = :emergency_contact_name, "
            "emergency_contact_phone = :emergency_contact_phone, notes = :notes, is_active = :is_active "
            "WHERE id = :id RETURNING person_id"
        ),
        {"id": patient_id, **body.model_dump(include={*PATIENT_FIELDS, "is_active"})},
    ).scalar_one_or_none()
    if person_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El paciente no existe")
    # Cambiar la identificación de la persona es cambiar de persona: no se permite aquí.
    data = body.person.model_dump(exclude={"identification_type", "identification"})
    sets = ", ".join(f"{f} = :{f}" for f in data)
    db.execute(text(f"UPDATE core.person SET {sets} WHERE id = :pid"), {**data, "pid": person_id})  # noqa: S608
    save_links(db, patient_id, body)


@router.get("/clients")
def list_clients(
    _: Auth,
    db: Db,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[ClientRow]:
    rows = db.execute(
        text("""
            SELECT c.id, pe.last_name || ' ' || pe.first_name AS full_name, pe.identification, c.is_active
            FROM core.client c JOIN core.person pe ON pe.id = c.person_id
            WHERE c.is_active AND (:q = '' OR pe.identification ILIKE :like
                  OR (pe.last_name || ' ' || pe.first_name) ILIKE :like)
            ORDER BY lower(pe.last_name), lower(pe.first_name)
            LIMIT :limit
        """),
        {"q": q.strip(), "like": f"%{q.strip()}%", "limit": limit},
    ).mappings()
    return [ClientRow(**r) for r in rows]


@router.post("/clients", status_code=status.HTTP_201_CREATED)
def create_client(body: ClientIn, _: Auth, db: Db) -> Created:
    person_id = upsert_person(db, body.person)
    client_id = db.execute(
        text("INSERT INTO core.client (person_id) VALUES (:p) RETURNING id"), {"p": person_id}
    ).scalar_one()
    return Created(id=client_id)
