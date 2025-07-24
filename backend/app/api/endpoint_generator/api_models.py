from pydantic import BaseModel
from enum import Enum
from sqlmodel import SQLModel, Field
from typing import Sequence, Generic, TypeVar, Annotated
from fastapi import Depends
from app.models import Status

exclude_fields = ["created_by", "updated_by", "updated_at", "status_id"]


class SQLOperators(str, Enum):
    eq = "eq"
    ilike = "ilike"
    _in = "in"
    gte = "gte"
    lte = "lte"
    gt = "gt"
    lt = "lt"


T = TypeVar("T", bound=SQLModel)


class PaginatedResponse(BaseModel, Generic[T]):
    data: Sequence[T]
    page: int
    per_page: int
    total_records: int
    pages: int


class PaginationParams(SQLModel):
    page: int = Field(default=1, ge=1, description="Текущая страница")
    per_page: int = Field(
        default=50, ge=1, le=1000, description="Сколько в записей выводится за один раз"
    )


class CommonQueryParams(BaseModel):
    status: Status = Status.active
    sort: str | None = None
    pagination: Annotated[PaginationParams, Depends()]


class GeneralAction(str, Enum):
    VIEW = "get-one"
    LIST = "get-list"
    CREATE = "create-one"
    UPDATE = "update-one"
    DELETE = "delete-one"
    RESTORE = "restore-one"
