from sqlmodel.sql.expression import SelectOfScalar
from sqlmodel import SQLModel, select, func, Session, asc, desc
from sqlalchemy import inspect
from fastapi import HTTPException
from typing import Any

from app.models import Status, SuperBase
from app.api.endpoint_generator.api_models import (
    SQLOperators,
    PaginationParams,
    PaginatedResponse,
)
from sqlalchemy.exc import ArgumentError


def set_status(statement: SelectOfScalar, model_db: SuperBase, status: Status):
    return statement.where(model_db.status_id == status)


# TODO
# Unused. If not needed - delete. Decida if needed.
def get_model_fields(model_db: SQLModel, exclude_fields: list[str] = []) -> list[str]:
    """Получить поля модели с их типами"""
    inspector = inspect(model_db)
    fields = {}
    if not inspector:
        return []
    fields = []
    for column in inspector.columns:
        if column.name not in exclude_fields:
            fields.append(column.name)
    return fields


def parse_sort_string(sort_string: str) -> tuple[list[str], list[str]]:
    """
    Парсит строку сортировки в массивы полей и направлений

    Формат: field1,-field2,field3
    - field1 → ASC (по умолчанию)
    - -field2 → DESC (минус означает убывание)
    - field3 → ASC

    Возвращает:
        tuple[sort_columns, sort_orders]

    Пример:
        parse_sort_string("name,-created_at,id")
        → (["name", "created_at", "id"], ["ASC", "DESC", "ASC"])
    """
    if not sort_string or not sort_string.strip():
        return [], []

    sort_columns = []
    sort_orders = []

    # Разбиваем по запятой и обрабатываем каждое поле
    fields = [field.strip() for field in sort_string.split(",") if field.strip()]

    for field in fields:
        if field.startswith("-"):
            # Убираем минус и добавляем DESC
            column_name = field[1:].strip()
            if column_name:  # Проверяем что после минуса есть название поля
                sort_columns.append(column_name)
                sort_orders.append("desc")
        else:
            # Обычное поле - ASC
            sort_columns.append(field)
            sort_orders.append("asc")

    return sort_columns, sort_orders


def apply_sorting(
    statement: SelectOfScalar,
    model_db: SQLModel,
    sort_columns: str | list[str],
    sort_orders: str | list[str] | None = None,
) -> SelectOfScalar:
    if sort_orders and not sort_columns:
        raise ValueError("Sort orders provided without corresponding sort columns.")

    if sort_columns:
        if not isinstance(sort_columns, list):
            sort_columns = [sort_columns]

        if sort_orders:
            if not isinstance(sort_orders, list):
                sort_orders = [sort_orders] * len(sort_columns)
            if len(sort_columns) != len(sort_orders):
                raise ValueError(
                    "The length of sort_columns and sort_orders must match."
                )

            for idx, order in enumerate(sort_orders):
                if order not in ["asc", "desc"]:
                    raise ValueError(
                        f"Invalid sort order: {order}. Only 'asc' or 'desc' are allowed."
                    )

        validated_sort_orders = (
            ["asc"] * len(sort_columns) if not sort_orders else sort_orders
        )

        for idx, column_name in enumerate(sort_columns):
            column = getattr(model_db, column_name, None)
            if not column:
                raise ArgumentError(f"Invalid column name: {column_name}")

            order = validated_sort_orders[idx]
            statement = statement.order_by(asc(column) if order == "asc" else desc(column))

    return statement


def set_filters(
    statement: SelectOfScalar, model_db: SuperBase, filters: dict[str, Any]
):
    if not filters:
        return statement
    new_dict = {}
    for k, v in filters.items():
        if k.startswith("created_at"):
            new_dict[k] = v.isoformat()
        else:
            new_dict[k] = v

    for k, v in filters.items():
        begin = ""
        end = SQLOperators.eq
        elems = k.split("__")
        begin = elems[0]
        if len(elems) > 1:
            end = elems[1]

        column = getattr(model_db, begin, None)
        if not column:
            HTTPException(
                status_code=400,
                detail=f"No column {column} in {model_db.__name__} table model",
            )
        if end == SQLOperators.eq:
            condition = column == v
            statement = statement.filter(condition)
        elif end == SQLOperators.ilike:
            condition = column.ilike(v)  # type: ignore
            statement = statement.filter(condition)
            pass
        elif end == SQLOperators._in:
            condition = column.in_(v)  # type: ignore
            statement = statement.filter(condition)
        elif end == SQLOperators.gte:
            condition = column >= v
            statement = statement.filter(condition)
        elif end == SQLOperators.lte:
            condition = column <= v
            statement = statement.filter(condition)
        elif end == SQLOperators.gt:
            condition = column > v
            statement = statement.filter(condition)
        elif end == SQLOperators.lt:
            condition = column < v
            statement = statement.filter(condition)
        else:
            raise HTTPException(status_code=422, detail="Unsupported SQL operator")

    return statement


def set_sorting(statement: SelectOfScalar, model_db: SuperBase, sort: str | None):

    if sort == None:
        return statement
    sort_columns, sort_orders = parse_sort_string(sort) if sort else ([], [])
    statement = apply_sorting(
        stmt=statement,
        model_db=model_db,
        sort_columns=sort_columns,
        sort_orders=sort_orders,
    )
    return statement


def set_offset_limit(
    session: Session,
    pagination: PaginationParams,
    model_db: SuperBase,
    statement,
):
    count_statement = select(func.count()).select_from(statement)
    total = session.exec(count_statement).one()

    pages = (total + pagination.per_page - 1) // pagination.per_page

    offset = (pagination.page - 1) * pagination.per_page

    statement = statement.offset(offset).limit(pagination.per_page)
    result = session.exec(statement).all()
    return PaginatedResponse(
        data=result,
        page=pagination.page,
        per_page=pagination.per_page,
        total_records=total,
        pages=pages,
    )


def get_prefix(model_db: SQLModel) -> str:
    endpoint_name = model_db.__name__.lower()
    return f"/{endpoint_name}"


def get_tags(model_db: SQLModel) -> list[str]:
    endpoint_name = model_db.__name__.lower()
    return [endpoint_name]
