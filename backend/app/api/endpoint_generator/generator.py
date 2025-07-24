from sqlmodel import SQLModel, Session, select
from enum import Enum
from typing import Callable, Annotated
from pydantic import BaseModel
from fastapi import params, APIRouter, Depends, HTTPException
from app.api.endpoint_generator.api_models import (
    GeneralAction,
    CommonQueryParams,
    exclude_fields,
)
from app.api.endpoint_generator.params_funcs import (
    set_status,
    set_filters,
    set_sorting,
    set_offset_limit,
)
from app.models import Status
from app.api.deps import CurrentUser
from app.api.endpoint_generator.filter_generator import create_filter_dependency


class EndpointGenerator:
    def __init__(
        self,
        *,
        session: Callable,
        path: str | None = None,
        tags: list[str | Enum] | None = None,
        router: APIRouter | None = None,
        model_db: SQLModel,
        model_create: SQLModel,
        model_update: SQLModel,
        model_public: SQLModel,
        model_public_with_pagination: BaseModel,
        included_actions: list[str] = [
            GeneralAction.VIEW,
            GeneralAction.LIST,
            GeneralAction.CREATE,
            GeneralAction.UPDATE,
            GeneralAction.DELETE,
            GeneralAction.RESTORE,
        ],
        dependencies_view: list[params.Depends] | None = None,
        dependencies_list: list[params.Depends] | None = None,
        dependencies_create: list[params.Depends] | None = None,
        dependencies_update: list[params.Depends] | None = None,
        dependencies_delete: list[params.Depends] | None = None,
        dependencies_restore: list[params.Depends] | None = None,
        deleted_actions: list[str] = [],
    ) -> None:
        endpoint_name = model_db.__name__.lower()
        self.session = session
        self.path = path if path else f"/{endpoint_name}"
        self.tags = tags if tags else [endpoint_name]
        self.model_db = model_db
        self.model_create = model_create
        self.model_update = model_update
        self.model_public = model_public
        self.model_public_with_pagination = model_public_with_pagination
        self.included_actions = included_actions
        self.deleted_actions = deleted_actions
        self.dependencies_view = dependencies_view
        self.dependencies_list = dependencies_list
        self.dependencies_create = dependencies_create
        self.dependencies_update = dependencies_update
        self.dependencies_delete = dependencies_delete
        self.dependencies_restore = dependencies_restore
        self.router = router if router else APIRouter(prefix=self.path, tags=self.tags)

    def _get_one_endpoint(self):
        def _get_one(
            session: Annotated[Session, Depends(self.session)],
            current_user: CurrentUser,
            id: int,
        ):
            model_db = session.get(self.model_db, id)  # type: ignore
            if not model_db:
                raise HTTPException(status_code=403, detail=f"id {id} is not found")
            return model_db

        return _get_one

    def _get_list_endpoint(self):
        def _get_list(
            *,
            session: Annotated[Session, Depends(self.session)],
            current_user: CurrentUser,
            query_params: Annotated[CommonQueryParams, Depends()],
            filters: dict = Depends(
                create_filter_dependency(self.model_db, exclude_fields)
            ),
        ):
            statement = select(self.model_db)  # type: ignore
            statement = set_status(
                statement=statement,
                model_db=self.model_db,  # type: ignore
                status=query_params.status,
            )
            statement = set_filters(
                statement=statement,
                model_db=self.model_db,  # type: ignore
                filters=filters,
            )
            statement = set_sorting(
                statement=statement,
                model_db=self.model_db,  # type: ignore
                sort=query_params.sort,
            )
            return set_offset_limit(
                session=session,
                pagination=query_params.pagination,
                model_db=self.model_db,  # type: ignore
                statement=statement,
            )

        return _get_list

    def _create_one_endpoint(self):
        def _create_one(
            session: Annotated[Session, Depends(self.session)],
            current_user: CurrentUser,
            body_in: self.model_create,  # type: ignore
        ):

            model_db = self.model_db.model_validate(body_in)
            try:
                session.add(model_db)
                session.commit()
                session.refresh(model_db)
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail="Error during creating. Please check input parameters",
                )
            return model_db

        return _create_one

    def _update_one_endpoint(self):
        def _update_one(
            session: Annotated[Session, Depends(self.session)],
            current_user: CurrentUser,
            body_in: self.model_update,  # type: ignore
            id: int,
        ):
            update_data = body_in.model_dump(exclude_unset=True)
            model_db = session.get(self.model_db, id)  # type: ignore
            if not model_db:
                raise HTTPException(status_code=403, detail=f"id {id} is not found")
            try:

                model_db.sqlmodel_update(update_data)
                session.add(model_db)
                session.commit()
                session.refresh(model_db)
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail="Error during updating. Please check input parameters",
                )
            return model_db

        return _update_one

    def _delete_one_endpoint(self):
        def _delete_one(
            session: Annotated[Session, Depends(self.session)],
            current_user: CurrentUser,
            id: int,
        ):
            model_db = session.exec(
                select(self.model_db).where(  # type: ignore
                    self.model_db.id == id, self.model_db.status_id != Status.deleted  # type: ignore
                )
            ).first()
            if not model_db:
                raise HTTPException(status_code=404, detail=f"id {id} doesn't exist")
            model_db.status_id = Status.deleted
            session.add(model_db)
            session.commit()
            session.refresh(model_db)
            return model_db

        return _delete_one

    def _restore_one_endpoint(self):
        def _restore_one(
            session: Annotated[Session, Depends(self.session)],
            current_user: CurrentUser,
            id: int,
        ):
            model_db = session.exec(
                select(self.model_db).where(  # type: ignore
                    self.model_db.id == id, self.model_db.status_id == Status.deleted  # type: ignore
                )
            ).first()
            if not model_db:
                raise HTTPException(
                    status_code=404, detail=f"id {id} doesn't exist to restore"
                )
            model_db.status_id = Status.active
            session.add(model_db)
            session.commit()
            session.refresh(model_db)
            return model_db

        return _restore_one

    def get_path(self, is_id_in_path=False, is_restore=False):
        if is_restore:
            return f"/{{id}}/restore"
        if is_id_in_path:
            return f"/{{id}}"
        else:
            return ""

    def get_router(self):

        if (GeneralAction.VIEW in self.included_actions) and (
            GeneralAction.VIEW not in self.deleted_actions
        ):
            self.router.add_api_route(
                path=self.get_path(is_id_in_path=True),
                endpoint=self._get_one_endpoint(),
                methods=["GET"],
                tags=self.tags,
                dependencies=self.dependencies_view,
                response_model=self.model_public,
                operation_id=f"1_get_one_{self.model_db.__name__}",
                description=f"Read a single {self.model_db.__name__} row from the database by its primary key.",
            )
        if (GeneralAction.LIST in self.included_actions) and (
            GeneralAction.LIST not in self.deleted_actions
        ):
            self.router.add_api_route(
                path=self.get_path(is_id_in_path=False),
                endpoint=self._get_list_endpoint(),
                methods=["GET"],
                tags=self.tags,
                dependencies=self.dependencies_list,
                response_model=self.model_public_with_pagination,
                operation_id=f"2_get_list_{self.model_db.__name__}",
                description=f"Read multiple {self.model_db.__name__} rows from the database.",
            )
        if (GeneralAction.CREATE in self.included_actions) and (
            GeneralAction.CREATE not in self.deleted_actions
        ):
            self.router.add_api_route(
                path=self.get_path(is_id_in_path=False),
                endpoint=self._create_one_endpoint(),
                methods=["POST"],
                tags=self.tags,
                dependencies=self.dependencies_create,
                response_model=self.model_public,
                operation_id=f"3_create_one_{self.model_db.__name__}",
                description=f"Create a {self.model_db.__name__} row in the database.",
            )
        if (GeneralAction.UPDATE in self.included_actions) and (
            GeneralAction.UPDATE not in self.deleted_actions
        ):
            self.router.add_api_route(
                path=self.get_path(is_id_in_path=True),
                endpoint=self._update_one_endpoint(),
                methods=["PATCH"],
                tags=self.tags,
                dependencies=self.dependencies_update,
                response_model=self.model_public,
                operation_id=f"4_update_one_{self.model_db.__name__}",
                description=f"Update a {self.model_db.__name__} row in the database.",
            )
        if (GeneralAction.DELETE in self.included_actions) and (
            GeneralAction.DELETE not in self.deleted_actions
        ):
            self.router.add_api_route(
                path=self.get_path(is_id_in_path=True),
                endpoint=self._delete_one_endpoint(),
                methods=["DELETE"],
                tags=self.tags,
                dependencies=self.dependencies_delete,
                response_model=self.model_public,
                operation_id=f"5_delete_one_{self.model_db.__name__}",
                description=f"Delete a {self.model_db.__name__} row in the database.",
            )
        if (GeneralAction.RESTORE in self.included_actions) and (
            GeneralAction.RESTORE not in self.deleted_actions
        ):
            self.router.add_api_route(
                path=self.get_path(is_id_in_path=True, is_restore=True),
                endpoint=self._restore_one_endpoint(),
                methods=["PATCH"],
                tags=self.tags,
                dependencies=self.dependencies_restore,
                response_model=self.model_public,
                operation_id=f"6_restore_one_{self.model_db.__name__}",
                description=f"Rstore a {self.model_db.__name__} row in the database.",
            )
        return self.router
