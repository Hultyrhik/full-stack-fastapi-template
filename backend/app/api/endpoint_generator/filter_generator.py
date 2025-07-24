from typing import Optional, Any, Dict, Callable
from fastapi import Query
from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import String, Integer, DateTime, Boolean, Float
from sqlmodel.sql.sqltypes import AutoString

from datetime import datetime


class FilterGenerator:

    # and	AND
    # or	OR
    # not	NOT
    # lt	<
    # gt	>
    # lte	<=
    # gte	>=
    # eq	=
    # neq	!=
    # in	IN
    # nin	NOT IN
    # like	LIKE

    # Операторы для разных типов полей
    TYPE_OPERATORS = {
        String: ["eq", "like", "in"],
        AutoString: ["eq", "like", "in"],  # SQLModel AutoString
        Integer: ["eq", "in"],
        Float: ["eq"],
        DateTime: ["gte", "lte", "gt", "lt"],
        Boolean: ["eq"],
    }

    # Описания операторов
    OPERATOR_DESCRIPTIONS = {
        "eq": "Точное совпадение",
        "like": "Частичное совпадение (поиск)",
        "gte": "Больше или равно",
        "lte": "Меньше или равно",
        "gt": "Больше",
        "lt": "Меньше",
        "in": "В списке (через запятую: 1,2,3)",
        "not_in": "Не в списке (через запятую: 1,2,3)",
    }

    # Маппинг операторов в FastCRUD формат (из FilterParser)
    OPERATOR_MAPPING = {
        "eq": "",  # field = value
        "like": "__ilike",  # field ILIKE %value%
        "gt": "__gt",  # field > value
        "gte": "__gte",  # field >= value
        "lt": "__lt",  # field < value
        "lte": "__lte",  # field <= value
        "in": "__in",  # field IN (values)
    }

    def __init__(self, model_class, exclude_fields: list = []):
        self.model_class = model_class
        self.exclude_fields = exclude_fields or []
        self.model_fields = self._get_model_fields()

    def _get_model_fields(self) -> Dict[str, Any]:
        inspector = inspect(self.model_class)
        fields = {}

        for column in inspector.columns:
            if column.name not in self.exclude_fields:
                fields[column.name] = column.type
        return fields

    def _get_python_type(self, sqlalchemy_type) -> str | int | float | bool | datetime:
        """Преобразует SQLAlchemy тип в Python тип"""
        type_mapping = {
            String: str,
            AutoString: str,  
            Integer: int,
            Float: float,
            DateTime: datetime,  
            Boolean: bool,
        }

        for sql_type, python_type in type_mapping.items():
            if isinstance(sqlalchemy_type, sql_type):
                return python_type

        return str  #type:ignore

    def _get_operators_for_type(self, sqlalchemy_type) -> list[str]:
        """Получить доступные операторы для типа поля"""
        for sql_type, operators in self.TYPE_OPERATORS.items():
            if isinstance(sqlalchemy_type, sql_type):
                return operators

        return ["eq"] 

    def generate_filter_function(self) -> Callable:

        function_params = []

        for field_name, field_type in self.model_fields.items():
            python_type = self._get_python_type(field_type)
            operators = self._get_operators_for_type(field_type)

            for operator in operators:
                param_name = f"filter_{field_name}_{operator}"
                alias = f"filter[{field_name}][{operator}]"
                description = f"{field_name} - {self.OPERATOR_DESCRIPTIONS.get(operator, operator)}"

                if operator == "in" or operator == "not_in":
                    function_params.append(
                        f"{param_name}: Optional[str] = Query(None, alias='{alias}', description='{description}')"
                    )
                else:
                    type_hint = "str" if python_type == str else python_type.__name__  # type: ignore
                    function_params.append(
                        f"{param_name}: Optional[{type_hint}] = Query(None, alias='{alias}', description='{description}')"
                    )
        function_def = (
            "def generated_filter_function(\n    "
            + ",\n    ".join(function_params)
            + "\n):\n"
        )

        function_def += "    filters = {}\n"

        for field_name, field_type in self.model_fields.items():
            operators = self._get_operators_for_type(field_type)

            for operator in operators:
                param_name = f"filter_{field_name}_{operator}"
                fastcrud_key = field_name + self.OPERATOR_MAPPING[operator]

                if operator == "like":
                    function_def += f"    if {param_name}:\n"
                    function_def += (
                        f"        filters['{fastcrud_key}'] = f'%{{{param_name}}}%'\n"
                    )
                elif operator == "in" or operator == "not_in":
                    function_def += f"    if {param_name}:\n"
                    function_def += f"        try:\n"
                    if self._get_python_type(field_type) == int:
                        function_def += f"            filters['{fastcrud_key}'] = [int(x.strip()) for x in {param_name}.split(',')]\n"
                    else:
                        function_def += f"            filters['{fastcrud_key}'] = [x.strip() for x in {param_name}.split(',')]\n"
                    function_def += f"        except ValueError:\n"
                    function_def += (
                        f"            pass  # Игнорируем невалидные значения\n"
                    )
                else:
                    function_def += f"    if {param_name} is not None:\n"
                    function_def += (
                        f"        filters['{fastcrud_key}'] = {param_name}\n"
                    )

        function_def += "    return filters\n"

        local_vars = {"Optional": Optional, "Query": Query, "datetime": datetime}
        exec(function_def, local_vars)

        return local_vars["generated_filter_function"]


def create_filter_dependency(model_class, exclude_fields: list = []) -> Callable:

    generator = FilterGenerator(model_class, exclude_fields)
    return generator.generate_filter_function()
