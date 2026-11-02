"""CRUD genérico de catálogos (patrón para las tablas simples de una sola tabla).

Cada catálogo se describe una vez en CATALOGS; de ahí salen la validación, los
endpoints y los metadatos que usa el front para dibujar la pantalla. Leer puede
cualquier usuario con sesión (los formularios necesitan las listas); escribir
solo un administrador, regla que impone la base (trigger admin_only -> 403).
Nunca se borra: se desactiva con is_active.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, create_model
from sqlalchemy import Column, insert, select, table, update

from app.auth import Auth
from app.db.session import Db

FieldType = Literal["text", "longtext", "percent", "bool"]

# Validación de cada tipo de campo (la base repite los límites con CHECK).
ANNOTATIONS: dict[FieldType, Any] = {
    "text": Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
    "longtext": Annotated[str | None, Field(default=None, max_length=500)],
    "percent": Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)],
    "bool": Annotated[bool, Field(default=False)],
}


@dataclass(frozen=True)
class CatalogField:
    name: str
    label: str
    type: FieldType


@dataclass(frozen=True)
class Catalog:
    key: str  # segmento de URL: /catalogs/{key}
    title: str
    table: str  # schema.tabla
    fields: tuple[CatalogField, ...]


NAME = CatalogField("name", "Nombre", "text")

CATALOGS = (
    Catalog("genders", "Géneros", "core.gender", (NAME,)),
    Catalog("marital-statuses", "Estados civiles", "core.marital_status", (NAME,)),
    Catalog(
        "therapy-types",
        "Tipos de terapia",
        "clinic.therapy_type",
        (NAME, CatalogField("description", "Descripción", "longtext")),
    ),
    Catalog("taxes", "Impuestos", "billing.tax", (NAME, CatalogField("percentage", "Porcentaje", "percent"))),
    Catalog(
        "payment-methods",
        "Métodos de pago",
        "billing.payment_method",
        (
            NAME,
            CatalogField("requires_reference", "Exige referencia", "bool"),
            CatalogField("requires_proof", "Exige comprobante", "bool"),
        ),
    ),
)

router = APIRouter(prefix="/catalogs", tags=["catalogs"])


class FieldMeta(BaseModel):
    name: str
    label: str
    type: FieldType


class CatalogMeta(BaseModel):
    key: str
    title: str
    fields: list[FieldMeta]


class Created(BaseModel):
    id: int


@router.get("")
def list_catalogs(_: Auth) -> list[CatalogMeta]:
    """Metadatos para el front: título y campos de cada catálogo."""
    return [
        CatalogMeta(key=c.key, title=c.title, fields=[FieldMeta(**f.__dict__) for f in c.fields])
        for c in CATALOGS
    ]


def _register(cat: Catalog) -> None:
    schema, name = cat.table.split(".")
    tbl = table(name, *(Column(c) for c in ("id", *(f.name for f in cat.fields), "is_active")), schema=schema)
    fields = {f.name: ANNOTATIONS[f.type] for f in cat.fields}
    model = cat.key.replace("-", "_")
    In = create_model(f"{model}_in", **fields)
    Update = create_model(f"{model}_update", **fields, is_active=(bool, True))
    Out = create_model(f"{model}_out", id=(int, ...), **fields, is_active=(bool, ...))

    def list_items(_: Auth, db: Db) -> list[Out]:
        rows = db.execute(select(tbl).order_by(tbl.c.is_active.desc(), tbl.c.name)).mappings()
        return [Out(**r) for r in rows]

    def create_item(body: In, _: Auth, db: Db) -> Created:
        new_id = db.execute(insert(tbl).values(**body.model_dump()).returning(tbl.c.id)).scalar_one()
        return Created(id=new_id)

    def update_item(item_id: int, body: Update, _: Auth, db: Db) -> None:
        res = db.execute(update(tbl).where(tbl.c.id == item_id).values(**body.model_dump()))
        if res.rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El registro no existe")

    path = f"/{cat.key}"
    router.add_api_route(path, list_items, methods=["GET"], summary=f"Listar {cat.title.lower()}")
    router.add_api_route(
        path, create_item, methods=["POST"], status_code=201, summary=f"Crear en {cat.title.lower()}"
    )
    router.add_api_route(
        f"{path}/{{item_id}}",
        update_item,
        methods=["PUT"],
        status_code=204,
        summary=f"Editar o desactivar en {cat.title.lower()}",
    )


for _cat in CATALOGS:
    _register(_cat)
