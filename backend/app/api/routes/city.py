from app.models import (
    City as ModelDB,
    CityCreate as ModelCreate,
    CityPublic as ModelPublic,
    CityUpdate as ModelUpdate,
    CityPublicWithRelation as ModelPublicWithRelation,
)

from app.api.deps import get_db
from app.api.endpoint_generator.generator import EndpointGenerator
from app.api.endpoint_generator.api_models import PaginatedResponse, GeneralAction
from app.api.endpoint_generator.params_funcs import get_prefix, get_tags
from fastapi import APIRouter


router = APIRouter(
    prefix=get_prefix(ModelDB), tags=get_tags(ModelDB)  # type:ignore
)

# Write custom routes between router and generated_endpoints
# to not be captured in GET, DELETE or PATCH /{id} path.
# Or create a new router with APIRouter and join to fastapi app separately
# Example below
# @router.get("/tessssstttttttt")
# def gh():
#     return 443322


generated_endpoints = EndpointGenerator(
    router=router,
    session=get_db,
    model_db=ModelDB,  # type: ignore
    model_create=ModelCreate,  # type: ignore
    model_public=ModelPublicWithRelation,  # type: ignore
    model_public_with_pagination=PaginatedResponse[ModelPublicWithRelation],  # type: ignore
    model_update=ModelUpdate,  # type: ignore
)

router = generated_endpoints.get_router()
