"""
Server entrypoint with FastAPI app defined
"""

import logging
import os
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi_utils.tasks import repeat_every
from starlette.middleware.sessions import SessionMiddleware
from tortoise.contrib.fastapi import register_tortoise

from city_search import models, serde
from city_search.legacy.api import router as legacy_api
from city_search.legacy.api import update_indexes
from city_search.settings import TORTOISE_ORM, settings

logger = logging.getLogger(__name__)

app = FastAPI(root_path=os.environ.get("API_ROOT_PATH", "/"))


@app.on_event("startup")
@repeat_every(seconds=5)  # 1 hour
async def remove_expired_tokens_task() -> None:
    await update_indexes(app)


# Register DB
register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=settings.debug,  # Do not generate schemas by default in non-debug mode!
    add_exception_handlers=True,
)

# Add middleware
if settings.secret_key == "test_secret":
    logger.warning(
        "Please, set secret key as random key on server startup (must be same for all workers)"
    )
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", include_in_schema=False)  # type: ignore
async def health() -> str:
    """Checks health of application, uncluding database and all systems"""
    return "OK"


@app.get("/", include_in_schema=False)  # type: ignore
async def index() -> Dict[str, str]:
    return {
        "message": (
            f"Hello World."
            f" Test environment variable is: {os.getenv('TEST_ENV_VAR')}"
        )
    }


@app.get(
    "/carrier",
    tags=["data"],
    response_model=List[serde.Carrier],
    summary="List carriers",
)
async def carrier_list():
    rv = list()
    for carrier in await models.Carrier.all():
        rv.append(serde.Carrier(code=carrier.code, name=carrier.name))
    return rv


@app.get(
    "/country",
    tags=["data"],
    response_model=List[serde.Country],
    summary="List countries",
)
async def country_list():
    rv = list()
    for country in await models.Country.all():
        rv.append(serde.Country(name=country.name))
    return rv


@app.get(
    "/city",
    tags=["data"],
    response_model=List[serde.City],
    summary="List cities",
)
async def city_list():
    rv = list()
    for city in await models.City.all().prefetch_related(
        "country", "names", "ranks", "ranks__carrier"
    ):
        translations = dict()
        for translation in city.names:
            translations[translation.locale] = translation.name

        ranks = dict()
        for rank in city.ranks:
            if rank.enabled:
                ranks[rank.carrier.code] = rank.rank

        if len(translations) == 0:
            name = None
        elif "en" in translations:
            name = translations["en"]
        else:
            name = translations[min(translations.keys())]

        rv.append(
            serde.City(
                code=city.code,
                country=city.country.name,
                name=name,
                translations=translations,
                ranks=ranks,
            )
        )
    return rv


# We need to specify custom openapi to add app.root_path to servers
def custom_openapi() -> Any:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="City-Search backend service",
        version="0.1.0",
        description="Provides city-search capabilities with elasticsearch",
        routes=app.routes,
    )
    openapi_schema["servers"] = [{"url": app.root_path}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # noqa

app.include_router(legacy_api)
